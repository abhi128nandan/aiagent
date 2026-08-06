import React, { useEffect, useState, useMemo } from 'react';
import {
    Search,
    Filter,
    Clock,
    Layers,
    CheckCircle2,
    Download,
    RefreshCw,
    Code2,
    FileText,
    Terminal,
    ChevronDown,
    ChevronUp,
    AlertCircle,
    Database,
    Zap,
    PlayCircle,
    Binary
} from 'lucide-react';
import { useAgentStore } from '../store/agentStore';
import { api, getBackendBaseUrl } from '../api/backend';

export const ObservabilityDashboard: React.FC = () => {
    const { activeSessionId, observabilityLogsBySession, setObservabilityLogs } = useAgentStore();
    const liveLogs = observabilityLogsBySession[activeSessionId] || [];

    // Local State
    const [searchQuery, setSearchQuery] = useState('');
    const [filterAgent, setFilterAgent] = useState('All');
    const [filterType, setFilterType] = useState('All');
    const [filterStatus, setFilterStatus] = useState('All');
    const [expandedLogId, setExpandedLogId] = useState<number | null>(null);
    const [summary, setSummary] = useState<any | null>(null);
    const [loading, setLoading] = useState(false);

    // Fetch historical logs & summary metrics
    const fetchLogsAndSummary = async () => {
        if (!activeSessionId) return;
        setLoading(true);
        try {
            const [logsRes, summaryRes] = await Promise.all([
                api.observability.getLogs(activeSessionId),
                api.observability.getSummary(activeSessionId)
            ]);
            setObservabilityLogs(logsRes, activeSessionId);
            setSummary(summaryRes);
        } catch (error) {
            console.error('Failed to load observability logs/summary:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchLogsAndSummary();
    }, [activeSessionId]);

    // Format timestamps nicely
    const formatTime = (tsStr: string) => {
        try {
            const date = new Date(tsStr);
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        } catch {
            return tsStr;
        }
    };

    // Filter logs based on search query and dropdown selections
    const filteredLogs = useMemo(() => {
        return liveLogs.filter((log) => {
            const matchesSearch = searchQuery
                ? log.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                  log.agent_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                  log.event_type?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                  JSON.stringify(log.metadata || {}).toLowerCase().includes(searchQuery.toLowerCase())
                : true;

            const matchesAgent = filterAgent === 'All' ? true : log.agent_name === filterAgent;
            const matchesType = filterType === 'All' ? true : log.event_type === filterType;
            const matchesStatus = filterStatus === 'All' ? true : log.status === filterStatus;

            return matchesSearch && matchesAgent && matchesType && matchesStatus;
        });
    }, [liveLogs, searchQuery, filterAgent, filterType, filterStatus]);

    // Export handler helpers
    const getExportUrl = (format: 'json' | 'csv' | 'pdf') => {
        return `${getBackendBaseUrl()}/api/agent/session/${activeSessionId}/observability/export/${format}`;
    };

    // Style configuration mapping for Agent types
    const getAgentBadgeStyle = (agent: string) => {
        switch (agent) {
            case 'Planner Agent':
                return 'bg-indigo-950/60 text-indigo-300 border-indigo-800/40';
            case 'Environment Agent':
                return 'bg-cyan-950/60 text-cyan-300 border-cyan-800/40';
            case 'Coder Agent':
                return 'bg-purple-950/60 text-purple-300 border-purple-800/40';
            case 'Judge Agent':
                return 'bg-amber-950/60 text-amber-300 border-amber-800/40';
            case 'Validator Agent':
                return 'bg-emerald-950/60 text-emerald-300 border-emerald-800/40';
            default:
                return 'bg-slate-900/60 text-slate-300 border-slate-700/40';
        }
    };

    // Icon helper for event types
    const getEventIcon = (type: string) => {
        switch (type) {
            case 'prompt_log':
                return <Code2 className="w-4 h-4 text-violet-400" />;
            case 'file_create':
            case 'file_modify':
            case 'file_read':
                return <FileText className="w-4 h-4 text-sky-400" />;
            case 'terminal':
            case 'build':
                return <Terminal className="w-4 h-4 text-amber-400" />;
            case 'testing':
                return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
            case 'dependency':
                return <Database className="w-4 h-4 text-teal-400" />;
            case 'error':
                return <AlertCircle className="w-4 h-4 text-rose-400" />;
            case 'activity':
                return <Zap className="w-4 h-4 text-yellow-400" />;
            default:
                return <PlayCircle className="w-4 h-4 text-slate-400" />;
        }
    };

    // Render visual unified diff
    const renderDiff = (diffStr: string) => {
        if (!diffStr) return <div className="text-slate-500 text-xs font-mono">No modifications made.</div>;
        const lines = diffStr.split('\n');
        return (
            <div className="font-mono text-[11px] leading-relaxed bg-[#0a0f1d] border border-slate-800 rounded p-3 overflow-x-auto max-h-[300px]">
                {lines.map((line, idx) => {
                    let className = 'text-slate-300';
                    if (line.startsWith('+') && !line.startsWith('+++')) {
                        className = 'bg-emerald-950/40 text-emerald-400 px-1 py-[1px] block';
                    } else if (line.startsWith('-') && !line.startsWith('---')) {
                        className = 'bg-rose-950/40 text-rose-400 px-1 py-[1px] block';
                    } else if (line.startsWith('@@')) {
                        className = 'text-cyan-500 font-semibold';
                    }
                    return (
                        <span key={idx} className={className}>
                            {line}
                        </span>
                    );
                })}
            </div>
        );
    };

    return (
        <div className="h-full w-full bg-background text-text flex flex-col overflow-hidden">
            {/* Header */}
            <div className="border-b border-border bg-surface px-6 py-4 flex items-center justify-between shrink-0">
                <div>
                    <h2 className="text-base font-semibold text-text flex items-center gap-2">
                        <Binary className="w-5 h-5 text-brand" />
                        AI Agent Observability Panel
                    </h2>
                    <p className="text-xs text-text-muted mt-0.5">
                        Real-time audit log of all steps executed by your AI builder agent.
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={fetchLogsAndSummary}
                        disabled={loading}
                        className="btn-secondary h-8 text-xs"
                    >
                        <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </button>
                    <div className="relative group">
                        <button className="btn-primary h-8 text-xs">
                            <Download className="w-3.5 h-3.5" />
                            Export Data
                        </button>
                        <div className="absolute right-0 mt-1 w-44 rounded-xl border border-border bg-surface shadow-xl hidden group-hover:block z-55 py-1">
                            <a
                                href={getExportUrl('json')}
                                download
                                className="flex items-center gap-2 px-3 py-2 text-xs text-text-muted hover:bg-surface-hover hover:text-text transition"
                            >
                                <FileText className="w-3.5 h-3.5 text-blue-500" />
                                Export JSON Log
                            </a>
                            <a
                                href={getExportUrl('csv')}
                                download
                                className="flex items-center gap-2 px-3 py-2 text-xs text-text-muted hover:bg-surface-hover hover:text-text transition"
                            >
                                <Database className="w-3.5 h-3.5 text-teal-500" />
                                Export CSV Log
                            </a>
                            <a
                                href={getExportUrl('pdf')}
                                download
                                className="flex items-center gap-2 px-3 py-2 text-xs text-text-muted hover:bg-surface-hover hover:text-text transition"
                            >
                                <AlertCircle className="w-3.5 h-3.5 text-rose-500" />
                                Download PDF Report
                            </a>
                        </div>
                    </div>
                </div>
            </div>

            {/* Dashboard Summary Section */}
            {summary && (
                <div className="grid grid-cols-4 gap-4 px-6 py-4 border-b border-border bg-surface shrink-0">
                    <div className="bg-background border border-border rounded-xl p-3.5 flex items-center gap-3">
                        <div className="p-2.5 rounded-lg bg-indigo-500/10 text-indigo-600">
                            <Clock className="w-5 h-5" />
                        </div>
                        <div>
                            <div className="text-[10px] text-text-muted uppercase tracking-wider">Session Duration</div>
                            <div className="text-lg font-bold text-text mt-0.5">
                                {summary.duration_seconds ? `${Math.round(summary.duration_seconds)}s` : '0s'}
                            </div>
                        </div>
                    </div>
                    <div className="bg-background border border-border rounded-xl p-3.5 flex items-center gap-3">
                        <div className="p-2.5 rounded-lg bg-emerald-500/10 text-emerald-600">
                            <CheckCircle2 className="w-5 h-5" />
                        </div>
                        <div>
                            <div className="text-[10px] text-text-muted uppercase tracking-wider">Total Steps</div>
                            <div className="text-lg font-bold text-text mt-0.5">
                                {summary.total_steps || 0}
                            </div>
                        </div>
                    </div>
                    <div className="bg-background border border-border rounded-xl p-3.5 flex items-center gap-3">
                        <div className="p-2.5 rounded-lg bg-blue-500/10 text-blue-600">
                            <Layers className="w-5 h-5" />
                        </div>
                        <div>
                            <div className="text-[10px] text-text-muted uppercase tracking-wider">Tokens Used</div>
                            <div className="text-lg font-bold text-text mt-0.5">
                                {summary.total_tokens ? summary.total_tokens.toLocaleString() : '0'}
                            </div>
                        </div>
                    </div>
                    <div className="bg-background border border-border rounded-xl p-3.5 flex items-center gap-3">
                        <div className="p-2.5 rounded-lg bg-rose-500/10 text-rose-600">
                            <AlertCircle className="w-5 h-5" />
                        </div>
                        <div>
                            <div className="text-[10px] text-text-muted uppercase tracking-wider">Errors</div>
                            <div className="text-lg font-bold text-text mt-0.5">
                                {summary.errors_count || 0}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Filters Toolbar */}
            <div className="px-6 py-3 border-b border-slate-800/80 bg-[#121319] flex flex-wrap items-center gap-3 shrink-0">
                {/* Search */}
                <div className="relative min-w-[200px] flex-1">
                    <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-500" />
                    <input
                        type="text"
                        placeholder="Search logs, metadata, code diffs..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full bg-[#1b1c24] border border-slate-800 rounded-lg pl-9 pr-4 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand transition"
                    />
                </div>

                {/* Filters */}
                <div className="flex items-center gap-2">
                    <Filter className="w-3.5 h-3.5 text-slate-500" />
                    <span className="text-xs text-slate-400">Filters:</span>
                </div>

                {/* Agent Filter */}
                <select
                    value={filterAgent}
                    onChange={(e) => setFilterAgent(e.target.value)}
                    className="bg-[#1b1c24] border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-brand"
                >
                    <option value="All">All Agents</option>
                    <option value="Planner Agent">Planner Agent</option>
                    <option value="Environment Agent">Environment Agent</option>
                    <option value="Coder Agent">Coder Agent</option>
                    <option value="Judge Agent">Judge Agent</option>
                    <option value="Validator Agent">Validator Agent</option>
                </select>

                {/* Event Type Filter */}
                <select
                    value={filterType}
                    onChange={(e) => setFilterType(e.target.value)}
                    className="bg-[#1b1c24] border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-brand"
                >
                    <option value="All">All Event Types</option>
                    <option value="activity">Agent Activity</option>
                    <option value="prompt_log">Prompt Logs</option>
                    <option value="file_read">File Reads</option>
                    <option value="file_create">File Creations</option>
                    <option value="file_modify">File Modifications</option>
                    <option value="terminal">Terminal Commands</option>
                    <option value="build">Build Outputs</option>
                    <option value="testing">Test Runs</option>
                    <option value="dependency">Dependencies</option>
                    <option value="error">Execution Errors</option>
                    <option value="session_summary">Session Summary</option>
                </select>

                {/* Status Filter */}
                <select
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value)}
                    className="bg-[#1b1c24] border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-brand"
                >
                    <option value="All">All Statuses</option>
                    <option value="success">Success</option>
                    <option value="failed">Failed</option>
                    <option value="running">Running</option>
                </select>
            </div>

            {/* Timeline Log Content */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
                {filteredLogs.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-slate-500 py-10">
                        <Clock className="w-8 h-8 text-slate-600 mb-2" />
                        <span className="text-xs">No observability logs match your criteria.</span>
                    </div>
                ) : (
                    filteredLogs.map((log) => {
                        const isExpanded = expandedLogId === log.id;
                        const hasDetails = ['prompt_log', 'file_modify', 'file_create', 'terminal', 'build', 'testing', 'error', 'session_summary'].includes(log.event_type);

                        return (
                            <div
                                key={log.id}
                                className={`border rounded-xl transition-all duration-200 overflow-hidden ${
                                    isExpanded
                                        ? 'border-brand bg-[#14161f]'
                                        : 'border-slate-800 bg-[#101116] hover:bg-[#15171f]/80 hover:border-slate-700'
                                }`}
                            >
                                {/* Collapsible Header Row */}
                                <div
                                    onClick={() => hasDetails && setExpandedLogId(isExpanded ? null : log.id)}
                                    className={`px-4 py-3 flex items-center justify-between gap-4 select-none ${
                                        hasDetails ? 'cursor-pointer' : ''
                                    }`}
                                >
                                    <div className="flex items-center gap-3 min-w-0">
                                        {/* Status Dot */}
                                        <div className="flex-shrink-0">
                                            {log.status === 'success' ? (
                                                <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" title="Success" />
                                            ) : log.status === 'failed' ? (
                                                <div className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse" title="Failed" />
                                            ) : (
                                                <div className="w-2.5 h-2.5 rounded-full bg-blue-500 animate-ping" title="Running" />
                                            )}
                                        </div>

                                        {/* Timestamp */}
                                        <div className="text-[10px] text-slate-500 font-mono flex-shrink-0">
                                            {formatTime(log.timestamp)}
                                        </div>

                                        {/* Agent Badge */}
                                        <span className={`px-2 py-0.5 rounded border text-[10px] font-semibold whitespace-nowrap ${getAgentBadgeStyle(log.agent_name)}`}>
                                            {log.agent_name}
                                        </span>

                                        {/* Description */}
                                        <div className="text-xs font-medium text-slate-200 truncate max-w-[450px]">
                                            {log.description}
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-3 flex-shrink-0">
                                        {/* Duration */}
                                        {log.duration !== null && log.duration !== undefined && (
                                            <span className="text-[10px] text-slate-500 font-mono bg-slate-900 border border-slate-800 px-1.5 py-0.5 rounded">
                                                {log.duration}s
                                            </span>
                                        )}

                                        {/* Type icon */}
                                        <div className="p-1 rounded bg-[#1c1d26] border border-slate-800/80" title={log.event_type}>
                                            {getEventIcon(log.event_type)}
                                        </div>

                                        {/* Expander Icon */}
                                        {hasDetails && (
                                            <div>
                                                {isExpanded ? (
                                                    <ChevronUp className="w-4 h-4 text-slate-400" />
                                                ) : (
                                                    <ChevronDown className="w-4 h-4 text-slate-400" />
                                                )}
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* Expanded Details Drawer */}
                                {isExpanded && (
                                    <div className="px-4 pb-4 pt-2 border-t border-slate-800/80 bg-[#0c0d12]">
                                        {/* Prompt/Response detail */}
                                        {log.event_type === 'prompt_log' && (
                                            <div className="space-y-3">
                                                <div>
                                                    <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1 flex items-center gap-1.5">
                                                        <Code2 className="w-3 h-3 text-violet-400" />
                                                        Sent Prompt (Input)
                                                    </div>
                                                    <pre className="font-mono text-[11px] bg-[#07080c] border border-slate-800/80 rounded p-3 text-slate-400 whitespace-pre-wrap max-h-[160px] overflow-y-auto leading-normal">
                                                        {log.metadata?.prompt}
                                                    </pre>
                                                </div>
                                                <div>
                                                    <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1 flex items-center gap-1.5">
                                                        <Zap className="w-3 h-3 text-emerald-400" />
                                                        Model Response (Output)
                                                    </div>
                                                    <pre className="font-mono text-[11px] bg-[#07080c] border border-slate-800/80 rounded p-3 text-slate-300 whitespace-pre-wrap max-h-[220px] overflow-y-auto leading-normal">
                                                        {log.metadata?.response}
                                                    </pre>
                                                </div>
                                            </div>
                                        )}

                                        {/* File modification detail */}
                                        {log.event_type === 'file_modify' && (
                                            <div>
                                                <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1.5">
                                                    Git Code Diff Modifications: {log.metadata?.file_path}
                                                </div>
                                                {renderDiff(log.metadata?.diff)}
                                            </div>
                                        )}

                                        {/* File creation detail */}
                                        {log.event_type === 'file_create' && (
                                            <div>
                                                <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1.5">
                                                    New File Created: {log.metadata?.file_path}
                                                </div>
                                                <pre className="font-mono text-[11px] bg-[#07080c] border border-slate-800 rounded p-3 text-slate-300 max-h-[200px] overflow-y-auto">
                                                    {log.metadata?.content_preview}
                                                </pre>
                                            </div>
                                        )}

                                        {/* Command, terminal or build logs */}
                                        {(log.event_type === 'terminal' || log.event_type === 'build' || log.event_type === 'testing') && (
                                            <div className="space-y-2">
                                                <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider flex items-center gap-1.5">
                                                    <Terminal className="w-3 h-3 text-amber-400" />
                                                    Executed Command Line
                                                </div>
                                                <div className="font-mono text-xs text-brand bg-slate-900 border border-slate-800 px-3 py-2 rounded">
                                                    $ {log.metadata?.command || log.metadata?.full_command}
                                                </div>
                                                {log.metadata?.output && (
                                                    <div>
                                                        <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1">
                                                            Console STDOUT / STDERR Output
                                                        </div>
                                                        <pre className="font-mono text-[11px] bg-[#07080c] border border-slate-800 rounded p-3 text-slate-400 max-h-[220px] overflow-y-auto whitespace-pre-wrap leading-normal">
                                                            {log.metadata?.output}
                                                        </pre>
                                                    </div>
                                                )}
                                            </div>
                                        )}

                                        {/* Execution errors */}
                                        {log.event_type === 'error' && (
                                            <div className="space-y-2">
                                                <div className="text-[10px] text-rose-400 font-bold uppercase tracking-wider flex items-center gap-1.5">
                                                    <AlertCircle className="w-3 h-3 text-rose-400" />
                                                    Error Trace details: {log.metadata?.error_type}
                                                </div>
                                                <div className="text-xs font-semibold text-rose-300">
                                                    {log.metadata?.error_message}
                                                </div>
                                                {log.metadata?.stack_trace && (
                                                    <pre className="font-mono text-[11px] bg-rose-950/20 border border-rose-900/40 rounded p-3 text-rose-400/90 whitespace-pre-wrap">
                                                        {log.metadata?.stack_trace}
                                                    </pre>
                                                )}
                                            </div>
                                        )}

                                        {/* Session Summary Final Detail Card */}
                                        {log.event_type === 'session_summary' && (
                                            <div className="space-y-3">
                                                <div className="text-[10px] text-emerald-400 font-bold uppercase tracking-wider flex items-center gap-1.5">
                                                    <CheckCircle2 className="w-3.5 h-3.5" />
                                                    Aggregated Session Execution Summary
                                                </div>
                                                <div className="grid grid-cols-2 gap-4">
                                                    <div className="p-3 bg-slate-900/50 rounded border border-slate-800">
                                                        <div className="text-[10px] text-slate-400">Total System Time</div>
                                                        <div className="text-sm font-semibold text-slate-200 mt-0.5">
                                                            {log.metadata?.duration_seconds ? `${Math.round(log.metadata.duration_seconds)} seconds` : 'N/A'}
                                                        </div>
                                                    </div>
                                                    <div className="p-3 bg-slate-900/50 rounded border border-slate-800">
                                                        <div className="text-[10px] text-slate-400">Model Tokens (Cost)</div>
                                                        <div className="text-sm font-semibold text-slate-200 mt-0.5">
                                                            {log.metadata?.total_tokens?.toLocaleString() || 0} (${log.metadata?.estimated_cost_usd?.toFixed(4) || '0.0000'})
                                                        </div>
                                                    </div>
                                                    <div className="p-3 bg-slate-900/50 rounded border border-slate-800">
                                                        <div className="text-[10px] text-slate-400">Successful Steps / Failed Steps</div>
                                                        <div className="text-sm font-semibold text-slate-200 mt-0.5">
                                                            {log.metadata?.successful_steps || 0} succeeded, {log.metadata?.failed_steps || 0} failed
                                                        </div>
                                                    </div>
                                                    <div className="p-3 bg-slate-900/50 rounded border border-slate-800">
                                                        <div className="text-[10px] text-slate-400">Code Coverage / Files Written</div>
                                                        <div className="text-sm font-semibold text-slate-200 mt-0.5">
                                                            {log.metadata?.code_coverage || 100}% coverage ({log.metadata?.files_written || 0} files created/modified)
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
};
