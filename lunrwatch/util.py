"""共通ユーティリティ（標準ライブラリのみ）。"""
import html
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
UTC = timezone.utc
VERSION = "0.1.0"


def now_utc():
    return datetime.now(UTC).replace(microsecond=0)


def iso(dt):
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def jst_date(s):
    """ISO(UTC)文字列 → 日本時間の日付 'YYYY-MM-DD'。"""
    return parse_iso(s).astimezone(JST).strftime("%Y-%m-%d")


def user_agent():
    contact = os.environ.get("LUNRWATCH_CONTACT", "personal research tool, non-commercial")
    return f"lunr-watch/{VERSION} ({contact})"


class FetchError(Exception):
    pass


def http_get(url, *, data=None, headers=None, timeout=30, retries=2, max_bytes=8_000_000):
    """GET/POST。失敗時は FetchError（理由は短い日本語）。認証・アクセス制限の回避はしない。"""
    h = {"User-Agent": user_agent(), "Accept": "*/*"}
    h.update(headers or {})
    last = "不明なエラー"
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise FetchError("応答が大きすぎる")
                return body
        except FetchError:
            raise
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code in (401, 403, 404, 410):  # 制限・不存在は再試行しない
                break
        except Exception as e:  # タイムアウト・接続断など
            last = f"接続失敗（{type(e).__name__}）"
        time.sleep(1.5 * (attempt + 1))
    raise FetchError(last)


_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def strip_html(s, limit=None):
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s or "")
    s = html.unescape(_TAG.sub(" ", s))
    s = _WS.sub(" ", s).strip()
    return s[:limit] if limit else s


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def write_json_atomic(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)
