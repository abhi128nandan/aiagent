import React, { useState, useEffect } from 'react';
import { Task } from '../types';
import Input from './Input';
import Button from './Button';
import { formatDate } from '../utils/helpers';

interface TaskFormProps {
  task?: Task | null;
  onSave: (taskData: Omit<Task, 'id' | 'created_at' | 'updated_at' | 'user_id'>) => void;
  onCancel: () => void;
}

const TaskForm: React.FC<TaskFormProps> = ({ task, onSave, onCancel }) => {
  const [title, setTitle] = useState(task?.title || '');
  const [description, setDescription] = useState(task?.description || '');
  const [dueDate, setDueDate] = useState(task?.due_date ? formatDate(task.due_date, 'YYYY-MM-DD') : '');
  const [priority, setPriority] = useState(task?.priority || 'medium');
  const [status, setStatus] = useState(task?.status || 'pending');
  const [titleError, setTitleError] = useState('');

  useEffect(() => {
    if (task) {
      setTitle(task.title);
      setDescription(task.description || '');
      setDueDate(task.due_date ? formatDate(task.due_date, 'YYYY-MM-DD') : '');
      setPriority(task.priority || 'medium');
      setStatus(task.status || 'pending');
    } else {
      setTitle('');
      setDescription('');
      setDueDate('');
      setPriority('medium');
      setStatus('pending');
    }
    setTitleError('');
  }, [task]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setTitleError('Task title is required.');
      return;
    }

    onSave({
      title,
      description,
      due_date: dueDate || null,
      priority: priority as 'low' | 'medium' | 'high',
      status: status as 'pending' | 'in-progress' | 'completed' | 'archived',
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 p-4">
      <Input
        label="Title"
        type="text"
        value={title}
        onChange={(e) => { setTitle(e.target.value); setTitleError(''); }}
        placeholder="e.g., Finish project report"
        error={titleError}
        name="title"
        required
      />
      <Input
        label="Description"
        type="textarea"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Details about the task..."
        name="description"
      />
      <Input
        label="Due Date"
        type="date"
        value={dueDate}
        onChange={(e) => setDueDate(e.target.value)}
        name="dueDate"
      />
      <div>
        <label htmlFor="priority" className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
        <select
          id="priority"
          name="priority"
          value={priority}
          onChange={(e) => setPriority(e.target.value)}
          className="w-full p-2 border border-border-color rounded-md"
        >
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
        </select>
      </div>
      <div>
        <label htmlFor="status" className="block text-sm font-medium text-gray-700 mb-1">Status</label>
        <select
          id="status"
          name="status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="w-full p-2 border border-border-color rounded-md"
        >
          <option value="pending">Pending</option>
          <option value="in-progress">In Progress</option>
          <option value="completed">Completed</option>
          <option value="archived">Archived</option>
        </select>
      </div>
      <div className="flex justify-end space-x-2 mt-6">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" variant="primary">
          {task ? 'Save Changes' : 'Create Task'}
        </Button>
      </div>
    </form>
  );
};

export default TaskForm;