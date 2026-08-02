#!/bin/zsh
# ダブルクリックで最新版に更新するためのランチャー（半自動運用）
cd "$(dirname "$0")" || exit 1
echo "=== 登録支援機関登録簿 更新 $(date '+%Y-%m-%d %H:%M:%S') ==="
/usr/bin/python3 ./update_data.py "$@"
status=$?
echo
if [ $status -eq 0 ]; then
  echo "完了しました。index.html をブラウザで開き直してください。"
else
  echo "エラーで終了しました（終了コード $status）。"
fi
echo "このウィンドウは閉じて構いません。"
