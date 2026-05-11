(function () {
  'use strict';

  const card = document.getElementById('cert-card');
  if (!card) return;

  const apiBase = (card.dataset.certApi || '').replace(/\/+$/, '');
  const uuid = extractUuid(window.location.pathname);
  if (!uuid || !apiBase) {
    showError();
    return;
  }

  fetchCert(apiBase, uuid);

  function extractUuid(pathname) {
    const match = pathname.match(/\/certificate-share\/([^/]+)\/?$/);
    return match ? match[1] : null;
  }

  async function fetchCert(api, id) {
    try {
      const res = await fetch(`${api}/api/certs/${encodeURIComponent(id)}`, {
        credentials: 'omit',
        cache: 'no-store',
      });
      if (!res.ok) {
        showError();
        return;
      }
      const data = await res.json();
      renderCert(data);
    } catch (err) {
      showError();
    }
  }

  function renderCert(data) {
    setText('cert-name', data.obfuscated_name || '');
    setText('cert-conference', data.conference || '');

    const img = document.getElementById('cert-image');
    if (img && data.image_url) {
      img.src = data.image_url;
      img.alt = `Certificate of Attendance for ${data.obfuscated_name || ''}`;
    }

    const shareUrl = window.location.href;
    const texts = readShareTexts(card, shareUrl);
    wireShareLinks(texts, shareUrl);
    bindLinkedInButton(texts.linkedin, shareUrl);

    document.getElementById('cert-loading').hidden = true;
    document.getElementById('cert-ready').hidden = false;
  }

  function readShareTexts(el, shareUrl) {
    const fields = ['default', 'linkedin', 'x', 'mastodon', 'whatsapp', 'telegram'];
    const out = {};
    for (const f of fields) {
      const raw = el.dataset[`shareText${f[0].toUpperCase() + f.slice(1)}`] || '';
      out[f] = raw.replace(/\{share_url\}/g, shareUrl);
    }
    return out;
  }

  function wireShareLinks(texts, shareUrl) {
    setHref('cert-share-x',
      `https://twitter.com/intent/tweet?text=${encodeURIComponent(texts.x)}`);
    setHref('cert-share-mastodon',
      `https://mastodonshare.com/?text=${encodeURIComponent(texts.mastodon)}`);
    setHref('cert-share-whatsapp',
      `https://wa.me/?text=${encodeURIComponent(texts.whatsapp)}`);
    setHref('cert-share-telegram',
      `https://t.me/share/url?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent(texts.telegram)}`);
    setHref('cert-share-email',
      `mailto:?subject=${encodeURIComponent('Certificate of Attendance — PyCon DE & PyData 2026')}&body=${encodeURIComponent(texts.default)}`);
  }

  function bindLinkedInButton(text, shareUrl) {
    const btn = document.querySelector('[data-share-platform="linkedin"]');
    if (!btn) return;
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      try {
        await navigator.clipboard.writeText(text);
        showToast('Text copied — paste it into your LinkedIn post.');
      } catch (err) {
        // Clipboard refused (e.g. http context); still open the dialog.
      }
      window.open(
        `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`,
        '_blank',
        'noopener',
      );
    });
  }

  function showError() {
    document.getElementById('cert-loading').hidden = true;
    document.getElementById('cert-error').hidden = false;
  }

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function setHref(id, value) {
    const el = document.getElementById(id);
    if (el) el.setAttribute('href', value);
  }

  function showToast(msg) {
    const t = document.getElementById('cert-toast');
    if (!t) return;
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(t._hideTimer);
    t._hideTimer = setTimeout(() => { t.hidden = true; }, 3500);
  }
})();
