const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const inr1 = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 });

export function cr(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  const a = Math.abs(v);
  const sign = v < 0 ? "−" : "";
  if (a >= 100000) return `${sign}₹${inr1.format(a / 100000)}L cr`;
  if (a >= 100) return `${sign}₹${inr.format(a)} cr`;
  return `${sign}₹${inr1.format(a)} cr`;
}

export function price(v) {
  if (v === null || v === undefined) return "–";
  return `₹${inr1.format(v)}`;
}

export function pct(v, digits = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  const r = Number(Math.abs(v).toFixed(digits));
  const s = r === 0 ? "" : v > 0 ? "+" : "−";
  return `${s}${Math.abs(v).toFixed(digits)}%`;
}

export function plain(v, digits = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  return Number(v).toFixed(digits);
}

export function tone(v) {
  if (v === null || v === undefined || Math.abs(v) < 0.05) return "";
  return v > 0 ? "up" : v < 0 ? "down" : "";
}

export function ago(iso, now = Date.now()) {
  const t = new Date(iso).getTime();
  const m = Math.round((now - t) / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  return d === 1 ? "yesterday" : `${d}d ago`;
}

export function clock(iso) {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata" });
}

export function ymd(s) {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-IN", { day: "numeric", month: "short", timeZone: "UTC" });
}

export function day(iso) {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" });
}
