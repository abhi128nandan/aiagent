import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

export const Layer0Ambient: React.FC = () => {
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      // Normalized coordinates -1 to 1
      const x = (e.clientX / window.innerWidth) * 2 - 1;
      const y = (e.clientY / window.innerHeight) * 2 - 1;
      setMousePos({ x, y });
    };

    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none z-0 bg-[#FAF8F4]">
      {/* Base Gradient Layer */}
      <div className="absolute inset-0 bg-gradient-to-b from-[#FAF8F4] via-[#F4F1EA] to-[#0A0A0A] opacity-80" />

      {/* Slowly moving massive orbs for volumetric lighting */}
      <motion.div
        animate={{
          x: [0, 50, -20, 0],
          y: [0, -50, 20, 0],
        }}
        transition={{ duration: 25, repeat: Infinity, ease: "linear" }}
        className="absolute top-[-10%] left-[-10%] w-[60vw] h-[60vw] rounded-full bg-[#F47A20] blur-[150px] opacity-[0.04]"
      />
      <motion.div
        animate={{
          x: [0, -30, 40, 0],
          y: [0, 40, -30, 0],
        }}
        transition={{ duration: 30, repeat: Infinity, ease: "linear" }}
        className="absolute bottom-1/4 right-[-5%] w-[50vw] h-[50vw] rounded-full bg-[#F47A20] blur-[180px] opacity-[0.03]"
      />
      <motion.div
        animate={{
          x: [0, 60, -60, 0],
          y: [0, -60, 60, 0],
        }}
        transition={{ duration: 40, repeat: Infinity, ease: "linear" }}
        className="absolute top-1/2 left-1/3 w-[80vw] h-[80vw] rounded-full bg-blue-500 blur-[200px] opacity-[0.01]"
      />

      {/* Depth Fog / Noise Overlay */}
      <div 
        className="absolute inset-0 opacity-[0.03] mix-blend-overlay"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
        }}
      />

      {/* Grid overlay with radial mask */}
      <div 
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage: `linear-gradient(to right, #1F2937 1px, transparent 1px), linear-gradient(to bottom, #1F2937 1px, transparent 1px)`,
          backgroundSize: '40px 40px',
          maskImage: 'radial-gradient(ellipse at center, black 10%, transparent 80%)',
          WebkitMaskImage: 'radial-gradient(ellipse at center, black 10%, transparent 80%)'
        }}
      />

      {/* Interactive Cursor Spotlight - Extremely subtle */}
      <motion.div 
        className="absolute inset-0 z-10 transition-opacity duration-300 opacity-70"
        style={{
          background: `radial-gradient(800px circle at ${mousePos.x * 50 + 50}% ${mousePos.y * 50 + 50}%, rgba(255, 255, 255, 0.4), transparent 40%)`
        }}
      />
    </div>
  );
};
