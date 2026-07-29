/*
 * Talk list search + facet filter.
 *
 * Progressive enhancement: templates/talks.html renders the complete list
 * server-side and leaves #talk-filters empty. Everything below is injected
 * here, so with JS disabled the page is still the full, readable programme.
 *
 * Filtering is pure DOM work over the already-rendered <li> elements — no
 * index, no fetch. That matters because /archive/{year}/talks/ is built in
 * the archive build while the Pagefind index only regenerates on a full
 * build, so this must not depend on Pagefind being fresh. For full-text
 * search across abstracts and transcripts the page links out to /search/.
 *
 * State lives in the query string, so a filtered view is shareable:
 *   /archive/2026/talks/?q=polars&track=Data%20Handling&recording=yes
 */
(function () {
  "use strict";

  var FACETS = [
    { key: "track", param: "track", label: "Track" },
    { key: "format", param: "format", label: "Format" },
    { key: "pythonSkill", param: "python_skill", label: "Python skill" },
    { key: "domainExpertise", param: "domain_expertise", label: "Domain expertise" },
    { key: "recording", param: "recording", label: "Recording" },
    { key: "transcript", param: "transcript", label: "Transcript" }
  ];

  // Skill levels read as a progression, not an alphabet.
  var LEVEL_ORDER = ["Novice", "Intermediate", "Advanced", "Expert"];
  var YES_NO_ORDER = ["yes", "no"];
  var VALUE_LABELS = { yes: "Available", no: "Not available" };

  var container = document.getElementById("talk-filters");
  var items = Array.prototype.slice.call(document.querySelectorAll(".talks > li"));
  if (!container || !items.length) return;

  var active = {};
  var query = "";
  FACETS.forEach(function (f) { active[f.key] = new Set(); });

  readURL();
  build();
  apply();

  function readURL() {
    var params = new URLSearchParams(window.location.search);
    query = (params.get("q") || "").trim();
    FACETS.forEach(function (f) {
      var raw = params.get(f.param);
      if (!raw) return;
      raw.split(",").forEach(function (v) {
        if (v.trim()) active[f.key].add(v.trim());
      });
    });
  }

  function updateURL() {
    var params = new URLSearchParams();
    if (query) params.set("q", query);
    FACETS.forEach(function (f) {
      if (active[f.key].size) {
        params.set(f.param, Array.from(active[f.key]).join(","));
      }
    });
    var qs = params.toString();
    history.replaceState(null, "", window.location.pathname + (qs ? "?" + qs : ""));
  }

  // The Pretalx importer writes the literal string "None" when a question
  // went unanswered (39 of the 2026 talks have python_skill: None). It is a
  // null marker, not a level, so it must not become a facet value.
  function isMissing(v) {
    return !v || v === "None";
  }

  function valuesFor(key) {
    var counts = Object.create(null);
    items.forEach(function (li) {
      var v = (li.dataset[key] || "").trim();
      if (!isMissing(v)) counts[v] = (counts[v] || 0) + 1;
    });
    return counts;
  }

  function sortValues(key, values) {
    if (key === "recording" || key === "transcript") {
      return values.slice().sort(function (a, b) {
        return YES_NO_ORDER.indexOf(a) - YES_NO_ORDER.indexOf(b);
      });
    }
    if (key === "pythonSkill" || key === "domainExpertise") {
      return values.slice().sort(function (a, b) {
        var ia = LEVEL_ORDER.indexOf(a), ib = LEVEL_ORDER.indexOf(b);
        return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
      });
    }
    return values.slice().sort(function (a, b) { return a.localeCompare(b); });
  }

  function build() {
    container.textContent = "";

    var search = document.createElement("div");
    search.className = "talk-filters__search";

    var label = document.createElement("label");
    label.className = "talk-filters__search-label";
    label.setAttribute("for", "talk-search");
    label.textContent = "Search talks";
    search.appendChild(label);

    var input = document.createElement("input");
    input.type = "search";
    input.id = "talk-search";
    input.className = "talk-filters__search-input";
    input.placeholder = "Title, speaker or abstract…";
    input.autocomplete = "off";
    input.value = query;
    input.addEventListener("input", function () {
      query = input.value.trim();
      updateURL();
      apply();
    });
    search.appendChild(input);
    container.appendChild(search);

    FACETS.forEach(function (f) {
      var counts = valuesFor(f.key);
      var values = sortValues(f.key, Object.keys(counts));
      // A facet with nothing to choose between is noise.
      if (values.length < 2) return;

      var group = document.createElement("div");
      group.className = "filter-group";

      var groupLabel = document.createElement("span");
      groupLabel.className = "filter-group-label talk-info-label";
      groupLabel.id = "facet-" + f.param;
      groupLabel.textContent = f.label;
      group.appendChild(groupLabel);

      var options = document.createElement("div");
      options.className = "filter-options";
      options.setAttribute("role", "group");
      options.setAttribute("aria-labelledby", groupLabel.id);

      values.forEach(function (val) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "filter-option";
        btn.dataset.filterKey = f.key;
        btn.dataset.filterValue = val;
        btn.textContent = (VALUE_LABELS[val] || val) + " (" + counts[val] + ")";
        btn.setAttribute("aria-pressed", active[f.key].has(val) ? "true" : "false");
        if (active[f.key].has(val)) btn.classList.add("active");
        btn.addEventListener("click", function () {
          if (active[f.key].has(val)) active[f.key].delete(val);
          else active[f.key].add(val);
          updateURL();
          build();
          apply();
        });
        options.appendChild(btn);
      });

      group.appendChild(options);
      container.appendChild(group);
    });

    var status = document.createElement("p");
    status.className = "filter-count";
    status.id = "talk-filter-count";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    container.appendChild(status);

    if (query || FACETS.some(function (f) { return active[f.key].size; })) {
      var clear = document.createElement("button");
      clear.type = "button";
      clear.className = "filter-clear";
      clear.textContent = "Clear all filters";
      clear.addEventListener("click", function () {
        query = "";
        FACETS.forEach(function (f) { active[f.key].clear(); });
        updateURL();
        build();
        apply();
        var el = document.getElementById("talk-search");
        if (el) el.focus();
      });
      container.appendChild(clear);
    }
  }

  function apply() {
    var needle = query.toLowerCase();
    var visible = 0;
    items.forEach(function (li) {
      var show = FACETS.every(function (f) {
        if (!active[f.key].size) return true;
        return active[f.key].has((li.dataset[f.key] || "").trim());
      });
      if (show && needle) {
        show = (li.dataset.search || "").indexOf(needle) !== -1;
      }
      li.hidden = !show;
      if (show) visible++;
    });

    var status = document.getElementById("talk-filter-count");
    if (!status) return;
    if (visible === items.length) {
      status.textContent = items.length + " talks";
    } else if (visible === 0) {
      status.textContent = "No talks match. Try fewer filters, or search all editions.";
    } else {
      status.textContent = visible + " of " + items.length + " talks";
    }
  }
})();
