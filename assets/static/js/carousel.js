/**
 * Featured Content Spotlight Carousel
 * ────────────────────────────────────
 * Lightweight vanilla JS for the PyCon DE 2026 homepage.
 *
 * - Auto-advances every 7 seconds
 * - Random initial slide on page load
 * - Pauses on hover / focus, resumes on leave
 * - Keyboard navigation (← → Home End)
 * - Touch / swipe support
 * - Respects prefers-reduced-motion
 * - Graceful degradation: exits silently if no carousel on page
 */

(function () {
  'use strict';

  var INTERVAL = 7000;       // ms between auto-advance
  var SWIPE_THRESHOLD = 50;  // px minimum for a swipe

  function FeaturedCarousel() {
    this.el = document.querySelector('.featured-carousel');
    if (!this.el) return;

    this.slides = Array.prototype.slice.call(
      this.el.querySelectorAll('.carousel-slide')
    );
    this.dots = Array.prototype.slice.call(
      this.el.querySelectorAll('.carousel-dot')
    );
    this.prevBtn = this.el.querySelector('.carousel-btn--prev');
    this.nextBtn = this.el.querySelector('.carousel-btn--next');
    this.status = document.getElementById('carousel-status');

    if (this.slides.length === 0) return;

    this.current = 0;
    this.timer = null;
    this.touchStartX = 0;
    this.reducedMotion = window.matchMedia(
      '(prefers-reduced-motion: reduce)'
    ).matches;

    this._init();
  }

  FeaturedCarousel.prototype._init = function () {
    // Random start
    if (this.slides.length > 1) {
      this.current = Math.floor(Math.random() * this.slides.length);
      this._update();
    }

    // Button listeners
    var self = this;

    if (this.prevBtn) {
      this.prevBtn.addEventListener('click', function () {
        self.prev();
      });
    }
    if (this.nextBtn) {
      this.nextBtn.addEventListener('click', function () {
        self.next();
      });
    }

    // Dot listeners
    this.dots.forEach(function (dot, i) {
      dot.addEventListener('click', function () {
        self.goTo(i);
      });
      dot.addEventListener('keydown', function (e) {
        self._handleDotKey(e, i);
      });
    });

    // Pause on hover / focus
    this.el.addEventListener('mouseenter', function () { self.pause(); });
    this.el.addEventListener('mouseleave', function () { self.resume(); });
    this.el.addEventListener('focusin',    function () { self.pause(); });
    this.el.addEventListener('focusout',   function () { self.resume(); });

    // Keyboard navigation on the carousel region
    this.el.addEventListener('keydown', function (e) {
      self._handleKey(e);
    });

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

    // Start auto-advance
    if (!this.reducedMotion) {
      this._startTimer();
    }
  };

  // ── Navigation ──

  FeaturedCarousel.prototype.next = function () {
    this.current = (this.current + 1) % this.slides.length;
    this._update();
    this._resetTimer();
  };

  FeaturedCarousel.prototype.prev = function () {
    this.current = (this.current - 1 + this.slides.length) % this.slides.length;
    this._update();
    this._resetTimer();
  };

  FeaturedCarousel.prototype.goTo = function (index) {
    this.current = Math.max(0, Math.min(index, this.slides.length - 1));
    this._update();
    this._resetTimer();
  };

  // ── Timer ──

  FeaturedCarousel.prototype._startTimer = function () {
    var self = this;
    this.timer = setInterval(function () {
      self.current = (self.current + 1) % self.slides.length;
      self._update();
    }, INTERVAL);
  };

  FeaturedCarousel.prototype._resetTimer = function () {
    this.pause();
    if (!this.reducedMotion) this._startTimer();
  };

  FeaturedCarousel.prototype.pause = function () {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  };

  FeaturedCarousel.prototype.resume = function () {
    if (!this.timer && !this.reducedMotion) {
      this._startTimer();
    }
  };

  // ── Update DOM ──

  FeaturedCarousel.prototype._update = function () {
    var idx = this.current;

    // Slides
    this.slides.forEach(function (slide, i) {
      if (i === idx) {
        slide.classList.add('active');
      } else {
        slide.classList.remove('active');
      }
    });

    // Dots
    this.dots.forEach(function (dot, i) {
      var isActive = (i === idx);
      if (isActive) {
        dot.classList.add('active');
      } else {
        dot.classList.remove('active');
      }
      dot.setAttribute('aria-selected', isActive ? 'true' : 'false');
      dot.tabIndex = isActive ? 0 : -1;
    });

    // Screen reader status
    if (this.status) {
      this.status.textContent =
        'Slide ' + (idx + 1) + ' of ' + this.slides.length;
    }
  };

  // ── Keyboard ──

  FeaturedCarousel.prototype._handleKey = function (e) {
    switch (e.key) {
      case 'ArrowLeft':
        e.preventDefault();
        this.prev();
        break;
      case 'ArrowRight':
        e.preventDefault();
        this.next();
        break;
      case 'Home':
        e.preventDefault();
        this.goTo(0);
        break;
      case 'End':
        e.preventDefault();
        this.goTo(this.slides.length - 1);
        break;
    }
  };

  FeaturedCarousel.prototype._handleDotKey = function (e, index) {
    switch (e.key) {
      case 'ArrowLeft':
        e.preventDefault();
        var prev = index === 0 ? this.dots.length - 1 : index - 1;
        this.dots[prev].focus();
        break;
      case 'ArrowRight':
        e.preventDefault();
        var next = (index + 1) % this.dots.length;
        this.dots[next].focus();
        break;
      case 'Home':
        e.preventDefault();
        this.dots[0].focus();
        break;
      case 'End':
        e.preventDefault();
        this.dots[this.dots.length - 1].focus();
        break;
    }
  };

  // ── Init on DOM ready ──

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      new FeaturedCarousel();
    });
  } else {
    new FeaturedCarousel();
  }

})();
