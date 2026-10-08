export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type Camera = { id: number; name: string; source_type: string | null };

export type Zone = {
  id: number;
  name: string;
  points: number[][];
  normalized: boolean;
  classes: string[];
  congestion_threshold: number | null;
  min_confidence: number | null;
};

export type EventItem = {
  id: number;
  camera: string;
  zone: string | null;
  run_id: string;
  event_type: string;
  class_name: string;
  confidence: number;
  timestamp: string;
  frame_id: number;
  track_id: number | null;
  count: number | null;
};

export type EventPage = { total: number; limit: number; offset: number; items: EventItem[] };

export type Run = {
  run_id: string;
  camera: string;
  events: number;
  first_event: string;
  last_event: string;
};

export type Stats = {
  total: number;
  by_event_type: Record<string, number>;
  by_class: Record<string, number>;
  by_zone: Record<string, number>;
};

export type Filters = {
  camera?: string;
  run_id?: string;
  zone?: string;
  event_type?: string;
  class_name?: string;
};

type Params = Record<string, string | number | undefined>;

async function get<T>(path: string, params: Params = {}): Promise<T> {
  const url = new URL(path, API_URL);
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") url.searchParams.set(key, String(value));
  }
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  cameras: () => get<Camera[]>("/cameras"),
  zones: (camera: string) => get<Zone[]>(`/cameras/${encodeURIComponent(camera)}/zones`),
  runs: () => get<Run[]>("/runs"),
  events: (params: Filters & { limit?: number; offset?: number }) => get<EventPage>("/events", params),
  stats: (filters: Filters) => get<Stats>("/stats", filters),
};