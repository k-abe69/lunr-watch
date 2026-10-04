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
    elif cmd != "build":
        print(__doc__)
        return 2
    build_site(store, sources, site_dir)
    print(f"サイト生成: {site_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
