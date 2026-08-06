# 登録支援機関登録簿 — 関東圏フィルター

出入国在留管理庁が公表している「登録支援機関登録簿」から関東圏（東京都・神奈川県・埼玉県・千葉県・茨城県・栃木県・群馬県）の機関を抽出して表示する 1 ファイル完結の検索ページ。

- 公表ページ: <https://www.moj.go.jp/isa/applications/ssw/nyuukokukanri07_00205.html>
- 現在の収録: **2026年7月28日現在 / 全国 11,494 件 → 関東圏 4,642 件**

## ファイル構成

| ファイル | 役割 |
|---|---|
| `index.html` | ページ本体。名簿データも `<script id="raw-data">` に JSON で内蔵しているので、これ 1 つで動く（サーバー不要） |
| `update_data.py` | 公表ページを見て最新 Excel を取得し、`index.html` の JSON と日付表記を書き換える。**標準ライブラリのみ**（外部パッケージ不要） |
| `update.command` | ダブルクリックで `update_data.py` を実行するランチャー |
| `.github/workflows/update-data.yml` | GitHub Actions 用。**平日 09:00〜22:00 の毎正時**（1 日 14 回）に自動実行してコミット |
| `update_state.json` | 前回取り込んだ Excel の content id / 公表日 / SHA-256 |
| `cache/` | ダウンロードした Excel の置き場（Git 管理外） |
| `worker/` | Telegram 送信を中継する Cloudflare Worker（Bot トークンの置き場） |

## データの持ち方

- **名簿データ**: `index.html` に埋め込み。ページを開いた時に `JSON.parse` するだけで、通信は一切しない。
- **利用者の入力**: ブラウザの localStorage に保存。**ブラウザごと・端末ごと**に保存され、ファイルには入らないので、`index.html` を差し替えても消えない。

  | キー | 内容 |
  |---|---|
  | `kanto_contacted_v1` | 「連絡済み」にした登録番号 |
  | `kanto_memo_v1` | MEMO 欄（登録番号がキー） |
  | `kanto_filters_v1` | 検索語・各フィルター・言語・「連絡済みを隠す」 |
  | `kanto_callback_v1` | 折り返し電話の予定に入れた登録番号 |
  | `kanto_fav_v1` | お気に入りに入れた登録番号 |
  | `kanto_settings_v1` / `kanto_memo_templates_v1` | 列の表示・動作・MEMO テンプレート（**版番号つき**、下記参照） |
  | `fda_countdown_v1` | 悬浮カウントダウンの位置と表示状態 |

  すべて**登録番号がキー**なので、名簿を更新しても「連絡済み」と MEMO は残る。逆に、抹消された機関の行は表示されなくなる（更新時のログに消えた登録番号が出る）。

## 更新のしかた

### 手動（いちばん簡単）

`update.command` をダブルクリック。または:

```bash
python3 "/Users/m4pro/fanda-tsk/update_data.py"
```

主なオプション:

```bash
python3 update_data.py --check      # 新版の有無だけ確認（新版ありなら終了コード 10）
python3 update_data.py --dry-run    # 差分だけ表示して書き換えない
python3 update_data.py --force      # 同じ版でも作り直す
python3 update_data.py --xlsx a.xlsx --page saved.html   # 完全オフラインで実行
```

実行すると `index.html.bak` にバックアップを取ってから書き換え、`新規 N 件 / 抹消 N 件`と登録番号を表示する。

### 自動（このマシン）

**設定していない。** 以前は launchd で定期実行していたが削除済み（`launchctl list | grep fanda` で何も出なければ解除できている）。
Mac 側は `update.command` をダブルクリックする手動運用のみ。定期更新は GitHub Actions が担当する。

### 自動（GitHub / 全員で共有したい場合）

リポジトリ <https://github.com/exploreeyrar/kanto-support-orgs> の `.github/workflows/update-data.yml` が**平日 09:00〜22:00 の毎正時**（cron は UTC の `0 0-13 * * 1-5`、1 日 14 回）に実行され、新版があれば `index.html` を書き換えてコミットする。新版が無い回は何もせず終了する（空コミットは作らない）。GitHub Pages を有効にすれば、URL を開くだけで常に最新の名簿になる（MEMO・連絡済みは各自のブラウザに残る）。

```bash
git init && git add -A && git commit -m "init" && git branch -M main
git remote add origin git@github.com:<user>/<repo>.git && git push -u origin main
```

## Excel の読み取りで気をつけている点

元データ（`001467099.xlsx` 相当）は 1 シート・9 行目からデータで、次のクセがある。`update_data.py` はこれらを吸収している。

1. **ふりがな**: 共有文字列に `<rPh>` でルビが入っており、素直に連結すると「事業アシスト協同組合ジギョウキョウドウクミアイ」になる → ルビを除外。
2. **複数事務所**: 2 つ目以降の事務所は登録番号のない継続行に入り、さらに `①②③` が名称・住所の頭に付く → マーカーを除去して `offices[]` にまとめる（従来データはここを取りこぼしていた）。
3. **登録年月日が Excel シリアル値**（`44333` など）→ `YYYY-MM-DD` に変換。
4. **電話番号の先頭 0 落ち**（数値として保存されたもの）→ 補完。1 セルに複数番号が改行で入る場合は連結しない。
5. **関東圏の事務所が無く本社だけ関東**の機関は、本社所在地を所在地として表示する。

## 左上のバッジ

ページ左上に `自動更新: YYYY-MM-DD HH:mm / データ取込: YYYY-MM-DD HH:mm` と表示される。

- **自動更新**: GitHub Actions のワークフローが最後に走った時刻。表示時に GitHub の公開 API
  (`/actions/workflows/update-data.yml/runs`) を 1 回だけ叩いて取得する。認証不要・公開リポジトリのみ。
  緑丸＝前回成功、赤丸＝前回失敗。オフラインや非公開リポジトリでは取得できず、この項目は表示されない。
- **データ取込**: `update_data.py` が最後に `index.html` を書き換えた時刻（＝名簿データが実際に更新された時刻）。
  スクリプトが HTML 内の `const DATA_BUILT_AT` を毎回書き換えている。

つまり「自動更新は動いているのにデータ取込が古い」＝ MOJ 側に新版が出ていないだけ、という読み方ができる。

## 連絡済みリストの共有（Telegram）

「連絡済みリストのみ表示」の隣にボタンが 2 つある。

- **📤 Telegram に送信**: 現在「連絡済み」にしている機関を、電話番号を識別子として Telegram に POST する
  （宛先はグループ `-5192236586`「bodoh JP」）。書式は次のとおりで、4096 文字の上限を超える場合は
  自動的に複数通に分割して順に送る（分割時は各通の 1 行目に同じ挨拶文が入る）。

  ```
  Saya telah menghubungi TSK berikut ini.
  #FANDA_TSK_CONTACTED v1
  2026-08-04 09:57 / 2 件

  09047391101 | 26登-013677 | 国際連携学舎合同会社
  0272266701 | 26登-013693 | 株式会社ライフライン
  ↳ MEMO: 7/30 TEL済み / 担当: 山田さん 折返し待ち
  ```

  MEMO がある機関はその機関の行の直後に `↳ MEMO:` 行が付く。MEMO 内の改行は ` / ` に潰して
  必ず 1 行に収めている（取り込み側が MEMO 内の数字を電話番号と誤認しないため）。
- **✏️ MEMO の単票送信**: MEMO 編集モーダルに「Telegram に送信する」チェックボックス（既定オン）があり、
  保存と同時にその 1 件だけを送る。編集中はプレビューが即時更新され、文字数を `n / 4096` で表示する
  （超過時は赤字になり送信をブロック）。本文は次の形。

  ```
  #FANDA_TSK_MEMO v1
  株式会社ライフライン
  電話番号: 0272266701
  関東圏内の所在地: 群馬県前橋市下大島町５２４番地１２
  登録年月日: 2026-07-28

  MEMO:
  7/30 TEL済み
  担当: 山田さん 折返し待ち
  ```

  ラベルは表示中の言語（日本語 / インドネシア語）に従う。保存は送信より先に行うので、
  送信に失敗しても入力内容は失われない。チェックを外すとプレビューは隠れ、ボタンは「保存」に戻る。
- **📥 リストを取り込む**: Telegram のメッセージをそのまま貼り付けて取り込む。電話番号で照合し、
  この端末の「連絡済み」に**追加**する（既存は消えない）。挨拶文・ヘッダー行・日時行・`↳ MEMO:` 行は無視し、
  ハイフンや空白入りの番号、素の番号だけの一覧も読める。同じ電話番号を複数の機関が使っている場合
  （実データで 48 番号・99 機関）は、その全機関が連絡済みになる。

### 送信経路（Bot トークンはページに持たせない）

```
ブラウザ ──POST text──▶ Cloudflare Worker ──sendMessage(token)──▶ Telegram
```

`index.html` にトークンは無く、`TG_ENDPOINT` に Worker の URL だけを書く。トークンは Worker の Secret に置く。
URL が漏れても任意のメッセージは送れないよう、Worker 側で次を強制している。

| 制限 | 返す HTTP |
|---|---|
| POST 以外 | 405 |
| `ALLOWED_ORIGINS` に無い Origin | 403 |
| 本文に `#FANDA_TSK_` を含まない | 400 |
| 本文が 4096 文字超 | 413 |
| `APP_KEY` を設定した場合、`X-App-Key` 不一致 | 403 |

#### デプロイ手順

```bash
cd worker
npx wrangler login                 # ブラウザで Cloudflare にログイン
npx wrangler secret put TG_TOKEN   # 聞かれたら Bot トークンを貼る（画面には残らない）
npx wrangler deploy                # 表示された https://....workers.dev を控える
```

デプロイ後、`index.html` の `TG_ENDPOINT` をその URL に書き換える。
GitHub Pages 以外のドメインから使う場合は `wrangler.toml` の `ALLOWED_ORIGINS` に追記して再デプロイする
（`file://` で開く場合の Origin は文字列 `null`）。

動作確認:

```bash
curl -i -X POST "https://<URL>" -H "Origin: null" \
  --data-urlencode 'text=#FANDA_TSK_CONTACTED v1
test'
```

#### 注意

- トークンは公開リポジトリにコミットされたことはない（`main` の `index.html` を検索して確認済み）。
  ただし平文でやり取りした経緯があるため、気になる場合は @BotFather の `/revoke` で作り直し、
  `npx wrangler secret put TG_TOKEN` で入れ直せばよい（ページ側の変更は不要）。
- 送信先は `wrangler.toml` の `TG_CHAT`。現在はグループ `-5192236586`（`bodoh JP`）で、Bot が
  メンバーかつ `can_send_messages: true` であることを確認済み。変更したら `npx wrangler deploy` で反映する。

## 一覧の操作まわり

- **表示**: ページ送りは無し。下までスクロールすると 100 件ずつ自動で継ぎ足される（`BATCH`）。
- **連絡済みを隠す**: 一覧上部のチェック。通常表示のときだけ効く。
- **折り返し電話の予定 / お気に入り**: MEMO 編集モーダルのチェックで登録。1 件でも入っていると右下に
  黄色（📞 折り返し予定）と赤（⭐ お気に入り）の浮動ボタンが出る。押すとその集合だけの一覧に切り替わり、
  「操作」列のチェックで一覧から外せる（＝折り返し済み／お気に入り解除）。もう一度ボタンを押すと通常表示に戻る。
- **地名の言語**: インドネシア語表示のときは都道府県と東京都の市区町村をローマ字（Tokyo / Shibuya …）で表示する。
  元の日本語は各要素の `title` に残してあるのでマウスを乗せれば確認できる。

## 設定の配り方（index.html を push せずに揃える）

`kanto_settings_v1` と `kanto_memo_templates_v1` は `{ v: DEFAULTS_VERSION, data: … }` の形で保存する。
読み込み時に `v` が現在の `DEFAULTS_VERSION` と一致しない保存データは**無視して既定値を使う**。つまり:

- ユーザーが設定画面で明示的に「保存」したときだけ、その内容が次回以降も使われる。
- 既定値を配り直したいときは `index.html` の `const DEFAULTS_VERSION` を +1 して配る。
  全員のカスタム設定が新しい既定値で上書きされる。
- **push せずに揃えたい場合**は設定画面の「設定の配布」で `現在の設定をコピー` → 相手に渡して
  `貼り付けた設定を適用`。列の表示・動作・MEMO テンプレートだけが移る。

いずれの経路でも、**「連絡済み」「MEMO」「フィルター」「折り返し」「お気に入り」は絶対に初期化されない**
（別キーで保存しており、この仕組みは触らない）。
