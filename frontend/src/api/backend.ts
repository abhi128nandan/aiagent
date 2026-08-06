import type { SandboxInfo } from '../store/agentStore';

export interface SandboxHealth {
    healthy: boolean;
    url?: string;
    status_code?: number;
    error?: string;
}

export interface SandboxUsage {
    cpu_percent?: number;
    mem_usage?: number;
    mem_limit?: number;
    mem_percent?: number;
    error?: string;
}

export interface LLMProfile {
    id: string;
    provider: string;
    model: string;
    temperature: number;
    max_tokens?: number | null;
    is_default: boolean;
    created_at?: string | null;
    updated_at?: string | null;
}

export interface LLMProfileCreate {
    provider: string;
    model: string;
    temperature?: number;
    max_tokens?: number | null;
    is_default?: boolean;
}

export interface LLMProfileUpdate {
    provider?: string;
    model?: string;
    temperature?: number;
    max_tokens?: number | null;
    is_default?: boolean;
}

export interface Conversation {
    id: string;
    status: string;
    created_at?: string | null;
    updated_at?: string | null;
}

export interface SettingsMap {
    default_llm_profile?: string | null;
    sandbox_timeout?: number;
    max_retries?: number;
    debug_mode?: boolean;
    [key: string]: unknown;
}

export const getBackendBaseUrl = () =>
    (import.meta.env.VITE_BACKEND_URL as string | undefined) || 'http://127.0.0.1:8000';

export const getApiToken = () =>
    (import.meta.env.VITE_API_TOKEN as string | undefined) || undefined;

export const getWebSocketUrl = () => {
    const configured = import.meta.env.VITE_BACKEND_WS_URL as string | undefined;
    if (configured) return configured;

    const url = new URL(getBackendBaseUrl());
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    url.pathname = '/api/agent/ws';
    return url.toString();
};

const apiUrl = (path: string) => `${getBackendBaseUrl()}${path}`;

const buildHeaders = (init?: RequestInit, auth = true) => {
    const headers = new Headers(init?.headers || {});
    const token = getApiToken();
    if (auth && token) headers.set('X-API-Key', token);
    if (init?.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
    return headers;
};

async function requestJson<T>(path: string, init: RequestInit = {}, auth = true): Promise<T> {
    const response = await fetch(apiUrl(path), {
        ...init,
        headers: buildHeaders(init, auth),
    });
    if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Request failed: ${response.status}`);
    }
    return response.json() as Promise<T>;
}

export const api = {
    agent: {
        health: () => requestJson<{ status: string; version: string }>('/api/agent/health', {}, false),
        createSession: (profileId?: string) =>
            requestJson<{ session_id: string; profile_id?: string; profile?: LLMProfile }>(
                '/api/agent/sessions',
                {
                    method: 'POST',
                    body: JSON.stringify(profileId ? { profile_id: profileId } : {}),
                },
                false
            ),
    },
    sandbox: {
        listAll: () => requestJson<{ sandboxes: SandboxInfo[] }>('/api/agent/sandboxes'),
        status: (sessionId: string) => requestJson<SandboxInfo>(`/api/agent/sandbox/${sessionId}/status`),
        health: (sessionId: string, port = 3000) =>
            requestJson<SandboxHealth>(`/api/agent/sandbox/${sessionId}/health?port=${port}`),
        files: (sessionId: string) => requestJson<{ files: string[] }>(`/api/agent/sandbox/${sessionId}/files`),
        readFile: (sessionId: string, path: string) =>
            requestJson<{ path: string; content: string }>(
                `/api/agent/sandbox/${sessionId}/files/read?path=${encodeURIComponent(path)}`
            ),
        writeFile: (sessionId: string, path: string, content: string) =>
            requestJson<{ success: boolean }>(
                `/api/agent/sandbox/${sessionId}/files/write`,
                {
                    method: 'POST',
                    body: JSON.stringify({ path, content })
                }
            ),
        pause: (sessionId: string) =>
            requestJson<{ paused: boolean }>(`/api/agent/sandbox/${sessionId}/pause`, { method: 'POST' }),
        resume: (sessionId: string) =>
            requestJson<{ resumed: boolean }>(`/api/agent/sandbox/${sessionId}/resume`, { method: 'POST' }),
        usage: (sessionId: string) =>
            requestJson<SandboxUsage>(`/api/agent/sandbox/${sessionId}/usage`),
        delete: (sessionId: string) =>
            requestJson<{ deleted: boolean }>(`/api/agent/sandbox/${sessionId}`, { method: 'DELETE' }),
    },
    documents: {
        upload: async (file: File, enableRag = true): Promise<{
            filename: string;
            document_id: string;
            text_length: number;
            text_preview: string;
            full_text: string;
            chunks_indexed: number;
            rag_enabled: boolean;
        }> => {
            const formData = new FormData();
            formData.append('file', file);
            const url = `${getBackendBaseUrl()}/api/agent/upload?enable_rag=${enableRag}`;
            const headers: Record<string, string> = {};
            const token = getApiToken();
            if (token) headers['X-API-Key'] = token;
            const response = await fetch(url, {
                method: 'POST',
                body: formData,
                headers,
            });
            if (!response.ok) {
                const text = await response.text();
                throw new Error(text || `Upload failed: ${response.status}`);
            }
            return response.json();
        },
        search: (query: string, topK = 5, documentId?: string) =>
            requestJson<{ query: string; results: { text: string; score: number; metadata: Record<string, string> }[]; count: number }>(
                `/api/agent/rag/search?query=${encodeURIComponent(query)}&top_k=${topK}${documentId ? `&document_id=${documentId}` : ''}`
            ),
    },
    settings: {
        getAll: () => requestJson<{ settings: SettingsMap }>('/api/settings'),
        update: (key: string, value: unknown) =>
            requestJson<{ updated: Record<string, unknown> }>(`/api/settings/${key}`, {
                method: 'PUT',
                body: JSON.stringify({ value }),
            }),
        reset: () => requestJson<{ settings: SettingsMap }>('/api/settings/reset', { method: 'POST' }),
        profiles: {
            create: (payload: LLMProfileCreate) =>
                requestJson<LLMProfile>('/api/settings/llm-profiles', {
                    method: 'POST',
                    body: JSON.stringify(payload),
                }),
            list: () => requestJson<{ profiles: LLMProfile[] }>('/api/settings/llm-profiles'),
            get: (profileId: string) => requestJson<LLMProfile>(`/api/settings/llm-profiles/${profileId}`),
            update: (profileId: string, payload: LLMProfileUpdate) =>
                requestJson<LLMProfile>(`/api/settings/llm-profiles/${profileId}`, {
                    method: 'PUT',
                    body: JSON.stringify(payload),
                }),
            delete: (profileId: string) =>
                requestJson<{ deleted: boolean }>(`/api/settings/llm-profiles/${profileId}`, {
                    method: 'DELETE',
                }),
            setDefault: (profileId: string) =>
                requestJson<LLMProfile>(`/api/settings/llm-profiles/${profileId}/default`, {
                    method: 'POST',
                }),
        },
    },
    secrets: {
        list: () => requestJson<{ secrets: { provider: string; masked: string; updated_at?: string }[] }>(
            '/api/secrets'
        ),
        get: (provider: string) => requestJson<{ provider: string; masked: string; updated_at?: string }>(
            `/api/secrets/${provider}`
        ),
        store: (provider: string, secret: string) =>
            requestJson<{ provider: string; masked: string }>(`/api/secrets/${provider}`, {
                method: 'POST',
                body: JSON.stringify({ secret }),
            }),
        delete: (provider: string) =>
            requestJson<{ deleted: boolean }>(`/api/secrets/${provider}`, { method: 'DELETE' }),
        test: (provider: string, secret?: string) =>
            requestJson<{ ok: boolean; status_code?: number; error?: string }>(
                `/api/secrets/${provider}/test`,
                {
                    method: 'POST',
                    body: JSON.stringify(secret ? { secret } : {}),
                }
            ),
    },
    conversations: {
        create: () => requestJson<Conversation>('/api/conversations', { method: 'POST' }),
        list: () => requestJson<{ conversations: Conversation[] }>('/api/conversations'),
        get: (conversationId: string) => requestJson<Conversation>(`/api/conversations/${conversationId}`),
        pause: (conversationId: string) =>
            requestJson<Conversation>(`/api/conversations/${conversationId}/pause`, { method: 'POST' }),
        resume: (conversationId: string) =>
            requestJson<Conversation>(`/api/conversations/${conversationId}/resume`, { method: 'POST' }),
        delete: (conversationId: string) =>
            requestJson<{ deleted: boolean }>(`/api/conversations/${conversationId}`, { method: 'DELETE' }),
    },
    observability: {
        getLogs: (sessionId: string, agentName?: string, eventType?: string, status?: string, search?: string) => {
            const params = new URLSearchParams();
            if (agentName) params.append('agent_name', agentName);
            if (eventType) params.append('event_type', eventType);
            if (status) params.append('status', status);
            if (search) params.append('search', search);
            const queryStr = params.toString() ? `?${params.toString()}` : '';
            return requestJson<any[]>(`/api/agent/session/${sessionId}/observability${queryStr}`);
        },
        getSummary: (sessionId: string) =>
            requestJson<any>(`/api/agent/session/${sessionId}/observability/summary`),
    },
    architecture: {
        getPlan: (sessionId: string) =>
            requestJson<any>(`/api/agent/session/${sessionId}/architecture`),
    },
};

export const backendApi = {
    health: api.agent.health,
    sandboxStatus: api.sandbox.status,
    sandboxHealth: api.sandbox.health,
    listFiles: api.sandbox.files,
    readFile: api.sandbox.readFile,
    writeFile: api.sandbox.writeFile,
    pauseSandbox: api.sandbox.pause,
    resumeSandbox: api.sandbox.resume,
    deleteSandbox: api.sandbox.delete,
};
