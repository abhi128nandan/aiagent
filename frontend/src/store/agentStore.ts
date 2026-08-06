import { create } from 'zustand';
import { api } from '../api/backend';

export interface Message {
    role: 'user' | 'agent' | 'system';
    content: string;
}

export interface AgentEvent {
    id: string;
    type: string;
    node?: string;
    data?: unknown;
    chunk?: string;
    timestamp: string;
}

export interface AgentSession {
    id: string;
    title: string;
    createdAt: string;
    updatedAt: string;
}

export interface SandboxInfo {
    session_id: string;
    container_name: string;
    container_ip: string;
    status: string;
    exposed_ports: { name: string; container_port: number; host_port: number }[];
    created_at: number;
}

export interface TokenUsageInfo {
    messageTokens: number;
    budgetTokens: number;
    usagePercent: number;
    activeModules: string[];
}

export interface ErrorAnalysisInfo {
    category: string;
    severity: string;
    errorType: string;
    message: string;
    file?: string;
    line?: number;
    suggestion?: string;
}

const SESSIONS_KEY = 'myaiagent.sessions';
const ACTIVE_SESSION_KEY = 'myaiagent.activeSessionId';

const createSession = (): AgentSession => {
    const now = new Date().toISOString();
    return {
        id: crypto.randomUUID(),
        title: 'New app',
        createdAt: now,
        updatedAt: now,
    };
};

const loadSessions = () => {
    try {
        const raw = localStorage.getItem(SESSIONS_KEY);
        const parsed = raw ? JSON.parse(raw) as AgentSession[] : [];
        return parsed.length ? parsed : [createSession()];
    } catch {
        return [createSession()];
    }
};

const initialSessions = loadSessions();
const initialActiveSessionId =
    localStorage.getItem(ACTIVE_SESSION_KEY) || initialSessions[0].id;

const persistSessions = (sessions: AgentSession[], activeSessionId: string) => {
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
    localStorage.setItem(ACTIVE_SESSION_KEY, activeSessionId);
};

interface AgentStore {
    status: string;
    connectionState: 'idle' | 'connecting' | 'open' | 'closed' | 'error';
    sessions: AgentSession[];
    activeSessionId: string;
    messagesBySession: Record<string, Message[]>;
    eventsBySession: Record<string, AgentEvent[]>;
    pendingBySession: Record<string, string[]>;
    filesBySession: Record<string, Record<string, string>>;
    activeFileBySession: Record<string, string | null>;
    logsBySession: Record<string, string>;
    sandboxBySession: Record<string, SandboxInfo | null>;
    previewUrlBySession: Record<string, string | null>;
    tokenUsageBySession: Record<string, TokenUsageInfo | null>;
    errorAnalysisBySession: Record<string, ErrorAnalysisInfo[]>;
        uploadedDocBySession: Record<string, { filename: string; documentId: string } | null>;
    srsTextBySession: Record<string, string | null>;
    planBySession: Record<string, any | null>;
    architecturalPlanBySession: Record<string, any | null>;
    streamingFileBySession: Record<string, { path: string; content: string; isStreaming: boolean } | null>;
    chatModeBySession: Record<string, 'build' | 'discuss'>;
    lockedFilesBySession: Record<string, string[]>;
    observabilityLogsBySession: Record<string, any[]>;
    interactiveBySession: Record<string, { active: boolean; output: string; prompt?: string; command?: string; certain?: boolean; options?: { label: string; selected: boolean }[] } | null>;
    appLogsBySession: Record<string, string>;
    activeProcessesBySession: Record<string, { pid: number; ppid: number; status: string; command: string }[]>;
    foregroundProcessBySession: Record<string, { pid: number; ppid: number; status: string; command: string } | null>;
    activeCommandBySession: Record<string, string | null>;
    activeCommandStartBySession: Record<string, number | null>;
    activeCommandPidBySession: Record<string, number | null>;
    agentTaskStatusBySession: Record<string, 'idle' | 'planning' | 'reading' | 'writing' | 'testing' | 'validating' | 'paused'>;
    _agentWs: WebSocket | null;
    error: string | null;

    addObservabilityLog: (log: any, sessionId?: string) => void;
    setObservabilityLogs: (logs: any[], sessionId?: string) => void;

    setStatus: (s: string) => void;
    setConnectionState: (s: AgentStore['connectionState']) => void;
    setError: (error: string | null) => void;
    fetchSessions: () => Promise<void>;
    createNewSession: () => Promise<string>;
    setActiveSession: (id: string) => void;
    renameActiveSession: (title: string) => void;
    addMessage: (m: Message, sessionId?: string) => void;
    updateLastMessage: (content: string, sessionId?: string) => void;
    addEvent: (event: Omit<AgentEvent, 'id' | 'timestamp'>, sessionId?: string) => void;
    queuePending: (message: string, sessionId?: string) => void;
    popPending: (sessionId?: string) => string | undefined;
    setFile: (path: string, content: string, sessionId?: string) => void;
    replaceFiles: (files: Record<string, string>, sessionId?: string) => void;
    setActiveFile: (path: string | null, sessionId?: string) => void;
    addLog: (log: string, sessionId?: string) => void;
    setSandbox: (sandbox: SandboxInfo | null, sessionId?: string) => void;
    setPreviewUrl: (url: string | null, sessionId?: string) => void;
    setTokenUsage: (usage: TokenUsageInfo, sessionId?: string) => void;
    addErrorAnalysis: (error: ErrorAnalysisInfo, sessionId?: string) => void;
    setUploadedDoc: (doc: { filename: string; documentId: string } | null, sessionId?: string) => void;
    setSrsText: (text: string | null, sessionId?: string) => void;
    consumeSrsText: (sessionId?: string) => string | null;
    setPlan: (plan: any, sessionId?: string) => void;
    fetchArchitecturalPlan: (sessionId?: string) => Promise<void>;
    startFileStream: (path: string, sessionId?: string) => void;
    appendFileStream: (content: string, sessionId?: string) => void;
    completeFileStream: (finalContent: string, sessionId?: string) => void;
    setChatMode: (mode: 'build' | 'discuss', sessionId?: string) => void;
    toggleFileLock: (path: string, sessionId?: string) => void;
    setInteractive: (active: boolean, sessionId?: string, info?: { prompt?: string; command?: string; certain?: boolean; options?: { label: string; selected: boolean }[] }) => void;
    appendInteractiveOutput: (data: string, sessionId?: string) => void;
    clearInteractive: (sessionId?: string) => void;
    appendAppLog: (data: string, sessionId?: string) => void;
    clearAppLogs: (sessionId?: string) => void;
    setAgentWs: (ws: WebSocket | null) => void;
    sendInteractiveInput: (data: string) => boolean;

    setActiveProcesses: (processes: { pid: number; ppid: number; status: string; command: string }[], sessionId?: string) => void;
    setForegroundProcess: (proc: { pid: number; ppid: number; status: string; command: string } | null, sessionId?: string) => void;
    setActiveCommand: (cmd: string | null, sessionId?: string) => void;
    setActiveCommandStart: (start: number | null, sessionId?: string) => void;
    setActiveCommandPid: (pid: number | null, sessionId?: string) => void;
    setAgentTaskStatus: (status: 'idle' | 'planning' | 'reading' | 'writing' | 'testing' | 'validating' | 'paused', sessionId?: string) => void;
    killProcess: (pid: number | null, signal?: number) => void;
    restartCommand: () => void;
    pauseAgent: () => void;
    resumeAgent: () => void;
    cancelAgent: () => void;
}

export const useAgentStore = create<AgentStore>((set, get) => ({
    status: 'idle',
    connectionState: 'idle',
    sessions: initialSessions,
    activeSessionId: initialActiveSessionId,
    messagesBySession: {},
    eventsBySession: {},
    pendingBySession: {},
    filesBySession: {},
    activeFileBySession: {},
    logsBySession: {},
    sandboxBySession: {},
    previewUrlBySession: {},
    tokenUsageBySession: {},
    errorAnalysisBySession: {},
        uploadedDocBySession: {},
    srsTextBySession: {},
    planBySession: {},
    architecturalPlanBySession: {},
    streamingFileBySession: {},
    chatModeBySession: {},
    lockedFilesBySession: {},
    observabilityLogsBySession: {},
    interactiveBySession: {},
    appLogsBySession: {},
    activeProcessesBySession: {},
    foregroundProcessBySession: {},
    activeCommandBySession: {},
    activeCommandStartBySession: {},
    activeCommandPidBySession: {},
    agentTaskStatusBySession: {},
    _agentWs: null,
    error: null,

    setStatus: (status) => set({ status }),
    setConnectionState: (connectionState) => set({ connectionState }),
    setError: (error) => set({ error }),

    fetchSessions: async () => {
        try {
            const res = await api.conversations.list();
            const conversations = res.conversations;
            if (conversations.length > 0) {
                const sessions: AgentSession[] = conversations.map(c => ({
                    id: c.id,
                    title: c.id.slice(0, 8),
                    createdAt: c.created_at || new Date().toISOString(),
                    updatedAt: c.updated_at || new Date().toISOString(),
                }));
                
                const local = localStorage.getItem(SESSIONS_KEY);
                const localSessions = local ? JSON.parse(local) as AgentSession[] : [];
                const localMap = new Map(localSessions.map(s => [s.id, s]));
                
                const finalSessions = sessions.map(s => {
                    const l = localMap.get(s.id);
                    if (l) {
                        return { ...s, title: l.title };
                    }
                    return s;
                });

                set({ sessions: finalSessions });
                
                const activeId = get().activeSessionId;
                if (!finalSessions.some(s => s.id === activeId)) {
                    set({ activeSessionId: finalSessions[0].id });
                    localStorage.setItem(ACTIVE_SESSION_KEY, finalSessions[0].id);
                }
            }
        } catch (e) {
            console.error("Failed to fetch sessions from backend:", e);
        }
    },

    createNewSession: async () => {
        try {
            const res = await api.conversations.create();
            const session: AgentSession = {
                id: res.id,
                title: 'New app',
                createdAt: res.created_at || new Date().toISOString(),
                updatedAt: res.updated_at || new Date().toISOString(),
            };
            set((state) => {
                const sessions = [session, ...state.sessions];
                persistSessions(sessions, session.id);
                return {
                    sessions,
                    activeSessionId: session.id,
                    status: 'idle',
                    connectionState: 'idle',
                    error: null,
                };
            });
            return session.id;
        } catch (e) {
            console.error("Failed to create session on backend:", e);
            const session = createSession();
            set((state) => {
                const sessions = [session, ...state.sessions];
                persistSessions(sessions, session.id);
                return {
                    sessions,
                    activeSessionId: session.id,
                    status: 'idle',
                    connectionState: 'idle',
                    error: null,
                };
            });
            return session.id;
        }
    },

    setActiveSession: (id) => set((state) => {
        persistSessions(state.sessions, id);
        return {
            activeSessionId: id,
            status: 'idle',
            connectionState: 'idle',
            error: null,
        };
    }),

    renameActiveSession: (title) => set((state) => {
        const sessions = state.sessions.map((session) =>
            session.id === state.activeSessionId
                ? { ...session, title, updatedAt: new Date().toISOString() }
                : session
        );
        persistSessions(sessions, state.activeSessionId);
        return { sessions };
    }),

    addMessage: (m, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        const messages = [...(state.messagesBySession[id] || []), m];
        const sessions = state.sessions.map((session) =>
            session.id === id
                ? {
                    ...session,
                    title: session.title === 'New app' && m.role === 'user'
                        ? m.content.slice(0, 42)
                        : session.title,
                    updatedAt: new Date().toISOString(),
                }
                : session
        );
        persistSessions(sessions, state.activeSessionId);
        return {
            sessions,
            messagesBySession: { ...state.messagesBySession, [id]: messages },
        };
    }),

    updateLastMessage: (content, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        const msgs = [...(state.messagesBySession[id] || [])];
        if (msgs.length > 0) msgs[msgs.length - 1].content += content;
        return { messagesBySession: { ...state.messagesBySession, [id]: msgs } };
    }),

    addEvent: (event, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        const events = [
            ...(state.eventsBySession[id] || []),
            { ...event, id: crypto.randomUUID(), timestamp: new Date().toISOString() },
        ];
        return { eventsBySession: { ...state.eventsBySession, [id]: events } };
    }),

    queuePending: (message, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        return {
            pendingBySession: {
                ...state.pendingBySession,
                [id]: [...(state.pendingBySession[id] || []), message],
            },
        };
    }),

    popPending: (sessionId) => {
        const id = sessionId || get().activeSessionId;
        const pending = get().pendingBySession[id] || [];
        const [message, ...rest] = pending;
        set((state) => ({
            pendingBySession: { ...state.pendingBySession, [id]: rest },
        }));
        return message;
    },

    setFile: (path, content, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        const currentFiles = state.filesBySession[id] || {};
        const newFiles = { ...currentFiles, [path]: content };
        const currentActiveFile = state.activeFileBySession[id];
        
        return {
            filesBySession: { ...state.filesBySession, [id]: newFiles },
            activeFileBySession: {
                ...state.activeFileBySession,
                [id]: currentActiveFile === null ? path : currentActiveFile,
            },
        };
    }),

    replaceFiles: (files, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        const currentActiveFile = state.activeFileBySession[id];
        
        return {
            filesBySession: { ...state.filesBySession, [id]: files },
            activeFileBySession: {
                ...state.activeFileBySession,
                [id]: currentActiveFile && files[currentActiveFile] !== undefined
                    ? currentActiveFile
                    : Object.keys(files)[0] || null,
            },
        };
    }),

    setActiveFile: (activeFile, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        return {
            activeFileBySession: { ...state.activeFileBySession, [id]: activeFile },
        };
    }),

    addLog: (log, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        const currentLogs = state.logsBySession[id] || '';
        return {
            logsBySession: { ...state.logsBySession, [id]: currentLogs + log + '\n' },
        };
    }),

    setSandbox: (sandbox, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        return {
            sandboxBySession: { ...state.sandboxBySession, [id]: sandbox },
        };
    }),

    setPreviewUrl: (previewUrl, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        return {
            previewUrlBySession: { ...state.previewUrlBySession, [id]: previewUrl },
        };
    }),

    setTokenUsage: (usage, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        return {
            tokenUsageBySession: { ...state.tokenUsageBySession, [id]: usage },
        };
    }),

    addErrorAnalysis: (error, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        const existing = state.errorAnalysisBySession[id] || [];
        return {
            errorAnalysisBySession: {
                ...state.errorAnalysisBySession,
                [id]: [...existing.slice(-19), error],  // Keep last 20
            },
        };
    }),

    setUploadedDoc: (doc, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        return {
            uploadedDocBySession: { ...state.uploadedDocBySession, [id]: doc },
        };
    }),

    setSrsText: (text, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        return {
            srsTextBySession: { ...state.srsTextBySession, [id]: text },
        };
    }),

    consumeSrsText: (sessionId) => {
        const state = get();
        const id = sessionId || state.activeSessionId;
        const text = state.srsTextBySession[id] || null;
        if (text) {
            set({
                srsTextBySession: { ...state.srsTextBySession, [id]: null },
            });
        }
        return text;
    },

    setPlan: (plan, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        return {
            planBySession: { ...state.planBySession, [id]: plan },
        };
    }),

    fetchArchitecturalPlan: async (sessionId) => {
        const id = sessionId || get().activeSessionId;
        try {
            const plan = await api.architecture.getPlan(id);
            set((state) => ({
                architecturalPlanBySession: {
                    ...state.architecturalPlanBySession,
                    [id]: plan && plan.status !== 'no_plan' ? plan : null,
                },
            }));
        } catch (e) {
            console.error("Failed to fetch architectural plan:", e);
            set((state) => ({
                architecturalPlanBySession: {
                    ...state.architecturalPlanBySession,
                    [id]: null,
                },
            }));
        }
    },

    startFileStream: (path, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        return {
            streamingFileBySession: {
                ...state.streamingFileBySession,
                [id]: { path, content: '', isStreaming: true },
            },
            activeFileBySession: {
                ...state.activeFileBySession,
                [id]: path,
            },
        };
    }),

    appendFileStream: (content, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        const current = state.streamingFileBySession[id];
        if (!current) return state;
        const newContent = current.content + content;
        return {
            streamingFileBySession: {
                ...state.streamingFileBySession,
                [id]: { ...current, content: newContent },
            },
            filesBySession: {
                ...state.filesBySession,
                [id]: {
                    ...(state.filesBySession[id] || {}),
                    [current.path]: newContent,
                },
            },
        };
    }),

    completeFileStream: (finalContent, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        const current = state.streamingFileBySession[id];
        if (!current) return state;
        return {
            streamingFileBySession: {
                ...state.streamingFileBySession,
                [id]: null,
            },
            filesBySession: {
                ...state.filesBySession,
                [id]: {
                    ...(state.filesBySession[id] || {}),
                    [current.path]: finalContent,
                },
            },
        };
    }),

    setChatMode: (chatMode, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        return {
            chatModeBySession: { ...state.chatModeBySession, [id]: chatMode },
        };
    }),

    toggleFileLock: (path, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        const current = state.lockedFilesBySession[id] || [];
        const isLocked = current.includes(path);
        const next = isLocked
            ? current.filter((p) => p !== path)
            : [...current, path];
        return {
            lockedFilesBySession: { ...state.lockedFilesBySession, [id]: next },
        };
    }),

    addObservabilityLog: (log, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        const existing = state.observabilityLogsBySession[id] || [];
        return {
            observabilityLogsBySession: {
                ...state.observabilityLogsBySession,
                [id]: [...existing, log],
            },
        };
    }),

    setObservabilityLogs: (logs, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        return {
            observabilityLogsBySession: {
                ...state.observabilityLogsBySession,
                [id]: logs,
            },
        };
    }),

    setInteractive: (active, sessionId, info) => set((state) => {
        const id = sessionId || state.activeSessionId;
        const current = state.interactiveBySession[id];
        return {
            interactiveBySession: {
                ...state.interactiveBySession,
                [id]: {
                    active,
                    output: current?.output || '',
                    prompt: info?.prompt ?? (active ? current?.prompt : undefined),
                    command: info?.command ?? (active ? current?.command : undefined),
                    certain: info?.certain ?? (active ? current?.certain : undefined),
                    options: info?.options ?? (active ? current?.options : undefined),
                },
            },
        };
    }),

    appendInteractiveOutput: (data, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        const current = state.interactiveBySession[id];
        return {
            interactiveBySession: {
                ...state.interactiveBySession,
                [id]: {
                    active: current?.active ?? false,
                    output: (current?.output || '') + data,
                },
            },
        };
    }),

    clearInteractive: (sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        return {
            interactiveBySession: {
                ...state.interactiveBySession,
                [id]: null,
            },
        };
    }),

    appendAppLog: (data, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        return {
            appLogsBySession: {
                ...state.appLogsBySession,
                [id]: (state.appLogsBySession[id] || '') + data,
            },
        };
    }),

    clearAppLogs: (sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        return {
            appLogsBySession: {
                ...state.appLogsBySession,
                [id]: '',
            },
        };
    }),

    setAgentWs: (ws) => set({ _agentWs: ws }),

    sendInteractiveInput: (data) => {
        const ws = get()._agentWs;
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'interactive_input',
                data,
            }));
            // Optimistically drop the "waiting" banner; the backend
            // re-broadcasts interactive_waiting if the command stalls again.
            get().setInteractive(false);
            return true;
        }
        return false;
    },

    setActiveProcesses: (processes, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        return { activeProcessesBySession: { ...state.activeProcessesBySession, [id]: processes } };
    }),
    setForegroundProcess: (proc, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        return { foregroundProcessBySession: { ...state.foregroundProcessBySession, [id]: proc } };
    }),
    setActiveCommand: (cmd, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        return { activeCommandBySession: { ...state.activeCommandBySession, [id]: cmd } };
    }),
    setActiveCommandStart: (start, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        return { activeCommandStartBySession: { ...state.activeCommandStartBySession, [id]: start } };
    }),
    setActiveCommandPid: (pid, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        return { activeCommandPidBySession: { ...state.activeCommandPidBySession, [id]: pid } };
    }),
    setAgentTaskStatus: (taskStatus, sessionId) => set((state) => {
        const id = sessionId || state.activeSessionId;
        return { agentTaskStatusBySession: { ...state.agentTaskStatusBySession, [id]: taskStatus } };
    }),
    killProcess: (pid, signal = 15) => {
        const ws = get()._agentWs;
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'kill_process',
                pid,
                signal
            }));
        }
    },
    restartCommand: () => {
        const ws = get()._agentWs;
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'restart_command'
            }));
        }
    },
    pauseAgent: () => {
        const ws = get()._agentWs;
        const sessionId = get().activeSessionId;
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'pause_agent'
            }));
            get().setAgentTaskStatus('paused', sessionId);
        }
    },
    resumeAgent: () => {
        const ws = get()._agentWs;
        const sessionId = get().activeSessionId;
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'resume_agent'
            }));
            get().setAgentTaskStatus('planning', sessionId);
        }
    },
    cancelAgent: () => {
        const ws = get()._agentWs;
        const sessionId = get().activeSessionId;
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'cancel_agent'
            }));
            get().setAgentTaskStatus('idle', sessionId);
        }
    },
}));
