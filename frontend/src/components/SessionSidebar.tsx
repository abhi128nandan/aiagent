import { Plus, MessageSquare } from 'lucide-react';
import { useAgentStore } from '../store/agentStore';

export function SessionSidebar() {
    const { sessions, activeSessionId, createNewSession, setActiveSession } = useAgentStore();

    return (
        <aside className="w-full h-full bg-transparent flex flex-col">
            <div className="h-12 px-4 border-b border-border/40 flex items-center justify-between shrink-0">
                <span className="text-xs font-bold text-text uppercase tracking-wider">Sessions</span>
                <button
                    type="button"
                    onClick={createNewSession}
                    className="p-1.5 rounded-lg hover:bg-brand/10 text-text-muted hover:text-brand transition-all duration-200"
                    title="New session"
                >
                    <Plus size={14} />
                </button>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
                {sessions.map((session) => (
                    <button
                        key={session.id}
                        type="button"
                        onClick={() => setActiveSession(session.id)}
                        className={`w-full text-left px-3 py-2 rounded-xl text-xs flex gap-2.5 items-center transition-all duration-200 group ${
                            activeSessionId === session.id
                                ? 'bg-gradient-to-r from-brand/10 to-transparent text-brand font-semibold shadow-[inset_2px_0_0_#F47A20]'
                                : 'text-text-muted hover:text-text hover:bg-surface-hover/50 hover:pl-4'
                        }`}
                    >
                        <MessageSquare size={14} className={`shrink-0 transition-all duration-300 ${activeSessionId === session.id ? 'opacity-100' : 'opacity-50 group-hover:opacity-80 group-hover:scale-110'}`} />
                        <span className="truncate">{session.title}</span>
                    </button>
                ))}
            </div>
        </aside>
    );
}
