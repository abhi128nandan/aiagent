import React from 'react';
import { Link } from 'react-router-dom';
import Button from '../components/Button';

const NotFound: React.FC = () => {
  return (
    <div className="flex-center min-h-screen bg-bg-color text-center flex-col p-4">
      <h1 className="text-6xl font-bold text-primary-color mb-4">404</h1>
      <h2 className="text-3xl font-semibold text-text-color mb-6">Page Not Found</h2>
      <p className="text-lg text-gray-700 mb-8">
        Oops! The page you are looking for does not exist.
      </p>
      <Link to="/">
        <Button variant="primary">Go to Dashboard</Button>
      </Link>
    </div>
  );
};

export default NotFound;