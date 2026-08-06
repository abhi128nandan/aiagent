import React, { useState } from 'react';
import { TerminalLog } from './Terminal';
import { EventLog } from './EventLog';
import { ErrorAnalysisPanel } from './ErrorAnalysisPanel';
import { Terminal, Activity, AlertTriangle, Bug } from 'lucide-react';

export const WorkspaceDebug: React.FC = () => {
  const [activeDebugTab, setActiveDebugTab] = useState<'terminals' | 'events' | 'errors'>('terminals');

  return (
    <div className="h-full w-full bg-background flex flex-col overflow-hidden text-text">
      {/* Top Debug Bar */}
      <div className="h-11 border-b border-border bg-surface px-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2 text-xs font-semibold text-text">
          <Bug size={16} className="text-brand opacity-90" />
          <span>Debug & Diagnostics Hub</span>
        </div>

        {/* Debug Sub-tabs */}
        <div className="flex items-center bg-background border border-border rounded-lg p-0.5 text-xs">
          <button
            onClick={() => setActiveDebugTab('terminals')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-md transition-all ${
              activeDebugTab === 'terminals'
                ? 'bg-brand text-white font-semibold shadow-xs'
                : 'text-text-muted hover:text-text'
            }`}
          >
            <Terminal size={13} />
            Terminals & Logs
          </button>
          <button
            onClick={() => setActiveDebugTab('events')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-md transition-all ${
              activeDebugTab === 'events'
                ? 'bg-brand text-white font-semibold shadow-xs'
                : 'text-text-muted hover:text-text'
            }`}
          >
            <Activity size={13} />
            Event Stream
          </button>
          <button
            onClick={() => setActiveDebugTab('errors')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-md transition-all ${
              activeDebugTab === 'errors'
                ? 'bg-brand text-white font-semibold shadow-xs'
                : 'text-text-muted hover:text-text'
            }`}
          >
            <AlertTriangle size={13} />
            Error Analysis
          </button>
        </div>
      </div>

      {/* Main Debug Workspace Content */}
      <div className="flex-1 overflow-hidden bg-background">
        {activeDebugTab === 'terminals' ? (
          <TerminalLog />
        ) : activeDebugTab === 'events' ? (
          <EventLog />
        ) : (
          <div className="p-6 max-w-3xl mx-auto">
            <ErrorAnalysisPanel />
          </div>
        )}
      </div>
    </div>
  );
};
