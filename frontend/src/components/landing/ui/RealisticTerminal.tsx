import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const realisticLogs = [
  { text: "Initializing Yantrika Planner...", type: "info", delay: 800 },
  { text: "✓ Requirements parsed and decomposed", type: "success", delay: 1200 },
  { text: "Generating system architecture...", type: "info", delay: 1500 },
  { text: "✓ React frontend generated (Vite + Tailwind)", type: "success", delay: 800 },
  { text: "✓ FastAPI backend generated", type: "success", delay: 400 },
  { text: "✓ PostgreSQL database schema defined", type: "success", delay: 500 },
  { text: "Provisioning Docker sandbox environment...", type: "command", delay: 1500 },
  { text: "Container sandbox_frontend_1 started", type: "success", delay: 800 },
  { text: "Container sandbox_backend_1 started", type: "success", delay: 400 },
  { text: "npm install", type: "command", delay: 2000 },
  { text: "added 241 packages, and audited 242 packages in 4s", type: "info", delay: 1000 },
  { text: "npm run test", type: "command", delay: 1500 },
  { text: "✓ 24 tests passed", type: "success", delay: 800 },
  { text: "Deployment ready. Initiating preview tunnel...", type: "info", delay: 1200 },
  { text: "✓ Tunnel established on port 5173", type: "success", delay: 800 }
];

export const RealisticTerminal: React.FC<{ className?: string }> = ({ className = '' }) => {
  const [visibleLogs, setVisibleLogs] = useState<number[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    let timeout: NodeJS.Timeout;

    const processNextLog = () => {
      if (currentIndex < realisticLogs.length) {
        const log = realisticLogs[currentIndex];
        timeout = setTimeout(() => {
          setVisibleLogs(prev => [...prev, currentIndex]);
          setCurrentIndex(prev => prev + 1);
        }, log.delay);
      } else {
        // Loop forever after a delay
        timeout = setTimeout(() => {
          setVisibleLogs([]);
          setCurrentIndex(0);
        }, 5000);
      }
    };

    processNextLog();

    return () => clearTimeout(timeout);
  }, [currentIndex]);

  // Keep scroll at bottom (simulated by slicing if too long, or just let it flow)
  const displayLogs = visibleLogs.slice(-8); // Show max 8 logs at a time

  return (
    <div className={`bg-[#0A0A0A] border border-[#222] rounded-xl shadow-2xl overflow-hidden font-mono text-[11px] sm:text-xs flex flex-col ${className}`}>
      {/* Terminal Header */}
      <div className="bg-[#1A1A1A] border-b border-[#333] px-4 py-2.5 flex items-center gap-2">
        <div className="flex gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-[#FF5F56]" />
          <div className="w-2.5 h-2.5 rounded-full bg-[#FFBD2E]" />
          <div className="w-2.5 h-2.5 rounded-full bg-[#27C93F]" />
        </div>
        <span className="text-[#888] mx-auto text-[10px]">yantrika-sandbox ~ bash</span>
      </div>

      {/* Terminal Body */}
      <div className="p-4 flex-1 overflow-hidden relative">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[#0A0A0A] pointer-events-none z-10" />
        <AnimatePresence>
          {displayLogs.map(index => {
            const log = realisticLogs[index];
            const colorClass = 
              log.type === 'success' ? 'text-[#4ADE80]' :
              log.type === 'command' ? 'text-[#F47A20]' : 'text-[#A1A1AA]';
            const prefix = log.type === 'command' ? '$ ' : '';

            return (
              <motion.div
                key={index}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                className={`mb-1.5 ${colorClass}`}
              >
                <span className="opacity-50 select-none">{prefix}</span>
                {log.text}
              </motion.div>
            );
          })}
        </AnimatePresence>
        
        {/* Blinking Cursor */}
        <motion.div 
          animate={{ opacity: [1, 0] }}
          transition={{ repeat: Infinity, duration: 0.8 }}
          className="w-2 h-3.5 bg-[#F47A20] mt-1 inline-block"
        />
      </div>
    </div>
  );
};
