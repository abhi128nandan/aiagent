import React, { useEffect, useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useTasks } from '../hooks/useTasks';
import { Task } from '../types';
import { formatDate } from '../utils/helpers';

const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const { tasks, loading, error, fetchTasks } = useTasks();
  const [dueToday, setDueToday] = useState<Task[]>([]);
  const [upcoming, setUpcoming] = useState<Task[]>([]);
  const [overdue, setOverdue] = useState<Task[]>([]);
  const [completed, setCompleted] = useState<Task[]>([]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  useEffect(() => {
    if (tasks.length > 0) {
      const today = new Date();
      today.setHours(0, 0, 0, 0);

      const filteredDueToday: Task[] = [];
      const filteredUpcoming: Task[] = [];
      const filteredOverdue: Task[] = [];
      const filteredCompleted: Task[] = [];

      tasks.forEach(task => {
        if (task.status === 'completed') {
          filteredCompleted.push(task);
        } else if (task.due_date) {
          const dueDate = new Date(task.due_date);
          dueDate.setHours(0, 0, 0, 0);

          if (dueDate.getTime() === today.getTime()) {
            filteredDueToday.push(task);
          } else if (dueDate.getTime() > today.getTime()) {
            filteredUpcoming.push(task);
          } else {
            filteredOverdue.push(task);
          }
        }
      });

      setDueToday(filteredDueToday);
      setUpcoming(filteredUpcoming);
      setOverdue(filteredOverdue);
      setCompleted(filteredCompleted);
    }
  }, [tasks]);

  if (loading) {
    return <div className="text-center p-4">Loading dashboard...</div>;
  }

  if (error) {
    return <div className="text-center p-4 text-danger-color">Error: {error}</div>;
  }

  return (
    <div className="dashboard p-4">
      <h1 className="text-3xl font-bold mb-6 text-text-color">Welcome, {user?.email || 'User'}!</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <DashboardCard title="Due Today" count={dueToday.length} tasks={dueToday} />
        <DashboardCard title="Upcoming" count={upcoming.length} tasks={upcoming} />
        <DashboardCard title="Overdue" count={overdue.length} tasks={overdue} />
        <DashboardCard title="Completed" count={completed.length} tasks={completed} />
      </div>

      <section className="recent-tasks mt-8">
        <h2 className="text-2xl font-semibold mb-4 text-text-color">Recent Activity</h2>
        {tasks.length === 0 ? (
          <p className="text-center text-gray-500">No tasks found. Start by creating a new one!</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {tasks.slice(0, 6).map(task => ( // Show up to 6 recent tasks
              <div key={task.id} className="bg-card-bg p-4 rounded-lg shadow-sm border border-border-color">
                <h3 className="font-semibold text-lg mb-1">{task.title}</h3>
                <p className="text-sm text-gray-600 mb-2">{task.description}</p>
                {task.due_date && (
                  <p className="text-xs text-gray-500">Due: {formatDate(task.due_date)}</p>
                )}
                <span className={`text-xs font-medium px-2 py-1 rounded-full ${
                  task.status === 'completed' ? 'bg-secondary-color text-white' :
                  task.status === 'in-progress' ? 'bg-primary-color text-white' :
                  'bg-gray-200 text-gray-800'
                }`}>
                  {task.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
};

interface DashboardCardProps {
  title: string;
  count: number;
  tasks: Task[];
}

const DashboardCard: React.FC<DashboardCardProps> = ({ title, count, tasks }) => {
  return (
    <div className="bg-card-bg p-6 rounded-lg shadow-md border border-border-color">
      <h2 className="text-xl font-semibold mb-2 text-text-color">{title}</h2>
      <p className="text-4xl font-bold text-primary-color mb-4">{count}</p>
      {tasks.length > 0 && (
        <ul className="list-none p-0 m-0 text-sm max-h-24 overflow-y-auto">
          {tasks.slice(0, 3).map(task => ( // Show top 3 tasks in card
            <li key={task.id} className="truncate text-gray-700">
              {task.title} {task.due_date && `(${formatDate(task.due_date)})`}
            </li>
          ))}
          {tasks.length > 3 && (
            <li className="text-gray-500">...and {tasks.length - 3} more</li>
          )}
        </ul>
      )}
      {tasks.length === 0 && (
        <p className="text-gray-500 text-sm">No tasks {title.toLowerCase()}.</p>
      )}
    </div>
  );
};

export default Dashboard;