export default function Bars({ data }: { data: Record<string, number> }) {
  const rows = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...rows.map(([, n]) => n));
  if (rows.length === 0) return <p className="muted">Belum ada data.</p>;
  return (
    <div className="bars">
      {rows.map(([label, n]) => (
        <div className="bar-row" key={label}>
          <span className="bar-label">{label}</span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${(n / max) * 100}%` }} />
          </div>
          <span className="bar-value">{n}</span>
        </div>
      ))}
    </div>
  );
}