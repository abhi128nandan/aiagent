document.addEventListener('DOMContentLoaded', () => {
    const appDiv = document.getElementById('app');
    appDiv.innerHTML = `
        <header>
            <h1>Task Manager</h1>
            <button id="theme-toggle">Toggle Theme</button>
        </header>
        <main>
            <form id="task-form">
                <input type="text" id="task-input" placeholder="Add a new task...">
                <button type="submit">Add Task</button>
            </form>
            <div id="stats">
                <span>Total Tasks: <span id="total-tasks">0</span></span>
                <span>Completed: <span id="completed-tasks">0</span></span>
                <span>Pending: <span id="pending-tasks">0</span></span>
            </div>
            <input type="text" id="filter-input" placeholder="Filter tasks...">
            <ul id="task-list"></ul>
        </main>
        <footer>
            <button id="export-json">Export JSON</button>
            <button id="import-json">Import JSON</button>
        </footer>
    `;

    const taskInput = document.getElementById('task-input');
    const taskForm = document.getElementById('task-form');
    const taskList = document.getElementById('task-list');
    const filterInput = document.getElementById('filter-input');
    const totalTasks = document.getElementById('total-tasks');
    const completedTasks = document.getElementById('completed-tasks');
    const pendingTasks = document.getElementById('pending-tasks');

    let tasks = [];

    function renderTasks() {
        taskList.innerHTML = '';
        tasks.forEach(task => {
            const li = document.createElement('li');
            li.textContent = task.description;
            if (task.completed) {
                li.style.textDecoration = 'line-through';
            }
            li.addEventListener('click', () => toggleTaskCompletion(task.id));
            taskList.appendChild(li);
        });
        updateStats();
    }

    function updateStats() {
        totalTasks.textContent = tasks.length;
        completedTasks.textContent = tasks.filter(task => task.completed).length;
        pendingTasks.textContent = tasks.filter(task => !task.completed).length;
    }

    function addTask(description) {
        const newTask = { id: Date.now(), description, completed: false };
        tasks.push(newTask);
        renderTasks();
    }

    function toggleTaskCompletion(id) {
        tasks = tasks.map(task => task.id === id ? { ...task, completed: !task.completed } : task);
        renderTasks();
    }

    function filterTasks(query) {
        const filteredTasks = tasks.filter(task => task.description.toLowerCase().includes(query.toLowerCase()));
        tasks = filteredTasks;
        renderTasks();
    }

    taskForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const description = taskInput.value.trim();
        if (description) {
            addTask(description);
            taskInput.value = '';
        }
    });

    filterInput.addEventListener('input', (e) => {
        filterTasks(e.target.value);
    });

    document.getElementById('theme-toggle').addEventListener('click', () => {
        document.body.classList.toggle('dark-theme');
    });

    document.getElementById('export-json').addEventListener('click', () => {
        const data = JSON.stringify(tasks, null, 2);
        const blob = new Blob([data], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'tasks.json';
        a.click();
    });

    document.getElementById('import-json').addEventListener('click', () => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json';
        input.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (event) => {
                    tasks = JSON.parse(event.target.result);
                    renderTasks();
                };
                reader.readAsText(file);
            }
        });
        input.click();
    });

    renderTasks();
});