(function () {
  "use strict";

  const FILTER_KEYS = [
    { key: "track", param: "track", label: "Track" },
    { key: "python-skill", param: "python_skill", label: "Python Skill" },
    { key: "domain-expertise", param: "domain_expertise", label: "Domain Expertise" },
  ];

  const LEVEL_ORDER = ["Novice", "Intermediate", "Advanced"];

  const container = document.getElementById("talk-filters");
  const talkItems = Array.from(document.querySelectorAll(".talks li"));

  if (!container || talkItems.length === 0) return;

  // --- gather unique values per filter from data attributes ---
  const valuesMap = {};
  FILTER_KEYS.forEach(function (f) {
    const set = {};
    talkItems.forEach(function (li) {
      var v = (li.dataset[toCamel(f.key)] || "").trim();
      if (v) set[v] = (set[v] || 0) + 1;
    });
    valuesMap[f.key] = set;
  });

  // --- read initial selection from URL query params ---
  var activeFilters = {}; // key -> Set of active values
  FILTER_KEYS.forEach(function (f) {
    activeFilters[f.key] = new Set();
  });
  readURL();

  // --- build UI ---
  buildFilterUI();
  applyFilters();

  // --- helpers ---

  function toCamel(s) {
    return s.replace(/-([a-z])/g, function (_, c) { return c.toUpperCase(); });
  }

  function sortValues(key, values) {
    if (key === "track") {
      return values.slice().sort(function (a, b) { return a.localeCompare(b); });
    }
    // sort skill levels in logical order
    return values.slice().sort(function (a, b) {
      var ia = LEVEL_ORDER.indexOf(a);
      var ib = LEVEL_ORDER.indexOf(b);
      if (ia === -1) ia = 999;
      if (ib === -1) ib = 999;
      return ia - ib;
    });
  }

  function readURL() {
    var params = new URLSearchParams(window.location.search);
    FILTER_KEYS.forEach(function (f) {
      var val = params.get(f.param);
      if (val) {
        val.split(",").forEach(function (v) {
          if (v.trim()) activeFilters[f.key].add(v.trim());
        });
      }
    });
  }

  function updateURL() {
    var params = new URLSearchParams();
    FILTER_KEYS.forEach(function (f) {
      if (activeFilters[f.key].size > 0) {
        params.set(f.param, Array.from(activeFilters[f.key]).join(","));
      }
    });
    var qs = params.toString();
    var newURL = window.location.pathname + (qs ? "?" + qs : "");
    history.replaceState(null, "", newURL);
  }

  function buildFilterUI() {
    container.innerHTML = "";

    FILTER_KEYS.forEach(function (f) {
      var values = Object.keys(valuesMap[f.key]);
      if (values.length === 0) return;

      values = sortValues(f.key, values);

      var group = document.createElement("div");
      group.className = "filter-group";

      var label = document.createElement("span");
      label.className = "filter-group-label talk-info-label";
      label.textContent = f.label;
      group.appendChild(label);

      var options = document.createElement("div");
      options.className = "filter-options";

      values.forEach(function (val) {
        var count = valuesMap[f.key][val];
        var span = document.createElement("span");
        span.className = f.key === "track" ? "track filter" : "levels";

        var a = document.createElement("a");
        a.href = "#";
        a.textContent = val + " (" + count + ")";
        a.dataset.filterKey = f.key;
        a.dataset.filterValue = val;

        if (activeFilters[f.key].has(val)) {
          a.classList.add("active");
        }

        a.addEventListener("click", function (e) {
          e.preventDefault();
          toggleFilter(f.key, val, a);
        });

        span.appendChild(a);
        options.appendChild(span);
      });

      group.appendChild(options);
      container.appendChild(group);
    });

    // clear all button
    var hasAny = FILTER_KEYS.some(function (f) { return activeFilters[f.key].size > 0; });
    if (hasAny) {
      var clearBtn = document.createElement("a");
      clearBtn.href = "#";
      clearBtn.className = "filter-clear";
      clearBtn.textContent = "Clear all filters";
      clearBtn.addEventListener("click", function (e) {
        e.preventDefault();
        FILTER_KEYS.forEach(function (f) { activeFilters[f.key].clear(); });
        updateURL();
        buildFilterUI();
        applyFilters();
      });
      container.appendChild(clearBtn);
    }
  }

  function toggleFilter(key, value, anchor) {
    if (activeFilters[key].has(value)) {
      activeFilters[key].delete(value);
    } else {
      activeFilters[key].add(value);
    }
    updateURL();
    buildFilterUI();
    applyFilters();
  }

  function applyFilters() {
    var visibleCount = 0;
    talkItems.forEach(function (li) {
      var show = FILTER_KEYS.every(function (f) {
        if (activeFilters[f.key].size === 0) return true;
        var val = (li.dataset[toCamel(f.key)] || "").trim();
        return activeFilters[f.key].has(val);
      });
      li.style.display = show ? "" : "none";
      if (show) visibleCount++;
    });

    // update count display
    var existing = container.querySelector(".filter-count");
    if (existing) existing.remove();

    var hasAny = FILTER_KEYS.some(function (f) { return activeFilters[f.key].size > 0; });
    if (hasAny) {
      var countEl = document.createElement("span");
      countEl.className = "filter-count";
      countEl.textContent = visibleCount + " of " + talkItems.length + " talks";
      container.appendChild(countEl);
    }
  }
})();
