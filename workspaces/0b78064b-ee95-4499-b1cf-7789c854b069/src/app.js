
document.addEventListener('DOMContentLoaded', () => {
    const appDiv = document.getElementById('app');
    appDiv.innerHTML = `
        <h1>To-Do List</h1>
        <input type="text" id="todoInput" placeholder="Add a new task">
        <button onclick="addTask()">Add Task</button>
        <ul id="taskList"></ul>
    `;

    const todoInput = document.getElementById('todoInput');
    const taskList = document.getElementById('taskList');

    function addTask() {
        const taskText = todoInput.value.trim();
        if (taskText) {
            const li = document.createElement('li');
            li.textContent = taskText;
            taskList.appendChild(li);
            todoInput.value = '';
        }
    }

    // Function to remove a task
    function removeTask(event) {
        if (event.target.tagName === 'LI') {
            event.target.remove();
        }
    }

    taskList.addEventListener('click', removeTask);

    // Function to clear all completed tasks
    function clearCompletedTasks() {
        const completedTasks = document.querySelectorAll('#taskList li');
        completedTasks.forEach(task => {
            if (task.style.textDecoration === 'line-through') {
                task.remove();
            }
        });
    }

    document.getElementById('clearCompleted').addEventListener('click', clearCompletedTasks);
});
