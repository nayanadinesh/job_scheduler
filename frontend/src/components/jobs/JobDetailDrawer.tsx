import { useQuery } from '@tanstack/react-query';
import { Ban, RotateCw, X } from 'lucide-react';
import type { Job } from '../../api';
import { cancelJob, getJobExecutions, getJobLogs, retryJob } from '../../api';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

interface JobDetailDrawerProps {
  job: Job | null;
  onClose: () => void;
  onMutate: () => void;
}

function fmt(s: string | null) {
  if (!s) return '—';
  return new Date(s).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

const LOG_LEVEL_CLASS: Record<string, string> = {
  info: 'log-line--info', warning: 'log-line--warn', warn: 'log-line--warn',
  error: 'log-line--error', debug: 'log-line--debug',
};

export function JobDetailDrawer({ job, onClose, onMutate }: JobDetailDrawerProps) {
  const open = !!job;

  const { data: executions } = useQuery({
    queryKey: ['executions', job?.id],
    queryFn: () => getJobExecutions(job!.id),
    enabled: open,
    refetchInterval: open ? 3000 : false,
  });

  const { data: logs } = useQuery({
    queryKey: ['logs', job?.id],
    queryFn: () => getJobLogs(job!.id),
    enabled: open,
    refetchInterval: open ? 3000 : false,
  });

  const canCancel = job && (job.status === 'queued' || job.status === 'scheduled');
  const canRetry = job && job.status === 'dead';

  const handleCancel = async () => {
    if (!job) return;
    try { await cancelJob(job.id); onMutate(); } catch { /* terminal */ }
  };
  const handleRetry = async () => {
    if (!job) return;
    try { await retryJob(job.id); onMutate(); } catch { /* ignore */ }
  };

  return (
    <>
      <div className={`drawer-scrim ${open ? 'drawer-scrim--open' : ''}`} onClick={onClose} />
      <aside className={`drawer ${open ? 'drawer--open' : ''}`}>
        {job && (
          <>
            <header className="drawer__head">
              <div className="drawer__head-main">
                <div className="drawer__title-row">
                  <h2 className="drawer__title">{job.type}</h2>
                  <Badge status={job.status} />
                </div>
                <span className="drawer__id mono">{job.id}</span>
              </div>
              <button className="icon-btn" onClick={onClose} title="Close"><X size={16} /></button>
            </header>

            <div className="drawer__body">
              {/* Meta grid */}
              <section className="drawer__section">
                <div className="meta-grid">
                  <div className="meta-item"><span className="meta-item__k">Priority</span><span className="meta-item__v mono">{job.priority}</span></div>
                  <div className="meta-item"><span className="meta-item__k">Attempts</span><span className="meta-item__v mono">{job.attempts}/{job.max_attempts}</span></div>
                  <div className="meta-item"><span className="meta-item__k">Run at</span><span className="meta-item__v">{fmt(job.run_at)}</span></div>
                  <div className="meta-item"><span className="meta-item__k">Created</span><span className="meta-item__v">{fmt(job.created_at)}</span></div>
                  <div className="meta-item"><span className="meta-item__k">Worker</span><span className="meta-item__v mono">{job.worker_id ? job.worker_id.slice(0, 12) : '—'}</span></div>
                  <div className="meta-item"><span className="meta-item__k">Dedup key</span><span className="meta-item__v mono">{job.dedup_key ?? '—'}</span></div>
                </div>
              </section>

              {/* Payload */}
              <section className="drawer__section">
                <h3 className="drawer__section-title">Payload</h3>
                <pre className="code-block mono">{JSON.stringify(job.payload ?? {}, null, 2)}</pre>
              </section>

              {/* Executions */}
              <section className="drawer__section">
                <h3 className="drawer__section-title">
                  Executions <span className="drawer__count">{executions?.length ?? 0}</span>
                </h3>
                {!executions?.length ? (
                  <p className="drawer__empty">No executions yet.</p>
                ) : (
                  <div className="exec-timeline">
                    {executions.map((e) => (
                      <div key={e.id} className="exec-item">
                        <div className="exec-item__marker">
                          <span className={`exec-dot exec-dot--${e.status}`} />
                        </div>
                        <div className="exec-item__body">
                          <div className="exec-item__row">
                            <span className="exec-item__attempt">Attempt #{e.attempt_no}</span>
                            <Badge status={e.status} />
                          </div>
                          <div className="exec-item__meta">
                            {fmt(e.started_at)}
                            {e.duration_ms != null && <> · <span className="mono">{e.duration_ms}ms</span></>}
                            {e.worker_id && <> · <span className="mono">{e.worker_id.slice(0, 8)}</span></>}
                          </div>
                          {e.error && <div className="exec-item__error mono">{e.error}</div>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Logs */}
              <section className="drawer__section">
                <h3 className="drawer__section-title">
                  Logs <span className="drawer__count">{logs?.length ?? 0}</span>
                </h3>
                {!logs?.length ? (
                  <p className="drawer__empty">No logs emitted.</p>
                ) : (
                  <div className="log-console">
                    {logs.map((l) => (
                      <div key={l.id} className={`log-line ${LOG_LEVEL_CLASS[l.level.toLowerCase()] ?? ''}`}>
                        <span className="log-line__ts mono">{new Date(l.ts).toLocaleTimeString()}</span>
                        <span className="log-line__lvl">{l.level}</span>
                        <span className="log-line__msg">{l.message}</span>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>

            {(canCancel || canRetry) && (
              <footer className="drawer__foot">
                {canCancel && (
                  <Button variant="danger" onClick={handleCancel}><Ban size={14} /> Cancel job</Button>
                )}
                {canRetry && (
                  <Button variant="primary" onClick={handleRetry}><RotateCw size={14} /> Retry job</Button>
                )}
              </footer>
            )}
          </>
        )}
      </aside>
    </>
  );
}
