// ==UserScript==
// @name         PearsonVUE JP お問合せフォーム 自動入力
// @namespace    https://github.com/local/pearsonvue-autofill
// @version      1.0.0
// @description  ピアソンVUE 受験者お問合せフォーム(Asia Pacific)を自動で埋める
// @author       you
// @match        https://www.pearsonvue.com/*/test-takers/customer-service/email/email-form-asia-pacific.html*
// @run-at       document-idle
// @grant        none
// ==/UserScript==

(function () {
  'use strict';

  /* ===================== ここを書き換えて使う ===================== */
  const CONFIG = {
    // お問い合わせ内容: 1〜10 の番号、または選択肢の文字列の一部（例: 'パスワード'）
    inquiry: 6, // 6. 試験予約 / 変更 / キャンセルについて

    // 試験プログラム
    program:      'SSW-1: ビルクリーニング分野（ぶんや）特定技能（とくていぎのう）1号（ごう）評価試験（ひょうかしけん）',
    candidateId:  'JBMEXAM-00000019357', // 受験者ID
    orderNumber:  '543124593',           // 試験登録番号 / オーダー番号

    // 問い合わせ内容詳細
    detail: `ご担当者様

試験の申し込みですが、私の在留カードとパスポートの氏名には「FANDA HERA SAPUTRI」と表記されているんですけが、予約後に届いた「試験予約のご案内」メールには「受験者：　SAPUTRI HERA FANDA」と表示されてしまいました。「登録時に使用された氏名は、試験日にご提示いただく本人確認書類上の氏名と完全に一致する必要があります」と案内されているんですけど、前記で試験当日の受付に問題となるのでしょうか？問題となりそうであればアカウントの登録情報の訂正をいただきたいです。

以下は引用です。`,

    nameJa:       'FANDA HERA SAPUTRI',  // 受験者氏名（日本語）
    nameRomaji:   'FANDA HERA SAPUTRI',  // 受験者氏名（ローマ字）
    phone:        '08075037915',
    email:        'wofandahera@gmail.com',
    zip:          '1930824',
    prefecture:   '東京都',
    city:         '八王子市長房町',
    address:      '1453番地　タイガーハイツB 208号',

    agree:        true,   // 利用規約への同意チェックを自動で入れる
    autoRun:      true,   // ページを開いたら自動で流し込む（false にすると右下ボタンのみ）
  };
  /* ============================================================== */

  // フィールドID対応表（フォーム側のID）
  const F = {
    inquiry:     'tfa_561',
    program:     'tfa_608',
    candidateId: 'tfa_610',
    orderNumber: 'tfa_564',
    detail:      'tfa_603',
    nameJa:      'tfa_614',
    nameRomaji:  'tfa_616',
    phone:       'tfa_606',
    email:       'tfa_665',
    zip:         'tfa_667',
    prefecture:  'tfa_669',
    city:        'tfa_671',
    address:     'tfa_683',
    agree:       'tfa_589',
  };

  // 「お問い合わせ内容」番号 → option の value
  const INQUIRY_VALUES = {
    1: 'tfa_672', // ユーザ名 / パスワードリセット
    2: 'tfa_673', // 氏名変更 / 登録情報変更
    3: 'tfa_674', // 受験者IDの統合申請
    4: 'tfa_675', // 利用制限解除申請
    5: 'tfa_676', // 担当者とりまとめ・団体登録予約
    6: 'tfa_677', // 試験予約 / 変更 / キャンセル
    7: 'tfa_678', // 受験料の支払い
    8: 'tfa_679', // 請求書の発行
    9: 'tfa_680', // スコアレポートの再発行
    10: 'tfa_681', // その他
  };

  /** React/フレームワーク経由でも値が反映されるよう、ネイティブ setter を使う */
  function nativeSet(el, value) {
    const proto = el instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : el instanceof HTMLSelectElement
        ? HTMLSelectElement.prototype
        : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
    setter.call(el, value);
  }

  function fire(el, ...types) {
    for (const t of types) {
      el.dispatchEvent(new Event(t, { bubbles: true }));
    }
  }

  function setText(id, value) {
    if (value === undefined || value === null || value === '') return false;
    const el = document.getElementById(id);
    if (!el) return false;
    el.focus();
    nativeSet(el, String(value));
    // wForms のヒント表示・バリデーションを更新させる
    fire(el, 'input', 'keyup', 'change', 'blur');
    return true;
  }

  function setSelect(id, wanted) {
    const el = document.getElementById(id);
    if (!el || wanted === undefined || wanted === null || wanted === '') return false;

    let value = null;
    if (typeof wanted === 'number' || /^\d+$/.test(String(wanted))) {
      value = INQUIRY_VALUES[Number(wanted)] || null;
    }
    if (!value) {
      const key = String(wanted);
      const hit = [...el.options].find(
        (o) => o.value === key || (o.textContent || '').includes(key)
      );
      value = hit ? hit.value : null;
    }
    if (!value) {
      console.warn('[autofill] お問い合わせ内容が見つかりません:', wanted);
      return false;
    }

    el.focus();
    nativeSet(el, value);
    fire(el, 'input', 'change', 'blur');
    return true;
  }

  function setCheckbox(id, checked) {
    const el = document.getElementById(id);
    if (!el) return false;
    if (!!el.checked !== !!checked) {
      el.click(); // click にしてサイト側のハンドラも走らせる
    }
    return true;
  }

  function fill() {
    let n = 0;
    n += setSelect(F.inquiry, CONFIG.inquiry) ? 1 : 0;
    n += setText(F.program, CONFIG.program) ? 1 : 0;
    n += setText(F.candidateId, CONFIG.candidateId) ? 1 : 0;
    n += setText(F.orderNumber, CONFIG.orderNumber) ? 1 : 0;
    n += setText(F.detail, CONFIG.detail) ? 1 : 0;
    n += setText(F.nameJa, CONFIG.nameJa) ? 1 : 0;
    n += setText(F.nameRomaji, CONFIG.nameRomaji) ? 1 : 0;
    n += setText(F.phone, CONFIG.phone) ? 1 : 0;
    n += setText(F.email, CONFIG.email) ? 1 : 0;
    n += setText(F.zip, CONFIG.zip) ? 1 : 0;
    n += setText(F.prefecture, CONFIG.prefecture) ? 1 : 0;
    n += setText(F.city, CONFIG.city) ? 1 : 0;
    n += setText(F.address, CONFIG.address) ? 1 : 0;
    n += setCheckbox(F.agree, CONFIG.agree) ? 1 : 0;

    document.activeElement && document.activeElement.blur();
    console.log(`[autofill] ${n} 項目を入力しました`);
    return n;
  }

  /** フォームは外部スクリプトで後から差し込まれるので、出現を待つ */
  function waitFor(selector, timeoutMs = 30000) {
    return new Promise((resolve, reject) => {
      const found = document.querySelector(selector);
      if (found) return resolve(found);

      const obs = new MutationObserver(() => {
        const el = document.querySelector(selector);
        if (el) {
          obs.disconnect();
          clearTimeout(timer);
          resolve(el);
        }
      });
      obs.observe(document.documentElement, { childList: true, subtree: true });

      const timer = setTimeout(() => {
        obs.disconnect();
        reject(new Error('form not found: ' + selector));
      }, timeoutMs);
    });
  }

  function addButton() {
    if (document.getElementById('tm-autofill-btn')) return;
    const btn = document.createElement('button');
    btn.id = 'tm-autofill-btn';
    btn.type = 'button';
    btn.textContent = '自動入力';
    btn.style.cssText = [
      'position:fixed', 'right:20px', 'bottom:20px', 'z-index:2147483000',
      'padding:10px 18px', 'font-size:14px', 'font-weight:700',
      'color:#fff', 'background:#003057', 'border:none', 'border-radius:4px',
      'box-shadow:0 2px 8px rgba(0,0,0,.3)', 'cursor:pointer',
    ].join(';');
    btn.addEventListener('click', fill);
    document.body.appendChild(btn);
  }

  waitFor('#' + F.inquiry)
    .then(() => {
      addButton();
      if (CONFIG.autoRun) {
        // wForms の初期化が終わるのを少し待つ
        setTimeout(fill, 600);
      }
    })
    .catch((e) => console.warn('[autofill]', e.message));
})();
