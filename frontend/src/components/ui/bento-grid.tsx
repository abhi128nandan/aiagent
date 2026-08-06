"use client";

import React from 'react';
import { motion } from 'framer-motion';
import { 
    Sparkles, Bot, Zap, Shield, 
    GitBranch, Eye, Terminal, Puzzle
} from 'lucide-react';

interface BentoFeature {
    icon: React.ReactNode;
    title: string;
    description: string;
    className?: string;
}

const features: BentoFeature[] = [
    {
        icon: <Sparkles size={24} />,
        title: "Natural Language Builder",
        description: "Describe what you want in plain English. Yantrika translates your intent into production-ready AI agents with real code, not templates.",
        className: "md:col-span-2 md:row-span-2",
    },
    {
        icon: <Bot size={24} />,
        title: "Multi-Agent Orchestration",
        description: "Coordinate multiple agents working in parallel. Define hierarchies, handoffs, and fallback logic visually.",
    },
    {
        icon: <Zap size={24} />,
        title: "One-Click Deploy",
        description: "Ship to production in seconds. Automatic containerization, scaling, and monitoring built in.",
    },
    {
        icon: <Terminal size={24} />,
        title: "Live Workspace IDE",
        description: "Full-featured code editor with terminal, file browser, and real-time preview. Edit agent logic without leaving the platform.",
        className: "md:col-span-2",
    },
    {
        icon: <Eye size={24} />,
        title: "AI Observability",
        description: "Track token usage, latency, error rates, and agent decision paths. Debug issues before your users see them.",
    },
    {
        icon: <Shield size={24} />,
        title: "Enterprise Security",
        description: "SOC-2 ready. Role-based access, audit logs, and data residency controls for regulated industries.",
    },
    {
        icon: <GitBranch size={24} />,
        title: "Version Control",
        description: "Every agent change is tracked. Roll back, compare, and branch agent configurations like code.",
    },
    {
        icon: <Puzzle size={24} />,
        title: "200+ Integrations",
        description: "Connect to SAP, Salesforce, Slack, databases, APIs, and custom webhooks. Your agents work where your team works.",
    },
];

const cardVariants: any = {
    hidden: { opacity: 0, y: 32 },
    visible: (i: number) => ({
        opacity: 1,
        y: 0,
        transition: {
            delay: i * 0.08,
            duration: 0.6,
            ease: [0.16, 1, 0.3, 1],
        },
    }),
};

export const BentoGrid: React.FC = () => {
    return (
        <section className="w-full py-32 px-6 bg-background relative">
            <div className="max-w-7xl mx-auto">
                {/* Section Header */}
                <div className="max-w-2xl mb-16 reveal">
                    <span className="text-sm font-semibold text-brand tracking-wide uppercase">
                        Capabilities
                    </span>
                    <h2 className="mt-3 text-4xl md:text-5xl font-bold tracking-tight text-text">
                        Everything you need to ship agents that work.
                    </h2>
                    <p className="mt-4 text-lg text-text-muted max-w-xl">
                        From ideation to production monitoring. One platform, zero context-switching.
                    </p>
                </div>

                {/* Bento Grid */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 auto-rows-auto">
                    {features.map((feature, i) => (
                        <motion.div
                            key={feature.title}
                            custom={i}
                            initial="hidden"
                            whileInView="visible"
                            viewport={{ once: true, margin: '-80px' }}
                            variants={cardVariants}
                            whileHover={{ y: -4, transition: { type: 'spring', stiffness: 400, damping: 30 } }}
                            className={`bento-card group flex flex-col justify-between ${feature.className || ''}`}
                        >
                            <div>
                                <div className="w-12 h-12 rounded-2xl bg-brand/8 border border-brand/10 flex items-center justify-center text-brand mb-6 group-hover:bg-brand/12 transition-colors">
                                    {feature.icon}
                                </div>
                                <h3 className="text-lg font-semibold text-text mb-2 tracking-tight">
                                    {feature.title}
                                </h3>
                                <p className="text-sm text-text-muted leading-relaxed">
                                    {feature.description}
                                </p>
                            </div>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
};

export default BentoGrid;
