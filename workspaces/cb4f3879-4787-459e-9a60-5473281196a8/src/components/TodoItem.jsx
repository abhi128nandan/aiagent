import React from 'react';

function TodoItem({ todo, onToggleComplete, onDeleteTodo }) {
  return (
    <li className={`TodoItem ${todo.completed ? 'completed' : ''}`}>
      <input
        type="checkbox"
        checked={todo.completed}
        onChange={() => onToggleComplete(todo.id)}
      />
      <span>{todo.text}</span>
      <button onClick={() => onDeleteTodo(todo.id)}>Delete</button>
    </li>
  );
}

export default TodoItem;