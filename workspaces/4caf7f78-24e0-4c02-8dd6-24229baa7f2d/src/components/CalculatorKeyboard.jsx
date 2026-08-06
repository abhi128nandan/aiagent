import React from 'react';
import CalculatorButton from './CalculatorButton';

const CalculatorKeyboard = ({ calculation, updateCalculation }) => {
  const buttons = [
    { label: '7', onClick: () => updateCalculation('7') },
    { label: '8', onClick: () => updateCalculation('8') },
    { label: '9', onClick: () => updateCalculation('9') },
    { label: '/', onClick: () => updateCalculation('/') },
    { label: '4', onClick: () => updateCalculation('4') },
    { label: '5', onClick: () => updateCalculation('5') },
    { label: '6', onClick: () => updateCalculation('6') },
    { label: '*', onClick: () => updateCalculation('*') },
    { label: '1', onClick: () => updateCalculation('1') },
    { label: '2', onClick: () => updateCalculation('2') },
    { label: '3', onClick: () => updateCalculation('3') },
    { label: '-', onClick: () => updateCalculation('-') },
    { label: '0', onClick: () => updateCalculation('0') },
    { label: '.', onClick: () => updateCalculation('.') },
    { label: '=', onClick: () => updateCalculation('=') },
    { label: '+', onClick: () => updateCalculation('+') },
  ];

  return (
    <div>
      {buttons.map((button, index) => (
        <CalculatorButton key={index} label={button.label} onClick={button.onClick} />
      ))}
    </div>
  );
};

export default CalculatorKeyboard;