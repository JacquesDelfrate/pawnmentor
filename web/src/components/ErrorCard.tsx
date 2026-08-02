import { Chessboard } from "react-chessboard";
import type { FlaggedError } from "../api";

const CATEGORY_LABELS: Record<string, string> = {
  hung_piece: "Hung piece",
  allowed_fork: "Allowed a fork",
  walked_into_pin: "Walked into a pin",
  bad_trade: "Bad trade",
  other_tactical_oversight: "Tactical oversight",
};

function formatDelta(deltaCp: number): string {
  const pawns = Math.abs(deltaCp) / 100;
  return `-${pawns.toFixed(1)} pawns`;
}

export function ErrorCard({ error }: { error: FlaggedError }) {
  return (
    <div className="rounded-lg border border-neutral-300 dark:border-neutral-700 p-4 flex flex-col md:flex-row gap-4">
      <div className="w-full md:w-64 shrink-0">
        <Chessboard options={{ position: error.fen_before, showNotation: true }} />
      </div>
      <div className="flex-1 space-y-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-semibold uppercase tracking-wide px-2 py-1 rounded bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300">
            {CATEGORY_LABELS[error.category] ?? error.category}
          </span>
          <span className="text-sm text-neutral-500">{formatDelta(error.delta_cp)}</span>
        </div>
        <p className="text-sm">
          You played <span className="font-mono font-semibold">{error.move_san}</span>{" "}
          &mdash; the engine preferred{" "}
          <span className="font-mono font-semibold">{error.best_move_san}</span>.
        </p>
        <p className="whitespace-pre-line text-sm leading-relaxed">{error.coaching_text}</p>
      </div>
    </div>
  );
}
