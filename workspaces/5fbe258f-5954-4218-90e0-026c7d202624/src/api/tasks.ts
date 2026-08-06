import axios from 'axios';
import { Task } from '../types';

const API_URL = 'http://localhost:5000/api/tasks'; // Backend API URL

const getAuthHeaders = (token: string) => ({
  headers: {
    Authorization: `Bearer ${token}`,
  },
});

const tasksApi = {
  async getAllTasks(token: string): Promise<Task[]> {
    try {
      const response = await axios.get(API_URL, getAuthHeaders(token));
      return response.data;
    } catch (error) {
      console.error('Error fetching tasks:', error);
      throw error;
    }
  },

  async getTaskById(id: number, token: string): Promise<Task> {
    try {
      const response = await axios.get(`${API_URL}/${id}`, getAuthHeaders(token));
      return response.data;
    } catch (error) {
      console.error(`Error fetching task ${id}:`, error);
      throw error;
    }
  },

  async createTask(taskData: Omit<Task, 'id' | 'created_at' | 'updated_at' | 'user_id'>, token: string): Promise<Task> {
    try {
      const response = await axios.post(API_URL, taskData, getAuthHeaders(token));
      return response.data;
    } catch (error) {
      console.error('Error creating task:', error);
      throw error;
    }
  },

  async updateTask(id: number, taskData: Omit<Task, 'id' | 'created_at' | 'updated_at' | 'user_id'>, token: string): Promise<Task> {
    try {
      const response = await axios.put(`${API_URL}/${id}`, taskData, getAuthHeaders(token));
      return response.data;
    } catch (error) {
      console.error(`Error updating task ${id}:`, error);
      throw error;
    }
  },

  async updateTaskStatus(id: number, status: 'pending' | 'in-progress' | 'completed' | 'archived', token: string): Promise<Task> {
    try {
      const response = await axios.patch(`${API_URL}/${id}/status`, { status }, getAuthHeaders(token));
      return response.data;
    } catch (error) {
      console.error(`Error updating task status ${id}:`, error);
      throw error;
    }
  },

  async deleteTask(id: number, token: string): Promise<void> {
    try {
      await axios.delete(`${API_URL}/${id}`, getAuthHeaders(token));
    } catch (error) {
      console.error(`Error deleting task ${id}:`, error);
      throw error;
    }
  },
};

export default tasksApi;