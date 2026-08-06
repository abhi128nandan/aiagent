# Project: Simple Calculator

## Description
A simple calculator application built with React and Vite

## Tasks Checklist

- [x] **MODIFY** `src/App.jsx`
  *Description:* Replace the default Vite React boilerplate with a simple calculator layout: add a display field, number buttons (0-9), operator buttons (+, -, *, /), equals button, and clear button. Set up React state for the current calculation using useState. Implement the calculation logic for each button click. Use the CalculatorDisplay, CalculatorButton, and CalculatorKeyboard components.

- [x] **CREATE** `src/components/CalculatorDisplay.jsx`
  *Description:* Create a component to display the current calculation, using a text input field to show the calculation and result. Use the useState hook to store the current calculation and update it when the user clicks on a button. Pass the calculation state as a prop to the CalculatorDisplay component.

- [x] **CREATE** `src/components/CalculatorButton.jsx`
  *Description:* Create a reusable button component for the calculator, with props for the button label and click handler. Implement the logic for handling button clicks, including updating the calculation state and performing the calculation when the equals button is clicked. Use the CalculatorButton component in the CalculatorKeyboard component.

- [x] **CREATE** `src/components/CalculatorKeyboard.jsx`
  *Description:* Create a component to render the calculator keyboard, using the CalculatorButton component for each button. Implement the logic for rendering the keyboard layout, including the number buttons, operator buttons, and equals button. Pass the calculation state and update function as props to the CalculatorKeyboard component.

- [x] **MODIFY** `src/index.css`
  *Description:* Add CSS styles for the calculator layout, including the display field, buttons, and keyboard layout. Use CSS grid or flexbox to create a responsive layout that works on different screen sizes.

- [x] **MODIFY** `src/App.css`
  *Description:* Add CSS styles for the App component, including the calculator container and any other necessary styles. Use CSS classes to style the calculator components and create a visually appealing design.

- [x] **MODIFY** `src/main.jsx`
  *Description:* No changes needed, as the main entry point is already set up to render the App component.

- [x] **MODIFY** `package.json`
  *Description:* No changes needed, as the package.json file is already set up with the necessary dependencies and scripts.

- [x] **MODIFY** `vite.config.js`
  *Description:* No changes needed, as the Vite configuration is already set up for a React application.

