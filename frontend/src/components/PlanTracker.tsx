import React from 'react';
import { useAgentStore } from '../store/agentStore';
import { CheckCircle2, Circle, ListTodo, ChevronDown, ChevronRight } from 'lucide-react';

export const PlanTracker: React.FC = () => {
    const { activeSessionId, planBySession, filesBySession } = useAgentStore();
    const [isExpanded, setIsExpanded] = React.useState(true);

    const plan = planBySession[activeSessionId];
    const generatedFiles = Object.keys(filesBySession[activeSessionId] || {});

    if (!plan || typeof plan !== 'object') {
        return null;
    }

    // Attempt to extract files from the plan JSON.
    // The plan might look like { project: "...", files: ["index.html", "src/main.js"] }
    const plannedFiles: unknown[] | null = Array.isArray(plan.steps)
        ? plan.steps
        : Array.isArray(plan.files)
        ? plan.files
        : Array.isArray(plan.file_list)
        ? plan.file_list
        : null;

    if (!plannedFiles || plannedFiles.length === 0) return null;

    // Normalize paths for comparison (e.g., remove leading './')
    const normalize = (p: string) => typeof p === 'string' ? p.replace(/^\.\//, '').trim() : '';
    
    const normalizedGenerated = generatedFiles.map(normalize);
    
    const progress: { file: string; isCreated: boolean }[] = plannedFiles.map((item: unknown) => {
        const itemObj = typeof item === 'object' && item !== null ? (item as Record<string, unknown>) : null;
        const filePath = typeof item === 'string' 
            ? item 
            : typeof itemObj?.file === 'string' 
            ? itemObj.file 
            : typeof itemObj?.path === 'string' 
            ? itemObj.path 
            : '';
        if (!filePath) return null;
        
        const normFile = normalize(filePath);
        // Check if any generated file ends with this planned file (to handle relative paths)
        const isCreated = normalizedGenerated.some(gf => gf === normFile || gf.endsWith(`/${normFile}`));
        return { file: filePath, isCreated };
    }).filter((p): p is { file: string; isCreated: boolean } => p !== null);

    const completedCount = progress.filter(p => p.isCreated).length;
    const totalCount = plannedFiles.length;
    const percentage = Math.round((completedCount / totalCount) * 100);

    return (
        <div className="bg-surface-hover border border-border rounded-lg m-4 shadow-sm flex flex-col overflow-hidden transition-all">
            <button 
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex items-center gap-2 px-3 py-2 bg-[#1a1b22] hover:bg-[#2a2b32] text-sm font-semibold transition-colors w-full text-left"
            >
                {isExpanded ? <ChevronDown size={16} className="text-text-muted" /> : <ChevronRight size={16} className="text-text-muted" />}
                <ListTodo size={16} className="text-brand" />
                <span>AI Project Plan</span>
                <div className="ml-auto flex items-center gap-2">
                    <span className="text-xs text-text-muted font-normal">{completedCount}/{totalCount} completed</span>
                    <div className="w-24 h-1.5 bg-surface rounded-full overflow-hidden">
                        <div 
                            className="h-full bg-brand transition-all duration-500 ease-out"
                            style={{ width: `${percentage}%` }}
                        />
                    </div>
                </div>
            </button>

            {isExpanded && (
                <div className="p-3 border-t border-border">
                    {plan.project && (
                        <div className="text-xs font-bold text-text-muted mb-2 uppercase tracking-wide">
                            {plan.project}
                        </div>
                    )}
                    <ul className="space-y-1.5">
                        {progress.map(({ file, isCreated }, i) => (
                            <li key={i} className="flex items-center gap-2 text-sm">
                                {isCreated ? (
                                    <CheckCircle2 size={16} className="text-green-500 flex-shrink-0" />
                                ) : (
                                    <Circle size={16} className="text-gray-600 flex-shrink-0" />
                                )}
                                <span className={isCreated ? 'text-gray-300 line-through opacity-70 truncate' : 'text-text truncate'}>
                                    {file}
                                </span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
};
