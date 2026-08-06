# Project: calculator

## Description
A simple calculator application built with React using Vite

## Tasks Checklist

- [ ] **MODIFY** `src/App.jsx`
  *Description:* Replace the default Vite React boilerplate with the calculator application layout: add a Calculator component import, and set up React state for calculator display using useState. Implement logic for handling user input, performing calculations, and displaying results. Import the Calculator component and render it in the App component. The Calculator component should be rendered inside a div with a CSS class 'calculator-container'. The state should be initialized with a default value of 0 for the display.

- [ ] **CREATE** `src/components/Calculator.jsx`
  *Description:* Create a Calculator component that includes input fields for numbers, buttons for operations (add, subtract, multiply, divide), and a display field for the result. Implement event handlers for button clicks and input field changes, and use React state to store the current calculation and result. Define a function to handle each operation and update the result state accordingly. The component should have a CSS class 'calculator' and should contain a form with input fields for the two numbers, buttons for the operations, and a paragraph to display the result. The input fields should have CSS classes 'number-input' and the buttons should have CSS classes 'operation-button'. The paragraph should have a CSS class 'result-display'.

- [ ] **MODIFY** `src/index.css`
  *Description:* Replace default Vite styles with application-specific CSS: add styles for the calculator layout, including input fields, buttons, and display field. Use CSS grid or flexbox to create a responsive layout. Define CSS classes for the calculator container, input fields, buttons, and display field. The calculator container should have a CSS class 'calculator-container' and should contain a grid with two columns and three rows. The input fields should have CSS classes 'number-input' and should be placed in the first and second columns of the first row. The buttons should have CSS classes 'operation-button' and should be placed in the first and second columns of the second and third rows. The display field should have a CSS class 'result-display' and should be placed in the first and second columns of the third row.

- [ ] **MODIFY** `src/main.jsx`
  *Description:* Update the main entry point of the application to render the Calculator component. Use React's ReactDOM.render function to render the Calculator component to the DOM. Ensure the Calculator component is properly imported and rendered in the main entry point. The Calculator component should be rendered inside a div with a CSS class 'calculator-container'.

- [ ] **MODIFY** `vite.config.js`
  *Description:* Update the Vite configuration to include any necessary plugins or settings for the calculator application. For example, add support for CSS modules or configure the development server to run on a specific port.

- [ ] **MODIFY** `package.json`
  *Description:* Update the package.json file to include any necessary dependencies for the calculator application. For example, add dependencies for React or CSS libraries. Ensure the dependencies are properly installed and configured.

