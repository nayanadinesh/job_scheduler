import { useQuery } from '@tanstack/react-query';
import { Activity, CheckCircle2, Clock, Cpu, Server, Timer, XCircle } from 'lucide-react';
import { getMetrics } from '../api';
import type { QueueStat } from '../api';
import { PageHeader } from '../components/layout/PageHeader';
import { DistributionBar } from '../components/metrics/DistributionBar';
import { StatCard } from '../components/metrics/StatCard';

const STATUS_COLORS: Record<string, string> = {
  queued: 'var(--blue)',
  running: 'var(--amber)',
  completed: 'var(--green)',
  failed: 'var(--red)',
  dead: 'var(--red)',
  scheduled: 'var(--violet)',
  cancelled: 'var(--slate)',
};

function segmentsFor(q: QueueStat) {
  return (['completed', 'running', 'queued', 'scheduled', 'failed', 'dead', 'cancelled'] as const).map(
    (key) => ({ key, value: q[key] ?? 0, color: STATUS_COLORS[key] }),
  );
}

export function OverviewPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['metrics'],
    queryFn: getMetrics,
    refetchInterval: 5000,
  });

  if (isLoading) return <div className="page-loading">Loading metrics…</div>;
  if (error || !data) return <div className="page-error">Failed to load metrics</div>;

  const t = data.totals;
  const total = t.total ?? 0;
  const completed = t.completed ?? 0;
  const inFlight = (t.running ?? 0) + (t.queued ?? 0);
  const successRate = total > 0 ? Math.round((completed / total) * 100) : 0;

  const heroSegments = (['completed', 'running', 'queued', 'scheduled', 'failed', 'dead', 'cancelled'] as const)
    .map((key) => ({ key, value: t[key] ?? 0, color: STATUS_COLORS[key] }));

  return (
    <div className="page">
      <PageHeader
        title="Overview"
        subtitle="Real-time state of your job fleet"
        live
        liveLabel="Live · 5s"
      />

      {/* Hero throughput panel */}
      <section className="hero-panel">
        <div className="hero-panel__main">
          <div className="hero-panel__metric">
            <span className="hero-panel__metric-label">Total jobs processed</span>
            <span className="hero-panel__metric-value">{total.toLocaleString()}</span>
            <div className="hero-panel__meta">
              <span className="hero-panel__chip hero-panel__chip--green">
                <CheckCircle2 size={13} /> {successRate}% success
              </span>
              <span className="hero-panel__chip hero-panel__chip--amber">
                <Activity size={13} /> {inFlight} in flight
              </span>
            </div>
          </div>
          <div className="hero-panel__dist">
            <DistributionBar segments={heroSegments} height={12} />
            <div className="hero-panel__legend">
              {heroSegments.filter((s) => s.value > 0).map((s) => (
                <span key={s.key} className="hero-panel__legend-item">
                  <span className="hero-panel__legend-dot" style={{ background: s.color }} />
                  {s.key} <b>{s.value}</b>
                </span>
              ))}
            </div>
          </div>
        </div>
        <div className="hero-panel__side">
          <div className="hero-panel__worker">
            <div className="hero-panel__worker-icon">
              <Server size={18} />
            </div>
            <div>
              <div className="hero-panel__worker-count">
                {data.workers.active}
                <span className="hero-panel__worker-total">/ {data.workers.total}</span>
              </div>
              <div className="hero-panel__worker-label">workers active</div>
            </div>
          </div>
        </div>
      </section>

      {/* Stat grid */}
      <section className="stat-grid">
        <StatCard label="Queued" value={t.queued ?? 0} icon={<Clock size={16} />} color="var(--blue)" />
        <StatCard label="Running" value={t.running ?? 0} icon={<Cpu size={16} />} color="var(--amber)" />
        <StatCard label="Completed" value={t.completed ?? 0} icon={<CheckCircle2 size={16} />} color="var(--green)" />
        <StatCard label="Failed / Dead" value={(t.failed ?? 0) + (t.dead ?? 0)} icon={<XCircle size={16} />} color="var(--red)" />
        <StatCard label="Scheduled" value={t.scheduled ?? 0} icon={<Timer size={16} />} color="var(--violet)" />
      </section>

      {/* Queue cards */}
      <section className="section">
        <div className="section__head">
          <h2 className="section__title">Queues</h2>
          <span className="section__count">{data.queues.length}</span>
        </div>
        <div className="queue-grid">
          {data.queues.length === 0 && (
            <div className="empty-state">
              <div className="empty-state__icon"><ListEmpty /></div>
              <p className="empty-state__title">No queues yet</p>
              <p className="empty-state__hint">Create a project and queue, then submit a job to get started.</p>
            </div>
          )}
          {data.queues.map((q) => (
            <div key={q.queue_id} className="queue-card">
              <div className="queue-card__head">
                <span className="queue-card__name">{q.queue_name}</span>
                <span className="queue-card__total">{q.total}</span>
              </div>
              <DistributionBar segments={segmentsFor(q)} />
              <div className="queue-card__stats">
                {(['completed', 'running', 'queued', 'dead'] as const).map((s) => (
                  q[s] > 0 ? (
                    <div key={s} className="queue-card__stat">
                      <span className="queue-card__stat-dot" style={{ background: STATUS_COLORS[s] }} />
                      <span className="queue-card__stat-key">{s}</span>
                      <span className="queue-card__stat-val">{q[s]}</span>
                    </div>
                  ) : null
                ))}
              </div>
              {q.avg_duration_ms !== null && (
                <div className="queue-card__footer">
                  <Timer size={12} />
                  avg {q.avg_duration_ms?.toFixed(0)}ms
                  <span className="queue-card__footer-sep">·</span>
                  {q.completed_executions} runs
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function ListEmpty() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="3" y="4" width="18" height="4" rx="1" />
      <rect x="3" y="10" width="18" height="4" rx="1" />
      <rect x="3" y="16" width="12" height="4" rx="1" />
    </svg>
  );
}
