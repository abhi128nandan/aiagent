import React, { useEffect, useRef, useState } from 'react';
import { Terminal as XTerm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { useAgentStore } from '../store/agentStore';
import { useAgentStream } from '../hooks/useAgentStream';
import '@xterm/xterm/css/xterm.css';
import {
    Terminal as TerminalIcon,
    Keyboard,
    FileText,
    Play,
    Pause,
    Square,
    RefreshCw,
    X,
    Cpu,
    Clock,

    AlertCircle,
    ListCollapse
} from 'lucide-react';

// ═══════════════════════════════════════════════════════════════════════
// 1. AGENT TERMINAL — read-only, shows agent actions, planning,
//    command summaries, reasoning, and task status. NO app logs.
// ═══════════════════════════════════════════════════════════════════════

const AgentTerminal: React.FC<{ xtermRef: React.MutableRefObject<XTerm | null> }> = ({ xtermRef }) => {
    const termRef = useRef<HTMLDivElement>(null);
    const { activeSessionId, interactiveBySession } = useAgentStore();
    const interactive = interactiveBySession[activeSessionId];
    const lastOutputLength = useRef(0);
    const lastSessionId = useRef(activeSessionId);

    useEffect(() => {
        if (!termRef.current) return;

        const term = new XTerm({
            theme: {
                background: '#0f1115',
                foreground: '#e2e8f0',
                cursor: 'transparent',
                cursorAccent: '#0f1115',
                selectionBackground: '#f59e0b33',
            },
            fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
            fontSize: 12,
            disableStdin: true,
            cursorBlink: false,
            convertEol: true,
        });

        const fitAddon = new FitAddon();
        term.loadAddon(fitAddon);
        term.open(termRef.current);
        fitAddon.fit();
        xtermRef.current = term;

        term.writeln('\x1b[36m┌─────────────────────────────────┐\x1b[0m');
        term.writeln('\x1b[36m│   [AGENT TERMINAL]              │\x1b[0m');
        term.writeln('\x1b[36m│   Agent actions & status only   │\x1b[0m');
        term.writeln('\x1b[36m└─────────────────────────────────┘\x1b[0m');
        term.writeln('');
        term.writeln('\x1b[90mAgent planning, execution steps, and task status will appear here.\x1b[0m');
        term.writeln('\x1b[90mApplication stdout/stderr is in the "App Logs" tab.\x1b[0m');
        term.writeln('');

        const resizeObserver = new ResizeObserver(() => {
            try { fitAddon.fit(); } catch {}
        });
        resizeObserver.observe(termRef.current);

        return () => {
            resizeObserver.disconnect();
            term.dispose();
        };
    }, [xtermRef]);

    // Reset when session changes
    useEffect(() => {
        if (lastSessionId.current !== activeSessionId) {
            if (xtermRef.current) {
                xtermRef.current.clear();
                xtermRef.current.writeln('\x1b[36m[AGENT TERMINAL]\x1b[0m');
                xtermRef.current.writeln('');
                lastOutputLength.current = 0;

                // Replay existing agent logs for this session
                const existing = interactiveBySession[activeSessionId];
                if (existing?.output) {
                    xtermRef.current.write(existing.output);
                    lastOutputLength.current = existing.output.length;
                }
            }
            lastSessionId.current = activeSessionId;
        }
    }, [activeSessionId, interactiveBySession, xtermRef]);

    // Stream agent messages (from logAgentEvent → appendInteractiveOutput)
    useEffect(() => {
        if (!xtermRef.current || !interactive) return;
        const output = interactive.output || '';
        
        // Handle clear event (when output length is less than before)
        if (output.length < lastOutputLength.current) {
            xtermRef.current.clear();
            lastOutputLength.current = 0;
        }

        if (output.length > lastOutputLength.current) {
            const newData = output.substring(lastOutputLength.current);
            xtermRef.current.write(newData);
            lastOutputLength.current = output.length;
        }
    }, [interactive, xtermRef]);

    return <div ref={termRef} className="h-full w-full" />;
};


// ═══════════════════════════════════════════════════════════════════════
// 2. APPLICATION LOGS TERMINAL — read-only, shows ALL raw command
//    output: stdout, stderr, build logs, Vite logs, stack traces, etc.
//    NO agent messages mixed in.
// ═══════════════════════════════════════════════════════════════════════

const AppLogsTerminal: React.FC<{ xtermRef: React.MutableRefObject<XTerm | null> }> = ({ xtermRef }) => {
    const termRef = useRef<HTMLDivElement>(null);
    const { activeSessionId, appLogsBySession } = useAgentStore();
    const appLogs = appLogsBySession[activeSessionId] || '';
    const lastLogsLength = useRef(0);
    const lastSessionId = useRef(activeSessionId);

    useEffect(() => {
        if (!termRef.current) return;

        const term = new XTerm({
            theme: {
                background: '#0a0c10',
                foreground: '#a8b5c8',
                cursor: 'transparent',
                selectionBackground: '#3b82f633',
                green: '#4ade80',
                red: '#f87171',
                yellow: '#fbbf24',
                cyan: '#22d3ee',
            },
            fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
            fontSize: 11,
            disableStdin: true,
            cursorBlink: false,
            convertEol: true,
        });

        const fitAddon = new FitAddon();
        term.loadAddon(fitAddon);
        term.open(termRef.current);
        fitAddon.fit();
        xtermRef.current = term;

        term.writeln('\x1b[35m┌─────────────────────────────────┐\x1b[0m');
        term.writeln('\x1b[35m│   [APPLICATION LOGS]            │\x1b[0m');
        term.writeln('\x1b[35m│   stdout · stderr · build logs  │\x1b[0m');
        term.writeln('\x1b[35m└─────────────────────────────────┘\x1b[0m');
        term.writeln('');
        term.writeln('\x1b[90mRaw command output, build logs, Vite/React logs, and stack traces appear here.\x1b[0m');
        term.writeln('');

        const resizeObserver = new ResizeObserver(() => {
            try { fitAddon.fit(); } catch {}
        });
        resizeObserver.observe(termRef.current);

        return () => {
            resizeObserver.disconnect();
            term.dispose();
        };
    }, [xtermRef]);

    // Reset when session changes
    useEffect(() => {
        if (lastSessionId.current !== activeSessionId) {
            if (xtermRef.current) {
                xtermRef.current.clear();
                xtermRef.current.writeln('\x1b[35m[APPLICATION LOGS]\x1b[0m');
                xtermRef.current.writeln('');
                lastLogsLength.current = 0;

                // Replay existing app logs for this session
                if (appLogs) {
                    xtermRef.current.write(appLogs);
                    lastLogsLength.current = appLogs.length;
                }
            }
            lastSessionId.current = activeSessionId;
        }
    }, [activeSessionId, appLogs, xtermRef]);

    // Stream new app log data
    useEffect(() => {
        if (!xtermRef.current) return;
        
        // Handle clear
        if (appLogs.length < lastLogsLength.current) {
            xtermRef.current.clear();
            lastLogsLength.current = 0;
        }

        if (appLogs.length > lastLogsLength.current) {
            const newData = appLogs.substring(lastLogsLength.current);
            xtermRef.current.write(newData);
            lastLogsLength.current = appLogs.length;
        }
    }, [appLogs, xtermRef]);

    return <div ref={termRef} className="h-full w-full" />;
};


// ═══════════════════════════════════════════════════════════════════════
// 3. USER TERMINAL — interactive Docker exec shell (direct access).
//    User can type commands and see results in real-time.
// ═══════════════════════════════════════════════════════════════════════

const UserTerminal: React.FC = () => {
    const termRef = useRef<HTMLDivElement>(null);
    const xtermRef = useRef<XTerm | null>(null);
    const socketRef = useRef<WebSocket | null>(null);
    const { activeSessionId } = useAgentStore();
    const { refreshSandbox } = useAgentStream();

    useEffect(() => {
        if (!termRef.current || !activeSessionId) return;

        const term = new XTerm({
            theme: {
                background: '#0f1115',
                foreground: '#e2e8f0',
                cursor: '#10b981',
                cursorAccent: '#0f1115',
                selectionBackground: '#10b98133',
            },
            fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
            fontSize: 12,
            cursorBlink: true,
            convertEol: true,
        });

        const fitAddon = new FitAddon();
        term.loadAddon(fitAddon);
        term.open(termRef.current);
        fitAddon.fit();
        xtermRef.current = term;

        term.writeln('\x1b[32m[User Terminal — Interactive Shell]\x1b[0m');
        term.writeln('\x1b[90mConnecting to sandbox...\x1b[0m');

        // ── Connect to sandbox terminal WebSocket ─────────────────────────
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname;
        const port = '8000';
        const wsUrl = `${protocol}//${host}:${port}/api/agent/sandbox/${activeSessionId}/terminal`;

        const ws = new WebSocket(wsUrl);
        socketRef.current = ws;

        ws.onopen = () => {
            term.writeln('\x1b[32m✓ Connected\x1b[0m\r\n');
            const dims = fitAddon.proposeDimensions();
            if (dims) {
                ws.send(JSON.stringify({
                    type: 'resize',
                    cols: dims.cols,
                    rows: dims.rows,
                }));
            }
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'output') {
                    term.write(msg.data);
                }
            } catch {
                term.write(event.data);
            }
        };

        ws.onerror = () => {
            term.writeln('\x1b[33m⚠ Sandbox not ready. Start a session first.\x1b[0m');
        };

        ws.onclose = () => {};

        // ── Terminal input ─────────────────────────────────────────────────
        const onDataDisposable = term.onData((data) => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'input', data }));
            }
            if (data.includes('\r') || data.includes('\n')) {
                setTimeout(() => { refreshSandbox(activeSessionId); }, 600);
            }
        });

        // ── Resize ─────────────────────────────────────────────────────────
        const resizeObserver = new ResizeObserver(() => {
            try {
                fitAddon.fit();
                if (ws.readyState === WebSocket.OPEN) {
                    const dims = fitAddon.proposeDimensions();
                    if (dims) {
                        ws.send(JSON.stringify({
                            type: 'resize',
                            cols: dims.cols,
                            rows: dims.rows,
                        }));
                    }
                }
            } catch {}
        });
        resizeObserver.observe(termRef.current);

        return () => {
            onDataDisposable.dispose();
            resizeObserver.disconnect();
            ws.close();
            term.dispose();
        };
    }, [activeSessionId, refreshSandbox]);

    return <div ref={termRef} className="h-full w-full" />;
};


// ═══════════════════════════════════════════════════════════════════════
// 4. INTERACTIVE ANSWER BAR
// ═══════════════════════════════════════════════════════════════════════

const InteractiveInputBar: React.FC = () => {
    const { activeSessionId, interactiveBySession, sendInteractiveInput, appendInteractiveOutput } = useAgentStore();
    const interactive = interactiveBySession[activeSessionId];
    const [value, setValue] = useState('');
    const inputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (interactive?.active) inputRef.current?.focus();
    }, [interactive?.active]);

    if (!interactive?.active) return null;

    const options = interactive.options || [];
    const isSelectMenu = options.length >= 2;

    const submit = (answer: string) => {
        const sent = sendInteractiveInput(answer + '\n');
        if (!sent) {
            appendInteractiveOutput('\x1b[31m✗ Could not send — connection to the agent is closed.\x1b[0m\r\n', activeSessionId);
            return;
        }
        setValue('');
    };

    const choose = (targetIdx: number) => {
        const selectedIdx = Math.max(0, options.findIndex(o => o.selected));
        const delta = targetIdx - selectedIdx;
        const seq = (delta >= 0 ? '\x1b[B'.repeat(delta) : '\x1b[A'.repeat(-delta)) + '\n';
        const sent = sendInteractiveInput(seq);
        if (sent) {
            appendInteractiveOutput(`\x1b[32m⌨ selected:\x1b[0m ${options[targetIdx].label}\r\n`, activeSessionId);
        } else {
            appendInteractiveOutput('\x1b[31m✗ Could not send — connection to the agent is closed.\x1b[0m\r\n', activeSessionId);
        }
    };

    return (
        <div className="border-b border-amber-500/40 bg-amber-500/10 px-4 py-2 shrink-0">
            <div className="text-xs text-amber-300 font-semibold mb-1">
                ⌨ {isSelectMenu
                    ? 'The command is asking you to choose an option:'
                    : interactive.certain === false
                        ? 'The command stalled — it may be waiting for input:'
                        : 'The command is asking:'}
            </div>
            {interactive.prompt && (
                <div className="text-xs text-amber-100 font-mono bg-black/30 rounded px-2 py-1 mb-2 whitespace-pre-wrap break-all">
                    {interactive.prompt}
                </div>
            )}
            {isSelectMenu ? (
                <div className="flex flex-wrap gap-2">
                    {options.map((opt, idx) => (
                        <button
                            key={`${idx}-${opt.label}`}
                            onClick={() => choose(idx)}
                            className={`px-3 py-1 rounded text-xs font-semibold border transition-colors ${
                                opt.selected
                                    ? 'bg-amber-500 text-black border-amber-400 hover:bg-amber-400'
                                    : 'bg-[#0f1115] text-amber-100 border-amber-500/40 hover:bg-amber-500/20'
                             }`}
                            title={opt.selected ? 'Currently highlighted (default)' : undefined}
                        >
                            {opt.label}{opt.selected ? '  (default)' : ''}
                        </button>
                    ))}
                </div>
            ) : (
                <div className="flex gap-2">
                    <input
                        ref={inputRef}
                        value={value}
                        onChange={(e) => setValue(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') submit(value); }}
                        placeholder="Type your answer and press Enter (empty = accept default)"
                        className="flex-1 bg-[#0f1115] border border-amber-500/40 rounded px-2 py-1 text-xs text-gray-100 font-mono focus:outline-none focus:border-amber-400"
                    />
                    <button
                        onClick={() => submit(value)}
                        className="px-3 py-1 rounded bg-amber-500 text-black text-xs font-bold hover:bg-amber-400"
                    >
                        Send
                    </button>
                </div>
            )}
        </div>
    );
};


// ═══════════════════════════════════════════════════════════════════════
// 5. ADVANCED PROCESS / TASK CONTROL & TERMINAL MAIN EXPORT
// ═══════════════════════════════════════════════════════════════════════

type TabId = 'agent' | 'app-logs' | 'user-terminal';

const SUGGESTIONS = [
    'npm install',
    'npm run dev',
    'npm run build',
    'npm test',
    'git status',
    'git diff',
    'pip install -r requirements.txt',
    'python manage.py runserver',
    'ls -la',
    'pwd'
];

export const TerminalLog: React.FC = () => {
    const [activeTab, setActiveTab] = useState<TabId>('agent');
    
    // Store states
    const {
        activeSessionId,
        interactiveBySession,
        appLogsBySession,
        activeProcessesBySession,
        foregroundProcessBySession,
        activeCommandBySession,
        activeCommandStartBySession,
        activeCommandPidBySession,
        agentTaskStatusBySession,
        
        // Actions
        killProcess,
        restartCommand,
        pauseAgent,
        resumeAgent,
        cancelAgent,
        sendInteractiveInput,
        appendInteractiveOutput,
        clearInteractive,
        clearAppLogs
    } = useAgentStore();

    const interactive = interactiveBySession[activeSessionId];
    const isWaiting = interactive?.active ?? false;
    const prevWaiting = useRef(false);
    const appLogs = appLogsBySession[activeSessionId] || '';
    const prevAppLogsLen = useRef(0);

    // XTerm Refs to support keyboard selections copy
    const agentTermRef = useRef<XTerm | null>(null);
    const appLogsTermRef = useRef<XTerm | null>(null);

    // Stdin textbox state
    const [inputValue, setInputValue] = useState('');
    const [history, setHistory] = useState<string[]>(() => {
        try {
            const saved = localStorage.getItem('myaiagent.cmd_history');
            return saved ? JSON.parse(saved) : [];
        } catch {
            return [];
        }
    });
    const [historyIndex, setHistoryIndex] = useState(-1);
    const [suggestions, setSuggestions] = useState<string[]>([]);
    const [activeSuggestionIdx, setActiveSuggestionIdx] = useState(0);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Process & Task control details
    const activeCommand = activeCommandBySession[activeSessionId] || null;
    const activeCommandStart = activeCommandStartBySession[activeSessionId] || null;
    const activeCommandPid = activeCommandPidBySession[activeSessionId] || null;
    const agentTaskStatus = agentTaskStatusBySession[activeSessionId] || 'idle';
    const activeProcesses = activeProcessesBySession[activeSessionId] || [];
    const foregroundProcess = foregroundProcessBySession[activeSessionId] || null;

    const [runtimeDuration, setRuntimeDuration] = useState(0);
    const [processesPanelOpen, setProcessesPanelOpen] = useState(false);
    
    // Safety modals state
    const [confirmModal, setConfirmModal] = useState<{
        open: boolean;
        title: string;
        message: string;
        action: () => void;
        type: 'kill' | 'cancel';
    }>({
        open: false,
        title: '',
        message: '',
        action: () => {},
        type: 'kill'
    });

    // Tick runtime duration
    useEffect(() => {
        if (!activeCommandStart) {
            setRuntimeDuration(0);
            return;
        }
        const interval = setInterval(() => {
            const elapsed = Math.round((Date.now() - activeCommandStart) / 1000);
            setRuntimeDuration(elapsed);
        }, 1000);
        return () => clearInterval(interval);
    }, [activeCommandStart]);

    // Save history
    const addToHistory = (cmd: string) => {
        if (!cmd.trim()) return;
        const filtered = history.filter(h => h !== cmd);
        const next = [cmd, ...filtered].slice(0, 50);
        setHistory(next);
        setHistoryIndex(-1);
        try {
            localStorage.setItem('myaiagent.cmd_history', JSON.stringify(next));
        } catch {}
    };

    // Auto-switch to Agent Terminal when agent is waiting for input
    useEffect(() => {
        if (isWaiting && !prevWaiting.current) {
            setActiveTab('agent');
        }
        prevWaiting.current = isWaiting;
    }, [isWaiting]);

    // Auto-switch to App Logs on first output
    useEffect(() => {
        if (appLogs.length > prevAppLogsLen.current && activeTab === 'agent') {
            if (prevAppLogsLen.current === 0 && appLogs.length > 0) {
                setActiveTab('app-logs');
            }
        }
        prevAppLogsLen.current = appLogs.length;
    }, [appLogs, activeTab]);

    // Resize textarea on content change
    useEffect(() => {
        const textarea = textareaRef.current;
        if (!textarea) return;
        textarea.style.height = 'auto';
        textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
    }, [inputValue]);

    // Stdin suggestions handler
    useEffect(() => {
        const val = inputValue.trim();
        if (!val) {
            setSuggestions([]);
            return;
        }
        const filtered = SUGGESTIONS.filter(
            s => s.toLowerCase().startsWith(val.toLowerCase()) && s.toLowerCase() !== val.toLowerCase()
        );
        setSuggestions(filtered);
        setActiveSuggestionIdx(0);
    }, [inputValue]);

    const handleCopySelection = () => {
        let selectedText = '';
        if (activeTab === 'agent' && agentTermRef.current) {
            selectedText = agentTermRef.current.getSelection();
        } else if (activeTab === 'app-logs' && appLogsTermRef.current) {
            selectedText = appLogsTermRef.current.getSelection();
        }
        if (selectedText) {
            navigator.clipboard.writeText(selectedText);
            appendInteractiveOutput('\x1b[32m✓ Selection copied to clipboard.\x1b[0m\r\n', activeSessionId);
        } else {
            appendInteractiveOutput('\x1b[33m⚠ No text selected to copy.\x1b[0m\r\n', activeSessionId);
        }
    };

    const submitStdin = (textToSend: string) => {
        const cleanVal = textToSend.trim();
        const sent = sendInteractiveInput(textToSend + '\n');
        if (sent) {
            appendInteractiveOutput(`\x1b[36m⌨ sent:\x1b[0m ${cleanVal || '⏎'}\r\n`, activeSessionId);
            addToHistory(cleanVal);
            setInputValue('');
            setSuggestions([]);
        } else {
            appendInteractiveOutput('\x1b[31m✗ No active agent connection — input not sent.\x1b[0m\r\n', activeSessionId);
        }
    };

    // Stdin Keyboard shortcuts
    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        // Ctrl+Shift+C -> Copy selection
        if (e.ctrlKey && e.shiftKey && e.key === 'C') {
            e.preventDefault();
            handleCopySelection();
            return;
        }

        // Ctrl+C -> SIGINT Stop
        if (e.ctrlKey && e.key === 'c') {
            // If text is selected in the window, do default (let browser copy it), otherwise interrupt
            const selection = window.getSelection()?.toString();
            if (!selection) {
                e.preventDefault();
                const targetPid = activeCommandPid || foregroundProcess?.pid;
                if (activeCommand || targetPid) {
                    if (targetPid) killProcess(targetPid, 2); // SIGINT
                    if (targetPid) {
                        appendInteractiveOutput(`\r\n\x1b[33mCtrl+C sent to process PID ${targetPid}\x1b[0m\r\n`, activeSessionId);
                    } else {
                        appendInteractiveOutput(`\r\n\x1b[33mCtrl+C sent to terminal\x1b[0m\r\n`, activeSessionId);
                    }
                } else {
                    appendInteractiveOutput('\r\n\x1b[90mCtrl+C pressed (No active command running)\x1b[0m\r\n', activeSessionId);
                }
                return;
            }
        }

        // Ctrl+Z -> Suspend
        if (e.ctrlKey && e.key === 'z') {
            e.preventDefault();
            const targetPid = activeCommandPid || foregroundProcess?.pid;
            if (activeCommand || targetPid) {
                if (targetPid) killProcess(targetPid, 20); // SIGTSTP
                if (targetPid) {
                    appendInteractiveOutput(`\r\n\x1b[33mCtrl+Z (SIGTSTP) sent to process PID ${targetPid}\x1b[0m\r\n`, activeSessionId);
                } else {
                    appendInteractiveOutput(`\r\n\x1b[33mCtrl+Z sent to terminal\x1b[0m\r\n`, activeSessionId);
                }
            }
            return;
        }

        // Ctrl+L -> Clear
        if (e.ctrlKey && e.key === 'l') {
            e.preventDefault();
            if (activeTab === 'agent') {
                clearInteractive(activeSessionId);
            } else if (activeTab === 'app-logs') {
                clearAppLogs(activeSessionId);
            }
            return;
        }

        // Esc -> Clear current input
        if (e.key === 'Escape') {
            e.preventDefault();
            setInputValue('');
            setSuggestions([]);
            return;
        }

        // Tab -> Autocomplete suggestion
        if (e.key === 'Tab' && suggestions.length > 0) {
            e.preventDefault();
            setInputValue(suggestions[activeSuggestionIdx]);
            setSuggestions([]);
            return;
        }

        // Enter -> Submit (without shift)
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            submitStdin(inputValue);
            return;
        }

        // History Up
        if (e.key === 'ArrowUp' && e.altKey === false) {
            if (suggestions.length > 0) {
                // Navigate suggestions instead if visible
                e.preventDefault();
                setActiveSuggestionIdx(prev => (prev - 1 + suggestions.length) % suggestions.length);
            } else if (inputValue === '' || history.includes(inputValue) || historyIndex >= 0) {
                e.preventDefault();
                const nextIdx = historyIndex + 1;
                if (nextIdx < history.length) {
                    setHistoryIndex(nextIdx);
                    setInputValue(history[nextIdx]);
                }
            }
        }

        // History Down
        if (e.key === 'ArrowDown' && e.altKey === false) {
            if (suggestions.length > 0) {
                // Navigate suggestions instead if visible
                e.preventDefault();
                setActiveSuggestionIdx(prev => (prev + 1) % suggestions.length);
            } else if (historyIndex >= 0) {
                e.preventDefault();
                const nextIdx = historyIndex - 1;
                setHistoryIndex(nextIdx);
                if (nextIdx >= 0) {
                    setInputValue(history[nextIdx]);
                } else {
                    setInputValue('');
                }
            }
        }
    };

    // Helper to render warning badges for long running commands
    const renderLongRunningWarning = () => {
        if (runtimeDuration > 60) {
            return (
                <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-400 text-[10px] font-medium shrink-0 animate-pulse">
                    <AlertCircle size={11} className="text-amber-400" />
                    <span>LONG RUNNING &gt; 60s</span>
                </div>
            );
        }
        if (runtimeDuration > 15) {
            return (
                <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-gray-500/10 border border-gray-500/20 text-gray-400 text-[10px] font-medium shrink-0">
                    <Clock size={11} className="text-gray-400" />
                    <span>RUNNING &gt; 15s</span>
                </div>
            );
        }
        return null;
    };

    // Safety modals helper triggers
    const triggerForceKill = (pid: number | null) => {
        setConfirmModal({
            open: true,
            title: 'Confirm Force Kill Process',
            message: pid 
                ? `Are you sure you want to send SIGKILL (9) to process PID ${pid}? This will immediately terminate the process and all its children. This cannot be undone.`
                : `Are you sure you want to force kill the active terminal shell? This will terminate the running session and restart it. This cannot be undone.`,
            type: 'kill',
            action: () => {
                if (pid) killProcess(pid, 9); // SIGKILL
                if (pid) {
                    appendInteractiveOutput(`\r\n\x1b[31m☠ SIGKILL sent to process PID ${pid}\x1b[0m\r\n`, activeSessionId);
                } else {
                    appendInteractiveOutput(`\r\n\x1b[31m☠ Force killed active terminal shell\x1b[0m\r\n`, activeSessionId);
                }
                setConfirmModal(prev => ({ ...prev, open: false }));
            }
        });
    };

    const triggerCancelTask = () => {
        setConfirmModal({
            open: true,
            title: 'Confirm Cancel Agent Task',
            message: 'Are you sure you want to cancel the active agent execution graph? Any running task logic will stop immediately.',
            type: 'cancel',
            action: () => {
                cancelAgent();
                setConfirmModal(prev => ({ ...prev, open: false }));
            }
        });
    };

    const tabs: { id: TabId; label: string; icon: React.ReactNode; badge?: boolean; sublabel: string }[] = [
        {
            id: 'agent',
            label: 'Agent Terminal',
            icon: <Keyboard size={13} />,
            badge: isWaiting,
            sublabel: isWaiting ? '⌨ Input Needed' : 'Agent Actions Only',
        },
        {
            id: 'app-logs',
            label: 'App Logs',
            icon: <FileText size={13} />,
            sublabel: 'stdout · stderr · build',
        },
        {
            id: 'user-terminal',
            label: 'User Terminal',
            icon: <TerminalIcon size={13} />,
            sublabel: 'Interactive Shell',
        },
    ];

    const currentTab = tabs.find(t => t.id === activeTab);

    return (
        <div className="h-full w-full bg-[#0f1115] flex flex-col relative overflow-hidden text-gray-200">
            
            {/* 1. AGENT TASK CONTROL DASHBOARD */}
            <div className="border-b border-[#1e293b] bg-[#0c0d12] px-4 py-2 shrink-0 flex items-center justify-between gap-4">
                <div className="flex items-center gap-1.5">
                    <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Agent State:</span>
                    <div className="flex items-center gap-1">
                        {['planning', 'reading', 'writing', 'testing', 'validating', 'paused', 'idle'].map((state) => {
                            const isActive = agentTaskStatus === state;
                            const colors: Record<string, string> = {
                                planning: 'bg-blue-500 text-blue-100 border-blue-400/30',
                                reading: 'bg-indigo-500 text-indigo-100 border-indigo-400/30',
                                writing: 'bg-teal-500 text-teal-100 border-teal-400/30',
                                testing: 'bg-purple-500 text-purple-100 border-purple-400/30',
                                validating: 'bg-emerald-500 text-emerald-100 border-emerald-400/30',
                                paused: 'bg-amber-500 text-black border-amber-400/30',
                                idle: 'bg-gray-700 text-gray-300 border-gray-600/30'
                            };
                            return (
                                <span
                                    key={state}
                                    className={`px-2 py-0.5 text-[10px] font-bold uppercase rounded border transition-all duration-300 ${
                                        isActive
                                            ? `${colors[state]} shadow-md scale-105 opacity-100`
                                            : 'bg-transparent text-gray-600 border-transparent opacity-40 hover:opacity-60'
                                    }`}
                                >
                                    {state}
                                </span>
                            );
                        })}
                    </div>
                </div>

                {/* Agent Control Actions */}
                <div className="flex items-center gap-2">
                    {agentTaskStatus !== 'idle' && agentTaskStatus !== 'paused' && (
                        <button
                            onClick={pauseAgent}
                            className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded bg-amber-500/10 hover:bg-amber-500/25 border border-amber-500/35 text-amber-400 transition-colors"
                            title="Pause Agent Graph Loop"
                        >
                            <Pause size={12} />
                            <span>Pause</span>
                        </button>
                    )}
                    {agentTaskStatus === 'paused' && (
                        <button
                            onClick={resumeAgent}
                            className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded bg-emerald-500/10 hover:bg-emerald-500/25 border border-emerald-500/35 text-emerald-400 transition-colors animate-pulse"
                            title="Resume Agent Graph Loop"
                        >
                            <Play size={12} />
                            <span>Resume</span>
                        </button>
                    )}
                    {agentTaskStatus !== 'idle' && (
                        <button
                            onClick={triggerCancelTask}
                            className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded bg-red-500/10 hover:bg-red-500/25 border border-red-500/35 text-red-400 transition-colors"
                            title="Cancel Agent Task Loop"
                        >
                            <Square size={12} />
                            <span>Cancel</span>
                        </button>
                    )}
                </div>
            </div>

            {/* 2. ACTIVE PROCESS CONTROL HEADER */}
            {(activeCommand || foregroundProcess) && (
                <div className="border-b border-[#1e293b] bg-[#13161c] px-4 py-2 shrink-0 flex items-center justify-between gap-4 transition-all duration-200">
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                        <div className="flex items-center gap-1.5 shrink-0">
                            <span className="relative flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                            </span>
                            <span className="text-xs font-bold text-emerald-400">COMMAND RUNNING</span>
                        </div>
                        <div className="flex items-center gap-1 text-[11px] font-mono bg-[#07080a] border border-[#1e293b] rounded px-2 py-0.5 text-gray-300 truncate max-w-md" title={activeCommand || foregroundProcess?.command}>
                            <span className="text-gray-500 shrink-0">$</span>
                            <span className="truncate">{activeCommand || foregroundProcess?.command}</span>
                        </div>
                        
                        <div className="flex items-center gap-3 shrink-0">
                            <div className="flex items-center gap-1 text-[10px] text-gray-400 font-mono">
                                <Cpu size={12} className="text-gray-500" />
                                <span>PID: {activeCommandPid || foregroundProcess?.pid || 'unknown'}</span>
                            </div>
                            <div className="flex items-center gap-1 text-[10px] text-gray-400 font-mono">
                                <Clock size={12} className="text-gray-500" />
                                <span>{runtimeDuration}s</span>
                            </div>
                        </div>

                        {renderLongRunningWarning()}
                    </div>

                    {/* Process Control Buttons */}
                    <div className="flex items-center gap-1.5 shrink-0">
                        <button
                            onClick={() => {
                                const pid = activeCommandPid || foregroundProcess?.pid;
                                if (pid) killProcess(pid, 2); // SIGINT stop
                                if (pid) {
                                    appendInteractiveOutput(`\r\n\x1b[33mStop button clicked. SIGINT sent to process PID ${pid}\x1b[0m\r\n`, activeSessionId);
                                } else {
                                    appendInteractiveOutput(`\r\n\x1b[33mStop button clicked. Sending Ctrl+C to terminal...\x1b[0m\r\n`, activeSessionId);
                                }
                            }}
                            className="px-2.5 py-1 text-xs font-bold rounded bg-amber-500 text-black hover:bg-amber-400 transition-colors"
                            title="Stop current process (SIGINT / Ctrl+C)"
                        >
                            Stop
                        </button>
                        <button
                            onClick={() => {
                                const pid = activeCommandPid || foregroundProcess?.pid;
                                triggerForceKill(pid || null);
                            }}
                            className="px-2.5 py-1 text-xs font-bold rounded bg-red-600 text-white hover:bg-red-500 transition-colors"
                            title="Force terminate process (SIGKILL / 9)"
                        >
                            Force Kill
                        </button>
                        <button
                            onClick={restartCommand}
                            className="flex items-center gap-1 px-2.5 py-1 text-xs font-bold rounded bg-blue-600 text-white hover:bg-blue-500 transition-colors"
                            title="Restart running process"
                        >
                            <RefreshCw size={12} />
                            <span>Restart</span>
                        </button>
                        <button
                            onClick={() => {
                                if (activeTab === 'agent') {
                                    clearInteractive(activeSessionId);
                                } else if (activeTab === 'app-logs') {
                                    clearAppLogs(activeSessionId);
                                }
                            }}
                            className="px-2.5 py-1 text-xs font-bold rounded bg-gray-700 text-gray-200 hover:bg-gray-600 transition-colors"
                            title="Clear active terminal output"
                        >
                            Clear
                        </button>
                    </div>
                </div>
            )}

            {/* Tab Header */}
            <div className="flex items-center justify-between border-b border-[#1e293b] px-4 py-1.5 shrink-0 bg-[#07080a]">
                <div className="flex gap-2">
                    {tabs.map((tab) => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-semibold transition-all relative border ${
                                activeTab === tab.id
                                    ? 'bg-[#1e293b] text-brand border-brand/20'
                                    : 'text-gray-400 hover:text-gray-200 border-transparent'
                            }`}
                        >
                            {tab.icon}
                            <span>{tab.label}</span>
                            {tab.badge && (
                                <span className="relative flex h-2.5 w-2.5 ml-1">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-amber-500"></span>
                                </span>
                            )}
                        </button>
                    ))}
                </div>
                
                <div className="flex items-center gap-4">
                    <div className={`text-[10px] uppercase tracking-wider ${isWaiting && activeTab === 'agent' ? 'text-amber-400' : 'text-gray-500'}`}>
                        {currentTab?.sublabel}
                    </div>

                    {/* Active Processes list toggle */}
                    <button
                        onClick={() => setProcessesPanelOpen(prev => !prev)}
                        className={`flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold border transition-colors ${
                            processesPanelOpen
                                ? 'bg-teal-500/10 border-teal-500/30 text-teal-400'
                                : 'bg-[#0f1115] border-[#1e293b] text-gray-400 hover:text-gray-200'
                        }`}
                        title="Show container sandbox active processes"
                    >
                        <ListCollapse size={12} />
                        <span>Sandbox Processes ({activeProcesses.length})</span>
                    </button>
                </div>
            </div>

            {/* Interactive answer bar — visible on every tab while waiting */}
            <InteractiveInputBar />

            {/* Content Pane */}
            <div className="flex-1 min-h-0 flex relative overflow-hidden">
                
                {/* Main Terminals Grid */}
                <div className="flex-1 min-h-0 relative">
                    <div className={`absolute inset-0 p-2 transition-opacity duration-200 flex flex-col ${activeTab === 'agent' ? 'z-10 opacity-100' : 'z-0 opacity-0 pointer-events-none'}`}>
                        <div className="flex-1 min-h-0 bg-[#0f1115] rounded border border-[#1e293b] p-1">
                            <AgentTerminal xtermRef={agentTermRef} />
                        </div>
                    </div>
                    <div className={`absolute inset-0 p-2 transition-opacity duration-200 flex flex-col ${activeTab === 'app-logs' ? 'z-10 opacity-100' : 'z-0 opacity-0 pointer-events-none'}`}>
                        <div className="flex-1 min-h-0 bg-[#0a0c10] rounded border border-[#1e293b]/70 p-1">
                            <AppLogsTerminal xtermRef={appLogsTermRef} />
                        </div>
                    </div>
                    <div className={`absolute inset-0 p-2 transition-opacity duration-200 ${activeTab === 'user-terminal' ? 'z-10 opacity-100' : 'z-0 opacity-0 pointer-events-none'}`}>
                        <div className="h-full w-full bg-[#0f1115] rounded border border-[#1e293b] p-1">
                            <UserTerminal />
                        </div>
                    </div>
                </div>

                {/* COLLAPSIBLE SANDBOX PROCESSES PANEL */}
                {processesPanelOpen && (
                    <div className="w-80 border-l border-[#1e293b] bg-[#0c0d12] flex flex-col shrink-0 transition-all duration-300">
                        <div className="px-4 py-2.5 border-b border-[#1e293b] flex items-center justify-between bg-[#07080a]">
                            <span className="text-xs font-bold text-gray-400 flex items-center gap-1.5">
                                <Cpu size={14} className="text-teal-400" />
                                <span>Sandbox Process Panel</span>
                            </span>
                            <button onClick={() => setProcessesPanelOpen(false)} className="text-gray-500 hover:text-gray-300">
                                <X size={14} />
                            </button>
                        </div>
                        <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-2">
                            {activeProcesses.length === 0 ? (
                                <div className="text-center py-8 text-gray-500 text-xs font-mono">
                                    No active processes inside sandbox.
                                </div>
                            ) : (
                                activeProcesses.map((proc) => {
                                    const isForeground = foregroundProcess && foregroundProcess.pid === proc.pid;
                                    const isShell = proc.command.includes('bash') || proc.command.includes('sh');
                                    return (
                                        <div
                                            key={proc.pid}
                                            className={`p-2 rounded border transition-colors ${
                                                isForeground
                                                    ? 'bg-teal-500/5 border-teal-500/30'
                                                    : 'bg-[#0f1115] border-[#1e293b]'
                                            }`}
                                        >
                                            <div className="flex items-start justify-between gap-2">
                                                <div className="min-w-0 flex-1">
                                                    <div className="flex items-center gap-1.5 flex-wrap">
                                                        <span className="text-[10px] font-bold font-mono bg-gray-800 text-gray-300 px-1.5 py-0.5 rounded">PID: {proc.pid}</span>
                                                        {isForeground && (
                                                            <span className="px-1.5 py-0.5 text-[8px] font-bold uppercase rounded bg-teal-500 text-black">Foreground</span>
                                                        )}
                                                        <span className={`px-1.5 py-0.5 text-[8px] font-semibold rounded font-mono ${
                                                            proc.status === 'R' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-gray-800 text-gray-400'
                                                        }`}>
                                                            {proc.status === 'R' ? 'RUNNING' : 'SLEEPING'}
                                                        </span>
                                                    </div>
                                                    <div className="text-[11px] font-mono text-gray-300 mt-1.5 break-all line-clamp-2" title={proc.command}>
                                                        {proc.command}
                                                    </div>
                                                </div>

                                                {/* Action controls for processes */}
                                                {!isShell && (
                                                    <div className="flex flex-col gap-1 shrink-0">
                                                        <button
                                                            onClick={() => {
                                                                killProcess(proc.pid, 2); // SIGINT
                                                                appendInteractiveOutput(`\r\n\x1b[33mSIGINT sent to PID ${proc.pid}\x1b[0m\r\n`, activeSessionId);
                                                            }}
                                                            className="px-1.5 py-0.5 text-[9px] font-bold rounded bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/20"
                                                            title="Stop process (SIGINT)"
                                                        >
                                                            Stop
                                                        </button>
                                                        <button
                                                            onClick={() => triggerForceKill(proc.pid)}
                                                            className="px-1.5 py-0.5 text-[9px] font-bold rounded bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20"
                                                            title="Force Kill (SIGKILL)"
                                                        >
                                                            Kill
                                                        </button>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })
                            )}
                        </div>
                    </div>
                )}
            </div>

            {/* 3. ADVANCED STDIN TEXTAREA BOX (Always visible under Agent Terminal tab) */}
            {activeTab === 'agent' && (
                <div className="px-4 pb-4 pt-1 shrink-0 border-t border-[#1e293b]/70 bg-[#07080a] relative">
                    
                    {/* Command suggestions overlay */}
                    {suggestions.length > 0 && (
                        <div className="absolute bottom-full left-4 right-4 bg-[#0d0e12] border border-[#1e293b] rounded-t-md shadow-2xl p-1 z-50 mb-1">
                            <div className="text-[9px] uppercase font-bold text-gray-500 px-2 py-0.5 border-b border-[#1e293b] mb-1 flex justify-between">
                                <span>Suggestions (Tab to accept, ↑/↓ to navigate)</span>
                                <span>{suggestions.length} matches</span>
                            </div>
                            <div className="max-h-40 overflow-y-auto">
                                {suggestions.map((sug, idx) => (
                                    <button
                                        key={sug}
                                        onClick={() => {
                                            setInputValue(sug);
                                            setSuggestions([]);
                                        }}
                                        className={`w-full text-left px-2 py-1 text-xs font-mono rounded transition-colors flex items-center justify-between ${
                                            idx === activeSuggestionIdx
                                                ? 'bg-[#1e293b] text-brand font-bold'
                                                : 'text-gray-400 hover:bg-[#151922] hover:text-gray-200'
                                        }`}
                                    >
                                        <span>{sug}</span>
                                        <span className="text-[9px] text-gray-600 font-sans">autocomplete</span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    <div className="flex gap-2 items-end">
                        <div className={`flex-1 flex flex-col rounded-lg border bg-[#0d0e12] px-3 py-1.5 transition-all duration-300 focus-within:ring-1 focus-within:ring-brand/50 ${
                            isWaiting 
                                ? 'border-amber-500/50 shadow-[0_0_8px_rgba(245,158,11,0.15)] focus-within:border-amber-400' 
                                : 'border-[#1e293b] focus-within:border-brand/60'
                        }`}>
                            <div className="flex items-center justify-between mb-1 shrink-0 select-none">
                                <span className={`text-[9px] font-bold uppercase tracking-wider ${isWaiting ? 'text-amber-400 animate-pulse' : 'text-gray-500'}`}>
                                    {isWaiting ? '● COMMAND WAITING FOR INPUT' : '● agent standard input'}
                                </span>
                                <span className="text-[8px] text-gray-600 font-mono">
                                    Ctrl+L (clear) · Ctrl+C (stop) · Ctrl+Shift+C (copy)
                                </span>
                            </div>

                            <textarea
                                ref={textareaRef}
                                rows={1}
                                value={inputValue}
                                onChange={(e) => setInputValue(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder={isWaiting ? "Type response here..." : "⌨ Type command or input to running terminal..."}
                                className="w-full bg-transparent resize-none overflow-y-auto text-xs text-gray-200 font-mono focus:outline-none py-1 min-h-[24px] max-h-[120px] leading-relaxed"
                            />
                        </div>

                        <div className="flex flex-col gap-1">
                            {inputValue.trim() && (
                                <button
                                    onClick={() => setInputValue('')}
                                    className="p-1 rounded hover:bg-gray-800 text-gray-500 hover:text-gray-300 self-end transition-colors"
                                    title="Clear input"
                                >
                                    <X size={14} />
                                </button>
                            )}
                            <button
                                onClick={() => submitStdin(inputValue)}
                                className={`px-4 py-2 rounded-lg text-xs font-bold transition-all shadow-md shrink-0 ${
                                    isWaiting
                                        ? 'bg-amber-500 text-black hover:bg-amber-400'
                                        : 'bg-brand text-black hover:bg-brand-hover'
                                }`}
                            >
                                Send
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* 4. SAFETY CONFIRMATION MODALS */}
            {confirmModal.open && (
                <div className="absolute inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-[999] animate-fade-in">
                    <div className="bg-[#0f1115] border border-[#1e293b] rounded-lg max-w-sm w-full p-4 shadow-2xl">
                        <div className="flex items-center gap-2 mb-3">
                            <AlertCircle className="text-red-500" size={18} />
                            <h3 className="text-sm font-bold text-gray-200">{confirmModal.title}</h3>
                        </div>
                        <p className="text-xs text-gray-400 mb-5 leading-relaxed">
                            {confirmModal.message}
                        </p>
                        <div className="flex items-center justify-end gap-2.5">
                            <button
                                onClick={() => setConfirmModal(prev => ({ ...prev, open: false }))}
                                className="px-3 py-1.5 rounded text-xs font-semibold bg-gray-850 hover:bg-gray-800 text-gray-300 transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={confirmModal.action}
                                className="px-3 py-1.5 rounded text-xs font-bold bg-red-600 hover:bg-red-500 text-white transition-colors"
                            >
                                Confirm
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
