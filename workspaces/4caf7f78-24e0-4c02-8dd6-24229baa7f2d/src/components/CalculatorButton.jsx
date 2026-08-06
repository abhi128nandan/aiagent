import React from 'react';

const CalculatorButton = ({ label, onClick }) => {
  return (
    <div>
      <button onClick={onClick}>{label}</button>
    </div>
  );
};

export default CalculatorButton;