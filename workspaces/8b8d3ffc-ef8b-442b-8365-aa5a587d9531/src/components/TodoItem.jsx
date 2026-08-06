import React from 'react';

function TodoItem({ todo, onToggleComplete, onDeleteTodo }) {
  return (
    <li className={`todo-item ${todo.completed ? 'completed' : ''}`}>
      <input
        type="checkbox"
        checked={todo.completed}
        onChange={() => onToggleComplete(todo.id)}
        aria-label={`Mark ${todo.text} as ${todo.completed ? 'incomplete' : 'complete'}`}
      />
      <span className="todo-text">{todo.text}</span>
      <button onClick={() => onDeleteTodo(todo.id)} aria-label={`Delete ${todo.text}`}>Delete</button>
    </li>
  );
}

export default TodoItem;