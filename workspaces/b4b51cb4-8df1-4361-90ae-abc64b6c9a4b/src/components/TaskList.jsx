import TaskItem from './TaskItem';

function TaskList({ tasks, onUpdateTask, onDeleteTask }) {
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');

  const filteredTasks = tasks.filter(task => {
    if (filter === 'completed') return task.completed;
    if (filter === 'pending') return !task.completed;
    return true;
  }).filter(task => 
    task.title.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="task-list">
      <div className="controls">
        <input
          type="text"
          placeholder="Search tasks..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="filters">
          <button onClick={() => setFilter('all')}>All</button>
          <button onClick={() => setFilter('pending')}>Pending</button>
          <button onClick={() => setFilter('completed')}>Completed</button>
        </div>
      </div>
      
      <div className="tasks">
        {filteredTasks.sort((a, b) => {
          // Sort by completion status first, then by due date
          if (a.completed && !b.completed) return 1;
          if (!a.completed && b.completed) return -1;
          return new Date(a.dueDate) - new Date(b.dueDate);
        }).map(task => (
          <TaskItem 
            key={task.id} 
            task={task} 
            onUpdate={onUpdateTask} 
            onDelete={onDeleteTask} 
          />
        ))}
      </div>
    </div>
  );
}

export default TaskList;