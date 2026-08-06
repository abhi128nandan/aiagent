function TaskItem({ task, onUpdate, onDelete }) {
  const handleToggle = () => {
    const updatedTask = { ...task, completed: !task.completed };
    onUpdate(updatedTask);
  };

  return (
    <div className={`task-item ${task.completed ? 'completed' : ''}`}>
      <div className="task-content">
        <input 
          type="checkbox" 
          checked={task.completed} 
          onChange={handleToggle}
        />
        <div className="task-info">
          <h3>{task.title}</h3>
          <div className="task-meta">
            <span className={`priority ${task.priority}`}>{task.priority}</span>
            <span className="category">{task.category}</span>
            <span className="due-date">{new Date(task.dueDate).toLocaleDateString()}</span>
          </div>
        </div>
      </div>
      <button 
        className="delete-btn" 
        onClick={() => onDelete(task.id)}
      >
        Delete
      </button>
    </div>
  );
}

export default TaskItem;