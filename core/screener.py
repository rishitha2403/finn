import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from core import net

BASE = "https://www.screener.in"
SYMBOL_RE = re.compile(r"^[A-Z0-9&\-]{1,20}$")


class NotFound(Exception):
    pass


def clean_symbol(s):
    s = (s or "").strip().upper()
    s = s.replace(".NS", "").replace(".BO", "")
    if not SYMBOL_RE.match(s):
        raise ValueError("symbol should look like TCS or BAJAJ-AUTO")
    return s


def num(text):
    if text is None:
        return None
    t = text.replace(",", "").replace("₹", "").replace("%", "").replace("Cr.", "").strip()
    if t in ("", "-", "--"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def label(cell):
    t = cell.get_text(" ", strip=True)
    t = t.replace("\xa0", " ").replace("+", "").strip()
    t = re.sub(r"\s+", " ", t)
    return t


def parse_table(section):
    if section is None:
        return None
    table = section.find("table", class_="data-table")
    if table is None:
        return None
    head = table.find("thead")
    cols = [th.get_text(" ", strip=True) for th in head.find_all("th")][1:] if head else []
    rows = {}
    for tr in table.find("tbody").find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        name = label(tds[0])
        if not name or name.lower().startswith("raw pdf"):
            continue
        rows[name] = [num(td.get_text(" ", strip=True)) for td in tds[1:]]
    return {"cols": cols, "rows": rows}


def parse_ranges(section):
    out = {}
    if section is None:
        return out
    for t in section.find_all("table", class_="ranges-table"):
        th = t.find("th")
        if not th:
            continue
        title = th.get_text(" ", strip=True)
        vals = {}
        for tr in t.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) >= 2:
                k = tds[0].get_text(" ", strip=True).rstrip(":")
                vals[k] = num(tds[1].get_text(" ", strip=True))
        out[title] = vals
    return out


def parse_top_ratios(soup):
    out = {}
    ul = soup.find(id="top-ratios")
    if not ul:
        return out
    for li in ul.find_all("li"):
        n = li.find(class_="name")
        v = li.find(class_="number")
        if n and v:
            out[n.get_text(" ", strip=True)] = num(v.get_text(" ", strip=True))
    return out


def parse_documents(soup, page_url):
    docs = {"concalls": [], "annual_reports": []}
    sec = soup.find(id="documents")
    if not sec:
        return docs
    cc = sec.find(class_="concalls")
    if cc:
        for li in cc.find_all("li"):
            date_el = li.find("div")
            date = date_el.get_text(" ", strip=True) if date_el else ""
            links = {}
            for a in li.find_all("a"):
                txt = a.get_text(" ", strip=True).lower()
                href = a.get("href")
                if not href:
                    continue
                href = urljoin(page_url, href)
                if "transcript" in txt:
                    links["transcript"] = href
                elif "ppt" in txt:
                    links["ppt"] = href
                elif "rec" in txt:
                    links["recording"] = href
            if date or links:
                docs["concalls"].append({"date": date, **links})
    ar = sec.find(class_="annual-reports")
    if ar:
        for a in ar.find_all("a"):
            href = a.get("href")
            if href:
                docs["annual_reports"].append({
                    "title": re.sub(r"\s+", " ", a.get_text(" ", strip=True)),
                    "url": urljoin(page_url, href),
                })
    return docs


def parse_codes(soup):
    text = soup.get_text(" ", strip=True)
    bse = re.search(r"BSE:\s*(\d{6})", text)
    nse = re.search(r"NSE:\s*([A-Z0-9&\-]+)", text)
    return (bse.group(1) if bse else None, nse.group(1) if nse else None)


def parse_page(html, url, symbol):
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    name = h1.get_text(" ", strip=True) if h1 else symbol
    about = None
    ab = soup.select_one(".company-profile .about") or soup.find(class_="about")
    if ab:
        about = re.sub(r"\s+", " ", ab.get_text(" ", strip=True))[:900]
    bse, nse = parse_codes(soup)
    pl = soup.find(id="profit-loss")
    return {
        "symbol": symbol,
        "name": name,
        "url": url,
        "about": about,
        "bse_code": bse,
        "nse_code": nse,
        "ratios": parse_top_ratios(soup),
        "quarters": parse_table(soup.find(id="quarters")),
        "annual": parse_table(pl),
        "growth": parse_ranges(pl),
        "balance": parse_table(soup.find(id="balance-sheet")),
        "cashflow": parse_table(soup.find(id="cash-flow")),
        "efficiency": parse_table(soup.find(id="ratios")),
        "shareholding": parse_table(soup.find(id="quarterly-shp") or soup.find(id="shareholding")),
        "documents": parse_documents(soup, url),
    }


def _has_data(p):
    q = p.get("quarters")
    return bool(q and q["rows"] and any(v is not None for vals in q["rows"].values() for v in vals))


def fetch(symbol):
    symbol = clean_symbol(symbol)
    tried = []
    for path in (f"/company/{symbol}/consolidated/", f"/company/{symbol}/"):
        url = BASE + path
        try:
            r = net.get(url, tries=2)
        except Exception as e:
            tried.append(str(e))
            continue
        page = parse_page(r.text, url, symbol)
        page["basis"] = "consolidated" if "consolidated" in path else "standalone"
        if _has_data(page):
            return page
        tried.append(f"{path}: no figures")
    raise NotFound(f"screener has no figures for {symbol} ({'; '.join(tried)[:200]})")
