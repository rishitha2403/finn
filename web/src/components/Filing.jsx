import { useState } from "react";
import { cr, pct, tone, clock, ago } from "../lib/fmt.js";

function Delta({ v }) {
  return <span className={`num ${tone(v)}`}>{pct(v)}</span>;
}

export function ResultsTable({ r }) {
  return (
    <div className="results">
      <table>
        <thead>
          <tr>
            <th scope="col">{r.period || "Latest quarter"}</th>
            <th scope="col" className="r">Value</th>
            <th scope="col" className="r">QoQ</th>
            <th scope="col" className="r">YoY</th>
          </tr>
        </thead>
        <tbody>
          {r.rows.map((row) => (
            <tr key={row.key}>
              <th scope="row">{row.name}</th>
              <td className="r num">{row.cur === null && row.key === "ebitda" && r.lender ? "n/m" : cr(row.cur)}</td>
              <td className="r"><Delta v={row.qoq} /></td>
              <td className="r"><Delta v={row.yoy} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="fine">
        {r.basis === "standalone" ? "Standalone" : "Consolidated"} figures from the filing.
        {r.ebitda_margin !== null && r.ebitda_margin !== undefined ? ` EBITDA margin ${r.ebitda_margin}%.` : ""}
        {r.lender ? " EBITDA isn't meaningful for a lender." : " EBITDA = PBT before exceptional items + finance costs + depreciation − other income."}
        {r.check?.status === "match" ? ` Revenue agrees with screener.in for ${r.check.against}.` : ""}
        {r.check?.status === "differs" ? ` Revenue differs from screener.in (${cr(r.check.screener_revenue)}); check the PDF.` : ""}
      </p>
      {r.notes?.length ? (
        <ul className="notes">{r.notes.map((n) => <li key={n}>{n}</li>)}</ul>
      ) : null}
    </div>
  );
}

function linkedin(name, company) {
  return `https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent(`${name} ${company}`)}`;
}

export function People({ people, company }) {
  return (
    <ul className="people">
      {people.map((p) => (
        <li key={`${p.name}-${p.role}`}>
          <div className="who">
            <span className={`move ${p.change === "appointed" || p.change === "re-appointed" ? "in" : "out"}`}>{p.change}</span>
            <strong>{p.name}</strong>
            <span className="role">{p.role}{p.effective ? `, from ${p.effective}` : ""}</span>
          </div>
          {p.background ? <p>{p.background}</p> : null}
          {p.previously?.length ? <p className="fine">Previously {p.previously.join("; ")}</p> : null}
          {p.education ? <p className="fine">{p.education}</p> : null}
          {p.reason ? <p className="fine">Reason given: {p.reason}</p> : null}
          <a className="quiet-link" href={linkedin(p.name, company)} target="_blank" rel="noreferrer">Find on LinkedIn</a>
        </li>
      ))}
    </ul>
  );
}

export function NeedsYou({ f, company, onDone, done, onResearch }) {
  const body = f.summary || f.title || f.subject;
  return (
    <article className={`need ${done ? "done" : ""}`}>
      <header>
        <button className="tick-box" aria-pressed={done} aria-label={done ? "Mark as not done" : "Mark as done"} onClick={() => onDone(f.id)}>
          <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M3 8.5l3 3 7-7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </button>
        <div className="head-text">
          <div className="who-line">
            <span className="sym">{f.symbol}</span>
            <span className="kind">{f.why}</span>
          </div>
          <time dateTime={f.ts} title={clock(f.ts)}>{ago(f.ts)}</time>
        </div>
      </header>
      {f.results ? <ResultsTable r={f.results} /> : null}
      {!f.results && f.people?.length ? <><p className="body">{body}</p><People people={f.people} company={company} /></> : null}
      {!f.results && !f.people?.length ? <p className="body">{body}</p> : null}
      {f.results && f.title ? <p className="fine">{f.title}</p> : null}
      <footer>
        {f.url ? <a href={f.url} target="_blank" rel="noreferrer">Open filing</a> : null}
        <button className="link" onClick={() => onResearch(f.symbol)}>Research {f.symbol}</button>
      </footer>
    </article>
  );
}

export function KnowRow({ f, onResearch }) {
  const [open, setOpen] = useState(false);
  const body = f.summary || f.title || f.subject;
  return (
    <li className={`know ${open ? "open" : ""}`}>
      <button className="row-btn" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="sym">{f.symbol}</span>
        <span className="row-main">
          <span className="kind">{f.why}</span>
          <span className="row-body">{body}</span>
        </span>
        <time dateTime={f.ts}>{ago(f.ts)}</time>
      </button>
      {open ? (
        <div className="row-more">
          {f.summary && f.title ? <p className="fine">{f.title}</p> : null}
          {f.model_flag === "raised" ? <p className="fine">Moved up: the model judged this filing material.</p> : null}
          {f.model_flag === "lowered" ? <p className="fine">Moved down: the model judged this filing immaterial.</p> : null}
          <div className="row-actions">
            {f.url ? <a href={f.url} target="_blank" rel="noreferrer">Open filing</a> : null}
            <button className="link" onClick={() => onResearch(f.symbol)}>Research {f.symbol}</button>
          </div>
        </div>
      ) : null}
    </li>
  );
}

export function RoutineGroup({ label, items }) {
  const [open, setOpen] = useState(false);
  const syms = [...new Set(items.map((i) => i.symbol))];
  return (
    <li className="routine">
      <button className="row-btn" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="count num">{items.length}</span>
        <span className="row-main">
          <span className="row-body">{label}</span>
          <span className="fine">{syms.slice(0, 5).join(", ")}{syms.length > 5 ? ` and ${syms.length - 5} more` : ""}</span>
        </span>
        <span className="chev" aria-hidden="true">{open ? "−" : "+"}</span>
      </button>
      {open ? (
        <ul className="routine-list">
          {items.map((f) => (
            <li key={f.id}>
              <span className="sym">{f.symbol}</span>
              {f.url ? <a href={f.url} target="_blank" rel="noreferrer">{f.title || f.subject}</a> : <span>{f.title || f.subject}</span>}
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}
