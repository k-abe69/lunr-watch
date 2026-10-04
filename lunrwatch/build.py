"""保存データから閲覧用の静的サイトを生成する（site/ に出力。data.js は file:// でも読める）。"""
import json
import os
import shutil

from .classify import RANK
from .util import UTC, jst_date, iso, now_utc, parse_iso

HERE = os.path.dirname(os.path.abspath(__file__))
SITE_SRC = os.path.join(os.path.dirname(HERE), "site_src")


def build_days(store, cfg_sources):
    by_day = {}
    for run in store.runs:
        by_day.setdefault(jst_date(run["started_at"]), []).append(run)
    days = {}
    for d, runs in by_day.items():
        merged = {}
        for run in runs:  # 同日に複数回実行した場合は、1回でも成功した情報源は成功扱い
            for s in run["sources"]:
                cur = merged.get(s["id"])
                if cur is None or s["status"] == "ok" or (cur["status"] != "ok" and s["status"] == "failed"):
                    merged[s["id"]] = s
        statuses = list(merged.values())
        enabled = [s for s in statuses if s["status"] != "unsupported"]
        failed = [s for s in enabled if s["status"] == "failed"]
        crit_failed = [s for s in failed if s["critical"]]
        if enabled and len(failed) == len(enabled):
            level = "all_failed"
        elif crit_failed:
            level = "incomplete"
        elif failed:
            level = "partial"
        else:
            level = "complete"
        clusters = {}
        for it in store.items.values():
            if it["first_seen_date"] == d and not it["baseline"]:
                clusters.setdefault(it["cluster_id"], []).append(it["id"])
        def top(ids):
            return max(max(RANK[store.items[i]["short_term"]], RANK[store.items[i]["mid_term"]]) for i in ids)
        # 本文未確認の一次情報（needs_review）は、確認済みの重要・注目とは別枠で数える
        review = [c for c, ids in clusters.items() if any(store.items[i].get("needs_review") for i in ids)]
        rest = {c: ids for c, ids in clusters.items() if c not in review}
        important = [c for c, ids in rest.items() if top(ids) == 3]
        notable = [c for c, ids in rest.items() if top(ids) == 2]
        days[d] = {
            "date": d, "runs": len(runs), "last_run": runs[-1]["started_at"], "level": level,
            "sources": statuses, "clusters": clusters, "important": important, "notable": notable, "review": review,
            "baseline": any(s.get("first_run") for run in runs for s in run["sources"]),
        }
    return days


def build_sources(store, cfg_sources):
    last = store.runs[-1]["sources"] if store.runs else []
    last_by = {s["id"]: s for s in last}
    out = []
    for src in cfg_sources["sources"]:
        s = dict(last_by.get(src["id"], {"id": src["id"], "name": src["name"], "tier": src["tier"],
                                         "critical": bool(src.get("critical")),
                                         "status": "unsupported" if (not src.get("enabled", True) or src["type"] == "unsupported") else "pending"}))
        s["last_success"] = store.state["sources"].get(src["id"], {}).get("last_success")
        s["url"] = src.get("url")
        out.append(s)
    return out


def build_site(store, cfg_sources, out_dir, generated_at=None):
    os.makedirs(out_dir, exist_ok=True)
    for name in os.listdir(SITE_SRC):
        shutil.copy2(os.path.join(SITE_SRC, name), os.path.join(out_dir, name))
    items = sorted(store.items.values(), key=lambda r: r["published_at"], reverse=True)
    data = {
        "generated_at": generated_at or iso(now_utc()),
        "items": items,
        "days": build_days(store, cfg_sources),
        "sources": build_sources(store, cfg_sources),
        "last_run": store.runs[-1]["started_at"] if store.runs else None,
    }
    with open(os.path.join(out_dir, "data.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write("window.LUNR = " + json.dumps(data, ensure_ascii=False) + ";\n")
    return data
