/**
 * Slideshow
 * ─────────
 * Crossfading slides for every element marked [data-slideshow]: the
 * homepage hero background (macros/intro.html) and the photo slideshow
 * (macros/photo-slideshow.html).
 *
 * Markup:
 *   <div data-slideshow data-slideshow-interval="6000"
 *        data-slideshow-shuffle             (optional)
 *        data-slideshow-pause-on-hover>     (optional)
 *     <figure data-slide class="active">…</figure>   first slide marked
 *     <figure data-slide>…</figure>                  active, so it shows
 *     <button data-slide-dot="0">…</button>          without JS; dots are
 *   </div>                                           optional, DOM index
 *
 * The visible slide carries the class `active`; CSS does the crossfade.
 *
 * Features:
 *   - Random order on each page load when data-slideshow-shuffle is set
 *     (Fisher-Yates shuffle)
 *   - Dots jump to a slide and restart the timer
 *   - Pauses while hovered or focused when data-slideshow-pause-on-hover
 *     is set, and always while the page is not visible
 *   - Respects prefers-reduced-motion (no cycling; dots still work)
 */

(function () {
  'use strict';

  function Slideshow(root) {
    this.root = root;
    this.slides = Array.prototype.slice.call(root.querySelectorAll('[data-slide]'));
    this.dots = Array.prototype.slice.call(root.querySelectorAll('[data-slide-dot]'));

    if (this.slides.length === 0) return;

    this.interval = parseInt(root.getAttribute('data-slideshow-interval'), 10);
    if (!(this.interval > 0)) {
      console.error('Slideshow needs data-slideshow-interval in milliseconds:', root);
      return;
    }

    // Playback order as DOM indices; dots always address DOM indices.
    this.order = this.slides.map(function (_, i) { return i; });
    this.position = 0;
    this.timer = null;
    this.hovered = false;
    this.focused = false;
    this.reducedMotion = window.matchMedia(
      '(prefers-reduced-motion: reduce)'
    ).matches;

    this._init();
  }

  Slideshow.prototype._init = function () {
    var self = this;

    if (this.root.hasAttribute('data-slideshow-shuffle')) {
      var i = this.order.length;
      while (i > 1) {
        var j = Math.floor(Math.random() * i);
        i--;
        var tmp = this.order[i];
        this.order[i] = this.order[j];
        this.order[j] = tmp;
      }
    }

    this._show(this.order[0]);

    this.dots.forEach(function (dot) {
      dot.addEventListener('click', function () {
        var index = parseInt(dot.getAttribute('data-slide-dot'), 10);
        self.position = self.order.indexOf(index);
        self._show(index);
        self._stopTimer();
        self._sync();
      });
    });

    // Reduced motion or a single slide: show one image, never cycle.
    if (this.reducedMotion || this.slides.length <= 1) return;

    if (this.root.hasAttribute('data-slideshow-pause-on-hover')) {
      this.root.addEventListener('mouseenter', function () {
        self.hovered = true;
        self._sync();
      });
      this.root.addEventListener('mouseleave', function () {
        self.hovered = false;
        self._sync();
      });
      this.root.addEventListener('focusin', function () {
        self.focused = true;
        self._sync();
      });
      this.root.addEventListener('focusout', function (event) {
        self.focused = self.root.contains(event.relatedTarget);
        self._sync();
      });
    }

    document.addEventListener('visibilitychange', function () {
      self._sync();
    });

    this._sync();
  };

  Slideshow.prototype._show = function (index) {
    this.slides.forEach(function (slide, i) {
      slide.classList.toggle('active', i === index);
      slide.setAttribute('aria-hidden', i === index ? 'false' : 'true');
    });
    this.dots.forEach(function (dot) {
      var current = parseInt(dot.getAttribute('data-slide-dot'), 10) === index;
      dot.classList.toggle('active', current);
      dot.setAttribute('aria-current', current ? 'true' : 'false');
    });
  };

  Slideshow.prototype._advance = function () {
    this.position = (this.position + 1) % this.order.length;
    this._show(this.order[this.position]);
  };

  // Run the timer only while nothing holds the slideshow still.
  Slideshow.prototype._sync = function () {
    if (this.reducedMotion || this.slides.length <= 1) return;
    if (document.hidden || this.hovered || this.focused) {
      this._stopTimer();
    } else {
      this._startTimer();
    }
  };

  Slideshow.prototype._startTimer = function () {
    if (this.timer) return;
    var self = this;
    this.timer = setInterval(function () {
      self._advance();
    }, this.interval);
  };

  Slideshow.prototype._stopTimer = function () {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  };

  // ── Init ──

  function init() {
    var roots = document.querySelectorAll('[data-slideshow]');
    Array.prototype.forEach.call(roots, function (root) {
      new Slideshow(root);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
