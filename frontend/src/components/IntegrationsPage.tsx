import React, { useState } from 'react';
import { Check, ExternalLink, Search, Sparkles } from 'lucide-react';

interface Integration {
  id: string;
  name: string;
  category: string;
  description: string;
  iconUrl: string;
  connected: boolean;
}

export const IntegrationsPage: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [integrations, setIntegrations] = useState<Integration[]>([
    { id: 'github', name: 'GitHub', category: 'Source Control', description: 'Commit and push generated repositories directly to GitHub.', iconUrl: 'https://cdn.simpleicons.org/github', connected: true },
    { id: 'docker', name: 'Docker Engine', category: 'Containerization', description: 'Zero-trust sandbox micro-container execution environment.', iconUrl: 'https://cdn.simpleicons.org/docker/2496ED', connected: true },
    { id: 'openai', name: 'OpenAI GPT-4o', category: 'LLM Provider', description: 'Primary model provider for complex multi-step reasoning.', iconUrl: 'https://cdn.simpleicons.org/openai', connected: true },
    { id: 'anthropic', name: 'Anthropic Claude', category: 'LLM Provider', description: 'High-precision code generation and architectural synthesis.', iconUrl: 'https://cdn.simpleicons.org/anthropic', connected: true },
    { id: 'supabase', name: 'Supabase', category: 'Database & Auth', description: 'Instant PostgreSQL database, authentication, and edge functions.', iconUrl: 'https://cdn.simpleicons.org/supabase/3ECF8E', connected: false },
    { id: 'stripe', name: 'Stripe', category: 'Payments', description: 'Accept payments and manage subscriptions in web applications.', iconUrl: 'https://cdn.simpleicons.org/stripe/008CDD', connected: false },
    { id: 'clerk', name: 'Clerk', category: 'Authentication', description: 'User authentication, social login, and user management UI.', iconUrl: 'https://cdn.simpleicons.org/clerk', connected: false },
    { id: 'google', name: 'Google Cloud / Gemini', category: 'LLM & Cloud', description: 'Gemini Flash models and Google Cloud platform integrations.', iconUrl: 'https://cdn.simpleicons.org/googlecloud', connected: true },
    { id: 'slack', name: 'Slack', category: 'Notifications', description: 'Real-time agent build updates and deployment notifications.', iconUrl: 'https://cdn.simpleicons.org/slack', connected: false },
    { id: 'vercel', name: 'Vercel', category: 'Deployment', description: 'One-click frontend deployment and serverless edge functions.', iconUrl: 'https://cdn.simpleicons.org/vercel', connected: false },
    { id: 'resend', name: 'Resend', category: 'Email', description: 'Transactional email API for web application auth & notifications.', iconUrl: 'https://cdn.simpleicons.org/resend', connected: false },
  ]);

  const toggleConnect = (id: string) => {
    setIntegrations(prev =>
      prev.map(item => (item.id === id ? { ...item, connected: !item.connected } : item))
    );
  };

  const filteredIntegrations = integrations.filter(item =>
    item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    item.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="h-full w-full bg-warm-gradient overflow-y-auto p-6 md:p-10 text-text">
      <div className="max-w-5xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border pb-6">
          <div className="space-y-1">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-brand/10 border border-brand/20 text-brand text-xs font-medium">
              <Sparkles size={12} />
              <span>Ecosystem Integrations</span>
            </div>
            <h1 className="text-2xl font-bold text-text tracking-tight">Ecosystem & Tool Integrations</h1>
            <p className="text-xs text-text-muted">
              Connect external AI model providers, databases, source control, and deployment services to Yantrika AI.
            </p>
          </div>

          <div className="relative w-full md:w-64">
            <Search size={14} className="absolute left-3 top-2.5 text-text-muted" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search integrations..."
              className="w-full pl-9 pr-3 py-1.5 bg-surface border border-border rounded-xl text-xs text-text placeholder:text-text-muted focus:outline-none focus:border-brand"
            />
          </div>
        </div>

        {/* Integration Card Grid (OOUM AI Studio style) */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredIntegrations.map((item) => (
            <div
              key={item.id}
              className="p-5 rounded-2xl border border-border bg-surface hover:border-brand/40 transition-all shadow-sm flex flex-col justify-between h-48"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-3">
                    <img src={item.iconUrl} alt={item.name} className="w-8 h-8 object-contain" />
                    <div>
                      <h3 className="text-sm font-bold text-text">{item.name}</h3>
                      <span className="text-[10px] text-brand font-medium uppercase tracking-wider">{item.category}</span>
                    </div>
                  </div>
                  {item.connected && (
                    <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 text-[10px] font-semibold flex items-center gap-1">
                      <Check size={10} /> Active
                    </span>
                  )}
                </div>
                <p className="text-xs text-text-muted leading-relaxed line-clamp-3">
                  {item.description}
                </p>
              </div>

              <div className="pt-3 border-t border-border/40 flex items-center justify-between">
                <span className="text-[11px] text-text-muted flex items-center gap-1">
                  Docs <ExternalLink size={10} />
                </span>
                <button
                  onClick={() => toggleConnect(item.id)}
                  className={item.connected ? 'btn-secondary h-7 text-xs px-3' : 'btn-primary h-7 text-xs px-3'}
                >
                  {item.connected ? 'Disconnect' : 'Connect'}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
