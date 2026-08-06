import React from 'react';

function OperatorButton({ operator, onClick }) {
  return (
    <button onClick={() => onClick(operator)}>{operator}</button>
  );
}

export default OperatorButton;