import React, { useEffect, useState } from 'react';
import { api } from '../api/backend';
import type { SandboxInfo } from '../store/agentStore';
import { Trash2, Box, RefreshCcw, X } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '../api/queryKeys';

interface SandboxManagerModalProps {
    onClose: () => void;
}

export const SandboxManagerModal: React.FC<SandboxManagerModalProps> = ({ onClose }) => {
    const [sandboxes, setSandboxes] = useState<SandboxInfo[]>([]);
    const [loading, setLoading] = useState(true);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const queryClient = useQueryClient();

    const fetchSandboxes = async () => {
        setLoading(true);
        try {
            const data = await api.sandbox.listAll();
            setSandboxes(data.sandboxes);
        } catch (error) {
            console.error('Failed to fetch sandboxes:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        let isCurrent = true;
        api.sandbox.listAll()
            .then(data => {
                if (isCurrent) setSandboxes(data.sandboxes);
            })
            .catch(error => {
                console.error('Failed to fetch sandboxes:', error);
            })
            .finally(() => {
                if (isCurrent) setLoading(false);
            });
        return () => {
            isCurrent = false;
        };
    }, []);

    const handleDelete = async (sessionId: string) => {
        setDeletingId(sessionId);
        try {
            await api.sandbox.delete(sessionId);
            setSandboxes(prev => prev.filter(s => s.session_id !== sessionId));
            // Invalidate current sandbox if we just deleted it
            queryClient.invalidateQueries({ queryKey: queryKeys.sandbox.status(sessionId) });
        } catch (error) {
            console.error('Failed to delete sandbox:', error);
        } finally {
            setDeletingId(null);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="bg-surface w-full max-w-2xl rounded-xl border border-border shadow-2xl flex flex-col max-h-[85vh]">
                <div className="flex items-center justify-between p-4 border-b border-border bg-surface-hover rounded-t-xl">
                    <div className="flex items-center gap-2 text-text font-medium">
                        <Box size={18} className="text-brand" />
                        <h2>Docker Sandboxes Manager</h2>
                    </div>
                    <div className="flex items-center gap-2">
                        <button 
                            onClick={fetchSandboxes} 
                            disabled={loading}
                            className="p-1.5 hover:bg-surface text-text-muted hover:text-text rounded transition-colors"
                            title="Refresh list"
                        >
                            <RefreshCcw size={16} className={loading ? 'animate-spin' : ''} />
                        </button>
                        <button 
                            onClick={onClose}
                            className="p-1.5 hover:bg-red-900/50 text-text-muted hover:text-red-400 rounded transition-colors"
                        >
                            <X size={18} />
                        </button>
                    </div>
                </div>

                <div className="p-4 overflow-y-auto flex-1">
                    {loading && sandboxes.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-32 text-text-muted">
                            <RefreshCcw size={24} className="animate-spin mb-2" />
                            <p className="text-sm">Loading sandboxes...</p>
                        </div>
                    ) : sandboxes.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-32 text-text-muted">
                            <Box size={32} className="mb-2 opacity-50" />
                            <p className="text-sm">No Docker sandboxes found.</p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {sandboxes.map(sandbox => (
                                <div key={sandbox.session_id} className="flex flex-col sm:flex-row sm:items-center justify-between p-3 bg-surface-hover border border-border rounded-lg gap-3">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className="font-mono text-xs font-semibold text-text truncate">
                                                {sandbox.container_name}
                                            </span>
                                            <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider ${
                                                sandbox.status === 'running' ? 'bg-green-900/30 text-green-400 border border-green-800' :
                                                sandbox.status === 'paused' ? 'bg-yellow-900/30 text-yellow-400 border border-yellow-800' :
                                                'bg-gray-800 text-gray-400 border border-gray-700'
                                            }`}>
                                                {sandbox.status}
                                            </span>
                                        </div>
                                        <div className="flex items-center gap-3 text-xs text-text-muted">
                                            <span>IP: <span className="text-gray-300">{sandbox.container_ip}</span></span>
                                            {sandbox.created_at > 0 && (
                                                <span>Created: {new Date(sandbox.created_at * 1000).toLocaleString()}</span>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex items-center">
                                        <button
                                            onClick={() => handleDelete(sandbox.session_id)}
                                            disabled={deletingId === sandbox.session_id}
                                            className="flex items-center gap-1 px-3 py-1.5 bg-red-950/30 hover:bg-red-900/50 text-red-400 text-xs font-medium rounded border border-red-900/50 transition-colors disabled:opacity-50"
                                        >
                                            {deletingId === sandbox.session_id ? (
                                                <RefreshCcw size={14} className="animate-spin" />
                                            ) : (
                                                <Trash2 size={14} />
                                            )}
                                            Delete
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
                
                <div className="p-3 border-t border-border bg-surface-hover text-xs text-text-muted flex items-center justify-between">
                    <span>Sandboxes automatically pause when inactive and delete after 24 hours.</span>
                    <span>Total: {sandboxes.length}</span>
                </div>
            </div>
        </div>
    );
};
