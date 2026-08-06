"use client";

import React, { useState } from 'react';
import { 
    Code, Database, Server, Layout, Smartphone, Globe, 
    Cloud, Terminal, Cpu, Layers, Workflow, Sparkles, ArrowRight
} from 'lucide-react';

interface Technology {
    name: string;
    icon: React.ReactNode;
}

const defaultTechnologies: Technology[] = [
    { name: "React", icon: <Code size={20} /> },
    { name: "Node.js", icon: <Server size={20} /> },
    { name: "Python", icon: <Terminal size={20} /> },
    { name: "SAP", icon: <Layers size={20} /> },
    { name: "WordPress", icon: <Globe size={20} /> },
    { name: "AWS", icon: <Cloud size={20} /> },
    { name: "Docker", icon: <Workflow size={20} /> },
    { name: "PostgreSQL", icon: <Database size={20} /> },
    { name: "iOS/Android", icon: <Smartphone size={20} /> },
    { name: "UI/UX", icon: <Layout size={20} /> },
    { name: "AI/ML", icon: <Cpu size={20} /> }
];

interface ResponsiveHeroBannerProps {
    onPrimaryClick?: () => void;
    technologies?: Technology[];
}

const ResponsiveHeroBanner: React.FC<ResponsiveHeroBannerProps> = ({
    onPrimaryClick,
    technologies = defaultTechnologies
}) => {
    const [prompt, setPrompt] = useState("");

    return (
        <section className="w-full relative overflow-hidden bg-background pt-32 pb-24 lg:pt-48 lg:pb-32">
            {/* Background Glow */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-hero-gradient blur-3xl opacity-60 pointer-events-none" />

            <div className="relative z-10 max-w-7xl mx-auto px-6">
                <div className="flex flex-col items-center text-center">
                    
                    {/* Headline */}
                    <h1 className="text-5xl md:text-7xl font-sans font-bold tracking-tight text-text max-w-4xl animate-fade-slide-in delay-100">
                        Build Intelligent Agents.
                        <br />
                        <span className="text-text-muted">Without the friction.</span>
                    </h1>

                    <p className="mt-6 text-lg md:text-xl text-text-muted max-w-2xl animate-fade-slide-in delay-200">
                        Design, deploy, and scale production-ready AI agents in minutes. Integrated with your favorite tools and tech stacks.
                    </p>

                    {/* Interactive Prompt Simulation (The Signature Element) */}
                    <div className="mt-12 w-full max-w-3xl animate-fade-slide-in delay-300 relative group">
                        <div className="absolute -inset-1 bg-gradient-to-r from-brand/20 to-brand/0 rounded-3xl blur opacity-0 group-hover:opacity-100 transition duration-500"></div>
                        <div className="relative flex items-center bg-surface border border-border/80 rounded-2xl p-2 prompt-input-shadow">
                            <div className="pl-4 pr-2 text-brand">
                                <Sparkles size={24} />
                            </div>
                            <input 
                                type="text" 
                                value={prompt}
                                onChange={(e) => setPrompt(e.target.value)}
                                placeholder="Build a customer support agent integrated with our SAP database..."
                                className="w-full bg-transparent border-none focus:ring-0 text-text md:text-lg px-2 py-4 outline-none placeholder:text-text-muted/50"
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' && onPrimaryClick) {
                                        onPrimaryClick();
                                    }
                                }}
                            />
                            <button 
                                onClick={(e) => {
                                    if (onPrimaryClick) {
                                        e.preventDefault();
                                        onPrimaryClick();
                                    }
                                }}
                                className="hidden sm:flex shrink-0 items-center justify-center h-12 px-6 rounded-xl bg-brand text-white font-medium hover:bg-brand-hover transition-colors shadow-sm gap-2"
                            >
                                Generate <ArrowRight size={16} />
                            </button>
                        </div>
                    </div>
                </div>

                {/* Marquee Section */}
                <div className="mt-32 pt-10 border-t border-border/40 overflow-hidden reveal">
                    <p className="text-sm text-text-muted text-center mb-8 font-medium tracking-wide uppercase">
                        Supported Technologies & Integrations
                    </p>
                    
                    <div className="relative flex overflow-x-hidden group">
                        {/* Gradient Masks */}
                        <div className="absolute top-0 bottom-0 left-0 w-24 bg-gradient-to-r from-background to-transparent z-10" />
                        <div className="absolute top-0 bottom-0 right-0 w-24 bg-gradient-to-l from-background to-transparent z-10" />
                        
                        <div className="animate-marquee flex whitespace-nowrap items-center group-hover:pause">
                            {technologies.map((tech, index) => (
                                <div key={index} className="flex items-center gap-2 mx-6 text-text-muted hover:text-text transition-colors cursor-default">
                                    <div className="p-2.5 rounded-xl bg-surface border border-border shadow-sm text-text-muted group-hover:text-brand transition-colors">
                                        {tech.icon}
                                    </div>
                                    <span className="font-semibold text-sm">{tech.name}</span>
                                </div>
                            ))}
                            {/* Duplicate for seamless loop */}
                            {technologies.map((tech, index) => (
                                <div key={`dup-${index}`} className="flex items-center gap-2 mx-6 text-text-muted hover:text-text transition-colors cursor-default">
                                    <div className="p-2.5 rounded-xl bg-surface border border-border shadow-sm text-text-muted group-hover:text-brand transition-colors">
                                        {tech.icon}
                                    </div>
                                    <span className="font-semibold text-sm">{tech.name}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
};

export default ResponsiveHeroBanner;
