# LUNR Watch

LUNR（Intuitive Machines）の投資判断に影響しうる「新しい変化」を、1日1回自動収集し、iPhoneで30秒で確認する個人用ツール。**追加費用ゼロ**が条件。株価予測・売買推奨はしない。公開情報のみを扱い、保有株数などの個人情報は持たない。判定はルールベースの暫定の目安で、投資判断の代わりにはならない。

## 無料構成（2026-10-04 に公式ドキュメントで確認）

| 役割 | 採用 | 無料の条件 | 上限到達時 |
|---|---|---|---|
| 自動実行 | GitHub Actions（標準ランナー, `schedule`） | 公開リポジトリは標準ランナー無料（[docs](https://docs.github.com/en/actions/reference/usage-limits-billing-and-administration)） | 実行されないだけ。有料機能は使わない |
| 保存 | リポジトリ内 `data/`（JSON Lines） | 年数MB程度 | 追記が止まるだけ。コピーでバックアップ・移行可 |
| 閲覧 | GitHub Pages（Actions経由） | Freeプランでは公開リポジトリが必須（[docs](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site)） | 同上 |
| AI/翻訳 | 使わない | — | ルールベースの分類と定型説明のみ。原題・原文抜粋は英語のまま表示 |

カード登録・Claude/APIの従量課金は不要。**Pagesは公開URLになり、収集データも公開される**（公開情報のみ）。

## 情報源（実在確認 2026-10-04）

| ID | 情報源 | 状態 |
|---|---|---|
| im_ir | Intuitive Machines 公式IR プレスリリースRSS（`/rss/news-releases.xml`） | ⚠ ローカルPCからは取得可（直近10件・冒頭約300字の抜粋）。**GitHub Actions上では2026-10-04に4回ともタイムアウト**（原因は未特定）。その間は「確認が不完全」と表示し、SEC・報道で補う |
| sec_edgar | SEC EDGAR 公式API（8-K・10-Q/K・S-3・424B・Form 4等） | ✅ 一覧は取得可。Secret設定後、GitHub上で `www.sec.gov` の提出書類一覧も取得できた。8-K添付の抜粋は、判定パターン修正後の実取得を次回の新しい8-Kで確認 |
| usaspending | USAspending API（政府の契約記録） | ✅ 確定額（obligation）とオプション含む最大額を区別して取得 |
| nasa_news / spacenews_* | NASA・SpaceNews のRSS（3ページ分） | ✅ 月面・CLPS等の語が見出しにあるものだけ採用 |
| gnews_* | Google News RSS検索 | ✅ 報道の集約。株価ページ・値動き記事・別会社は除外 |
| firefly / astrobotic / ispace | 競合の公式RSS | ✅ 月面関連のみ採用 |
| x_social | X（SNS） | ❌ 未対応（無料で規約に沿った安定取得手段がない） |

- **公式IRについて**：RSSが404だったのは別のパスを試したため。正しいパスでは取得できる。一方、IRの詳細ページ（全文）は調査時に応答せず、RSS以外は未確認。
- **8-Kで公式発表の全部を代替できるとは限らない**。公式IR配信と8-Kは別の文書で、内容が同じとは限らない。
- 未対応・取得できない部分は画面に「未対応」「本文未確認」と表示し、確認済みとは扱わない。

### SECの連絡先（要設定）
`www.sec.gov`（8-K本文など）は、連絡先を含まないUser-Agentに**403**を返した（連絡先らしい文字列を含めると200）。SECはfair access方針でUser-Agentに連絡先の明示を求めている。連絡先をSecretで設定したGitHub上の実行では、同じ提出書類の一覧が取得できた（2026-10-04）。ただし常に取れるとは断定しない。
- 連絡先（メール等、本人のもの）をリポジトリの **Secret** `LUNRWATCH_CONTACT` に設定した後の初回実行で、8-Kの原文抜粋が取れるかを確認する。
- 未設定の間：開示の一覧（種別・日時・項目番号）だけ取得し、8-K/10-Q等は**「新しい開示あり・本文未確認」として要確認**に表示する。本文の内容は評価しない。

## 重要度の考え方

- 「収集できた」と「内容を判断できた」を分ける。本文を確認できていない一次情報（8-K等）は、重要と断定せず、日報の最上部の**「要確認」**に出す。定型の開示（Form 4等）は要確認にしない。判定不能な一次情報も除外せず要確認に残す。
- 短期／中長期の重要度（重要・注目・参考）、影響方向（プラス・マイナス・混在・不明）、確かさ、新規性（新規・続報・既知の再掲の可能性）を分けて表示し、**判定理由を必ず表示**する。
- 影響方向は、LUNR名が見出しにあり、疑問形・推測表現でない場合の語による「暫定」判定のみ。プラスは公式発表の契約獲得の動詞に限る。決算の見出しは語から良否を判定しない。
- 金額は、**確定額と最大枠を混同しない**：政府契約は両方を並記。報道・公式抜粋は「up to / more than / anticipated」等の限定語を検出して注意文を出す。
- 品質の点検結果：[docs/QUALITY_REVIEW.md](docs/QUALITY_REVIEW.md)。

## 取りこぼしと自動実行の制約

- **失敗日の取りこぼしの回収**：各情報源の「前回の正常取得」から再取得するが、成立するのは**情報源が掲載している範囲内**・**停止が約7日以内**の場合のみ。
  - RSSは直近の掲載分しか返さない（IR 10件、NASA 30件、競合はブログ全体など。日次の通常運用では十分だが、長期停止後は掲載から落ちた記事は回収できない）。
  - 取得対象期間（前回成功の36時間前〜最大7日）より古い記事は、新情報とは数えず、アーカイブのみに入れる。
  - 7日を超えて止まった場合は、復旧時に画面の取得状況と最終実行日時を確認し、必要なら原典を直接見る。
- **自動停止**：GitHub公式は「公開リポジトリでは、リポジトリの活動が60日間ない場合にスケジュール実行が自動で無効化される」と記載するが、**「活動」の定義は書かれていない**。毎日のデータコミット（ボットによる）が活動として数えられるかは**公式に確認できていない**ため、これに依存しない。
  - 画面は、最終実行から36時間を超えると全ページ最上部に**赤い警告**（「情報が古い可能性」）を出す（Pagesが更新されなくても、閲覧時刻で判定する）。
  - 月に一度ほど、ActionsタブでワークフローがEnabledのままか確認する。止まっていたら「Enable workflow」を押す。
- **実行時刻**：初期は日本時間7:17（UTC 22:17）。GitHubは毎時0分の高負荷時にscheduleが遅れると記載しているため、0分を避けている。数分〜1時間ほど遅れることがある。変更は [daily.yml](.github/workflows/daily.yml) の `cron` 1行。スケジュールはデフォルトブランチ上のワークフローだけが対象。

## 仕組み

```
cron → python -m lunrwatch run → data/(items.jsonl, runs.jsonl, state.json) をコミット
                              → site/ を生成 → GitHub Pages
```

- **新規性**：初回取得分と対象期間より古い記事は `baseline`（アーカイブのみ）。
- **重複**：SECは受理番号、報道はURL、契約記録は契約ID＋更新日時で一意化。同じ話題は見出しの類似でまとめ、決算の8-Kは同一発表の公式IR配信と統合。再実行しても増えない。
- **取得失敗と情報なしの区別**：重要な情報源（`critical`）の失敗＝「確認が不完全」、全失敗＝「重要情報の有無は確認できていません」。
- 設定：[config/sources.json](config/sources.json)（情報源の追加・無効化）、[config/rules.json](config/rules.json)（判定語）。

## 使い方

```
python -m lunrwatch run      # 収集・保存・サイト生成（Python 3.10+、標準ライブラリのみ）
python -m lunrwatch build    # サイトだけ再生成
python -m unittest discover -s tests -v
```

環境変数：`LUNRWATCH_DATA` / `LUNRWATCH_SITE` / `LUNRWATCH_CONTACT`（Actionsでは Secret から渡す）。ローカルでは `site/index.html` を開けば見られる。

## 公開手順

1. 公開リポジトリを作成し、このフォルダの内容をpushする（`data/` は初期の基準データ）。
2. Settings → Pages → Source を **GitHub Actions** にする。
3. Settings → Secrets and variables → Actions → **Secrets**（Variablesではない）に `LUNRWATCH_CONTACT`（本人の連絡先メール等）を設定する。連絡先はUser-Agentとしてsec.govへ送られるだけで、ログ・保存データ・HTML・エラー表示には出さない（テストで確認）。
4. Actions → `daily-collect` → **Run workflow** で手動実行する。成功するとPagesのURLが出る。
5. iPhoneのSafariでそのURLを開き、共有 → **ホーム画面に追加**。
