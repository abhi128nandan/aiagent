import { Plus, MessageSquare } from 'lucide-react';
import { useAgentStore } from '../store/agentStore';

export function SessionSidebar() {
    const { sessions, activeSessionId, createNewSession, setActiveSession } = useAgentStore();

    return (
        <aside className="w-48 shrink-0 border-r border-border/40 bg-surface flex flex-col">
            <div className="h-10 px-3 border-b border-border/40 flex items-center justify-between">
                <span className="text-xs font-semibold text-text">Sessions</span>
                <button
                    type="button"
                    onClick={createNewSession}
                    className="p-1 rounded hover:bg-surface-hover text-text-muted hover:text-text transition-colors"
                    title="New session"
                >
                    <Plus size={14} />
                </button>
            </div>
            <div className="flex-1 overflow-y-auto p-1.5 space-y-0.5">
                {sessions.map((session) => (
                    <button
                        key={session.id}
                        type="button"
                        onClick={() => setActiveSession(session.id)}
                        className={`w-full text-left px-2 py-1.5 rounded-md text-xs flex gap-2 items-center transition-colors ${
                            activeSessionId === session.id
                                ? 'bg-brand/15 text-brand font-medium border border-brand/20'
                                : 'text-text-muted hover:text-text hover:bg-surface-hover'
                        }`}
                    >
                        <MessageSquare size={13} className="shrink-0 opacity-70" />
                        <span className="truncate">{session.title}</span>
                    </button>
                ))}
            </div>
        </aside>
    );
}
