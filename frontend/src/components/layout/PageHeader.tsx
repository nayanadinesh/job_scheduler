import type { ReactNode } from 'react';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  live?: boolean;
  liveLabel?: string;
  actions?: ReactNode;
}

export function PageHeader({ title, subtitle, live, liveLabel = 'Live', actions }: PageHeaderProps) {
  return (
    <header className="page-header">
      <div className="page-header__text">
        <div className="page-header__title-row">
          <h1 className="page-header__title">{title}</h1>
          {live && (
            <span className="live-badge">
              <span className="live-badge__dot" />
              {liveLabel}
            </span>
          )}
        </div>
        {subtitle && <p className="page-header__subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </header>
  );
}
