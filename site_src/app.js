"use strict";
(function () {
  var D = window.LUNR || { items: [], days: {}, sources: [], generated_at: null, last_run: null };
  var app = document.getElementById("app");
  var RANK = { "重要": 3, "注目": 2, "参考": 1, "未評価": 0 };
  var TIER = { sec: 5, gov: 4, official: 4, peer: 3, media: 2, aggregator: 1 };
  var TIER_LABEL = { sec: "SEC開示（一次）", gov: "政府機関（一次）", official: "企業公式（一次）", peer: "提携・競合の公式", media: "報道", aggregator: "報道（集約）", social: "SNS" };
  var LEVEL_LABEL = { complete: "全情報源を確認", partial: "一部の補助情報源が取得失敗", incomplete: "確認が不完全", all_failed: "全情報源の取得に失敗" };
  var STATUS_LABEL = { ok: "成功", failed: "失敗", unsupported: "未対応", pending: "未実行" };
  var byId = {}, clusters = {};
  D.items.forEach(function (it) { byId[it.id] = it; (clusters[it.cluster_id] = clusters[it.cluster_id] || []).push(it); });

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function safeUrl(u) { return /^https?:\/\//i.test(u || "") ? u : "#"; }
  var fmtDT = new Intl.DateTimeFormat("ja-JP", { timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
  function jst(iso) { return iso ? fmtDT.format(new Date(iso)).replace(/\//g, "-") + " JST" : "—"; }
  function jstDate(iso) { return new Date(new Date(iso).getTime() + 9 * 3600e3).toISOString().slice(0, 10); }
  function todayJst() { return jstDate(new Date().toISOString()); }

  function level(r) { return r >= 3 ? "imp" : r === 2 ? "note" : "ref"; }
  function badge(label, val, cls) { return '<span class="b ' + (cls || level(RANK[val] || 0)) + '">' + esc(label) + "：" + esc(val === "未評価" ? "要確認" : val) + "</span>"; }
  function dirCls(d) { return d === "プラス" ? "pos" : d === "マイナス" ? "neg" : d === "混在" ? "mix" : "unk"; }
  function primary(list) {  // 代表は、本文（抜粋）がある項目を優先し、次に一次情報性の高い発信元
    function has(i) { return i.body_status === "excerpt" || i.body_status === "summary" ? 1 : 0; }
    return list.slice().sort(function (a, b) { return has(b) - has(a) || (TIER[b.tier] || 0) - (TIER[a.tier] || 0) || (a.published_at < b.published_at ? -1 : 1); })[0];
  }
  function top(list) { return Math.max.apply(null, list.map(function (i) { return Math.max(RANK[i.short_term], RANK[i.mid_term]); })); }

  function novelty(it) {
    if (it.baseline) return "既出（初回取得・過去分）";
    if (it.recap_of) return "既知の再掲の可能性";
    var older = (clusters[it.cluster_id] || []).filter(function (o) { return o.id !== it.id && o.first_seen_at < it.first_seen_at; });
    return older.length ? "続報" : "新規";
  }

  function card(list, open, extraNote) {
    var p = primary(list);
    var others = list.filter(function (i) { return i.id !== p.id; });
    var nov = novelty(p);
    var prior = (clusters[p.cluster_id] || []).filter(function (o) { return o.first_seen_at < p.first_seen_at && o.id !== p.id; })
      .sort(function (a, b) { return a.published_at < b.published_at ? 1 : -1; }).slice(0, 1);
    var body = {
      headline_only: "見出しのみ取得。本文は未確認", summary: "配信元の要約・冒頭のみ取得（全文は未確認）",
      excerpt: "冒頭の抜粋のみ取得（全文は未確認）", metadata: "提出書類の種別・項目番号のみ。本文は未確認"
    }[p.body_status] || "";
    var h = '<details class="card"' + (open ? " open" : "") + "><summary>";
    h += '<div class="badges">' + (p.needs_review ? '<span class="b rev">' + esc(p.needs_review) + "</span>" : "") + badge("短期", p.short_term) + badge("中長期", p.mid_term) +
      '<span class="b ' + dirCls(p.direction) + '">方向：' + esc(p.direction) + "</span>" +
      '<span class="b tag">確かさ：' + esc(p.reliability) + '</span><span class="b ' + (nov === "新規" ? "new" : nov === "続報" ? "new" : "tag") + '">' + esc(nov) + "</span></div>";
    h += '<div class="t">' + esc(p.title) + "</div>";
    h += '<div class="src">' + esc(p.source_name) + (p.publisher ? "／" + esc(p.publisher) : "") + "｜発表 " + jst(p.published_at) + "</div></summary>";
    h += '<div class="body">';
    h += "<h3>事実（原文より。生成による補足なし）</h3>";
    h += '<p class="excerpt">' + (p.summary ? esc(p.summary) : "（見出しのみ。見出し：" + esc(p.title) + "）") + "</p>";
    h += '<p class="note-small">' + esc(body) + "。取得 " + jst(p.first_seen_at) + "</p>";
    h += "<h3>なぜLUNRに関係するか（ルール判定）</h3><p>" + esc(p.why_related) + "</p>";
    h += "<h3>判定理由（ルールによる目安。精密な投資分析ではありません）</h3><ul>" + p.reasons.map(function (r) { return "<li>" + esc(r) + "</li>"; }).join("") + "</ul>";
    if (p.follow_ups && p.follow_ups.length) h += "<h3>今後確認すべき点</h3><ul>" + p.follow_ups.map(function (r) { return "<li>" + esc(r) + "</li>"; }).join("") + "</ul>";
    if (prior.length) h += "<h3>続報：前回からの変化</h3><p>前回（" + jstDate(prior[0].published_at) + " " + esc(prior[0].source_name) + "）：" + esc(prior[0].title) + "<br>今回：" + esc(p.title) + '</p><p class="note-small">差分の要約は自動生成していません。両方の原文で確認してください。</p>';
    h += '<h3>テーマ</h3><div class="badges">' + p.themes.map(function (t) { return '<span class="b tag">' + esc(t) + "</span>"; }).join("") + "</div>";
    h += '<p><a class="btn" href="' + esc(safeUrl(p.url)) + '" target="_blank" rel="noopener noreferrer">原文を開く（' + esc(TIER_LABEL[p.tier] || p.tier) + "）</a></p>";
    if (others.length) {
      h += "<h3>同じ話題の他の情報 " + others.length + "件</h3><ul>" + others.map(function (o) {
        return '<li><a href="' + esc(safeUrl(o.url)) + '" target="_blank" rel="noopener noreferrer">' + esc(o.title) + "</a>（" + esc(o.source_name) + (o.publisher ? "／" + esc(o.publisher) : "") + "）</li>";
      }).join("") + "</ul>";
    }
    if (extraNote) h += '<p class="note-small">' + esc(extraNote) + "</p>";
    return h + "</div></details>";
  }

  function srcTable(sources) {
    var h = '<table><tr><th>情報源</th><th>状態</th><th>詳細</th></tr>';
    sources.forEach(function (s) {
      var det = "";
      if (s.status === "ok") det = "取得" + s.fetched + "件（新規" + s.added + "／重複" + s.duplicates + "／無関係" + s.irrelevant + "）<br>取得範囲 " + (s.range_from ? jst(s.range_from) + " 〜 " + jst(s.range_to) : "該当なし");
      else if (s.status === "failed") det = "失敗：" + esc(s.error || "");
      else det = esc(s.note || "");
      if (s.last_success) det += '<br><span class="note-small">最終成功 ' + jst(s.last_success) + "</span>";
      h += "<tr><td>" + esc(s.name) + (s.critical ? ' <span class="b tag">重要</span>' : "") + '</td><td class="st-' + s.status + '">' + (STATUS_LABEL[s.status] || s.status) + "</td><td>" + det + "</td></tr>";
    });
    return h + "</table>";
  }

  function dayView(date, isToday) {
    var d = D.days[date];
    if (!d) return "<h1>" + esc(date) + '</h1><p>この日の実行記録はありません。</p><a class="btn" href="#/days">日報一覧へ</a>';
    var imp = d.important.length, note = d.notable.length, rev = (d.review || []).length;
    var h = "";
    var failedNames = d.sources.filter(function (s) { return s.status === "failed"; }).map(function (s) { return s.name; });
    var stale = isToday && date !== todayJst();
    var heroCls = (!imp && rev) ? " warnhero" : "";
    h += '<div class="hero' + heroCls + '">';
    if (d.level === "all_failed") h += '<div class="big zero">取得に失敗しました。重要情報の有無は確認できていません</div>';
    else if (imp) h += '<div class="big">本日の重要な新情報：' + imp + "件</div>" + (rev ? '<div class="meta revline">他に、新しい開示 ' + rev + "件の本文が未確認です（要確認）</div>" : "");
    else if (rev) h += '<div class="big zero">本文を確認できた範囲では重要な新情報はありません。ただし、新しい開示 ' + rev + "件の本文が未確認です（要確認）</div>";
    else if (d.baseline) h += '<div class="big zero">初回取得日です。過去分はアーカイブに保存しました（「新情報」の判定は次回の実行から）</div>';
    else h += '<div class="big zero">確認できた範囲では、重要な新情報はありません' + (d.level === "complete" ? "" : "（確認は不完全）") + "</div>";
    if (d.level !== "all_failed") h += '<div class="meta">要確認 ' + rev + "件 ／ 注目 " + note + "件 ／ 参考 " + (Object.keys(d.clusters).length - imp - note - rev) + "件</div>";
    h += '<div class="meta">' + esc(date) + " の日報｜最終実行 " + jst(d.last_run) + "（この日 " + d.runs + "回）</div></div>";
    if (stale) h += '<div class="banner warn">最終実行は ' + esc(date) + " です（今日は " + todayJst() + "）。自動実行が止まっている可能性があります。<small>「取得状況」で確認してください。</small></div>";
    if (d.level === "all_failed") h += '<div class="banner bad">全情報源の取得に失敗<small>「情報なし」ではありません。' + esc(failedNames.join("、")) + "</small></div>";
    else if (d.level === "incomplete") h += '<div class="banner warn">確認が不完全<small>重要な情報源が取得できていません：' + esc(failedNames.join("、")) + "</small></div>";
    else if (d.level === "partial") h += '<div class="banner warn">一部の補助情報源が取得できていません<small>' + esc(failedNames.join("、")) + "</small></div>";
    if (d.baseline) h += '<div class="banner ok">初回取得：過去の記事はアーカイブに保存しましたが、「新情報」には数えていません。</div>';
    var ids = Object.keys(d.clusters);
    var groups = ids.map(function (c) { return d.clusters[c].map(function (i) { return byId[i]; }); });
    groups.sort(function (a, b) { return top(b) - top(a); });
    var revSet = {}; (d.review || []).forEach(function (c) { revSet[c] = 1; });
    var revGroups = groups.filter(function (x) { return revSet[x[0].cluster_id]; });
    groups = groups.filter(function (x) { return !revSet[x[0].cluster_id]; });
    if (revGroups.length) h += "<h2>要確認（" + revGroups.length + "件）</h2><p class=\"note-small\">新しい開示を検出しましたが、本文を確認できていないか、重要度を判定できません。重要度は書類の種別などによる暫定で、内容は評価していません。原文を確認してください。</p>" + revGroups.map(function (x) { return card(x, true); }).join("");
    var sec = [["重要", 3], ["注目", 2], ["参考", 1], ["未評価", 0]];
    sec.forEach(function (s) {
      var g = groups.filter(function (x) { return top(x) === s[1]; });
      if (!g.length) return;
      if (s[1] >= 2) h += "<h2>" + s[0] + "（" + g.length + "件）</h2>" + g.map(function (x, i) { return card(x, s[1] === 3 && i < 2); }).join("");
      else h += '<details class="more"><summary><b>' + s[0] + "（" + g.length + "件）を表示</b></summary>" + g.map(function (x) { return card(x, false); }).join("") + "</details>";
    });
    h += '<details class="more"><summary><b>この日の情報源ごとの取得結果</b></summary>' + srcTable(d.sources) + "</details>";
    h += '<p class="foot">判定は見出し・書類種別に基づくルールで、投資判断の代わりにはなりません。株価予測・売買推奨は行いません。</p>';
    return h;
  }

  function today() {
    var dates = Object.keys(D.days).sort();
    if (!dates.length) return '<div class="hero"><div class="big zero">まだ実行記録がありません</div><div class="meta">自動実行または手動実行の完了後に表示されます。</div></div>';
    return dayView(dates[dates.length - 1], true) + '<p><a class="btn" href="#/days">過去の日報</a><a class="btn" href="#/search">検索</a></p>';
  }

  function days() {
    var dates = Object.keys(D.days).sort().reverse();
    var h = "<h1>日報</h1>";
    if (!dates.length) return h + "<p>まだありません。</p>";
    dates.forEach(function (k) {
      var d = D.days[k];
      var rv = (d.review || []).length;
      var s = d.level === "all_failed" ? "取得失敗" : (d.important.length ? "重要 " + d.important.length + "件" : "重要な新情報なし") + (rv ? "／要確認 " + rv + "件" : "");
      var lv = d.level === "complete" ? "" : "｜" + LEVEL_LABEL[d.level];
      h += '<a class="row" href="#/day/' + k + '"><div><div class="d">' + k + '</div><div class="s">' + esc(s + lv) + "</div></div><div class=\"s\">注目 " + d.notable.length + " ›</div></a>";
    });
    return h;
  }

  var THEMES = ["決算・財務", "受注・契約", "月面ミッション", "通信・衛星", "資金調達・希薄化", "政策・予算", "提携・競合", "その他"];
  function search(params) {
    var q = params.q || "", imp = params.imp || "", th = params.th || "", dr = params.dr || "", base = params.base === "1";
    var h = "<h1>検索・絞り込み</h1>";
    h += '<input id="q" type="search" placeholder="キーワード（例：IM-3、NASA、offering）" value="' + esc(q) + '">';
    h += '<div class="filters"><select id="imp"><option value="">重要度：すべて</option><option value="3"' + (imp === "3" ? " selected" : "") + '>重要のみ</option><option value="2"' + (imp === "2" ? " selected" : "") + '>注目以上</option></select>';
    h += '<select id="th"><option value="">テーマ：すべて</option>' + THEMES.map(function (t) { return '<option' + (th === t ? " selected" : "") + ">" + t + "</option>"; }).join("") + "</select>";
    h += '<select id="dr"><option value="">影響方向：すべて</option>' + ["プラス", "マイナス", "混在", "不明"].map(function (t) { return '<option' + (dr === t ? " selected" : "") + ">" + t + "</option>"; }).join("") + "</select></div>";
    h += '<label class="chk"><input id="base" type="checkbox"' + (base ? " checked" : "") + "> 初回取得の過去分も含める</label>";
    var terms = q.toLowerCase().split(/\s+/).filter(Boolean);
    var res = D.items.filter(function (i) {
      if (!base && i.baseline) return false;
      if (imp && Math.max(RANK[i.short_term], RANK[i.mid_term]) < +imp) return false;
      if (th && i.themes.indexOf(th) < 0) return false;
      if (dr && i.direction !== dr) return false;
      var hay = (i.title + " " + i.summary + " " + i.source_name + " " + (i.publisher || "") + " " + i.themes.join(" ")).toLowerCase();
      return terms.every(function (t) { return hay.indexOf(t) >= 0; });
    });
    var seen = {}, groups = [];
    res.forEach(function (i) { if (!seen[i.cluster_id]) { seen[i.cluster_id] = 1; groups.push((clusters[i.cluster_id] || [i]).filter(function (o) { return res.indexOf(o) >= 0; })); } });
    h += '<div id="res"><p class="note-small">' + groups.length + "件の話題（" + res.length + "件の情報）。新しい順、最大50件表示。</p>" + groups.slice(0, 50).map(function (g) { return card(g, false); }).join("") + "</div>";
    return h;
  }

  function status() {
    var h = "<h1>取得状況</h1>";
    h += '<div class="hero"><div class="meta">最終実行 ' + jst(D.last_run) + "<br>サイト生成 " + jst(D.generated_at) + "</div></div>";
    h += "<p class=\"note-small\">「情報なし」と「取得失敗」は区別されます。未対応の情報源の内容は確認していません。</p>" + srcTable(D.sources);
    h += '<p class="foot">自動実行はGitHub Actionsの定期実行で、数分〜1時間程度遅れることがあります。</p>';
    return h;
  }

  function freshness() {
    if (!D.last_run) return "";
    var hrs = (Date.now() - new Date(D.last_run).getTime()) / 3600e3;
    if (hrs <= 36) return "";
    var days = Math.floor(hrs / 24);
    return '<div class="banner bad">情報が古い可能性があります：最終実行は ' + jst(D.last_run) + "（約" + days + "日前）<small>自動実行が止まっている可能性があります。GitHubのActionsタブで確認してください。「重要情報なし」ではなく「更新されていない」状態です。</small></div>";
  }

  function route() {
    var hash = location.hash.replace(/^#/, "") || "/";
    var parts = hash.split("?"), path = parts[0], params = {};
    (parts[1] || "").split("&").forEach(function (kv) { if (kv) { var p = kv.split("="); params[p[0]] = decodeURIComponent(p[1] || ""); } });
    var tab = "today", html;
    if (path === "/days") { tab = "days"; html = days(); }
    else if (path.indexOf("/day/") === 0) { tab = "days"; html = dayView(path.slice(5), false); }
    else if (path === "/search") { tab = "search"; html = search(params); }
    else if (path === "/status") { tab = "status"; html = status(); }
    else html = today();
    app.innerHTML = freshness() + html;
    Array.prototype.forEach.call(document.querySelectorAll(".tabs a"), function (a) { a.classList.toggle("on", a.getAttribute("data-tab") === tab); });
    if (tab === "search") bindSearch();
    window.scrollTo(0, 0);
  }

  function bindSearch() {
    function go() {
      var p = ["q=" + encodeURIComponent(document.getElementById("q").value), "imp=" + document.getElementById("imp").value,
        "th=" + encodeURIComponent(document.getElementById("th").value), "dr=" + encodeURIComponent(document.getElementById("dr").value),
        "base=" + (document.getElementById("base").checked ? "1" : "")];
      var h = "#/search?" + p.join("&");
      var focus = document.activeElement && document.activeElement.id, pos = focus === "q" ? document.getElementById("q").selectionStart : 0;
      history.replaceState(null, "", h);
      var scroll = window.scrollY;
      app.innerHTML = search(parseParams(h));
      bindSearch();
      window.scrollTo(0, scroll);
      if (focus) { var el = document.getElementById(focus); el.focus(); if (focus === "q") el.setSelectionRange(pos, pos); }
    }
    ["q", "imp", "th", "dr", "base"].forEach(function (id) { document.getElementById(id).addEventListener(id === "q" ? "input" : "change", go); });
  }
  function parseParams(h) { var p = {}; (h.split("?")[1] || "").split("&").forEach(function (kv) { if (kv) { var s = kv.split("="); p[s[0]] = decodeURIComponent(s[1] || ""); } }); return p; }

  window.addEventListener("hashchange", route);
  route();
})();
