import { useEffect, useState } from 'react';
import { Pause, Play, RefreshCcw, Square, Trash2, Box, Download } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/backend';
import { queryKeys } from '../api/queryKeys';
import { useAgentStore } from '../store/agentStore';
import { useAgentStream } from '../hooks/useAgentStream';
import { SandboxManagerModal } from './SandboxManagerModal';

export function SandboxPanel() {
    const [showManager, setShowManager] = useState(false);
    const { activeSessionId, sandboxBySession, previewUrlBySession, setSandbox, setPreviewUrl, addLog, setError } = useAgentStore();
    const sandbox = sandboxBySession[activeSessionId] || null;
    const previewUrl = previewUrlBySession[activeSessionId] || null;
    const { refreshSandbox, retryPending } = useAgentStream();
    const queryClient = useQueryClient();

    const { data: sandboxStatus } = useQuery({
        queryKey: queryKeys.sandbox.status(activeSessionId),
        queryFn: () => api.sandbox.status(activeSessionId),
        enabled: Boolean(activeSessionId),
        staleTime: 3000,
    });

    useEffect(() => {
        if (sandboxStatus) setSandbox(sandboxStatus);
    }, [sandboxStatus, setSandbox]);

    const pauseMutation = useMutation({
        mutationFn: () => api.sandbox.pause(activeSessionId),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.sandbox.status(activeSessionId) }),
    });

    const resumeMutation = useMutation({
        mutationFn: () => api.sandbox.resume(activeSessionId),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.sandbox.status(activeSessionId) }),
    });

    const deleteMutation = useMutation({
        mutationFn: () => api.sandbox.delete(activeSessionId),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.sandbox.status(activeSessionId) }),
    });

    const runAction = async (label: string, action: () => Promise<unknown>) => {
        try {
            await action();
            addLog(`> ${label}`);
            await refreshSandbox(activeSessionId);
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            setError(message);
            addLog(`> ${label} failed: ${message}`);
        }
    };

    const isRunning = sandbox?.status === 'running';

    return (
        <div className="h-10 border-b border-border/40 bg-surface flex items-center gap-2 px-3 text-xs shrink-0">
            <span className="text-text-muted font-medium">Sandbox</span>
            <span className={`px-2 py-0.5 rounded text-[11px] font-medium border ${
                isRunning
                    ? 'border-emerald-500/20 text-emerald-400 bg-emerald-500/10'
                    : 'border-border/40 text-text-muted bg-surface-hover'
            }`}>
                {sandbox?.status || 'unknown'}
            </span>
            {previewUrl && <span className="text-text-muted truncate max-w-52 text-[11px] font-mono">{previewUrl}</span>}

            <div className="ml-auto flex items-center gap-1">
                <button title="Refresh" className="icon-btn" onClick={() => refreshSandbox(activeSessionId)}>
                    <RefreshCcw size={13} />
                </button>
                <button title="Retry queued message" className="icon-btn" onClick={retryPending}>
                    <Play size={13} />
                </button>
                <button
                    title="Pause sandbox"
                    className="icon-btn"
                    onClick={() => runAction('Sandbox paused', () => pauseMutation.mutateAsync())}
                >
                    <Pause size={13} />
                </button>
                <button
                    title="Resume sandbox"
                    className="icon-btn"
                    onClick={() => runAction('Sandbox resumed', () => resumeMutation.mutateAsync())}
                >
                    <Square size={13} />
                </button>
                <button
                    title="Delete current sandbox"
                    className="icon-btn text-rose-400 hover:text-rose-300"
                    onClick={() => runAction('Sandbox deleted', async () => {
                        await deleteMutation.mutateAsync();
                        setSandbox(null);
                        setPreviewUrl(null);
                    })}
                >
                    <Trash2 size={13} />
                </button>
                <div className="w-px h-3 bg-border/40 mx-1" />
                <button
                    title="Download Workspace (ZIP)"
                    className="btn-secondary h-7 px-2.5 text-xs"
                    onClick={() => {
                        window.open(`http://127.0.0.1:8000/api/agent/sandbox/${activeSessionId}/download`, '_blank');
                    }}
                >
                    <Download size={13} />
                    <span>Download</span>
                </button>
                <button
                    title="Manage all sandboxes"
                    className="btn-secondary h-7 px-2.5 text-xs"
                    onClick={() => setShowManager(true)}
                >
                    <Box size={13} />
                    <span>Manage</span>
                </button>
            </div>
            
            {showManager && <SandboxManagerModal onClose={() => setShowManager(false)} />}
        </div>
    );
}
