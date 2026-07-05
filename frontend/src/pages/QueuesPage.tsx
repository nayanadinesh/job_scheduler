import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarClock, FolderPlus, Pause, Play, Plus, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { Queue } from '../api';
import {
  createProject, createQueue, deleteQueue, listProjects, listQueues,
  pauseQueue, resumeQueue,
} from '../api';
import { PageHeader } from '../components/layout/PageHeader';
import { Button } from '../components/ui/Button';
import { Modal } from '../components/ui/Modal';
import { ScheduleManager } from '../components/queues/ScheduleManager';

export function QueuesPage() {
  const qc = useQueryClient();
  const [selectedProject, setSelectedProject] = useState('');
  const [showProject, setShowProject] = useState(false);
  const [showQueue, setShowQueue] = useState(false);
  const [cronQueue, setCronQueue] = useState<Queue | null>(null);

  const { data: projects } = useQuery({ queryKey: ['projects'], queryFn: listProjects });
  const { data: queues } = useQuery({
    queryKey: ['queues', selectedProject],
    queryFn: () => listQueues(selectedProject),
    enabled: !!selectedProject,
  });

  useEffect(() => {
    if (!selectedProject && projects?.length) setSelectedProject(projects[0].id);
  }, [projects, selectedProject]);

  const invalidateQueues = () => qc.invalidateQueries({ queryKey: ['queues', selectedProject] });

  const pauseMut = useMutation({ mutationFn: pauseQueue, onSuccess: invalidateQueues });
  const resumeMut = useMutation({ mutationFn: resumeQueue, onSuccess: invalidateQueues });
  const deleteMut = useMutation({ mutationFn: deleteQueue, onSuccess: invalidateQueues });

  return (
    <div className="page">
      <PageHeader
        title="Queues"
        subtitle="Provision and configure queues, retry policies and cron schedules"
        actions={
          <div className="header-actions">
            <Button variant="secondary" onClick={() => setShowProject(true)}>
              <FolderPlus size={15} /> New project
            </Button>
            <Button onClick={() => setShowQueue(true)} disabled={!selectedProject}>
              <Plus size={15} /> New queue
            </Button>
          </div>
        }
      />

      <div className="toolbar">
        <label className="field">
          <span className="field__label">Project</span>
          <select className="field__select" value={selectedProject}
            onChange={(e) => setSelectedProject(e.target.value)}>
            <option value="">Select project…</option>
            {projects?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
      </div>

      {!selectedProject ? (
        <div className="empty-state empty-state--panel">
          <div className="empty-state__icon"><FolderPlus size={26} /></div>
          <p className="empty-state__title">No project selected</p>
          <p className="empty-state__hint">Create a project to start provisioning queues.</p>
        </div>
      ) : queues && queues.length === 0 ? (
        <div className="empty-state empty-state--panel">
          <p className="empty-state__title">No queues in this project</p>
          <p className="empty-state__hint">Create your first queue to start accepting jobs.</p>
        </div>
      ) : (
        <div className="queue-admin-grid">
          {queues?.map((q) => (
            <div key={q.id} className="admin-card">
              <div className="admin-card__head">
                <div className="admin-card__title-row">
                  <span className="admin-card__name">{q.name}</span>
                  {q.is_paused
                    ? <span className="badge badge--amber"><span className="badge__dot" />paused</span>
                    : <span className="badge badge--green"><span className="badge__dot badge__dot--pulse" />active</span>}
                </div>
                <span className="admin-card__id mono">{q.id.slice(0, 8)}</span>
              </div>

              <div className="admin-card__config">
                <div className="config-item"><span className="config-item__k">Priority</span><span className="config-item__v mono">{q.priority}</span></div>
                <div className="config-item"><span className="config-item__k">Concurrency</span><span className="config-item__v mono">{q.concurrency_limit}</span></div>
                <div className="config-item"><span className="config-item__k">Strategy</span><span className="config-item__v">{q.retry_policy?.strategy ?? 'default'}</span></div>
                <div className="config-item"><span className="config-item__k">Max attempts</span><span className="config-item__v mono">{q.retry_policy?.max_attempts ?? 3}</span></div>
              </div>

              <div className="admin-card__actions">
                <button className="text-btn" onClick={() => setCronQueue(q)}>
                  <CalendarClock size={14} /> Schedules
                </button>
                <div className="admin-card__actions-right">
                  {q.is_paused ? (
                    <button className="icon-btn icon-btn--accent" title="Resume" onClick={() => resumeMut.mutate(q.id)}><Play size={14} /></button>
                  ) : (
                    <button className="icon-btn" title="Pause" onClick={() => pauseMut.mutate(q.id)}><Pause size={14} /></button>
                  )}
                  <button className="icon-btn icon-btn--danger" title="Delete queue"
                    onClick={() => { if (confirm(`Delete queue "${q.name}"? This removes all its jobs.`)) deleteMut.mutate(q.id); }}>
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <NewProjectModal open={showProject} onClose={() => setShowProject(false)}
        onCreated={(id) => { qc.invalidateQueries({ queryKey: ['projects'] }); setSelectedProject(id); }} />

      <NewQueueModal open={showQueue} projectId={selectedProject} onClose={() => setShowQueue(false)}
        onCreated={invalidateQueues} />

      <Modal open={!!cronQueue} onClose={() => setCronQueue(null)} title={`Schedules · ${cronQueue?.name ?? ''}`}>
        {cronQueue && <ScheduleManager queueId={cronQueue.id} />}
      </Modal>
    </div>
  );
}

/* ── New Project modal ──────────────────────────────────────────────── */
function NewProjectModal({ open, onClose, onCreated }: {
  open: boolean; onClose: () => void; onCreated: (id: string) => void;
}) {
  const [name, setName] = useState('');
  const mut = useMutation({
    mutationFn: () => createProject(name),
    onSuccess: (p) => { onCreated(p.id); setName(''); onClose(); },
  });

  return (
    <Modal open={open} onClose={onClose} title="New project"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={!name || mut.isPending}>
            {mut.isPending ? 'Creating…' : 'Create project'}
          </Button>
        </>
      }>
      <label className="field">
        <span className="field__label">Project name</span>
        <input className="field__input" value={name} autoFocus
          onChange={(e) => setName(e.target.value)} placeholder="production" />
      </label>
    </Modal>
  );
}

/* ── New Queue modal ────────────────────────────────────────────────── */
function NewQueueModal({ open, projectId, onClose, onCreated }: {
  open: boolean; projectId: string; onClose: () => void; onCreated: () => void;
}) {
  const [name, setName] = useState('');
  const [priority, setPriority] = useState('5');
  const [concurrency, setConcurrency] = useState('10');
  const [strategy, setStrategy] = useState('exponential');
  const [maxAttempts, setMaxAttempts] = useState('3');
  const [baseDelay, setBaseDelay] = useState('5');

  const mut = useMutation({
    mutationFn: () => createQueue(projectId, {
      name,
      priority: Number(priority),
      concurrency_limit: Number(concurrency),
      retry_policy: {
        strategy,
        base_delay_s: Number(baseDelay),
        max_attempts: Number(maxAttempts),
        max_delay_s: 3600,
      },
    }),
    onSuccess: () => { onCreated(); reset(); onClose(); },
  });

  const reset = () => { setName(''); setPriority('5'); setConcurrency('10'); setStrategy('exponential'); setMaxAttempts('3'); setBaseDelay('5'); };

  return (
    <Modal open={open} onClose={onClose} title="New queue"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mut.mutate()} disabled={!name || mut.isPending}>
            {mut.isPending ? 'Creating…' : 'Create queue'}
          </Button>
        </>
      }>
      <div className="form-stack">
        <label className="field">
          <span className="field__label">Queue name</span>
          <input className="field__input" value={name} autoFocus
            onChange={(e) => setName(e.target.value)} placeholder="default" />
        </label>
        <div className="form-grid">
          <label className="field">
            <span className="field__label">Priority (1–10)</span>
            <input className="field__input mono" type="number" min={1} max={10} value={priority}
              onChange={(e) => setPriority(e.target.value)} />
          </label>
          <label className="field">
            <span className="field__label">Concurrency</span>
            <input className="field__input mono" type="number" min={1} value={concurrency}
              onChange={(e) => setConcurrency(e.target.value)} />
          </label>
        </div>
        <div className="modal__divider">Retry policy</div>
        <label className="field">
          <span className="field__label">Backoff strategy</span>
          <select className="field__select" value={strategy} onChange={(e) => setStrategy(e.target.value)}>
            <option value="fixed">Fixed</option>
            <option value="linear">Linear</option>
            <option value="exponential">Exponential</option>
          </select>
        </label>
        <div className="form-grid">
          <label className="field">
            <span className="field__label">Max attempts</span>
            <input className="field__input mono" type="number" min={1} value={maxAttempts}
              onChange={(e) => setMaxAttempts(e.target.value)} />
          </label>
          <label className="field">
            <span className="field__label">Base delay (s)</span>
            <input className="field__input mono" type="number" min={1} value={baseDelay}
              onChange={(e) => setBaseDelay(e.target.value)} />
          </label>
        </div>
      </div>
    </Modal>
  );
}
