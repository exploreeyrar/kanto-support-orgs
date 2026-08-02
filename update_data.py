#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
登録支援機関登録簿（出入国在留管理庁）の最新 Excel を取得し、index.html に埋め込まれた
関東圏データを更新する。

  https://www.moj.go.jp/isa/applications/ssw/nyuukokukanri07_00205.html

標準ライブラリのみで動作する（openpyxl 等の外部依存なし）。

使い方:
  python3 update_data.py                 # 公表ページを見て、新版があれば index.html を更新
  python3 update_data.py --check         # 新版の有無だけ確認（更新はしない / 新版ありなら終了コード 10）
  python3 update_data.py --force         # 前回と同じ版でも作り直す
  python3 update_data.py --xlsx a.xlsx   # 手元の Excel を使う（ダウンロードしない）
  python3 update_data.py --page page.html --xlsx a.xlsx   # 保存済みページ＋手元 Excel（完全オフライン）
  python3 update_data.py --dry-run       # 差分だけ表示して index.html は書き換えない
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import unicodedata
import urllib.request
import zipfile
from xml.etree import ElementTree as ET

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PAGE_URL = "https://www.moj.go.jp/isa/applications/ssw/nyuukokukanri07_00205.html"
SITE_ROOT = "https://www.moj.go.jp"
DEFAULT_HTML = os.path.join(BASE_DIR, "index.html")
STATE_PATH = os.path.join(BASE_DIR, "update_state.json")
CACHE_DIR = os.path.join(BASE_DIR, "cache")
USER_AGENT = "Fanda-TSK-list-updater/1.0 (personal use; weekly)"

KANTO_PREFS = ["東京都", "神奈川県", "埼玉県", "千葉県", "茨城県", "栃木県", "群馬県"]
ID_MONTHS = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
             "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NO_RE = re.compile(r"^\d{2}登-\d{6}$")


# ---------------------------------------------------------------- 取得

def fetch(url, binary=False):
    """URL でもローカルパスでも読めるようにしておく（オフライン検証用）。"""
    if not re.match(r"^https?://", url):
        mode = "rb" if binary else "r"
        with open(url, mode, **({} if binary else {"encoding": "utf-8", "errors": "ignore"})) as f:
            return f.read()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as res:
        raw = res.read()
    return raw if binary else raw.decode("utf-8", "ignore")


def parse_page(html):
    """公表ページから 日本語版 Excel の URL と『〇年〇月〇日現在』を取り出す。"""
    links = re.findall(r'<a[^>]+href="(/isa/content/(\d+)\.xlsx)"[^>]*>(.*?)</a>', html, re.S)
    if not links:
        raise SystemExit("公表ページから Excel のリンクを見つけられませんでした（ページ構成が変わった可能性）")
    href = content_id = None
    for h, cid, label in links:
        text = re.sub(r"<[^>]+>", "", label)
        if "英語" in text or "List of" in text:      # 英語版はスキップ
            continue
        href, content_id = h, cid
        break
    if href is None:
        href, content_id = links[0][0], links[0][1]

    date = None
    m = re.search(r"([0-9０-９]{4})年\s*([0-9０-９]{1,2})月\s*([0-9０-９]{1,2})日\s*現在", html)
    if m:
        y, mo, d = (int(unicodedata.normalize("NFKC", g)) for g in m.groups())
        date = datetime.date(y, mo, d)
    return {"url": SITE_ROOT + href, "content_id": content_id, "page_date": date}


# ---------------------------------------------------------------- Excel 解析

def _si_text(si):
    """ふりがな（rPh）を除いた本文だけを取り出す。"""
    parts = []
    for child in si:
        tag = child.tag[len(NS):] if child.tag.startswith(NS) else child.tag
        if tag == "t":
            parts.append(child.text or "")
        elif tag == "r":
            for rc in child:
                rtag = rc.tag[len(NS):] if rc.tag.startswith(NS) else rc.tag
                if rtag == "t":
                    parts.append(rc.text or "")
        # rPh（ふりがな）と phoneticPr は無視する
    return "".join(parts)


def load_shared_strings(zf):
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    return [_si_text(si) for si in root.findall(NS + "si")]


def col_of(ref):
    letters = re.match(r"([A-Z]+)", ref).group(1)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def sheet_rows(zf, shared):
    """シートを 1 行ずつ {列インデックス: 文字列} で返す。"""
    sheet_name = None
    for n in zf.namelist():
        if re.match(r"xl/worksheets/sheet\d+\.xml$", n):
            sheet_name = n
            break
    if not sheet_name:
        raise SystemExit("Excel 内にワークシートが見つかりません")

    with zf.open(sheet_name) as fh:
        row = {}
        cell_ref = cell_type = None
        value = inline = None
        for event, el in ET.iterparse(fh, events=("start", "end")):
            tag = el.tag[len(NS):] if el.tag.startswith(NS) else el.tag
            if event == "start":
                if tag == "row":
                    row = {}
                elif tag == "c":
                    cell_ref = el.get("r")
                    cell_type = el.get("t")
                    value = inline = None
            else:
                if tag == "v":
                    value = el.text
                elif tag == "is":
                    inline = _si_text(el)
                elif tag == "c":
                    text = ""
                    if cell_type == "s" and value is not None:
                        idx = int(value)
                        text = shared[idx] if 0 <= idx < len(shared) else ""
                    elif cell_type == "inlineStr":
                        text = inline or ""
                    elif value is not None:
                        text = value
                    text = (text or "").strip()
                    if text and cell_ref:
                        row[col_of(cell_ref)] = text
                    el.clear()
                elif tag == "row":
                    yield row
                    el.clear()


# ---------------------------------------------------------------- 値の正規化

EXCEL_EPOCH = datetime.date(1899, 12, 30)


def norm_date(v):
    """Excel のシリアル値・和文表記・ISO をすべて YYYY-MM-DD に揃える。"""
    s = (v or "").strip()
    if not s:
        return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    if re.match(r"^\d{4,6}(\.0+)?$", s):
        try:
            return (EXCEL_EPOCH + datetime.timedelta(days=int(float(s)))).isoformat()
        except (ValueError, OverflowError):
            return s
    m = re.match(r"^(\d{4})[/年](\d{1,2})[/月](\d{1,2})日?$", s)
    if m:
        y, mo, d = (int(g) for g in m.groups())
        try:
            return datetime.date(y, mo, d).isoformat()
        except ValueError:
            return s
    return s


def norm_phone(v):
    """数値として保存され先頭の 0 が落ちた電話番号を補う。
    1 セルに複数の番号が改行で入っていることがあるので、行ごとに処理して連結しない。"""
    out = []
    for line in re.split(r"[\r\n]+", (v or "").strip()):
        s = re.sub(r"[\s　]", "", line)
        if s.isdigit() and not s.startswith("0") and len(s) in (9, 10):
            s = "0" + s
        if s:
            out.append(s)
    return "\n".join(out)


# 複数事務所は「①…／②…」のように丸数字が前置される
MARKER_RE = re.compile(r"^[\s　]*(?:[①-⑳㉑-㉟㊱-㊿]|\(\d{1,2}\)|（\d{1,2}）)[\s　]*")


def strip_marker(v):
    s = (v or "").strip()
    while True:
        s2 = MARKER_RE.sub("", s)
        if s2 == s:
            return s.strip()
        s = s2


def pref_of(address):
    for p in KANTO_PREFS:
        if address.startswith(p):
            return p
    return ""


# ---------------------------------------------------------------- レコード組み立て

# 列: A登録番号 B登録年月日 C名称 D郵便番号 E所在地 F電話番号 G代表者
#     H事務所名 I事務所郵便番号 J事務所所在地 K支援内容 L開始予定日 M対応言語 N備考
C_NO, C_DATE, C_NAME, C_ZIP, C_ADDR, C_TEL, C_REP = 0, 1, 2, 3, 4, 5, 6
C_OFC_NAME, C_OFC_ZIP, C_OFC_ADDR, C_SUPPORT, C_START, C_LANG, C_REMARKS = 7, 8, 9, 10, 11, 12, 13


def build_records(zf):
    shared = load_shared_strings(zf)
    records = []
    total = 0
    current = None          # 作成中の 1 機関（関東圏外でも事務所行を拾うため常に保持）
    last_office_name = ""

    for row in sheet_rows(zf, shared):
        no = row.get(C_NO, "")
        if NO_RE.match(no):
            if current:
                records.append(current)
            total += 1
            hq_addr = strip_marker(row.get(C_ADDR, ""))
            current = {
                "no": no,
                "name": row.get(C_NAME, ""),
                "prefs": [],
                "offices": [],
                "phone": norm_phone(row.get(C_TEL, "")),
                "rep": row.get(C_REP, ""),
                "lang": row.get(C_LANG, ""),
                "date": norm_date(row.get(C_DATE, "")),
                "remarks": row.get(C_REMARKS, ""),
                "hq_addr": hq_addr,
            }
            hq_pref = pref_of(hq_addr)
            if hq_pref:
                current["prefs"].append(hq_pref)
            last_office_name = ""
        elif current is None:
            continue        # データ開始前のヘッダー行

        # 1 行目・継続行のどちらでも、事務所（H・I・J）があれば拾う
        ofc_name = strip_marker(row.get(C_OFC_NAME, ""))
        ofc_addr = strip_marker(row.get(C_OFC_ADDR, ""))
        if ofc_name:
            last_office_name = ofc_name
        if ofc_addr:
            ofc_pref = pref_of(ofc_addr)
            if ofc_pref:
                current["offices"].append({
                    "name": ofc_name or last_office_name or current["name"],
                    "address": ofc_addr,
                    "pref": ofc_pref,
                })
                if ofc_pref not in current["prefs"]:
                    current["prefs"].append(ofc_pref)

    if current:
        records.append(current)

    kanto = []
    for r in records:
        if not r["prefs"]:
            continue
        # 関東圏の事務所が 1 件もない（本社だけが関東圏）場合は本社を所在地として表示する
        if not r["offices"]:
            r["offices"] = [{"name": r["name"], "address": r["hq_addr"], "pref": r["prefs"][0]}]
        r["prefs"].sort(key=KANTO_PREFS.index)
        del r["hq_addr"]
        kanto.append(r)
    return kanto, total


# ---------------------------------------------------------------- index.html 更新

RAW_RE = re.compile(r'(<script type="application/json" id="raw-data">)(.*?)(</script>)', re.S)


def read_embedded(html):
    m = RAW_RE.search(html)
    if not m:
        raise SystemExit("index.html の raw-data ブロックが見つかりません")
    try:
        return json.loads(m.group(2))
    except json.JSONDecodeError:
        return []


def update_html(html, records, page_date):
    payload = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    html = RAW_RE.sub(lambda m: m.group(1) + payload + m.group(3), html, count=1)

    if page_date:
        ja = "{}年{}月{}日現在".format(page_date.year, page_date.month, page_date.day)
        idn = "per {} {} {}".format(page_date.day, ID_MONTHS[page_date.month], page_date.year)
        html = re.sub(r"[0-9０-９]{4}年\s*[0-9０-９]{1,2}月\s*[0-9０-９]{1,2}日\s*現在", ja, html)
        html = re.sub(r"per \d{1,2} (?:Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember) \d{4}", idn, html)
    return html


# ---------------------------------------------------------------- 状態ファイル

def load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="登録支援機関登録簿の最新版で index.html を更新する")
    ap.add_argument("--html", default=DEFAULT_HTML, help="更新する HTML（既定: 同じフォルダの index.html）")
    ap.add_argument("--page", default=PAGE_URL, help="公表ページの URL または保存済み HTML のパス")
    ap.add_argument("--xlsx", help="ダウンロードせずに使う Excel のパス")
    ap.add_argument("--page-date", help="公表日を YYYY-MM-DD で明示指定")
    ap.add_argument("--check", action="store_true", help="新版の有無だけ確認する（新版ありなら終了コード 10）")
    ap.add_argument("--force", action="store_true", help="前回と同じ版でも更新する")
    ap.add_argument("--dry-run", action="store_true", help="差分表示のみ。index.html は書き換えない")
    ap.add_argument("--no-backup", action="store_true", help="index.html.bak を作らない")
    args = ap.parse_args()

    state = load_state()
    info = {"url": None, "content_id": None, "page_date": None}

    if args.xlsx and args.page == PAGE_URL:
        info["content_id"] = os.path.splitext(os.path.basename(args.xlsx))[0]
    else:
        print("公表ページを確認中: {}".format(args.page))
        info = parse_page(fetch(args.page))
        print("  最新 Excel : {}".format(info["url"]))
        print("  公表日     : {}".format(info["page_date"] or "（不明）"))

    if args.page_date:
        info["page_date"] = datetime.date.fromisoformat(args.page_date)

    same = info["content_id"] and info["content_id"] == state.get("content_id")
    if args.check:
        if same:
            print("新版なし（前回と同じ {}）".format(info["content_id"]))
            return 0
        print("新版あり: {}".format(info["content_id"]))
        return 10
    if same and not args.force and not args.xlsx:
        print("新版なし。更新をスキップしました（--force で強制実行）")
        return 0

    # --- Excel を用意
    if args.xlsx:
        xlsx_path = args.xlsx
        blob = open(xlsx_path, "rb").read()
    else:
        os.makedirs(CACHE_DIR, exist_ok=True)
        xlsx_path = os.path.join(CACHE_DIR, "{}.xlsx".format(info["content_id"]))
        print("ダウンロード中 ...")
        blob = fetch(info["url"], binary=True)
        with open(xlsx_path, "wb") as f:
            f.write(blob)
    digest = hashlib.sha256(blob).hexdigest()
    print("Excel: {} ({:.1f} MB, sha256 {}…)".format(xlsx_path, len(blob) / 1048576, digest[:12]))

    # --- 解析
    with zipfile.ZipFile(xlsx_path) as zf:
        records, total = build_records(zf)
    records.sort(key=lambda r: r["no"])
    print("解析結果: 全国 {:,} 件 → 関東圏 {:,} 件".format(total, len(records)))

    bad_dates = [r["no"] for r in records if not re.match(r"^\d{4}-\d{2}-\d{2}$", r["date"] or "")]
    if bad_dates:
        print("  ※ 登録年月日を解釈できなかった機関: {} 件 ({} …)".format(len(bad_dates), ", ".join(bad_dates[:5])))

    # --- 差分
    html = open(args.html, encoding="utf-8").read()
    old = read_embedded(html)
    old_nos = {r["no"] for r in old}
    new_nos = {r["no"] for r in records}
    added = sorted(new_nos - old_nos)
    removed = sorted(old_nos - new_nos)
    print("差分: 現在 {:,} 件 → {:,} 件（新規 {} 件 / 抹消・圏外 {} 件）".format(
        len(old), len(records), len(added), len(removed)))
    if added:
        print("  新規: {}{}".format(", ".join(added[:10]), " …" if len(added) > 10 else ""))
    if removed:
        print("  消滅: {}{}".format(", ".join(removed[:10]), " …" if len(removed) > 10 else ""))
        print("  ※ 消滅した登録番号に『連絡済み』や MEMO を付けていた場合、その行は表示されなくなります"
              "（ブラウザの保存データ自体は残ります）")

    if args.dry_run:
        print("--dry-run のため index.html は変更していません")
        return 0

    # --- 書き換え
    if not args.no_backup:
        shutil.copy2(args.html, args.html + ".bak")
        print("バックアップ: {}".format(args.html + ".bak"))
    new_html = update_html(html, records, info["page_date"])
    with open(args.html, "w", encoding="utf-8") as f:
        f.write(new_html)
    print("更新完了: {} ({:.1f} MB)".format(args.html, len(new_html.encode("utf-8")) / 1048576))

    save_state({
        "content_id": info["content_id"],
        "page_date": info["page_date"].isoformat() if info["page_date"] else None,
        "sha256": digest,
        "records": len(records),
        "nationwide": total,
        "updated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
