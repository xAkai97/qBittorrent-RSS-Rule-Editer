// MAL Multi-Select Export - content_script.js
// Injects a simple UI that allows selecting anime cards on MAL and copying
// selected items to the clipboard as JSON/CSV/plain text.

(function () {
  'use strict';

  // Configuration
  const TOOLBAR_ID = 'mal-export-toolbar-v1';
  const CHECKBOX_CLASS = 'mal-export-checkbox-v1';
  const SELECTED_CLASS = 'mal-export-selected-v1';

  // Utility: create the toolbar UI
  function createToolbar() {
    if (document.getElementById(TOOLBAR_ID)) return;

    const toolbar = document.createElement('div');
    toolbar.id = TOOLBAR_ID;
    toolbar.className = 'mal-export-toolbar';

    const countEl = document.createElement('span');
    countEl.id = TOOLBAR_ID + '-count';
    countEl.textContent = '0 selected';
    toolbar.appendChild(countEl);

    const copyBtn = document.createElement('button');
    copyBtn.textContent = 'Copy to clipboard';
    copyBtn.addEventListener('click', onCopyClicked);
    toolbar.appendChild(copyBtn);

    const downloadBtn = document.createElement('button');
    downloadBtn.textContent = 'Download JSON';
    downloadBtn.addEventListener('click', onDownloadClicked);
    toolbar.appendChild(downloadBtn);

    const clearBtn = document.createElement('button');
    clearBtn.textContent = 'Clear';
    clearBtn.addEventListener('click', clearSelections);
    toolbar.appendChild(clearBtn);

    document.body.prepend(toolbar);
  }

  // Utility: find candidate anime card elements on MAL pages.
  // This attempts to handle several MAL layouts (season pages, search results, lists).
  function findAnimeNodes() {
    const nodes = new Set();

    // Season / Browse grid: article.card or .anime-card
    document.querySelectorAll('article, .anime-card, .seasonal-anime').forEach(el => {
      nodes.add(el);
    });

    // Search / list results: .js-seasonal-anime or .anime-list .info
    document.querySelectorAll('.seasonal-anime .info, .anime-list .info').forEach(el => {
      nodes.add(el.closest('div') || el);
    });

    // Fallback: any element with an <a> to /anime/<id>
    document.querySelectorAll('a[href*="/anime/"]')?.forEach(a => {
      const p = a.closest('div, li, article') || a.parentElement;
      if (p) nodes.add(p);
    });

    return Array.from(nodes);
  }

  // Extract metadata for a node: title, url, malId, image
  function extractMeta(node) {
    try {
      // Find link to anime
      const link = node.querySelector('a[href*="/anime/"]');
      const href = link ? link.href : null;
      let malId = null;
      if (href) {
        const m = href.match(/\/anime\/(\d+)/);
        if (m) malId = m[1];
      }

      // Title: prefer h3/h2 or link text
      let title = null;
      const h = node.querySelector('h3, h2, .title, .item-title');
      if (h && h.textContent && h.textContent.trim()) title = h.textContent.trim();
      if (!title && link) title = link.textContent.trim();

      // Image: find img element
      const img = node.querySelector('img') || node.querySelector('picture img');
      const image = img ? (img.src || img.getAttribute('data-src')) : null;

      return { title: title || '', url: href || '', malId: malId || '', image: image || '' };
    } catch (e) {
      return { title: '', url: '', malId: '', image: '' };
    }
  }

  function updateCount() {
    const countEl = document.getElementById(TOOLBAR_ID + '-count');
    const n = document.querySelectorAll('.' + CHECKBOX_CLASS + ':checked')?.length || 0;
    if (countEl) countEl.textContent = `${n} selected`;
  }

  function onCopyClicked() {
    const selected = gatherSelected();
    if (!selected.length) return alert('No items selected');
    const json = JSON.stringify(selected, null, 2);
    navigator.clipboard.writeText(json).then(() => alert('Copied ' + selected.length + ' items (JSON) to clipboard'), err => alert('Copy failed: ' + err));
  }

  function onDownloadClicked() {
    const selected = gatherSelected();
    if (!selected.length) return alert('No items selected');
    const blob = new Blob([JSON.stringify(selected, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'mal-selected.json';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function clearSelections() {
    document.querySelectorAll('.' + CHECKBOX_CLASS).forEach(cb => cb.checked = false);
    document.querySelectorAll('.' + SELECTED_CLASS).forEach(el => el.classList.remove(SELECTED_CLASS));
    updateCount();
  }

  function gatherSelected() {
    const out = [];
    document.querySelectorAll('.' + CHECKBOX_CLASS + ':checked').forEach(cb => {
      const node = cb.__malNodeRef;
      if (!node) return;
      const meta = extractMeta(node);
      out.push(meta);
    });
    return out;
  }

  // Attach checkbox to a node
  function attachCheckbox(node) {
    if (!node || node.__malExportAttached) return;
    node.__malExportAttached = true;

    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.className = CHECKBOX_CLASS;

    cb.style.marginRight = '6px';

    cb.__malNodeRef = node;
    cb.addEventListener('change', () => {
      if (cb.checked) node.classList.add(SELECTED_CLASS); else node.classList.remove(SELECTED_CLASS);
      updateCount();
    });

    // Try to insert at the title area or top-left of the node
    const target = node.querySelector('h3, h2, .title, a') || node.firstElementChild || node;
    try {
      target.prepend(cb);
    } catch (e) {
      node.insertBefore(cb, node.firstChild);
    }
  }

  function ensureToolbar() {
    createToolbar();
  }

  function scanAndAttach() {
    ensureToolbar();
    const nodes = findAnimeNodes();
    nodes.forEach(n => attachCheckbox(n));
  }

  // Observe page changes (useful for dynamic content / SPA navigation)
  const observer = new MutationObserver((mutations) => {
    // Minimal debounce
    if (window.__malExportScanTimer) clearTimeout(window.__malExportScanTimer);
    window.__malExportScanTimer = setTimeout(() => {
      scanAndAttach();
    }, 200);
  });

  observer.observe(document.documentElement || document.body, { childList: true, subtree: true });

  // Initial run
  scanAndAttach();

})();
