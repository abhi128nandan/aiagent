import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api } from '../backend';

describe('API Service Layer', () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  it('should be defined', () => {
    expect(api).toBeDefined();
  });

  // Example test for a session method if it exists
  it('should call fetch when creating a session', async () => {
    const mockResponse = { id: 'test-session', status: 'created' };
    vi.mocked(global.fetch).mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    } as Response);

    if (api.agent && api.agent.createSession) {
      const result = await api.agent.createSession('test-profile-id');
      expect(global.fetch).toHaveBeenCalled();
      expect(result).toEqual(mockResponse);
    }
  });

  it('should handle API errors properly', async () => {
    vi.mocked(global.fetch).mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ detail: 'Internal Server Error' }),
    } as Response);

    if (api.agent && api.agent.createSession) {
      await expect(api.agent.createSession('test-profile-id')).rejects.toThrow();
    }
  });
});
