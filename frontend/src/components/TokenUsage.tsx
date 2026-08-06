import React from 'react';
import { Brain, Zap } from 'lucide-react';
import { useAgentStore } from '../store/agentStore';

export const TokenUsage: React.FC = () => {
    const { tokenUsageBySession, activeSessionId, status } = useAgentStore();
    const usage = tokenUsageBySession[activeSessionId] || null;

    if (!usage || status === 'idle') return null;

    const percent = Math.min(100, Math.round(usage.usagePercent));
    const isWarning = percent > 70;
    const isCritical = percent > 90;

    const barColor = isCritical
        ? 'bg-rose-500'
        : isWarning
            ? 'bg-amber-500'
            : 'bg-brand';

    const textColor = isCritical
        ? 'text-rose-400'
        : isWarning
            ? 'text-amber-400'
            : 'text-text-muted';

    return (
        <div className="flex items-center gap-2 text-[11px]">
            {/* Context budget bar */}
            <div className="flex items-center gap-1.5" title={`Context: ${usage.messageTokens.toLocaleString()} / ${usage.budgetTokens.toLocaleString()} tokens (${percent}%)`}>
                <Brain size={12} className={textColor} />
                <div className="w-14 h-1.5 rounded-full bg-surface-hover overflow-hidden">
                    <div
                        className={`h-full rounded-full transition-all duration-300 ${barColor}`}
                        style={{ width: `${percent}%` }}
                    />
                </div>
                <span className={textColor}>{percent}%</span>
            </div>

            {/* Active modules indicator */}
            {usage.activeModules && usage.activeModules.length > 0 && (
                <div className="flex items-center gap-1 border-l border-border/40 pl-2">
                    <Zap size={10} className="text-brand opacity-80" />
                    {usage.activeModules.map((mod) => (
                        <span
                            key={mod}
                            className="px-1 py-0.2 rounded bg-surface border border-border/40 text-text-muted text-[9px] font-mono"
                            title={getModuleDescription(mod)}
                        >
                            {mod}
                        </span>
                    ))}
                </div>
            )}
        </div>
    );
};

function getModuleDescription(mod: string): string {
    const descriptions: Record<string, string> = {
        ctx: 'Context Manager — pruning messages to fit model limits',
        err: 'Error Analyzer — classifying errors and suggesting fixes',
        ws: 'Workspace Indexer — analyzing project structure',
        rag: 'RAG Retriever — searching indexed documents',
        mem: 'Memory Manager — tracking long-term context',
    };
    return descriptions[mod] || mod;
}
