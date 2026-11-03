import { useEffect, useMemo, useState } from "react";
import Brief from "./views/Brief.jsx";
import Watch from "./views/Watch.jsx";
import Research from "./views/Research.jsx";
import { useData } from "./lib/data.js";
import { markVisit } from "./lib/store.js";
import { ago } from "./lib/fmt.js";

function useHash() {
  const [h, setH] = useState(window.location.hash || "#/brief");
  useEffect(() => {
    const f = () => setH(window.location.hash || "#/brief");
    window.addEventListener("hashchange", f);
    return () => window.removeEventListener("hashchange", f);
  }, []);
  return h;
}

const TABS = [
  { id: "brief", label: "Brief", icon: "M4 6h16M4 12h10M4 18h6" },
  { id: "watch", label: "Watch", icon: "M3 17l5-6 4 3 5-7 4 5" },
  { id: "research", label: "Research", icon: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4" },
];

function Footer({ meta }) {
  if (!meta) return null;
  const u = meta.usage || {};
  return (
    <footer className="app-foot fine">
      <p>Data refreshed {ago(meta.generated_at)}. Filings from BSE, prices from Yahoo Finance, fundamentals from company filings via screener.in.</p>
      {u.calls !== undefined ? (
        <p>Last refresh used {u.calls} model call{u.calls === 1 ? "" : "s"} ({u.cache_hits || 0} cached). On free tier: ₹0. At paid rates: about ${(u.usd_if_paid || 0).toFixed(3)}.</p>
      ) : null}
    </footer>
  );
}

export default function App() {
  const hash = useHash();
  const data = useData();
  const visit = useMemo(() => markVisit(), []);
  const parts = hash.replace(/^#\/?/, "").split("/");
  const tab = TABS.some((t) => t.id === parts[0]) ? parts[0] : "brief";
  const sym = tab === "research" ? decodeURIComponent(parts[1] || "") : "";
  const go = (h) => {
    window.location.hash = h;
    window.scrollTo({ top: 0 });
  };

  useEffect(() => {
    document.title = sym ? `FINN: ${sym}` : "FINN";
  }, [sym]);

  const ready = data.meta && data.filings && data.eod;

  return (
    <div className="app">
      <header className="top">
        <a href="#/brief" className="brand" aria-label="FINN home">
          <svg viewBox="0 0 64 64" width="22" height="22" aria-hidden="true"><rect width="64" height="64" rx="14" fill="currentColor" /><rect x="14" y="40" width="36" height="8" rx="2" fill="var(--mark)" /><rect x="14" y="28" width="24" height="6" rx="2" fill="var(--bg)" opacity=".85" /><rect x="14" y="18" width="14" height="5" rx="2" fill="var(--bg)" opacity=".5" /></svg>
          <span>FINN</span>
        </a>
        <span className="today">{new Date().toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" })}</span>
      </header>

      <main>
        {tab === "research" ? (
          <Research symbol={sym} data={ready ? data : null} go={go} />
        ) : data.loading ? (
          <p className="pending">Loading your portfolio…</p>
        ) : !ready ? (
          <div className="setup">
            <h1 className="page-title">No portfolio data yet</h1>
            <p>The daily run hasn't produced data for this deployment. Run <code>python -m pipeline.run</code> once and push, or trigger the "FINN daily run" workflow on GitHub.</p>
            <p>Research works without it: <a href="#/research">analyse any company</a>.</p>
          </div>
        ) : tab === "watch" ? (
          <Watch data={data} go={go} />
        ) : (
          <Brief data={data} visit={visit} go={go} />
        )}
        <Footer meta={data.meta} />
      </main>

      <nav className="tabs" aria-label="Main">
        {TABS.map((t) => (
          <a key={t.id} href={`#/${t.id}`} className={tab === t.id ? "on" : ""} aria-current={tab === t.id ? "page" : undefined}>
            <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d={t.icon} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
            <span>{t.label}</span>
          </a>
        ))}
      </nav>
    </div>
  );
}
