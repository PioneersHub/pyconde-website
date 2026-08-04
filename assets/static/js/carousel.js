/**
 * Reusable Carousel Component
 * ────────────────────────────
 * Multi-instance, dual-mode carousel for the PyCon DE 2026 website.
 *
 * Modes:
 *   "multi"     — 3 cards on desktop (>768px), 1 on mobile, translateX sliding
 *   "spotlight"  — 1 slide at a time, opacity crossfade
 *
 * Set mode via data-carousel-mode attribute on the root element.
 * Each carousel is identified by data-carousel-id (supports multiple on one page).
 *
 * Features (both modes):
 *   - Auto-advances every 5 seconds
 *   - Random slide order on each page load (always starts at position 0)
 *   - Pauses on hover / focus, resumes on leave
 *   - Keyboard navigation (← → Home End)
 *   - Touch / swipe support
 *   - Respects prefers-reduced-motion
 *   - Graceful degradation: skips if no carousel elements found
 */

(function () {
  'use strict';

  var INTERVAL = 5000;
  var SWIPE_THRESHOLD = 50;
  var DESKTOP_VISIBLE = 3;
  var MOBILE_VISIBLE = 1;
  var BREAKPOINT = 768;

  // ── Constructor ──

  function Carousel(el) {
    this.el = el;
    this.id = el.getAttribute('data-carousel-id') || 'carousel';
    this.mode = el.getAttribute('data-carousel-mode') || 'multi';

    this.track = el.querySelector('.carousel-slides');
    this.slides = Array.prototype.slice.call(el.querySelectorAll('.carousel-slide'));
    this.dots = Array.prototype.slice.call(el.querySelectorAll('.carousel-dot'));
    this.prevBtn = el.querySelector('.carousel-btn--prev');
    this.nextBtn = el.querySelector('.carousel-btn--next');
    this.status = document.getElementById('carousel-status-' + this.id);

    if (this.slides.length === 0) return;

    this.current = 0;
    this.timer = null;
    this.touchStartX = 0;
    this.reducedMotion = window.matchMedia(
      '(prefers-reduced-motion: reduce)'
    ).matches;

    this._init();
  }

  // ── Visible count (mode-aware) ──

  /*
   * How many slides are on screen. A carousel may declare it in CSS as
   * --carousel-visible, in which case that value wins at every breakpoint:
   * the slide width is `calc(100% / var(--carousel-visible))`, so reading
   * the same property here is what keeps the translate maths and the
   * layout from ever disagreeing. Carousels that do not set it keep the
   * original 3-on-desktop / 1-on-mobile behaviour.
   */
  Carousel.prototype._visibleCount = function () {
    if (this.mode === 'spotlight') return 1;
    var declared = parseInt(
      window.getComputedStyle(this.el).getPropertyValue('--carousel-visible'), 10
    );
    if (declared > 0) return declared;
    return window.innerWidth > BREAKPOINT ? DESKTOP_VISIBLE : MOBILE_VISIBLE;
  };

  Carousel.prototype._maxPosition = function () {
    return Math.max(0, this.slides.length - this._visibleCount());
  };

  // ── Init ──

  Carousel.prototype._init = function () {
    // Shuffle slide order in the DOM (Fisher-Yates). Opt out with
    // data-carousel-shuffle="false" where the order carries meaning —
    // newest-first, or a hand-curated running order.
    if (this.slides.length > 1 && this.el.getAttribute('data-carousel-shuffle') !== 'false') {
      var i = this.slides.length;
      while (i > 1) {
        var j = Math.floor(Math.random() * i);
        i--;
        this.track.insertBefore(this.slides[j], this.slides[i].nextSibling);
        var tmp = this.slides[i];
        this.slides[i] = this.slides[j];
        this.slides[j] = tmp;
      }
      // Re-sync dot labels to match the new slide order
      for (var d = 0; d < this.dots.length && d < this.slides.length; d++) {
        var name = this.slides[d].getAttribute('aria-label') || '';
        this.dots[d].setAttribute('aria-label', 'Go to slide ' + (d + 1) + ': ' + name.replace(/^Slide \d+ of \d+:\s*/, ''));
      }
    }

    if (this.slides.length > 1) {
      this._update(true);
    }

    var self = this;
    this.handedOver = false;

    if (this.prevBtn) {
      this.prevBtn.addEventListener('click', function () { self.prev(); });
    }
    if (this.nextBtn) {
      this.nextBtn.addEventListener('click', function () { self.next(); });
    }

    this.dots.forEach(function (dot, i) {
      dot.addEventListener('click', function () { self.goTo(i); });
      dot.addEventListener('keydown', function (e) { self._handleDotKey(e, i); });
    });

    this.el.addEventListener('mouseenter', function () { self.pause(); });
    this.el.addEventListener('mouseleave', function () { self.resume(); });
    this.el.addEventListener('focusin',    function () { self.pause(); });
    this.el.addEventListener('focusout',   function () { self.resume(); });
    this.el.addEventListener('keydown', function (e) { self._handleKey(e); });

    this._initDrag();

    // Resize handler (multi mode recalculates visible count)
    if (this.mode === 'multi') {
      var resizeTimeout;
      window.addEventListener('resize', function () {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(function () {
          if (self.current > self._maxPosition()) {
            self.current = self._maxPosition();
          }
          self._update(true);
          self._syncFit();
        }, 150);
      });
    }

    this._syncFit();
  };

  // ── Navigation ──

  Carousel.prototype.next = function () {
    var max = this._maxPosition();
    this.current = this.current >= max ? 0 : this.current + 1;
    this._update();
    this._resetTimer();
  };

  Carousel.prototype.prev = function () {
    var max = this._maxPosition();
    this.current = this.current <= 0 ? max : this.current - 1;
    this._update();
    this._resetTimer();
  };

  Carousel.prototype.goTo = function (index) {
    var max = this._maxPosition();
    this.current = Math.max(0, Math.min(index, max));
    this._update();
    this._resetTimer();
  };

  // ── Timer ──

  Carousel.prototype._startTimer = function () {
    var self = this;
    if (this.timer) clearInterval(this.timer);
    this.timer = setInterval(function () {
      var max = self._maxPosition();
      self.current = self.current >= max ? 0 : self.current + 1;
      self._update();
    }, INTERVAL);
  };

  Carousel.prototype._resetTimer = function () {
    this.pause();
    if (this._canAutoplay()) this._startTimer();
  };

  Carousel.prototype.pause = function () {
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
  };

  Carousel.prototype.resume = function () {
    if (!this.timer && this._canAutoplay()) this._startTimer();
  };

  /*
   * Autoplay is off when it would be pointless or unwelcome: fewer slides
   * than fit on screen (there is nowhere to go), reduced motion, or the
   * reader having already dragged or swiped — once someone steers, the
   * carousel stops steering itself.
   */
  Carousel.prototype._canAutoplay = function () {
    return !this.reducedMotion && !this.handedOver && this._maxPosition() > 0;
  };

  /* Everything fits: no autoplay, and the controls have nothing to do. */
  Carousel.prototype._syncFit = function () {
    var fits = this._maxPosition() === 0;
    this.el.classList.toggle('carousel--fits', fits);
    if (fits) this.pause();
    else this.resume();
  };

  /* The reader took over — stop moving on our own from here on. */
  Carousel.prototype.handOver = function () {
    this.handedOver = true;
    this.pause();
  };

  // ── Drag / swipe ──

  /*
   * One handler for finger and mouse: pointer events cover both, so the
   * shelf can be pushed around with a trackpad exactly as on a phone. The
   * track follows the pointer live and snaps to the nearest card on
   * release; a drag longer than a few pixels also swallows the click that
   * follows, so dragging across a card never opens it.
   */
  Carousel.prototype._initDrag = function () {
    var self = this;
    var viewport = this.el.querySelector('.carousel-viewport') || this.el;
    var startX = 0, dx = 0, dragging = false, width = 1;

    if (!window.PointerEvent) return;

    viewport.addEventListener('pointerdown', function (e) {
      if (e.pointerType === 'mouse' && e.button !== 0) return;
      if (self._maxPosition() === 0) return;
      dragging = true;
      startX = e.clientX;
      dx = 0;
      width = viewport.getBoundingClientRect().width || 1;
      self.handOver();
      if (self.track) self.track.style.transition = 'none';
      self.el.classList.add('is-dragging');
    });

    viewport.addEventListener('pointermove', function (e) {
      if (!dragging) return;
      dx = e.clientX - startX;
      if (self.mode === 'multi' && self.track) {
        var base = (self.current * 100) / self._visibleCount();
        self.track.style.transform =
          'translateX(calc(-' + base + '% + ' + dx + 'px))';
      }
    });

    function release() {
      if (!dragging) return;
      dragging = false;
      self.el.classList.remove('is-dragging');
      if (self.track) self.track.style.transition = '';
      // A card's width in pixels. If the viewport reports nothing useful,
      // fall back to a single step in the drag's direction rather than
      // dividing by something near zero and flinging to the end.
      var step = width / self._visibleCount();
      var cards = step > 1 ? Math.round(-dx / step) : (dx < 0 ? 1 : -1);
      if (Math.abs(dx) > SWIPE_THRESHOLD) {
        self.goTo(self.current + (cards || (dx < 0 ? 1 : -1)));
      } else {
        self._update();
      }
    }

    viewport.addEventListener('pointerup', release);
    viewport.addEventListener('pointercancel', release);
    viewport.addEventListener('pointerleave', release);

    // A drag that ends on a card must not also follow its link.
    viewport.addEventListener('click', function (e) {
      if (Math.abs(dx) > 5) {
        e.preventDefault();
        e.stopPropagation();
        dx = 0;
      }
    }, true);
  };

  // ── Update DOM (mode-aware) ──

  Carousel.prototype._update = function (instant) {
    if (this.mode === 'spotlight') {
      this._updateSpotlight();
    } else {
      this._updateMulti(instant);
    }
    this._updateDots();
    this._updateStatus();
  };

  /** Spotlight: toggle .active class, opacity crossfade */
  Carousel.prototype._updateSpotlight = function () {
    var idx = this.current;
    this.slides.forEach(function (slide, i) {
      if (i === idx) {
        slide.classList.add('active');
      } else {
        slide.classList.remove('active');
      }
    });
  };

  /** Multi: translateX on track */
  Carousel.prototype._updateMulti = function (instant) {
    var visible = this._visibleCount();
    var pct = (this.current * 100) / visible;

    if (this.track) {
      if (instant) {
        this.track.style.transition = 'none';
        this.track.style.transform = 'translateX(-' + pct + '%)';
        void this.track.offsetHeight; // force reflow
        this.track.style.transition = '';
      } else {
        this.track.style.transform = 'translateX(-' + pct + '%)';
      }
    }
  };

  /** Dots: spotlight highlights 1, multi highlights visible range */
  Carousel.prototype._updateDots = function () {
    var visible = this._visibleCount();
    var start = this.current;
    var end = this.current + visible - 1;

    this.dots.forEach(function (dot, i) {
      var isActive = (i >= start && i <= end);
      if (isActive) {
        dot.classList.add('active');
      } else {
        dot.classList.remove('active');
      }
      dot.setAttribute('aria-selected', isActive ? 'true' : 'false');
      dot.tabIndex = (i === start) ? 0 : -1;
    });
  };

  /** Screen reader announcement */
  Carousel.prototype._updateStatus = function () {
    if (!this.status) return;
    var visible = this._visibleCount();
    if (visible > 1) {
      this.status.textContent =
        'Showing items ' + (this.current + 1) + ' to ' +
        (this.current + visible) + ' of ' + this.slides.length;
    } else {
      this.status.textContent =
        'Slide ' + (this.current + 1) + ' of ' + this.slides.length;
    }
  };

  // ── Keyboard ──

  Carousel.prototype._handleKey = function (e) {
    switch (e.key) {
      case 'ArrowLeft':  e.preventDefault(); this.prev(); break;
      case 'ArrowRight': e.preventDefault(); this.next(); break;
      case 'Home':       e.preventDefault(); this.goTo(0); break;
      case 'End':        e.preventDefault(); this.goTo(this.slides.length - 1); break;
    }
  };

  Carousel.prototype._handleDotKey = function (e, index) {
    switch (e.key) {
      case 'ArrowLeft':
        e.preventDefault();
        this.dots[index === 0 ? this.dots.length - 1 : index - 1].focus();
        break;
      case 'ArrowRight':
        e.preventDefault();
        this.dots[(index + 1) % this.dots.length].focus();
        break;
      case 'Home':  e.preventDefault(); this.dots[0].focus(); break;
      case 'End':   e.preventDefault(); this.dots[this.dots.length - 1].focus(); break;
    }
  };

  // ── Init all carousels on page ──

  function initAllCarousels() {
    var els = document.querySelectorAll('[data-carousel-id]');
    for (var i = 0; i < els.length; i++) {
      new Carousel(els[i]);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAllCarousels);
  } else {
    initAllCarousels();
  }

})();
