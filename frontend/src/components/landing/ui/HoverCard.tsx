import React from 'react';
import { motion } from 'framer-motion';
import type { HTMLMotionProps } from 'framer-motion';

interface HoverCardProps extends HTMLMotionProps<"div"> {
  children: React.ReactNode;
  className?: string;
  tiltMaxAngleX?: number;
  tiltMaxAngleY?: number;
}

export const HoverCard: React.FC<HoverCardProps> = ({
  children,
  className = '',
  tiltMaxAngleX = 6,
  tiltMaxAngleY = 6,
  ...props
}) => {
  return (
    <motion.div
      whileHover={{ 
        y: -6, 
        rotateX: tiltMaxAngleX ? 1.5 : 0,
        rotateY: tiltMaxAngleY ? 1.5 : 0,
        scale: 1.01, 
        transition: { duration: 0.25, ease: "easeOut" }
      }}
      className={`relative bg-white border border-[#E9DED2] rounded-[20px] shadow-sm hover:shadow-xl hover:border-[#F47A20]/40 transition-shadow duration-300 group overflow-hidden ${className}`}
      {...props}
    >
      {/* Subtle border glow on hover */}
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none ring-1 ring-inset ring-[#F47A20]/20 rounded-[20px]" />
      
      <div className="relative z-10 h-full">
        {children}
      </div>
    </motion.div>
  );
};
