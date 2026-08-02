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

## データの持ち方

- **名簿データ**: `index.html` に埋め込み。ページを開いた時に `JSON.parse` するだけで、通信は一切しない。
- **利用者の入力**: ブラウザの localStorage に保存。**ブラウザごと・端末ごと**に保存され、ファイルには入らないので、`index.html` を差し替えても消えない。

  | キー | 内容 |
  |---|---|
  | `kanto_contacted_v1` | 「連絡済み」にした登録番号 |
  | `kanto_memo_v1` | MEMO 欄（登録番号がキー） |
  | `kanto_filters_v1` | 検索語・各フィルター・言語・ページ番号 |
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
