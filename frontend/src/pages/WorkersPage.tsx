import { useQuery } from '@tanstack/react-query';
import { Server } from 'lucide-react';
import { listWorkers } from '../api';
import { PageHeader } from '../components/layout/PageHeader';
import { Badge } from '../components/ui/Badge';

function fmtTime(s: string | null) {
  if (!s) return '—';
  return new Date(s).toLocaleTimeString(undefined, {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

function heartbeatAge(s: string | null): { label: string; stale: boolean } {
  if (!s) return { label: '—', stale: true };
  const secs = Math.max(0, Math.round((Date.now() - new Date(s).getTime()) / 1000));
  return { label: secs < 60 ? `${secs}s ago` : `${Math.round(secs / 60)}m ago`, stale: secs > 30 };
}

export function WorkersPage() {
  const { data: workers, isLoading } = useQuery({
    queryKey: ['workers'],
    queryFn: listWorkers,
    refetchInterval: 5000,
  });

  const activeCount = workers?.filter((w) => w.status === 'active').length ?? 0;

  return (
    <div className="page">
      <PageHeader
        title="Workers"
        subtitle={`${activeCount} active · ${workers?.length ?? 0} total`}
        live
        liveLabel="Live · 5s"
      />

      {isLoading && <div className="page-loading">Loading workers…</div>}

      {!isLoading && (!workers || workers.length === 0) && (
        <div className="empty-state empty-state--panel">
          <div className="empty-state__icon"><Server size={26} /></div>
          <p className="empty-state__title">No workers registered</p>
          <p className="empty-state__hint">Start a worker process with <code className="inline-code">python -m app.worker</code>.</p>
        </div>
      )}

      {workers && workers.length > 0 && (
        <div className="panel">
          <table className="data-table">
            <thead>
              <tr>
                <th>Worker</th>
                <th>Host</th>
                <th>Status</th>
                <th>Queues</th>
                <th>Heartbeat</th>
                <th className="ta-right">Started</th>
              </tr>
            </thead>
            <tbody>
              {workers.map((w) => {
                const hb = heartbeatAge(w.last_heartbeat_at);
                return (
                  <tr key={w.id}>
                    <td>
                      <div className="cell-job">
                        <span className="cell-worker-icon"><Server size={13} /></span>
                        <span className="cell-job__id mono">{w.id.slice(0, 12)}</span>
                      </div>
                    </td>
                    <td className="cell-muted">{w.hostname}</td>
                    <td><Badge status={w.status} /></td>
                    <td>
                      <div className="chip-row">
                        {w.queue_ids?.map((qid: string) => (
                          <span key={qid} className="mono queue-chip">{qid.slice(0, 8)}</span>
                        ))}
                      </div>
                    </td>
                    <td>
                      <span className={`hb ${hb.stale && w.status === 'active' ? 'hb--stale' : ''}`}>
                        {hb.label}
                      </span>
                    </td>
                    <td className="cell-date ta-right">{fmtTime(w.started_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
