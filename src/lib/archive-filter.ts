export function initArchiveFilter() {
  const topicPills = document.querySelectorAll<HTMLButtonElement>("[data-topic]");
  const evidencePills = document.querySelectorAll<HTMLButtonElement>("[data-evidence-filter]");
  const archiveItems = document.querySelectorAll<HTMLLIElement>(".archive-item");
  const archiveList = document.getElementById("archive-list");
  const emptyState = document.getElementById("archive-empty-state");
  const searchInput = document.getElementById("archive-search-input") as HTMLInputElement | null;
  const clearSearchBtn = document.getElementById("archive-search-clear") as HTMLButtonElement | null;
  const kbdHint = document.getElementById("archive-kbd-hint");
  const countEl = document.getElementById("archive-results-count");
  const resetInlineBtn = document.getElementById("archive-reset-inline") as HTMLButtonElement | null;
  const resetEmptyBtn = document.getElementById("archive-reset-empty") as HTMLButtonElement | null;
  const statusEl = document.getElementById("filter-status");

  const totalCount = archiveItems.length;
  let activeTopic = "all";
  let activeEvidence = "all";
  let rawQuery = "";

  function syncUrl() {
    const url = new URL(window.location.href);
    if (rawQuery.trim()) {
      url.searchParams.set("q", rawQuery.trim());
    } else {
      url.searchParams.delete("q");
    }
    if (activeTopic !== "all") {
      url.searchParams.set("topic", activeTopic);
    } else {
      url.searchParams.delete("topic");
    }
    if (activeEvidence !== "all") {
      url.searchParams.set("evidence", activeEvidence);
    } else {
      url.searchParams.delete("evidence");
    }
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  }

  function applyFilters(updateHistory = true) {
    const tokens = rawQuery
      .toLowerCase()
      .trim()
      .split(/\s+/)
      .filter(Boolean);

    topicPills.forEach((pill) => {
      const isMatch = pill.getAttribute("data-topic") === activeTopic;
      pill.classList.toggle("is-active", isMatch);
      pill.setAttribute("aria-pressed", String(isMatch));
    });

    evidencePills.forEach((pill) => {
      const isMatch = pill.getAttribute("data-evidence-filter") === activeEvidence;
      pill.classList.toggle("is-active", isMatch);
      pill.setAttribute("aria-pressed", String(isMatch));
    });

    let visibleCount = 0;
    archiveItems.forEach((item) => {
      const itemTopics = (item.getAttribute("data-topics") || "").split("|");
      const itemEvidence = item.getAttribute("data-evidence") || "";
      const haystack = item.getAttribute("data-search") || "";

      const matchesTopic = activeTopic === "all" || itemTopics.includes(activeTopic);
      const matchesEvidence = activeEvidence === "all" || itemEvidence === activeEvidence;
      const matchesQuery = tokens.length === 0 || tokens.every((tok) => haystack.includes(tok));

      if (matchesTopic && matchesEvidence && matchesQuery) {
        item.style.display = "";
        visibleCount++;
        const indexEl = item.querySelector(".archive-index");
        if (indexEl) indexEl.textContent = String(visibleCount).padStart(2, "0");
      } else {
        item.style.display = "none";
      }
    });

    const isFiltered = activeTopic !== "all" || activeEvidence !== "all" || tokens.length > 0;

    if (clearSearchBtn) clearSearchBtn.hidden = rawQuery.length === 0;
    if (kbdHint) kbdHint.hidden = rawQuery.length > 0;
    if (resetInlineBtn) resetInlineBtn.hidden = !isFiltered;
    if (archiveList) archiveList.hidden = visibleCount === 0;
    if (emptyState) emptyState.hidden = visibleCount > 0;

    const summary = isFiltered
      ? `Showing ${visibleCount} of ${totalCount} ${totalCount === 1 ? "edition" : "editions"}`
      : `Showing all ${totalCount} ${totalCount === 1 ? "edition" : "editions"}`;

    if (countEl) countEl.textContent = summary;
    if (statusEl) statusEl.textContent = `${summary}.`;

    if (updateHistory) syncUrl();
  }

  function resetAll(focusSearch = false) {
    activeTopic = "all";
    activeEvidence = "all";
    rawQuery = "";
    if (searchInput) {
      searchInput.value = "";
      if (focusSearch) searchInput.focus();
    }
    applyFilters(true);
  }

  topicPills.forEach((pill) => {
    pill.addEventListener("click", () => {
      activeTopic = pill.getAttribute("data-topic") || "all";
      applyFilters(true);
    });
  });

  evidencePills.forEach((pill) => {
    pill.addEventListener("click", () => {
      activeEvidence = pill.getAttribute("data-evidence-filter") || "all";
      applyFilters(true);
    });
  });

  if (searchInput) {
    searchInput.addEventListener("input", () => {
      rawQuery = searchInput.value;
      applyFilters(true);
    });

    searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        if (searchInput.value.length > 0) {
          e.preventDefault();
          rawQuery = "";
          searchInput.value = "";
          applyFilters(true);
        } else {
          searchInput.blur();
        }
      }
    });
  }

  if (clearSearchBtn && searchInput) {
    clearSearchBtn.addEventListener("click", () => {
      rawQuery = "";
      searchInput.value = "";
      applyFilters(true);
      searchInput.focus();
    });
  }

  if (resetInlineBtn) {
    resetInlineBtn.addEventListener("click", () => resetAll(false));
  }

  if (resetEmptyBtn) {
    resetEmptyBtn.addEventListener("click", () => resetAll(true));
  }

  document.addEventListener("keydown", (e) => {
    if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
    const target = e.target as HTMLElement | null;
    const tag = target?.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target?.isContentEditable) return;
    if (searchInput) {
      e.preventDefault();
      searchInput.focus();
      searchInput.select();
    }
  });

  const params = new URLSearchParams(window.location.search);
  const paramTopic = params.get("topic");
  const paramEvidence = params.get("evidence");
  const paramQuery = params.get("q");

  if (paramTopic && [...topicPills].some((p) => p.getAttribute("data-topic") === paramTopic)) {
    activeTopic = paramTopic;
  }
  if (paramEvidence && [...evidencePills].some((p) => p.getAttribute("data-evidence-filter") === paramEvidence)) {
    activeEvidence = paramEvidence;
  }
  if (paramQuery && searchInput) {
    rawQuery = paramQuery;
    searchInput.value = paramQuery;
  }

  applyFilters(false);

  return { applyFilters, resetAll };
}
