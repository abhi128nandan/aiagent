import React from 'react';
import { motion } from 'framer-motion';
import type { HTMLMotionProps, Variants } from 'framer-motion';

type AnimationType = 'fadeUp' | 'fadeLeft' | 'fadeRight' | 'scaleIn' | 'fadeIn';

interface MotionWrapperProps extends HTMLMotionProps<"div"> {
  children: React.ReactNode;
  animation?: AnimationType;
  delay?: number;
  duration?: number;
  className?: string;
  once?: boolean;
}

export const MotionWrapper: React.FC<MotionWrapperProps> = ({
  children,
  animation = 'fadeUp',
  delay = 0,
  duration = 0.5,
  className = '',
  once = true,
  ...props
}) => {
  const getVariants = (): Variants => {
    switch (animation) {
      case 'fadeUp':
        return {
          hidden: { opacity: 0, y: 24 },
          visible: { opacity: 1, y: 0, transition: { duration, delay, ease: [0.25, 0.1, 0.25, 1] } },
        };
      case 'fadeLeft':
        return {
          hidden: { opacity: 0, x: -24 },
          visible: { opacity: 1, x: 0, transition: { duration, delay, ease: [0.25, 0.1, 0.25, 1] } },
        };
      case 'fadeRight':
        return {
          hidden: { opacity: 0, x: 24 },
          visible: { opacity: 1, x: 0, transition: { duration, delay, ease: [0.25, 0.1, 0.25, 1] } },
        };
      case 'scaleIn':
        return {
          hidden: { opacity: 0, scale: 0.95 },
          visible: { opacity: 1, scale: 1, transition: { duration, delay, ease: [0.25, 0.1, 0.25, 1] } },
        };
      case 'fadeIn':
      default:
        return {
          hidden: { opacity: 0 },
          visible: { opacity: 1, transition: { duration, delay, ease: [0.25, 0.1, 0.25, 1] } },
        };
    }
  };

  return (
    <motion.div
      initial="hidden"
      whileInView="visible"
      viewport={{ once, margin: "-50px" }}
      variants={getVariants()}
      className={className}
      {...props}
    >
      {children}
    </motion.div>
  );
};

interface StaggerContainerProps extends HTMLMotionProps<"div"> {
  children: React.ReactNode;
  delayChildren?: number;
  staggerChildren?: number;
  className?: string;
  once?: boolean;
}

export const StaggerContainer: React.FC<StaggerContainerProps> = ({
  children,
  delayChildren = 0,
  staggerChildren = 0.1,
  className = '',
  once = true,
  ...props
}) => {
  const containerVariants: Variants = {
    hidden: {},
    visible: {
      transition: {
        staggerChildren,
        delayChildren,
      },
    },
  };

  return (
    <motion.div
      initial="hidden"
      whileInView="visible"
      viewport={{ once, margin: "-50px" }}
      variants={containerVariants}
      className={className}
      {...props}
    >
      {children}
    </motion.div>
  );
};
