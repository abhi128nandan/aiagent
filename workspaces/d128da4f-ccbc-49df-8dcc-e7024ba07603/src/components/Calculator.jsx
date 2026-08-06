
import React, { useState } from 'react';
import './Calculator.css';

const Calculator = () => {
  const [displayValue, setDisplayValue] = useState('0');
  const [operator, setOperator] = useState(null);
  const [firstOperand, setFirstOperand] = useState(null);

  const handleNumberClick = (number) => {
    if (displayValue === '0') {
      setDisplayValue(number);
    } else {
      setDisplayValue(displayValue + number);
    }
  };

  const handleOperatorClick = (op) => {
    if (firstOperand === null) {
      setFirstOperand(parseFloat(displayValue));
    } else if (operator !== null) {
      const result = performCalculation(firstOperand, operator, parseFloat(displayValue));
      setFirstOperand(result);
    }
    setOperator(op);
    setDisplayValue('0');
  };

  const handleEqualsClick = () => {
    if (firstOperand !== null && operator !== null) {
      const result = performCalculation(firstOperand, operator, parseFloat(displayValue));
      setDisplayValue(result.toString());
      setFirstOperand(null);
      setOperator(null);
    }
  };

  const handleClearClick = () => {
    setDisplayValue('0');
    setOperator(null);
    setFirstOperand(null);
  };

  const performCalculation = (a, op, b) => {
    switch (op) {
      case '+':
        return a + b;
      case '-':
        return a - b;
      case '*':
        return a * b;
      case '/':
        return a / b;
      default:
        return 0;
    }
  };

  return (
    <div className="calculator">
      <div className="display">{displayValue}</div>
      <button onClick={handleClearClick}>C</button>
      <button onClick={() => handleOperatorClick('/')}>/</button>
      <button onClick={() => handleNumberClick('7')}>7</button>
      <button onClick={() => handleNumberClick('8')}>8</button>
      <button onClick={() => handleNumberClick('9')}>9</button>
      <button onClick={() => handleOperatorClick('*')}>*</button>
      <button onClick={() => handleNumberClick('4')}>4</button>
      <button onClick={() => handleNumberClick('5')}>5</button>
      <button onClick={() => handleNumberClick('6')}>6</button>
      <button onClick={() => handleOperatorClick('-')}>-</button>
      <button onClick={() => handleNumberClick('1')}>1</button>
      <button onClick={() => handleNumberClick('2')}>2</button>
      <button onClick={() => handleNumberClick('3')}>3</button>
      <button onClick={() => handleOperatorClick('+')}>+</button>
      <button onClick={() => handleNumberClick('0')}>0</button>
      <button onClick={handleEqualsClick}>=</button>
    </div>
  );
};

export default Calculator;
