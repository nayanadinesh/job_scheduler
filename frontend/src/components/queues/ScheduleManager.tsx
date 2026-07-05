import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { createScheduledJob, deleteScheduledJob, listScheduledJobs } from '../../api';
import { Button } from '../ui/Button';

const CRON_PRESETS = [
  { label: 'Every minute', expr: '* * * * *' },
  { label: 'Hourly', expr: '0 * * * *' },
  { label: 'Daily midnight', expr: '0 0 * * *' },
  { label: 'Weekly (Mon)', expr: '0 0 * * 1' },
];

function fmt(s: string | null) {
  if (!s) return '—';
  return new Date(s).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

export function ScheduleManager({ queueId }: { queueId: string }) {
  const qc = useQueryClient();
  const [name, setName] = useState('');
  const [cronExpr, setCronExpr] = useState('0 * * * *');
  const [jobType, setJobType] = useState('simulation');
  const [error, setError] = useState('');

  const { data: schedules } = useQuery({
    queryKey: ['schedules', queueId],
    queryFn: () => listScheduledJobs(queueId),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ['schedules', queueId] });

  const createMut = useMutation({
    mutationFn: () => createScheduledJob(queueId, {
      name, cron_expr: cronExpr, job_type: jobType,
      job_payload: { durationMs: 300, failRate: 0 },
    }),
    onSuccess: () => { setName(''); setError(''); invalidate(); },
    onError: (e: unknown) => setError(
      String((e as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'Invalid cron expression'),
    ),
  });

  const deleteMut = useMutation({ mutationFn: deleteScheduledJob, onSuccess: invalidate });

  return (
    <div className="sched-mgr">
      {/* Existing schedules */}
      {schedules && schedules.length > 0 ? (
        <div className="sched-list">
          {schedules.map((s) => (
            <div key={s.id} className="sched-item">
              <div className="sched-item__main">
                <span className="sched-item__name">{s.name}</span>
                <span className="mono sched-item__cron">{s.cron_expr}</span>
              </div>
              <div className="sched-item__meta">
                <span className="sched-item__next">next {fmt(s.next_run_at)}</span>
                <button className="icon-btn icon-btn--danger" title="Delete schedule"
                  onClick={() => deleteMut.mutate(s.id)}>
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="sched-empty">No cron schedules yet. Add one below.</p>
      )}

      {/* Create form */}
      <div className="sched-form">
        <div className="sched-form__row">
          <label className="field">
            <span className="field__label">Name</span>
            <input className="field__input" value={name}
              onChange={(e) => setName(e.target.value)} placeholder="nightly-sync" />
          </label>
          <label className="field">
            <span className="field__label">Job type</span>
            <input className="field__input" value={jobType}
              onChange={(e) => setJobType(e.target.value)} placeholder="simulation" />
          </label>
        </div>

        <label className="field">
          <span className="field__label">Cron expression</span>
          <input className="field__input mono" value={cronExpr}
            onChange={(e) => setCronExpr(e.target.value)} placeholder="0 * * * *" />
        </label>

        <div className="cron-presets">
          {CRON_PRESETS.map((p) => (
            <button key={p.expr} className={`cron-chip ${cronExpr === p.expr ? 'cron-chip--active' : ''}`}
              onClick={() => setCronExpr(p.expr)}>
              {p.label}
            </button>
          ))}
        </div>

        {error && <div className="alert alert--error">{error}</div>}

        <Button size="sm" onClick={() => createMut.mutate()} disabled={!name || !jobType || createMut.isPending}>
          <Plus size={14} /> {createMut.isPending ? 'Adding…' : 'Add schedule'}
        </Button>
      </div>
    </div>
  );
}
