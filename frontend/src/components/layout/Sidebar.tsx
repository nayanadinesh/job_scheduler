import { Activity, LayoutDashboard, Layers, ListChecks, LogOut, PlusCircle, Server } from 'lucide-react';
import { NavLink, useNavigate } from 'react-router-dom';
import { clearToken } from '../../lib/auth';

const sections = [
  {
    title: 'Monitor',
    items: [
      { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
      { to: '/jobs', label: 'Job Explorer', icon: ListChecks },
      { to: '/workers', label: 'Workers', icon: Server },
    ],
  },
  {
    title: 'Manage',
    items: [
      { to: '/queues', label: 'Queues', icon: Layers },
      { to: '/submit', label: 'Submit Job', icon: PlusCircle },
    ],
  },
];

export function Sidebar() {
  const navigate = useNavigate();

  const handleLogout = () => {
    clearToken();
    navigate('/login');
  };

  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <div className="sidebar__mark">
          <Activity size={17} strokeWidth={2.5} />
        </div>
        <div className="sidebar__brand-text">
          <span className="sidebar__brand-name">Scheduler</span>
          <span className="sidebar__brand-sub">Control Plane</span>
        </div>
      </div>

      <nav className="sidebar__nav">
        {sections.map((section) => (
          <div className="sidebar__section" key={section.title}>
            <span className="sidebar__section-title">{section.title}</span>
            {section.items.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `sidebar__link ${isActive ? 'sidebar__link--active' : ''}`
                }
              >
                <Icon size={16} strokeWidth={2} />
                <span>{label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <button className="sidebar__logout" onClick={handleLogout}>
        <LogOut size={15} strokeWidth={2} />
        <span>Sign out</span>
      </button>
    </aside>
  );
}
