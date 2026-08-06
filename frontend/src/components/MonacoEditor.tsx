import React, { useState, useEffect } from 'react';
import { Editor } from '@monaco-editor/react';
import { useAgentStore } from '../store/agentStore';
import { api } from '../api/backend';
import { Save, Loader2, Lock, Unlock, X, FileCode2, ChevronRight, Sparkles } from 'lucide-react';

const langMap: Record<string, string> = {
    py: 'python', js: 'javascript', ts: 'typescript',
    tsx: 'typescriptreact', jsx: 'javascriptreact',
    rs: 'rust', go: 'go', json: 'json', html: 'html', css: 'css',
    abap: 'abap'
};

export const CodeEditor: React.FC = () => {
    const {
        activeFileBySession,
        filesBySession,
        activeSessionId,
        setActiveFile,
        setFile,
        addLog,
        streamingFileBySession,
        lockedFilesBySession,
        toggleFileLock,
    } = useAgentStore();

    const [isSaving, setIsSaving] = useState(false);
    const [isDirty, setIsDirty] = useState(false);
    const [openTabs, setOpenTabs] = useState<string[]>([]);
    const editorRef = React.useRef<any>(null);

    // Get files for current session
    const files = filesBySession[activeSessionId] || {};
    const activeFile = activeFileBySession[activeSessionId] || null;

    // Streaming state
    const streamingFile = streamingFileBySession[activeSessionId];
    const isStreaming = !!(streamingFile?.isStreaming && streamingFile?.path === activeFile);

    const lockedFiles = lockedFilesBySession[activeSessionId] || [];
    const isLocked = activeFile ? lockedFiles.includes(activeFile) : false;

    const content = activeFile ? files[activeFile] || '' : '';
    const contentRef = React.useRef(content);
    contentRef.current = content;

    // Track active file additions to tabs
    useEffect(() => {
        if (activeFile && !openTabs.includes(activeFile)) {
            setOpenTabs(prev => [...prev, activeFile]);
        }
    }, [activeFile, openTabs]);

    const handleCloseTab = (e: React.MouseEvent, path: string) => {
        e.stopPropagation();
        const nextTabs = openTabs.filter(t => t !== path);
        setOpenTabs(nextTabs);
        if (activeFile === path) {
            const fallback = nextTabs[nextTabs.length - 1] || null;
            setActiveFile(fallback, activeSessionId);
        }
    };

    const handleSave = React.useCallback(async () => {
        if (!activeFile || isSaving) return;
        setIsSaving(true);
        try {
            await api.sandbox.writeFile(activeSessionId, activeFile, contentRef.current);
            addLog(`> Saved changes to ${activeFile}`, activeSessionId);
            setIsDirty(false);
        } catch (err) {
            console.error(err);
            addLog(`> ❌ Failed to save ${activeFile}: ${err instanceof Error ? err.message : String(err)}`, activeSessionId);
        } finally {
            setIsSaving(false);
        }
    }, [activeFile, activeSessionId, isSaving, addLog]);

    const handleSaveRef = React.useRef(handleSave);
    handleSaveRef.current = handleSave;

    // Reset dirty state on active file change
    useEffect(() => {
        setIsDirty(false);
    }, [activeFile]);

    // Auto-scroll during streaming
    useEffect(() => {
        if (isStreaming && editorRef.current) {
            const model = editorRef.current.getModel();
            if (model) {
                const lineCount = model.getLineCount();
                editorRef.current.revealLine(lineCount);
            }
        }
    }, [content, isStreaming]);

    // Actionable Empty State per Guideline #9
    if (!activeFile) {
        return (
            <div className="h-full w-full flex flex-col items-center justify-center text-text-muted bg-surface p-8 text-center select-none">
                <div className="h-12 w-12 rounded-xl bg-background border border-border flex items-center justify-center text-text-muted mb-4 shadow-xs">
                    <FileCode2 size={24} className="opacity-70" />
                </div>
                <h3 className="text-sm font-semibold text-text mb-1">No file open</h3>
                <p className="text-xs text-text-muted max-w-sm mb-6 leading-relaxed">
                    Select a file from the explorer on the left or generate your first application using the AI Agent.
                </p>
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => {
                            const chatInput = document.querySelector('input[type="text"]') as HTMLInputElement;
                            chatInput?.focus();
                        }}
                        className="btn-primary"
                    >
                        <Sparkles size={13} />
                        <span>Generate Project</span>
                    </button>
                </div>
            </div>
        );
    }

    const ext = activeFile.split('.').pop() || '';
    const lang = langMap[ext] || 'plaintext';
    const breadcrumbPath = activeFile.split('/');

    const handleEditorDidMount = (editor: any, monaco: any) => {
        editorRef.current = editor;
        editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
            handleSaveRef.current?.();
        });
    };

    const handleChange = (val: string | undefined) => {
        if (isStreaming) return;
        setFile(activeFile, val || '');
        setIsDirty(true);
    };

    const lineCount = content.split('\n').length;

    return (
        <div className="h-full w-full flex flex-col bg-surface relative">
            {/* Top Multi-Tab Bar */}
            <div className="bg-surface-hover border-b border-border flex items-center shrink-0 overflow-x-auto scrollbar-hide text-xs">
                {openTabs.map((tabPath) => {
                    const tabName = tabPath.split('/').pop() || tabPath;
                    const isActive = tabPath === activeFile;
                    return (
                        <div
                            key={tabPath}
                            onClick={() => setActiveFile(tabPath, activeSessionId)}
                            className={`flex items-center gap-2 px-3 py-1.5 border-r border-border cursor-pointer transition-colors shrink-0 text-xs ${
                                isActive
                                    ? 'bg-surface text-text border-t-2 border-t-brand font-medium shadow-xs'
                                    : 'text-text-muted hover:bg-surface hover:text-text'
                            }`}
                        >
                            <span>{tabName}</span>
                            {isActive && isDirty && <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />}
                            <button
                                onClick={(e) => handleCloseTab(e, tabPath)}
                                className="p-0.5 rounded hover:bg-border/60 text-text-muted hover:text-text transition-colors"
                            >
                                <X size={11} />
                            </button>
                        </div>
                    );
                })}
            </div>

            {/* Breadcrumb Path & Save Bar */}
            <div className="bg-surface text-text-muted text-xs py-1 px-3 border-b border-border flex justify-between items-center shrink-0">
                <div className="flex items-center gap-1 text-[11px]">
                    {breadcrumbPath.map((part, idx) => (
                        <React.Fragment key={idx}>
                            {idx > 0 && <ChevronRight size={10} className="text-text-muted/40" />}
                            <span className={idx === breadcrumbPath.length - 1 ? 'text-text font-medium' : 'text-text-muted'}>
                                {part}
                            </span>
                        </React.Fragment>
                    ))}

                    {isDirty && <span className="text-amber-400 font-bold ml-1">*</span>}

                    {isLocked && (
                        <span className="flex items-center gap-1 text-amber-400 font-medium ml-2 bg-amber-500/10 border border-amber-500/20 px-1.5 py-0.2 rounded text-[10px]" title="Locked (AI cannot modify)">
                            <Lock size={10} />
                            <span>Locked</span>
                        </span>
                    )}

                    {isStreaming && (
                        <span className="flex items-center gap-1 text-emerald-400 text-[10px] ml-2">
                            <span className="animate-pulse">●</span> 
                            AI writing...
                        </span>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    <button
                        onClick={() => activeFile && toggleFileLock(activeFile, activeSessionId)}
                        className={`p-1 rounded transition-colors ${
                            isLocked ? 'text-amber-400 bg-amber-500/10' : 'text-text-muted hover:text-text'
                        }`}
                        title={isLocked ? "Unlock File" : "Lock File"}
                    >
                        {isLocked ? <Lock size={12} /> : <Unlock size={12} />}
                    </button>

                    <button
                        onClick={handleSave}
                        disabled={isSaving || isStreaming}
                        className={isDirty && !isStreaming ? 'btn-primary h-6 text-[11px] px-2' : 'btn-secondary h-6 text-[11px] px-2'}
                    >
                        <Save size={10} />
                        <span>{isSaving ? 'Saving...' : 'Save'}</span>
                    </button>

                    <span className="text-text-muted font-mono text-[10px] bg-background border border-border px-1.5 py-0.2 rounded uppercase">
                        {lang}
                    </span>
                </div>
            </div>

            {/* Editor Canvas */}
            <div className="flex-1 w-full relative">
                <Editor
                    language={lang}
                    value={content}
                    onChange={handleChange}
                    onMount={handleEditorDidMount}
                    theme="vs"
                    options={{
                        fontSize: 13,
                        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                        minimap: { enabled: true, scale: 0.75 },
                        automaticLayout: true,
                        scrollBeyondLastLine: false,
                        padding: { top: 12 },
                        wordWrap: "on",
                        readOnly: isStreaming,
                        smoothScrolling: true,
                        cursorBlinking: "smooth",
                    }}
                />

                {/* Streaming Progress Badge */}
                {isStreaming && (
                    <div className="absolute bottom-3 right-4 bg-emerald-950/90 text-emerald-300 
                                    text-xs px-3 py-1.5 rounded-full flex items-center gap-2
                                    border border-emerald-700/50 backdrop-blur-md shadow-lg z-20">
                        <Loader2 size={12} className="animate-spin text-emerald-400" />
                        <span>{lineCount} lines</span>
                        <span className="text-emerald-500/40">|</span>
                        <span className="text-emerald-400/80">{content.length} chars</span>
                    </div>
                )}
            </div>
        </div>
    );
};
