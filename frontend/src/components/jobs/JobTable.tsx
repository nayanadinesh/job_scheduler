import { Ban, RotateCw } from 'lucide-react';
import type { Job } from '../../api';
import { cancelJob, retryJob } from '../../api';
import { Badge } from '../ui/Badge';

interface JobTableProps {
  jobs: Job[];
  onRefresh: () => void;
  onSelect: (job: Job) => void;
  selectedId?: string;
}

function fmtDate(s: string) {
  return new Date(s).toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

export function JobTable({ jobs, onRefresh, onSelect, selectedId }: JobTableProps) {
  const handleCancel = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    try { await cancelJob(id); onRefresh(); } catch { /* already terminal */ }
  };
  const handleRetry = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    try { await retryJob(id); onRefresh(); } catch { /* ignore */ }
  };

  if (!jobs.length) {
    return (
      <div className="empty-state empty-state--panel">
        <p className="empty-state__title">No jobs found</p>
        <p className="empty-state__hint">Adjust the filter or submit a new job.</p>
      </div>
    );
  }

  return (
    <div className="panel">
      <table className="data-table data-table--clickable">
        <thead>
          <tr>
            <th>Job</th>
            <th>Status</th>
            <th className="ta-center">Priority</th>
            <th className="ta-center">Attempts</th>
            <th>Run at</th>
            <th>Created</th>
            <th className="ta-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => {
            const canCancel = job.status === 'queued' || job.status === 'scheduled';
            const canRetry = job.status === 'dead';
            return (
              <tr
                key={job.id}
                onClick={() => onSelect(job)}
                className={selectedId === job.id ? 'row--selected' : ''}
              >
                <td>
                  <div className="cell-job">
                    <span className="cell-job__type">{job.type}</span>
                    <span className="cell-job__id mono">{job.id.slice(0, 8)}</span>
                  </div>
                </td>
                <td><Badge status={job.status} /></td>
                <td className="ta-center"><span className="prio-pill">{job.priority}</span></td>
                <td className="ta-center">
                  <span className="mono cell-attempts">
                    {job.attempts}<span className="cell-attempts__max">/{job.max_attempts}</span>
                  </span>
                </td>
                <td className="cell-date">{job.run_at ? fmtDate(job.run_at) : '—'}</td>
                <td className="cell-date">{fmtDate(job.created_at)}</td>
                <td className="ta-right">
                  <div className="cell-actions">
                    {canCancel && (
                      <button className="icon-btn icon-btn--danger" onClick={(e) => handleCancel(e, job.id)} title="Cancel job">
                        <Ban size={14} />
                      </button>
                    )}
                    {canRetry && (
                      <button className="icon-btn icon-btn--accent" onClick={(e) => handleRetry(e, job.id)} title="Retry job">
                        <RotateCw size={14} />
                      </button>
                    )}
                    {!canCancel && !canRetry && <span className="cell-actions__none">—</span>}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
