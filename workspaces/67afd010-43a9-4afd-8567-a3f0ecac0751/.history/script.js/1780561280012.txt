let display = document.getElementById('display');
let currentInput = '';
let operator = null;
let firstOperand = null;

function appendNumber(number) {
    if (currentInput.length < 10) {
        currentInput += number;
        updateDisplay();
    }
}

function appendOperator(op) {
    if (firstOperand === null) {
        firstOperand = parseFloat(currentInput);
    } else {
        calculateResult();
        firstOperand = result;
    }
    operator = op;
    currentInput = '';
}

function appendDecimal() {
    if (!currentInput.includes('.')) {
        currentInput += '.';
        updateDisplay();
    }
}

function clearDisplay() {
    currentInput = '';
    operator = null;
    firstOperand = null;
    updateDisplay();
}

function calculateResult() {
    let secondOperand = parseFloat(currentInput);
    switch (operator) {
        case '+':
            result = firstOperand + secondOperand;
            break;
        case '-':
            result = firstOperand - secondOperand;
            break;
        case '*':
            result = firstOperand * secondOperand;
            break;
        case '/':
            if (secondOperand !== 0) {
                result = firstOperand / secondOperand;
            } else {
                result = 'Error';
            }
            break;
        default:
            result = currentInput;
    }
    display.value = result;
    currentInput = result.toString();
}

function updateDisplay() {
    display.value = currentInput;
}