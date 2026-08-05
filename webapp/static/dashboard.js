// Client-side title search + tristate filters for the series list. All
// series are already rendered server-side in one page, so this just
// shows/hides cards/entries - no server round-trip needed. Sort is handled
// server-side (it needs data the page doesn't otherwise carry, and only
// changes rarely).
(function () {
  var searchInput = document.getElementById("series-search");
  var countEl = document.getElementById("series-count");
  var panel = document.getElementById("filter-panel");
  var panelToggle = document.getElementById("filter-panel-toggle");
  var filterCountEl = document.getElementById("filter-count");
  var trackersList = document.getElementById("filter-trackers-list");
  var resetButton = document.getElementById("filter-reset");
  if (!searchInput) return;

  // Entry-level tristate filters: button id -> data-* attribute on .entry.
  var ENTRY_FILTERS = {
    "filter-ignored": "data-ignored",
    "filter-chosen": "data-chosen",
    "filter-has-best": "data-has-best",
    "filter-has-dual-audio": "data-has-dual-audio",
    "filter-has-removed": "data-has-removed",
    "filter-has-preferred": "data-has-preferred",
    "filter-has-private": "data-has-private",
  };

  // known tracker name -> its tristate button element, built dynamically.
  var trackerButtons = {};

  function nextState(state) {
    if (state === "any") return "include";
    if (state === "include") return "exclude";
    return "any";
  }

  function matchesTristate(state, boolValue) {
    if (state === "any") return true;
    if (state === "include") return boolValue === true;
    return boolValue === false; // "exclude"
  }

  function discoverTrackers() {
    var seen = {};
    document.querySelectorAll(".series-list .entry").forEach(function (entry) {
      (entry.getAttribute("data-trackers") || "").split(",").forEach(function (t) {
        if (t) seen[t] = true;
      });
    });

    Object.keys(seen).sort().forEach(function (tracker) {
      if (trackerButtons[tracker]) return;

      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tristate";
      btn.dataset.state = "any";
      btn.dataset.tracker = tracker;
      btn.innerHTML = "<span></span><span class=\"tristate-icon\"></span>";
      btn.querySelector("span").textContent = tracker;
      btn.addEventListener("click", function () {
        btn.dataset.state = nextState(btn.dataset.state);
        applyFilters();
      });

      trackerButtons[tracker] = btn;
      trackersList.appendChild(btn);
    });

    var empty = trackersList.querySelector(".filter-panel-empty");
    if (empty && Object.keys(trackerButtons).length > 0) empty.remove();
  }

  function entryMatchesFilters(entry) {
    for (var id in ENTRY_FILTERS) {
      var btn = document.getElementById(id);
      if (!btn) continue;
      var value = entry.getAttribute(ENTRY_FILTERS[id]) === "true";
      if (!matchesTristate(btn.dataset.state, value)) return false;
    }

    var entryTrackers = (entry.getAttribute("data-trackers") || "").split(",");
    for (var tracker in trackerButtons) {
      var state = trackerButtons[tracker].dataset.state;
      if (state === "any") continue;
      var has = entryTrackers.indexOf(tracker) !== -1;
      if (!matchesTristate(state, has)) return false;
    }

    return true;
  }

  function updateFilterCount() {
    if (!filterCountEl) return;
    var active = document.querySelectorAll(".tristate[data-state=\"include\"], .tristate[data-state=\"exclude\"]").length;
    filterCountEl.textContent = active;
    filterCountEl.hidden = active === 0;
  }

  function applyFilters() {
    discoverTrackers();

    var query = searchInput.value.trim().toLowerCase();
    var mappingBtn = document.getElementById("filter-has-mapping");
    var visible = 0;

    document.querySelectorAll(".series-list .card").forEach(function (card) {
      var titleMatches = !query || card.getAttribute("data-title").indexOf(query) !== -1;
      var hasMapping = card.getAttribute("data-has-mapping") === "true";
      var mappingOk = !mappingBtn || matchesTristate(mappingBtn.dataset.state, hasMapping);

      if (!titleMatches || !mappingOk) {
        card.style.display = "none";
        return;
      }

      var entries = card.querySelectorAll(".entry");
      var anyEntryVisible = entries.length === 0;

      entries.forEach(function (entry) {
        var entryVisible = entryMatchesFilters(entry);
        entry.style.display = entryVisible ? "" : "none";
        if (entryVisible) anyEntryVisible = true;
      });

      card.style.display = anyEntryVisible ? "" : "none";
      if (anyEntryVisible) visible++;
    });

    if (countEl) countEl.textContent = visible;
    updateFilterCount();
  }

  searchInput.addEventListener("input", applyFilters);

  document.querySelectorAll(".filter-panel .tristate[id]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      btn.dataset.state = nextState(btn.dataset.state);
      applyFilters();
    });
  });

  if (resetButton) {
    resetButton.addEventListener("click", function () {
      document.querySelectorAll(".filter-panel .tristate").forEach(function (btn) {
        btn.dataset.state = "any";
      });
      applyFilters();
    });
  }

  if (panelToggle && panel) {
    panelToggle.addEventListener("click", function (e) {
      e.stopPropagation();
      panel.classList.toggle("open");
    });
    panel.addEventListener("click", function (e) { e.stopPropagation(); });
    document.addEventListener("click", function () {
      panel.classList.remove("open");
    });
  }

  // A card/entry swapped in by htmx (after Ignore/Prefer/Download/etc.) is
  // freshly server-rendered and doesn't know about the current search/filter
  // state yet - re-apply on every swap so it doesn't just pop back into
  // view, and pick up any newly-seen tracker along the way.
  document.body.addEventListener("htmx:afterSwap", applyFilters);

  applyFilters();
})();
