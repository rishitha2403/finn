import { useEffect, useState } from "react";

const cache = new Map();

export async function getJSON(url) {
  if (cache.has(url)) return cache.get(url);
  const p = fetch(url, { cache: "no-cache" }).then(async (r) => {
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      const e = new Error(body.error || `${r.status} from ${url}`);
      e.status = r.status;
      throw e;
    }
    return r.json();
  });
  cache.set(url, p);
  p.catch(() => cache.delete(url));
  return p;
}

export function useData() {
  const [state, setState] = useState({ loading: true });
  useEffect(() => {
    Promise.all([
      getJSON("/data/meta.json"),
      getJSON("/data/filings.json"),
      getJSON("/data/eod.json"),
    ])
      .then(([meta, filings, eod]) => setState({ meta, filings, eod }))
      .catch((e) => setState({ error: e.message }));
  }, []);
  return state;
}

export async function research(symbol, stage, body) {
  const url = `/api/research?symbol=${encodeURIComponent(symbol)}&stage=${stage}`;
  const r = await fetch(url, body ? {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  } : undefined);
  const js = await r.json().catch(() => ({ error: `Server returned ${r.status}` }));
  if (!r.ok) throw new Error(js.error || `Server returned ${r.status}`);
  return js;
}
