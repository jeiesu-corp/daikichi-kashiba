# scripts/

店舗HP `daikichi-kashiba.com` の運用用スクリプト。

## sync_daikichi_blog.py — 店長ブログ自動同期

大吉公式ブログ「店長ブログ 香芝畑店」（https://www.kaitori-daikichi.jp/blog/kashiba-hata）の最新3件を取得し、
`index.html` の `<!-- BLOG_RESULTS_START -->` 〜 `<!-- BLOG_RESULTS_END -->` の間をカードHTMLに書き換えます。
内容に変更がないときはファイルを更新しません（mtime も変えません）。

```bash
python3 scripts/sync_daikichi_blog.py               # 同期（変更があれば index.html を更新）
python3 scripts/sync_daikichi_blog.py --dry-run -v  # 書き込まず差分を表示
python3 scripts/sync_daikichi_blog.py --check-only  # 更新の要否だけ判定
python3 scripts/sync_daikichi_blog.py --commit-push # 更新したら git add/commit/push まで
```

| 終了コード | 意味 |
| --- | --- |
| 0 | 更新した（`--dry-run` / `--check-only` では「更新が必要」） |
| 10 | 変更なし（正常） |
| 1 | エラー（取得失敗・マーカー不在など） |

- サムネイルは個別記事ページ本文の先頭にある商品写真URLを直リンク（大吉サイトはReferer制限なし・実測200）。
  共通バナー（`ca368b950a150a889cf0` / `IMG_FREE_URL_TMP`）は除外。
- 定型タイトル末尾の「〇〇の高価買取なら信頼と実績の買取専門店『買取大吉 香芝畑店』へ」は自動で削除。
- 既に index.html に出ている記事URLの画像は再取得せず再利用（新着記事の分だけ追加通信）。
- 記事ページ取得に失敗した場合は、そのカードだけ画像なし・紹介文は一覧の抜粋で生成して続行。

### 定期実行の例

```cron
0 9 * * * cd /path/to/daikichi-kashiba && /usr/bin/python3 scripts/sync_daikichi_blog.py --commit-push || [ $? -eq 10 ]
```

（終了コード 10 = 変更なし は正常系なので、そのまま失敗扱いにしないこと）

## update_monthly_campaign.py — キャンペーンポップアップの月次差し替え

`index.html` の `<!-- CAMPAIGN_POPUP_START -->` 〜 `<!-- CAMPAIGN_POPUP_END -->` の間だけを、
その月の季節タイトル（例：11月「秋の特別感謝祭」／12月「歳末・冬の特別感謝祭」）で作り直します。
「香芝畑店限定！」「買取金額 30%UP」・注記3行・ボタン3つ・期限（その月の末日 23:59:59 JST）・
1日1回表示／`?campaign=1` で強制表示の制御は毎回そろえて出力します。

```bash
python3 scripts/update_monthly_campaign.py                  # 今日の月で差し替え
python3 scripts/update_monthly_campaign.py --month 12        # 12月分を生成（テスト用）
python3 scripts/update_monthly_campaign.py --month 12 --dry-run  # 書き込まず標準出力へ
python3 scripts/update_monthly_campaign.py --commit-push     # 差し替えたら git add/commit/push まで
python3 scripts/update_monthly_campaign.py --list            # 12か月分のタイトル一覧
```

| 終了コード | 意味 |
| --- | --- |
| 0 | 更新した |
| 10 | 変更なし（正常） |
| 1 | エラー（マーカー不在など） |

- タイトル・配色・装飾の表はスクリプト冒頭の `MONTHS`。文言を変えたいときはここを編集する。
- マーカーの中はスクリプトが生成する領域。手作業で編集しない（次の自動更新で上書きされる）。
- 毎月1日 08:30 の定期アクション（`scheduled-actions/🎉-香芝畑店月次キャンペーン自動更新`）から実行される。
