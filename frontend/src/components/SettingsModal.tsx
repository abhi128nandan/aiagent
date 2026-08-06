import React, { useEffect, useState } from 'react';
import { api } from '../api/backend';
import type { LLMProfile, LLMProfileCreate } from '../api/backend';
import { Settings, Sliders, Cpu, Trash2, CheckCircle2, Circle, Plus, X, Loader2, Box, Beaker, Info } from 'lucide-react';

interface SettingsModalProps {
    onClose: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ onClose }) => {
    const [activeTab, setActiveTab] = useState<'general' | 'profiles' | 'sandbox' | 'experimental' | 'about'>('general');
    const [profiles, setProfiles] = useState<LLMProfile[]>([]);
    const [generalSettings, setGeneralSettings] = useState<Record<string, any>>({});
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState<string | null>(null);

    // Form state for creating a new profile
    const [showAddForm, setShowAddForm] = useState(false);
    const [newProvider, setNewProvider] = useState('gemini');
    const [newModel, setNewModel] = useState('gemini/gemini-2.5-flash');
    const [newTemp, setNewTemp] = useState(0.2);
    const [newMaxTokens, setNewMaxTokens] = useState<number | ''>('');
    const [newIsDefault, setNewIsDefault] = useState(false);

    const loadData = async () => {
        setLoading(true);
        try {
            const [profilesRes, settingsRes] = await Promise.all([
                api.settings.profiles.list(),
                api.settings.getAll(),
            ]);
            setProfiles(profilesRes.profiles);
            setGeneralSettings(settingsRes.settings);
        } catch (error) {
            console.error('Failed to load settings data:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, []);

    const handleCreateProfile = async (e: React.FormEvent) => {
        e.preventDefault();
        setActionLoading('create');
        try {
            const payload: LLMProfileCreate = {
                provider: newProvider,
                model: newModel,
                temperature: newTemp,
                max_tokens: newMaxTokens === '' ? null : newMaxTokens,
                is_default: newIsDefault,
            };
            await api.settings.profiles.create(payload);
            setShowAddForm(false);
            setNewTemp(0.2);
            setNewMaxTokens('');
            setNewIsDefault(false);
            await loadData();
        } catch (error) {
            console.error('Failed to create profile:', error);
            alert('Failed to create LLM profile. Please check the inputs.');
        } finally {
            setActionLoading(null);
        }
    };

    const handleDeleteProfile = async (id: string) => {
        if (!confirm('Are you sure you want to delete this profile?')) return;
        setActionLoading(`delete-${id}`);
        try {
            await api.settings.profiles.delete(id);
            await loadData();
        } catch (error) {
            console.error('Failed to delete profile:', error);
        } finally {
            setActionLoading(null);
        }
    };

    const handleSetDefaultProfile = async (id: string) => {
        setActionLoading(`default-${id}`);
        try {
            await api.settings.profiles.setDefault(id);
            await loadData();
        } catch (error) {
            console.error('Failed to set default profile:', error);
        } finally {
            setActionLoading(null);
        }
    };

    const handleUpdateSetting = async (key: string, value: any) => {
        setActionLoading(key);
        try {
            await api.settings.update(key, value);
            setGeneralSettings(prev => ({ ...prev, [key]: value }));
        } catch (error) {
            console.error(`Failed to update setting ${key}:`, error);
        } finally {
            setActionLoading(null);
        }
    };

    useEffect(() => {
        if (newProvider === 'gemini') {
            setNewModel('gemini/gemini-2.5-flash');
        } else if (newProvider === 'groq') {
            setNewModel('groq/llama-3.3-70b-versatile');
        } else if (newProvider === 'ollama') {
            setNewModel('ollama/qwen2.5-coder:7b');
        } else if (newProvider === 'openai') {
            setNewModel('openai/gpt-4o-mini');
        }
    }, [newProvider]);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 font-sans">
            <div className="bg-surface w-full max-w-2xl rounded-2xl border border-border shadow-2xl flex flex-col max-h-[85vh] overflow-hidden text-text">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-border bg-surface shrink-0">
                    <div className="flex items-center gap-2 text-text font-bold text-sm">
                        <Settings size={18} className="text-brand" />
                        <h2>Platform Settings</h2>
                    </div>
                    <button 
                        onClick={onClose}
                        className="p-1.5 hover:bg-surface-hover text-text-muted hover:text-text rounded-lg transition-colors"
                    >
                        <X size={18} />
                    </button>
                </div>

                {/* Tabs */}
                <div className="flex border-b border-border bg-background shrink-0 text-xs font-semibold overflow-x-auto">
                    <button
                        onClick={() => setActiveTab('general')}
                        className={`py-3 px-4 flex items-center gap-2 border-b-2 transition-all ${
                            activeTab === 'general'
                                ? 'border-brand text-brand bg-surface'
                                : 'border-transparent text-text-muted hover:text-text'
                        }`}
                    >
                        <Sliders size={14} />
                        General
                    </button>
                    <button
                        onClick={() => setActiveTab('profiles')}
                        className={`py-3 px-4 flex items-center gap-2 border-b-2 transition-all ${
                            activeTab === 'profiles'
                                ? 'border-brand text-brand bg-surface'
                                : 'border-transparent text-text-muted hover:text-text'
                        }`}
                    >
                        <Cpu size={14} />
                        LLM Profiles
                    </button>
                    <button
                        onClick={() => setActiveTab('sandbox')}
                        className={`py-3 px-4 flex items-center gap-2 border-b-2 transition-all ${
                            activeTab === 'sandbox'
                                ? 'border-brand text-brand bg-surface'
                                : 'border-transparent text-text-muted hover:text-text'
                        }`}
                    >
                        <Box size={14} />
                        Sandbox
                    </button>
                    <button
                        onClick={() => setActiveTab('experimental')}
                        className={`py-3 px-4 flex items-center gap-2 border-b-2 transition-all ${
                            activeTab === 'experimental'
                                ? 'border-brand text-brand bg-surface'
                                : 'border-transparent text-text-muted hover:text-text'
                        }`}
                    >
                        <Beaker size={14} />
                        Experimental
                    </button>
                    <button
                        onClick={() => setActiveTab('about')}
                        className={`py-3 px-4 flex items-center gap-2 border-b-2 transition-all ${
                            activeTab === 'about'
                                ? 'border-brand text-brand bg-surface'
                                : 'border-transparent text-text-muted hover:text-text'
                        }`}
                    >
                        <Info size={14} />
                        About
                    </button>
                </div>

                {/* Content */}
                <div className="p-5 overflow-y-auto flex-1 min-h-[300px] text-xs">
                    {loading ? (
                        <div className="flex flex-col items-center justify-center h-48 text-text-muted">
                            <Loader2 size={24} className="animate-spin mb-2 text-brand" />
                            <p className="text-xs">Loading settings...</p>
                        </div>
                    ) : activeTab === 'general' ? (
                        <div className="space-y-4">
                            <h3 className="text-sm font-bold text-text">General Configurations</h3>
                            
                            <div className="space-y-3">
                                <div className="flex flex-col sm:flex-row sm:items-center justify-between p-3.5 border border-border bg-surface rounded-xl gap-2 shadow-xs">
                                    <div className="space-y-0.5">
                                        <h4 className="font-bold text-text">Max LLM Repair Iterations</h4>
                                        <p className="text-text-muted">Maximum repair loops before the agent reports build failure.</p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <input
                                            type="number"
                                            value={generalSettings.max_retries || 5}
                                            onChange={e => handleUpdateSetting('max_retries', parseInt(e.target.value))}
                                            className="w-20 bg-background border border-border rounded-lg px-2.5 py-1 text-xs text-text text-center focus:border-brand outline-none font-bold"
                                        />
                                        {actionLoading === 'max_retries' && <Loader2 size={14} className="animate-spin text-brand" />}
                                    </div>
                                </div>

                                <div className="flex flex-col sm:flex-row sm:items-center justify-between p-3.5 border border-border bg-surface rounded-xl gap-2 shadow-xs">
                                    <div className="space-y-0.5">
                                        <h4 className="font-bold text-text">Debug Log Mode</h4>
                                        <p className="text-text-muted">Enables verbose internal execution tracing in console and log files.</p>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <button
                                            onClick={() => handleUpdateSetting('debug_mode', !generalSettings.debug_mode)}
                                            disabled={actionLoading === 'debug_mode'}
                                            className={`relative inline-flex h-5 w-10 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${
                                                generalSettings.debug_mode ? 'bg-brand' : 'bg-slate-300'
                                            }`}
                                        >
                                            <span
                                                className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                                                    generalSettings.debug_mode ? 'translate-x-5' : 'translate-x-0'
                                                }`}
                                            />
                                        </button>
                                        {actionLoading === 'debug_mode' && <Loader2 size={14} className="animate-spin text-brand" />}
                                    </div>
                                </div>
                            </div>
                        </div>
                    ) : activeTab === 'profiles' ? (
                        <div className="space-y-4">
                            <div className="flex justify-between items-center">
                                <h3 className="text-sm font-bold text-text">Configured LLM Profiles</h3>
                                {!showAddForm && (
                                    <button
                                        onClick={() => setShowAddForm(true)}
                                        className="btn-primary text-xs px-3 py-1.5"
                                    >
                                        <Plus size={14} />
                                        Add Profile
                                    </button>
                                )}
                            </div>

                            {showAddForm && (
                                <form onSubmit={handleCreateProfile} className="p-4 border border-brand bg-brand/5 rounded-xl space-y-3 shadow-xs">
                                    <div className="flex justify-between items-center border-b border-border pb-2">
                                        <span className="font-bold text-brand">Create LLM Profile</span>
                                        <button type="button" onClick={() => setShowAddForm(false)} className="text-text-muted hover:text-text">
                                            <X size={14} />
                                        </button>
                                    </div>
                                    <div className="grid grid-cols-2 gap-3">
                                        <div className="space-y-1">
                                            <label className="text-text-muted block font-medium">Provider</label>
                                            <select
                                                value={newProvider}
                                                onChange={e => setNewProvider(e.target.value)}
                                                className="w-full bg-surface border border-border rounded-lg px-3 py-1.5 text-text focus:border-brand outline-none"
                                            >
                                                <option value="gemini">Gemini</option>
                                                <option value="groq">Groq</option>
                                                <option value="ollama">Ollama (Local)</option>
                                                <option value="openai">OpenAI</option>
                                            </select>
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-text-muted block font-medium">Model Identifier</label>
                                            <input
                                                type="text"
                                                required
                                                value={newModel}
                                                onChange={e => setNewModel(e.target.value)}
                                                placeholder="gemini/gemini-2.5-flash"
                                                className="w-full bg-surface border border-border rounded-lg px-3 py-1.5 text-text focus:border-brand outline-none font-mono"
                                            />
                                        </div>
                                    </div>
                                    <div className="flex items-center justify-between pt-2">
                                        <label className="flex items-center gap-2 text-text-muted cursor-pointer font-medium">
                                            <input
                                                type="checkbox"
                                                checked={newIsDefault}
                                                onChange={e => setNewIsDefault(e.target.checked)}
                                                className="rounded border-border text-brand focus:ring-brand"
                                            />
                                            Set as default profile
                                        </label>
                                        <div className="flex gap-2">
                                            <button
                                                type="button"
                                                onClick={() => setShowAddForm(false)}
                                                className="btn-secondary text-xs px-3 py-1"
                                            >
                                                Cancel
                                            </button>
                                            <button
                                                type="submit"
                                                disabled={actionLoading === 'create'}
                                                className="btn-primary text-xs px-3 py-1"
                                            >
                                                {actionLoading === 'create' && <Loader2 size={12} className="animate-spin" />}
                                                Save Profile
                                            </button>
                                        </div>
                                    </div>
                                </form>
                            )}

                            <div className="space-y-2">
                                {profiles.length === 0 ? (
                                    <p className="text-text-muted text-center py-8">No custom LLM profiles found. Falling back to backend defaults (.env).</p>
                                ) : (
                                    profiles.map(p => (
                                        <div 
                                            key={p.id} 
                                            className={`p-3.5 rounded-xl border flex items-center justify-between transition-all ${
                                                p.is_default 
                                                    ? 'border-brand/50 bg-brand/5' 
                                                    : 'border-border bg-surface hover:bg-surface-hover'
                                            }`}
                                        >
                                            <div className="space-y-1">
                                                <div className="flex items-center gap-2">
                                                    <span className="font-bold text-[10px] text-text uppercase tracking-wider bg-background px-2 py-0.5 rounded border border-border">
                                                        {p.provider}
                                                    </span>
                                                    <span className="font-mono font-bold text-text">
                                                        {p.model}
                                                    </span>
                                                    {p.is_default && (
                                                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-brand/10 text-brand border border-brand/20 font-bold uppercase">
                                                            Default
                                                        </span>
                                                    )}
                                                </div>
                                            </div>

                                            <div className="flex items-center gap-2">
                                                {p.is_default ? (
                                                    <span className="text-brand p-1" title="Active default model">
                                                        <CheckCircle2 size={16} />
                                                    </span>
                                                ) : (
                                                    <button
                                                        onClick={() => handleSetDefaultProfile(p.id)}
                                                        disabled={actionLoading !== null}
                                                        className="p-1 hover:bg-surface-hover text-text-muted hover:text-text rounded transition-colors"
                                                        title="Set as default model"
                                                    >
                                                        <Circle size={16} />
                                                    </button>
                                                )}
                                                <button
                                                    onClick={() => handleDeleteProfile(p.id)}
                                                    disabled={actionLoading !== null}
                                                    className="p-1 hover:bg-rose-50 text-text-muted hover:text-rose-600 rounded transition-colors"
                                                    title="Delete profile"
                                                >
                                                    <Trash2 size={16} />
                                                </button>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    ) : activeTab === 'sandbox' ? (
                        <div className="space-y-4">
                            <h3 className="text-sm font-bold text-text">Docker Sandbox Settings</h3>
                            <div className="p-4 border border-border bg-surface rounded-xl space-y-3 shadow-xs">
                                <div className="flex justify-between items-center">
                                    <div>
                                        <h4 className="font-bold text-text">Sandbox Timeout</h4>
                                        <p className="text-text-muted">Maximum execution time for shell commands inside container (seconds).</p>
                                    </div>
                                    <input
                                        type="number"
                                        value={generalSettings.sandbox_timeout || 30}
                                        onChange={e => handleUpdateSetting('sandbox_timeout', parseInt(e.target.value))}
                                        className="w-20 bg-background border border-border rounded-lg px-2.5 py-1 text-xs text-text text-center focus:border-brand outline-none font-bold"
                                    />
                                </div>
                            </div>
                        </div>
                    ) : activeTab === 'experimental' ? (
                        <div className="space-y-4">
                            <h3 className="text-sm font-bold text-text">Experimental Features</h3>
                            <div className="p-4 border border-border bg-surface rounded-xl space-y-2 text-text-muted shadow-xs">
                                <p className="font-medium text-text">Multi-Modal Vision & Architectural Synthesis</p>
                                <p>Experimental features are enabled by default for LLM code generation and automated testing loops.</p>
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-4 text-center py-6">
                            <div className="p-3 bg-brand/10 text-brand w-fit rounded-2xl mx-auto">
                                <Info size={28} />
                            </div>
                            <h3 className="text-base font-bold text-text">Yantrika AI Platform</h3>
                            <p className="text-text-muted max-w-sm mx-auto leading-relaxed">
                                Version 2.5.0 · Autonomous Multi-Agent AI Engineering Platform with Zero-Trust Docker Sandboxes and Monaco IDE.
                            </p>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-3 border-t border-border bg-background text-xs text-text-muted flex items-center justify-between shrink-0">
                    <span>Manage configurations and LLM model profiles.</span>
                    <button
                        onClick={async () => {
                            if (confirm('Reset all settings to default configuration?')) {
                                setActionLoading('reset');
                                try {
                                    await api.settings.reset();
                                    await loadData();
                                } catch (error) {
                                    console.error(error);
                                } finally {
                                    setActionLoading(null);
                                }
                            }
                        }}
                        className="text-rose-600 hover:text-rose-700 font-bold transition-colors"
                    >
                        Reset Settings
                    </button>
                </div>
            </div>
        </div>
    );
};
