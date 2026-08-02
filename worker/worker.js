/**
 * 連絡済みリストを Telegram に送るための中継 Worker。
 *
 * ページ（index.html）は Bot トークンを持たず、この Worker に本文だけを POST する。
 * トークンは Cloudflare の Secret として保持され、ブラウザには一切降りてこない。
 *
 *   ブラウザ ──POST text──▶ Worker ──sendMessage(token)──▶ Telegram
 *
 * 受け付ける条件（絞っておくことで、URL が漏れても任意のメッセージは送れない）:
 *   - POST のみ
 *   - Origin が ALLOWED_ORIGINS に含まれること
 *   - 本文が "#FANDA_TSK_CONTACTED" で始まること
 *   - 本文が 4096 文字以内であること
 *   - APP_KEY を設定した場合は X-App-Key ヘッダーが一致すること（任意）
 */

const TG_API = 'https://api.telegram.org';
const HEADER_PREFIX = '#FANDA_TSK_CONTACTED';
const MAX_LEN = 4096;

function corsHeaders(origin, allowed) {
  const permitted = allowed.includes('*') || allowed.includes(origin);
  return {
    'Access-Control-Allow-Origin': permitted ? (origin || 'null') : 'https://example.invalid',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, X-App-Key',
    'Access-Control-Max-Age': '86400',
    'Vary': 'Origin'
  };
}

function json(body, status, headers) {
  return new Response(JSON.stringify(body), {
    status: status,
    headers: Object.assign({ 'Content-Type': 'application/json; charset=utf-8' }, headers)
  });
}

async function readText(request) {
  const ct = request.headers.get('Content-Type') || '';
  if (ct.includes('application/json')) {
    const body = await request.json().catch(() => ({}));
    return String((body && body.text) || '');
  }
  const form = await request.formData().catch(() => null);
  return form ? String(form.get('text') || '') : '';
}

export default {
  async fetch(request, env) {
    const allowed = String(env.ALLOWED_ORIGINS || '*')
      .split(',').map(s => s.trim()).filter(Boolean);
    // file:// で開いた場合、ブラウザは Origin を "null" にするか、そもそも付けてこない。
    // どちらも同じ扱いにする（Origin なしのリクエストはブラウザの別サイトからは発生しない）。
    const origin = request.headers.get('Origin') || 'null';
    const headers = corsHeaders(origin, allowed);

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: headers });
    }
    if (request.method !== 'POST') {
      return json({ ok: false, description: 'POST only' }, 405, headers);
    }
    if (!(allowed.includes('*') || allowed.includes(origin))) {
      return json({ ok: false, description: 'origin not allowed: ' + (origin || '(none)') }, 403, headers);
    }
    if (env.APP_KEY && request.headers.get('X-App-Key') !== env.APP_KEY) {
      return json({ ok: false, description: 'bad app key' }, 403, headers);
    }
    if (!env.TG_TOKEN) {
      return json({ ok: false, description: 'TG_TOKEN is not configured on the worker' }, 500, headers);
    }

    const text = await readText(request);
    if (!text.startsWith(HEADER_PREFIX)) {
      return json({ ok: false, description: 'unexpected payload' }, 400, headers);
    }
    if (text.length > MAX_LEN) {
      return json({ ok: false, description: 'text too long' }, 413, headers);
    }

    const res = await fetch(`${TG_API}/bot${env.TG_TOKEN}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: env.TG_CHAT,
        text: text,
        disable_web_page_preview: true
      })
    });
    const data = await res.json().catch(() => ({ ok: false, description: 'invalid response from Telegram' }));
    return json(data, data.ok ? 200 : 502, headers);
  }
};
