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
| `com.fanda.tsk.update.plist` | launchd 用。毎週月曜 9:00 に自動実行 |
| `.github/workflows/update-data.yml` | GitHub Actions 用。毎週月曜 09:00 JST に自動実行してコミット |
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

### 自動（このマシン / launchd）

インストール済み。毎週月曜 9:00 に実行され、ログは `update.log` に残る。

```bash
launchctl list | grep com.fanda.tsk.update        # 動いているか確認
launchctl kickstart -k gui/$(id -u)/com.fanda.tsk.update   # 今すぐ 1 回実行
launchctl bootout gui/$(id -u)/com.fanda.tsk.update        # 停止（アンインストール）
```

> **置き場所について**: macOS のプライバシー保護（TCC）により、`~/Downloads` `~/Documents` `~/Desktop` 配下では launchd からの実行が `Operation not permitted` で失敗する（両方とも実測で失敗を確認済み）。そのためこのフォルダは保護対象外の **`~/fanda-tsk`** に置いている。別の場所へ移す場合も保護対象外のパスを選び、`com.fanda.tsk.update.plist` 内のパスを書き換えて `~/Library/LaunchAgents/` にコピーし直し、`launchctl bootout` → `bootstrap` で読み込み直すこと。

### 自動（GitHub / 全員で共有したい場合）

リポジトリにして push すると、`.github/workflows/update-data.yml` が毎週月曜 09:00 JST に実行され、変更があれば `index.html` をコミットする。GitHub Pages を有効にすれば、URL を開くだけで常に最新の名簿になる（MEMO・連絡済みは各自のブラウザに残る）。

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
