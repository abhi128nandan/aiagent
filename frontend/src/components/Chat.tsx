import React, { useState, useRef, useEffect } from 'react';
import { useAgentStore } from '../store/agentStore';
import { Send, Terminal, Loader2, Square, Play, FileText, PlayCircle, Search, CheckCircle2, ChevronDown, ChevronUp, Sparkles } from 'lucide-react';
import { useAgentStream } from '../hooks/useAgentStream';
import { FileUpload } from './FileUpload';
import { ErrorAnalysisPanel } from './ErrorAnalysisPanel';
import { PlanTracker } from './PlanTracker';

interface ActionCardProps {
    type: 'write' | 'run' | 'search' | 'finish';
    title: string;
    detail?: string;
    content?: string;
}

const ActionCard: React.FC<ActionCardProps> = ({ type, title, detail, content }) => {
    const [isOpen, setIsOpen] = useState(false);
    
    const iconMap = {
        write: <FileText size={13} className="text-cyan-600 opacity-80" />,
        run: <PlayCircle size={13} className="text-emerald-600 opacity-80" />,
        search: <Search size={13} className="text-brand opacity-80" />,
        finish: <CheckCircle2 size={13} className="text-emerald-600 opacity-80" />,
    };

    return (
        <div className="border border-border/80 bg-surface rounded-xl overflow-hidden my-2 shadow-xs w-full max-w-full text-xs">
            <button
                type="button"
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-left hover:bg-surface-hover transition-colors font-medium text-xs"
            >
                {iconMap[type]}
                <span className="flex-1 text-text truncate font-mono text-[11px]">{title}</span>
                {detail && <span className="text-[10px] text-text-muted bg-background px-2 py-0.5 rounded-md border border-border shrink-0">{detail}</span>}
                {content && (
                    isOpen ? <ChevronUp size={12} className="text-text-muted shrink-0" /> : <ChevronDown size={12} className="text-text-muted shrink-0" />
                )}
            </button>
            {isOpen && content && (
                <div className="border-t border-border bg-[#151722] p-3 font-mono text-[11px] leading-relaxed max-h-[240px] overflow-y-auto text-slate-200">
                    <pre className="whitespace-pre-wrap">{content.trim()}</pre>
                </div>
            )}
        </div>
    );
};

const parseMessageContent = (text: string) => {
    const regex = /(<think>[\s\S]*?<\/think>|<write\s+path=['"]([^'"]+)['"]>([\s\S]*?)<\/write>|<run>([\s\S]*?)<\/run>|<search>([\s\S]*?)<\/search>|<finish>([\s\S]*?)<\/finish>)/g;
    
    const parts = [];
    let lastIndex = 0;
    let match;
    
    while ((match = regex.exec(text)) !== null) {
        if (match.index > lastIndex) {
            parts.push({ type: 'text', content: text.substring(lastIndex, match.index) });
        }
        
        const fullMatch = match[0];
        if (fullMatch.startsWith('<think>')) {
            parts.push({ type: 'think', content: fullMatch.replace(/<\/?think>/g, '') });
        } else if (fullMatch.startsWith('<write')) {
            parts.push({
                type: 'write',
                path: match[2],
                content: match[3],
            });
        } else if (fullMatch.startsWith('<run>')) {
            parts.push({
                type: 'run',
                content: match[4],
            });
        } else if (fullMatch.startsWith('<search>')) {
            parts.push({
                type: 'search',
                content: match[5],
            });
        } else if (fullMatch.startsWith('<finish>')) {
            parts.push({
                type: 'finish',
                content: match[6],
            });
        }
        
        lastIndex = regex.lastIndex;
    }
    
    if (lastIndex < text.length) {
        parts.push({ type: 'text', content: text.substring(lastIndex) });
    }
    
    return parts;
};

export const Chat: React.FC = () => {
    const {
        activeSessionId,
        messagesBySession,
        pendingBySession,
        status,
        connectionState,
        error,
        chatModeBySession,
        setChatMode,
    } = useAgentStore();
    const chatMode = chatModeBySession[activeSessionId] || 'build';
    const { send, resume, stop } = useAgentStream();
    const [input, setInput] = useState('');
    const endRef = useRef<HTMLDivElement>(null);
    const messages = messagesBySession[activeSessionId] || [];
    const pending = pendingBySession[activeSessionId] || [];

    const isRunning = connectionState === 'open' && status !== 'idle' && status !== 'error';

    useEffect(() => {
        endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (input.trim()) {
            const srsText = useAgentStore.getState().consumeSrsText(activeSessionId);
            const fullMessage = srsText
                ? `[SRS DOCUMENT]\n${srsText}\n\n[USER INSTRUCTION]\n${input.trim()}`
                : input.trim();
            send(fullMessage);
            setInput('');
        }
    };

    const handlePromptChipClick = (promptText: string) => {
        setInput(promptText);
    };

    const quickStartChips = [
        { label: "React", prompt: "Create a modern React + Vite application with Tailwind CSS." },
        { label: "FastAPI", prompt: "Create a Python FastAPI backend with Pydantic schemas." },
        { label: "Docker", prompt: "List active processes in the Docker sandbox and report environment status." }
    ];

    return (
        <div className="flex flex-col h-full bg-surface">
            {/* Header */}
            <div className="h-12 px-4 border-b border-border bg-surface flex items-center justify-between shrink-0">
                <div className="flex items-center gap-2">
                    <Terminal size={16} className="text-brand" />
                    <span className="font-bold text-text text-xs tracking-tight">AI Builder Console</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                    {pending.length > 0 && <span className="text-amber-600 font-medium text-[10px]">{pending.length} queued</span>}
                    <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-semibold capitalize ${
                        status === 'idle' || connectionState === 'closed' ? 'bg-slate-100 text-slate-600 border border-slate-200' :
                        connectionState === 'open' ? 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/20' :
                        connectionState === 'error' || status === 'error' ? 'bg-rose-500/10 text-rose-600 border border-rose-500/20' :
                        'bg-brand/10 text-brand border border-brand/20 flex items-center gap-1'
                    }`}>
                        {(status.startsWith('running') || status === 'planning' || status === 'connecting') && <Loader2 size={10} className="animate-spin" />}
                        {connectionState === 'open' ? status : connectionState}
                    </span>
                </div>
            </div>
            
            <PlanTracker />

            {/* Message Feed */}
            <div className="flex-1 flex flex-col overflow-y-auto p-4 space-y-4">
                {error && (
                    <div className="text-xs border border-rose-200 bg-rose-50 text-rose-800 rounded-xl p-3 shadow-xs shrink-0">
                        {error}
                    </div>
                )}

                {messages.length === 0 && (
                    <div className="flex-1 flex flex-col items-center justify-center text-text-muted p-6 text-center min-h-[200px]">
                        <div className="h-12 w-12 rounded-2xl bg-brand/10 border border-brand/20 flex items-center justify-center text-brand mb-4 shadow-sm shrink-0">
                            <Sparkles size={22} />
                        </div>
                        <h3 className="text-base font-bold text-text mb-1">AI Builder Ready</h3>
                        <p className="text-xs text-text-muted max-w-sm mb-6 leading-relaxed">
                            Describe the full-stack software application you want to generate, or pick a starter template below.
                        </p>

                        <div className="flex flex-wrap gap-2 justify-center max-w-sm">
                            {quickStartChips.map((chip, idx) => (
                                <button
                                    key={idx}
                                    type="button"
                                    onClick={() => handlePromptChipClick(chip.prompt)}
                                    className="btn-secondary text-xs px-3 py-1.5"
                                >
                                    <span>{chip.label}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {messages.map((msg, i) => (
                    <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[88%] rounded-2xl p-3.5 text-xs sm:text-sm shadow-xs ${
                            msg.role === 'user' 
                                ? 'bg-brand text-white rounded-br-none font-medium' 
                                : msg.role === 'system'
                                ? 'bg-amber-500/10 border border-amber-500/20 text-amber-900 rounded-bl-none w-full'
                                : 'bg-background border border-border text-text rounded-bl-none w-full'
                        }`}>
                            {msg.role === 'system' ? (
                                <div className="space-y-1 w-full whitespace-pre-wrap font-sans text-xs">
                                    {msg.content}
                                </div>
                            ) : msg.role === 'agent' ? (
                                <div className="space-y-1 w-full">
                                    {parseMessageContent(msg.content).map((part, idx) => {
                                        if (part.type === 'think') {
                                            return (
                                                <div key={idx} className="text-text-muted italic text-[11px] my-2 pl-3 border-l-2 border-brand bg-surface p-2 rounded-lg">
                                                    {part.content}
                                                </div>
                                            );
                                        }
                                        if (part.type === 'write') {
                                            return (
                                                <ActionCard
                                                    key={idx}
                                                    type="write"
                                                    title={`Write ${part.path}`}
                                                    detail="File Action"
                                                    content={part.content}
                                                />
                                            );
                                        }
                                        if (part.type === 'run') {
                                            return (
                                                <ActionCard
                                                    key={idx}
                                                    type="run"
                                                    title={`Run: ${part.content.trim()}`}
                                                    detail="Shell Command"
                                                    content={part.content}
                                                />
                                            );
                                        }
                                        if (part.type === 'search') {
                                            return (
                                                <ActionCard
                                                    key={idx}
                                                    type="search"
                                                    title={`Search: ${part.content.trim()}`}
                                                    detail="Web Search"
                                                    content={part.content}
                                                />
                                            );
                                        }
                                        if (part.type === 'finish') {
                                            return (
                                                <ActionCard
                                                    key={idx}
                                                    type="finish"
                                                    title="Task Finished"
                                                    detail="Complete"
                                                    content={part.content}
                                                />
                                            );
                                        }
                                        return <span key={idx} className="whitespace-pre-wrap font-sans">{part.content}</span>;
                                    })}
                                </div>
                            ) : (
                                <span className="whitespace-pre-wrap">{msg.content}</span>
                            )}
                        </div>
                    </div>
                ))}
                <div ref={endRef} />
            </div>

            {/* Input & Form */}
            <form onSubmit={handleSubmit} className="p-3 border-t border-border bg-surface space-y-2 shrink-0">
                <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center bg-background border border-border rounded-xl p-0.5 text-xs">
                        <button
                            type="button"
                            onClick={() => setChatMode('build', activeSessionId)}
                            className={`px-3 py-1 rounded-lg transition-colors font-medium ${
                                chatMode === 'build'
                                    ? 'bg-brand text-white shadow-xs'
                                    : 'text-text-muted hover:text-text'
                            }`}
                        >
                            Build
                        </button>
                        <button
                            type="button"
                            onClick={() => setChatMode('discuss', activeSessionId)}
                            className={`px-3 py-1 rounded-lg transition-colors font-medium ${
                                chatMode === 'discuss'
                                    ? 'bg-brand text-white shadow-xs'
                                    : 'text-text-muted hover:text-text'
                            }`}
                        >
                            Discuss
                        </button>
                    </div>
                    <FileUpload />
                </div>

                <ErrorAnalysisPanel />

                <div className="relative flex items-center">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder={chatMode === 'discuss' ? "Ask a question about the project (Discuss)..." : "Describe what to build or fix..."}
                        className="w-full bg-background border border-border rounded-2xl pl-4 pr-12 py-3 text-xs sm:text-sm focus:outline-none focus:border-brand focus:ring-2 focus:ring-brand/20 text-text transition-all shadow-inner"
                    />
                    {isRunning ? (
                        <button 
                            type="button" 
                            onClick={stop}
                            title="Stop Agent"
                            className="absolute right-2 p-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl transition-colors shadow-xs"
                        >
                            <Square size={14} />
                        </button>
                    ) : (
                        <div className="absolute right-2 flex items-center gap-1">
                            {messages.length > 0 && (
                                <button 
                                    type="button" 
                                    onClick={resume}
                                    title="Resume Agent"
                                    className="p-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-colors flex items-center justify-center shadow-xs"
                                >
                                    <Play size={14} fill="currentColor" />
                                </button>
                            )}
                            <button 
                                type="submit" 
                                disabled={!input.trim() || connectionState === 'connecting'}
                                className="p-2 bg-brand hover:bg-brand-hover text-white rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-xs"
                            >
                                <Send size={14} />
                            </button>
                        </div>
                    )}
                </div>
            </form>
        </div>
    );
};
