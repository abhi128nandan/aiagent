'use client'

import React, { useState, useRef, useEffect } from 'react'
import {
  Plus, Lightbulb, Paperclip, Image, FileCode,
  ChevronDown, Check, Sparkles, Zap, Brain,
  SendHorizontal
} from 'lucide-react'

// ─── Types ───────────────────────────────────────────────────────────────────
interface Model {
  id: string
  name: string
  description: string
  icon: React.ReactNode
  badge?: string
}

// ─── Models ───────────────────────────────────────────────────────────────────
const models: Model[] = [
  { id: 'gemini-pro', name: 'Gemini Pro', description: 'Fast & intelligent', icon: <Sparkles className="size-4 text-brand" />, badge: 'Default' },
  { id: 'gpt-4o', name: 'GPT-4o', description: 'OpenAI flagship', icon: <Zap className="size-4 text-green-500" /> },
  { id: 'claude-3.7', name: 'Claude 3.7', description: 'Most capable', icon: <Brain className="size-4 text-purple-500" />, badge: 'Pro' },
  { id: 'llama-3', name: 'Llama 3', description: 'Open source', icon: <Brain className="size-4 text-orange-500" /> },
]

// ─── Model Selector ───────────────────────────────────────────────────────────
function ModelSelector({ selectedModel = 'gemini-pro', onModelChange }: {
  selectedModel?: string
  onModelChange?: (model: Model) => void
}) {
  const [isOpen, setIsOpen] = useState(false)
  const [selected, setSelected] = useState(models.find(m => m.id === selectedModel) || models[0])

  const handleSelect = (model: Model) => {
    setSelected(model)
    setIsOpen(false)
    onModelChange?.(model)
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200 text-text-muted hover:text-text hover:bg-surface-hover active:scale-95 border border-border/60"
      >
        {selected.icon}
        <span>{selected.name}</span>
        <ChevronDown className={`size-3.5 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
          <div className="absolute bottom-full left-0 mb-2 z-50 min-w-[220px] bg-surface border border-border rounded-xl shadow-xl overflow-hidden">
            <div className="p-1.5">
              <div className="px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                Select Model
              </div>
              {models.map((model) => (
                <button
                  key={model.id}
                  onClick={() => handleSelect(model)}
                  className={`w-full flex items-center gap-3 px-2.5 py-2 rounded-lg text-left transition-all duration-150 ${
                    selected.id === model.id
                      ? 'bg-brand-muted text-brand'
                      : 'text-text-muted hover:bg-surface-hover hover:text-text'
                  }`}
                >
                  <div className="flex-shrink-0">{model.icon}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-text">{model.name}</span>
                      {model.badge && (
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                          model.badge === 'Pro' ? 'bg-purple-100 text-purple-600' : 'bg-brand-muted text-brand'
                        }`}>
                          {model.badge}
                        </span>
                      )}
                    </div>
                    <span className="text-[11px] text-text-muted">{model.description}</span>
                  </div>
                  {selected.id === model.id && <Check className="size-4 text-brand flex-shrink-0" />}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// ─── Chat Input ───────────────────────────────────────────────────────────────
export function BoltChatInput({ onSend, placeholder = "Describe the agent you want to build...", onModelChange }: {
  onSend?: (message: string) => void
  placeholder?: string
  onModelChange?: (model: Model) => void
}) {
  const [message, setMessage] = useState('')
  const [showAttachMenu, setShowAttachMenu] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`
    }
  }, [message])

  const handleSubmit = () => {
    if (message.trim()) {
      onSend?.(message)
      setMessage('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="relative w-full max-w-[700px] mx-auto">
      {/* Glow ring on focus */}
      <div className="absolute -inset-[1px] rounded-2xl bg-gradient-to-b from-brand/10 to-transparent pointer-events-none" />
      <div className="relative rounded-2xl bg-surface border border-border shadow-[0_4px_24px_rgba(0,0,0,0.06)] hover:shadow-[0_4px_32px_rgba(244,122,32,0.08)] transition-shadow duration-300">
        {/* Textarea */}
        <div className="relative">
          <textarea
            ref={textareaRef}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className="w-full resize-none bg-transparent text-[15px] text-text placeholder-text-muted/50 px-5 pt-5 pb-3 focus:outline-none min-h-[80px] max-h-[200px]"
            style={{ height: '80px' }}
          />
        </div>

        {/* Footer bar */}
        <div className="flex items-center justify-between px-3 pb-3 pt-1">
          <div className="flex items-center gap-1">
            {/* Attach menu */}
            <div className="relative">
              <button
                onClick={() => setShowAttachMenu(!showAttachMenu)}
                className="flex items-center justify-center size-8 rounded-full bg-surface-hover hover:bg-border text-text-muted hover:text-text transition-all duration-200 active:scale-95"
              >
                <Plus className={`size-4 transition-transform duration-200 ${showAttachMenu ? 'rotate-45' : ''}`} />
              </button>

              {showAttachMenu && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowAttachMenu(false)} />
                  <div className="absolute bottom-full left-0 mb-2 z-50 bg-surface border border-border rounded-xl shadow-xl overflow-hidden">
                    <div className="p-1.5 min-w-[180px]">
                      {[
                        { icon: <Paperclip className="size-4" />, label: 'Upload file' },
                        { icon: <Image className="size-4" />, label: 'Add image' },
                        { icon: <FileCode className="size-4" />, label: 'Import code' },
                      ].map((item, i) => (
                        <button key={i} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-text-muted hover:bg-surface-hover hover:text-text transition-all duration-150">
                          {item.icon}
                          <span className="text-sm">{item.label}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </div>

            <ModelSelector onModelChange={onModelChange} />
          </div>

          <div className="flex items-center gap-2 ml-auto">
            <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium text-text-muted hover:text-text hover:bg-surface-hover transition-all duration-200">
              <Lightbulb className="size-4" />
              <span className="hidden sm:inline">Plan</span>
            </button>

            <button
              onClick={handleSubmit}
              disabled={!message.trim()}
              className="flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold bg-brand hover:bg-brand-hover text-white transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed active:scale-95 shadow-[0_0_20px_rgba(244,122,32,0.25)]"
            >
              <span className="hidden sm:inline">Generate</span>
              <SendHorizontal className="size-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Ray Background (light theme) ─────────────────────────────────────────────
function HeroBackground() {
  return (
    <div className="absolute inset-0 w-full h-full overflow-hidden pointer-events-none select-none">
      {/* Subtle radial glow */}
      <div
        className="absolute left-1/2 top-0 -translate-x-1/2 w-[900px] h-[500px] opacity-40"
        style={{
          background: `radial-gradient(ellipse at 50% 0%, rgba(244,122,32,0.12) 0%, rgba(244,122,32,0.04) 40%, transparent 70%)`
        }}
      />
      {/* Subtle grid */}
      <div
        className="absolute inset-0 opacity-[0.025]"
        style={{
          backgroundImage: `linear-gradient(#09090B 1px, transparent 1px), linear-gradient(90deg, #09090B 1px, transparent 1px)`,
          backgroundSize: '64px 64px',
        }}
      />
    </div>
  )
}

// ─── Main BoltStyleChat Component ─────────────────────────────────────────────
interface BoltChatProps {
  subtitle?: string
  placeholder?: string
  onSend?: (message: string) => void
}

export function BoltStyleChat({
  subtitle = "Describe what you want. Yantrika AI turns it into a production-ready agent — in minutes.",
  placeholder = "Build a customer support agent integrated with our SAP database...",
  onSend,
}: BoltChatProps) {
  return (
    <div className="relative flex flex-col items-center justify-center w-full overflow-hidden bg-background pt-28 pb-24 lg:pt-40 lg:pb-32">
      <HeroBackground />

      <div className="relative z-10 flex flex-col items-center justify-center w-full px-6 gap-8">
        {/* Headline */}
        <div className="text-center max-w-4xl">
          <h1 className="text-5xl sm:text-6xl md:text-7xl font-bold text-text tracking-tight leading-[1.08] animate-fade-slide-in">
            Build{' '}
            <span className="inline-block pr-2 py-1 -my-1 bg-gradient-to-br from-brand via-brand to-brand/60 bg-clip-text text-transparent italic">
              Intelligent
            </span>{' '}
            Agents.
            <br />
            <span className="text-text-muted">Without the friction.</span>
          </h1>
          <p className="mt-5 text-lg md:text-xl text-text-muted max-w-2xl mx-auto animate-fade-slide-in delay-100">
            {subtitle}
          </p>
        </div>

        {/* Chat Input */}
        <div className="w-full max-w-[720px] animate-fade-slide-in delay-200">
          <BoltChatInput placeholder={placeholder} onSend={onSend} />
        </div>

      </div>
    </div>
  )
}

export default BoltStyleChat
