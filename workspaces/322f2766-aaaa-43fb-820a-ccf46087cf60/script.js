let taskList = document.getElementById('taskList');

function addTask() {
    let input = document.getElementById('taskInput');
    let taskText = input.value.trim();
    
    if (taskText !== '') {
        let li = document.createElement('li');
        li.textContent = taskText;

        let deleteButton = document.createElement('button');
        deleteButton.textContent = 'Delete';
        deleteButton.onclick = function() {
            taskList.removeChild(li);
        };

        li.appendChild(deleteButton);
        taskList.appendChild(li);

        input.value = '';
    }
}