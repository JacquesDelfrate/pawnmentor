from __future__ import annotations

from typing import NotRequired, TypedDict

import chess
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.engine.peer import build_peer_pool
from app.engine.pool import EnginePool
from app.engine.trajectory import MoveEval, eval_trajectory
from app.graph.nodes.classify import Classification, classify_error
from app.graph.nodes.diagnosis import Diagnosis, diagnose_error
from app.graph.nodes.dialogue import CoachingMessage, generate_dialogue
from app.graph.nodes.filter import FlaggedError, filter_errors
from app.graph.nodes.motifs import classify_motifs
from app.graph.state import MotifState
from app.llm.client import LLMClient


def build_motifs_graph() -> CompiledStateGraph[MotifState, None, MotifState, MotifState]:
    graph: StateGraph[MotifState, None, MotifState, MotifState] = StateGraph(MotifState)
    graph.add_node("classify_motifs", classify_motifs)
    graph.add_edge(START, "classify_motifs")
    graph.add_edge("classify_motifs", END)
    return graph.compile(checkpointer=InMemorySaver())


class PipelineState(TypedDict):
    """State for the full game-review pipeline: scan -> filter -> diagnose ->
    classify -> dialogue. Defined here rather than in state.py because it
    needs types from every node module, each of which would otherwise need
    to import this file back -- this file already sits downstream of all of
    them, so it's the one place that can reference everything without a
    cycle.
    """

    fen: str
    moves_uci: list[str]
    player_color: bool
    player_rating: int
    move_evals: NotRequired[list[MoveEval]]
    flagged_errors: NotRequired[list[FlaggedError]]
    diagnoses: NotRequired[list[Diagnosis]]
    classifications: NotRequired[list[Classification]]
    coaching_messages: NotRequired[list[CoachingMessage]]


def build_pipeline_graph(
    full_pool: EnginePool,
    stockfish_path: str,
    llm: LLMClient,
    *,
    scan_depth: int = 16,
    diagnosis_depth: int = 20,
) -> CompiledStateGraph[PipelineState, None, PipelineState, PipelineState]:
    """Wires the complete deterministic-then-LLM pipeline. Engine pools and
    the LLM client are runtime dependencies captured by closure in each node
    function, not stored in graph state -- state is the checkpointed data
    (scan results, flagged errors, diagnoses...), not live resources like
    pooled engine processes or an HTTP client.

    `stockfish_path` builds a fresh ENGINE_PEER pool per compiled graph
    (peer strength depends on the specific player being reviewed, set per
    call via `player_rating` in state -- the pool itself only needs
    rebuilding when the *path* changes, so one per graph is enough).
    """

    def scan(state: PipelineState) -> dict[str, list[MoveEval]]:
        board = chess.Board(state["fen"])
        moves = [chess.Move.from_uci(uci) for uci in state["moves_uci"]]
        move_evals = eval_trajectory(full_pool, board, moves, depth=scan_depth)
        return {"move_evals": move_evals}

    def filter_node(state: PipelineState) -> dict[str, list[FlaggedError]]:
        # Spins up and tears down one ENGINE_PEER process per game review
        # (not per candidate move within it -- filter_errors reuses this
        # single pool across all its reachability checks). Not a per-call
        # process spawn in the sense the "never spawn a Stockfish process
        # per call" convention is warning against, but it's also not a
        # long-lived pooled resource the way full_pool is; a rating-keyed
        # peer-pool cache would fix that and is a reasonable follow-up if
        # review volume ever makes this a real cost.
        with build_peer_pool(stockfish_path, state["player_rating"]) as peer_pool:
            flagged = filter_errors(
                state["move_evals"],
                state["player_color"],
                state["player_rating"],
                peer_pool,
                full_pool,
                depth=scan_depth,
            )
        return {"flagged_errors": flagged}

    def diagnose_node(state: PipelineState) -> dict[str, list[Diagnosis]]:
        diagnoses = [
            diagnose_error(full_pool, flagged, depth=diagnosis_depth)
            for flagged in state["flagged_errors"]
        ]
        return {"diagnoses": diagnoses}

    def classify_node(state: PipelineState) -> dict[str, list[Classification]]:
        classifications = [classify_error(diagnosis) for diagnosis in state["diagnoses"]]
        return {"classifications": classifications}

    async def dialogue_node(state: PipelineState) -> dict[str, list[CoachingMessage]]:
        messages = [
            await generate_dialogue(llm, classification, state["player_rating"])
            for classification in state["classifications"]
        ]
        return {"coaching_messages": messages}

    graph: StateGraph[PipelineState, None, PipelineState, PipelineState] = StateGraph(PipelineState)
    graph.add_node("scan", scan)
    graph.add_node("filter", filter_node)
    graph.add_node("diagnose", diagnose_node)
    graph.add_node("classify", classify_node)
    graph.add_node("dialogue", dialogue_node)

    graph.add_edge(START, "scan")
    graph.add_edge("scan", "filter")
    graph.add_edge("filter", "diagnose")
    graph.add_edge("diagnose", "classify")
    graph.add_edge("classify", "dialogue")
    graph.add_edge("dialogue", END)

    return graph.compile(checkpointer=InMemorySaver())
