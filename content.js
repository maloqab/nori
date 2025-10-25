const OVERLAY_ID = "nori-overlay";
const TEXTAREA_ID = "nori-textarea";
const CLOSE_BUTTON_ID = "nori-close";
const STORAGE_KEY = "nori_note";
const HISTORY_KEY = "nori_notes";
const HISTORY_LIMIT = 50;
const ANIMATION_DURATION_MS = 250;

const HISTORY_TOGGLE_ID = "nori-history-toggle";
const SIDEBAR_ID = "nori-sidebar";
const HISTORY_LIST_ID = "nori-history-list";
const EXPORT_BUTTON_ID = "nori-export";
const TOAST_ID = "nori-toast";
const SIDEBAR_OPEN_CLASS = "sidebar-open";

const ICON_SVGS = {
  history: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg>`,
  lock: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="1.5"/><path d="M9 11V8a3 3 0 0 1 6 0v3"/></svg>`,
  unlock: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="1.5"/><path d="M9 11V8a3 3 0 0 1 5.5-1.5"/></svg>`,
  delete: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 7h14"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M8 7l1-3h6l1 3"/><path d="M6 7l.5 13h11L18 7"/></svg>`,
  export: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v11"/><path d="M8 9l4-4 4 4"/><path d="M5 16v1.5A1.5 1.5 0 0 0 6.5 19h11a1.5 1.5 0 0 0 1.5-1.5V16"/></svg>`,
  back: `<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9.6 6v12" stroke-width="1.5"/><path d="M18 12h-6.1" stroke-width="1.4"/><path d="M15 8.5 11.9 12l3.1 3.5" stroke-width="1.7"/></svg>`,
};

const storageGet = (keys) =>
  new Promise((resolve) => {
    chrome.storage.sync.get(keys, (result) => {
      if (chrome.runtime.lastError) {
        resolve({});
        return;
      }
      resolve(result);
    });
  });

const storageSet = (items) =>
  new Promise((resolve) => {
    chrome.storage.sync.set(items, () => {
      resolve(!chrome.runtime.lastError);
    });
  });

let historyState = [];
let currentOverlay = null;
let currentNoteId = null;

const handleKeydown = (event) => {
  if (event.key === "Escape") {
    void closeOverlay();
  }
};

const generateNoteId = () => {
  if (crypto?.randomUUID) {
    return crypto.randomUUID();
  }

  return `nori_${Date.now().toString(36)}_${Math.random()
    .toString(16)
    .slice(2, 8)}`;
};

const formatTimestamp = (iso, forExport = false) => {
  if (!iso) {
    return "";
  }

  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  if (forExport) {
    return date.toISOString();
  }

  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "numeric",
    minute: "2-digit",
  });
};

const showToast = (message) => {
  if (!currentOverlay) {
    return;
  }

  const toast = currentOverlay.querySelector(`#${TOAST_ID}`);
  if (!toast) {
    return;
  }

  toast.textContent = message;
  toast.classList.add("visible");

  window.setTimeout(() => {
    toast.classList.remove("visible");
  }, 2400);
};

const enforceHistoryLimit = (notes) => {
  const copy = [...notes];

  while (copy.length > HISTORY_LIMIT) {
    let removalIndex = -1;
    for (let idx = copy.length - 1; idx >= 0; idx -= 1) {
      if (!copy[idx].locked) {
        removalIndex = idx;
        break;
      }
    }

    if (removalIndex === -1) {
      return { success: false, notes: notes.slice(1) };
    }

    copy.splice(removalIndex, 1);
  }

  return { success: true, notes: copy };
};

const renderHistoryList = () => {
  if (!currentOverlay) {
    return;
  }

  const container = currentOverlay.querySelector(`#${HISTORY_LIST_ID}`);
  if (!container) {
    return;
  }

  container.textContent = "";

  if (!historyState.length) {
    const empty = document.createElement("p");
    empty.className = "nori-history-empty";
    empty.textContent =
      "Your saved notes will collect here once you close the overlay.";
    container.appendChild(empty);
    return;
  }

  historyState.forEach((note) => {
    const item = document.createElement("article");
    item.className = "nori-history-item";
    item.dataset.noteId = note.id;
    if (note.id === currentNoteId) {
      item.classList.add("active");
    }
    if (note.locked) {
      item.classList.add("locked");
    }

    const meta = document.createElement("div");
    meta.className = "nori-history-meta";

    const timestamp = document.createElement("time");
    timestamp.className = "nori-history-time";
    timestamp.textContent = formatTimestamp(note.updatedAt || note.createdAt);
    timestamp.dateTime = note.updatedAt || note.createdAt || "";

    const actions = document.createElement("div");
    actions.className = "nori-history-actions";

    const lockButton = document.createElement("button");
    lockButton.type = "button";
    lockButton.className = "nori-icon-btn nori-lock-btn";
    lockButton.innerHTML = note.locked ? ICON_SVGS.lock : ICON_SVGS.unlock;
    lockButton.dataset.action = "toggle-lock";
    lockButton.setAttribute("aria-pressed", note.locked ? "true" : "false");
    lockButton.title = note.locked ? "Unlock note" : "Lock note";

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "nori-icon-btn nori-delete-btn";
    deleteButton.innerHTML = ICON_SVGS.delete;
    deleteButton.dataset.action = "delete-note";
    deleteButton.title = "Delete note";

    actions.append(lockButton, deleteButton);
    meta.append(timestamp, actions);

    const bodyButton = document.createElement("button");
    bodyButton.type = "button";
    bodyButton.className = "nori-history-body";
    bodyButton.dataset.action = "load-note";
    bodyButton.textContent = note.content.trim() || "(empty note)";

    item.append(meta, bodyButton);
    container.appendChild(item);
  });
};

const setSidebarState = (open) => {
  if (!currentOverlay) {
    return;
  }

  const sidebar = currentOverlay.querySelector(`#${SIDEBAR_ID}`);
  const toggle = currentOverlay.querySelector(`#${HISTORY_TOGGLE_ID}`);
  if (!sidebar) {
    return;
  }

  if (open) {
    currentOverlay.classList.add(SIDEBAR_OPEN_CLASS);
    sidebar.setAttribute("aria-hidden", "false");
    toggle?.setAttribute("aria-expanded", "true");
  } else {
    currentOverlay.classList.remove(SIDEBAR_OPEN_CLASS);
    sidebar.setAttribute("aria-hidden", "true");
    toggle?.setAttribute("aria-expanded", "false");
  }
};

const resetCurrentNoteContext = () => {
  currentNoteId = null;
};

const persistCurrentValue = async (value) => {
  await storageSet({ [STORAGE_KEY]: value });
};

const persistHistory = async () => {
  await storageSet({ [HISTORY_KEY]: historyState });
};

const handleNoteFinalization = async (rawValue) => {
  const trimmed = rawValue.trim();

  if (!trimmed) {
    if (currentNoteId) {
      const existingIndex = historyState.findIndex(
        (note) => note.id === currentNoteId
      );
      if (existingIndex !== -1) {
        const updatedHistory = [...historyState];
        updatedHistory.splice(existingIndex, 1);
        historyState = updatedHistory;
        await persistHistory();
        renderHistoryList();
      }
    }
    resetCurrentNoteContext();
    await persistCurrentValue("");
    return true;
  }

  const timestamp = new Date().toISOString();

  if (currentNoteId) {
    const existingIndex = historyState.findIndex(
      (note) => note.id === currentNoteId
    );

    if (existingIndex !== -1) {
      const existing = historyState[existingIndex];
      const updatedNote = {
        ...existing,
        content: rawValue,
        updatedAt: timestamp,
      };

      const reordered = [...historyState];
      reordered.splice(existingIndex, 1);
      reordered.unshift(updatedNote);

      historyState = reordered;
      await persistCurrentValue(rawValue);
      await persistHistory();
      renderHistoryList();
      return true;
    }

    resetCurrentNoteContext();
  }

  const newNote = {
    id: generateNoteId(),
    content: rawValue,
    createdAt: timestamp,
    updatedAt: timestamp,
    locked: false,
  };

  const candidateHistory = [newNote, ...historyState];
  const check = enforceHistoryLimit(candidateHistory);

  if (!check.success) {
    showToast("All notes are locked. Unlock one to add a new note.");
    return false;
  }

  historyState = check.notes;
  currentNoteId = newNote.id;
  await persistCurrentValue(rawValue);
  await persistHistory();
  renderHistoryList();
  showToast("Saved to history.");
  return true;
};

const closeOverlay = async () => {
  const overlay = document.getElementById(OVERLAY_ID);
  if (!overlay || overlay.dataset.closing === "true") {
    return;
  }

  const textarea = overlay.querySelector(`#${TEXTAREA_ID}`);
  const noteValue = textarea ? textarea.value : "";
  const canClose = await handleNoteFinalization(noteValue);

  if (!canClose) {
    textarea?.focus({ preventScroll: true });
    return;
  }

  overlay.dataset.closing = "true";
  resetCurrentNoteContext();

  overlay.classList.remove("fade-in");
  overlay.classList.add("fade-out");
  document.removeEventListener("keydown", handleKeydown);

  window.setTimeout(() => {
    overlay.remove();
    currentOverlay = null;
  }, ANIMATION_DURATION_MS);
};

const handleHistoryAction = async (event) => {
  const target = event.target;
  const actionElement = target.closest("[data-action]");
  if (!actionElement) {
    return;
  }

  const action = actionElement.dataset.action;
  const itemElement = actionElement.closest("[data-note-id]");
  if (!itemElement) {
    return;
  }

  const noteId = itemElement.dataset.noteId;
  const noteIndex = historyState.findIndex((note) => note.id === noteId);
  if (noteIndex === -1) {
    return;
  }

  const textarea = currentOverlay?.querySelector(`#${TEXTAREA_ID}`);

  if (action === "load-note") {
    const note = historyState[noteIndex];
    if (textarea) {
      textarea.value = note.content;
      textarea.focus({ preventScroll: true });
      currentNoteId = note.id;
      await persistCurrentValue(note.content);
      renderHistoryList();
      showToast("Loaded note into editor.");
      setSidebarState(false);
    }
    return;
  }

  if (action === "toggle-lock") {
    const note = historyState[noteIndex];
    const updated = { ...note, locked: !note.locked, updatedAt: note.updatedAt };
    const newHistory = [...historyState];
    newHistory.splice(noteIndex, 1, updated);
    historyState = newHistory;
    await persistHistory();
    renderHistoryList();
    showToast(updated.locked ? "Note locked." : "Note unlocked.");
    return;
  }

  if (action === "delete-note") {
    const note = historyState[noteIndex];
    const newHistory = [...historyState];
    newHistory.splice(noteIndex, 1);
    historyState = newHistory;
    if (currentNoteId === note.id) {
      resetCurrentNoteContext();
    }
    await persistHistory();
    renderHistoryList();
    showToast("Note deleted.");
  }
};

const exportHistoryToMarkdown = () => {
  if (!historyState.length) {
    showToast("No notes to export yet.");
    return;
  }

  const exportTimestamp = new Date().toISOString();
  const lines = [
    "# Nori Notes Export",
    "",
    `Exported on ${exportTimestamp}`,
    "",
  ];

  historyState.forEach((note, index) => {
    const heading = `## Note ${historyState.length - index}${
      note.locked ? " (locked)" : ""
    }`;
    lines.push(heading);
    if (note.updatedAt || note.createdAt) {
      lines.push(`_Last updated: ${formatTimestamp(note.updatedAt || note.createdAt, true)}_`);
    }
    lines.push("");
    lines.push(note.content || "(empty note)");
    lines.push("");
  });

  const blob = new Blob([lines.join("\n")], {
    type: "text/markdown;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `nori-notes-${exportTimestamp.slice(0, 10)}.md`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
  showToast("Export started.");
};

const attachOverlayEvents = () => {
  if (!currentOverlay) {
    return;
  }

  const textarea = currentOverlay.querySelector(`#${TEXTAREA_ID}`);
  const closeButton = currentOverlay.querySelector(`#${CLOSE_BUTTON_ID}`);
  const historyToggle = currentOverlay.querySelector(`#${HISTORY_TOGGLE_ID}`);
  const historyList = currentOverlay.querySelector(`#${HISTORY_LIST_ID}`);
  const exportButton = currentOverlay.querySelector(`#${EXPORT_BUTTON_ID}`);
  const sidebarClose = currentOverlay.querySelector("#nori-sidebar-close");
  const sidebar = currentOverlay.querySelector(".nori-sidebar");
  const sidebarReveal = currentOverlay.querySelector(".nori-sidebar__reveal-zone");
  const sidebarHeader = currentOverlay.querySelector(".nori-sidebar__header");
  const header = currentOverlay.querySelector(".nori-main__header");
  const footer = currentOverlay.querySelector(".nori-main__footer");
  const topZone = currentOverlay.querySelector(".nori-control-zone--top");
  const bottomZone = currentOverlay.querySelector(".nori-control-zone--bottom");

  textarea?.addEventListener("input", (event) => {
    const value = event.target.value;
    persistCurrentValue(value);
  });

  closeButton?.addEventListener("click", () => {
    void closeOverlay();
  });

  historyToggle?.addEventListener("click", () => {
    const isOpen = currentOverlay?.classList.contains(SIDEBAR_OPEN_CLASS);
    setSidebarState(!isOpen);
  });

  sidebarClose?.addEventListener("click", () => {
    setSidebarState(false);
  });

  historyList?.addEventListener("click", (event) => {
    void handleHistoryAction(event);
  });

  exportButton?.addEventListener("click", () => {
    exportHistoryToMarkdown();
  });

  const focusTextarea = () => {
    textarea?.focus({ preventScroll: true });
  };

  const bindHoverToggle = (element, className) => {
    if (!element) {
      return;
    }
    element.addEventListener("mouseenter", () => {
      currentOverlay?.classList.add(className);
    });
    element.addEventListener("mouseleave", () => {
      currentOverlay?.classList.remove(className);
    });
  };

  const bindFocusToggle = (element, className) => {
    if (!element) {
      return;
    }
    element.addEventListener("focus", () => {
      currentOverlay?.classList.add(className);
    });
    element.addEventListener("blur", () => {
      currentOverlay?.classList.remove(className);
    });
  };

  bindHoverToggle(topZone, "top-hover");
  bindHoverToggle(header, "top-hover");
  bindHoverToggle(historyToggle, "top-hover");
  bindHoverToggle(closeButton, "top-hover");
  bindHoverToggle(sidebarClose, "top-hover");

  bindFocusToggle(historyToggle, "top-hover");
  bindFocusToggle(closeButton, "top-hover");
  bindFocusToggle(sidebarClose, "top-hover");

  bindHoverToggle(bottomZone, "bottom-hover");
  bindHoverToggle(footer, "bottom-hover");
  bindHoverToggle(exportButton, "bottom-hover");

  bindFocusToggle(exportButton, "bottom-hover");

  topZone?.addEventListener("click", focusTextarea);
  bottomZone?.addEventListener("click", focusTextarea);

  let sidebarHideTimeout = null;

  const showSidebarControls = () => {
    if (!sidebar) {
      return;
    }
    if (sidebarHideTimeout) {
      clearTimeout(sidebarHideTimeout);
      sidebarHideTimeout = null;
    }
    sidebar.classList.add("show-controls");
  };

  const scheduleHideSidebarControls = (delay = 140) => {
    if (!sidebar) {
      return;
    }
    if (sidebarHideTimeout) {
      clearTimeout(sidebarHideTimeout);
    }
    sidebarHideTimeout = window.setTimeout(() => {
      sidebar.classList.remove("show-controls");
      sidebarHideTimeout = null;
    }, delay);
  };

  const handleSidebarPointerLeave = (event) => {
    if (!sidebar) {
      return;
    }
    const related = event.relatedTarget;
    if (!related || !sidebar.contains(related)) {
      scheduleHideSidebarControls();
    }
  };

  sidebarReveal?.addEventListener("mouseenter", showSidebarControls);
  sidebarReveal?.addEventListener("mouseleave", handleSidebarPointerLeave);
  sidebarHeader?.addEventListener("mouseenter", showSidebarControls);
  sidebar?.addEventListener("mouseenter", showSidebarControls);
  sidebar?.addEventListener("mouseleave", handleSidebarPointerLeave);

  sidebarClose?.addEventListener("focus", () => showSidebarControls());
  sidebarClose?.addEventListener("blur", () => scheduleHideSidebarControls());
  historyList?.addEventListener("focusin", () => scheduleHideSidebarControls());
};

const injectStyles = () => {
  if (document.getElementById("nori-style")) {
    return;
  }

  const style = document.createElement("link");
  style.rel = "stylesheet";
  style.href = chrome.runtime.getURL("styles.css");
  style.id = "nori-style";
  document.head.appendChild(style);
};

const openOverlay = async () => {
  injectStyles();

  const existingOverlay = document.getElementById(OVERLAY_ID);
  if (existingOverlay) {
    existingOverlay.classList.remove("fade-out");
    existingOverlay.classList.add("fade-in");
    existingOverlay.querySelector(`#${TEXTAREA_ID}`)?.focus({ preventScroll: true });
    return;
  }

  const overlay = document.createElement("div");
  overlay.id = OVERLAY_ID;
  overlay.classList.add("fade-in");
  overlay.innerHTML = `
    <div class="nori-surface">
      <aside id="${SIDEBAR_ID}" class="nori-sidebar" aria-hidden="true">
        <div class="nori-sidebar__reveal-zone" aria-hidden="true"></div>
        <header class="nori-sidebar__header">
          <h2 class="nori-sidebar__title">History</h2>
          <button type="button" class="nori-icon-btn nori-icon-btn--back" id="nori-sidebar-close" aria-label="Close history panel">${ICON_SVGS.back}</button>
        </header>
        <div class="nori-sidebar__list" id="${HISTORY_LIST_ID}"></div>
      </aside>
      <div class="nori-main">
        <div class="nori-control-zone nori-control-zone--top" aria-hidden="true"></div>
        <header class="nori-main__header">
          <button type="button" class="nori-icon-btn" id="${HISTORY_TOGGLE_ID}" aria-label="Toggle history sidebar" aria-controls="${SIDEBAR_ID}" aria-expanded="false">${ICON_SVGS.history}</button>
          <span class="nori-brand" aria-hidden="true">Nori</span>
          <button type="button" class="nori-icon-btn" id="${CLOSE_BUTTON_ID}" aria-label="Close Nori overlay">✕</button>
        </header>
        <textarea id="${TEXTAREA_ID}" placeholder="write your thoughts..."></textarea>
        <footer class="nori-main__footer">
          <button type="button" id="${EXPORT_BUTTON_ID}" class="nori-export-btn" aria-label="Export history as Markdown">${ICON_SVGS.export}</button>
        </footer>
        <div class="nori-control-zone nori-control-zone--bottom" aria-hidden="true"></div>
      </div>
    </div>
    <div id="${TOAST_ID}" class="nori-toast" role="status" aria-live="polite"></div>
  `;

  document.body.appendChild(overlay);
  currentOverlay = overlay;
  resetCurrentNoteContext();

  const stored = await storageGet([STORAGE_KEY, HISTORY_KEY]);
  const initialValue = stored[STORAGE_KEY] || "";
  const loadedHistory = Array.isArray(stored[HISTORY_KEY])
    ? stored[HISTORY_KEY]
    : [];

  historyState = loadedHistory;
  renderHistoryList();

  const textarea = overlay.querySelector(`#${TEXTAREA_ID}`);
  if (textarea) {
    textarea.value = initialValue;
    textarea.focus({ preventScroll: true });
  }

  attachOverlayEvents();
  document.addEventListener("keydown", handleKeydown);
};

chrome.runtime.onMessage.addListener((message) => {
  if (message.action !== "toggleOverlay") {
    return false;
  }

  const overlay = document.getElementById(OVERLAY_ID);
  if (overlay) {
    void closeOverlay();
  } else {
    void openOverlay();
  }

  return false;
});
