import { useState, useEffect } from 'react';
import AddTaskForm from './components/AddTaskForm';
import TaskList from './components/TaskList';
import './App.css';

function App() {
  const [tasks, setTasks] = useState([]);
  const [filter, setFilter] = useState('all');

  // Fetch tasks from API
  useEffect(() => {
    fetch('/api/tasks')
      .then(response => response.json())
      .then(data => setTasks(data))
      .catch(error => console.error('Error fetching tasks:', error));
  }, []);

  const addTask = (task) => {
    fetch('/api/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(task)
    })
    .then(response => response.json())
    .then(newTask => setTasks([...tasks, newTask]))
    .catch(error => console.error('Error adding task:', error));
  };

  const updateTask = (updatedTask) => {
    fetch(`/api/tasks/${updatedTask._id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updatedTask)
    })
    .then(response => response.json())
    .then(updated => {
      setTasks(tasks.map(task => 
        task._id === updated._id ? updated : task
      ));
    })
    .catch(error => console.error('Error updating task:', error));
  };

  const deleteTask = (id) => {
    fetch(`/api/tasks/${id}`, { method: 'DELETE' })
    .then(() => setTasks(tasks.filter(task => task._id !== id)))
    .catch(error => console.error('Error deleting task:', error));
  };

  const filteredTasks = tasks.filter(task => {
    if (filter === 'completed') return task.completed;
    if (filter === 'pending') return !task.completed;
    return true;
  });

  return (
    <div className="App">
      <h1>Task Manager</h1>
      <AddTaskForm onAdd={addTask} />
      <div className="filters">
        <button onClick={() => setFilter('all')}>All</button>
        <button onClick={() => setFilter('pending')}>Pending</button>
        <button onClick={() => setFilter('completed')}>Completed</button>
      </div>
      <TaskList 
        tasks={filteredTasks} 
        onUpdate={updateTask} 
        onDelete={deleteTask} 
      />
    </div>
  );
}

export default App;