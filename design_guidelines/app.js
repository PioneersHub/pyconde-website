/* PyCon DE & PyData 2026 — Design Guidelines App */

(async function () {
  const res = await fetch('design-system.json');
  const DS = await res.json();

  /* ---- helpers ---- */
  function textColorFor(hex) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.55 ? '#1a1a1a' : '#ffffff';
  }

  function isForbidden(list, bg, text) {
    return list.some(c => c.bg === bg && c.text === text);
  }

  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

  /* ---- 1. Color Palette ---- */
  function renderSwatches(colors, containerId) {
    const grid = $(containerId);
    colors.forEach(c => {
      if (!c.hex) {
        // Spot color without hex (e.g., HKS 99K)
        grid.innerHTML += `
          <div class="color-swatch">
            <div class="swatch-color" style="background:repeating-linear-gradient(45deg,#ddd,#ddd 4px,#eee 4px,#eee 8px);color:#666">${c.id}</div>
            <div class="swatch-info">
              <div class="name">${c.name}</div>
              <code>${c.note || 'Spot color'}</code>
            </div>
          </div>`;
        return;
      }
      const txt = textColorFor(c.hex);
      grid.innerHTML += `
        <div class="color-swatch">
          <div class="swatch-color" style="background:${c.hex};color:${txt}">${c.id}</div>
          <div class="swatch-info">
            <div class="name">${c.name}</div>
            <code>${c.hex}</code><br>
            <code>rgb(${c.rgb.join(',')})</code><br>
            <code>${c.cmyk}</code>
          </div>
        </div>`;
    });
  }

  renderSwatches(DS.colors.primary, '#primary-swatches');
  renderSwatches(DS.colors.secondary, '#secondary-swatches');
  renderSwatches(DS.colors.neutral, '#neutral-swatches');

  /* ---- 2. Color Combination Matrices ---- */
  function renderComboMatrix(allColors, forbiddenList, containerId) {
    const grid = $(containerId);
    const cols = allColors.length;
    grid.style.gridTemplateColumns = `72px repeat(${cols}, 1fr)`;

    // Corner cell
    grid.innerHTML = '<div class="combo-header" style="background:#fafafa">BG \\ Text</div>';

    // Header row
    allColors.forEach(c => {
      grid.innerHTML += `<div class="combo-header" style="color:${c.hex}">${c.name}</div>`;
    });

    // Data rows
    allColors.forEach(bg => {
      grid.innerHTML += `<div class="combo-row-label">${bg.name}</div>`;
      allColors.forEach(txt => {
        const same = bg.hex === txt.hex;
        const forbidden = isForbidden(forbiddenList, bg.hex, txt.hex);
        let cls = 'combo-cell';
        if (same) cls += ' self';
        else if (forbidden) cls += ' forbidden';
        const content = same ? '' : 'ABC';
        grid.innerHTML += `<div class="${cls}" style="background:${bg.hex};color:${txt.hex}">${content}</div>`;
      });
    });
  }

  const primaryAll = [
    ...DS.colors.primary,
    { id: 'N1', name: 'Silver', hex: '#b7bcbf' },
    { id: 'WH', name: 'White', hex: '#ffffff' }
  ];
  renderComboMatrix(primaryAll, DS.forbidden_combinations.primary, '#primary-matrix');
  renderComboMatrix(DS.colors.secondary, DS.forbidden_combinations.secondary, '#secondary-matrix');

  /* ---- 2b. Forbidden lists ---- */
  function renderForbiddenList(list, containerId) {
    const el = $(containerId);
    list.forEach(c => {
      el.innerHTML += `
        <div class="forbidden-item">
          <div class="swatch-mini" style="background:${c.bg};color:${c.text}">${c.bg === c.text ? '' : 'Ab'}</div>
          <span>${c.bgName} bg</span>
          <span class="arrow">\u2192</span>
          <span>${c.textName} text</span>
        </div>`;
    });
  }

  renderForbiddenList(DS.forbidden_combinations.primary, '#forbidden-primary');
  renderForbiddenList(DS.forbidden_combinations.secondary, '#forbidden-secondary');

  /* ---- 3. Typography ---- */
  const typeEl = $('#type-examples');
  DS.typography.levels.forEach(l => {
    const fw = l.weight === 'Bold' ? 'bold' : 'normal';
    typeEl.innerHTML += `
      <div class="type-example">
        <div class="label">${l.name} \u2014 ${l.size} ${l.weight}</div>
        <div class="type-specimen" style="font-size:${l.size};font-weight:${fw}">
          PyConDE &amp; PyData Darmstadt 2026
        </div>
      </div>`;
  });

  /* ---- 4. Color Bars ---- */
  const barColors = [
    { name: 'Green',        hex: '#00aa41' },
    { name: 'Lime',         hex: '#96dc00' },
    { name: 'Yellow-Green', hex: '#fac800' },
    { name: 'Cyan',         hex: '#00c8e1' },
    { name: 'Blue',         hex: '#3778be' },
    { name: 'Magenta',      hex: '#d14190' },
    { name: 'Red',          hex: '#c41011' }
  ];
  const barEl = $('#bar-demo');
  barColors.forEach(b => {
    const tc = textColorFor(b.hex);
    barEl.innerHTML += `<div class="bar" style="background:${b.hex};color:${tc}">
      <span class="bar-label">${b.name}</span>
      <span class="bar-unit">height = X</span>
    </div>`;
  });

  /* ---- 5. Page gallery with lightbox ---- */
  const gallery = $('#page-gallery');
  const lightbox = $('#lightbox');
  const lbImg = $('#lb-img');
  const lbCaption = $('#lb-caption');

  DS.pages.forEach(p => {
    gallery.innerHTML += `
      <div class="page-thumb" data-src="${p.image}" data-caption="Page ${p.page}: ${p.title}">
        <img src="${p.image}" alt="Page ${p.page}: ${p.title}" loading="lazy">
        <div class="caption">Page ${p.page}: ${p.title}</div>
      </div>`;
  });

  // Lightbox behavior
  $$('.page-thumb').forEach(thumb => {
    thumb.addEventListener('click', () => {
      lbImg.src = thumb.dataset.src;
      lbCaption.textContent = thumb.dataset.caption;
      lightbox.classList.add('active');
    });
  });

  lightbox.addEventListener('click', () => {
    lightbox.classList.remove('active');
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') lightbox.classList.remove('active');
  });

  /* ---- Nav scroll spy ---- */
  const navLinks = $$('nav a');
  const sections = $$('.section');
  const observer = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        navLinks.forEach(l => l.classList.remove('active'));
        const link = $(`nav a[href="#${e.target.id}"]`);
        if (link) link.classList.add('active');
      }
    });
  }, { rootMargin: '-20% 0px -60% 0px' });
  sections.forEach(s => observer.observe(s));
})();
