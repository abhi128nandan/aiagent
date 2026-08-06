import { useCallback, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api, getWebSocketUrl } from '../api/backend';
import { queryKeys } from '../api/queryKeys';
import { useAgentStore } from '../store/agentStore';

interface LangGraphEvent {
    type: string;
    node?: string;
    data?: any;
    chunk?: string;
    seq?: number;
    replay?: boolean;
    ts?: number;
}

const extractWrite = (content: string) =>
    content.match(/<write\s+path=['"]([^'"]+)['"]>([\s\S]*?)<\/write>/);

const logAgentEvent = (msg: string, sessionId?: string) => {
    const store = useAgentStore.getState();
    const id = sessionId || store.activeSessionId;
    if (!id) return;
    store.addLog(msg, id);
    let color = '\x1b[90m'; // gray
    if (msg.includes('✅') || msg.includes('📦')) color = '\x1b[32m'; // green
    if (msg.includes('❌')) color = '\x1b[31m'; // red
    if (msg.includes('⏳') || msg.includes('📝')) color = '\x1b[36m'; // cyan
    if (msg.includes('🔧') || msg.includes('⌨')) color = '\x1b[33m'; // yellow
    store.appendInteractiveOutput(`\r\n${color}${msg.replace(/\n/g, '\r\n')}\x1b[0m\r\n`, id);
};

export function useAgentStream() {
    const queryClient = useQueryClient();
    const ws = useRef<WebSocket | null>(null);
    const isReceivingStream = useRef(false);
    const retryCount = useRef(0);
    const reconnectTimer = useRef<number | null>(null);
    const lastSeq = useRef<Record<string, number>>({});

    const refreshSandbox = useCallback(async (sessionId: string) => {
        const store = useAgentStore.getState();
        try {
            const [sandbox, fileList] = await Promise.all([
                api.sandbox.status(sessionId),
                api.sandbox.files(sessionId),
            ]);

            const files: Record<string, string> = {};
            await Promise.all(fileList.files.map(async (path) => {
                if (
                    path.includes('node_modules/') ||
                    path.includes('.git/') ||
                    path.includes('venv/') ||
                    path.includes('.venv/') ||
                    path.includes('.agents/') ||
                    path.includes('.codex/')
                ) {
                    return;
                }
                try {
                    files[path] = (await api.sandbox.readFile(sessionId, path)).content;
                } catch (error) {
                    logAgentEvent(`> Could not read ${path}: ${error instanceof Error ? error.message : String(error)}`, sessionId);
                }
            }));

            store.setSandbox(sandbox, sessionId);
            store.replaceFiles(files, sessionId);

            for (const port of [3000, 5173, 8000]) {
                try {
                    const health = await api.sandbox.health(sessionId, port);
                    if (health.healthy && health.url) {
                        store.setPreviewUrl(health.url, sessionId);
                        return;
                    }
                } catch {
                    // App preview is optional; keep looking across common ports.
                }
            }

            queryClient.invalidateQueries({ queryKey: queryKeys.sandbox.status(sessionId) });
            queryClient.invalidateQueries({ queryKey: queryKeys.sandbox.files(sessionId) });
        } catch (error) {
            logAgentEvent(`> Sandbox refresh failed: ${error instanceof Error ? error.message : String(error)}`, sessionId);
        }
    }, [queryClient]);

    const handleAgentContent = useCallback((content: string, sessionId: string) => {
        const store = useAgentStore.getState();
        if (!content.trim()) return;

        store.addMessage({ role: 'agent', content }, sessionId);

        const writeMatch = extractWrite(content);
        if (writeMatch) {
            store.setFile(writeMatch[1], writeMatch[2].trim(), sessionId);
        }
    }, []);

    const handleEvent = useCallback((event: LangGraphEvent, sessionId: string) => {
        if (typeof event.seq === 'number') {
            const currentSeq = lastSeq.current[sessionId] || 0;
            if (event.seq <= currentSeq) return;
            lastSeq.current[sessionId] = event.seq;
        }

        const store = useAgentStore.getState();

        // ── Streaming parser events (real-time file preview) ──────────
        if (event.type === 'action_open' && (event as any).action === 'write') {
            store.startFileStream((event as any).path, sessionId);
            logAgentEvent(`> 📝 Writing ${(event as any).path}...`, sessionId);
            return;
        }

        if (event.type === 'action_chunk' && (event as any).action === 'write') {
            // content contains the FULL body so far, not a delta
            const fullContent = (event as any).content || '';
            const current = store.streamingFileBySession[sessionId];
            if (current && current.isStreaming) {
                // Replace rather than append since parser sends full body
                const id = sessionId || store.activeSessionId;
                const files = store.filesBySession[id] || {};
                useAgentStore.setState({
                    streamingFileBySession: {
                        ...store.streamingFileBySession,
                        [id]: { ...current, content: fullContent },
                    },
                    filesBySession: {
                        ...store.filesBySession,
                        [id]: { ...files, [current.path]: fullContent },
                    },
                });
            }
            return;
        }

        if (event.type === 'action_close' && (event as any).action === 'write') {
            store.completeFileStream((event as any).content || '', sessionId);
            logAgentEvent(`> ✅ Wrote ${(event as any).path}`, sessionId);
            return;
        }

        if (event.type === 'action_exec') {
            const exitCode = (event as any).exit_code;
            const icon = exitCode === 0 ? '✅' : '❌';
            const detail = (event as any).command || (event as any).path || (event as any).query || '';
            logAgentEvent(`> ${icon} ${(event as any).action}: ${detail} (exit: ${exitCode})`, sessionId);
            return;
        }

        if (event.type === 'action_exec_start') {
            logAgentEvent(`> ⏳ [${(event as any).index}/${(event as any).total}] ${(event as any).action}: ${(event as any).detail}`, sessionId);
            return;
        }

        if (event.type === 'command_auto_fixed') {
            logAgentEvent(`> 🔧 Auto-fixed command: "${(event as any).original}" ➡️ "${(event as any).fixed}" (${(event as any).warning})`, sessionId);
            return;
        }

        if (event.type === 'batch_complete') {
            logAgentEvent(`> 📦 Batch: ${(event as any).succeeded}/${(event as any).total} actions succeeded`, sessionId);
            void refreshSandbox(sessionId);
            return;
        }
        // ── Custom process and command monitoring events ──────────
        if (event.type === 'process_start') {
            store.setActiveCommand((event as any).command || '', sessionId);
            store.setActiveCommandStart(Date.now(), sessionId);
            store.setActiveCommandPid(null, sessionId);
            return;
        }
        if (event.type === 'process_end') {
            store.setActiveCommand(null, sessionId);
            store.setActiveCommandStart(null, sessionId);
            store.setActiveCommandPid(null, sessionId);
            return;
        }
        if (event.type === 'foreground_pid') {
            store.setActiveCommandPid((event as any).pid || null, sessionId);
            return;
        }
        if (event.type === 'process_list') {
            store.setActiveProcesses((event as any).processes || [], sessionId);
            if ((event as any).foreground_process) {
                store.setForegroundProcess((event as any).foreground_process, sessionId);
            } else {
                store.setForegroundProcess(null, sessionId);
            }
            return;
        }
        if (event.type === 'agent_cancelled') {
            store.setAgentTaskStatus('idle', sessionId);
            return;
        }

        // ── Agent log events (command summaries → Agent Terminal) ────────
        if (event.type === 'agent_log') {
            const data = (event as any).data || '';
            store.appendInteractiveOutput(data, sessionId);
            return;
        }

        // ── Interactive terminal events ───────────────────────────────
        if (event.type === 'interactive_output') {
            const data = (event as any).data || '';
            // Route raw command output to App Logs terminal (not Agent Terminal)
            store.appendAppLog(data, sessionId);
            store.addLog(data, sessionId);
            return;
        }

        if (event.type === 'interactive_waiting') {
            const stripAnsi = (s: string) => s.replace(/\x1b\[[0-9;]*m/g, '').trim();
            const promptText = stripAnsi((event as any).prompt || '');
            const contextText = stripAnsi((event as any).context || '');
            const commandText = stripAnsi((event as any).command || '');
            const certain = (event as any).certain !== false;
            const options = ((event as any).options || []) as { label: string; selected: boolean }[];

            // Skip duplicate notifications for the same prompt
            const existing = useAgentStore.getState().interactiveBySession[sessionId];
            if (existing?.active && existing.prompt === promptText) return;

            store.setInteractive(true, sessionId, { prompt: promptText, command: commandText, certain, options });

            const parts: string[] = [];
            parts.push(certain
                ? '⌨ **The running command is asking you a question:**'
                : '⌨ **The running command has stalled — it may be waiting for input:**');
            if (commandText) parts.push(`Command: \`${commandText}\``);
            parts.push('```\n' + (promptText || contextText || '(no prompt text captured)') + '\n```');
            parts.push(options.length >= 2
                ? '👉 Click one of the **option buttons** in the **Agent Terminal** panel below to choose.'
                : '👉 Type your answer in the **amber input box** in the **Agent Terminal** panel below (or press Enter there to accept the default).');
            store.addMessage({ role: 'system', content: parts.join('\n') }, sessionId);
            logAgentEvent(`\r\n\x1b[33m⌨ Command is waiting for your input:\x1b[0m\r\n${promptText || contextText}\r\n`, sessionId);
            return;
        }

        if (event.type === 'interactive_done') {
            store.clearInteractive(sessionId);
            return;
        }

        // Skip text_chunk and action_open/close for non-write actions
        if (event.type === 'text_chunk' || event.type === 'action_open' || event.type === 'action_close' || event.type === 'action_chunk') {
            return;
        }

        store.addEvent(event, sessionId);

        // ── Log node transitions to the interactive terminal ──────────────
        if (event.type === 'on_chain_start' && event.node) {
            const nodeLabels: Record<string, string> = {
                plan_bootstrap: '📋 Planning architecture...',
                plan_detail: '📝 Generating file-level plan...',
                setup_environment: '🔧 Setting up environment...',
                implement: '🔨 Implementing code...',
                execute: '🔨 Executing node...',
                validate: '✅ Validating output...',
                judge: '⚖️ Reviewing plan quality...',
                research: '🔍 Researching solutions...',
            };
            const label = nodeLabels[event.node];
            if (label) {
                logAgentEvent(`> ${label}`, sessionId);
            }

            // Update agent task status based on current node
            if (['plan_bootstrap', 'plan_detail', 'research', 'judge', 'setup_environment'].includes(event.node)) {
                store.setAgentTaskStatus('planning', sessionId);
            } else if (event.node === 'implement') {
                store.setAgentTaskStatus('writing', sessionId);
            } else if (event.node === 'execute') {
                store.setAgentTaskStatus('testing', sessionId);
            } else if (event.node === 'validate') {
                store.setAgentTaskStatus('validating', sessionId);
            }
        }

        if (event.type === 'on_chat_model_stream') {
            if (!event.chunk) return;
            if (!isReceivingStream.current) {
                isReceivingStream.current = true;
                store.addMessage({ role: 'agent', content: event.chunk }, sessionId);
            } else {
                store.updateLastMessage(event.chunk, sessionId);
            }
            return;
        }

        if (event.type === 'observability_log') {
            const logData = (event as any).log;
            if (logData) {
                store.addObservabilityLog(logData, sessionId);
            }
            return;
        }

        if (event.type === 'error') {
            const errorMsg = event.data?.message || event.chunk || (event as any).message || (event as any).error || 'An unknown error occurred';
            logAgentEvent(`> ❌ Error: ${errorMsg}`, sessionId);
            store.addMessage({ role: 'agent', content: `❌ **Error**: ${errorMsg}` }, sessionId);
            store.setStatus('error');
            store.setAgentTaskStatus('idle', sessionId);
            return;
        }


        if (event.type === 'on_chain_end') {
            isReceivingStream.current = false;

            const output = event.data?.output;
            const content = output?.content;
            if (typeof content === 'string' && ['plan', 'implement', 'RunnableSequence'].includes(event.node || '')) {
                handleAgentContent(content, sessionId);
            }

            // Extract plan from plan node output
            if (event.node === 'plan' && output?.plan) {
                try {
                    const parsedPlan = typeof output.plan === 'string' ? JSON.parse(output.plan) : output.plan;
                    store.setPlan(parsedPlan, sessionId);
                } catch (e) {
                    console.warn("Failed to parse plan JSON", e);
                }
            }

            if (event.node === 'architecture_plan') {
                void store.fetchArchitecturalPlan(sessionId);
            }

            const observation = output?.last_obs;
            if (observation) {
                logAgentEvent(`> ${observation.output || JSON.stringify(observation)}`, sessionId);
                void refreshSandbox(sessionId);
            }

            if (output?.status) {
                store.setStatus(output.status);
                if (output.status === 'done' || output.status === 'error') {
                    store.setAgentTaskStatus('idle', sessionId);
                }
            }

            // Extract token usage from implement node output
            if (typeof output?.token_count === 'number') {
                const budgetTokens = output?.context_budget?.conversation || 4096;
                const activeModules: string[] = [];
                if (output?.token_count > 0) activeModules.push('ctx');
                if (output?.last_error_analysis) activeModules.push('err');
                if (output?.workspace_summary) activeModules.push('ws');
                store.setTokenUsage({
                    messageTokens: output.token_count,
                    budgetTokens,
                    usagePercent: Math.round((output.token_count / budgetTokens) * 100),
                    activeModules,
                }, sessionId);
            }

            // Extract error analysis
            if (output?.error_history && Array.isArray(output.error_history)) {
                const latest = output.error_history[output.error_history.length - 1];
                if (latest) {
                    store.addErrorAnalysis({
                        category: latest.category || 'unknown',
                        severity: latest.severity || 'medium',
                        errorType: latest.error_type || 'Error',
                        message: latest.message || '',
                        file: latest.file,
                        line: latest.line,
                        suggestion: latest.suggestion,
                    }, sessionId);
                }
            }
        }

        if (event.type === 'on_tool_end' && event.node === 'execute') {
            const obs = event.data?.output;
            if (obs) {
                logAgentEvent(`> [${new Date().toLocaleTimeString()}] ${JSON.stringify(obs)}`, sessionId);
                void refreshSandbox(sessionId);
            }
        }

        if (event.node) {
            store.setStatus(`running: ${event.node}`);
        }
    }, [handleAgentContent, refreshSandbox]);

    const openAndSend = useCallback((message: string, sessionId: string, action: 'start' | 'resume' = 'start') => {
        const store = useAgentStore.getState();

        if (ws.current) {
            // Detach handlers BEFORE closing — a stale socket's onclose must
            // never fire reconnect logic for an old session, and a stale
            // CONNECTING socket must never send its old start message.
            ws.current.onopen = null;
            ws.current.onmessage = null;
            ws.current.onerror = null;
            ws.current.onclose = null;
            try { ws.current.close(1000); } catch { /* already closed */ }
        }

        if (reconnectTimer.current) {
            window.clearTimeout(reconnectTimer.current);
            reconnectTimer.current = null;
        }

        store.setConnectionState('connecting');
        store.setStatus('connecting');
        store.setError(null);

        const socket = new WebSocket(getWebSocketUrl());
        ws.current = socket;
        // Share the WebSocket reference via the store so any component
        // (e.g. the Terminal) can send interactive input through it.
        store.setAgentWs(socket);

        socket.onopen = () => {
            if (ws.current !== socket) return; // superseded by a newer connection
            retryCount.current = 0;
            store.setConnectionState('open');
            store.setStatus(action === 'resume' ? 'running: resuming' : 'planning');
            store.setAgentTaskStatus('planning', sessionId);
            logAgentEvent(`> ⚡ Agent connected. ${action === 'resume' ? 'Resuming...' : 'Processing your request...'}`, sessionId);
            const lastSeqForSession = lastSeq.current[sessionId] || 0;
            socket.send(JSON.stringify({
                session_id: sessionId,
                action,
                message,
                chat_mode: store.chatModeBySession[sessionId] || 'build',
                locked_files: store.lockedFilesBySession[sessionId] || [],
                last_seq: lastSeqForSession,
            }));
        };

        socket.onmessage = (e) => {
            if (ws.current !== socket) return;
            try {
                const event = JSON.parse(e.data) as LangGraphEvent;
                if (event.type === 'ping') {
                    socket.send(JSON.stringify({
                        type: 'pong',
                        ts: event.ts,
                        last_seq: lastSeq.current[sessionId] || 0,
                    }));
                    return;
                }
                handleEvent(event, sessionId);
            } catch (error) {
                store.setError('Failed to parse backend event');
                logAgentEvent(`> Event parse error: ${error instanceof Error ? error.message : String(error)}`, sessionId);
            }
        };

        socket.onerror = () => {
            if (ws.current !== socket) return;
            store.setConnectionState('error');
            store.setStatus('error');
            store.setError('WebSocket error. Backend may be offline.');
        };

        socket.onclose = (event) => {
            if (ws.current !== socket) return; // a newer connection took over
            store.setConnectionState(event.code === 1000 ? 'closed' : 'error');
            store.setAgentWs(null);  // Clear shared WS reference

            if (event.code !== 1000) {
                retryCount.current += 1;
                const delay = Math.min(1000 * (2 ** (retryCount.current - 1)), 30000);
                logAgentEvent(`> WebSocket closed unexpectedly. Reconnecting in ${Math.round(delay / 1000)}s...`, sessionId);
                reconnectTimer.current = window.setTimeout(() => openAndSend(message, sessionId, action), delay);
                if (retryCount.current > 6) {
                    store.queuePending(message, sessionId);
                    store.setError('Message queued. Reconnect or send again when backend is ready.');
                }
                return;
            }

            if (store.status !== 'error') {
                store.setStatus('idle');
                store.setAgentTaskStatus('idle', sessionId);
                logAgentEvent(`> ✅ Agent task completed.`, sessionId);
            } else {
                store.setAgentTaskStatus('idle', sessionId);
            }
        };
    }, [handleEvent]);

    const send = useCallback((message: string) => {
        const store = useAgentStore.getState();
        const sessionId = store.activeSessionId;
        store.addMessage({ role: 'user', content: message }, sessionId);
        openAndSend(message, sessionId, 'start');
    }, [openAndSend]);

    const resume = useCallback(() => {
        const store = useAgentStore.getState();
        const sessionId = store.activeSessionId;
        logAgentEvent(`> Resuming agent execution...`, sessionId);
        openAndSend('', sessionId, 'resume');
    }, [openAndSend]);

    const retryPending = useCallback(() => {
        const store = useAgentStore.getState();
        const sessionId = store.activeSessionId;
        const message = store.popPending(sessionId);
        if (message) openAndSend(message, sessionId, 'start');
    }, [openAndSend]);

    const stop = useCallback(() => {
        const store = useAgentStore.getState();
        if (ws.current) {
            ws.current.close(1000);
        }
        if (reconnectTimer.current) {
            window.clearTimeout(reconnectTimer.current);
            reconnectTimer.current = null;
        }
        store.setStatus('idle');
        store.setConnectionState('closed');
        logAgentEvent(`> Generation stopped by user.`, store.activeSessionId);
    }, []);

    return { send, resume, retryPending, refreshSandbox, stop };
}
