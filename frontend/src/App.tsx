import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { PanelGroup, Panel, PanelResizeHandle } from 'react-resizable-panels';
import { useAgentStore } from './store/agentStore';
import { useAgentStream } from './hooks/useAgentStream';
import { Chat } from './components/Chat';
import { CodeEditor } from './components/MonacoEditor';
import { TerminalLog } from './components/Terminal';
import { FileBrowser } from './components/FileBrowser';
import { SessionSidebar } from './components/SessionSidebar';
import { SandboxPanel } from './components/SandboxPanel';
import { BrowserPreview } from './components/BrowserPreview';
import { TokenUsage } from './components/TokenUsage';
import { SettingsModal } from './components/SettingsModal';
import { ObservabilityDashboard } from './components/ObservabilityDashboard';
import { ArchitectureView } from './components/ArchitectureView';
import { WorkspaceDashboard } from './components/WorkspaceDashboard';
import { WorkspaceDebug } from './components/WorkspaceDebug';
import { YantrikaLandingPage } from './components/YantrikaLandingPage';
import { IntegrationsPage } from './components/IntegrationsPage';
import {
  Code2,
  Settings,
  Sparkles,
  Code,
  Globe,
  Bug,
  LayoutGrid,
  BarChart2,
  FolderTree,
  PanelBottomClose,
  PanelBottomOpen,
  LayoutDashboard,
  Layers,
  PanelLeftClose,
  PanelLeftOpen,
  HelpCircle,
  FolderKanban
} from 'lucide-react';

export type AppView = 'landing' | 'app';
export type WorkspaceMode = 'dashboard' | 'projects' | 'builder' | 'ide' | 'preview' | 'debug' | 'integrations' | 'system';

function App() {
  const { activeSessionId, fetchSessions, fetchArchitecturalPlan, status, connectionState, filesBySession } = useAgentStore();
  const { refreshSandbox } = useAgentStream();
  const [appView, setAppView] = useState<AppView>('landing');
  const [showSettings, setShowSettings] = useState(false);
  const [workspaceMode, setWorkspaceMode] = useState<WorkspaceMode>('dashboard');
  const [systemSubTab, setSystemSubTab] = useState<'architecture' | 'observability'>('architecture');
  const [sidebarExpanded, setSidebarExpanded] = useState(true);

  // IDE view internal panel states
  const [showFileExplorer, setShowFileExplorer] = useState(true);
  const [showTerminal, setShowTerminal] = useState(true);

  const files = filesBySession[activeSessionId] || {};
  const fileCount = Object.keys(files).length;

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  useEffect(() => {
    if (activeSessionId) {
      refreshSandbox(activeSessionId);
      fetchArchitecturalPlan(activeSessionId);
    }
  }, [activeSessionId, refreshSandbox, fetchArchitecturalPlan]);

  // Semantic Status Badge Helper
  const getStatusBadge = () => {
    if (connectionState === 'error' || status === 'error') {
      return { dot: 'bg-rose-500', label: 'Error', bg: 'bg-rose-500/10 border-rose-500/20 text-rose-600' };
    }
    if (status === 'planning') {
      return { dot: 'bg-amber-500 animate-pulse', label: 'Planning', bg: 'bg-amber-500/10 border-amber-500/20 text-amber-600' };
    }
    if (status.startsWith('running') || connectionState === 'open') {
      return { dot: 'bg-emerald-500 animate-ping', label: 'Running', bg: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-600' };
    }
    return { dot: 'bg-slate-400', label: 'Idle', bg: 'bg-slate-100 border-slate-200 text-slate-600' };
  };

  const statusBadge = getStatusBadge();

  // Navigation items
  const navItems: { key: WorkspaceMode; icon: React.ReactNode; label: string }[] = [
    { key: 'dashboard', icon: <LayoutDashboard size={18} />, label: 'Dashboard' },
    { key: 'projects', icon: <FolderKanban size={18} />, label: 'Projects' },
    { key: 'builder', icon: <Sparkles size={18} />, label: 'Builder' },
    { key: 'ide', icon: <Code size={18} />, label: 'Workspace' },
    { key: 'preview', icon: <Globe size={18} />, label: 'Preview' },
    { key: 'debug', icon: <Bug size={18} />, label: 'Debug' },
    { key: 'integrations', icon: <Layers size={18} />, label: 'Integrations' },
  ];

  // ─── Landing Page Experience ───
  if (appView === 'landing') {
    return (
      <div className="h-screen w-screen overflow-y-auto">
        <YantrikaLandingPage
          onStartBuilding={() => {
            window.scrollTo({ top: 0, behavior: 'instant' });
            setAppView('app');
            setWorkspaceMode('builder');
          }}
          onOpenApp={(mode?: string) => {
            window.scrollTo({ top: 0, behavior: 'instant' });
            setAppView('app');
            if (mode) {
              setWorkspaceMode(mode.toLowerCase() as WorkspaceMode);
            } else {
              setWorkspaceMode('dashboard');
            }
          }}
        />
        {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
      </div>
    );
  }

  // ─── Application Workspace Experience ───
  return (
    <div className="h-screen w-screen bg-background flex overflow-hidden font-sans text-text">

      {/* ─── Collapsible Left Sidebar ─── */}
      <aside className={`sidebar-base ${sidebarExpanded ? 'sidebar-expanded' : 'sidebar-collapsed'}`}>
        {/* Sidebar Header: Logo + Toggle */}
        <div className="h-14 px-3 flex items-center justify-between border-b border-border shrink-0">
          {sidebarExpanded ? (
            <div className="flex items-center gap-2 font-extrabold text-sm tracking-tight select-none overflow-hidden whitespace-nowrap">
              <Code2 size={20} className="text-brand shrink-0" />
              <span>Yantrika <span className="text-brand">AI</span></span>
            </div>
          ) : (
            <Code2 size={20} className="text-brand mx-auto" />
          )}
          <button
            onClick={() => setSidebarExpanded(!sidebarExpanded)}
            className="p-1 rounded-lg text-text-muted hover:text-text hover:bg-surface-hover transition-colors shrink-0"
            title={sidebarExpanded ? 'Collapse sidebar' : 'Expand sidebar'}
          >
            {sidebarExpanded ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
          </button>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 overflow-y-auto overflow-x-hidden py-2 px-2 space-y-0.5 scrollbar-hide">
          {navItems.map((item) => (
            <button
              key={item.key}
              onClick={() => setWorkspaceMode(item.key)}
              className={`sidebar-item w-full ${workspaceMode === item.key ? 'sidebar-item-active' : ''}`}
              title={!sidebarExpanded ? item.label : undefined}
            >
              <span className="shrink-0">{item.icon}</span>
              {sidebarExpanded && (
                <span className="truncate text-xs">{item.label}</span>
              )}
            </button>
          ))}
        </nav>

        {/* Sidebar Footer: Settings, Help, Status */}
        <div className="border-t border-border py-2 px-2 space-y-0.5 shrink-0">
          <button
            onClick={() => setShowSettings(true)}
            className="sidebar-item w-full"
            title={!sidebarExpanded ? 'Settings' : undefined}
          >
            <Settings size={18} className="shrink-0" />
            {sidebarExpanded && <span className="truncate text-xs">Settings</span>}
          </button>
          <button
            className="sidebar-item w-full"
            title={!sidebarExpanded ? 'Help & Docs' : undefined}
          >
            <HelpCircle size={18} className="shrink-0" />
            {sidebarExpanded && <span className="truncate text-xs">Help & Docs</span>}
          </button>

          {/* Status Badge */}
          <div className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-xs font-semibold ${statusBadge.bg}`}>
            <span className={`h-2 w-2 rounded-full ${statusBadge.dot} shrink-0`} />
            {sidebarExpanded && <span className="truncate">{statusBadge.label}</span>}
          </div>
        </div>
      </aside>

      {/* ─── Main Content Area ─── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Thin Top Bar (contextual) */}
        <header className="h-11 border-b border-border bg-surface flex items-center px-4 shrink-0 justify-between z-20">
          <div className="flex items-center gap-3">
            {/* Breadcrumb */}
            <span className="text-xs font-semibold text-text">
              {navItems.find(n => n.key === workspaceMode)?.label || 'Dashboard'}
            </span>

            {/* IDE-specific toggles */}
            {workspaceMode === 'ide' && (
              <div className="flex items-center gap-1 border-l border-border pl-3 ml-1">
                <button
                  onClick={() => setShowFileExplorer(!showFileExplorer)}
                  className={`p-1.5 rounded-lg text-xs transition-colors ${
                    showFileExplorer ? 'text-brand bg-brand-muted' : 'text-text-muted hover:text-text'
                  }`}
                  title={showFileExplorer ? 'Hide File Explorer' : 'Show File Explorer'}
                >
                  <FolderTree size={14} />
                </button>
                <button
                  onClick={() => setShowTerminal(!showTerminal)}
                  className={`p-1.5 rounded-lg text-xs transition-colors ${
                    showTerminal ? 'text-brand bg-brand-muted' : 'text-text-muted hover:text-text'
                  }`}
                  title={showTerminal ? 'Hide Terminal' : 'Show Terminal'}
                >
                  {showTerminal ? <PanelBottomClose size={14} /> : <PanelBottomOpen size={14} />}
                </button>
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">
            {/* Progressive CTA */}
            {workspaceMode === 'builder' && fileCount > 0 && (
              <button
                onClick={() => setWorkspaceMode('ide')}
                className="btn-primary h-7 text-xs px-3 shadow-xs"
              >
                Open Workspace →
              </button>
            )}
            <TokenUsage />
            <button
              onClick={() => { setAppView('landing'); }}
              className="text-xs text-text-muted hover:text-brand font-medium transition-colors"
              title="Back to landing page"
            >
              Home
            </button>
          </div>
        </header>

        {/* ─── Workspace Content ─── */}
        <div className="flex-1 flex overflow-hidden relative">
          <AnimatePresence mode="wait">
            {workspaceMode === 'dashboard' && (
              <motion.div
                key="dashboard"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className="w-full h-full absolute inset-0"
              >
                <WorkspaceDashboard
                  onOpenBuilder={() => setWorkspaceMode('builder')}
                  onOpenIDE={() => setWorkspaceMode('ide')}
                />
              </motion.div>
            )}

            {workspaceMode === 'projects' && (
              <motion.div
                key="projects"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className="w-full h-full absolute inset-0 flex overflow-hidden"
              >
                <div className="w-64 border-r border-border bg-surface/50 backdrop-blur-md shrink-0">
                  <SessionSidebar />
                </div>
                <WorkspaceDashboard
                  onOpenBuilder={() => setWorkspaceMode('builder')}
                  onOpenIDE={() => setWorkspaceMode('ide')}
                />
              </motion.div>
            )}

            {workspaceMode === 'builder' && (
              <motion.div
                key="builder"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className="w-full h-full absolute inset-0 flex overflow-hidden bg-background"
              >
                <div className="border-r border-border bg-surface/50 backdrop-blur-md z-10">
                  <SessionSidebar />
                </div>
                <div className="flex-1 flex flex-col h-full max-w-4xl mx-auto border-x border-border/40 bg-surface/80 shadow-2xl w-full backdrop-blur-xl">
                  <Chat />
                </div>
              </motion.div>
            )}

            {workspaceMode === 'ide' && (
              <motion.div
                key="ide"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className="w-full h-full absolute inset-0 flex flex-col bg-background overflow-hidden"
              >
                <SandboxPanel />
                <PanelGroup direction="vertical" className="flex-1">
                  <Panel defaultSize={showTerminal ? 75 : 100} minSize={40}>
                    <PanelGroup direction="horizontal" className="h-full">
                      {showFileExplorer && (
                        <>
                          <Panel defaultSize={18} minSize={12} maxSize={28}>
                            <div className="h-full border-r border-border/40 bg-[#0E0E0E]">
                              <FileBrowser />
                            </div>
                          </Panel>
                          <PanelResizeHandle className="resize-handle-horizontal" />
                        </>
                      )}
                      <Panel defaultSize={showFileExplorer ? 82 : 100} minSize={50}>
                        <div className="h-full bg-[#141414]">
                          <CodeEditor />
                        </div>
                      </Panel>
                    </PanelGroup>
                  </Panel>
                  {showTerminal && (
                    <>
                      <PanelResizeHandle className="resize-handle-vertical" />
                      <Panel defaultSize={25} minSize={12} maxSize={60}>
                        <div className="h-full border-t border-border/40 bg-[#0E0E0E]">
                          <TerminalLog />
                        </div>
                      </Panel>
                    </>
                  )}
                </PanelGroup>
              </motion.div>
            )}

            {workspaceMode === 'preview' && (
              <motion.div
                key="preview"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className="w-full h-full absolute inset-0"
              >
                <BrowserPreview />
              </motion.div>
            )}

            {workspaceMode === 'debug' && (
              <motion.div
                key="debug"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className="w-full h-full absolute inset-0"
              >
                <WorkspaceDebug />
              </motion.div>
            )}

            {workspaceMode === 'integrations' && (
              <motion.div
                key="integrations"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className="w-full h-full absolute inset-0"
              >
                <IntegrationsPage />
              </motion.div>
            )}

            {workspaceMode === 'system' && (
              <motion.div
                key="system"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className="w-full h-full absolute inset-0 flex flex-col bg-surface/30 overflow-hidden"
              >
                <div className="h-10 border-b border-border/40 bg-surface/80 backdrop-blur-md px-4 flex items-center justify-between shrink-0 text-xs z-10">
                  <span className="font-bold text-text">System Administration</span>
                  <div className="flex items-center bg-background border border-border rounded-lg p-0.5">
                    <button
                      onClick={() => setSystemSubTab('architecture')}
                      className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-md transition-all ${
                        systemSubTab === 'architecture' ? 'bg-brand text-white font-semibold shadow-sm' : 'text-text-muted hover:text-text'
                      }`}
                    >
                      <LayoutGrid size={12} />
                      Architecture Map
                    </button>
                    <button
                      onClick={() => setSystemSubTab('observability')}
                      className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-md transition-all ${
                        systemSubTab === 'observability' ? 'bg-brand text-white font-semibold shadow-sm' : 'text-text-muted hover:text-text'
                      }`}
                    >
                      <BarChart2 size={12} />
                      AI Observability
                    </button>
                  </div>
                </div>
                <div className="flex-1 overflow-hidden">
                  {systemSubTab === 'architecture' ? <ArchitectureView /> : <ObservabilityDashboard />}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
    </div>
  );
}

export default App;
