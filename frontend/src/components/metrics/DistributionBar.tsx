interface Segment {
  key: string;
  value: number;
  color: string;
}

interface DistributionBarProps {
  segments: Segment[];
  height?: number;
}

/** A single stacked bar showing the proportion of each status. */
export function DistributionBar({ segments, height = 8 }: DistributionBarProps) {
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  const visible = segments.filter((s) => s.value > 0);

  return (
    <div className="dist-bar" style={{ height }}>
      {total === 0 ? (
        <div className="dist-bar__empty" />
      ) : (
        visible.map((s) => (
          <div
            key={s.key}
            className="dist-bar__seg"
            style={{
              width: `${(s.value / total) * 100}%`,
              background: s.color,
            }}
            title={`${s.key}: ${s.value}`}
          />
        ))
      )}
    </div>
  );
}
