import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';

export const LivePrompt: React.FC<{ className?: string }> = ({ className = '' }) => {
  const [text, setText] = useState("");
  const target = "Build a real-time analytics dashboard with React, Tailwind, and Supabase.";
  
  useEffect(() => {
    let index = 0;
    const interval = setInterval(() => {
      if (index <= target.length) {
        setText(target.slice(0, index));
        index++;
      } else {
        // Pause then clear and restart to keep it "living"
        setTimeout(() => {
          index = 0;
          setText("");
        }, 3000);
      }
    }, 50);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className={`bg-white/80 backdrop-blur-2xl border border-white shadow-[0_20px_60px_rgb(0,0,0,0.08)] rounded-2xl p-5 md:p-6 ${className}`}>
      <div className="absolute inset-0 rounded-2xl border border-white/50 pointer-events-none" />
      <div className="flex items-center gap-3 mb-4">
        <div className="w-8 h-8 rounded-full bg-[#F47A20]/10 flex items-center justify-center">
          <Sparkles size={16} className="text-[#F47A20]" />
        </div>
        <span className="text-[11px] font-bold uppercase tracking-widest text-[#F47A20]">Vision Prompt</span>
      </div>
      <p className="text-lg md:text-xl text-[#1F2937] font-medium leading-relaxed min-h-[60px]">
        {text}
        <motion.span 
          animate={{ opacity: [1, 0] }}
          transition={{ repeat: Infinity, duration: 0.8 }}
          className="inline-block w-2.5 h-5 bg-[#F47A20] ml-1 align-middle"
        />
      </p>
    </div>
  );
};
