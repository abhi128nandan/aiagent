import { Activity } from 'lucide-react';
import { useAgentStore } from '../store/agentStore';

export function EventLog() {
    const { activeSessionId, eventsBySession } = useAgentStore();
    const events = eventsBySession[activeSessionId] || [];

    return (
        <div className="h-full bg-surface border-l border-border/40 flex flex-col text-xs">
            <div className="h-10 px-3 border-b border-border/40 flex items-center gap-2 font-medium text-text shrink-0">
                <Activity size={14} className="opacity-70" />
                <span>Events</span>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1.5 text-xs">
                {events.length === 0 ? (
                    <div className="text-text-muted p-2 text-xs">No events logged.</div>
                ) : events.slice(-80).map((event) => (
                    <div key={event.id} className="border border-border/40 rounded-md p-2 bg-[#0d0e14]">
                        <div className="flex justify-between gap-2 text-[11px]">
                            <span className="text-brand font-mono">{event.type}</span>
                            <span className="text-text-muted truncate font-mono">{event.node || 'graph'}</span>
                        </div>
                        {event.chunk && <div className="text-text-muted text-[11px] truncate mt-1 font-mono">{event.chunk}</div>}
                    </div>
                ))}
            </div>
        </div>
    );
}
