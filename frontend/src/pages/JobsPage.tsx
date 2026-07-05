import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import type { Job } from '../api';
import { listJobs, listProjects, listQueues } from '../api';
import { JobDetailDrawer } from '../components/jobs/JobDetailDrawer';
import { JobTable } from '../components/jobs/JobTable';
import { PageHeader } from '../components/layout/PageHeader';

type Status = 'all' | 'queued' | 'running' | 'completed' | 'failed' | 'dead' | 'scheduled' | 'cancelled';

const STATUSES: Status[] = ['all', 'queued', 'running', 'completed', 'failed', 'dead', 'scheduled', 'cancelled'];

export function JobsPage() {
  const [selectedProject, setSelectedProject] = useState('');
  const [selectedQueue, setSelectedQueue] = useState('');
  const [statusFilter, setStatusFilter] = useState<Status>('all');
  const [selected, setSelected] = useState<Job | null>(null);

  const { data: projects } = useQuery({ queryKey: ['projects'], queryFn: listProjects });

  const { data: queues } = useQuery({
    queryKey: ['queues', selectedProject],
    queryFn: () => listQueues(selectedProject),
    enabled: !!selectedProject,
  });

  const { data: jobs, refetch } = useQuery({
    queryKey: ['jobs', selectedQueue, statusFilter],
    queryFn: () => listJobs(selectedQueue, statusFilter === 'all' ? undefined : statusFilter),
    enabled: !!selectedQueue,
    refetchInterval: 3000,
  });

  useEffect(() => {
    if (!selectedProject && projects?.length) setSelectedProject(projects[0].id);
  }, [projects, selectedProject]);
  useEffect(() => {
    if (selectedProject && !selectedQueue && queues?.length) setSelectedQueue(queues[0].id);
  }, [queues, selectedProject, selectedQueue]);

  // Keep the open drawer's job in sync with fresh polling data.
  useEffect(() => {
    if (selected && jobs) {
      const fresh = jobs.find((j) => j.id === selected.id);
      if (fresh && fresh.status !== selected.status) setSelected(fresh);
    }
  }, [jobs, selected]);

  const deadCount = jobs?.filter((j) => j.status === 'dead').length ?? 0;

  return (
    <div className="page">
      <PageHeader
        title="Job Explorer"
        subtitle="Browse, inspect, cancel and retry jobs · click a row for logs & executions"
        live={!!selectedQueue}
        liveLabel="Live · 3s"
      />

      <div className="toolbar">
        <div className="toolbar__selects">
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

        <div className="segmented">
          {STATUSES.map((s) => (
            <button
              key={s}
              className={`segmented__item ${statusFilter === s ? 'segmented__item--active' : ''}`}
              onClick={() => setStatusFilter(s)}
            >
              {s}
              {s === 'dead' && deadCount > 0 && <span className="segmented__badge">{deadCount}</span>}
            </button>
          ))}
        </div>
      </div>

      {!selectedQueue ? (
        <div className="empty-state empty-state--panel">
          <p className="empty-state__title">Select a queue</p>
          <p className="empty-state__hint">Pick a project and queue above to browse its jobs.</p>
        </div>
      ) : (
        <JobTable
          jobs={jobs ?? []}
          onRefresh={refetch}
          onSelect={setSelected}
          selectedId={selected?.id}
        />
      )}

      <JobDetailDrawer job={selected} onClose={() => setSelected(null)} onMutate={refetch} />
    </div>
  );
}
