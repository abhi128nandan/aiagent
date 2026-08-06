import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

export const SceneBackground: React.FC = () => {
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
    <div className="absolute inset-0 overflow-hidden pointer-events-none z-0 bg-[#FAF8F4]">
      {/* Layer 1: Animated Mesh Gradient */}
      <motion.div 
        animate={{
          backgroundPosition: ['0% 0%', '100% 100%', '0% 0%']
        }}
        transition={{ duration: 30, repeat: Infinity, ease: "linear" }}
        className="absolute inset-0 opacity-40 mix-blend-multiply"
        style={{
          background: `radial-gradient(circle at center, #FFF3E6 0%, transparent 50%), radial-gradient(circle at top right, #F47A2015 0%, transparent 40%), radial-gradient(circle at bottom left, #FFB88515 0%, transparent 40%)`,
          backgroundSize: '200% 200%'
        }}
      />

      {/* Layer 2: Noise Texture */}
      <div 
        className="absolute inset-0 opacity-[0.02] mix-blend-overlay"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
        }}
      />

      {/* Layer 3: Blurred Radial Lights (Spring-driven based on mouse but very slow/ambient) */}
      <motion.div
        animate={{ x: mousePos.x * 20, y: mousePos.y * 20 }}
        transition={{ type: "spring", damping: 50, stiffness: 100 }}
        className="absolute top-1/4 left-1/4 w-[40vw] h-[40vw] rounded-full bg-[#F47A20] blur-[120px] opacity-[0.03]"
      />
      <motion.div
        animate={{ x: mousePos.x * -30, y: mousePos.y * -30 }}
        transition={{ type: "spring", damping: 60, stiffness: 80 }}
        className="absolute bottom-1/4 right-1/4 w-[50vw] h-[50vw] rounded-full bg-[#F47A20] blur-[150px] opacity-[0.02]"
      />

      {/* Layer 4: Grid */}
      <div 
        className="absolute inset-0 opacity-[0.03] mask-image-radial"
        style={{
          backgroundImage: `linear-gradient(to right, #1F2937 1px, transparent 1px), linear-gradient(to bottom, #1F2937 1px, transparent 1px)`,
          backgroundSize: '40px 40px',
          maskImage: 'radial-gradient(ellipse at center, black 20%, transparent 70%)',
          WebkitMaskImage: 'radial-gradient(ellipse at center, black 20%, transparent 70%)'
        }}
      />

      {/* Layer 5: Cursor Spotlight */}
      <motion.div 
        className="absolute inset-0 z-10 transition-opacity duration-300 opacity-70"
        style={{
          background: `radial-gradient(600px circle at ${mousePos.x * 50 + 50}% ${mousePos.y * 50 + 50}%, rgba(244, 122, 32, 0.05), transparent 40%)`
        }}
      />

      {/* Layer 6: Floating Particles (Max 5) */}
      {[...Array(5)].map((_, i) => (
        <motion.div
          key={i}
          animate={{
            y: [-20, 20, -20],
            x: [-10, 10, -10],
            opacity: [0.1, 0.3, 0.1]
          }}
          transition={{
            duration: 10 + i * 2,
            repeat: Infinity,
            ease: "easeInOut",
            delay: i * -3
          }}
          className="absolute w-1 h-1 rounded-full bg-[#F47A20]"
          style={{
            left: `${15 + i * 20}%`,
            top: `${20 + (i % 3) * 25}%`,
            boxShadow: '0 0 10px 2px rgba(244,122,32,0.4)'
          }}
        />
      ))}
    </div>
  );
};
