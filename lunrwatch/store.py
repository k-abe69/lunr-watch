"""収集の実行・重複排除・永続保存。保存形式は JSON Lines（items / runs）と state.json。"""
import hashlib
import json
import os
import re
from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from . import sources as S
from .classify import Rules, assess
from .util import FetchError, iso, jst_date, now_utc, parse_iso, read_json, write_json_atomic

TIER_RANK = {"sec": 5, "gov": 4, "official": 4, "peer": 3, "media": 2, "aggregator": 1}
STOP = set("the a an of to in on for and with at by from is are as its it this that new will after over into says intuitive machines lunr".split())


def canonical_url(url):
    p = urlparse(url)
    q = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith(("utm_", "fbclid", "ref"))]
    return urlunparse((p.scheme, p.netloc.lower(), p.path.rstrip("/"), "", urlencode(q), ""))


def item_key(src, e):
    ex = e["extra"]
    if src["type"] == "sec":
        return "sec:" + ex["accession"]
    if src["type"] == "usaspending":
        return f"usa:{ex['award_id']}|{ex['version']}"
    return "url:" + canonical_url(e["url"])


def item_id(key):
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def tokens(title):
    return {t for t in re.findall(r"[a-z0-9][a-z0-9\-\.]+", title.lower()) if t not in STOP and len(t) > 2}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


class Store:
    def __init__(self, data_dir):
        self.dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.items_path = os.path.join(data_dir, "items.jsonl")
        self.runs_path = os.path.join(data_dir, "runs.jsonl")
        self.state_path = os.path.join(data_dir, "state.json")
        self.items = {}
        for rec in self._read_lines(self.items_path):
            self.items[rec["id"]] = rec
        self.runs = list(self._read_lines(self.runs_path))
        self.state = read_json(self.state_path, {"sources": {}})

    @staticmethod
    def _read_lines(path):
        if not os.path.exists(path):
            return []
        out = []
        with open(path, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    out.append(json.loads(ln))
        return out

    def save(self):
        tmp = self.items_path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            for rec in sorted(self.items.values(), key=lambda r: (r["first_seen_at"], r["id"])):
                f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
        os.replace(tmp, self.items_path)
        tmp = self.runs_path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            for r in self.runs:
                f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
        os.replace(tmp, self.runs_path)
        write_json_atomic(self.state_path, self.state)

    SEC_LINK_ITEMS = {"2.02"}  # 決算のみ。他の項目は同時期の複数の発表のどれに当たるか推測になるため結びつけない
    QUARTER = re.compile(r"(?<![A-Za-z0-9])(?:Q([1-4])|(first|second|third|fourth) quarter)(?![A-Za-z0-9])", re.I)
    QNUM = {"first": "1", "second": "2", "third": "3", "fourth": "4"}
    RESULTS = re.compile(r"financial results", re.I)

    @staticmethod
    def _is_sec8k(r):
        return r["tier"] == "sec" and r["extra"].get("form", "").startswith("8-K")

    def _same_announcement(self, a, b):
        """SECの8-Kと、同じ発表の公式IR配信（36時間以内）を同一の話題とみなす。"""
        sec, ir = (a, b) if self._is_sec8k(a) else (b, a)
        if not (self._is_sec8k(sec) and ir["tier"] == "official" and not self._is_sec8k(ir)):
            return False
        items = set(sec["extra"].get("items", []))
        if not items & self.SEC_LINK_ITEMS:
            return False
        if abs((parse_iso(sec["published_at"]) - parse_iso(ir["published_at"])).total_seconds()) > 36 * 3600:
            return False
        if "2.02" in items:  # 決算の8-Kは、決算発表のIR配信とだけ結びつける（日程告知とは結びつけない）
            return bool(self.RESULTS.search(ir["title"])) and "announces date" not in ir["title"].lower()
        return True

    def find_cluster(self, rec):
        """同じ話題の既存項目を探す。戻り値 (cluster_id, 関連項目id, 種別)。種別: same / sec_ir / None。
        SECの件名・政府契約記録は定型なので、見出しの類似では結びつけない。"""
        if rec["source_id"] == "usaspending":
            return None, None, None
        for o in self.items.values():
            if self._same_announcement(rec, o):
                return o["cluster_id"], o["id"], "sec_ir"
        if rec["tier"] == "sec":
            return None, None, None
        mine = tokens(rec["title"])
        best, best_sim = None, 0.0
        pub = parse_iso(rec["published_at"])
        for o in self.items.values():
            if o["tier"] == "sec" or o["source_id"] == "usaspending":
                continue
            if bool(o.get("notice")) != bool(rec.get("notice")):  # 日程告知は決算発表などと別の話題
                continue
            if abs((parse_iso(o["published_at"]) - pub).days) > 7:
                continue
            theirs = tokens(o["title"])
            sim = jaccard(mine, theirs)
            shared = len(mine & theirs)
            if min(len(mine), len(theirs)) >= 4 and shared >= 3:  # 言い換えた見出し（一方が他方に含まれる）
                sim = max(sim, 0.9 * shared / min(len(mine), len(theirs)))
            if sim > best_sim:
                best, best_sim = o, sim
        if best and best_sim >= 0.6:
            return best["cluster_id"], best["id"], "same"
        return None, None, None

    AMOUNT = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)\s?(million|billion)", re.I)

    def find_known_amount(self, rec):
        """政府の契約記録の金額が、既に公式発表（IR等）の本文抜粋にある金額と一致するか（0.5%以内）。"""
        ex = rec["extra"]
        targets = [v for v in (ex.get("potential"), ex.get("obligated")) if v]
        if not targets:
            return None
        for o in self.items.values():
            if o["tier"] not in ("official", "peer") or o["source_id"] == rec["source_id"]:
                continue
            for m in self.AMOUNT.finditer(o["title"] + " " + o["summary"]):
                val = float(m.group(1).replace(",", "")) * (1e6 if m.group(2).lower() == "million" else 1e9)
                if any(abs(val - t) / t <= 0.005 for t in targets):
                    return o
        return None

    def find_recap(self, rec):
        """報道が、既に公式発表済みの決算を後から振り返っているだけの可能性を検出する。"""
        if rec["tier"] not in ("media", "aggregator"):
            return None
        m = self.QUARTER.search(rec["title"])
        if not m:
            return None
        q = m.group(1) or self.QNUM[m.group(2).lower()]
        pub = parse_iso(rec["published_at"])
        for o in self.items.values():
            if o["tier"] != "official" or o.get("notice") or not self.RESULTS.search(o["title"]):
                continue
            om = self.QUARTER.search(o["title"])
            if not om or (om.group(1) or self.QNUM[om.group(2).lower()]) != q:
                continue
            days = (pub - parse_iso(o["published_at"])).days
            if 3 < days <= 120:
                return o
        return None


PRIMARY = ("sec", "official", "gov", "peer")
RANK_NUM = {"重要": 3, "注目": 2, "参考": 1, "未評価": 0}


def apply_review_status(rec):
    """本文を確認できていない一次情報を「要確認」にする。収集成功と、内容を判断できたことは別。
    定型的な開示（参考どまりの Form 4 など）は対象外。"""
    rec["needs_review"] = None
    unverified = rec["body_status"] in ("metadata", "headline_only")
    if rec["tier"] not in PRIMARY:
        return
    top = max(RANK_NUM[rec["short_term"]], RANK_NUM[rec["mid_term"]])
    if rec["short_term"] == "未評価":
        rec["needs_review"] = "重要度を判定できない一次情報（要確認）"
    elif unverified and top >= 2:
        rec["needs_review"] = "新しい開示あり・本文未確認"
    if unverified and rec["tier"] == "sec":
        rec["reasons"].append("本文未確認：書類の種別・項目番号だけに基づく判定で、内容（金額・条件・数値）は評価していない。")
    elif unverified:
        rec["reasons"].append("本文未確認：見出しだけに基づく判定。")


def link_sec_ir(store, new, other):
    """同じ発表を8-Kと公式IR配信の両方で確認できた場合、8-K側の「本文未確認」を理由付きで解除する。
    8-K本文そのものを読めたわけではないため、その旨を判定理由に残す。"""
    sec, ir = (new, other) if new["tier"] == "sec" else (other, new)
    sec["needs_review"] = None
    note = "同じ発表を公式IRの配信（冒頭抜粋）でも確認。8-K本文そのものは未確認で、IR配信が8-Kの全内容を代替するとは限らない。"
    if note not in sec["reasons"]:
        sec["reasons"].append(note)


def run_collect(cfg_sources, rules_cfg, store, *, now=None, fetchers=None, enrich=True):
    """全情報源を1回収集して保存する。戻り値は実行記録(run)。"""
    now = now or now_utc()
    fetchers = fetchers or S.FETCHERS
    rules = Rules(rules_cfg)
    lb = rules_cfg["lookback"]
    run = {"run_id": iso(now), "started_at": iso(now), "sources": []}
    enriched = 0
    for src in cfg_sources["sources"]:
        rec = {"id": src["id"], "name": src["name"], "tier": src["tier"], "critical": bool(src.get("critical"))}
        if not src.get("enabled", True) or src["type"] == "unsupported":
            rec.update(status="unsupported", note=src.get("note", "無効化されています"))
            run["sources"].append(rec)
            continue
        st = store.state["sources"].get(src["id"], {})
        last_ok = parse_iso(st["last_success"]) if st.get("last_success") else None
        first = last_ok is None
        if first:
            cutoff = now - timedelta(days=src.get("baseline_days", 30))
            new_from = None
        else:
            cutoff = max(now - timedelta(days=lb["max_days"]), last_ok - timedelta(hours=lb["overlap_hours"]))
            new_from = cutoff
        try:
            entries = fetchers[src["type"]](src, cutoff=cutoff)
        except FetchError as e:
            rec.update(status="failed", error=str(e))
            run["sources"].append(rec)
            continue
        except Exception as e:  # 想定外の失敗も「取得失敗」として扱い、情報なしにしない
            rec.update(status="failed", error=f"想定外のエラー（{type(e).__name__}）")
            run["sources"].append(rec)
            continue
        pubs = sorted(e["published"] for e in entries)
        added = dup = irrelevant = 0
        for e in sorted(entries, key=lambda x: x["published"]):
            iid = item_id(item_key(src, e))
            if iid in store.items:
                dup += 1
                continue
            a = assess(e, src, rules)
            if a is None:
                irrelevant += 1
                continue
            baseline = first or e["published"] < iso(new_from)
            summary = e["summary"]
            if src["type"] == "sec":
                body_status = "metadata"
                if enrich and e["extra"]["form"].startswith("8-K") and enriched < 8 and e["published"] >= iso(now - timedelta(days=30)):
                    ex = S.enrich_sec_8k(e)
                    enriched += 1
                    if ex:
                        summary, body_status = ex, "excerpt"
            else:
                body_status = "summary" if len(summary) >= 80 else "headline_only"
            rec_item = {
                "id": iid, "source_id": src["id"], "source_name": src["name"], "tier": src["tier"],
                "title": a.get("headline", e["title"]), "publisher": a.get("publisher"), "url": e["url"],
                "published_at": e["published"], "first_seen_at": iso(now), "first_seen_date": jst_date(iso(now)),
                "summary": summary[:700], "body_status": body_status,
                "themes": a["themes"], "short_term": a["short_term"], "mid_term": a["mid_term"],
                "direction": a["direction"], "reliability": a["reliability"], "reasons": a["reasons"],
                "follow_ups": a["follow_ups"], "why_related": a["why_related"], "baseline": baseline,
                "extra": {k: v for k, v in e["extra"].items() if k != "base"}, "judged_by": "rule-v1",
            }
            rec_item["notice"] = bool(rules.sched.search(rec_item["title"]))
            apply_review_status(rec_item)
            recap = store.find_recap(rec_item)
            if recap:
                rec_item["recap_of"] = recap["id"]
                for k in ("short_term", "mid_term"):
                    if RANK_NUM[rec_item[k]] > 1:
                        rec_item[k] = "参考"
                rec_item["reasons"].append(
                    f"公式の決算発表（{jst_date(recap['published_at'])}）から{(parse_iso(e['published']) - parse_iso(recap['published_at'])).days}日後の報道で、既知の決算の再掲・後追いの可能性が高い。新しい材料としては扱わず、重要度を参考に下げた。")
            if src["type"] == "usaspending":
                known = store.find_known_amount(rec_item)
                if known:
                    rec_item["recap_of"] = known["id"]
                    rec_item["mid_term"] = "参考" if RANK_NUM[rec_item["mid_term"]] > 1 else rec_item["mid_term"]
                    rec_item["reasons"].append(f"契約の金額が、既に公式発表済みの『{known['title'][:60]}』（{jst_date(known['published_at'])}）の金額と一致する。既知の契約の記録更新の可能性が高く、新しい材料としては扱わない。")
            cid, prev, kind = store.find_cluster(rec_item)
            rec_item["cluster_id"] = cid or iid
            rec_item["related_to"] = prev
            if kind == "sec_ir":
                link_sec_ir(store, rec_item, store.items[prev])
            store.items[iid] = rec_item
            added += 1
        store.state["sources"].setdefault(src["id"], {})["last_success"] = iso(now)
        rec.update(status="ok", fetched=len(entries), added=added, duplicates=dup, irrelevant=irrelevant,
                   first_run=first, range_from=pubs[0] if pubs else None, range_to=pubs[-1] if pubs else None,
                   window_from=iso(cutoff), window_to=iso(now))
        run["sources"].append(rec)
    run["finished_at"] = iso(now_utc())
    store.runs.append(run)
    store.save()
    return run
