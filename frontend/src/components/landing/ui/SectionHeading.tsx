import React from 'react';
import { MotionWrapper } from './MotionWrapper';

interface SectionHeadingProps {
  title: string;
  subtitle?: string;
  badge?: string;
  align?: 'left' | 'center';
  className?: string;
}

export const SectionHeading: React.FC<SectionHeadingProps> = ({
  title,
  subtitle,
  badge,
  align = 'center',
  className = ''
}) => {
  const alignClass = align === 'center' ? 'text-center mx-auto' : 'text-left';

  return (
    <div className={`mb-16 md:mb-20 ${alignClass} ${className}`}>
      {badge && (
        <MotionWrapper animation="fadeUp" delay={0}>
          <p className="text-xs uppercase tracking-widest font-bold text-[#F47A20] mb-3">
            {badge}
          </p>
        </MotionWrapper>
      )}
      
      <MotionWrapper animation="fadeUp" delay={0.1}>
        <h2 className="text-3xl md:text-5xl font-extrabold tracking-tight text-[#1F2937] leading-[1.15]">
          {title}
        </h2>
      </MotionWrapper>
      
      {subtitle && (
        <MotionWrapper animation="fadeUp" delay={0.2}>
          <p className="text-sm md:text-base text-[#6B7280] mt-4 max-w-2xl leading-relaxed">
            {subtitle}
          </p>
        </MotionWrapper>
      )}
    </div>
  );
};
