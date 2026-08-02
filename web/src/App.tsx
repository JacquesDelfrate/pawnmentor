import { useState } from "react";
import { ApiError, createReview, ingestGames } from "./api";
import type { IngestedGame, Review } from "./api";
import { ErrorCard } from "./components/ErrorCard";

type Status = { kind: "idle" } | { kind: "loading" } | { kind: "error"; message: string };

function App() {
  const [username, setUsername] = useState("");
  const [games, setGames] = useState<IngestedGame[]>([]);
  const [rating, setRating] = useState(1200);
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [review, setReview] = useState<Review | null>(null);
  const [reviewingGameId, setReviewingGameId] = useState<number | null>(null);

  async function handleLoadGames(event: React.FormEvent) {
    event.preventDefault();
    if (!username.trim()) return;
    setStatus({ kind: "loading" });
    setReview(null);
    try {
      const fetched = await ingestGames(username.trim());
      setGames(fetched);
      setStatus({ kind: "idle" });
    } catch (err) {
      setStatus({ kind: "error", message: errorMessage(err) });
    }
  }

  async function handleReview(gameId: number) {
    setStatus({ kind: "loading" });
    setReviewingGameId(gameId);
    setReview(null);
    try {
      const result = await createReview(gameId, username.trim(), rating);
      setReview(result);
      setStatus({ kind: "idle" });
    } catch (err) {
      setStatus({ kind: "error", message: errorMessage(err) });
    }
  }

  return (
    <div className="min-h-screen bg-white dark:bg-neutral-950 text-neutral-900 dark:text-neutral-100">
      <div className="max-w-3xl mx-auto px-4 py-10 space-y-8">
        <header>
          <h1 className="text-2xl font-bold">PawnMentor</h1>
          <p className="text-sm text-neutral-500">
            Coaching for club players, not another analysis board.
          </p>
        </header>

        <form onSubmit={handleLoadGames} className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm">
            chess.com username
            <input
              className="border border-neutral-300 dark:border-neutral-700 rounded px-3 py-2 bg-transparent"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g. hikaru"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            your rating
            <input
              type="number"
              className="border border-neutral-300 dark:border-neutral-700 rounded px-3 py-2 bg-transparent w-28"
              value={rating}
              onChange={(e) => setRating(Number(e.target.value))}
            />
          </label>
          <button
            type="submit"
            className="rounded bg-neutral-900 text-white dark:bg-white dark:text-neutral-900 px-4 py-2 text-sm font-medium disabled:opacity-50"
            disabled={status.kind === "loading"}
          >
            Load current games
          </button>
        </form>

        {status.kind === "error" && (
          <p className="text-sm text-red-600 dark:text-red-400">{status.message}</p>
        )}

        {games.length > 0 && (
          <ul className="divide-y divide-neutral-200 dark:divide-neutral-800 border border-neutral-200 dark:border-neutral-800 rounded-lg">
            {games.map((game) => (
              <li key={game.id} className="flex items-center justify-between px-4 py-3">
                <span className="text-sm">
                  {game.white_username} vs {game.black_username}
                </span>
                <button
                  type="button"
                  className="text-sm underline disabled:opacity-50 disabled:no-underline"
                  onClick={() => handleReview(game.id)}
                  disabled={status.kind === "loading"}
                >
                  {status.kind === "loading" && reviewingGameId === game.id
                    ? "Reviewing…"
                    : "Review"}
                </button>
              </li>
            ))}
          </ul>
        )}

        {review && (
          <section className="space-y-4">
            <h2 className="text-lg font-semibold">
              Review for {review.player_username} ({review.player_rating})
            </h2>
            {review.flagged_errors.length === 0 ? (
              <p className="text-sm text-neutral-500">
                No pedagogically useful mistakes found in this game.
              </p>
            ) : (
              review.flagged_errors.map((error) => (
                <ErrorCard key={`${error.ply}-${error.move_san}`} error={error} />
              ))
            )}
          </section>
        )}
      </div>
    </div>
  );
}

function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Something went wrong.";
}

export default App;
