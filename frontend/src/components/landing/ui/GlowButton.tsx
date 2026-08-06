import React from 'react';
import { motion } from 'framer-motion';
import type { HTMLMotionProps } from 'framer-motion';

interface GlowButtonProps extends HTMLMotionProps<"button"> {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary';
  className?: string;
  icon?: React.ReactNode;
}

export const GlowButton: React.FC<GlowButtonProps> = ({
  children,
  variant = 'primary',
  className = '',
  icon,
  ...props
}) => {
  const baseClasses = "relative inline-flex items-center justify-center gap-2 rounded-2xl text-sm font-bold transition-all duration-300 overflow-hidden group";
  
  const variantClasses = variant === 'primary' 
    ? "bg-[#F47A20] text-white shadow-md hover:shadow-xl hover:shadow-[#F47A20]/20"
    : "bg-white text-[#1F2937] border border-[#E9DED2] shadow-sm hover:shadow-md hover:border-[#F47A20]/40";

  return (
    <motion.button
      whileHover={{ y: -2 }}
      whileTap={{ scale: 0.98 }}
      className={`${baseClasses} ${variantClasses} ${className}`}
      {...props}
    >
      {/* Subtle hover gradient movement (Primary only) */}
      {variant === 'primary' && (
        <span className="absolute inset-0 w-full h-full bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full group-hover:animate-[shimmer_1.5s_infinite]" />
      )}
      
      <span className="relative z-10 flex items-center gap-2">
        {children}
        {icon && (
          <span className="transition-transform duration-300 group-hover:translate-x-1.5">
            {icon}
          </span>
        )}
      </span>
    </motion.button>
  );
};
