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

  Carousel.prototype._visibleCount = function () {
    if (this.mode === 'spotlight') return 1;
    return window.innerWidth > BREAKPOINT ? DESKTOP_VISIBLE : MOBILE_VISIBLE;
  };

  Carousel.prototype._maxPosition = function () {
    return Math.max(0, this.slides.length - this._visibleCount());
  };

  // ── Init ──

  Carousel.prototype._init = function () {
    // Shuffle slide order in the DOM (Fisher-Yates)
    if (this.slides.length > 1) {
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

    // Touch / swipe
    this.el.addEventListener('touchstart', function (e) {
      if (e.touches.length === 1) self.touchStartX = e.touches[0].clientX;
    }, { passive: true });
    this.el.addEventListener('touchend', function (e) {
      if (e.changedTouches.length !== 1) return;
      var diff = self.touchStartX - e.changedTouches[0].clientX;
      if (Math.abs(diff) > SWIPE_THRESHOLD) {
        if (diff > 0) self.next(); else self.prev();
      }
    }, { passive: true });

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
        }, 150);
      });
    }

    if (!this.reducedMotion) {
      this._startTimer();
    }
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
    this.timer = setInterval(function () {
      var max = self._maxPosition();
      self.current = self.current >= max ? 0 : self.current + 1;
      self._update();
    }, INTERVAL);
  };

  Carousel.prototype._resetTimer = function () {
    this.pause();
    if (!this.reducedMotion) this._startTimer();
  };

  Carousel.prototype.pause = function () {
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
  };

  Carousel.prototype.resume = function () {
    if (!this.timer && !this.reducedMotion) this._startTimer();
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
