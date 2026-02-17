// Shared frontend utilities (Vanilla JS)
// - API base resolution
// - student_key handling
// - fetch wrapper
// - simple modal / toast

(function () {
  const isLocal = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
  const isFrontendDevServer = isLocal && (location.port && location.port !== '8000');

  const override = localStorage.getItem('API_BASE_OVERRIDE');
  const API_BASE = override
    ? override.replace(/\/$/, '')
    : (isFrontendDevServer ? 'http://localhost:8000/api' : '/api');

  function getStudentKey() {
    const key = localStorage.getItem('student_key');
    if (key && key.length > 10) return key;
    const newKey = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random()).toString();
    localStorage.setItem('student_key', newKey);
    return newKey;
  }

  async function apiFetch(path, { method = 'GET', headers = {}, body } = {}) {
    const url = API_BASE + path;
    const finalHeaders = {
      'Content-Type': 'application/json',
      ...headers,
    };

    // Attach student key for "my suggestions" and push endpoints.
    if (path.startsWith('/suggestions') || path.startsWith('/me/') || path.startsWith('/push')) {
      finalHeaders['X-Student-Key'] = getStudentKey();
    }

    const res = await fetch(url, {
      method,
      headers: finalHeaders,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { raw: text };
    }

    if (!res.ok) {
      const message = (data && (data.detail || data.message)) ? (data.detail || data.message) : ('HTTP ' + res.status);
      const err = new Error(message);
      err.status = res.status;
      err.data = data;
      throw err;
    }

    return data;
  }

  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([k, v]) => {
      if (k === 'class') node.className = v;
      else if (k.startsWith('on') && typeof v === 'function') node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v);
    });
    [].concat(children).filter(Boolean).forEach((c) => node.append(c.nodeType ? c : document.createTextNode(String(c))));
    return node;
  }

  function toast(message, variant = 'info') {
    const root = document.getElementById('toast-root') || document.body.appendChild(el('div', {
      id: 'toast-root',
      class: 'fixed bottom-4 left-1/2 -translate-x-1/2 z-50 space-y-2',
    }));

    const color = variant === 'error'
      ? 'bg-red-600'
      : variant === 'success'
        ? 'bg-emerald-600'
        : 'bg-slate-900';

    const t = el('div', {
      class: `${color} text-white px-4 py-3 rounded-2xl shadow-lg ring-1 ring-white/10 backdrop-blur transition-all duration-300 ease-out translate-y-2 opacity-0 max-w-[90vw]`,
    }, [message]);
    root.appendChild(t);
    requestAnimationFrame(() => {
      t.classList.remove('translate-y-2', 'opacity-0');
    });
    setTimeout(() => {
      t.classList.add('translate-y-2', 'opacity-0');
      setTimeout(() => t.remove(), 250);
    }, 2400);
  }

  function openModal({ title = '완료', message = '' } = {}) {
    const overlay = el('div', {
      class: 'fixed inset-0 z-50 bg-slate-950/40 backdrop-blur-sm flex items-center justify-center p-4',
    });

    const card = el('div', {
      class: 'w-full max-w-md rounded-3xl bg-white shadow-xl ring-1 ring-slate-200 overflow-hidden animate-[pop_.18s_ease-out]',
    });

    const head = el('div', { class: 'px-6 py-5 border-b border-slate-100' }, [
      el('div', { class: 'text-base font-semibold text-slate-900' }, [title]),
      el('div', { class: 'text-sm text-slate-500 mt-1' }, ['확인 후 계속 진행하세요.']),
    ]);
    const body = el('div', { class: 'px-6 py-5 text-sm text-slate-700 leading-relaxed' }, [message]);
    const foot = el('div', { class: 'px-6 py-5 bg-slate-50 flex items-center justify-end gap-2' }, [
      el('button', {
        class: 'px-4 py-2 rounded-2xl bg-slate-900 text-white text-sm font-medium shadow-sm hover:shadow-md transition',
        onclick: () => overlay.remove(),
      }, ['확인']),
    ]);

    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.remove();
    });

    card.append(head, body, foot);
    overlay.append(card);
    document.body.append(overlay);
  }

  window.App = {
    API_BASE,
    apiFetch,
    getStudentKey,
    toast,
    openModal,
    el,
  };
})();
