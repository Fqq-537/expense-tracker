const CAT_COLORS = {
  餐饮: '#e8833a',
  交通: '#3f8fd6',
  购物: '#c261c9',
  居住: '#4aa96c',
  娱乐: '#e0b03c',
  学习: '#5d6bd8',
  医疗: '#d95f5f',
  其他: '#8b94a3',
};

const state = {
  month: '',
  summary: null,
  records: [],
  categories: [],
};

const $ = (id) => document.getElementById(id);

function fmtMoney(n) {
  return '¥' + Number(n || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let msg = `请求失败（${res.status}）`;
    try {
      const data = await res.json();
      if (data && data.error) msg = data.error;
    } catch (e) { /* 忽略解析失败 */ }
    throw new Error(msg);
  }
  if (res.status === 204) return null;
  return res.json();
}

/* ------------------------------ 渲染 ------------------------------ */

function renderKpis() {
  const s = state.summary;
  if (!s) return;
  $('kpi-total').textContent = fmtMoney(s.total);
  $('kpi-count').textContent = s.count;
  $('kpi-avg').textContent = fmtMoney(s.avg_per_day);
  $('kpi-max').textContent = fmtMoney(s.max_single);
  $('kpi-avg-note').textContent = `按 ${s.days_elapsed} 天计`;
}

function renderCatChart() {
  const box = $('cat-chart');
  const rows = state.summary ? state.summary.by_category : [];
  box.innerHTML = '';

  if (!rows.length) {
    box.innerHTML = '<p class="empty">本月还没有记录</p>';
    return;
  }

  const max = Math.max(...rows.map((r) => r.amount));
  rows.forEach((row) => {
    const el = document.createElement('div');
    el.className = 'bar-row';
    el.innerHTML = `
      <span class="name">${row.category}</span>
      <span class="bar-track"><i class="bar-fill"></i></span>
      <span class="val">${fmtMoney(row.amount)} · ${row.pct}%</span>
    `;
    const fill = el.querySelector('.bar-fill');
    fill.style.background = CAT_COLORS[row.category] || '#8b94a3';
    box.appendChild(el);
    requestAnimationFrame(() => {
      fill.style.width = Math.max(4, (row.amount / max) * 100) + '%';
    });
  });
}

function renderDayChart() {
  const box = $('day-chart');
  const s = state.summary;
  box.innerHTML = '';
  if (!s) return;

  const map = new Map(s.by_day.map((d) => [d.date, d.amount]));
  const days = s.days_in_month;
  const max = Math.max(1, ...s.by_day.map((d) => d.amount));

  for (let day = 1; day <= days; day += 1) {
    const key = `${s.month}-${String(day).padStart(2, '0')}`;
    const amount = map.get(key) || 0;
    const col = document.createElement('div');
    col.className = 'col';
    col.title = `${key}　${amount ? fmtMoney(amount) : '无记录'}`;
    const bar = document.createElement('i');
    if (amount > 0) {
      bar.classList.add('has');
      bar.style.height = Math.max(6, (amount / max) * 100) + '%';
    } else {
      bar.style.height = '2px';
    }
    col.appendChild(bar);
    box.appendChild(col);
  }

  const axis = $('day-axis');
  axis.innerHTML = `<span>1 日</span><span>${Math.ceil(days / 2)} 日</span><span>${days} 日</span>`;

  $('day-hint').textContent = s.by_day.length
    ? `${s.by_day.length} 天有支出，单日最高 ${fmtMoney(max)}`
    : '';
}

function renderList() {
  const box = $('list');
  box.innerHTML = '';

  if (!state.records.length) {
    box.innerHTML = '<li class="empty" style="display:block;border:0">这个月还没有记录，先记一笔试试</li>';
    $('list-meta').textContent = '';
    return;
  }

  $('list-meta').textContent = `共 ${state.records.length} 笔`;

  state.records.forEach((r) => {
    const li = document.createElement('li');
    li.innerHTML = `
      <span class="d">${r.date.slice(5)}</span>
      <span class="tag">${r.category}</span>
      <span class="note${r.note ? '' : ' none'}">${escapeHtml(r.note) || '—'}</span>
      <span class="amt">${fmtMoney(r.amount)}</span>
      <button class="del" title="删除" data-id="${r.id}" aria-label="删除">×</button>
    `;
    li.querySelector('.tag').style.background =
      (CAT_COLORS[r.category] || '#8b94a3') + '1a';
    li.querySelector('.tag').style.color = CAT_COLORS[r.category] || '#3d4757';
    box.appendChild(li);
  });
}

function escapeHtml(str) {
  return String(str || '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[ch]));
}

/* ------------------------------ 数据 ------------------------------ */

async function loadAll() {
  const month = state.month;
  const [summary, list] = await Promise.all([
    api(`/api/summary?month=${month}`),
    api(`/api/records?month=${month}`),
  ]);
  state.summary = summary;
  state.records = list.records;
  renderKpis();
  renderCatChart();
  renderDayChart();
  renderList();
}

function setHint(text, kind) {
  const el = $('hint');
  el.textContent = text || '';
  el.className = 'hint' + (kind ? ' ' + kind : '');
}

/* ------------------------------ 交互 ------------------------------ */

async function onSubmit(event) {
  event.preventDefault();
  const btn = event.target.querySelector('button');
  const payload = {
    date: $('f-date').value,
    amount: Number($('f-amount').value),
    category: $('f-category').value,
    note: $('f-note').value.trim(),
  };

  btn.disabled = true;
  try {
    await api('/api/records', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    $('f-amount').value = '';
    $('f-note').value = '';
    setHint('已添加', 'ok');
    setTimeout(() => setHint(''), 1800);
    await loadAll();
  } catch (err) {
    setHint(err.message, 'err');
  } finally {
    btn.disabled = false;
  }
}

async function onListClick(event) {
  const btn = event.target.closest('.del');
  if (!btn) return;
  try {
    await api(`/api/records/${btn.dataset.id}`, { method: 'DELETE' });
    await loadAll();
  } catch (err) {
    setHint(err.message, 'err');
  }
}

async function init() {
  try {
    const meta = await api('/api/meta');
    state.categories = meta.categories;
    state.month = meta.month;

    const select = $('f-category');
    select.innerHTML = meta.categories
      .map((c) => `<option value="${c}">${c}</option>`)
      .join('');

    $('f-date').value = meta.today;
    $('month').value = meta.month;

    $('form').addEventListener('submit', onSubmit);
    $('list').addEventListener('click', onListClick);

    $('month').addEventListener('change', async (e) => {
      if (!e.target.value) return;
      state.month = e.target.value;
      await loadAll();
    });

    await loadAll();
  } catch (err) {
    setHint('加载失败：' + err.message + '（请确认服务已启动）', 'err');
  }
}

init();
