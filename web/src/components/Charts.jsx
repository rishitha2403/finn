import { useState } from "react";

export function Spark({ values, w = 72, h = 22, up }) {
  const vs = values.filter((v) => v !== null && v !== undefined);
  if (vs.length < 2) return <svg width={w} height={h} />;
  const min = Math.min(...vs);
  const max = Math.max(...vs);
  const sx = (i) => (i / (vs.length - 1)) * (w - 4) + 2;
  const sy = (v) => h - 3 - ((v - min) / (max - min || 1)) * (h - 6);
  const d = vs.map((v, i) => `${i ? "L" : "M"}${sx(i).toFixed(1)},${sy(v).toFixed(1)}`).join("");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true" className="spark">
      <path d={d} fill="none" stroke={up ? "var(--up)" : "var(--down)"} strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={sx(vs.length - 1)} cy={sy(vs[vs.length - 1])} r="2.2" fill={up ? "var(--up)" : "var(--down)"} />
    </svg>
  );
}

function Tip({ text }) {
  return <div className="tip" role="status">{text}</div>;
}

export function Bars({ data, fmt, label, height = 120 }) {
  const [hot, setHot] = useState(null);
  const vals = data.map((d) => d.value).filter((v) => v !== null && v !== undefined);
  if (!vals.length) return null;
  const max = Math.max(0, ...vals);
  const min = Math.min(0, ...vals);
  const span = max - min || 1;
  const n = data.length;
  const W = 320;
  const gap = 6;
  const bw = (W - gap * (n - 1)) / n;
  const zero = height - ((0 - min) / span) * height;
  const shown = hot === null ? n - 1 : hot;
  return (
    <figure className="chart" aria-label={label}>
      <Tip text={`${data[shown].label}: ${fmt(data[shown].value)}`} />
      <svg viewBox={`0 0 ${W} ${height + 18}`} width="100%" role="img" aria-label={label}>
        <line x1="0" x2={W} y1={zero} y2={zero} className="axis" />
        {data.map((d, i) => {
          if (d.value === null || d.value === undefined) return null;
          const x = i * (bw + gap);
          const y = d.value >= 0 ? zero - (d.value / span) * height : zero;
          const hgt = Math.max(1.5, (Math.abs(d.value) / span) * height);
          const r = Math.min(4, bw / 2, hgt / 2);
          const pos = d.value >= 0;
          const path = pos
            ? `M${x},${y + hgt} V${y + r} Q${x},${y} ${x + r},${y} H${x + bw - r} Q${x + bw},${y} ${x + bw},${y + r} V${y + hgt} Z`
            : `M${x},${y} V${y + hgt - r} Q${x},${y + hgt} ${x + r},${y + hgt} H${x + bw - r} Q${x + bw},${y + hgt} ${x + bw},${y + hgt - r} V${y} Z`;
          return (
            <g key={d.label} onMouseEnter={() => setHot(i)} onClick={() => setHot(i)} onMouseLeave={() => setHot(null)}>
              <rect x={x - gap / 2} y="0" width={bw + gap} height={height} fill="transparent" />
              <path d={path} className={`bar ${i === shown ? "on" : ""} ${d.value < 0 ? "neg" : ""}`} />
            </g>
          );
        })}
        {data.map((d, i) =>
          i === 0 || i === n - 1 || n <= 6 ? (
            <text key={d.label} x={i * (bw + gap) + bw / 2} y={height + 14} className="tick" textAnchor="middle">{d.label}</text>
          ) : null
        )}
      </svg>
    </figure>
  );
}

export function PairBars({ data, a, b, fmt, label, height = 120 }) {
  const [hot, setHot] = useState(null);
  const vals = data.flatMap((d) => [d[a.key], d[b.key]]).filter((v) => v !== null && v !== undefined);
  if (!vals.length) return null;
  const max = Math.max(0, ...vals);
  const min = Math.min(0, ...vals);
  const span = max - min || 1;
  const n = data.length;
  const W = 320;
  const gap = 12;
  const gw = (W - gap * (n - 1)) / n;
  const bw = (gw - 2) / 2;
  const zero = height - ((0 - min) / span) * height;
  const shown = hot === null ? n - 1 : hot;
  const bar = (x, v, cls) => {
    if (v === null || v === undefined) return null;
    const y = v >= 0 ? zero - (v / span) * height : zero;
    const h = Math.max(1.5, (Math.abs(v) / span) * height);
    return <rect x={x} y={y} width={bw} height={h} rx="2" className={cls} />;
  };
  return (
    <figure className="chart" aria-label={label}>
      <div className="legend">
        <span><i className="sw s1" />{a.name}</span>
        <span><i className="sw s2" />{b.name}</span>
      </div>
      <Tip text={`${data[shown].label}: ${a.name} ${fmt(data[shown][a.key])}, ${b.name} ${fmt(data[shown][b.key])}`} />
      <svg viewBox={`0 0 ${W} ${height + 18}`} width="100%" role="img" aria-label={label}>
        <line x1="0" x2={W} y1={zero} y2={zero} className="axis" />
        {data.map((d, i) => {
          const x = i * (gw + gap);
          return (
            <g key={d.label} onMouseEnter={() => setHot(i)} onClick={() => setHot(i)} onMouseLeave={() => setHot(null)} className={i === shown ? "grp on" : "grp"}>
              <rect x={x - gap / 2} y="0" width={gw + gap} height={height} fill="transparent" />
              {bar(x, d[a.key], "s1")}
              {bar(x + bw + 2, d[b.key], "s2")}
            </g>
          );
        })}
        {data.map((d, i) => (
          <text key={d.label} x={i * (gw + gap) + gw / 2} y={height + 14} className="tick" textAnchor="middle">{d.label}</text>
        ))}
      </svg>
    </figure>
  );
}

export function Line({ data, fmt, label, height = 70 }) {
  const [hot, setHot] = useState(null);
  const pts = data.filter((d) => d.value !== null && d.value !== undefined);
  if (pts.length < 2) return null;
  const W = 320;
  const min = Math.min(...pts.map((p) => p.value));
  const max = Math.max(...pts.map((p) => p.value));
  const pad = (max - min) * 0.15 || 1;
  const lo = min - pad;
  const hi = max + pad;
  const sx = (i) => (i / (pts.length - 1)) * (W - 16) + 8;
  const sy = (v) => height - ((v - lo) / (hi - lo)) * height;
  const d = pts.map((p, i) => `${i ? "L" : "M"}${sx(i)},${sy(p.value)}`).join("");
  const shown = hot === null ? pts.length - 1 : hot;
  return (
    <figure className="chart" aria-label={label}>
      <Tip text={`${pts[shown].label}: ${fmt(pts[shown].value)}`} />
      <svg viewBox={`0 0 ${W} ${height + 18}`} width="100%" role="img" aria-label={label}>
        <path d={d} className="line" />
        {pts.map((p, i) => (
          <g key={p.label} onMouseEnter={() => setHot(i)} onClick={() => setHot(i)} onMouseLeave={() => setHot(null)}>
            <rect x={sx(i) - 14} y="0" width="28" height={height} fill="transparent" />
            <circle cx={sx(i)} cy={sy(p.value)} r={i === shown ? 4.5 : 3} className="dot" />
          </g>
        ))}
        <text x={sx(0)} y={height + 14} className="tick" textAnchor="start">{pts[0].label}</text>
        <text x={sx(pts.length - 1)} y={height + 14} className="tick" textAnchor="end">{pts[pts.length - 1].label}</text>
      </svg>
    </figure>
  );
}
