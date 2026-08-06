import React, { useEffect, useRef, useState } from 'react';
import { useAgentStore } from '../store/agentStore';
import mermaid from 'mermaid';
import { 
    LayoutGrid, 
    FileText, 
    Layers, 
    Network, 
    GitCommit, 
    GitBranch, 
    Server, 
    Activity,
    AlertCircle, 
    CheckCircle,
    HelpCircle,
    Calendar,
    ChevronRight,
    RefreshCw
} from 'lucide-react';

// Initialize mermaid for dark-mode layout
mermaid.initialize({
    startOnLoad: false,
    theme: 'dark',
    securityLevel: 'loose',
    themeVariables: {
        background: '#181920',
        primaryColor: '#4f46e5',
        primaryTextColor: '#f8fafc',
        lineColor: '#64748b',
        secondaryColor: '#312e81',
        tertiaryColor: '#1e1b4b',
    }
});

interface MermaidRendererProps {
    chart: string;
}

export const MermaidRenderer: React.FC<MermaidRendererProps> = ({ chart }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [svg, setSvg] = useState<string>('');
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!chart) return;
        
        setError(null);
        setSvg('');
        
        // Remove any markdown code block wrappers if present
        let cleanChart = chart.replace(/```mermaid/gi, '').replace(/```/g, '').trim();
        
        // Sanitize node labels in square brackets to prevent parsing errors from unescaped quotes.
        // F[Frontend "React App"] -> F["Frontend 'React App'"]
        cleanChart = cleanChart.replace(/\[([^\]]+)\]/g, (_match, inner) => {
            let text = inner.trim();
            if (text.startsWith('"') && text.endsWith('"')) {
                let core = text.substring(1, text.length - 1);
                core = core.replace(/"/g, "'");
                return `["${core}"]`;
            } else if (text.startsWith("'") && text.endsWith("'")) {
                let core = text.substring(1, text.length - 1);
                core = core.replace(/"/g, "'");
                return `["${core}"]`;
            } else {
                let core = text.replace(/"/g, "'");
                return `["${core}"]`;
            }
        });
        const id = `mermaid-${Math.floor(Math.random() * 100000)}`;
        
        const renderDiagram = async () => {
            try {
                const { svg: renderedSvg } = await mermaid.render(id, cleanChart);
                setSvg(renderedSvg);
            } catch (err: any) {
                console.error("Mermaid rendering failed:", err);
                setError(err?.message || "Failed to render Mermaid diagram. Please verify syntax.");
            }
        };

        renderDiagram();
    }, [chart]);

    if (error) {
        return (
            <div className="p-4 rounded-xl bg-red-950/20 border border-red-500/30 text-red-400 text-xs font-mono whitespace-pre-wrap max-h-[400px] overflow-auto">
                <div className="flex items-center gap-2 font-semibold mb-2 text-sm">
                    <AlertCircle size={16} />
                    <span>Mermaid Rendering Error</span>
                </div>
                <p className="mb-3 text-red-300">{error}</p>
                <div className="p-3 bg-black/40 rounded border border-slate-800 text-[10px] text-slate-400 overflow-x-auto">
                    {chart}
                </div>
            </div>
        );
    }

    return (
        <div className="flex justify-center items-center overflow-auto p-6 bg-[#13141c]/50 border border-slate-800/80 rounded-2xl min-h-[450px] transition-all hover:border-slate-700/80">
            {svg ? (
                <div 
                    ref={containerRef} 
                    className="mermaid-svg-container max-w-full scale-105 transform origin-center"
                    dangerouslySetInnerHTML={{ __html: svg }} 
                />
            ) : (
                <div className="flex items-center gap-3 text-slate-400 text-sm">
                    <RefreshCw className="animate-spin text-brand" size={18} />
                    <span>Rendering system blueprint...</span>
                </div>
            )}
        </div>
    );
};

export const ArchitectureView: React.FC = () => {
    const { activeSessionId, architecturalPlanBySession, fetchArchitecturalPlan } = useAgentStore();
    const [subTab, setSubTab] = useState<'diagrams' | 'adrs'>('diagrams');
    const [activeDiagram, setActiveDiagram] = useState<string>('system');
    const [activeAdrId, setActiveAdrId] = useState<string | null>(null);
    const [loading, setLoading] = useState<boolean>(false);

    const plan = activeSessionId ? architecturalPlanBySession[activeSessionId] : null;

    useEffect(() => {
        if (activeSessionId) {
            setLoading(true);
            fetchArchitecturalPlan(activeSessionId).finally(() => setLoading(false));
        }
    }, [activeSessionId, fetchArchitecturalPlan]);

    const handleRefresh = () => {
        if (activeSessionId) {
            setLoading(true);
            fetchArchitecturalPlan(activeSessionId).finally(() => setLoading(false));
        }
    };

    if (loading && !plan) {
        return (
            <div className="flex-1 flex flex-col items-center justify-center bg-[#13141c] text-slate-300 p-8">
                <RefreshCw className="animate-spin text-brand mb-4" size={36} />
                <h3 className="font-semibold text-lg">Loading Architecture Spec</h3>
                <p className="text-sm text-slate-500 mt-1">Retrieving Mermaid files and ADR models...</p>
            </div>
        );
    }

    if (!plan) {
        return (
            <div className="flex-1 flex flex-col items-center justify-center bg-[#13141c] text-slate-300 p-8 text-center">
                <div className="w-16 h-16 rounded-full bg-[#1b1c26] border border-slate-800 flex items-center justify-center mb-4 text-brand">
                    <LayoutGrid size={28} />
                </div>
                <h3 className="font-semibold text-lg">No Architecture Specs Found</h3>
                <p className="text-sm text-slate-500 max-w-md mt-2">
                    Submit an SRS document or prompt the agent to build your application first. The Architecture Node will automatically generate detailed diagrams and ADRs.
                </p>
                <button
                    onClick={handleRefresh}
                    className="mt-6 flex items-center gap-2 px-4 py-2 rounded-xl bg-brand text-white font-medium text-sm hover:bg-brand-hover transition-all"
                >
                    <RefreshCw size={16} />
                    Check Status
                </button>
            </div>
        );
    }

    const artifacts = plan.architectural_artifacts || {};
    const decisions = plan.architecture_decisions || [];

    // Get current diagram body
    let currentDiagramContent = '';
    if (activeDiagram === 'system') currentDiagramContent = artifacts.system_diagram;
    else if (activeDiagram === 'component') currentDiagramContent = artifacts.component_diagram;
    else if (activeDiagram === 'flow') currentDiagramContent = artifacts.data_flow_diagram;
    else if (activeDiagram === 'deployment') currentDiagramContent = artifacts.deployment_diagram;
    else if (activeDiagram.startsWith('sequence-')) {
        const idx = parseInt(activeDiagram.split('-')[1]);
        currentDiagramContent = artifacts.sequence_diagrams?.[idx] || '';
    }

    // Default to first ADR if none is active
    const selectedAdr = decisions.find((d: any) => d.id === activeAdrId) || decisions[0];

    return (
        <div className="flex-1 flex flex-col bg-[#13141c] text-slate-100 overflow-hidden h-full">
            {/* Metadata Summary Banner */}
            <div className="border-b border-slate-800/80 bg-[#171822] p-4 shrink-0 flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-brand/10 border border-brand/20 flex items-center justify-center text-brand">
                        <Layers size={20} />
                    </div>
                    <div>
                        <div className="flex items-center gap-2">
                            <h2 className="font-bold text-sm text-white">System Architecture Specifications</h2>
                            {plan.architecture_approved ? (
                                <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-medium border border-emerald-500/20">
                                    <CheckCircle size={10} />
                                    Approved
                                </span>
                            ) : (
                                <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 font-medium border border-indigo-500/20">
                                    <Activity size={10} />
                                    In Review
                                </span>
                            )}
                        </div>
                        <p className="text-xs text-slate-400 mt-0.5">
                            {plan.tech_stack_summary || 'Analyzing Technology Stack...'}
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-6 text-xs text-slate-400">
                    <div className="flex flex-col items-end">
                        <span className="text-[10px] text-slate-500">EST. COMPLEXITY</span>
                        <span className={`font-semibold mt-0.5 px-2 py-0.5 rounded text-[10px] ${
                            plan.estimated_complexity === 'Low' ? 'bg-emerald-500/10 text-emerald-400' :
                            plan.estimated_complexity === 'Medium' ? 'bg-amber-500/10 text-amber-400' :
                            plan.estimated_complexity === 'High' ? 'bg-orange-500/10 text-orange-400' :
                            'bg-red-500/10 text-red-400'
                        }`}>
                            {plan.estimated_complexity || 'Medium'}
                        </span>
                    </div>
                    <div className="w-px h-6 bg-slate-800" />
                    <div className="flex flex-col items-end">
                        <span className="text-[10px] text-slate-500">REVISIONS</span>
                        <span className="font-semibold text-slate-200 mt-0.5">
                            Rev #{plan.architecture_revision || 1}
                        </span>
                    </div>
                    <div className="w-px h-6 bg-slate-800" />
                    <button
                        onClick={handleRefresh}
                        disabled={loading}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-800 hover:border-slate-700 bg-slate-900/60 text-slate-300 hover:text-white transition-all disabled:opacity-50"
                    >
                        <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
                        Reload
                    </button>
                </div>
            </div>

            {/* Sub-navigation */}
            <div className="h-10 border-b border-slate-800/80 bg-[#151620] px-4 flex items-center justify-between shrink-0">
                <div className="flex gap-4">
                    <button
                        onClick={() => setSubTab('diagrams')}
                        className={`flex items-center gap-2 text-xs font-semibold h-10 border-b-2 transition-all px-1 ${
                            subTab === 'diagrams'
                                ? 'border-brand text-brand'
                                : 'border-transparent text-slate-400 hover:text-slate-200'
                        }`}
                    >
                        <Network size={14} />
                        Architectural Diagrams
                    </button>
                    <button
                        onClick={() => setSubTab('adrs')}
                        className={`flex items-center gap-2 text-xs font-semibold h-10 border-b-2 transition-all px-1 ${
                            subTab === 'adrs'
                                ? 'border-brand text-brand'
                                : 'border-transparent text-slate-400 hover:text-slate-200'
                        }`}
                    >
                        <FileText size={14} />
                        Architecture Decision Records (ADRs)
                    </button>
                </div>

                <div className="text-[10px] text-slate-500 flex items-center gap-1.5">
                    <Calendar size={12} />
                    <span>Spec Generated: {new Date(plan.architecture_generated_at).toLocaleString()}</span>
                </div>
            </div>

            {/* Main view content */}
            <div className="flex-1 flex overflow-hidden">
                {subTab === 'diagrams' ? (
                    <div className="flex-1 flex overflow-hidden">
                        {/* Diagrams Sidebar */}
                        <div className="w-64 border-r border-slate-800/80 bg-[#161721] p-3 flex flex-col gap-1 shrink-0 overflow-y-auto">
                            <div className="text-[10px] font-bold text-slate-500 px-2 uppercase tracking-wider mb-2">
                                System Blueprints
                            </div>
                            
                            <button
                                onClick={() => setActiveDiagram('system')}
                                className={`flex items-center justify-between w-full text-left p-2 rounded-xl text-xs transition-all ${
                                    activeDiagram === 'system'
                                        ? 'bg-brand/10 border border-brand/20 text-brand font-medium'
                                        : 'hover:bg-slate-900 border border-transparent text-slate-400 hover:text-slate-200'
                                }`}
                            >
                                <div className="flex items-center gap-2">
                                    <Layers size={13} />
                                    <span>High-Level Container</span>
                                </div>
                                <ChevronRight size={12} className="opacity-60" />
                            </button>

                            <button
                                onClick={() => setActiveDiagram('component')}
                                className={`flex items-center justify-between w-full text-left p-2 rounded-xl text-xs transition-all ${
                                    activeDiagram === 'component'
                                        ? 'bg-brand/10 border border-brand/20 text-brand font-medium'
                                        : 'hover:bg-slate-900 border border-transparent text-slate-400 hover:text-slate-200'
                                }`}
                            >
                                <div className="flex items-center gap-2">
                                    <Network size={13} />
                                    <span>Component Interactions</span>
                                </div>
                                <ChevronRight size={12} className="opacity-60" />
                            </button>

                            <button
                                onClick={() => setActiveDiagram('flow')}
                                className={`flex items-center justify-between w-full text-left p-2 rounded-xl text-xs transition-all ${
                                    activeDiagram === 'flow'
                                        ? 'bg-brand/10 border border-brand/20 text-brand font-medium'
                                        : 'hover:bg-slate-900 border border-transparent text-slate-400 hover:text-slate-200'
                                }`}
                            >
                                <div className="flex items-center gap-2">
                                    <GitBranch size={13} />
                                    <span>Data Flow Layout</span>
                                </div>
                                <ChevronRight size={12} className="opacity-60" />
                            </button>

                            <button
                                onClick={() => setActiveDiagram('deployment')}
                                className={`flex items-center justify-between w-full text-left p-2 rounded-xl text-xs transition-all ${
                                    activeDiagram === 'deployment'
                                        ? 'bg-brand/10 border border-brand/20 text-brand font-medium'
                                        : 'hover:bg-slate-900 border border-transparent text-slate-400 hover:text-slate-200'
                                }`}
                            >
                                <div className="flex items-center gap-2">
                                    <Server size={13} />
                                    <span>Deployment Structure</span>
                                </div>
                                <ChevronRight size={12} className="opacity-60" />
                            </button>

                            {artifacts.sequence_diagrams?.length > 0 && (
                                <>
                                    <div className="text-[10px] font-bold text-slate-500 px-2 uppercase tracking-wider mt-4 mb-2">
                                        Sequence flows
                                    </div>
                                    {artifacts.sequence_diagrams.map((_: string, index: number) => (
                                        <button
                                            key={index}
                                            onClick={() => setActiveDiagram(`sequence-${index}`)}
                                            className={`flex items-center justify-between w-full text-left p-2 rounded-xl text-xs transition-all ${
                                                activeDiagram === `sequence-${index}`
                                                    ? 'bg-brand/10 border border-brand/20 text-brand font-medium'
                                                    : 'hover:bg-slate-900 border border-transparent text-slate-400 hover:text-slate-200'
                                            }`}
                                        >
                                            <div className="flex items-center gap-2">
                                                <GitCommit size={13} />
                                                <span>Interaction Sequence #{index + 1}</span>
                                            </div>
                                            <ChevronRight size={12} className="opacity-60" />
                                        </button>
                                    ))}
                                </>
                            )}
                        </div>

                        {/* Rendering Canvas */}
                        <div className="flex-1 p-6 overflow-y-auto flex flex-col justify-between">
                            <div className="flex-1 flex flex-col">
                                <h3 className="text-sm font-semibold mb-3 text-white flex items-center gap-2">
                                    {activeDiagram === 'system' && 'High-Level Container Diagram'}
                                    {activeDiagram === 'component' && 'Component Interaction Blueprint'}
                                    {activeDiagram === 'flow' && 'System Data Flow Layout'}
                                    {activeDiagram === 'deployment' && 'Deployment Structure Blueprint'}
                                    {activeDiagram.startsWith('sequence-') && `Interaction Sequence #${parseInt(activeDiagram.split('-')[1]) + 1}`}
                                </h3>
                                
                                <MermaidRenderer chart={currentDiagramContent} />
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="flex-1 flex overflow-hidden">
                        {/* ADR list sidebar */}
                        <div className="w-80 border-r border-slate-800/80 bg-[#161721] p-3 flex flex-col gap-2 shrink-0 overflow-y-auto">
                            <div className="text-[10px] font-bold text-slate-500 px-2 uppercase tracking-wider mb-2">
                                Decision Changelog
                            </div>

                            {decisions.length === 0 ? (
                                <div className="text-xs text-slate-500 p-4 text-center">
                                    No decision records generated yet.
                                </div>
                            ) : (
                                decisions.map((adr: any) => (
                                    <button
                                        key={adr.id}
                                        onClick={() => setActiveAdrId(adr.id)}
                                        className={`w-full text-left p-3 rounded-xl border transition-all flex flex-col gap-2 ${
                                            (selectedAdr?.id === adr.id)
                                                ? 'bg-brand/10 border-brand/30 text-white'
                                                : 'hover:bg-slate-900/60 border-slate-800/60 text-slate-400 hover:text-slate-200'
                                        }`}
                                    >
                                        <div className="flex items-center justify-between w-full">
                                            <span className="font-mono text-[10px] font-semibold text-brand bg-brand/10 px-1.5 py-0.5 rounded">
                                                {adr.id}
                                            </span>
                                            <span className={`text-[9px] px-1.5 py-0.5 rounded font-medium ${
                                                adr.status === 'Accepted' ? 'bg-emerald-500/10 text-emerald-400' :
                                                adr.status === 'Proposed' ? 'bg-amber-500/10 text-amber-400' :
                                                'bg-slate-500/10 text-slate-400'
                                            }`}>
                                                {adr.status}
                                            </span>
                                        </div>
                                        <h4 className="font-semibold text-xs leading-snug text-slate-200">
                                            {adr.title}
                                        </h4>
                                        <p className="text-[10px] text-slate-500 line-clamp-2">
                                            {adr.decision}
                                        </p>
                                    </button>
                                ))
                            )}
                        </div>

                        {/* ADR Content Detail Viewer */}
                        <div className="flex-1 p-6 overflow-y-auto bg-[#13141c]/30">
                            {selectedAdr ? (
                                <div className="max-w-3xl flex flex-col gap-6">
                                    <div className="border-b border-slate-800/80 pb-4">
                                        <div className="flex items-center gap-3 mb-2">
                                            <span className="font-mono text-xs font-semibold text-brand bg-brand/10 px-2 py-0.5 rounded border border-brand/20">
                                                {selectedAdr.id}
                                            </span>
                                            <span className={`text-xs px-2 py-0.5 rounded font-medium border ${
                                                selectedAdr.status === 'Accepted' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25' :
                                                selectedAdr.status === 'Proposed' ? 'bg-amber-500/10 text-amber-400 border-amber-500/25' :
                                                'bg-slate-500/10 text-slate-400 border-slate-800'
                                            }`}>
                                                {selectedAdr.status} Decision Record
                                            </span>
                                        </div>
                                        <h2 className="text-xl font-bold text-white leading-tight">
                                            {selectedAdr.title}
                                        </h2>
                                        <p className="text-[10px] text-slate-500 mt-2 flex items-center gap-1">
                                            <span>Created: {new Date(selectedAdr.created_at).toLocaleString()}</span>
                                            {selectedAdr.updated_at && (
                                                <span>• Updated: {new Date(selectedAdr.updated_at).toLocaleString()}</span>
                                            )}
                                        </p>
                                    </div>

                                    {/* Context Section */}
                                    <div className="flex flex-col gap-1.5">
                                        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                                            <HelpCircle size={12} className="text-slate-500" />
                                            Context & Problem Statement
                                        </h3>
                                        <p className="text-xs text-slate-300 leading-relaxed bg-[#171822]/40 border border-slate-800/60 p-4 rounded-xl">
                                            {selectedAdr.context}
                                        </p>
                                    </div>

                                    {/* Decision Section */}
                                    <div className="flex flex-col gap-1.5">
                                        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                                            <CheckCircle size={12} className="text-emerald-500" />
                                            Decision Outcome
                                        </h3>
                                        <p className="text-xs text-slate-200 font-medium leading-relaxed bg-emerald-950/5 border border-emerald-500/15 p-4 rounded-xl">
                                            {selectedAdr.decision}
                                        </p>
                                    </div>

                                    {/* Consequences Section */}
                                    <div className="flex flex-col gap-1.5">
                                        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                                            <AlertCircle size={12} className="text-amber-500" />
                                            Implications & Consequences
                                        </h3>
                                        <p className="text-xs text-slate-300 leading-relaxed bg-amber-950/5 border border-amber-500/15 p-4 rounded-xl">
                                            {selectedAdr.consequences}
                                        </p>
                                    </div>

                                    {/* Alternatives Section */}
                                    {selectedAdr.alternatives?.length > 0 && (
                                        <div className="flex flex-col gap-1.5">
                                            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                                                <Layers size={12} className="text-indigo-500" />
                                                Alternatives Considered
                                            </h3>
                                            <ul className="flex flex-col gap-2 bg-[#171822]/40 border border-slate-800/60 p-4 rounded-xl">
                                                {selectedAdr.alternatives.map((alt: string, index: number) => (
                                                    <li key={index} className="text-xs text-slate-300 flex items-start gap-2">
                                                        <span className="w-1.5 h-1.5 rounded-full bg-brand mt-1.5 shrink-0" />
                                                        <span>{alt}</span>
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div className="flex items-center justify-center h-full text-slate-500 text-xs">
                                    Select a Decision Record to view detailed context.
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
