import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

const codeSnippet = `import { useState, useEffect } from 'react';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(URL, KEY);

export function useRealtimeData() {
  const [data, setData] = useState([]);
  
  useEffect(() => {
    const channel = supabase
      .channel('schema-db-changes')
      .on('postgres_changes', 
          { event: '*', schema: 'public' }, 
          (payload) => {
        setData(prev => [...prev, payload.new]);
      })
      .subscribe();
      
    return () => supabase.removeChannel(channel);
  }, []);
  
  return data;
}`;

export const MockEditor: React.FC<{ className?: string }> = ({ className = '' }) => {
  const [text, setText] = useState('');
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    let timeout: NodeJS.Timeout;
    
    if (currentIndex < codeSnippet.length) {
      timeout = setTimeout(() => {
        setText(prev => prev + codeSnippet[currentIndex]);
        setCurrentIndex(prev => prev + 1);
      }, Math.random() * 30 + 10); // Random typing speed
    } else {
      // Loop
      timeout = setTimeout(() => {
        setText('');
        setCurrentIndex(0);
      }, 3000);
    }
    
    return () => clearTimeout(timeout);
  }, [currentIndex]);

  return (
    <div className={`bg-[#1E1E1E] rounded-xl border border-[#333] shadow-2xl overflow-hidden flex flex-col font-mono text-[11px] sm:text-xs ${className}`}>
      {/* Editor Tabs */}
      <div className="bg-[#2D2D2D] flex items-end px-2 pt-2 border-b border-[#1E1E1E]">
        <div className="bg-[#1E1E1E] text-[#D4D4D4] px-4 py-1.5 rounded-t-lg border-t border-x border-[#333] flex items-center gap-2">
          <span className="text-[#519ABA]">TS</span>
          useRealtimeData.ts
        </div>
        <div className="bg-transparent text-[#858585] px-4 py-1.5 hover:bg-[#1E1E1E]/50 cursor-pointer rounded-t-lg transition-colors flex items-center gap-2">
          <span className="text-[#519ABA]">TSX</span>
          Dashboard.tsx
        </div>
      </div>
      
      {/* Editor Body */}
      <div className="p-4 flex-1 overflow-auto relative text-[#D4D4D4] whitespace-pre">
        <code>
          <span dangerouslySetInnerHTML={{ __html: highlight(text) }} />
          <motion.span 
            animate={{ opacity: [1, 0] }}
            transition={{ repeat: Infinity, duration: 0.8 }}
            className="inline-block w-2 h-4 bg-[#007ACC] ml-0.5 align-middle"
          />
        </code>
      </div>
    </div>
  );
};

// Extremely simple pseudo-highlighter for the mock editor
function highlight(code: string) {
  return code
    .replace(/import|from|export|function|const|return/g, '<span class="text-[#569CD6]">$&</span>')
    .replace(/useState|useEffect|createClient/g, '<span class="text-[#DCDCAA]">$&</span>')
    .replace(/'[^']*'/g, '<span class="text-[#CE9178]">$&</span>')
    .replace(/supabase|channel|subscribe/g, '<span class="text-[#9CDCFE]">$&</span>');
}
