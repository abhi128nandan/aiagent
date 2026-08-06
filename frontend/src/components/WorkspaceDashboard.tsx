import React from 'react';
import { Plus, MessageSquare, Sparkles, Folder, Play, ArrowRight, Clock, Code } from 'lucide-react';
import { useAgentStore } from '../store/agentStore';

interface WorkspaceDashboardProps {
  onOpenBuilder: () => void;
  onOpenIDE: () => void;
}

export const WorkspaceDashboard: React.FC<WorkspaceDashboardProps> = ({ onOpenBuilder, onOpenIDE }) => {
  const { sessions, activeSessionId, createNewSession, setActiveSession, filesBySession } = useAgentStore();
  const files = filesBySession[activeSessionId] || {};
  const fileCount = Object.keys(files).length;

  const handleStartNewProject = () => {
    createNewSession();
    onOpenBuilder();
  };

  const handleContinueSession = (sessionId: string) => {
    setActiveSession(sessionId);
    if (fileCount > 0) {
      onOpenIDE();
    } else {
      onOpenBuilder();
    }
  };

  return (
    <div className="h-full w-full bg-warm-gradient overflow-y-auto p-6 md:p-10 text-text">
      <div className="max-w-5xl mx-auto space-y-8">
        {/* Welcome Banner */}
        <div className="card-20 p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-xl">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#F47A20]/10 border border-[#F47A20]/20 text-[#F47A20] text-xs font-semibold">
              <Sparkles size={12} />
              <span>Autonomous AI Engineering Platform</span>
            </div>
            <h1 className="text-2xl font-extrabold text-[#1F2937] tracking-tight">Welcome back</h1>
            <p className="text-xs text-[#6B7280] leading-relaxed">
              Start a new AI project, resume an active session, or jump into the code editor.
            </p>
          </div>
          <button
            onClick={handleStartNewProject}
            className="btn-primary px-4 py-2 text-xs font-semibold shrink-0 shadow-md"
          >
            <Plus size={15} />
            <span>New AI Project</span>
          </button>
        </div>

        {/* Quick Action Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div
            onClick={handleStartNewProject}
            className="border border-border bg-surface p-5 rounded-2xl hover:border-brand/50 hover:shadow-md transition-all cursor-pointer group flex flex-col justify-between h-36"
          >
            <div className="flex items-center justify-between">
              <div className="p-2.5 rounded-xl bg-brand/10 text-brand">
                <Sparkles size={18} />
              </div>
              <ArrowRight size={14} className="text-text-muted group-hover:text-brand group-hover:translate-x-1 transition-all" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-text">AI Builder</h3>
              <p className="text-xs text-text-muted mt-0.5">Prompt the AI to generate a full application</p>
            </div>
          </div>

          <div
            onClick={onOpenIDE}
            className="border border-border bg-surface p-5 rounded-2xl hover:border-brand/50 hover:shadow-md transition-all cursor-pointer group flex flex-col justify-between h-36"
          >
            <div className="flex items-center justify-between">
              <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-600">
                <Code size={18} />
              </div>
              <ArrowRight size={14} className="text-text-muted group-hover:text-emerald-600 group-hover:translate-x-1 transition-all" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-text">Code IDE</h3>
              <p className="text-xs text-text-muted mt-0.5">Edit generated code with Monaco Editor</p>
            </div>
          </div>

          <div
            onClick={() => {
              if (sessions.length > 0) handleContinueSession(sessions[0].id);
            }}
            className="border border-border bg-surface p-5 rounded-2xl hover:border-brand/50 hover:shadow-md transition-all cursor-pointer group flex flex-col justify-between h-36"
          >
            <div className="flex items-center justify-between">
              <div className="p-2.5 rounded-xl bg-blue-500/10 text-blue-600">
                <Play size={18} />
              </div>
              <ArrowRight size={14} className="text-text-muted group-hover:text-blue-600 group-hover:translate-x-1 transition-all" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-text">Resume Active Session</h3>
              <p className="text-xs text-text-muted mt-0.5">Continue working on your current workspace</p>
            </div>
          </div>
        </div>

        {/* Recent Sessions List */}
        <div className="space-y-3">
          <div className="flex items-center justify-between border-b border-border pb-2">
            <h2 className="text-xs font-semibold text-text flex items-center gap-2">
              <Clock size={14} className="text-text-muted opacity-70" />
              <span>Recent Sessions & Projects ({sessions.length})</span>
            </h2>
          </div>

          {sessions.length === 0 ? (
            <div className="border border-border bg-surface p-8 rounded-2xl text-center space-y-3 shadow-xs">
              <Folder size={28} className="mx-auto text-text-muted opacity-50" />
              <p className="text-xs font-semibold text-text">No projects yet</p>
              <p className="text-[11px] text-text-muted max-w-xs mx-auto leading-relaxed">
                Create your first AI application to begin building with autonomous agents.
              </p>
              <button
                onClick={handleStartNewProject}
                className="btn-primary text-xs px-3 py-1.5 inline-flex items-center gap-1.5"
              >
                <Plus size={13} />
                <span>Create Project</span>
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {sessions.map((session) => {
                const isActive = session.id === activeSessionId;
                return (
                  <div
                    key={session.id}
                    onClick={() => handleContinueSession(session.id)}
                    className={`p-4 rounded-2xl border transition-all cursor-pointer flex items-center justify-between ${
                      isActive
                        ? 'border-brand/40 bg-brand/10 shadow-xs'
                        : 'border-border bg-surface hover:bg-surface-hover hover:border-border'
                    }`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className={`p-2 rounded-xl ${isActive ? 'bg-brand text-white' : 'bg-surface-hover text-text-muted'}`}>
                        <MessageSquare size={14} />
                      </div>
                      <div className="min-w-0">
                        <h4 className="text-xs font-semibold text-text truncate">{session.title}</h4>
                        <span className="text-[10px] text-text-muted font-mono">Session ID: {session.id.slice(0, 8)}</span>
                      </div>
                    </div>
                    <ArrowRight size={13} className="text-text-muted shrink-0 opacity-60" />
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
