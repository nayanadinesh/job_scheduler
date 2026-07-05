import { useMutation, useQuery } from '@tanstack/react-query';
import { CheckCircle2, Send } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import type { Schedule } from '../api';
import { listProjects, listQueues, submitJob } from '../api';
import { PageHeader } from '../components/layout/PageHeader';
import { Button } from '../components/ui/Button';

type Mode = 'simple' | 'advanced';
type ScheduleKind = 'immediate' | 'delay' | 'scheduled' | 'batch';

const SCHEDULE_KINDS: { key: ScheduleKind; label: string }[] = [
  { key: 'immediate', label: 'Immediate' },
  { key: 'delay', label: 'Delayed' },
  { key: 'scheduled', label: 'Scheduled' },
  { key: 'batch', label: 'Batch' },
];

/** Format now+1h as a datetime-local value (YYYY-MM-DDTHH:mm). */
function defaultRunAt(): string {
  const d = new Date(Date.now() + 3_600_000);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function SubmitJobPage() {
  const [selectedProject, setSelectedProject] = useState('');
  const [selectedQueue, setSelectedQueue] = useState('');
  const [jobType, setJobType] = useState('simulation');
  const [priority, setPriority] = useState('5');
  const [scheduleKind, setScheduleKind] = useState<ScheduleKind>('immediate');
  const [delayS, setDelayS] = useState('30');
  const [runAt, setRunAt] = useState(defaultRunAt);
  const [batchCount, setBatchCount] = useState('10');
  const [dedupKey, setDedupKey] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // Simple mode fields (simulation payload)
  const [mode, setMode] = useState<Mode>('simple');
  const [durationMs, setDurationMs] = useState('500');
  const [failRate, setFailRate] = useState('0.1');
  // Advanced mode: raw JSON payload
  const [rawPayload, setRawPayload] = useState('{\n  "durationMs": 500,\n  "failRate": 0.1\n}');

  const { data: projects } = useQuery({ queryKey: ['projects'], queryFn: listProjects });
  const { data: queues } = useQuery({
    queryKey: ['queues', selectedProject],
    queryFn: () => listQueues(selectedProject),
    enabled: !!selectedProject,
  });

  useEffect(() => {
    if (!selectedProject && projects?.length) setSelectedProject(projects[0].id);
  }, [projects, selectedProject]);
  useEffect(() => {
    if (selectedProject && !selectedQueue && queues?.length) setSelectedQueue(queues[0].id);
  }, [queues, selectedProject, selectedQueue]);

  const payloadError = useMemo(() => {
    if (mode === 'simple') return null;
    try { JSON.parse(rawPayload); return null; } catch { return 'Payload must be valid JSON'; }
  }, [mode, rawPayload]);

  const buildSchedule = (): Schedule => {
    switch (scheduleKind) {
      case 'delay': return { kind: 'delay', delay_s: Number(delayS) };
      case 'scheduled': return { kind: 'scheduled', run_at: new Date(runAt).toISOString() };
      case 'batch': return { kind: 'batch', count: Number(batchCount) };
      default: return { kind: 'immediate' };
    }
  };

  const mutation = useMutation({
    mutationFn: () => {
      const payload = mode === 'simple'
        ? { durationMs: Number(durationMs), failRate: Number(failRate) }
        : JSON.parse(rawPayload);
      return submitJob(selectedQueue, {
        type: jobType,
        payload,
        priority: Number(priority),
        schedule: buildSchedule(),
        ...(dedupKey ? { dedup_key: dedupKey } : {}),
      });
    },
    onSuccess: (result) => {
      const n = Array.isArray(result) ? result.length : 1;
      setSuccessMsg(n > 1
        ? `${n} jobs submitted — the worker fleet will pick them up shortly.`
        : 'Job submitted — the worker will pick it up shortly.');
      setDedupKey('');
      setTimeout(() => setSuccessMsg(''), 3500);
    },
  });

  const canSubmit = !!selectedQueue && !!jobType && !payloadError && !mutation.isPending;

  return (
    <div className="page">
      <PageHeader title="Submit Job" subtitle="Enqueue a job — immediate or delayed — with full control" />

      <div className="submit-layout">
        <div className="panel panel--pad submit-form">
          <div className="form-grid">
            <label className="field">
              <span className="field__label">Project</span>
              <select className="field__select" value={selectedProject}
                onChange={(e) => { setSelectedProject(e.target.value); setSelectedQueue(''); }}>
                <option value="">Select project…</option>
                {projects?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </label>
            <label className="field">
              <span className="field__label">Queue</span>
              <select className="field__select" value={selectedQueue}
                onChange={(e) => setSelectedQueue(e.target.value)} disabled={!selectedProject}>
                <option value="">Select queue…</option>
                {queues?.map((q) => <option key={q.id} value={q.id}>{q.name}</option>)}
              </select>
            </label>
          </div>

          <div className="form-grid">
            <label className="field">
              <span className="field__label">Job type</span>
              <input className="field__input" value={jobType}
                onChange={(e) => setJobType(e.target.value)} placeholder="simulation" />
            </label>
            <label className="field">
              <span className="field__label">Priority (1–10)</span>
              <input className="field__input mono" type="number" min={1} max={10} value={priority}
                onChange={(e) => setPriority(e.target.value)} />
            </label>
          </div>

          {/* Schedule */}
          <div className="field">
            <span className="field__label">Schedule</span>
            <div className="schedule-row">
              <div className="segmented">
                {SCHEDULE_KINDS.map(({ key, label }) => (
                  <button key={key}
                    className={`segmented__item ${scheduleKind === key ? 'segmented__item--active' : ''}`}
                    onClick={() => setScheduleKind(key)}>{label}</button>
                ))}
              </div>
              {scheduleKind === 'delay' && (
                <div className="delay-input">
                  <input className="field__input mono" type="number" min={1} value={delayS}
                    onChange={(e) => setDelayS(e.target.value)} />
                  <span className="delay-input__unit">seconds</span>
                </div>
              )}
              {scheduleKind === 'scheduled' && (
                <input className="field__input" type="datetime-local" value={runAt}
                  onChange={(e) => setRunAt(e.target.value)} style={{ width: 'auto' }} />
              )}
              {scheduleKind === 'batch' && (
                <div className="delay-input">
                  <input className="field__input mono" type="number" min={2} max={1000} value={batchCount}
                    onChange={(e) => setBatchCount(e.target.value)} />
                  <span className="delay-input__unit">jobs</span>
                </div>
              )}
            </div>
            <span className="field__hint">
              {scheduleKind === 'immediate' && 'Claimable right away.'}
              {scheduleKind === 'delay' && 'Becomes claimable after the delay elapses.'}
              {scheduleKind === 'scheduled' && 'Runs at the chosen absolute time.'}
              {scheduleKind === 'batch' && 'Fans out N identical jobs in one request.'}
            </span>
          </div>

          {/* Payload */}
          <div className="field">
            <div className="field__label-row">
              <span className="field__label">Payload</span>
              <div className="segmented segmented--sm">
                <button className={`segmented__item ${mode === 'simple' ? 'segmented__item--active' : ''}`}
                  onClick={() => setMode('simple')}>Simulation</button>
                <button className={`segmented__item ${mode === 'advanced' ? 'segmented__item--active' : ''}`}
                  onClick={() => setMode('advanced')}>Raw JSON</button>
              </div>
            </div>

            {mode === 'simple' ? (
              <div className="form-grid">
                <label className="field">
                  <span className="field__sublabel">Duration (ms)</span>
                  <input className="field__input mono" type="number" min={1} value={durationMs}
                    onChange={(e) => setDurationMs(e.target.value)} />
                </label>
                <label className="field">
                  <span className="field__sublabel">Fail rate (0–1)</span>
                  <input className="field__input mono" type="number" min={0} max={1} step={0.05} value={failRate}
                    onChange={(e) => setFailRate(e.target.value)} />
                </label>
              </div>
            ) : (
              <textarea className="field__textarea mono" rows={6} value={rawPayload}
                onChange={(e) => setRawPayload(e.target.value)} spellCheck={false} />
            )}
            {payloadError && <div className="field__error">{payloadError}</div>}
          </div>

          {/* Dedup */}
          <label className="field">
            <span className="field__label">Dedup key <span className="field__optional">optional</span></span>
            <input className="field__input mono" value={dedupKey}
              onChange={(e) => setDedupKey(e.target.value)} placeholder="idempotency-key-123" />
          </label>

          {mutation.isError && (
            <div className="alert alert--error">
              {String((mutation.error as { response?: { data?: { message?: string } } })
                .response?.data?.message ?? 'Submission failed')}
            </div>
          )}
          {successMsg && (
            <div className="alert alert--success">
              <CheckCircle2 size={15} /> {successMsg}
            </div>
          )}

          <Button size="lg" onClick={() => mutation.mutate()} disabled={!canSubmit} className="submit-btn">
            <Send size={15} />
            {mutation.isPending ? 'Submitting…' : 'Submit job'}
          </Button>
        </div>

        <aside className="submit-aside">
          <h3 className="submit-aside__title">Reference</h3>
          <ul className="submit-aside__list">
            <li><b>Immediate</b> runs at once · <b>Delayed</b> waits N seconds · <b>Scheduled</b> runs at an absolute time · <b>Batch</b> fans out N jobs.</li>
            <li><b>Simulation</b> payload: <b>duration</b> is work time, <b>fail rate</b> (0–1) the failure probability that triggers retries.</li>
            <li><b>Raw JSON</b> lets you send any payload shape for custom job types.</li>
            <li><b>Dedup key</b> makes submission idempotent — a duplicate key in the same queue returns <code className="inline-code">409</code> (batch keys are suffixed per index).</li>
            <li><b>Priority</b> (1–10) — higher is claimed first; exhausted retries land in the dead-letter queue.</li>
          </ul>
        </aside>
      </div>
    </div>
  );
}
