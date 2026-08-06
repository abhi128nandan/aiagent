import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Layers } from 'lucide-react';

const thinkingStates = [
  "Analyzing requirements...",
  "Decomposing features...",
  "Resolving dependencies...",
  "Optimizing graph...",
  "Allocating agents...",
  "Drafting specifications...",
];

export const LivePlanner: React.FC<{ className?: string }> = ({ className = '' }) => {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setIndex(prev => (prev + 1) % thinkingStates.length);
    }, 1500 + Math.random() * 1000); // Randomize slightly for organic feel
    return () => clearInterval(interval);
  }, []);

  return (
    <div className={`relative rounded-2xl bg-white/70 backdrop-blur-xl border border-white shadow-[0_8px_30px_rgb(0,0,0,0.04)] p-4 flex flex-col gap-3 overflow-hidden ${className}`}>
      {/* Inner glass border highlight */}
      <div className="absolute inset-0 rounded-2xl border border-white/40 pointer-events-none" />
      
      <div className="flex items-center gap-3 relative z-10">
        <div className="relative w-8 h-8 flex items-center justify-center">
          {/* Pulsing ring */}
          <motion.div 
            animate={{ scale: [1, 1.5, 1], opacity: [0.5, 0, 0.5] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
            className="absolute inset-0 rounded-full bg-[#F47A20]"
          />
          <div className="absolute inset-1 rounded-full bg-white flex items-center justify-center z-10 shadow-sm">
            <Layers size={14} className="text-[#F47A20]" />
          </div>
        </div>
        <div>
          <h4 className="text-[10px] font-bold tracking-widest text-[#9CA3AF] uppercase">Agent Status</h4>
          <p className="text-xs font-bold text-[#1F2937]">Core Planner</p>
        </div>
      </div>

      <div className="bg-[#F9FAFB]/80 rounded-lg p-2.5 relative z-10 h-10 flex items-center overflow-hidden border border-[#E9DED2]/50">
        <AnimatePresence mode="wait">
          <motion.div
            key={index}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3 }}
            className="text-[11px] font-mono text-[#4B5563] flex items-center gap-2"
          >
            <motion.span 
              animate={{ opacity: [1, 0] }}
              transition={{ duration: 0.8, repeat: Infinity }}
              className="w-1.5 h-1.5 rounded-full bg-[#F47A20] inline-block"
            />
            {thinkingStates[index]}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
};
