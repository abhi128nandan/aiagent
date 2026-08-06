import React, { useEffect, useState } from 'react';
import { useTasks } from '../hooks/useTasks';
import TaskList from '../components/TaskList';
import TaskForm from '../components/TaskForm';
import Modal from '../components/Modal';
import Button from '../components/Button';
import Input from '../components/Input';
import { Task } from '../types';

const Tasks: React.FC = () => {
  const { tasks, loading, error, fetchTasks, addTask, updateTask, updateTaskStatus, deleteTask } = useTasks();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [filter, setFilter] = useState('');
  const [sort, setSort] = useState('due_date'); // Default sort

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  const handleCreateTask = () => {
    setEditingTask(null);
    setIsModalOpen(true);
  };

  const handleEditTask = (task: Task) => {
    setEditingTask(task);
    setIsModalOpen(true);
  };

  const handleSaveTask = async (taskData: Omit<Task, 'id' | 'created_at' | 'updated_at' | 'user_id'>) => {
    if (editingTask) {
      await updateTask(editingTask.id, taskData);
    } else {
      await addTask(taskData);
    }
    setIsModalOpen(false);
    setEditingTask(null);
  };

  const handleDeleteTask = async (id: number) => {
    if (window.confirm('Are you sure you want to delete this task?')) {
      await deleteTask(id);
    }
  };

  const handleToggleComplete = async (id: number, currentStatus: 'pending' | 'in-progress' | 'completed') => {
    const newStatus = currentStatus === 'completed' ? 'pending' : 'completed';
    await updateTaskStatus(id, newStatus);
  };

  const filteredTasks = tasks.filter(task =>
    task.title.toLowerCase().includes(filter.toLowerCase()) ||
    task.description?.toLowerCase().includes(filter.toLowerCase())
  );

  const sortedTasks = [...filteredTasks].sort((a, b) => {
    if (sort === 'due_date') {
      const dateA = a.due_date ? new Date(a.due_date).getTime() : Infinity;
      const dateB = b.due_date ? new Date(b.due_date).getTime() : Infinity;
      return dateA - dateB;
    }
    if (sort === 'priority') {
      const priorityOrder = { 'high': 3, 'medium': 2, 'low': 1 };
      return (priorityOrder[b.priority as keyof typeof priorityOrder] || 0) - (priorityOrder[a.priority as keyof typeof priorityOrder] || 0);
    }
    if (sort === 'created_at') {
      const dateA = new Date(a.created_at).getTime();
      const dateB = new Date(b.created_at).getTime();
      return dateB - dateA; // Newest first
    }
    if (sort === 'title') {
      return a.title.localeCompare(b.title);
    }
    return 0;
  });


  if (loading) {
    return <div className="text-center p-4">Loading tasks...</div>;
  }

  if (error) {
    return <div className="text-center p-4 text-danger-color">Error: {error}</div>;
  }

  return (
    <div className="tasks-page p-4">
      <h1 className="text-3xl font-bold mb-6 text-text-color">My Tasks</h1>

      <div className="flex justify-between items-center mb-6">
        <Button onClick={handleCreateTask} variant="primary">
          Add New Task
        </Button>
        <div className="flex space-x-4">
          <Input
            type="text"
            placeholder="Search tasks..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-64"
          />
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="p-2 border border-border-color rounded-md"
          >
            <option value="due_date">Sort by Due Date</option>
            <option value="priority">Sort by Priority</option>
            <option value="created_at">Sort by Creation Date</option>
            <option value="title">Sort by Title</option>
          </select>
        </div>
      </div>

      {sortedTasks.length === 0 ? (
        <p className="text-center text-gray-500">No tasks found. Create one to get started!</p>
      ) : (
        <TaskList
          tasks={sortedTasks}
          onEdit={handleEditTask}
          onDelete={handleDeleteTask}
          onToggleComplete={handleToggleComplete}
        />
      )}

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={editingTask ? 'Edit Task' : 'Create New Task'}>
        <TaskForm
          task={editingTask}
          onSave={handleSaveTask}
          onCancel={() => setIsModalOpen(false)}
        />
      </Modal>
    </div>
  );
};

export default Tasks;