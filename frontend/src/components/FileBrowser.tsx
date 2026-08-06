import React, { useState } from 'react';
import { File, Folder, ChevronRight, RefreshCw, Lock, Unlock } from 'lucide-react';
import { useAgentStore } from '../store/agentStore';
import { useAgentStream } from '../hooks/useAgentStream';

export const FileBrowser: React.FC = () => {
    const {
        filesBySession,
        activeFileBySession,
        activeSessionId,
        setActiveFile,
        lockedFilesBySession,
        toggleFileLock,
    } = useAgentStore();
    const { refreshSandbox } = useAgentStream();
    const [isRefreshing, setIsRefreshing] = useState(false);
    
    // Get files and active file for current session
    const files = filesBySession[activeSessionId] || {};
    const activeFile = activeFileBySession[activeSessionId] || null;
    const lockedFiles = lockedFilesBySession[activeSessionId] || [];
    const fileList = Object.keys(files).sort();

    const handleRefresh = async () => {
        if (!activeSessionId || isRefreshing) return;
        setIsRefreshing(true);
        try {
            await refreshSandbox(activeSessionId);
        } finally {
            setIsRefreshing(false);
        }
    };

    return (
        <div className="h-full bg-surface text-xs flex flex-col">
            {/* Header: Sentence-Case "Workspace" */}
            <div className="h-10 px-3 border-b border-border/40 font-medium text-text flex items-center justify-between shrink-0">
                <div className="flex items-center gap-2">
                    <Folder size={14} className="text-text-muted opacity-70" />
                    <span>Workspace</span>
                </div>
                <button
                    onClick={handleRefresh}
                    className={`p-1 hover:text-text transition-colors rounded hover:bg-surface-hover ${
                        isRefreshing ? 'animate-spin text-brand' : 'text-text-muted'
                    }`}
                    title="Refresh Workspace Files"
                    disabled={!activeSessionId || isRefreshing}
                >
                    <RefreshCw size={12} />
                </button>
            </div>

            <div className="flex-1 overflow-y-auto p-1.5 space-y-0.5">
                {fileList.length === 0 ? (
                    <div className="text-text-muted text-[11px] p-3 text-center">
                        <p className="font-medium text-text mb-1">No files in workspace</p>
                        <p className="text-[10px]">Prompt the AI Agent to generate code or refresh sandbox.</p>
                    </div>
                ) : (
                    fileList.map((path) => {
                        const isLocked = lockedFiles.includes(path);
                        const isActive = activeFile === path;
                        return (
                            <div 
                                key={path}
                                className={`group flex items-center justify-between px-2.5 py-1 rounded-lg cursor-pointer transition-all ${
                                    isActive
                                        ? 'bg-brand/15 text-brand font-semibold shadow-xs'
                                        : 'text-text-muted hover:text-text hover:bg-surface-hover'
                                }`}
                            >
                                <div 
                                    className="flex items-center gap-2 flex-1 min-w-0"
                                    onClick={() => setActiveFile(path)}
                                >
                                    <ChevronRight size={12} className={isActive ? 'opacity-100 text-brand' : 'opacity-0'} />
                                    <File size={13} className={isLocked ? 'text-amber-400' : 'opacity-60'} />
                                    <span className="truncate text-xs">{path}</span>
                                </div>
                                <button
                                    type="button"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        toggleFileLock(path, activeSessionId);
                                    }}
                                    className={`p-1 rounded hover:bg-surface-hover transition-colors ${
                                        isLocked 
                                            ? 'text-amber-400 opacity-100' 
                                            : 'text-text-muted opacity-0 group-hover:opacity-100 hover:text-text'
                                    }`}
                                    title={isLocked ? "Unlock File" : "Lock File"}
                                >
                                    {isLocked ? <Lock size={11} /> : <Unlock size={11} />}
                                </button>
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
};
