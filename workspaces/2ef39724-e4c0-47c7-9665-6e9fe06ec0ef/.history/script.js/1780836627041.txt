let display = document.getElementById('display');
let clearButton = document.getElementById('clear');
let backspaceButton = document.getElementById('backspace');
let equalsButton = document.getElementById('equals');
let addButton = document.getElementById('add');
let subtractButton = document.getElementById('subtract');
let multiplyButton = document.getElementById('multiply');
let divideButton = document.getElementById('divide');
let numberButtons = document.querySelectorAll('#number-0, #number-1, #number-2, #number-3, #number-4, #number-5, #number-6, #number-7, #number-8, #number-9');

let currentNumber = '';
let previousNumber = '';
let operator = '';

clearButton.addEventListener('click', () => {
    currentNumber = '';
    previousNumber = '';
    operator = '';
    display.value = '';
});

backspaceButton.addEventListener('click', () => {
    currentNumber = currentNumber.slice(0, -1);
    display.value = currentNumber;
});

equalsButton.addEventListener('click', () => {
    let result;
    switch (operator) {
        case '+':
            result = parseFloat(previousNumber) + parseFloat(currentNumber);
            break;
        case '-':
            result = parseFloat(previousNumber) - parseFloat(currentNumber);
            break;
        case '*':
            result = parseFloat(previousNumber) * parseFloat(currentNumber);
            break;
        case '/':
            result = parseFloat(previousNumber) / parseFloat(currentNumber);
            break;
        default:
            result = '';
    }
    display.value = result;
    previousNumber = result;
    currentNumber = '';
});

addButton.addEventListener('click', () => {
    operator = '+';
    previousNumber = currentNumber;
    currentNumber = '';
});

subtractButton.addEventListener('click', () => {
    operator = '-';
    previousNumber = currentNumber;
    currentNumber = '';
});

multiplyButton.addEventListener('click', () => {
    operator = '*';
    previousNumber = currentNumber;
    currentNumber = '';
});

divideButton.addEventListener('click', () => {
    operator = '/';
    previousNumber = currentNumber;
    currentNumber = '';
});

numberButtons.forEach(button => {
    button.addEventListener('click', () => {
        currentNumber += button.textContent;
        display.value = currentNumber;
    });
});