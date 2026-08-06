import { useState } from 'react';
import { Globe, RefreshCw, ExternalLink, Monitor, Tablet, Smartphone, Terminal, Server } from 'lucide-react';
import { useAgentStore } from '../store/agentStore';

export function BrowserPreview() {
    const { previewUrlBySession, activeSessionId } = useAgentStore();
    const previewUrl = previewUrlBySession[activeSessionId] || null;
    const [deviceView, setDeviceView] = useState<'desktop' | 'tablet' | 'mobile'>('desktop');
    const [iframeKey, setIframeKey] = useState(0);

    const handleRefresh = () => {
        setIframeKey(prev => prev + 1);
    };

    const getDeviceWidth = () => {
        switch (deviceView) {
            case 'tablet':
                return 'max-w-[768px] border-x border-border/80 my-4 shadow-2xl rounded-lg overflow-hidden';
            case 'mobile':
                return 'max-w-[375px] border-x border-border/80 my-4 shadow-2xl rounded-xl overflow-hidden';
            default:
                return 'w-full h-full';
        }
    };

    return (
        <div className="h-full bg-warm-gradient flex flex-col overflow-hidden">
            {/* Top Toolbar */}
            <div className="h-10 px-3 border-b border-border bg-surface flex items-center justify-between text-xs text-text-muted shrink-0">
                <div className="flex items-center gap-2 min-w-0 flex-1">
                    <Globe size={14} className="opacity-70 text-brand shrink-0" />
                    <span className="truncate text-xs font-mono bg-background border border-border px-2.5 py-0.5 rounded-md text-text max-w-lg shadow-inner">
                        {previewUrl || 'http://localhost:5173'}
                    </span>
                </div>

                {/* Controls */}
                <div className="flex items-center gap-2 shrink-0">
                    {/* Device Viewport Switcher */}
                    <div className="flex items-center bg-background border border-border rounded-md p-0.5">
                        <button
                            onClick={() => setDeviceView('desktop')}
                            className={`p-1 rounded transition-colors ${deviceView === 'desktop' ? 'bg-brand/20 text-brand font-semibold' : 'text-text-muted hover:text-text'}`}
                            title="Desktop View"
                        >
                            <Monitor size={12} />
                        </button>
                        <button
                            onClick={() => setDeviceView('tablet')}
                            className={`p-1 rounded transition-colors ${deviceView === 'tablet' ? 'bg-brand/20 text-brand font-semibold' : 'text-text-muted hover:text-text'}`}
                            title="Tablet View"
                        >
                            <Tablet size={12} />
                        </button>
                        <button
                            onClick={() => setDeviceView('mobile')}
                            className={`p-1 rounded transition-colors ${deviceView === 'mobile' ? 'bg-brand/20 text-brand font-semibold' : 'text-text-muted hover:text-text'}`}
                            title="Mobile View"
                        >
                            <Smartphone size={12} />
                        </button>
                    </div>

                    <button
                        onClick={handleRefresh}
                        className="p-1.5 rounded-md hover:bg-surface-hover text-text-muted hover:text-text transition-colors border border-border"
                        title="Reload Preview"
                    >
                        <RefreshCw size={13} />
                    </button>

                    {previewUrl && (
                        <a
                            href={previewUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1.5 rounded-md hover:bg-surface-hover text-text-muted hover:text-text transition-colors border border-border flex items-center gap-1"
                            title="Open in new browser tab"
                        >
                            <ExternalLink size={13} />
                        </a>
                    )}
                </div>
            </div>

            {/* Preview Frame */}
            <div className="flex-1 bg-background flex items-center justify-center overflow-hidden relative p-4">
                {previewUrl ? (
                    <div className="transition-all duration-300 h-full w-full flex justify-center">
                        <iframe
                            key={iframeKey}
                            title="Sandbox preview"
                            src={previewUrl}
                            className={`h-full bg-white border border-border shadow-xs ${getDeviceWidth()}`}
                        />
                    </div>
                ) : (
                    <div className="max-w-md w-full border border-border bg-surface rounded-2xl p-8 shadow-xs text-center space-y-4">
                        <div className="p-3 rounded-2xl bg-brand/10 text-brand w-fit mx-auto">
                            <Server size={24} />
                        </div>
                        <div className="space-y-1.5">
                            <h4 className="font-bold text-text text-base">Application Not Running</h4>
                            <p className="text-xs text-text-muted leading-relaxed">
                                Development server is currently idle on port <span className="font-mono text-brand font-semibold">5173</span>. Prompt the AI agent to start the app server.
                            </p>
                        </div>

                        <div className="pt-4 border-t border-border flex items-center justify-center gap-4 text-xs font-mono text-text-muted">
                            <span className="flex items-center gap-1.5"><Globe size={13} className="text-brand" /> http://localhost:5173</span>
                            <span className="flex items-center gap-1.5"><Terminal size={13} className="text-emerald-600" /> Port 5173</span>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
