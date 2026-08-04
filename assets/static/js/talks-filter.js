/*
 * Talk list search + facet filter.
 *
 * Progressive enhancement: templates/talks.html renders the complete list
 * server-side and leaves #talk-filters empty. Everything below is injected
 * here, so with JS disabled the page is still the full, readable programme.
 *
 * Filtering is pure DOM work over the already-rendered <li> elements — no
 * index, no fetch. That matters because /archive/{year}/ is built in
 * the archive build while the Pagefind index only regenerates on a full
 * build, so this must not depend on Pagefind being fresh. For full-text
 * search across abstracts and transcripts the page links out to /search/.
 *
 * Each facet is a combobox: type to narrow the options, Enter or click to
 * toggle one. Twenty tracks as pills pushed the list itself below the fold,
 * which is what the dropdowns fix — the whole filter bar is now two rows
 * regardless of how many values an edition has.
 *
 * State lives in the query string, so a filtered view is shareable:
 *   /archive/2026/talks/?q=polars&track=Data%20Handling&recording=yes
 */
(function () {
  "use strict";

  var FACETS = [
    { key: "track", param: "track", label: "Track", noun: "tracks" },
    { key: "format", param: "format", label: "Format", noun: "formats" },
    { key: "pythonSkill", param: "python_skill", label: "Python skill", noun: "levels" },
    { key: "domainExpertise", param: "domain_expertise", label: "Domain expertise", noun: "levels" },
    { key: "recording", param: "recording", label: "Recording", noun: "options" }
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
    if (key === "recording") {
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

  function labelFor(value) {
    return VALUE_LABELS[value] || value;
  }

  function anyActive() {
    return FACETS.some(function (f) { return active[f.key].size; });
  }

  function build() {
    container.textContent = "";

    var bar = document.createElement("div");
    bar.className = "talk-filters__bar";

    bar.appendChild(buildSearch());
    FACETS.forEach(function (f) {
      var counts = valuesFor(f.key);
      var values = sortValues(f.key, Object.keys(counts));
      // A facet with nothing to choose between is noise.
      if (values.length < 2) return;
      bar.appendChild(buildCombo(f, values, counts));
    });
    container.appendChild(bar);

    if (anyActive()) container.appendChild(buildChips());

    var status = document.createElement("p");
    status.className = "filter-count";
    status.id = "talk-filter-count";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    container.appendChild(status);
  }

  function buildSearch() {
    var field = document.createElement("div");
    field.className = "talk-filters__field talk-filters__field--search";

    var label = document.createElement("label");
    label.className = "talk-filters__label";
    label.setAttribute("for", "talk-search");
    label.textContent = "Search talks";
    field.appendChild(label);

    var input = document.createElement("input");
    input.type = "search";
    input.id = "talk-search";
    input.className = "talk-filters__input";
    input.placeholder = "Title, speaker or abstract…";
    input.autocomplete = "off";
    input.value = query;
    input.addEventListener("input", function () {
      query = input.value.trim();
      updateURL();
      apply();
    });
    field.appendChild(input);
    return field;
  }

  /*
   * One facet as a combobox. The input doubles as the autocomplete filter
   * and as the summary of what is selected, so the control keeps a single
   * line whether nothing or six values are chosen. Selected values are
   * removable from the chip row below the bar.
   */
  function buildCombo(facet, values, counts) {
    var field = document.createElement("div");
    field.className = "talk-filters__field";

    var listId = "facet-list-" + facet.param;
    var label = document.createElement("label");
    label.className = "talk-filters__label";
    label.setAttribute("for", "facet-" + facet.param);
    label.textContent = facet.label;
    field.appendChild(label);

    var combo = document.createElement("div");
    combo.className = "combo";

    var input = document.createElement("input");
    input.type = "text";
    input.id = "facet-" + facet.param;
    input.className = "talk-filters__input combo__input";
    input.autocomplete = "off";
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-controls", listId);
    input.setAttribute("aria-autocomplete", "list");

    var list = document.createElement("ul");
    list.className = "combo__list";
    list.id = listId;
    list.setAttribute("role", "listbox");
    list.setAttribute("aria-multiselectable", "true");
    list.hidden = true;

    var toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "combo__toggle";
    toggle.tabIndex = -1;
    toggle.setAttribute("aria-hidden", "true");
    toggle.textContent = "▾";

    var options = [];
    var cursor = -1;

    values.forEach(function (value, index) {
      var option = document.createElement("li");
      option.className = "combo__option";
      option.id = listId + "-" + index;
      option.setAttribute("role", "option");
      option.dataset.value = value;
      option.dataset.match = labelFor(value).toLowerCase();
      option.setAttribute("aria-selected", active[facet.key].has(value) ? "true" : "false");
      if (active[facet.key].has(value)) option.classList.add("is-selected");

      var text = document.createElement("span");
      text.className = "combo__option-label";
      text.textContent = labelFor(value);
      option.appendChild(text);

      var count = document.createElement("span");
      count.className = "combo__option-count";
      count.textContent = counts[value];
      option.appendChild(count);

      // mousedown, not click: the input's blur would close the list first.
      option.addEventListener("mousedown", function (event) {
        event.preventDefault();
        toggleValue(facet, value);
      });
      list.appendChild(option);
      options.push(option);
    });

    function summarise() {
      var chosen = Array.from(active[facet.key]);
      if (!chosen.length) {
        input.value = "";
        input.placeholder = "All " + facet.noun;
        field.classList.remove("is-filtered");
        return;
      }
      input.value = "";
      input.placeholder = chosen.length === 1
        ? labelFor(chosen[0])
        : chosen.length + " selected";
      field.classList.add("is-filtered");
    }

    function visibleOptions() {
      return options.filter(function (o) { return !o.hidden; });
    }

    function highlight(next) {
      var shown = visibleOptions();
      if (!shown.length) return;
      cursor = (next + shown.length) % shown.length;
      options.forEach(function (o) { o.classList.remove("is-active"); });
      var current = shown[cursor];
      current.classList.add("is-active");
      input.setAttribute("aria-activedescendant", current.id);
      current.scrollIntoView({ block: "nearest" });
    }

    function open() {
      if (!list.hidden) return;
      closeAllCombos();
      list.hidden = false;
      input.setAttribute("aria-expanded", "true");
      cursor = -1;
    }

    function close() {
      list.hidden = true;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      options.forEach(function (o) { o.classList.remove("is-active"); });
      filterOptions("");
      cursor = -1;
    }

    function filterOptions(needle) {
      var text = needle.trim().toLowerCase();
      options.forEach(function (o) {
        o.hidden = text ? o.dataset.match.indexOf(text) === -1 : false;
      });
    }

    input.addEventListener("focus", open);
    input.addEventListener("click", open);
    toggle.addEventListener("mousedown", function (event) {
      event.preventDefault();
      if (list.hidden) { input.focus(); } else { close(); }
    });
    input.addEventListener("input", function () {
      open();
      filterOptions(input.value);
      cursor = -1;
    });
    input.addEventListener("keydown", function (event) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        open();
        highlight(cursor + 1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        open();
        highlight(cursor - 1);
      } else if (event.key === "Enter") {
        var shown = visibleOptions();
        var pick = cursor >= 0 ? shown[cursor] : (shown.length === 1 ? shown[0] : null);
        if (pick) {
          event.preventDefault();
          toggleValue(facet, pick.dataset.value);
        }
      } else if (event.key === "Escape") {
        if (!list.hidden) event.stopPropagation();
        close();
      }
    });
    input.addEventListener("blur", function () {
      // A click on an option fires mousedown first, so the value is already
      // toggled by the time focus leaves.
      window.setTimeout(close, 0);
    });

    summarise();
    combo.appendChild(input);
    combo.appendChild(toggle);
    combo.appendChild(list);
    field.appendChild(combo);
    return field;
  }

  function closeAllCombos() {
    Array.prototype.forEach.call(container.querySelectorAll(".combo__list"), function (list) {
      list.hidden = true;
      var input = list.parentNode.querySelector(".combo__input");
      if (input) input.setAttribute("aria-expanded", "false");
    });
  }

  /* Everything currently narrowing the list, in one removable row — the
     combobox summarises its own facet, but only the chips show the whole
     filter state at a glance. */
  function buildChips() {
    var row = document.createElement("div");
    row.className = "filter-chips";

    var heading = document.createElement("span");
    heading.className = "filter-chips__label talk-info-label";
    heading.textContent = "Filtering by";
    row.appendChild(heading);

    FACETS.forEach(function (f) {
      Array.from(active[f.key]).forEach(function (value) {
        var chip = document.createElement("button");
        chip.type = "button";
        chip.className = "filter-chip";
        chip.title = "Remove filter: " + f.label + " — " + labelFor(value);
        chip.setAttribute("aria-label", chip.title);
        chip.appendChild(document.createTextNode(labelFor(value)));
        var x = document.createElement("span");
        x.className = "filter-chip__x";
        x.setAttribute("aria-hidden", "true");
        x.textContent = "×";
        chip.appendChild(x);
        chip.addEventListener("click", function () { toggleValue(f, value); });
        row.appendChild(chip);
      });
    });

    var clear = document.createElement("button");
    clear.type = "button";
    clear.className = "filter-clear";
    clear.textContent = "Clear all";
    clear.addEventListener("click", function () {
      query = "";
      FACETS.forEach(function (f) { active[f.key].clear(); });
      updateURL();
      build();
      apply();
      var el = document.getElementById("talk-search");
      if (el) el.focus();
    });
    row.appendChild(clear);
    return row;
  }

  function toggleValue(facet, value) {
    if (active[facet.key].has(value)) active[facet.key].delete(value);
    else active[facet.key].add(value);
    updateURL();
    build();
    apply();
    var reopened = document.getElementById("facet-" + facet.param);
    if (reopened) reopened.focus();
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
