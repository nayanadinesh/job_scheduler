import type { ReactNode } from 'react';

interface StatCardProps {
  label: string;
  value: number | string;
  icon: ReactNode;
  color?: string;
  sub?: string;
  accent?: boolean;
}

export function StatCard({ label, value, icon, color = 'var(--accent)', sub, accent }: StatCardProps) {
  return (
    <div
      className={`stat-card ${accent ? 'stat-card--accent' : ''}`}
      style={{ '--stat-color': color } as React.CSSProperties}
    >
      <div className="stat-card__top">
        <span className="stat-card__label">{label}</span>
        <span className="stat-card__icon">{icon}</span>
      </div>
      <div className="stat-card__value">{value}</div>
      {sub && <div className="stat-card__sub">{sub}</div>}
      <div className="stat-card__bar" />
    </div>
  );
}
