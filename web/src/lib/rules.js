export const DEFAULT_RULES = { price_pct: 4, volume_x: 2, lookback: 20 };

export function scan(eod, rules, sinceDate = null) {
  const r = { ...DEFAULT_RULES, ...rules };
  const out = [];
  for (const [sym, rows] of Object.entries(eod || {})) {
    for (let i = r.lookback + 1; i < rows.length; i++) {
      const [d, c, v] = rows[i];
      if (sinceDate && d < sinceDate) continue;
      const pc = rows[i - 1][1];
      if (!pc) continue;
      const ret = (c / pc - 1) * 100;
      let sum = 0;
      for (let j = i - r.lookback; j < i; j++) sum += rows[j][2];
      const avg = sum / r.lookback;
      const vx = avg ? v / avg : null;
      const why = [];
      if (Math.abs(ret) >= r.price_pct) why.push("price");
      if (vx !== null && vx >= r.volume_x) why.push("volume");
      if (why.length) out.push({ symbol: sym, date: d, close: c, ret, vx, why });
    }
  }
  out.sort((a, b) => (a.date === b.date ? Math.abs(b.ret) - Math.abs(a.ret) : a.date < b.date ? 1 : -1));
  return out;
}

export function sessions(eod, n) {
  const any = Object.values(eod || {})[0] || [];
  return any.slice(-n).map((r) => r[0]);
}

export function rank(item, watched) {
  let s = item.score;
  if (watched.includes(item.category)) s += 8;
  else if (s < 85) s -= 10;
  return s;
}

export function tierOf(s) {
  if (s >= 70) return "act";
  if (s >= 40) return "know";
  return "routine";
}
