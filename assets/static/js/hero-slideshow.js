/**
 * Hero Background Slideshow
 * ─────────────────────────
 * Crossfading background images for the intro/hero section.
 *
 * Features:
 *   - Random image order on each page load (Fisher-Yates shuffle)
 *   - Smooth opacity crossfade (1.5s CSS transition)
 *   - Auto-advances every 6 seconds
 *   - Pauses when page is not visible (Page Visibility API)
 *   - Respects prefers-reduced-motion (shows first image, no cycling)
 */

(function () {
  'use strict';

  var INTERVAL = 6000;

  function HeroSlideshow(section) {
    this.section = section;
    this.slides = Array.prototype.slice.call(
      section.querySelectorAll('.intro__slide')
    );

    if (this.slides.length === 0) return;

    this.current = 0;
    this.timer = null;
    this.reducedMotion = window.matchMedia(
      '(prefers-reduced-motion: reduce)'
    ).matches;

    this._init();
  }

  HeroSlideshow.prototype._init = function () {
    // Fisher-Yates shuffle
    var i = this.slides.length;
    while (i > 1) {
      var j = Math.floor(Math.random() * i);
      i--;
      var tmp = this.slides[i];
      this.slides[i] = this.slides[j];
      this.slides[j] = tmp;
    }

    // Activate first slide
    this.slides[0].classList.add('active');

    // If reduced motion or single slide, show first image only
    if (this.reducedMotion || this.slides.length <= 1) return;

    this._startTimer();

    // Pause when tab is not visible
    var self = this;
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) {
        self._stopTimer();
      } else {
        self._startTimer();
      }
    });
  };

  HeroSlideshow.prototype._advance = function () {
    this.slides[this.current].classList.remove('active');
    this.current = (this.current + 1) % this.slides.length;
    this.slides[this.current].classList.add('active');
  };

  HeroSlideshow.prototype._startTimer = function () {
    if (this.timer) return;
    var self = this;
    this.timer = setInterval(function () {
      self._advance();
    }, INTERVAL);
  };

  HeroSlideshow.prototype._stopTimer = function () {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  };

  // ── Init ──

  function init() {
    var section = document.querySelector('[data-hero-slideshow]');
    if (section) {
      new HeroSlideshow(section);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
