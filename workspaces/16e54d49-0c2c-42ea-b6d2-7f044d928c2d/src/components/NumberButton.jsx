import React from 'react';

function NumberButton({ number, onClick }) {
  return (
    <button onClick={() => onClick(number)}>{number}</button>
  );
}

export default NumberButton;