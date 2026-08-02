export type IngestedGame = {
  id: number;
  external_id: string;
  white_username: string;
  black_username: string;
};

export type FlaggedError = {
  ply: number;
  fen_before: string;
  move_san: string;
  best_move_san: string;
  delta_cp: number;
  category: string;
  coaching_text: string;
};

export type Review = {
  id: number;
  status: string;
  player_username: string;
  player_rating: number;
  flagged_errors: FlaggedError[];
};

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(body.detail ?? response.statusText, response.status);
  }
  return response.json() as Promise<T>;
}

export function ingestGames(username: string): Promise<IngestedGame[]> {
  return request("/games/ingest", {
    method: "POST",
    body: JSON.stringify({ username }),
  });
}

export function createReview(
  gameId: number,
  playerUsername: string,
  playerRating: number,
): Promise<Review> {
  return request("/reviews", {
    method: "POST",
    body: JSON.stringify({
      game_id: gameId,
      player_username: playerUsername,
      player_rating: playerRating,
    }),
  });
}

export { ApiError };
