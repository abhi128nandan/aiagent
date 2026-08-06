import React from 'react';
import { Outlet } from 'react-router-dom';
import Navbar from './Navbar';
import Sidebar from './Sidebar';

const Layout: React.FC = () => {
  return (
    <>
      <Navbar />
      <div className="main-content-area">
        <Sidebar />
        <main className="flex-1 p-4 overflow-auto">
          <Outlet /> {/* Renders the matched child route component */}
        </main>
      </div>
    </>
  );
};

export default Layout;