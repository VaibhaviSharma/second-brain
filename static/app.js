/**
 * app.js — Second Brain web UI (single-page app)
 *
 * Vanilla JS, no framework. Hash-router drives which view is rendered.
 * All data comes from the Flask REST API at /api/*.
 * Views: home (card grid), category (detail), add (form), search (results).
 */
'use strict';

// ── Theme (restore before first render) ──────────────────────────────────────
const savedTheme = localStorage.getItem('theme') || 'dark';
document.documentElement.dataset.theme = savedTheme;

// ── Constants ─────────────────────────────────────────────────────────────────
const CAT_IMAGES = {
  link:     'https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=600&auto=format&fit=crop',
  job:      'https://images.unsplash.com/photo-1497032628192-86f99bcd76bc?w=600&auto=format&fit=crop',
  skill:    'https://images.unsplash.com/photo-1456513080510-7bf3a84b82f8?w=600&auto=format&fit=crop',
  idea:     'https://images.unsplash.com/photo-1495576775051-8af0d10f06bd?w=600&auto=format&fit=crop',
  note:     'https://images.unsplash.com/photo-1512314889357-e157c22f938d?w=600&auto=format&fit=crop',
  resource: 'https://images.unsplash.com/photo-1519681393784-d120267933ba?w=600&auto=format&fit=crop',
};

const CAT_LABELS = {
  link: 'Saved Links', job: 'Jobs', skill: 'Learning',
  idea: 'Ideas', note: 'Notes', resource: 'Inspiration',
};

const DEFAULT_IMG = 'https://images.unsplash.com/photo-1497366216548-37526070297c?w=600&auto=format&fit=crop';

const CAT_ORDER = ['link', 'job', 'skill', 'idea', 'note', 'resource'];

// ── Helpers ───────────────────────────────────────────────────────────────────

function esc(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function faviconUrl(url) {
  try {
    const host = new URL(url).hostname;
    return `https://www.google.com/s2/favicons?domain=${host}&sz=32`;
  } catch { return ''; }
}

function platformLabel(url) {
  if (!url) return '';
  try {
    const h = new URL(url).hostname.replace('www.', '');
    if (h.includes('youtube')) return 'YouTube';
    if (h.includes('linkedin')) return 'LinkedIn';
    if (h.includes('instagram')) return 'Instagram';
    if (h.includes('substack')) return 'Substack';
    if (h.includes('github')) return 'GitHub';
    if (h.includes('twitter') || h.includes('x.com')) return 'X';
    if (h.includes('reddit')) return 'Reddit';
    if (h.includes('medium')) return 'Medium';
    if (h.includes('netflix')) return 'Netflix';
    if (h.includes('spotify')) return 'Spotify';
    return h.split('.')[0].charAt(0).toUpperCase() + h.split('.')[0].slice(1);
  } catch { return ''; }
}

function formatDate(iso) {
  if (!iso) return '';
  return iso.slice(0, 10);
}

// ── Toast ─────────────────────────────────────────────────────────────────────

function showToast(msg, type = 'success') {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.className = `toast ${type} show`;
  setTimeout(() => { t.className = 'toast'; }, 2500);
}

// ── Theme toggle ──────────────────────────────────────────────────────────────

function toggleTheme() {
  const html = document.documentElement;
  html.dataset.theme = html.dataset.theme === 'dark' ? 'light' : 'dark';
  localStorage.setItem('theme', html.dataset.theme);
}

// ── Navigation ────────────────────────────────────────────────────────────────

function navigate(view, param) {
  if (view === 'home') location.hash = '';
  else if (view === 'category') location.hash = `category/${param}`;
  else if (view === 'add') location.hash = 'add';
  else if (view === 'search') location.hash = `search/${encodeURIComponent(param)}`;
}

// ── Search debounce ───────────────────────────────────────────────────────────

let _searchTimer = null;

function setupSearch() {
  const input = document.getElementById('search-input');
  if (!input) return;
  input.addEventListener('input', () => {
    clearTimeout(_searchTimer);
    const val = input.value.trim();
    if (val.length > 1) {
      _searchTimer = setTimeout(() => navigate('search', val), 300);
    } else if (val.length === 0) {
      _searchTimer = setTimeout(() => navigate('home'), 300);
    }
  });
}

// ── App shell ─────────────────────────────────────────────────────────────────

function renderApp() {
  document.getElementById('app').innerHTML = `
    <div class="header">
      <div class="logo">Second Brain</div>
      <div class="search-wrap">
        <input id="search-input" type="search" placeholder="Search everything..." autocomplete="off">
      </div>
      <div class="header-actions">
        <button class="btn-icon" id="theme-btn" title="Toggle theme">&#9681;</button>
        <button class="btn-add" onclick="navigate('add')">+ Add</button>
      </div>
    </div>
    <div class="main" id="main-content"></div>
    <div id="toast"></div>
  `;
  document.getElementById('theme-btn').addEventListener('click', toggleTheme);
  setupSearch();
}

function setMain(html) {
  const el = document.getElementById('main-content');
  if (el) el.innerHTML = html;
}

// ── Home view ─────────────────────────────────────────────────────────────────

async function renderHome() {
  setMain('<div class="loading-state">Loading...</div>');

  try {
    const statsData = await fetch('/api/stats').then(r => r.json());
    const byType = statsData.by_type || {};

    // Determine which types to show (known order first, then extras)
    const allTypes = [...CAT_ORDER, ...Object.keys(byType).filter(t => !CAT_ORDER.includes(t))];

    // Fetch recent entries for each type
    const entryResults = await Promise.all(
      allTypes.map(type =>
        fetch(`/api/entries?limit=5&type=${type}`)
          .then(r => r.json())
          .then(d => ({ type, entries: d.entries || [] }))
          .catch(() => ({ type, entries: [] }))
      )
    );

    const entryMap = {};
    entryResults.forEach(({ type, entries }) => { entryMap[type] = entries; });

    const cards = allTypes.map(type => {
      const label = CAT_LABELS[type] || (type.charAt(0).toUpperCase() + type.slice(1));
      const count = byType[type] || 0;
      const img = CAT_IMAGES[type] || DEFAULT_IMG;
      const entries = entryMap[type] || [];

      let linksHTML;
      if (entries.length === 0) {
        linksHTML = '<div class="no-links">Nothing saved yet</div>';
      } else {
        const items = entries.map(entry => `
          <li class="card-link-item" onclick="event.stopPropagation()">
            <img class="favicon" src="${esc(faviconUrl(entry.url || ''))}" onerror="this.style.display='none'" alt="">
            <a class="link-title" href="${esc(entry.url || '#')}" target="_blank" rel="noopener" title="${esc(entry.title)}">${esc(entry.title)}</a>
          </li>
        `).join('');
        linksHTML = `<ul class="card-links">${items}</ul>`;
      }

      const footer = count > 5
        ? `<div class="card-footer"><a class="view-all" href="#category/${type}" onclick="event.stopPropagation()">View all &#8594;</a></div>`
        : '';

      return `
        <div class="card" onclick="navigate('category','${esc(type)}')">
          <div class="card-header">
            <span class="card-title">${esc(label)}</span>
            <span class="card-count">${count}</span>
          </div>
          <img class="card-img" src="${esc(img)}" alt="${esc(label)}" loading="lazy" onerror="this.src='${esc(DEFAULT_IMG)}'">
          ${linksHTML}
          ${footer}
        </div>
      `;
    }).join('');

    setMain(`<div class="grid">${cards}</div>`);
  } catch (err) {
    setMain(`<div class="empty-state">Error loading data: ${esc(err.message)}</div>`);
  }
}

// ── Category / detail view ────────────────────────────────────────────────────

let _activeTag = null;
let _categoryEntries = [];

async function renderCategory(type) {
  _activeTag = null;
  _categoryEntries = [];

  const label = CAT_LABELS[type] || (type.charAt(0).toUpperCase() + type.slice(1));
  const img = CAT_IMAGES[type] || DEFAULT_IMG;

  setMain(`
    <div class="detail-view">
      <div class="detail-header">
        <button class="btn-back" onclick="navigate('home')">&#8592; Back</button>
        <span class="detail-title">${esc(label)}</span>
      </div>
      <img class="detail-banner" src="${esc(img)}" alt="${esc(label)}" onerror="this.style.display='none'">
      <div id="tag-controls" class="detail-controls"></div>
      <div id="entry-list" class="entry-list"><div class="loading-state">Loading...</div></div>
    </div>
  `);

  try {
    const data = await fetch(`/api/entries?type=${encodeURIComponent(type)}&status=active&limit=200`).then(r => r.json());
    _categoryEntries = data.entries || [];

    // Collect all unique tags
    const tagSet = new Set();
    _categoryEntries.forEach(e => {
      if (e.tags) e.tags.split(',').forEach(t => { const tt = t.trim(); if (tt) tagSet.add(tt); });
    });

    const tagControls = document.getElementById('tag-controls');
    if (tagControls && tagSet.size > 0) {
      const pills = ['All', ...Array.from(tagSet).sort()].map(tag => `
        <button class="tag-pill${tag === 'All' ? ' active' : ''}" onclick="filterByTag('${esc(tag)}')">${esc(tag)}</button>
      `).join('');
      tagControls.innerHTML = pills;
    }

    renderEntryList();
  } catch (err) {
    const el = document.getElementById('entry-list');
    if (el) el.innerHTML = `<div class="empty-state">Error: ${esc(err.message)}</div>`;
  }
}

function filterByTag(tag) {
  _activeTag = tag === 'All' ? null : tag;

  // Update pill active state
  document.querySelectorAll('.tag-pill').forEach(pill => {
    pill.classList.toggle('active', pill.textContent === tag);
  });

  renderEntryList();
}

function renderEntryList() {
  const el = document.getElementById('entry-list');
  if (!el) return;

  const filtered = _activeTag
    ? _categoryEntries.filter(e => e.tags && e.tags.split(',').map(t => t.trim()).includes(_activeTag))
    : _categoryEntries;

  if (filtered.length === 0) {
    el.innerHTML = '<div class="empty-state">No entries found.</div>';
    return;
  }

  el.innerHTML = filtered.map(entry => entryCardHTML(entry)).join('');
}

function entryCardHTML(entry) {
  const titleEl = entry.url
    ? `<a class="entry-title" href="${esc(entry.url)}" target="_blank" rel="noopener">${esc(entry.title)}</a>`
    : `<span class="entry-title" style="cursor:default">${esc(entry.title)}</span>`;

  const platform = platformLabel(entry.url);
  const favSrc = entry.url ? faviconUrl(entry.url) : '';
  const platformEl = platform
    ? `<span class="entry-platform">
        ${favSrc ? `<img src="${esc(favSrc)}" width="12" height="12" style="border-radius:2px" onerror="this.style.display='none'" alt="">` : ''}
        ${esc(platform)}
      </span>`
    : '';

  const tagsEl = entry.tags
    ? `<div class="entry-tags">${entry.tags.split(',').filter(t => t.trim()).map(t => `<span class="entry-tag">#${esc(t.trim())}</span>`).join('')}</div>`
    : '';

  const dateEl = `<span class="entry-date">${formatDate(entry.created_at)}</span>`;

  return `
    <div class="entry-card" id="ec-${entry.id}">
      ${titleEl}
      <div class="entry-meta">
        ${platformEl}
        ${tagsEl}
        ${dateEl}
      </div>
      <div class="entry-actions">
        <button class="btn-sm" onclick="openEditModal(${entry.id})">Edit</button>
        <button class="btn-sm" onclick="archiveEntry(${entry.id})">Archive</button>
        <button class="btn-sm danger" onclick="deleteEntry(${entry.id})">Delete</button>
      </div>
    </div>
  `;
}

async function archiveEntry(id) {
  try {
    await fetch(`/api/entries/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'archived' }),
    });
    _categoryEntries = _categoryEntries.filter(e => e.id !== id);
    renderEntryList();
    showToast('Archived');
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function deleteEntry(id) {
  const entry = _categoryEntries.find(e => e.id === id);
  if (!confirm(`Delete "${entry ? entry.title : 'this entry'}"?`)) return;
  try {
    await fetch(`/api/entries/${id}`, { method: 'DELETE' });
    _categoryEntries = _categoryEntries.filter(e => e.id !== id);
    renderEntryList();
    showToast('Deleted');
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

// ── Edit modal ────────────────────────────────────────────────────────────────

function openEditModal(id) {
  const entry = _categoryEntries.find(e => e.id === id) || _searchEntries.find(e => e.id === id);
  if (!entry) return;
  showEditModal(entry);
}

function showEditModal(entry) {
  // Remove existing modal if any
  const existing = document.getElementById('edit-modal-overlay');
  if (existing) existing.remove();

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay open';
  overlay.id = 'edit-modal-overlay';
  overlay.innerHTML = `
    <div class="modal">
      <div class="modal-header">
        <span class="modal-title">Edit Entry</span>
        <button class="btn-icon" onclick="closeEditModal()">&#10005;</button>
      </div>
      <form id="edit-form" onsubmit="submitEditForm(event, ${entry.id})">
        <div class="form-group">
          <label>Title</label>
          <input type="text" name="title" value="${esc(entry.title)}" required>
        </div>
        <div class="form-group">
          <label>URL</label>
          <input type="url" name="url" value="${esc(entry.url || '')}">
        </div>
        <div class="form-group">
          <label>Tags (comma-separated)</label>
          <input type="text" name="tags" value="${esc(entry.tags || '')}">
        </div>
        <div class="form-group">
          <label>Notes</label>
          <textarea name="content">${esc(entry.content || '')}</textarea>
        </div>
        <div style="display:flex;gap:10px;margin-top:8px">
          <button type="submit" class="btn-primary" style="flex:1;padding:10px">Save</button>
          <button type="button" class="btn-sm" style="flex:0;padding:10px 16px" onclick="closeEditModal()">Cancel</button>
        </div>
      </form>
    </div>
  `;
  overlay.addEventListener('click', e => { if (e.target === overlay) closeEditModal(); });
  document.body.appendChild(overlay);
}

function closeEditModal() {
  const overlay = document.getElementById('edit-modal-overlay');
  if (overlay) overlay.remove();
}

async function submitEditForm(event, id) {
  event.preventDefault();
  const form = event.target;
  const data = {
    title: form.title.value.trim(),
    url: form.url.value.trim(),
    tags: form.tags.value.trim(),
    content: form.content.value.trim(),
  };
  try {
    const updated = await fetch(`/api/entries/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(r => r.json());

    // Update local entry list
    const idx = _categoryEntries.findIndex(e => e.id === id);
    if (idx !== -1) _categoryEntries[idx] = updated;
    const sidx = _searchEntries.findIndex(e => e.id === id);
    if (sidx !== -1) _searchEntries[sidx] = updated;

    closeEditModal();
    renderEntryList();
    showToast('Saved!');
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

// ── Add view ──────────────────────────────────────────────────────────────────

async function renderAdd() {
  setMain('<div class="add-view"><div class="form-wrap"><div class="loading-state">Loading...</div></div></div>');

  let typeOptions = '';
  try {
    const types = await fetch('/api/types').then(r => r.json());
    const knownTypes = new Set(types.map(t => t.type));
    CAT_ORDER.forEach(t => knownTypes.add(t));
    typeOptions = Array.from(knownTypes).map(t =>
      `<option value="${esc(t)}">${esc(CAT_LABELS[t] || t)}</option>`
    ).join('');
  } catch {
    typeOptions = CAT_ORDER.map(t => `<option value="${esc(t)}">${esc(CAT_LABELS[t] || t)}</option>`).join('');
  }

  setMain(`
    <div class="add-view">
      <div class="form-wrap">
        <div class="detail-header">
          <button class="btn-back" onclick="navigate('home')">&#8592; Back</button>
          <span class="detail-title">Add Entry</span>
        </div>
        <form id="add-form" onsubmit="submitAdd(event)">
          <div class="form-group">
            <label>URL (optional)</label>
            <input type="url" id="add-url" name="url" placeholder="https://..." autocomplete="off">
          </div>
          <div class="form-group">
            <label>Title *</label>
            <input type="text" id="add-title" name="title" required autocomplete="off">
          </div>
          <div class="form-group">
            <label>Category</label>
            <select id="add-type" name="type">
              ${typeOptions}
            </select>
          </div>
          <div class="form-group">
            <label>Tags (comma-separated)</label>
            <input type="text" id="add-tags" name="tags" placeholder="tag1, tag2" autocomplete="off">
          </div>
          <div class="form-group">
            <label>Notes</label>
            <textarea id="add-content" name="content" placeholder="Optional notes..."></textarea>
          </div>
          <button type="submit" class="btn-primary">Save</button>
        </form>
      </div>
    </div>
  `);

  // Auto-populate title from URL
  const urlInput = document.getElementById('add-url');
  const titleInput = document.getElementById('add-title');
  if (urlInput && titleInput) {
    urlInput.addEventListener('blur', () => {
      if (urlInput.value.trim() && !titleInput.value.trim()) {
        titleInput.value = urlInput.value.trim();
      }
    });
  }
}

async function submitAdd(event) {
  event.preventDefault();
  const form = event.target;
  const data = {
    title: form.title.value.trim(),
    url: form.url ? form.url.value.trim() : '',
    type: form.type.value,
    tags: form.tags.value.trim(),
    content: form.content.value.trim(),
  };
  if (!data.title) { showToast('Title is required', 'error'); return; }
  try {
    await fetch('/api/entries', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    showToast('Saved!');
    navigate('home');
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

// ── Search view ───────────────────────────────────────────────────────────────

let _searchEntries = [];

async function renderSearch(q) {
  _searchEntries = [];
  setMain(`
    <div class="detail-view">
      <div class="detail-header">
        <button class="btn-back" onclick="navigate('home')">&#8592; Back</button>
        <span class="detail-title">Search: ${esc(q)}</span>
      </div>
      <div id="entry-list" class="entry-list"><div class="loading-state">Searching...</div></div>
    </div>
  `);

  try {
    const data = await fetch(`/api/entries?q=${encodeURIComponent(q)}&limit=50`).then(r => r.json());
    _searchEntries = data.entries || [];

    const el = document.getElementById('entry-list');
    if (!el) return;

    if (_searchEntries.length === 0) {
      el.innerHTML = `<div class="empty-state">No results for "${esc(q)}"</div>`;
      return;
    }

    el.innerHTML = _searchEntries.map(entry => searchEntryCardHTML(entry)).join('');
  } catch (err) {
    const el = document.getElementById('entry-list');
    if (el) el.innerHTML = `<div class="empty-state">Error: ${esc(err.message)}</div>`;
  }
}

function searchEntryCardHTML(entry) {
  const label = CAT_LABELS[entry.type] || entry.type;
  const titleEl = entry.url
    ? `<a class="entry-title" href="${esc(entry.url)}" target="_blank" rel="noopener">${esc(entry.title)}</a>`
    : `<span class="entry-title" style="cursor:default">${esc(entry.title)}</span>`;

  const platform = platformLabel(entry.url);
  const favSrc = entry.url ? faviconUrl(entry.url) : '';
  const platformEl = platform
    ? `<span class="entry-platform">
        ${favSrc ? `<img src="${esc(favSrc)}" width="12" height="12" style="border-radius:2px" onerror="this.style.display='none'" alt="">` : ''}
        ${esc(platform)}
      </span>`
    : '';

  const typeEl = `<span class="entry-platform">${esc(label)}</span>`;
  const tagsEl = entry.tags
    ? `<div class="entry-tags">${entry.tags.split(',').filter(t => t.trim()).map(t => `<span class="entry-tag">#${esc(t.trim())}</span>`).join('')}</div>`
    : '';
  const dateEl = `<span class="entry-date">${formatDate(entry.created_at)}</span>`;

  return `
    <div class="entry-card" id="ec-${entry.id}">
      ${titleEl}
      <div class="entry-meta">
        ${typeEl}
        ${platformEl}
        ${tagsEl}
        ${dateEl}
      </div>
      <div class="entry-actions">
        <button class="btn-sm" onclick="openEditModal(${entry.id})">Edit</button>
        <button class="btn-sm danger" onclick="deleteSearchEntry(${entry.id})">Delete</button>
      </div>
    </div>
  `;
}

async function deleteSearchEntry(id) {
  const entry = _searchEntries.find(e => e.id === id);
  if (!confirm(`Delete "${entry ? entry.title : 'this entry'}"?`)) return;
  try {
    await fetch(`/api/entries/${id}`, { method: 'DELETE' });
    _searchEntries = _searchEntries.filter(e => e.id !== id);
    const el = document.getElementById('entry-list');
    if (el) el.innerHTML = _searchEntries.length
      ? _searchEntries.map(entry => searchEntryCardHTML(entry)).join('')
      : '<div class="empty-state">No results.</div>';
    showToast('Deleted');
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

// ── Router ────────────────────────────────────────────────────────────────────

function route() {
  const hash = location.hash.slice(1);
  if (!hash) { renderHome(); return; }
  if (hash.startsWith('category/')) { renderCategory(hash.slice(9)); return; }
  if (hash === 'add') { renderAdd(); return; }
  if (hash.startsWith('search/')) { renderSearch(decodeURIComponent(hash.slice(7))); return; }
  renderHome();
}

window.addEventListener('hashchange', route);
window.addEventListener('DOMContentLoaded', () => {
  renderApp();
  route();
});
