import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import Button from './Button';

const Navbar: React.FC = () => {
  const { isAuthenticated, user, logout } = useAuth();

  return (
    <nav className="bg-white shadow-md p-4 flex justify-between items-center">
      <Link to="/" className="text-2xl font-bold text-primary-color">
        To-Do App
      </Link>
      <div className="flex items-center space-x-4">
        {isAuthenticated ? (
          <>
            <span className="text-text-color">Hello, {user?.email || 'User'}!</span>
            <Button onClick={logout} variant="secondary">
              Logout
            </Button>
          </>
        ) : (
          <>
            <Link to="/auth" className="text-primary-color hover:text-secondary-color">
              Login / Register
            </Link>
          </>
        )}
      </div>
    </nav>
  );
};

export default Navbar;