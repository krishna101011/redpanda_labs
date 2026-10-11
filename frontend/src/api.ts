export type Challenge = {
  id: string; version: string; title: string; track: string; difficulty: 'Beginner' | 'Intermediate' | 'Advanced';
  summary: string; description: string; learning_objectives: string[]; prerequisites: string[]; tags: string[];
  estimated_minutes: number; offline_hints: { level: number; title: string; content: string }[];
  completion_explanation: string; validation: Record<string, unknown>; state: 'locked' | 'available' | 'in_progress' | 'completed';
  locked: boolean; prerequisites_missing: string[]; progress: { hint_level: number; latest_feedback: string | null; completed_at: string | null };
  [key: string]: unknown;
};
export type Note = { id: string; kind: 'note' | 'explanation'; title: string; content: string; challenge_id: string | null; tags: string[]; created_at: string; updated_at: string };

async function responseError(response: Response): Promise<Error> {
  let message = `Request failed (${response.status})`;
  try {
    const body = await response.json();
    const detail = body.detail;
    message = typeof detail === 'string' ? detail : detail?.message ? detail.message : JSON.stringify(detail ?? body);
  } catch { /* Keep a useful status-based fallback for non-JSON errors. */ }
  return new Error(message);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers ?? {});
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const response = await fetch(path.startsWith('/api/') ? path : `/api/${path.replace(/^\//, '')}`, { ...init, headers });
  if (!response.ok) throw await responseError(response);
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/zip') || contentType.includes('application/x-tar') || contentType.includes('application/octet-stream')) return await response.blob() as T;
  return await response.json() as T;
}

export async function download(path: string, filename: string, init?: RequestInit) {
  // Download endpoints can intentionally return JSON (progress export), ZIP (challenge pack), or TAR (workspace).
  // Read the raw response body instead of api<T>, which correctly parses ordinary JSON API responses.
  const headers = new Headers(init?.headers ?? {});
  if (init?.body && !(init.body instanceof FormData) && !(init.body instanceof Blob) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const response = await fetch(path.startsWith('/api/') ? path : `/api/${path.replace(/^\//, '')}`, { ...init, headers });
  if (!response.ok) throw await responseError(response);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = 'none';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
