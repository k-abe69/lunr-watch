"""テスト。実データとは別の一時ディレクトリで、固定のフィクスチャだけを使う（実ニュースと混ぜない）。
実行: python -m unittest discover -s tests -v"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lunrwatch import sources as S  # noqa: E402
from lunrwatch.build import build_site  # noqa: E402
from lunrwatch.store import Store, run_collect  # noqa: E402
from lunrwatch.util import FetchError, UTC, iso, read_json  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = read_json(os.path.join(ROOT, "config", "rules.json"), None)
CFG = {"sources": [
    {"id": "sec", "name": "TEST SEC", "type": "sec", "tier": "sec", "critical": True, "enabled": True, "relevance": "self", "cik": "1", "url": "x"},
    {"id": "news", "name": "TEST NEWS", "type": "rss", "tier": "media", "critical": False, "enabled": True, "relevance": "name", "url": "x"},
    {"id": "ir", "name": "TEST IR", "type": "unsupported", "tier": "official", "enabled": False, "note": "未対応"},
]}
T0 = datetime(2026, 1, 10, 22, 0, tzinfo=UTC)  # = 日本時間 1/11 07:00


def entry(title, hours_ago, now, url=None, summary="", extra=None):
    return {"title": title, "url": url or "https://example.test/" + title.replace(" ", "-"),
            "published": iso(now - timedelta(hours=hours_ago)), "summary": summary, "extra": extra or {}}


def sec_entry(acc, form, items, hours_ago, now):
    return {"title": f"SEC Form {form}", "url": "https://example.test/sec/" + acc, "published": iso(now - timedelta(hours=hours_ago)),
            "summary": "", "extra": {"form": form, "items": items, "accession": acc, "cik": "1", "base": "b"}}


class FakeWorld:
    def __init__(self):
        self.sec, self.news, self.fail = [], [], set()

    def fetchers(self):
        def mk(name, getter):
            def f(src, cutoff):
                if name in self.fail:
                    raise FetchError("HTTP 503")
                return [e for e in getter() if e["published"] >= iso(cutoff)] if name == "sec" else getter()
            return f
        return {"sec": mk("sec", lambda: self.sec), "rss": mk("news", lambda: self.news)}


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.w = FakeWorld()

    def tearDown(self):
        self.tmp.cleanup()

    def run_at(self, now):
        store = Store(self.dir)
        return run_collect(CFG, RULES, store, now=now, fetchers=self.w.fetchers(), enrich=False), Store(self.dir)

    def day(self, store, date):
        return build_site(store, CFG, os.path.join(self.dir, "site"))["days"].get(date)

    def test_first_run_is_baseline_not_new(self):
        self.w.news = [entry("Intuitive Machines wins NASA task order", 200, T0)]
        self.w.sec = [sec_entry("0001-26-1", "8-K", ["2.02"], 100, T0)]
        _, st = self.run_at(T0)
        self.assertEqual(len(st.items), 2)
        self.assertTrue(all(i["baseline"] for i in st.items.values()))
        d = self.day(st, "2026-01-11")
        self.assertEqual(d["important"], [])
        self.assertTrue(d["baseline"])

    def test_rerun_no_duplicates_and_new_item_detected(self):
        self.w.news = [entry("Intuitive Machines wins NASA task order", 200, T0)]
        self.run_at(T0)
        t1 = T0 + timedelta(days=1)
        self.w.news.append(entry("Intuitive Machines IM-3 launch delayed", 3, t1, summary="x" * 100))
        self.w.sec = [sec_entry("0001-26-2", "8-K", ["2.02", "9.01"], 2, t1)]
        self.run_at(t1)
        _, st = self.run_at(t1)  # 同じ内容でもう一度（再実行）
        self.assertEqual(len(st.items), 3)
        new = [i for i in st.items.values() if not i["baseline"]]
        self.assertEqual(len(new), 2)
        d = self.day(st, "2026-01-12")
        self.assertEqual(len(d["important"]), 1)  # 打ち上げ延期（本文あり）
        self.assertEqual(len(d["review"]), 1)     # 8-K決算：本文未確認なので「重要」ではなく「要確認」
        sec = next(i for i in new if i["tier"] == "sec")
        self.assertEqual((sec["short_term"], sec["direction"]), ("重要", "不明"))
        news = next(i for i in new if i["tier"] == "media")
        self.assertEqual(news["direction"], "マイナス")
        self.assertTrue(any("暫定" in r for r in news["reasons"]))

    def test_no_news_day_is_not_failure(self):
        self.w.news = [entry("Intuitive Machines wins NASA task order", 200, T0)]
        self.run_at(T0)
        t1 = T0 + timedelta(days=1)
        _, st = self.run_at(t1)
        d = self.day(st, "2026-01-12")
        self.assertEqual(d["level"], "complete")
        self.assertEqual(d["important"], [])
        self.assertEqual(d["clusters"], {})

    def test_partial_and_total_failure_are_distinguished(self):
        self.run_at(T0)
        t1 = T0 + timedelta(days=1)
        self.w.fail = {"sec"}
        _, st = self.run_at(t1)
        d = self.day(st, "2026-01-12")
        self.assertEqual(d["level"], "incomplete")  # 重要な情報源(sec)が失敗
        t2 = t1 + timedelta(days=1)
        self.w.fail = {"sec", "news"}
        _, st = self.run_at(t2)
        self.assertEqual(self.day(st, "2026-01-13")["level"], "all_failed")
        self.assertEqual(st.state["sources"]["sec"]["last_success"], iso(T0))  # 失敗では最終成功が進まない
        failed = [s for s in st.runs[-1]["sources"] if s["status"] == "failed"]
        self.assertEqual(failed[0]["error"], "HTTP 503")
        self.assertIn("unsupported", [s["status"] for s in st.runs[-1]["sources"]])

    def test_recovery_after_failure_collects_missed_items(self):
        self.run_at(T0)
        self.w.fail = {"sec"}
        self.run_at(T0 + timedelta(days=1))
        # 失敗中(1日前)に出た開示が、復旧後の実行で新規として回収される
        t2 = T0 + timedelta(days=2)
        self.w.fail = set()
        self.w.sec = [sec_entry("0001-26-3", "10-Q", [], 30, t2)]
        _, st = self.run_at(t2)
        it = next(iter(st.items.values()))
        self.assertFalse(it["baseline"])
        self.assertEqual(it["short_term"], "重要")

    def test_old_article_appearing_later_is_not_new(self):
        self.w.news = [entry("Intuitive Machines wins NASA task order", 200, T0)]
        self.run_at(T0)
        t1 = T0 + timedelta(days=1)
        self.w.news.append(entry("Intuitive Machines IM-1 lander tipped over", 24 * 90, t1))  # 90日前の記事が突然現れる
        _, st = self.run_at(t1)
        self.assertTrue(all(i["baseline"] for i in st.items.values()))

    def test_duplicate_coverage_is_clustered_primary_preferred(self):
        self.w.news = []
        self.run_at(T0)
        t1 = T0 + timedelta(days=1)
        self.w.news = [
            entry("NASA selects Intuitive Machines for lunar communications services", 5, t1, url="https://a.test/1"),
            entry("NASA selects Intuitive Machines for lunar communications services - SomeSite", 4, t1, url="https://b.test/2"),
        ]
        _, st = self.run_at(t1)
        self.assertEqual(len({i["cluster_id"] for i in st.items.values()}), 1)
        d = self.day(st, "2026-01-12")
        self.assertEqual(len(d["clusters"]), 1)

    def test_irrelevant_and_noise_filtered(self):
        self.w.news = [entry("Rocket Lab launches new satellites", 3, T0),
                       entry("Intuitive Machines (NASDAQ:LUNR) Stock Price Down 2.1% - Here's Why", 3, T0)]
        run, st = self.run_at(T0)
        self.assertEqual(len(st.items), 0)
        self.assertEqual(next(s for s in run["sources"] if s["id"] == "news")["irrelevant"], 2)

    def test_reload_persisted_data_identical(self):
        self.w.news = [entry("Intuitive Machines IM-3 launch delayed", 3, T0)]
        _, st = self.run_at(T0)
        again = Store(self.dir)
        self.assertEqual(st.items, again.items)
        self.assertEqual(st.runs, again.runs)

    def test_sec_enrich_requires_contact_and_extracts_exhibit(self):
        calls = []
        def fake(url, **kw):
            calls.append(url)
            if url.endswith("index.json"):
                return json.dumps({"directory": {"item": [{"name": "a8k.htm"}, {"name": "lunr-20260630xexx991.htm"}]}}).encode()
            return b"<html><body><h1>Q results</h1><p>Revenue was <b>X</b>.</p></body></html>"
        orig, S.http_get, S.SEC_PACE = S.http_get, fake, 0
        try:
            e = sec_entry("0001-26-9", "8-K", ["2.02"], 1, T0)
            os.environ.pop("LUNRWATCH_CONTACT", None)
            self.assertIsNone(S.enrich_sec_8k(e))
            self.assertEqual(calls, [])  # 連絡先なしではwww.sec.govへアクセスしない
            os.environ["LUNRWATCH_CONTACT"] = "test@example.invalid"
            self.assertEqual(S.enrich_sec_8k(e), "Q results Revenue was X .")
        finally:
            S.http_get = orig
            os.environ.pop("LUNRWATCH_CONTACT", None)

    def test_schedule_13_forms_are_rated(self):
        self.w.sec = [sec_entry("0001-26-8", "SCHEDULE 13G/A", [], 1, T0)]
        _, st = self.run_at(T0)
        self.assertEqual(next(iter(st.items.values()))["short_term"], "参考")

    def test_unverified_primary_is_review_not_important_and_routine_is_not_flagged(self):
        self.run_at(T0)
        t1 = T0 + timedelta(days=1)
        self.w.sec = [sec_entry("0001-26-5", "8-K", ["1.01"], 2, t1), sec_entry("0001-26-6", "4", [], 2, t1),
                      sec_entry("0001-26-7", "ZZZ-UNKNOWN", [], 2, t1)]
        _, st = self.run_at(t1)
        by = {i["extra"]["accession"]: i for i in st.items.values()}
        self.assertEqual(by["0001-26-5"]["needs_review"], "新しい開示あり・本文未確認")
        self.assertIsNone(by["0001-26-6"]["needs_review"])        # Form 4 は定型（参考）
        self.assertIn("要確認", by["0001-26-7"]["needs_review"])   # 判定不能な一次情報は除外せず要確認
        d = self.day(st, "2026-01-12")
        self.assertEqual(len(d["review"]), 2)
        self.assertEqual(d["important"], [])

    def test_direction_is_conservative(self):
        self.run_at(T0)
        t1 = T0 + timedelta(days=1)
        self.w.news = [entry("Intuitive Machines awarded big contract by analysts say", 3, t1),
                       entry("Will Intuitive Machines win a contract?", 3, t1),
                       entry("Intuitive Machines could be selected for lunar program", 3, t1)]
        _, st = self.run_at(t1)
        self.assertTrue(all(i["direction"] == "不明" for i in st.items.values()), [i["direction"] for i in st.items.values()])

    def test_sec_8k_links_to_same_day_ir_release_and_media_recap_is_downgraded(self):
        CFG2 = {"sources": CFG["sources"] + [{"id": "ir", "name": "TEST IR", "type": "rss", "tier": "official", "critical": True, "enabled": True, "relevance": "self", "url": "x"}]}
        feeds = {"sec": [], "ir": [], "news": []}
        def mk(k):
            return lambda src, cutoff: [e for e in feeds[k] if e["published"] >= iso(cutoff)]
        fetchers = {"sec": mk("sec"), "rss": None}
        def rss(src, cutoff):
            return feeds["ir" if src["id"] == "ir" else "news"]
        fetchers["rss"] = rss
        def go(now):
            run_collect(CFG2, RULES, Store(self.dir), now=now, fetchers=fetchers, enrich=False)
            return Store(self.dir)
        go(T0)
        t1 = T0 + timedelta(days=1)
        feeds["ir"] = [entry("Intuitive Machines Reports Second Quarter 2026 Financial Results; Record Backlog", 5, t1, summary="HOUSTON ... " * 10)]
        feeds["sec"] = [sec_entry("0001-26-20", "8-K", ["2.02", "9.01"], 5, t1)]
        feeds["ir"].append(entry("Intuitive Machines Announces Date for Second Quarter 2026 Financial Results Conference Call", 4, t1))
        st = go(t1)
        by = {i["title"][:30]: i for i in st.items.values()}
        sec = next(i for i in st.items.values() if i["tier"] == "sec")
        res = next(i for i in st.items.values() if i["tier"] == "official" and "Reports" in i["title"])
        sched = next(i for i in st.items.values() if i["tier"] == "official" and "Date" in i["title"])
        self.assertEqual(sec["cluster_id"], res["cluster_id"])          # 同じ発表は1つの話題
        self.assertNotEqual(sec["cluster_id"], sched["cluster_id"])     # 日程告知とは結びつけない
        self.assertIsNone(sec["needs_review"])
        self.assertTrue(any("8-K本文そのものは未確認" in r for r in sec["reasons"]))
        self.assertEqual((sched["short_term"], sched["mid_term"]), ("参考", "参考"))
        self.assertEqual(res["direction"], "不明")                       # 決算見出しの "Record" で方向を断定しない
        # 10日後に、同じ四半期の決算を振り返る報道が出ても新材料にしない
        t2 = t1 + timedelta(days=10)
        feeds["news"] = [entry("Intuitive Machines Q2 miss prompts analyst target cuts", 2, t2)]
        st = go(t2)
        rc = next(i for i in st.items.values() if i["tier"] == "media")
        self.assertEqual(rc["recap_of"], res["id"])
        self.assertEqual(rc["short_term"], "参考")

    def test_amount_phrase_qualifier_is_reported(self):
        self.run_at(T0)
        t1 = T0 + timedelta(days=1)
        self.w.news = [entry("Intuitive Machines selected for program", 3, t1, summary="authorization to proceed with an anticipated value of more than $600 million for 30 months")]
        _, st = self.run_at(t1)
        it = next(iter(st.items.values()))
        self.assertTrue(any("限定語" in r and "$600 million" in r for r in it["reasons"]), it["reasons"])

    def test_gov_contract_record_matching_known_official_amount_is_not_new(self):
        CFG3 = {"sources": [
            {"id": "ir", "name": "TEST IR", "type": "rss", "tier": "official", "enabled": True, "relevance": "self", "url": "x"},
            {"id": "usa", "name": "TEST USA", "type": "usaspending", "tier": "gov", "enabled": True, "relevance": "self", "url": "x"}]}
        feeds = {"ir": [], "usa": []}
        fetchers = {"rss": lambda src, cutoff: feeds["ir"], "usaspending": lambda src, cutoff: feeds["usa"]}
        def go(now):
            run_collect(CFG3, RULES, Store(self.dir), now=now, fetchers=fetchers, enrich=False)
            return Store(self.dir)
        go(T0)
        t1 = T0 + timedelta(days=1)
        feeds["ir"] = [entry("Intuitive Machines Secures NASA CLPS Award", 400, t1, summary="Firm-fixed-price contract valued up to $148.3 million scales production")]
        feeds["usa"] = [entry("契約記録の更新: X1", 3, t1, extra={"award_id": "X1", "version": "v1", "obligated": 35683800.0, "potential": 148358178.0, "start_date": "2026-01-05", "end_date": "2027-08-30"})]
        st = go(t1)
        rec = next(i for i in st.items.values() if i["source_id"] == "usa")
        ir = next(i for i in st.items.values() if i["source_id"] == "ir")
        self.assertEqual(rec["recap_of"], ir["id"])
        self.assertEqual(rec["mid_term"], "参考")
        self.assertTrue(any("確定済み額 $35,683,800" in r and "最大額 $148,358,178" in r for r in rec["reasons"]))

    def test_contact_is_never_written_to_data_site_or_errors(self):
        import io, contextlib, urllib.request
        secret = "secret-contact-xyz@example.invalid"
        os.environ["LUNRWATCH_CONTACT"] = secret
        seen = {}
        class Boom(Exception):
            pass
        def fake_urlopen(req, timeout=0):
            seen["ua"] = req.headers.get("User-agent")
            raise OSError("connection refused for " + req.full_url)
        orig = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        try:
            cfg = {"sources": [{"id": "n", "name": "N", "type": "rss", "tier": "media", "critical": True, "enabled": True,
                                "relevance": "name", "url": "https://example.test/feed"}]}
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                import lunrwatch.util as U
                orig_sleep, U.time.sleep = U.time.sleep, lambda *_: None
                try:
                    store = Store(self.dir)
                    run_collect(cfg, RULES, store, now=T0)
                    build_site(Store(self.dir), cfg, os.path.join(self.dir, "site"))
                finally:
                    U.time.sleep = orig_sleep
        finally:
            urllib.request.urlopen = orig
            os.environ.pop("LUNRWATCH_CONTACT", None)
        self.assertIn(secret, seen["ua"])  # 送信先へのUser-Agentにだけ使われる
        blob = buf.getvalue()
        for root, _, files in os.walk(self.dir):
            for f in files:
                blob += open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
        self.assertNotIn(secret, blob)
        self.assertIn("接続失敗", blob)  # 失敗理由は短い定型文のみ

    def test_feed_parsers(self):
        rss = b"""<rss><channel><item><title>A &amp; B</title><link>https://x.test/a</link>
        <pubDate>Mon, 05 Jan 2026 10:00:00 GMT</pubDate><description>&lt;p&gt;hi&lt;/p&gt;</description></item>
        <item><title>no date</title><link>https://x.test/b</link></item></channel></rss>"""
        out = S.parse_feed(rss)
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0]["title"], out[0]["summary"], out[0]["published"]), ("A & B", "hi", "2026-01-05T10:00:00Z"))
        with self.assertRaises(FetchError):
            S.parse_feed(b"<html>not xml")


if __name__ == "__main__":
    unittest.main()
