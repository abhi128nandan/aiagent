import React, { createContext, useState, useEffect, useCallback, useContext } from 'react';
import tasksApi from '../api/tasks';
import { Task } from '../types';
import { AuthContext } from './AuthContext';

interface TaskContextType {
  tasks: Task[];
  loading: boolean;
  error: string | null;
  fetchTasks: () => Promise<void>;
  addTask: (taskData: Omit<Task, 'id' | 'created_at' | 'updated_at' | 'user_id'>) => Promise<void>;
  updateTask: (id: number, taskData: Omit<Task, 'id' | 'created_at' | 'updated_at' | 'user_id'>) => Promise<void>;
  updateTaskStatus: (id: number, status: 'pending' | 'in-progress' | 'completed' | 'archived') => Promise<void>;
  deleteTask: (id: number) => Promise<void>;
}

export const TaskContext = createContext<TaskContextType | undefined>(undefined);

export const TaskContextProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { token, isAuthenticated } = useContext(AuthContext)!;
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTasks = useCallback(async () => {
    if (!token || !isAuthenticated) {
      setTasks([]); // Clear tasks if not authenticated
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const fetchedTasks = await tasksApi.getAllTasks(token);
      setTasks(fetchedTasks);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to fetch tasks');
    } finally {
      setLoading(false);
    }
  }, [token, isAuthenticated]);

  const addTask = useCallback(async (taskData: Omit<Task, 'id' | 'created_at' | 'updated_at' | 'user_id'>) => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const newTask = await tasksApi.createTask(taskData, token);
      setTasks(prevTasks => [...prevTasks, newTask]);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to add task');
    } finally {
      setLoading(false);
    }
  }, [token]);

  const updateTask = useCallback(async (id: number, taskData: Omit<Task, 'id' | 'created_at' | 'updated_at' | 'user_id'>) => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const updatedTask = await tasksApi.updateTask(id, taskData, token);
      setTasks(prevTasks => prevTasks.map(task => (task.id === id ? updatedTask : task)));
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to update task');
    } finally {
      setLoading(false);
    }
  }, [token]);

  const updateTaskStatus = useCallback(async (id: number, status: 'pending' | 'in-progress' | 'completed' | 'archived') => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const updatedTask = await tasksApi.updateTaskStatus(id, status, token);
      setTasks(prevTasks => prevTasks.map(task => (task.id === id ? updatedTask : task)));
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to update task status');
    } finally {
      setLoading(false);
    }
  }, [token]);

  const deleteTask = useCallback(async (id: number) => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      await tasksApi.deleteTask(id, token);
      setTasks(prevTasks => prevTasks.filter(task => task.id !== id));
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to delete task');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchTasks();
    } else {
      setTasks([]); // Clear tasks if user logs out
    }
  }, [isAuthenticated, fetchTasks]);

  const value = {
    tasks,
    loading,
    error,
    fetchTasks,
    addTask,
    updateTask,
    updateTaskStatus,
    deleteTask,
  };

  return <TaskContext.Provider value={value}>{children}</TaskContext.Provider>;
};