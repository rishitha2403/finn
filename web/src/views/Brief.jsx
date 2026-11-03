import { useMemo, useState } from "react";
import { NeedsYou, KnowRow, RoutineGroup } from "../components/Filing.jsx";
import { rank, scan, tierOf } from "../lib/rules.js";
import { useStored } from "../lib/store.js";
import { clock, pct, tone, ymd } from "../lib/fmt.js";

const WINDOWS = [
  { id: "visit", label: "Since last visit" },
  { id: "24", label: "24 hours", h: 24 },
  { id: "72", label: "3 days", h: 72 },
  { id: "168", label: "7 days", h: 168 },
  { id: "720", label: "30 days", h: 720 },
];

function windowStart(id, visit, now, custom) {
  if (id === "custom" && custom) return new Date(custom + "T00:00:00+05:30").getTime();
  if (id === "visit") {
    if (visit && now - visit < 7 * 864e5) return visit;
    return now - 24 * 36e5;
  }
  const w = WINDOWS.find((x) => x.id === id);
  return now - (w?.h || 24) * 36e5;
}

function sinceText(id, start, visit) {
  if (id === "visit") {
    return visit && Date.now() - visit < 7 * 864e5 ? `since you last looked, ${clock(new Date(start).toISOString())}` : "in the last 24 hours";
  }
  if (id === "custom") return `since ${new Date(start).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}`;
  return `in the last ${WINDOWS.find((w) => w.id === id).label}`;
}

export default function Brief({ data, visit, go }) {
  const { meta, filings, eod } = data;
  const [win, setWin] = useStored("window", "visit");
  const [custom, setCustom] = useStored("customFrom", "");
  const [watched] = useStored("watch", meta.default_watch);
  const [rules] = useStored("rules", meta.default_rules);
  const [done, setDone] = useStored("done", []);
  const [showDone, setShowDone] = useState(false);
  const names = useMemo(() => Object.fromEntries(meta.portfolio.map((p) => [p.symbol, p.name])), [meta]);

  const now = Date.now();
  const start = windowStart(win, visit, now, custom);
  const inWin = filings.filter((f) => new Date(f.ts).getTime() >= start);
  const ranked = inWin.map((f) => ({ ...f, r: rank(f, watched) })).sort((a, b) => b.r - a.r || (a.ts < b.ts ? 1 : -1));
  const act = ranked.filter((f) => tierOf(f.r) === "act");
  const open = act.filter((f) => !done.includes(f.id));
  const closed = act.filter((f) => done.includes(f.id));
  const know = ranked.filter((f) => tierOf(f.r) === "know");
  const routine = ranked.filter((f) => tierOf(f.r) === "routine");

  const startDay = new Date(start + 5.5 * 36e5).toISOString().slice(0, 10);
  const moves = scan(eod, rules, startDay);
  const lastSession = Object.values(eod)[0]?.slice(-1)[0]?.[0];
  const movesShown = moves.length ? moves : [];

  const groups = {};
  for (const f of routine) (groups[f.category] ||= []).push(f);
  const groupList = Object.entries(groups).sort((a, b) => b[1].length - a[1].length);

  const toggleDone = (id) => setDone(done.includes(id) ? done.filter((x) => x !== id) : [...done.slice(-300), id]);
  const research = (s) => go(`#/research/${s}`);

  return (
    <div className="brief">
      <section className="hero" aria-live="polite">
        <p className="hero-line">
          <span className="big num">{inWin.length}</span> filings across {meta.portfolio.length} holdings {sinceText(win, start, visit)}.
        </p>
        <p className="hero-sub">
          {open.length ? <><strong>{open.length} need you.</strong> </> : <strong>Nothing needs you. </strong>}
          {know.length} worth knowing, {routine.length} set aside.
          {movesShown.length ? ` ${movesShown.length} price or volume move${movesShown.length > 1 ? "s" : ""} crossed your lines.` : ""}
        </p>
      </section>

      <div className="windows" role="tablist" aria-label="Time window">
        {WINDOWS.map((w) => (
          <button key={w.id} role="tab" aria-selected={win === w.id} className={win === w.id ? "chip on" : "chip"} onClick={() => setWin(w.id)}>{w.label}</button>
        ))}
        <label className={win === "custom" ? "chip on date" : "chip date"}>
          <span>From</span>
          <input type="date" value={custom} max={new Date().toISOString().slice(0, 10)} onChange={(e) => { setCustom(e.target.value); setWin("custom"); }} />
        </label>
      </div>

      {movesShown.length ? (
        <section className="moves" aria-label="Moves past your lines">
          <h2>Moves past your lines</h2>
          <ul>
            {movesShown.slice(0, 8).map((m) => (
              <li key={m.symbol + m.date}>
                <button className="move-row" onClick={() => research(m.symbol)}>
                  <span className="sym">{m.symbol}</span>
                  <span className={`num ${tone(m.ret)}`}>{pct(m.ret)}</span>
                  <span className="fine">{m.vx && m.vx >= 1.5 ? `${m.vx.toFixed(1)}× usual volume` : ""}</span>
                  <span className="fine when">{m.date === lastSession ? "last close" : ymd(m.date)}</span>
                </button>
              </li>
            ))}
          </ul>
          <button className="link small" onClick={() => go("#/watch")}>Change what counts as unusual</button>
        </section>
      ) : null}

      <section aria-label="Needs you">
        {open.length ? <h2>Needs you</h2> : null}
        {open.map((f) => (
          <NeedsYou key={f.id} f={f} company={names[f.symbol]} done={false} onDone={toggleDone} onResearch={research} />
        ))}
        {!open.length && act.length ? <p className="empty">You've cleared everything that needed you in this window.</p> : null}
        {closed.length ? (
          <>
            <button className="link small" onClick={() => setShowDone(!showDone)}>{showDone ? "Hide" : "Show"} {closed.length} done</button>
            {showDone ? closed.map((f) => <NeedsYou key={f.id} f={f} company={names[f.symbol]} done onDone={toggleDone} onResearch={research} />) : null}
          </>
        ) : null}
      </section>

      {know.length ? (
        <section aria-label="Worth knowing">
          <h2>Worth knowing</h2>
          <ul className="list">{know.map((f) => <KnowRow key={f.id} f={f} onResearch={research} />)}</ul>
        </section>
      ) : null}

      {routine.length ? (
        <section aria-label="Set aside">
          <h2>Set aside</h2>
          <p className="fine section-note">Routine paperwork and categories you don't watch. Tap a group to see every filing.</p>
          <ul className="list">{groupList.map(([cat, items]) => <RoutineGroup key={cat} label={meta.labels[cat] || cat} items={items} />)}</ul>
        </section>
      ) : null}

      {!inWin.length ? <p className="empty">No filings in this window. Try a longer one above.</p> : null}
    </div>
  );
}
