import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, ArrowRight, Menu, X, Brain, Palette } from 'lucide-react';
import { BoltStyleChat } from './ui/bolt-style-chat';
import { BentoGrid } from './ui/bento-grid';

// ─── react-icons ──────────────────────────────────────────────────────────────
import {
  SiReact, SiNextdotjs, SiVuedotjs, SiAngular, SiNodedotjs,
  SiPython, SiTypescript, SiSap, SiWordpress, SiShopify,
  SiGooglecloud, SiDocker, SiKubernetes,
  SiPostgresql, SiMongodb, SiRedis, SiGraphql, SiIos,
  SiAndroid, SiFlutter, SiFigma, SiTensorflow, SiTailwindcss, SiGo, SiRust,
} from 'react-icons/si';
import { FaJava, FaAws, FaMicrosoft } from 'react-icons/fa';

interface YantrikaLandingPageProps {
  onStartBuilding: () => void;
  onOpenApp?: (mode?: string) => void;
}

export const YantrikaLandingPage: React.FC<YantrikaLandingPageProps> = ({ onStartBuilding, onOpenApp }) => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 40);
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const navItems = ['Features', 'Pricing', 'Docs', 'Blog'];

  return (
    <div className="min-h-screen bg-background text-text font-sans overflow-x-hidden">

      {/* ── Fixed Navbar ── */}
      <motion.nav
        initial={{ y: -80, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className={`fixed top-0 left-0 right-0 z-[100] transition-all duration-300 ${
          isScrolled ? 'glass-nav py-3' : 'bg-transparent py-5'
        }`}
      >
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-between">
          {/* Logo */}
          <div
            className="flex items-center gap-2.5 cursor-pointer group"
            onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
          >
            <div className="w-8 h-8 rounded-xl bg-brand flex items-center justify-center shadow-sm group-hover:shadow-md transition-shadow">
              <Sparkles size={16} className="text-white" />
            </div>
            <span className="font-bold text-base tracking-tight text-text">Yantrika AI</span>
          </div>

          {/* Desktop Nav */}
          <div className="hidden md:flex items-center gap-1">
            {navItems.map((item) => (
              <button
                key={item}
                className="px-4 py-2 text-sm font-medium text-text-muted hover:text-text transition-colors rounded-lg hover:bg-surface-hover"
              >
                {item}
              </button>
            ))}
          </div>

          {/* Desktop CTA */}
          <div className="hidden md:flex items-center gap-3">
            <button className="text-sm font-medium text-text-muted hover:text-text transition-colors">
              Sign In
            </button>
            <button
              onClick={() => { if (onOpenApp) onOpenApp(); else onStartBuilding(); }}
              className="h-9 px-5 inline-flex items-center gap-2 rounded-xl bg-brand text-white text-sm font-semibold hover:bg-brand-hover transition-all shadow-[0_2px_8px_rgba(244,122,32,0.25)] hover:shadow-[0_4px_12px_rgba(244,122,32,0.4)]"
            >
              Launch App <ArrowRight size={14} />
            </button>
          </div>

          {/* Mobile Hamburger */}
          <button
            className="md:hidden p-2 rounded-xl hover:bg-surface-hover transition-colors text-text"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        {/* Mobile Menu */}
        <AnimatePresence>
          {mobileMenuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
              className="md:hidden bg-surface border-t border-border/40 overflow-hidden"
            >
              <div className="px-6 py-4 flex flex-col gap-1">
                {navItems.map((item) => (
                  <button
                    key={item}
                    className="w-full text-left px-4 py-3 text-sm font-medium text-text-muted hover:text-text hover:bg-surface-hover rounded-xl transition-colors"
                  >
                    {item}
                  </button>
                ))}
                <div className="mt-3 pt-3 border-t border-border/40 flex flex-col gap-2">
                  <button className="w-full text-left px-4 py-3 text-sm font-medium text-text-muted">
                    Sign In
                  </button>
                  <button
                    onClick={() => { setMobileMenuOpen(false); if (onOpenApp) onOpenApp(); else onStartBuilding(); }}
                    className="w-full h-11 inline-flex items-center justify-center gap-2 rounded-xl bg-brand text-white text-sm font-semibold hover:bg-brand-hover transition-all shadow-[0_2px_8px_rgba(244,122,32,0.25)]"
                  >
                    Launch App <ArrowRight size={14} />
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.nav>

      <BoltStyleChat
        onSend={(msg) => {
          console.log('Agent prompt:', msg);
          onStartBuilding();
        }}
      />

      {/* ── Tech Marquee ── */}
      <div className="border-t border-border/40 py-10 overflow-hidden bg-background">
        <p className="text-sm text-text-muted text-center mb-8 font-medium tracking-wide uppercase">
          Supported Technologies & Integrations
        </p>
        <div className="relative flex overflow-x-hidden group">
          <div className="absolute top-0 bottom-0 left-0 w-24 bg-gradient-to-r from-background to-transparent z-10" />
          <div className="absolute top-0 bottom-0 right-0 w-24 bg-gradient-to-l from-background to-transparent z-10" />
          <div className="animate-marquee flex whitespace-nowrap items-center group-hover:pause">
            {[
              { name: "React", icon: <SiReact size={18} /> },
              { name: "Next.js", icon: <SiNextdotjs size={18} /> },
              { name: "Vue.js", icon: <SiVuedotjs size={18} /> },
              { name: "Angular", icon: <SiAngular size={18} /> },
              { name: "Node.js", icon: <SiNodedotjs size={18} /> },
              { name: "Python", icon: <SiPython size={18} /> },
              { name: "Java", icon: <FaJava size={18} /> },
              { name: "Go", icon: <SiGo size={18} /> },
              { name: "Rust", icon: <SiRust size={18} /> },
              { name: "TypeScript", icon: <SiTypescript size={18} /> },
              { name: "SAP", icon: <SiSap size={18} /> },
              { name: "WordPress", icon: <SiWordpress size={18} /> },
              { name: "Shopify", icon: <SiShopify size={18} /> },
              { name: "AWS", icon: <FaAws size={18} /> },
              { name: "GCP", icon: <SiGooglecloud size={18} /> },
              { name: "Azure", icon: <FaMicrosoft size={18} /> },
              { name: "Docker", icon: <SiDocker size={18} /> },
              { name: "Kubernetes", icon: <SiKubernetes size={18} /> },
              { name: "PostgreSQL", icon: <SiPostgresql size={18} /> },
              { name: "MongoDB", icon: <SiMongodb size={18} /> },
              { name: "Redis", icon: <SiRedis size={18} /> },
              { name: "GraphQL", icon: <SiGraphql size={18} /> },
              { name: "iOS", icon: <SiIos size={18} /> },
              { name: "Android", icon: <SiAndroid size={18} /> },
              { name: "Flutter", icon: <SiFlutter size={18} /> },
              { name: "React Native", icon: <SiReact size={18} /> },
              { name: "Figma", icon: <SiFigma size={18} /> },
              { name: "AI/ML", icon: <Brain size={18} /> },
              { name: "TensorFlow", icon: <SiTensorflow size={18} /> },
              { name: "Tailwind CSS", icon: <SiTailwindcss size={18} /> },
              { name: "UI/UX", icon: <Palette size={18} /> },
            ].flatMap((tech, i, arr) => [tech, ...( i === arr.length - 1 ? arr : []) ]).map((tech, index) => (
              <div key={index} className="flex items-center gap-2 mx-6 text-text-muted hover:text-text transition-colors cursor-default group/item">
                <div className="p-2.5 rounded-xl bg-surface border border-border shadow-sm text-text-muted group-hover/item:text-brand transition-colors">
                  {tech.icon}
                </div>
                <span className="font-semibold text-sm">{tech.name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Bento Features Grid ── */}
      <BentoGrid />

      {/* ── CTA Section ── */}
      <section className="w-full py-32 px-6 bg-surface border-t border-border relative overflow-hidden reveal">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[300px] bg-brand/10 rounded-full blur-[120px] pointer-events-none" />
        <div className="relative z-10 max-w-3xl mx-auto text-center">
          <motion.h2
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-100px' }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
            className="text-4xl md:text-5xl font-bold tracking-tight text-text"
          >
            Stop stitching tools together.
            <br />
            <span className="text-text-muted">Start shipping agents.</span>
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-100px' }}
            transition={{ duration: 0.8, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
            className="mt-6 text-lg text-text-muted max-w-xl mx-auto"
          >
            Join teams already building production AI agents with Yantrika. Free to start, scales with you.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-100px' }}
            transition={{ duration: 0.8, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4"
          >
            <button
              onClick={onStartBuilding}
              className="h-12 px-8 inline-flex items-center gap-2 rounded-xl bg-text text-white font-semibold text-sm hover:bg-text/90 transition-colors shadow-sm"
            >
              Start Building — Free <ArrowRight size={16} />
            </button>
            <button className="h-12 px-8 inline-flex items-center gap-2 rounded-xl border border-border bg-surface text-text font-medium text-sm hover:bg-surface-hover transition-colors">
              Talk to Sales
            </button>
          </motion.div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-border bg-background py-16 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-12 mb-16">
            <div className="col-span-2 md:col-span-1">
              <div className="flex items-center gap-2.5 mb-4">
                <div className="w-7 h-7 rounded-lg bg-brand flex items-center justify-center">
                  <Sparkles size={14} className="text-white" />
                </div>
                <span className="font-bold text-sm text-text">Yantrika AI</span>
              </div>
              <p className="text-sm text-text-muted leading-relaxed max-w-xs">
                The unified platform for building, deploying, and monitoring production-grade AI agents.
              </p>
            </div>
            <div>
              <h4 className="text-xs font-semibold text-text uppercase tracking-wider mb-4">Product</h4>
              <ul className="space-y-2.5">
                {['Builder', 'Workspace', 'Preview', 'Integrations', 'Pricing'].map(item => (
                  <li key={item}>
                    <button
                      onClick={() => { if (onOpenApp) onOpenApp(item); }}
                      className="text-sm text-text-muted hover:text-text transition-colors"
                    >
                      {item}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="text-xs font-semibold text-text uppercase tracking-wider mb-4">Resources</h4>
              <ul className="space-y-2.5">
                {['Documentation', 'API Reference', 'Changelog', 'Status', 'Blog'].map(item => (
                  <li key={item}><a href="#" className="text-sm text-text-muted hover:text-text transition-colors">{item}</a></li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="text-xs font-semibold text-text uppercase tracking-wider mb-4">Company</h4>
              <ul className="space-y-2.5">
                {['About', 'Careers', 'Contact', 'Privacy', 'Terms'].map(item => (
                  <li key={item}><a href="#" className="text-sm text-text-muted hover:text-text transition-colors">{item}</a></li>
                ))}
              </ul>
            </div>
          </div>
          <div className="pt-8 border-t border-border flex flex-col md:flex-row justify-between items-center gap-4">
            <span className="text-xs text-text-muted">
              © {new Date().getFullYear()} Yantrika AI. All rights reserved.
            </span>
            <div className="flex items-center gap-6">
              <a href="#" className="text-text-muted hover:text-text transition-colors" aria-label="Twitter/X">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" /></svg>
              </a>
              <a href="#" className="text-text-muted hover:text-text transition-colors" aria-label="GitHub">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" /></svg>
              </a>
              <a href="#" className="text-text-muted hover:text-text transition-colors" aria-label="LinkedIn">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" /></svg>
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};
