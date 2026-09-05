import React, { useSyncExternalStore } from 'react';
import { motion } from 'framer-motion';

const emptySubscribe = () => () => {};

export const AmbientFloat: React.FC<{
  children: React.ReactNode;
  delay?: number;
  duration?: number;
  className?: string;
}> = ({ children, delay = 0, duration = 12, className = '' }) => {
  const mounted = useSyncExternalStore(emptySubscribe, () => true, () => false);

  if (!mounted) return <div className={className}>{children}</div>;

  return (
    <motion.div
      className={className}
      animate={{
        y: [0, -15, 0],
        x: [0, 5, -5, 0],
        rotate: [0, 0.5, -0.5, 0]
      }}
      transition={{
        y: { duration: duration, repeat: Infinity, ease: "easeInOut", delay },
        x: { duration: duration * 1.2, repeat: Infinity, ease: "easeInOut", delay },
        rotate: { duration: duration * 1.5, repeat: Infinity, ease: "easeInOut", delay }
      }}
    >
      {children}
    </motion.div>
  );
};
