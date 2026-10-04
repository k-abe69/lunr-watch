"""情報源ごとの取得処理。戻り値は raw entry のリスト。
raw entry: {title, url, published(ISO UTC), summary, extra{}}。取得失敗は FetchError。"""
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import timedelta
from email.utils import parsedate_to_datetime

from .util import FetchError, UTC, http_get, iso, now_utc, strip_html

SEC_PACE = 0.25  # SEC公式のアクセス上限（毎秒10回）より十分低く保つ


def _ns_strip(tag):
    return tag.rsplit("}", 1)[-1]


def _parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        dt = parsedate_to_datetime(s)
    except Exception:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return iso(dt)


def parse_feed(xml_bytes):
    """RSS 2.0 / Atom を共通形式に。"""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise FetchError(f"フィードを解析できない（{e}）")
    out = []
    for el in root.iter():
        if _ns_strip(el.tag) not in ("item", "entry"):
            continue
        f = {}
        for c in el:
            name = _ns_strip(c.tag)
            if name == "link":
                f.setdefault("link", c.get("href") or (c.text or "").strip())
            elif name in ("title", "description", "summary", "content", "pubDate", "published", "updated", "date", "source"):
                f.setdefault(name, (c.text or "").strip())
        title = strip_html(f.get("title", ""))
        link = f.get("link", "")
        pub = _parse_date(f.get("pubDate") or f.get("published") or f.get("updated") or f.get("date"))
        if not title or not link or not pub:
            continue  # 日付がない項目は新規性を判定できないので扱わない
        summary = strip_html(f.get("description") or f.get("summary") or f.get("content") or "", 600)
        out.append({"title": title, "url": link, "published": pub, "summary": summary, "extra": {}})
    return out


def fetch_rss(src, **_):
    """pages>1 のときは ?paged=N（WordPress系）を順に取得し、途中のページ失敗は全体の失敗にする。"""
    out, seen = [], set()
    for n in range(1, int(src.get("pages", 1)) + 1):
        url = src["url"] if n == 1 else src["url"] + ("&" if "?" in src["url"] else "?") + f"paged={n}"
        if n > 1:
            time.sleep(0.5)
        try:
            entries = parse_feed(http_get(url))
        except FetchError as e:
            if n > 1 and "HTTP 400" in str(e):  # 最終ページを超えた
                break
            raise
        fresh = [e for e in entries if e["url"] not in seen]
        if not fresh:
            break
        seen.update(e["url"] for e in fresh)
        out += fresh
    return out


def fetch_sec(src, cutoff):
    raw = http_get(src["url"], headers={"Accept": "application/json"})
    try:
        d = json.loads(raw)
        r = d["filings"]["recent"]
        n = len(r["accessionNumber"])
    except Exception:
        raise FetchError("SECの応答形式が想定と異なる")
    cik = str(int(src["cik"]))
    out = []
    for i in range(n):
        acc = r["accessionNumber"][i]
        form = r["form"][i]
        accepted = r.get("acceptanceDateTime", [""] * n)[i] or ""
        pub = _parse_date(accepted) or _parse_date(r["filingDate"][i] + "T00:00:00Z")
        if not pub or pub < iso(cutoff):
            continue
        nodash = acc.replace("-", "")
        base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{nodash}"
        doc = r["primaryDocument"][i] or ""
        url = f"{base}/{doc}" if form.startswith("8-K") and doc and "/" not in doc else f"{base}/{acc}-index.htm"
        items = r.get("items", [""] * n)[i] or ""
        title = f"SEC Form {form}" + (f"（Items {items}）" if items else "")
        desc = r.get("primaryDocDescription", [""] * n)[i] or ""
        out.append({"title": title, "url": url, "published": pub, "summary": desc, "extra": {
            "form": form, "items": [x for x in items.split(",") if x], "accession": acc, "cik": cik, "base": base}})
    return out


def enrich_sec_8k(entry):
    """新規の8-Kだけ、添付(Ex-99)の冒頭を原文抜粋として取得する。失敗しても項目は残す。"""
    ex = entry["extra"]
    # www.sec.gov は連絡先のないUser-Agentを403で拒否する（SECのfair access方針）。連絡先未設定なら取得しない。
    if "@" not in os.environ.get("LUNRWATCH_CONTACT", ""):
        return None
    try:
        time.sleep(SEC_PACE)
        idx = json.loads(http_get(ex["base"] + "/index.json"))
        files = [f["name"] for f in idx["directory"]["item"]]
        cands = [f for f in files if re.search(r"(ex|exhibit)[-_]?99", f, re.I) and f.lower().endswith((".htm", ".html"))]
        if not cands:
            return None
        time.sleep(SEC_PACE)
        text = strip_html(http_get(f"{ex['base']}/{cands[0]}", max_bytes=3_000_000).decode("utf-8", "replace"))
        return text[:700] if text else None
    except Exception:
        return None


def fetch_usaspending(src, cutoff):
    body = {
        "filters": {
            "recipient_search_text": [src["recipient"]],
            "award_type_codes": ["A", "B", "C", "D"],
            "time_period": [{"start_date": cutoff.strftime("%Y-%m-%d"),
                             "end_date": (now_utc() + timedelta(days=1)).strftime("%Y-%m-%d"), "date_type": "action_date"}],
        },
        "fields": ["Award ID", "Recipient Name", "Award Amount", "Description", "Awarding Agency",
                   "Last Modified Date", "Start Date", "generated_internal_id"],
        "sort": "Last Modified Date", "order": "desc", "limit": 25, "page": 1,
    }
    raw = http_get(src["url"], data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        results = json.loads(raw)["results"]
    except Exception:
        raise FetchError("USAspendingの応答形式が想定と異なる")
    out = []
    for a in results:
        lm = a.get("Last Modified Date") or ""
        pub = _parse_date(lm.replace(" ", "T") + "Z") if lm else None
        if not pub or pub < iso(cutoff):
            continue
        desc = strip_html(a.get("Description") or "", 300)
        listed = a.get("Award Amount")
        extra = {"award_id": a.get("Award ID"), "agency": a.get("Awarding Agency"), "version": lm}
        detail = _usaspending_detail(a.get("generated_internal_id"))
        if detail:
            extra.update(detail)
            ob, pot = detail["obligated"], detail["potential"]
            amt = f"確定済み額（obligation）${ob:,.0f}" + (f"／オプション等を含む最大額 ${pot:,.0f}" if pot else "") if ob is not None else ""
            period = f"／履行期間 {detail['start_date']}〜{detail.get('end_date') or '?'}" if detail.get("start_date") else ""
            summary = f"{desc}（USAspending: {amt}{period}）"
        else:
            summary = desc + (f"（USAspending一覧の金額 ${listed:,.0f}。確定額か最大額かの内訳は未取得）" if isinstance(listed, (int, float)) else "")
        title = f"契約記録の更新: {a.get('Award ID')}（{a.get('Awarding Agency')}）{desc[:60]}"
        out.append({"title": title, "url": f"https://www.usaspending.gov/award/{a.get('generated_internal_id')}",
                    "published": pub, "summary": summary, "extra": extra})
    return out


def _usaspending_detail(gid):
    """契約の確定額と最大額を区別するための詳細取得。失敗しても一覧の情報だけで続行する。"""
    if not gid:
        return None
    try:
        time.sleep(0.2)
        d = json.loads(http_get(f"https://api.usaspending.gov/api/v2/awards/{gid}/", retries=1))
        pop = d.get("period_of_performance") or {}
        return {"obligated": d.get("total_obligation"), "potential": d.get("base_and_all_options"),
                "start_date": (pop.get("start_date") or "")[:10], "end_date": (pop.get("potential_end_date") or pop.get("end_date") or "")[:10]}
    except Exception:
        return None


FETCHERS = {"rss": fetch_rss, "sec": fetch_sec, "usaspending": fetch_usaspending}
