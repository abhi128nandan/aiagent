import React, { createContext, useState, useEffect, useCallback } from 'react';
import authApi from '../api/auth';
import { User } from '../types';

interface AuthContextType {
  isAuthenticated: boolean;
  user: User | null;
  token: string | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthContextProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const setAuthData = useCallback((newToken: string, newUser: User) => {
    localStorage.setItem('token', newToken);
    setToken(newToken);
    setUser(newUser);
    setIsAuthenticated(true);
    setError(null);
  }, []);

  const clearAuthData = useCallback(() => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
    setIsAuthenticated(false);
    setError(null);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await authApi.login(email, password);
      setAuthData(response.token, response.user);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Login failed');
      clearAuthData();
    } finally {
      setLoading(false);
    }
  }, [setAuthData, clearAuthData]);

  const register = useCallback(async (email: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await authApi.register(email, password);
      setAuthData(response.token, response.user);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Registration failed');
      clearAuthData();
    } finally {
      setLoading(false);
    }
  }, [setAuthData, clearAuthData]);

  const logout = useCallback(() => {
    clearAuthData();
  }, [clearAuthData]);

  useEffect(() => {
    const checkAuth = async () => {
      setLoading(true);
      const storedToken = localStorage.getItem('token');
      if (storedToken) {
        try {
          const profile = await authApi.getProfile(storedToken);
          setAuthData(storedToken, profile);
        } catch (err) {
          console.error('Failed to fetch user profile with stored token:', err);
          clearAuthData();
        }
      }
      setLoading(false);
    };
    checkAuth();
  }, [setAuthData, clearAuthData]);

  const value = {
    isAuthenticated,
    user,
    token,
    loading,
    error,
    login,
    register,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};