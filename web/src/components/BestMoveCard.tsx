import { Chessboard } from "react-chessboard";
import type { BestMove } from "../api";

function formatScore(bestMove: BestMove): string | null {
  if (bestMove.mate_in !== null) {
    const side = bestMove.mate_in > 0 ? "You" : "Your opponent";
    return `${side} mate in ${Math.abs(bestMove.mate_in)}`;
  }
  if (bestMove.score_cp === null) return null;
  const pawns = bestMove.score_cp / 100;
  const sign = pawns > 0 ? "+" : "";
  return `${sign}${pawns.toFixed(2)} for you`;
}

export function BestMoveCard({ bestMove }: { bestMove: BestMove }) {
  const score = formatScore(bestMove);

  return (
    <div className="rounded-lg border border-amber-400/60 bg-amber-50 dark:bg-amber-950/30 p-4 flex flex-col md:flex-row gap-4">
      <div className="w-full md:w-64 shrink-0">
        <Chessboard options={{ position: bestMove.fen, showNotation: true }} />
      </div>
      <div className="flex-1 space-y-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide">Current position</h3>

        {bestMove.is_game_over ? (
          <p className="text-sm text-neutral-600 dark:text-neutral-400">
            This game is finished &mdash; nothing left to play.
          </p>
        ) : !bestMove.is_player_turn ? (
          <p className="text-sm text-neutral-600 dark:text-neutral-400">
            It&rsquo;s your opponent&rsquo;s move. Nothing to recommend until they reply.
          </p>
        ) : (
          <>
            <p className="text-sm">
              Engine recommends{" "}
              <span className="font-mono font-semibold text-base">{bestMove.best_move_san}</span>
              {score && <span className="text-neutral-500"> ({score})</span>}
            </p>
            {bestMove.pv_san.length > 1 && (
              <p className="text-sm text-neutral-600 dark:text-neutral-400">
                Expected continuation:{" "}
                <span className="font-mono">{bestMove.pv_san.slice(0, 6).join(" ")}</span>
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
