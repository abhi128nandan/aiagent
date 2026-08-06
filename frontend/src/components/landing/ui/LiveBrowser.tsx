import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export const LiveBrowser: React.FC<{ className?: string }> = ({ className = '' }) => {
  const [stage, setStage] = useState(0);

  useEffect(() => {
    // 0: Initial load (skeleton)
    // 1: Sidebar snaps in
    // 2: Header & widgets pop
    // 3: Chart animates
    // 4: Toast notification
    const sequence = [
      { time: 1000, stage: 1 },
      { time: 2000, stage: 2 },
      { time: 2800, stage: 3 },
      { time: 3800, stage: 4 },
      { time: 7000, stage: 0 }, // Reset loop
    ];
    
    let timeouts = sequence.map(s => setTimeout(() => setStage(s.stage), s.time));
    return () => timeouts.forEach(clearTimeout);
  }, [stage]);

  return (
    <div className={`bg-white/95 backdrop-blur-2xl border border-white shadow-[0_20px_50px_rgb(0,0,0,0.1)] rounded-2xl overflow-hidden flex flex-col ${className}`}>
      {/* Inner border */}
      <div className="absolute inset-0 rounded-2xl border border-white/60 pointer-events-none z-50" />
      
      {/* Browser Header */}
      <div className="bg-[#FAF8F4]/80 backdrop-blur-md border-b border-[#E9DED2] px-4 py-3 flex items-center gap-4 relative z-10">
        <div className="flex gap-1.5">
          <div className="w-3 h-3 rounded-full bg-[#E5E7EB]" />
          <div className="w-3 h-3 rounded-full bg-[#E5E7EB]" />
          <div className="w-3 h-3 rounded-full bg-[#E5E7EB]" />
        </div>
        <div className="flex-1 bg-white/80 border border-[#E9DED2] rounded-md h-7 flex items-center px-4 justify-center shadow-sm">
          <span className="text-[11px] font-mono text-[#9CA3AF]">localhost:5173</span>
        </div>
      </div>

      {/* Browser Body */}
      <div className="flex-1 flex overflow-hidden bg-[#F9FAFB] relative z-0">
        {/* Sidebar */}
        <motion.div 
          initial={{ width: 0, opacity: 0 }}
          animate={{ width: stage >= 1 ? 64 : 0, opacity: stage >= 1 ? 1 : 0 }}
          transition={{ type: "spring", damping: 20, stiffness: 100 }}
          className="h-full bg-white border-r border-[#E9DED2] flex flex-col items-center py-6 gap-6 shadow-sm"
        >
          <div className="w-8 h-8 rounded bg-[#F47A20]/20 mb-4" />
          <div className="w-6 h-6 rounded bg-gray-100" />
          <div className="w-6 h-6 rounded bg-gray-100" />
          <div className="w-6 h-6 rounded bg-gray-100" />
        </motion.div>

        {/* Content */}
        <div className="flex-1 p-6 md:p-8 overflow-hidden flex flex-col gap-6">
          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: stage >= 2 ? 1 : 0, y: stage >= 2 ? 0 : 10 }}
            className="w-1/3 h-5 bg-gray-200 rounded-md"
          />
          
          <div className="grid grid-cols-3 gap-6">
            {[1, 2, 3].map((i) => (
              <motion.div 
                key={i}
                initial={{ opacity: 0, scale: 0.9, y: 10 }}
                animate={{ opacity: stage >= 2 ? 1 : 0, scale: stage >= 2 ? 1 : 0.9, y: stage >= 2 ? 0 : 10 }}
                transition={{ delay: i * 0.1, type: "spring" }}
                className="bg-white p-4 rounded-xl border border-[#E9DED2] shadow-sm h-24 flex flex-col justify-between"
              >
                <div className="w-1/2 h-2.5 bg-gray-100 rounded" />
                <div className="w-3/4 h-4 bg-gray-200 rounded" />
              </motion.div>
            ))}
          </div>

          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: stage >= 3 ? 1 : 0, y: stage >= 3 ? 0 : 20 }}
            className="bg-white rounded-xl border border-[#E9DED2] shadow-sm p-6 flex-1 flex items-end gap-3"
          >
            {[40, 70, 30, 90, 50, 80, 20, 100, 60].map((h, i) => (
              <motion.div 
                key={i}
                initial={{ height: 0 }}
                animate={{ height: stage >= 3 ? `${h}%` : 0 }}
                transition={{ delay: 0.2 + i * 0.05, duration: 0.6, type: "spring", bounce: 0.2 }}
                className="flex-1 bg-gradient-to-t from-[#F47A20]/20 to-[#F47A20]/60 rounded-t-sm"
              />
            ))}
          </motion.div>
        </div>

        {/* Hot Reload Indicator / Success Toast */}
        <AnimatePresence>
          {stage === 0 && (
            <motion.div key="loader"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="absolute inset-0 bg-white/50 backdrop-blur-sm z-40 flex items-center justify-center"
            >
               <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: "linear" }} className="w-6 h-6 border-2 border-gray-300 border-t-[#F47A20] rounded-full" />
            </motion.div>
          )}
          {stage >= 4 && (
            <motion.div key="toast"
              initial={{ opacity: 0, y: 20, x: "-50%" }}
              animate={{ opacity: 1, y: 0, x: "-50%" }}
              exit={{ opacity: 0, y: 20, x: "-50%" }}
              className="absolute bottom-6 left-1/2 bg-[#1F2937] text-white text-xs font-bold px-4 py-2 rounded-full shadow-2xl flex items-center gap-3 z-50 border border-gray-700"
            >
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              Hot Reload Complete
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};
