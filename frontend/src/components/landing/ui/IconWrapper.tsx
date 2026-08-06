import React from 'react';
import { motion } from 'framer-motion';
import type { HTMLMotionProps } from 'framer-motion';

type IconAnimationType = 'rotate' | 'cubeRotate' | 'pulse' | 'branch' | 'glow' | 'none';

interface IconWrapperProps extends HTMLMotionProps<"div"> {
  children: React.ReactNode;
  animation?: IconAnimationType;
  className?: string;
}

export const IconWrapper: React.FC<IconWrapperProps> = ({
  children,
  animation = 'none',
  className = '',
  ...props
}) => {
  const getAnimationVariants = (): any => {
    switch (animation) {
      case 'rotate':
        return {
          rest: { rotate: 0 },
          hover: { rotate: 90, transition: { duration: 0.5, ease: "linear" } }
        };
      case 'cubeRotate':
        return {
          rest: { rotateY: 0, rotateX: 0 },
          hover: { rotateY: 15, rotateX: -15, transition: { duration: 0.4, ease: "easeOut" } }
        };
      case 'pulse':
        return {
          rest: { scale: 1 },
          hover: { scale: [1, 1.1, 1], transition: { duration: 0.6, repeat: Infinity } }
        };
      case 'branch':
        return {
          rest: { rotate: 0, y: 0 },
          hover: { rotate: 10, y: -2, transition: { duration: 0.3 } }
        };
      case 'glow':
        return {
          rest: { filter: 'drop-shadow(0px 0px 0px rgba(244,122,32,0))' },
          hover: { filter: 'drop-shadow(0px 0px 8px rgba(244,122,32,0.4))', transition: { duration: 0.3 } }
        };
      default:
        return {};
    }
  };

  return (
    <motion.div
      initial="rest"
      whileHover="hover"
      whileInView="rest"
      variants={getAnimationVariants()}
      className={`inline-flex items-center justify-center ${className}`}
      {...props}
    >
      {children}
    </motion.div>
  );
};
