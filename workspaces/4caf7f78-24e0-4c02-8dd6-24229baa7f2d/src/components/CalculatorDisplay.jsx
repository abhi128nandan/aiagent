import React from 'react';

const CalculatorDisplay = ({ calculation }) => {
  return (
    <div>
      <input type="text" value={calculation} readOnly />
    </div>
  );
};

export default CalculatorDisplay;