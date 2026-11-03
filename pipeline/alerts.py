DEFAULT_RULES = {
    "price_pct": 4.0,
    "volume_x": 2.0,
    "lookback": 20,
}


def scan(eod, rules=None, last_n=1):
    r = {**DEFAULT_RULES, **(rules or {})}
    out = []
    for sym, rows in eod.items():
        n = len(rows)
        start = max(r["lookback"] + 1, n - last_n)
        for i in range(start, n):
            d, c, v = rows[i]
            pc = rows[i - 1][1]
            if not pc:
                continue
            ret = (c / pc - 1) * 100
            window = [x[2] for x in rows[i - r["lookback"]:i]]
            avg = sum(window) / len(window) if window else 0
            vx = v / avg if avg else None
            why = []
            if abs(ret) >= r["price_pct"]:
                why.append("price")
            if vx is not None and vx >= r["volume_x"]:
                why.append("volume")
            if why:
                out.append({
                    "symbol": sym,
                    "date": d,
                    "close": c,
                    "ret": round(ret, 2),
                    "vol_x": round(vx, 2) if vx is not None else None,
                    "why": why,
                })
    out.sort(key=lambda a: (a["date"], abs(a["ret"])), reverse=True)
    return out
