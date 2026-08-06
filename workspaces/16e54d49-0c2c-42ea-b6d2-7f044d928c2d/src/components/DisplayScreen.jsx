import React from 'react';

function DisplayScreen({ calculation, result }) {
  return (
    <div>
      <p>Calculation: {calculation}</p>
      <p>Result: {result}</p>
    </div>
  );
}

export default DisplayScreen;