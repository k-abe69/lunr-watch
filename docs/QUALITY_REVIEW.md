# 抽出品質の点検（実データ・2026-10-04）

実データ108件（初回基準日）から代表14件を選び、内容を確認して判定の妥当性を点検した記録。**AIによる日次分析は使わない。** 内容の確認は、公式フィードの抜粋、USAspending API、外部報道の検索結果で行った（IR詳細ページと8-K本文は取得できていない。下記「確認の限界」）。

凡例：S=短期の株価材料、M=中長期の事業。取得範囲＝見出し／抜粋（配信元が付ける冒頭約300字）／本文。

| # | 原題・発表日・原典 | 取得範囲 | 分類・判定（修正後） | 内容の確認 | 妥当性・修正 |
|---|---|---|---|---|---|
| 1 | [Intuitive Machines Selected for Multi-Satellite Communications Infrastructure Program](https://investors.intuitivemachines.com/news-releases/news-release-details/intuitive-machines-selected-multi-satellite-communications)（2026-08-17、公式IR） | 抜粋（金額は抜粋の後ろで未取得） | S重要／M注目／方向プラス（暫定）／確かさ高。受注・契約、通信・衛星 | 外部報道：非公表顧客から「着手許可」を受けた案件で、**想定額は$600M超**（確定受注額ではない）、期間30か月 | 重要度は妥当。**「プラス」は見出しの語による暫定**で、確定額/最大枠は未確認と理由に明記している。抜粋に金額がないため金額は評価していない（限界） |
| 2 | [Reports Second Quarter 2026 Financial Results; Continues Record Backlog Expansion…](https://investors.intuitivemachines.com/news-releases/news-release-details/intuitive-machines-reports-second-quarter-2026-financial-results)（2026-08-13、公式IR。8-K Item 2.02と同一発表） | 抜粋 | S重要／M注目／方向**不明** | 外部報道：受注残は過去最高$1.8B、一方で売上$206.2M（予想$221.1M）・損失は予想より拡大、通期見通し$900M〜$1B据え置き＝**好悪が混在** | **誤判定を修正**：修正前は見出しの "Record" で「プラス」だった。決算見出しは語から方向を判定しない仕様にした |
| 3 | [Announces Date for Second Quarter 2026 Financial Results Conference Call](https://investors.intuitivemachines.com/news-releases/news-release-details/intuitive-machines-announces-date-second-quarter-2026-financial)（2026-07-28、公式IR） | 抜粋 | S参考／M参考／不明 | 決算発表日（8/13）の告知のみ | **誤判定を修正**：修正前は "financial results" でS重要だった。日程告知は重要度を上げない |
| 4 | [Books Order for Two IM 300 Platforms from New Customer](https://investors.intuitivemachines.com/news-releases/news-release-details/intuitive-machines-books-order-two-im-300-platforms-new-customer)（2026-09-01、公式IR） | 抜粋 | S注目／M注目／プラス（暫定） | 外部報道：顧客・契約額・納期はいずれも**非公表** | 妥当。金額を評価していない旨を理由に明記 |
| 5 | [Secures Sixth NASA CLPS Award…](https://investors.intuitivemachines.com/news-releases/news-release-details/intuitive-machines-secures-sixth-nasa-clps-award-establish-high)（2026-06-30、公式IR） | 抜粋（副見出しに金額） | S注目／M重要／プラス（暫定） | 抜粋に「Firm-fixed-price contract **valued up to $148.3 million**」。USAspending（#6）で確定済み$35.7M・最大$148.4Mと**一致** | 妥当。「valued up to」を限定語として検出し「確定受注額とは限らない」と表示 |
| 6 | USAspending 契約記録 80JSC026F7020（2026-09-22更新） | 契約記録の項目（詳細API） | S参考／M参考／不明／既知の再掲 | 確定済み$35,683,800／オプション含む最大$148,358,178（確定は24.1%）、期間2026-06-30〜2027-08-30 | **既知情報の再掲を修正**：修正前は「新規契約」でM注目。#5の公式発表と金額が一致するため既知として参考に下げた |
| 7 | USAspending 契約記録 80GSFC25CA007（NSN、2026-10-01更新） | 契約記録の項目（詳細API） | S参考／M参考／不明 | 確定済み**$1,015,000**に対し、オプション含む最大**$4,820,000,000**（確定は0.0%）、開始2025-02、既存契約の更新 | **最大枠と確定額の混同を修正**：修正前は一覧APIの$1,015,000だけを表示していた。両方を並記し、既存契約の更新として参考に |
| 8 | SEC Form 8-K（Items 2.02, 9.01）（2026-08-13） | メタ情報（項目番号）。本文未確認 | #2と同一の話題に統合。S重要／M重要。同一発表を公式IR配信で確認、8-K本文は未確認と理由に明記 | #2と同じ決算発表 | **重複を修正**：8-Kと決算IR配信を別々に掲載していた。決算（2.02）に限り同一話題へ統合 |
| 9 | SEC Form 8-K（Items 1.01, 7.01, 8.01, 9.01）（2026-08-03） | メタ情報のみ。**本文未確認** | **要確認**（新しい開示あり・本文未確認）。種別による暫定でS重要／M重要 | 内容不明。同日の「Goonhilly買収完了」配信と関係する可能性はあるが、同時期に別の発表（8/4 L3Harris）もあり推測になるため**結びつけない** | 妥当（確認済みと扱わず要確認に残す）。連絡先設定後に抜粋が取れるか要検証 |
| 10 | SEC Form 10-Q（2026-08-13） | メタ情報のみ。**本文未確認** | **要確認**。S重要／M重要（定期開示の種別による暫定） | 内容未確認 | 妥当（数値は評価していない） |
| 11 | SEC Form 4（2026-09-22ほか8件） | メタ情報のみ | S参考／M参考。要確認にはしない（定型） | 内容未確認（取引の種類は不明） | 妥当。定型の開示は要確認の山に入れない |
| 12 | Intuitive Machines Q2 miss prompts analyst target cuts（Google News経由、10-04付） | 見出しのみ | S参考／M参考／不明／**既知の再掲の可能性** | 外部報道：決算（8/13）後のアナリスト反応が中心。10/4付で新しい事実があるかは不明 | **修正**：決算の約7週間後の報道を新材料としていた。同じ四半期の公式決算が既にあるため再掲として参考に下げた（修正前は「マイナス」と断定していた） |
| 13 | Is LUNR Building a Full-Service Space Infrastructure Platform?（Google News経由、09-30付） | 見出しのみ | S参考／M参考／不明 | 疑問形の分析記事 | **修正**：修正前はS注目・M注目。疑問形の媒体記事は新事実として扱わない |
| 14 | [Astrobotic Awarded 2 NASA Contracts for CLPS Moon Base Missions](https://www.astrobotic.com/astrobotic-awarded-2-nasa-contracts-for-clps-moon-base-missions/)（2026-06-30、競合の公式） ほか Firefly $144M CLPS（同日） | 抜粋 | S参考／M注目／不明。提携・競合 | 同日にNASAのMoon Base向けCLPSが複数社へ発注（LUNRの第6次CLPSと同日）。競合の受注はLUNRの機会・脅威の両面がある | 妥当。LUNR名なし＝直接の影響は不明のまま。「Firefly $144M」は限定語なし→確定額か要確認と表示 |

## 除外した例（無関係・ノイズ）

Google Newsの43件を採用せず（例）：株価ページ（"stock price, news, quote…"）、"Intuitive Machines vs. Rocket Lab: Which Space Stock…"、"Why is … stock climbing today?"、"LunR Royalties (TSX:LUNR)"（別会社）。NASAの"APOD: Harvest Moon…"や宇宙望遠鏡の記事は、月面・CLPS等の関連語が見出しにないため除外。競合ブログ130件のうち月面と無関係な約100件も除外。

## 重点確認の結論

| 観点 | 結果 |
|---|---|
| 契約の最大枠と確定受注額の混同 | USAspendingで混同を発見→確定額と最大額を並記。報道・公式抜粋は「up to / more than / anticipated / valued」等の限定語を検出して注意文を出す。ただし金額が抜粋の後ろにある場合は検出できない |
| 既知情報の再掲 | 3件を発見→「同じ四半期の決算の後追い報道」「公式発表済みの金額と一致する契約記録」を再掲として参考に下げる処理を追加 |
| 単語だけで方向を断定 | 決算見出し（"Record"）で「プラス」にしていた誤りを修正。現在は、LUNR名が見出しにあり、疑問形・推測表現でなく、プラスは**公式発表**の契約獲得の動詞に限る。いずれも「暫定」と表示 |
| 同じ発表の重複 | 8-Kと決算IR配信の重複を統合。報道間は見出しの類似で統合するが、実データではまだ該当例が少なく、重複排除の効果は自動テストでのみ確認 |

## 確認の限界

- 公式IRのRSSは取得できたが、**配信される抜粋は冒頭約300字**。IR詳細ページは本調査では応答がなく（接続がタイムアウト）、全文は取得できていない。
- SECの `www.sec.gov` は、連絡先を含まないUser-Agentで403だった（連絡先らしき文字列を含めると200）。**403の原因がUser-Agentの形式だけかは未検証**。8-K本文の取得は、運用者の連絡先を設定した後の実取得で確認する。
- 上記「内容の確認」の外部報道は検索結果の要約に基づく二次情報で、一次の全文確認ではない。
- 判定は暫定のルールであり、数週間の運用で `config/rules.json` を調整する前提。
