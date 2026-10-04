"""ルールベースの関連判定・重要度判定。精密な投資分析ではなく、見出し・種別に基づく暫定の目安。"""
import re
from datetime import datetime

RANK = {"重要": 3, "注目": 2, "参考": 1, "未評価": 0}

THEME_FOLLOW = {
    "決算・財務": "売上・受注残・営業キャッシュフローの数値（原典で確認）",
    "受注・契約": "契約の確定額と最大枠の区別、期間、実際の発注の有無",
    "月面ミッション": "打ち上げ・着陸の日程と、予定に対する実績の差",
    "通信・衛星": "通信・衛星事業の受注・実績と収益化の時期",
    "資金調達・希薄化": "発行株数・価格・調達額と希薄化の規模",
    "政策・予算": "予算・調達方針の確定状況（案か成立か）と対象プログラム",
    "提携・競合": "LUNRの受注機会・競争環境への具体的な影響",
}


class Rules:
    def __init__(self, cfg):
        self.cfg = cfg
        f = lambda k: re.compile(cfg[k], re.I)
        self.self_name = f("self_name")
        self.peer_rel = f("peer_relevance")
        self.exclude = f("exclude_title")
        self.sched = f("sched_notice")
        self.results = f("results_title")
        self.qual = f("amount_qualifier")
        self.amount = re.compile(r"(?:\S+\s+){0,4}\$\s?[\d,.]+\s?(?:million|billion|M|B|k)?(?:\s+\S+){0,1}", re.I)
        self.neg = f("direction_negative")
        self.pos = f("direction_positive")
        self.uncertain = f("uncertain_words")
        self.short_imp = f("short_important")
        self.mid_imp = f("mid_important")
        self.themes = {k: re.compile(v, re.I) for k, v in cfg["themes"].items()}


def _first(rx, text):
    m = rx.search(text)
    return m.group(0) if m else None


def publisher_of(title, tier):
    """Google News形式「見出し - 媒体名」から媒体名を分ける。"""
    if tier == "aggregator" and " - " in title:
        head, pub = title.rsplit(" - ", 1)
        return head.strip(), pub.strip()
    return title, None


def classify_sec(entry, rules):
    ex = entry["extra"]
    form = ex["form"]
    cfg = rules.cfg
    base_form = form.replace("/A", "")
    if base_form.startswith("8-K"):
        keys = [k for k in ex["items"] if k in cfg["sec_8k_items"]]
        best = max((cfg["sec_8k_items"][k] for k in keys), key=lambda r: RANK[r["short"]], default=None)
        if best is None:
            return {"short_term": "未評価", "mid_term": "未評価", "direction": "不明", "themes": [],
                    "reasons": ["8-Kだが項目番号が不明または未対応のため未評価。"], "follow_ups": ["原文で内容を確認"]}
        reasons = [cfg["sec_8k_items"][k]["why"] for k in keys if k != "9.01"] or [best["why"]]
        themes = []
        for k in keys:
            t = cfg["sec_8k_items"][k]["theme"]
            if t not in themes and k != "9.01":
                themes.append(t)
        follow = []
        for k in keys:
            follow += [x for x in cfg["sec_8k_items"][k]["follow"] if x not in follow]
        mixed = any(cfg["sec_8k_items"][k]["direction"] == "混在" for k in keys)
        return {"short_term": best["short"], "mid_term": best["mid"], "direction": "混在" if mixed else "不明",
                "themes": themes or [best["theme"]], "reasons": reasons, "follow_ups": follow}
    rule = None
    if base_form.startswith("SCHEDULE 13"):
        base_form = "SC 13"
    for k in ("10-K", "10-Q", "DEF 14A", "S-3", "S-8", "424B", "SC 13", "144", "4"):
        if base_form == k or base_form.startswith(k):
            if k == "4" and base_form != "4":
                continue
            rule = cfg["sec_forms"][k]
            break
    if rule is None:
        return {"short_term": "未評価", "mid_term": "未評価", "direction": "不明", "themes": [],
                "reasons": [f"Form {form} は判定ルール未対応のため未評価。"], "follow_ups": ["原文で内容を確認"]}
    return {"short_term": rule["short"], "mid_term": rule["mid"], "direction": rule["direction"],
            "themes": [rule["theme"]], "reasons": [rule["why"]], "follow_ups": list(rule["follow"])}


def assess(entry, src, rules):
    """entry を判定し、関連なしなら None。戻り値は保存用の判定 dict。"""
    tier = src["tier"]
    if src["type"] == "sec":
        a = classify_sec(entry, rules)
        a.update(why_related="SEC開示（Intuitive Machines本人の提出書類）。", reliability="高",
                 relevance_hit="SEC提出書類")
        return a

    title, publisher = publisher_of(entry["title"], tier)
    text = f"{title} {entry['summary']}"
    if rules.exclude.search(title):
        return None  # 株価ページ・値動きだけの記事・個人予想などは対象外
    self_hit = _first(rules.self_name, text)
    self_in_title = _first(rules.self_name, title)
    peer_hit = _first(rules.peer_rel, text)
    mode = src["relevance"]

    if mode == "self":
        ok = True
    elif mode == "name":
        ok = bool(self_hit)
    else:  # peer: タイトルに関連語、または本文に異なる関連語が2種類以上（本文中の1回だけの言及は採用しない）
        kinds = {m.group(0).lower() for m in rules.peer_rel.finditer(text)}
        ok = bool(self_hit or _first(rules.peer_rel, title) or (len(kinds) >= 2 and tier != "gov"))
    if not ok:
        return None

    reasons = []
    themes = [t for t, rx in rules.themes.items() if rx.search(text)][:3]

    if src["type"] == "usaspending":
        ex = entry["extra"]
        why = "連邦政府の契約記録（USAspending）にIntuitive Machinesが受注者として登録された更新。"
        existing = bool(ex.get("start_date")) and (
            datetime.strptime(entry["published"][:10], "%Y-%m-%d") - datetime.strptime(ex["start_date"][:10], "%Y-%m-%d")).days > 120
        reasons.append("政府の契約データベースの更新。契約の確定額（obligation）と、オプションを含む最大額は別物で、将来の売上を保証しない。")
        if ex.get("potential") and ex.get("obligated") is not None and ex["potential"] > 0:
            reasons.append(f"確定済み額 ${ex['obligated']:,.0f} に対し、オプション等を含む最大額 ${ex['potential']:,.0f}（確定は最大額の{ex['obligated'] / ex['potential'] * 100:.1f}%）。")
        if existing:
            reasons.append(f"契約の開始日は {ex['start_date']} で、新規受注ではなく既存契約の更新（既知情報の可能性が高い）。")
            mid = "参考"
        else:
            mid = "注目"
        follow = ["確定額と最大額の差（今後の発注・オプション行使の見込み）を原典で確認", "既知の契約の更新か、新規の受注か"]
        return {"short_term": "参考", "mid_term": mid, "direction": "不明", "themes": themes or ["受注・契約"], "reasons": reasons,
                "follow_ups": follow, "why_related": why, "reliability": "高", "relevance_hit": "受注者名"}

    if self_hit:
        if tier in ("peer",):
            why = f"本文・見出しに『{self_hit}』を含む。競合・周辺企業の発表でLUNRとの関連が明示されている。"
        else:
            why = f"見出しまたは要約に『{self_hit}』を含み、LUNRの事業に直接関係する。"
    elif tier == "peer":
        why = f"競合・周辺企業の公式発表。『{peer_hit}』に関する内容でLUNRの機会・脅威になり得る（具体的な影響は本文で要確認）。"
    else:
        why = f"『{peer_hit}』に関する内容。LUNRの顧客・競合・政策環境に関係する可能性がある（具体的な関連は未確認）。"

    # 重要度
    s_hit = _first(rules.short_imp, title)
    m_hit = _first(rules.mid_imp, text)
    m_in_title = _first(rules.mid_imp, title)
    is_sched = bool(rules.sched.search(title))
    is_results = bool(rules.results.search(title)) and not is_sched
    primary_src = tier in ("gov", "official", "peer", "sec")
    opinion = title.rstrip().endswith("?") and tier in ("media", "aggregator")
    if opinion:
        short = mid = "参考"
        reasons.append("疑問形の見出しで、分析・意見記事の可能性が高い。新しい事実の報道としては扱わない。")
    elif is_sched:
        short = mid = "参考"
        reasons.append("決算説明会などの日程の告知で、業績・事業の内容そのものではない。")
        themes = themes or ["決算・財務"]
    else:
        if self_in_title and s_hit:
            short = "重要"; reasons.append(f"LUNR名と株価材料になり得る語『{s_hit}』が見出しにある。")
        elif self_hit and s_hit:
            short = "注目"; reasons.append(f"LUNRに関する記載があり、見出しに『{s_hit}』を含む。")
        elif self_in_title:
            short = "注目"; reasons.append("LUNR名が見出しにあるが、短期の材料になる語は見出しにない。")
        elif self_hit:
            short = "参考"; reasons.append("LUNRへの言及は要約中のみで、短期の材料になる語は見出しにない。")
        elif s_hit:
            short = "注目" if tier != "peer" else "参考"; reasons.append(f"LUNR名はないが、見出しに『{s_hit}』を含む。")
        else:
            short = "参考"; reasons.append("短期の株価材料を示す語は見出しにない。")
        if self_hit and m_hit and primary_src and (m_in_title or tier in ("official", "sec")):
            mid = "重要"; reasons.append(f"中長期の事業に関わる『{m_hit}』に言及。")
        elif self_hit or m_hit:
            mid = "注目"; reasons.append("LUNRまたは中長期の事業テーマに関係。" + (f"（『{m_hit}』）" if m_hit else ""))
        else:
            mid = "参考"
    # 金額表現：原文に出ている場合だけ引用し、限定語の有無を示す（確定受注額かどうかは判断しない）
    am = rules.amount.search(text)
    if am:
        phrase = am.group(0).strip()
        q = _first(rules.qual, phrase)
        if q:
            reasons.append(f"原文の金額表現『{phrase}』に限定語『{q}』があり、確定受注額とは限らない。")
        else:
            reasons.append(f"原文の金額表現『{phrase}』。確定額か最大枠かは原文で要確認。")

    # 影響方向（LUNR名が見出しにあり、断定を避ける条件を満たす場合のみ。語による暫定判定）
    direction = "不明"
    primary_src = tier in ("gov", "official", "peer", "sec")
    if is_sched:
        pass
    elif is_results and self_in_title:
        reasons.append("決算の見出しは、売上・利益・受注残・見通しを予想や前期と比べる必要があり、見出しの語からは良否を判定しない。")
    elif self_in_title:
        neg = _first(rules.neg, title)
        pos = _first(rules.pos, title)
        hedged = title.rstrip().endswith("?") or _first(rules.uncertain, title)
        if hedged:
            reasons.append("見出しが疑問形・推測表現のため、影響方向は判定しない。")
        elif neg and pos:
            direction = "混在"; reasons.append(f"見出しに肯定語『{pos}』と否定語『{neg}』が併存（文脈未確認の暫定判定）。")
        elif neg:
            direction = "マイナス"; reasons.append(f"見出しの語『{neg}』による暫定判定。文脈は未確認。")
        elif pos and primary_src:
            direction = "プラス"
            reasons.append(f"公式発表の見出しの語『{pos}』による暫定判定。契約の確定額か最大枠か、既発表の再掲かは未確認で、金額の大小は評価していない。")
        elif pos:
            reasons.append(f"見出しに『{pos}』があるが、報道のみで一次情報を確認していないため、プラス判定はしない。")
    if direction == "不明":
        reasons.append("影響方向は断定できないため不明。")

    # 確かさ
    if tier in ("gov", "official", "peer", "sec"):
        reliability = "高"
        reasons.append("発信元の公式発表（一次情報）。")
    else:
        reliability = "中"
        reasons.append("報道（一次情報での確認は未実施）。")
        if tier == "aggregator":
            reasons[-1] = "報道の集約サイト経由（原典・一次情報での確認は未実施）。"
    if _first(rules.uncertain, title):
        reliability = "低" if reliability == "中" else "中"
        reasons.append(f"見出しに推測・予定を示す語『{_first(rules.uncertain, title)}』があり、確定事実か要確認。")

    follow = [THEME_FOLLOW[t] for t in themes if t in THEME_FOLLOW][:3] or ["本文を読んでLUNRへの具体的な影響を確認"]
    return {"short_term": short, "mid_term": mid, "direction": direction, "themes": themes or ["提携・競合" if tier == "peer" else "その他"],
            "reasons": reasons, "follow_ups": follow, "why_related": why, "reliability": reliability,
            "relevance_hit": self_hit or peer_hit, "publisher": publisher, "headline": title}
