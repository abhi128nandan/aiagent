import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'link';
  size?: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
}

const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  children,
  className = '',
  ...props
}) => {
  const baseStyles = 'font-medium transition-all duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-offset-2';
  let variantStyles = '';
  let sizeStyles = '';

  switch (variant) {
    case 'primary':
      variantStyles = 'bg-primary-color text-white hover:bg-blue-600 focus:ring-primary-color';
      break;
    case 'secondary':
      variantStyles = 'bg-gray-200 text-gray-800 hover:bg-gray-300 focus:ring-gray-400';
      break;
    case 'danger':
      variantStyles = 'bg-danger-color text-white hover:bg-red-600 focus:ring-danger-color';
      break;
    case 'ghost':
      variantStyles = 'bg-transparent text-gray-700 hover:bg-gray-100 focus:ring-gray-300';
      break;
    case 'link':
      variantStyles = 'bg-transparent text-primary-color hover:underline focus:ring-primary-color p-0';
      break;
  }

  switch (size) {
    case 'sm':
      sizeStyles = 'px-3 py-1.5 text-sm rounded-md';
      break;
    case 'md':
      sizeStyles = 'px-4 py-2 text-base rounded-lg';
      break;
    case 'lg':
      sizeStyles = 'px-6 py-3 text-lg rounded-lg';
      break;
  }

  return (
    <button
      className={`${baseStyles} ${variantStyles} ${sizeStyles} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
};

export default Button;