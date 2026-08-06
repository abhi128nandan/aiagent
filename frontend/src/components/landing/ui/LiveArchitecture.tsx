import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export const LiveArchitecture: React.FC<{ className?: string }> = ({ className = '' }) => {
  const [stage, setStage] = useState(0);

  useEffect(() => {
    // Loop continuously building the architecture
    const interval = setInterval(() => {
      setStage(prev => (prev + 1) % 6);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className={`bg-white/90 backdrop-blur-xl border border-white shadow-[0_8px_30px_rgb(0,0,0,0.06)] rounded-2xl p-6 relative overflow-hidden ${className}`}>
      {/* Inner reflection */}
      <div className="absolute inset-0 rounded-2xl border border-white/60 pointer-events-none" />

      <div className="flex items-center justify-between mb-6 relative z-10">
        <h4 className="text-xs font-bold uppercase tracking-widest text-[#F47A20]">System Design</h4>
        <div className="flex gap-1">
          <motion.div animate={{ opacity: [1, 0] }} transition={{ repeat: Infinity, duration: 0.5 }} className="w-1.5 h-1.5 rounded-full bg-[#F47A20]" />
          <div className="text-[9px] font-bold text-[#9CA3AF] uppercase">Live</div>
        </div>
      </div>

      <div className="relative h-[180px] w-full z-10">
        <svg width="100%" height="100%" className="absolute inset-0 overflow-visible">
          {/* Paths drawn based on stage */}
          <motion.path
            d="M 60,30 L 150,30"
            stroke="#E9DED2" strokeWidth="2" strokeDasharray="4 4" fill="transparent"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: stage >= 1 ? 1 : 0, opacity: stage >= 1 ? 1 : 0 }}
            transition={{ duration: 0.6 }}
          />
          <motion.path
            d="M 190,30 L 250,30 L 250,90"
            stroke="#E9DED2" strokeWidth="2" strokeDasharray="4 4" fill="transparent"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: stage >= 2 ? 1 : 0, opacity: stage >= 2 ? 1 : 0 }}
            transition={{ duration: 0.8 }}
          />
          <motion.path
            d="M 170,50 L 170,120"
            stroke="#E9DED2" strokeWidth="2" strokeDasharray="4 4" fill="transparent"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: stage >= 3 ? 1 : 0, opacity: stage >= 3 ? 1 : 0 }}
            transition={{ duration: 0.6 }}
          />
          <motion.path
            d="M 230,140 L 150,140"
            stroke="#E9DED2" strokeWidth="2" strokeDasharray="4 4" fill="transparent"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: stage >= 4 ? 1 : 0, opacity: stage >= 4 ? 1 : 0 }}
            transition={{ duration: 0.6 }}
          />

          {/* Active Data Packets (Dots moving along paths) */}
          <AnimatePresence>
            {stage >= 1 && (
              <motion.circle key="dot1" r="3" fill="#F47A20"
                initial={{ offsetDistance: "0%" }} animate={{ offsetDistance: "100%" }}
                transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                style={{ offsetPath: `path('M 60,30 L 150,30')` as any }}
              />
            )}
            {stage >= 3 && (
              <motion.circle key="dot2" r="3" fill="#F47A20"
                initial={{ offsetDistance: "0%" }} animate={{ offsetDistance: "100%" }}
                transition={{ duration: 2, repeat: Infinity, ease: "linear", delay: 0.5 }}
                style={{ offsetPath: `path('M 170,50 L 170,120')` as any }}
              />
            )}
          </AnimatePresence>
        </svg>

        {/* Nodes */}
        <motion.div
          initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
          className="absolute top-[10px] left-0 w-[60px] h-[40px] bg-white border border-[#E9DED2] shadow-sm rounded-lg flex items-center justify-center text-[10px] font-bold text-[#1F2937]"
        >
          Client
        </motion.div>

        <motion.div
          initial={{ scale: 0, opacity: 0 }} animate={{ scale: stage >= 1 ? 1 : 0, opacity: stage >= 1 ? 1 : 0 }} transition={{ type: "spring" }}
          className="absolute top-[10px] left-[150px] w-[40px] h-[40px] bg-[#1F2937] text-white shadow-lg rounded-lg flex items-center justify-center text-[10px] font-bold"
        >
          API
        </motion.div>

        <motion.div
          initial={{ scale: 0, opacity: 0 }} animate={{ scale: stage >= 2 ? 1 : 0, opacity: stage >= 2 ? 1 : 0 }} transition={{ type: "spring" }}
          className="absolute top-[90px] left-[230px] w-[40px] h-[40px] bg-emerald-50 text-emerald-600 border border-emerald-200 shadow-sm rounded-lg flex items-center justify-center text-[10px] font-bold"
        >
          DB
        </motion.div>

        <motion.div
          initial={{ scale: 0, opacity: 0 }} animate={{ scale: stage >= 3 ? 1 : 0, opacity: stage >= 3 ? 1 : 0 }} transition={{ type: "spring" }}
          className="absolute top-[120px] left-[150px] w-[40px] h-[40px] bg-blue-50 text-blue-600 border border-blue-200 shadow-sm rounded-lg flex items-center justify-center text-[10px] font-bold"
        >
          Redis
        </motion.div>

        <motion.div
          initial={{ scale: 0, opacity: 0 }} animate={{ scale: stage >= 4 ? 1 : 0, opacity: stage >= 4 ? 1 : 0 }} transition={{ type: "spring" }}
          className="absolute top-[120px] left-[80px] w-[50px] h-[40px] bg-purple-50 text-purple-600 border border-purple-200 shadow-sm rounded-lg flex items-center justify-center text-[10px] font-bold"
        >
          Auth
        </motion.div>
      </div>
    </div>
  );
};
