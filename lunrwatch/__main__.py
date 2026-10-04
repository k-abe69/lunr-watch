"""使い方:
  python -m lunrwatch run      収集して保存し、サイトも生成する
  python -m lunrwatch build    保存済みデータからサイトだけ再生成する
環境変数: LUNRWATCH_DATA（データ保存先, 既定 data）, LUNRWATCH_SITE（出力先, 既定 site）,
          LUNRWATCH_CONTACT（SEC等へ送るUser-Agentの連絡先）, LUNRWATCH_SOURCES（情報源設定の上書き）
"""
import os
import sys

from .build import build_site
from .store import Store, run_collect
from .util import read_json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def probe():
    """実行環境から一次情報へ届くかの診断。状態と長さだけを表示し、連絡先などは出さない。常に正常終了。"""
    import json as _json
    from . import sources as S
    from .util import FetchError, http_get
    contact = "設定あり" if "@" in os.environ.get("LUNRWATCH_CONTACT", "") else "未設定"
    print(f"連絡先: {contact}")
    for name, url in [("公式IR RSS", "https://investors.intuitivemachines.com/rss/news-releases.xml"),
                      ("SEC 提出一覧(data.sec.gov)", "https://data.sec.gov/submissions/CIK0001844452.json"),
                      ("SEC 提出書類(www.sec.gov)", "https://www.sec.gov/Archives/edgar/data/1844452/000162828026056476/index.json")]:
        try:
            body = http_get(url, timeout=20, retries=0)
            print(f"[ok  ] {name}: {len(body)}バイト")
        except FetchError as e:
            print(f"[fail] {name}: {e}")
    entry = {"extra": {"base": "https://www.sec.gov/Archives/edgar/data/1844452/000162828026056476"}}
    text = S.enrich_sec_8k(entry)
    print("8-K添付の抜粋取得:", f"成功（{len(text)}文字）" if text else "取得なし（本文未確認として表示）")
    return 0


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "run"
    data_dir = os.environ.get("LUNRWATCH_DATA", os.path.join(ROOT, "data"))
    site_dir = os.environ.get("LUNRWATCH_SITE", os.path.join(ROOT, "site"))
    sources = read_json(os.environ.get("LUNRWATCH_SOURCES", os.path.join(ROOT, "config", "sources.json")), None)
    rules = read_json(os.path.join(ROOT, "config", "rules.json"), None)
    store = Store(data_dir)
    if cmd == "run":
        run = run_collect(sources, rules, store)
        for s in run["sources"]:
            detail = (f"取得{s['fetched']}件 / 新規{s['added']}件 / 重複{s['duplicates']}件 / 無関係{s['irrelevant']}件"
                      if s["status"] == "ok" else s.get("error") or s.get("note", ""))
            print(f"[{s['status']:11}] {s['id']:16} {detail}")
        ok = sum(1 for s in run["sources"] if s["status"] == "ok")
        failed = sum(1 for s in run["sources"] if s["status"] == "failed")
        print(f"成功{ok} / 失敗{failed}")
    elif cmd == "probe":
        return probe()
    elif cmd != "build":
        print(__doc__)
        return 2
    build_site(store, sources, site_dir)
    print(f"サイト生成: {site_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
