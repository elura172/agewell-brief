// Shared by the homepage's frameworks-section shortcut and the dedicated
// /archive/ page's topic filter bar — kept as one module so both call sites
// filter against the exact same logic instead of two copies drifting apart.
export function initArchiveFilter() {
  const filterPills = document.querySelectorAll<HTMLButtonElement>(".filter-pill");
  const archiveItems = document.querySelectorAll<HTMLLIElement>(".archive-item");

  function applyTopicFilter(topic: string) {
    filterPills.forEach((p) => {
      const cat = p.getAttribute("data-topic");
      if (cat === topic) {
        p.classList.add("is-active");
        p.setAttribute("aria-pressed", "true");
      } else {
        p.classList.remove("is-active");
        p.setAttribute("aria-pressed", "false");
      }
    });

    let visibleCount = 0;
    archiveItems.forEach((item) => {
      const rawTopics = item.getAttribute("data-topics") || "";
      const topicList = rawTopics.split("|");

      if (topic === "all" || topicList.includes(topic)) {
        item.style.display = "";
        visibleCount++;
        const indexEl = item.querySelector(".archive-index");
        if (indexEl) indexEl.textContent = String(visibleCount).padStart(2, "0");
      } else {
        item.style.display = "none";
      }
    });

    const statusEl = document.getElementById("filter-status");
    if (statusEl) {
      const label = topic === "all" ? "all topics" : topic;
      statusEl.textContent = `Showing ${visibleCount} ${visibleCount === 1 ? "brief" : "briefs"} for ${label}.`;
    }
  }

  filterPills.forEach((pill) => {
    pill.addEventListener("click", () => {
      const topic = pill.getAttribute("data-topic") || "all";
      applyTopicFilter(topic);
    });
  });

  // Keep topic filters linkable so a copied archive URL can reopen the same
  // selection. Homepage topic links now lead to their dedicated topic pages.
  const requestedTopic = new URLSearchParams(window.location.search).get("topic");
  if (requestedTopic) {
    const match = [...filterPills].find((p) => p.getAttribute("data-topic") === requestedTopic);
    if (match) applyTopicFilter(requestedTopic);
  }

  return { applyTopicFilter };
}
