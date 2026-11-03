import math
import tempfile
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
BSE_PDF = "https://www.bseindia.com/xml-data/corpfiling/AttachLive/{name}"
BSE_PDF_OLD = "https://www.bseindia.com/xml-data/corpfiling/AttachHis/{name}"


def prices(symbols, days=180):
    import yfinance as yf

    tickers = [f"{s}.NS" for s in symbols]
    df = yf.download(
        tickers,
        period=f"{days}d",
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=True,
    )
    out = {}
    for s, t in zip(symbols, tickers):
        try:
            sub = df[t] if len(tickers) > 1 else df
        except KeyError:
            continue
        sub = sub.dropna(subset=["Close"])
        if sub.empty:
            continue
        rows = []
        for idx, r in sub.iterrows():
            v = r.get("Volume")
            rows.append([
                idx.strftime("%Y-%m-%d"),
                round(float(r["Close"]), 2),
                int(v) if v is not None and not math.isnan(v) else 0,
            ])
        out[s] = rows
    return out


def _bse_client():
    from bse import BSE

    return BSE(download_folder=tempfile.mkdtemp())


def bse_code(client, symbol):
    try:
        return client.getScripCode(symbol)
    except Exception:
        return None


def _parse_bse_dt(s):
    s = (s or "").split(".")[0]
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=IST)
    except ValueError:
        return None


def bse_announcements(client, symbol, code, since, until):
    items = []
    page = 1
    while page <= 10:
        data = client.announcements(page_no=page, from_date=since, to_date=until, scripcode=str(code))
        rows = data.get("Table") or []
        for r in rows:
            dt = _parse_bse_dt(r.get("NEWS_DT") or r.get("DT_TM"))
            att = (r.get("ATTACHMENTNAME") or "").strip()
            items.append({
                "id": f"bse:{r.get('NEWSID')}",
                "symbol": symbol,
                "ts": dt.isoformat() if dt else None,
                "source": "BSE",
                "title": (r.get("HEADLINE") or "").strip(),
                "subject": (r.get("NEWSSUB") or "").strip(),
                "category_raw": (r.get("CATEGORYNAME") or "").strip(),
                "subcategory_raw": (r.get("SUBCATNAME") or "").strip(),
                "critical": bool(r.get("CRITICALNEWS")),
                "url": BSE_PDF.format(name=att) if att else None,
                "url_alt": BSE_PDF_OLD.format(name=att) if att else None,
            })
        total = 0
        t1 = data.get("Table1") or []
        if t1:
            total = t1[0].get("ROWCNT") or 0
        if not rows or len(items) >= total:
            break
        page += 1
    return items


def _nse_client():
    from nse import NSE

    return NSE(download_folder=tempfile.mkdtemp())


def nse_announcements(client, symbol, since, until):
    rows = client.announcements(symbol=symbol, from_date=since.date(), to_date=until.date())
    items = []
    for r in rows or []:
        try:
            dt = datetime.strptime(r.get("an_dt", ""), "%d-%b-%Y %H:%M:%S").replace(tzinfo=IST)
        except ValueError:
            dt = None
        items.append({
            "id": f"nse:{r.get('seq_id')}",
            "symbol": symbol,
            "ts": dt.isoformat() if dt else None,
            "source": "NSE",
            "title": (r.get("attchmntText") or "").strip(),
            "subject": (r.get("desc") or "").strip(),
            "category_raw": "",
            "subcategory_raw": (r.get("desc") or "").strip(),
            "critical": False,
            "url": r.get("attchmntFile"),
            "url_alt": None,
        })
    return items


def announcements(portfolio, days, log):
    until = datetime.now(IST)
    since = until - timedelta(days=days)
    out = []
    status = {}
    bse = None
    try:
        bse = _bse_client()
    except Exception as e:
        log(f"BSE client failed: {e}")
    nse = None
    for p in portfolio:
        sym = p["symbol"]
        got = None
        if bse is not None:
            code = bse_code(bse, sym) or p.get("bse")
            if code:
                try:
                    got = bse_announcements(bse, sym, code, since, until)
                    status[sym] = f"bse:{len(got)}"
                except Exception as e:
                    log(f"BSE {sym}: {e}")
        if got is None:
            try:
                if nse is None:
                    nse = _nse_client()
                got = nse_announcements(nse, sym, since, until)
                status[sym] = f"nse:{len(got)}"
            except Exception as e:
                log(f"NSE {sym}: {e}")
                status[sym] = "failed"
                got = []
        out.extend(got)
    for c in (bse, nse):
        try:
            if c is not None:
                c.exit()
        except Exception:
            pass
    return out, status
