// Client-side title search + entry filters for the series list. All series
// are already rendered server-side in one page, so this just shows/hides
// cards/entries - no server round-trip needed. Sort is handled server-side
// (it needs data the page doesn't otherwise carry, and only changes rarely).
(function () {
  var searchInput = document.getElementById("series-search");
  var showIgnoredCheckbox = document.getElementById("filter-show-ignored");
  var needsPickCheckbox = document.getElementById("filter-needs-pick");
  var countEl = document.getElementById("series-count");
  if (!searchInput) return;

  function applyFilters() {
    var query = searchInput.value.trim().toLowerCase();
    var showIgnored = !showIgnoredCheckbox || showIgnoredCheckbox.checked;
    var onlyNeedsPick = !!(needsPickCheckbox && needsPickCheckbox.checked);
    var visible = 0;

    document.querySelectorAll(".series-list .card").forEach(function (card) {
      var titleMatches = !query || card.getAttribute("data-title").indexOf(query) !== -1;
      var entries = card.querySelectorAll(".entry");
      // A series with no AniList entries at all isn't gated by the entry
      // filters - it's only ever hidden by the title search.
      var anyEntryVisible = entries.length === 0;

      entries.forEach(function (entry) {
        var isIgnored = entry.getAttribute("data-ignored") === "true";
        var isChosen = entry.getAttribute("data-chosen") === "true";
        var entryVisible = (showIgnored || !isIgnored) && (!onlyNeedsPick || !isChosen);
        entry.style.display = entryVisible ? "" : "none";
        if (entryVisible) anyEntryVisible = true;
      });

      var cardVisible = titleMatches && anyEntryVisible;
      card.style.display = cardVisible ? "" : "none";
      if (cardVisible) visible++;
    });

    if (countEl) countEl.textContent = visible;
  }

  searchInput.addEventListener("input", applyFilters);
  if (showIgnoredCheckbox) showIgnoredCheckbox.addEventListener("change", applyFilters);
  if (needsPickCheckbox) needsPickCheckbox.addEventListener("change", applyFilters);
})();
