import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement | HTMLTextAreaElement> {
  label?: string;
  error?: string;
  type?: 'text' | 'email' | 'password' | 'number' | 'date' | 'textarea';
}

const Input: React.FC<InputProps> = ({ label, error, type = 'text', className = '', ...props }) => {
  const inputId = props.id || props.name;

  const renderInput = () => {
    if (type === 'textarea') {
      return (
        <textarea
          id={inputId}
          className={`mt-1 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md ${error ? 'border-danger-color' : ''} ${className}`}
          rows={3}
          {...(props as React.TextareaHTMLAttributes<HTMLTextAreaElement>)}
        />
      );
    }
    return (
      <input
        id={inputId}
        type={type}
        className={`mt-1 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md ${error ? 'border-danger-color' : ''} ${className}`}
        {...(props as React.InputHTMLAttributes<HTMLInputElement>)}
      />
    );
  };

  return (
    <div className="mb-4">
      {label && (
        <label htmlFor={inputId} className="block text-sm font-medium text-gray-700 mb-1">
          {label}
        </label>
      )}
      {renderInput()}
      {error && <p className="error-message mt-1">{error}</p>}
    </div>
  );
};

export default Input;