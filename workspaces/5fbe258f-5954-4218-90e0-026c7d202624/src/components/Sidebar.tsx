import React from 'react';
import { Link } from 'react-router-dom';
import Button from './Button';

interface SidebarProps {
  onCreateTask?: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ onCreateTask }) => {
  return (
    <aside className="w-64 bg-white shadow-md p-4 border-r border-border-color flex-shrink-0">
      <nav className="space-y-2">
        <Link to="/" className="block p-2 rounded hover:bg-bg-color text-text-color">
          Dashboard
        </Link>
        <Link to="/tasks" className="block p-2 rounded hover:bg-bg-color text-text-color">
          All Tasks
        </Link>
        {/* Future links for filtering */}
        <Link to="/tasks?filter=today" className="block p-2 rounded hover:bg-bg-color text-text-color">
          Due Today
        </Link>
        <Link to="/tasks?filter=upcoming" className="block p-2 rounded hover:bg-bg-color text-text-color">
          Upcoming
        </Link>
        <Link to="/tasks?filter=completed" className="block p-2 rounded hover:bg-bg-color text-text-color">
          Completed
        </Link>
      </nav>
      <div className="mt-6">
        <Button onClick={onCreateTask} variant="primary" className="w-full">
          + Create New Task
        </Button>
      </div>
    </aside>
  );
};

export default Sidebar;