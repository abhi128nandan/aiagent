import React from 'react';

const Task = ({ task, onDelete, onEdit }) => {
  return (
    <div>
      <p>{task.text}</p>
      <button onClick={() => onDelete(task.id)}>Delete</button>
      <button onClick={() => onEdit(task.id)}>Edit</button>
    </div>
  );
};

export default Task;