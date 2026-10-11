import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './api';

afterEach(() => vi.restoreAllMocks());

describe('API helper', () => {
  it('sends JSON headers for body requests and decodes successful JSON', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ saved: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    const value = await api<{ saved: boolean }>('/notes', { method: 'POST', body: JSON.stringify({ title: 'A note' }) });
    expect(fetchMock).toHaveBeenCalledWith('/api/notes', expect.objectContaining({ method: 'POST', headers: expect.any(Headers) }));
    expect(value.saved).toBe(true);
  });

  it('surfaces backend errors as useful exceptions', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ detail: 'Docker is unavailable.' }), { status: 503, headers: { 'Content-Type': 'application/json' } }));
    await expect(api('/challenges/challenge-01/start', { method: 'POST' })).rejects.toThrow('Docker is unavailable.');
  });
});
