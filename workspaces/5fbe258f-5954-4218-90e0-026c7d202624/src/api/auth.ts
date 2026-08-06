import axios from 'axios';
import { User } from '../types';

const API_URL = 'http://localhost:5000/api/auth'; // Backend Auth API URL

interface AuthResponse {
  token: string;
  user: User;
}

const authApi = {
  async register(email: string, password: string): Promise<AuthResponse> {
    try {
      const response = await axios.post(`${API_URL}/register`, { email, password });
      return response.data;
    } catch (error) {
      console.error('Registration error:', error);
      throw error;
    }
  },

  async login(email: string, password: string): Promise<AuthResponse> {
    try {
      const response = await axios.post(`${API_URL}/login`, { email, password });
      return response.data;
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    }
  },

  async getProfile(token: string): Promise<User> {
    try {
      const response = await axios.get(`${API_URL}/profile`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      return response.data;
    } catch (error) {
      console.error('Error fetching profile:', error);
      throw error;
    }
  },
};

export default authApi;