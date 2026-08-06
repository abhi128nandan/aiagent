import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import Input from '../components/Input';
import Button from '../components/Button';
import { validateEmail, validatePassword } from '../utils/helpers';

const Auth: React.FC = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [emailError, setEmailError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const { login, register, error, isAuthenticated, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/'); // Redirect to dashboard if already authenticated
    }
  }, [isAuthenticated, navigate]);

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setEmail(e.target.value);
    setEmailError('');
  };

  const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setPassword(e.target.value);
    setPasswordError('');
  };

  const validateForm = () => {
    let isValid = true;
    if (!validateEmail(email)) {
      setEmailError('Please enter a valid email address.');
      isValid = false;
    }
    if (!validatePassword(password)) {
      setPasswordError('Password must be at least 6 characters long.');
      isValid = false;
    }
    return isValid;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) {
      return;
    }

    if (isLogin) {
      await login(email, password);
    } else {
      await register(email, password);
    }
  };

  return (
    <div className="flex-center min-h-screen bg-bg-color">
      <div className="bg-card-bg p-8 rounded-lg shadow-lg w-full max-w-md">
        <h1 className="text-3xl font-bold text-center mb-6 text-text-color">
          {isLogin ? 'Login' : 'Register'}
        </h1>
        {error && <p className="error-message text-center mb-4">{error}</p>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Email"
            type="email"
            value={email}
            onChange={handleEmailChange}
            placeholder="Enter your email"
            error={emailError}
            name="email"
            required
          />
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={handlePasswordChange}
            placeholder="Enter your password"
            error={passwordError}
            name="password"
            required
          />
          <Button type="submit" variant="primary" className="w-full" disabled={loading}>
            {loading ? 'Loading...' : (isLogin ? 'Login' : 'Register')}
          </Button>
        </form>
        <p className="text-center mt-4 text-text-color">
          {isLogin ? "Don't have an account?" : "Already have an account?"}{' '}
          <Button variant="link" onClick={() => setIsLogin(!isLogin)} disabled={loading}>
            {isLogin ? 'Register here' : 'Login here'}
          </Button>
        </p>
      </div>
    </div>
  );
};

export default Auth;