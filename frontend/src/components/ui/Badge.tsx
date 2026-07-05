import { clsx } from 'clsx';

const palette: Record<string, string> = {
  queued:    'badge--blue',
  running:   'badge--amber',
  claimed:   'badge--amber',
  completed: 'badge--green',
  failed:    'badge--red',
  dead:      'badge--red',
  scheduled: 'badge--violet',
  cancelled: 'badge--slate',
  active:    'badge--green',
  stopped:   'badge--slate',
};

interface BadgeProps {
  status: string;
  className?: string;
  pulse?: boolean;
}

export function Badge({ status, className, pulse }: BadgeProps) {
  const tone = palette[status] ?? 'badge--slate';
  const shouldPulse = pulse ?? (status === 'running' || status === 'active' || status === 'claimed');
  return (
    <span className={clsx('badge', tone, className)}>
      <span className={clsx('badge__dot', shouldPulse && 'badge__dot--pulse')} />
      {status}
    </span>
  );
}
