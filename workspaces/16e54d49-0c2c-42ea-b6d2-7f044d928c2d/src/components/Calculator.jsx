import React, { useState } from 'react';
import DisplayScreen from './DisplayScreen';
import NumberButton from './NumberButton';
import OperatorButton from './OperatorButton';
import EqualsButton from './EqualsButton';

function Calculator() {
  const [currentCalculation, setCurrentCalculation] = useState('');
  const [result, setResult] = useState('');

  const handleNumberClick = (number) => {
    setCurrentCalculation(currentCalculation + number);
  };

  const handleOperatorClick = (operator) => {
    setCurrentCalculation(currentCalculation + operator);
  };

  const handleEqualsClick = () => {
    const calculationResult = eval(currentCalculation);
    setResult(calculationResult);
  };

  return (
    <div>
      <DisplayScreen calculation={currentCalculation} result={result} />
      <div>
        <NumberButton number="7" onClick={handleNumberClick} />
        <NumberButton number="8" onClick={handleNumberClick} />
        <NumberButton number="9" onClick={handleNumberClick} />
        <OperatorButton operator="/" onClick={handleOperatorClick} />
      </div>
      <div>
        <NumberButton number="4" onClick={handleNumberClick} />
        <NumberButton number="5" onClick={handleNumberClick} />
        <NumberButton number="6" onClick={handleNumberClick} />
        <OperatorButton operator="*" onClick={handleOperatorClick} />
      </div>
      <div>
        <NumberButton number="1" onClick={handleNumberClick} />
        <NumberButton number="2" onClick={handleNumberClick} />
        <NumberButton number="3" onClick={handleNumberClick} />
        <OperatorButton operator="-" onClick={handleOperatorClick} />
      </div>
      <div>
        <NumberButton number="0" onClick={handleNumberClick} />
        <EqualsButton onClick={handleEqualsClick} />
        <OperatorButton operator="+" onClick={handleOperatorClick} />
      </div>
    </div>
  );
}

export default Calculator;