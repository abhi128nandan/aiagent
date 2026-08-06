import React from 'react';
import { Task } from '../types';
import Button from './Button';
import { formatDate } from '../utils/helpers';

interface TaskItemProps {
  task: Task;
  onEdit: (task: Task) => void;
  onDelete: (id: number) => void;
  onToggleComplete: (id: number, status: 'pending' | 'in-progress' | 'completed') => void;
}

const TaskItem: React.FC<TaskItemProps> = ({ task, onEdit, onDelete, onToggleComplete }) => {
  const isCompleted = task.status === 'completed';

  const getPriorityClass = (priority: 'low' | 'medium' | 'high') => {
    switch (priority) {
      case 'high': return 'bg-danger-color text-white';
      case 'medium': return 'bg-accent-color text-white';
      case 'low': return 'bg-secondary-color text-white';
      default: return 'bg-gray-200 text-gray-800';
    }
  };

  return (
    <div className={`bg-card-bg p-4 rounded-lg shadow-sm border border-border-color flex items-center justify-between ${isCompleted ? 'opacity-70 line-through' : ''}`}>
      <div className="flex items-center flex-1">
        <input
          type="checkbox"
          checked={isCompleted}
          onChange={() => onToggleComplete(task.id, task.status)}
          className="mr-3 h-5 w-5 text-primary-color focus:ring-primary-color border-gray-300 rounded"
        />
        <div>
          <h3 className="font-semibold text-lg text-text-color">{task.title}</h3>
          {task.description && <p className="text-sm text-gray-600">{task.description}</p>}
          <div className="flex items-center space-x-2 text-xs mt-1">
            {task.due_date && (
              <span className="text-gray-500">Due: {formatDate(task.due_date)}</span>
            )}
            <span className={`px-2 py-1 rounded-full ${getPriorityClass(task.priority)}`}>
              {task.priority}
            </span>
            <span className={`px-2 py-1 rounded-full text-xs font-medium ${
              task.status === 'completed' ? 'bg-secondary-color text-white' :
              task.status === 'in-progress' ? 'bg-primary-color text-white' :
              'bg-gray-200 text-gray-800'
            }`}>
              {task.status}
            </span>
          </div>
        </div>
      </div>
      <div className="flex space-x-2">
        <Button onClick={() => onEdit(task)} variant="secondary" size="sm">
          Edit
        </Button>
        <Button onClick={() => onDelete(task.id)} variant="danger" size="sm">
          Delete
        </Button>
      </div>
    </div>
  );
};

export default TaskItem;