const OVERLAY_ID = "nori-overlay";
const TEXTAREA_ID = "nori-textarea";
const CLOSE_BUTTON_ID = "nori-close";
const STORAGE_KEY = "nori_note";
const HISTORY_KEY = "nori_notes";
const HISTORY_LIMIT = 50;
const ANIMATION_DURATION_MS = 320;

const HISTORY_TOGGLE_ID = "nori-history-toggle";
const SIDEBAR_ID = "nori-sidebar";
const HISTORY_LIST_ID = "nori-history-list";
const EXPORT_BUTTON_ID = "nori-export";
const NEW_NOTE_BUTTON_ID = "nori-new-note";
const MAIN_NEW_NOTE_BUTTON_ID = "nori-main-new-note";
const SEARCH_BUTTON_ID = "nori-search";
const SEARCH_INPUT_ID = "nori-search-input";
const TOAST_ID = "nori-toast";
const SIDEBAR_OPEN_CLASS = "sidebar-open";
const EDITOR_LINKS_ID = "nori-editor-links";

const HISTORY_LINK_LIMIT = 4;
const EDITOR_LINK_LIMIT = 6;
const LINK_LABEL_MAX_LENGTH = 42;
const URL_PATTERN =
  /\b((?:https?:\/\/|www\.)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:\/[^\s]*)?)/gi;
const TRAILING_PUNCTUATION_PATTERN = /[),.;!?"'\]]+$/;
const PROTOCOL_PATTERN = /^https?:\/\//i;

const ICON_SVGS = {
  history: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg>`,
  lock: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="1.5"/><path d="M9 11V8a3 3 0 0 1 6 0v3"/></svg>`,
  unlock: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="1.5"/><path d="M9 11V8a3 3 0 0 1 5.5-1.5"/></svg>`,
  delete: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 7h14"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M8 7l1-3h6l1 3"/><path d="M6 7l.5 13h11L18 7"/></svg>`,
  export: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v11"/><path d="M8 9l4-4 4 4"/><path d="M5 16v1.5A1.5 1.5 0 0 0 6.5 19h11a1.5 1.5 0 0 0 1.5-1.5V16"/></svg>`,
  plus: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14"/><path d="M5 12h14"/></svg>`,
  search: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="5"/><path d="M16 16l4 4"/></svg>`,
  back: `<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9.6 6v12" stroke-width="1.5"/><path d="M18 12h-6.1" stroke-width="1.4"/><path d="M15 8.5 11.9 12l3.1 3.5" stroke-width="1.7"/></svg>`,
};

const HISTORY_PREVIEW_DEBOUNCE_MS = 400;
const SYNC_WARNING_INTERVAL_MS = 2400;

const createStorageArea = (areaName) => {
  const area = chrome?.storage?.[areaName];
  const unavailableResult = {
    ok: false,
    error: `${areaName} storage unavailable`,
  };

  return {
    get: (keys) =>
      new Promise((resolve) => {
        if (!area) {
          resolve({});
          return;
        }
        area.get(keys, (result) => {
          if (chrome.runtime.lastError) {
            console.warn(
              `[nori] ${areaName} storage get failed:`,
              chrome.runtime.lastError.message
            );
            resolve({});
            return;
          }
          resolve(result || {});
        });
      }),
    set: (items) =>
      new Promise((resolve) => {
        if (!area) {
          resolve(unavailableResult);
          return;
        }
        area.set(items, () => {
          if (chrome.runtime.lastError) {
            resolve({
              ok: false,
              error: chrome.runtime.lastError.message || "Unknown storage error",
            });
            return;
          }
          resolve({ ok: true });
        });
      }),
    remove: (keys) =>
      new Promise((resolve) => {
        if (!area) {
          resolve(unavailableResult);
          return;
        }
        area.remove(keys, () => {
          if (chrome.runtime.lastError) {
            resolve({
              ok: false,
              error: chrome.runtime.lastError.message || "Unknown storage error",
            });
            return;
          }
          resolve({ ok: true });
        });
      }),
  };
};

const storage = {
  sync: createStorageArea("sync"),
  local: createStorageArea("local"),
};

let lastSyncWarningAt = 0;

let historyState = [];
let currentOverlay = null;
let currentNoteId = null;
let historyFilter = "";
let historyLoadSequence = 0;
let historyUpdateTimeout = null;

const notifySyncIssue = (errorMessage) => {
  const now = Date.now();
  console.warn("[nori] Chrome Sync save failed:", errorMessage);
  if (now - lastSyncWarningAt < SYNC_WARNING_INTERVAL_MS) {
    return;
  }
  lastSyncWarningAt = now;
  showToast("Saved locally; Chrome Sync quota hit.");
};

const handleHistoryPersistResult = (result) => {
  if (!result?.ok) {
    notifySyncIssue(result?.error);
  }
};

const clearPendingHistoryUpdate = () => {
  if (historyUpdateTimeout) {
    window.clearTimeout(historyUpdateTimeout);
    historyUpdateTimeout = null;
  }
};

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

const normalizeUrl = (url) => {
  if (!url || typeof url !== "string") {
    return "";
  }
  const trimmed = url.trim();
  if (!trimmed) {
    return "";
  }
  return PROTOCOL_PATTERN.test(trimmed) ? trimmed : `https://${trimmed}`;
};

const extractUrls = (text = "") => {
  if (!text || typeof text !== "string") {
    return [];
  }

  const matches = text.match(URL_PATTERN);
  if (!matches) {
    return [];
  }

  const seen = new Set();
  return matches
    .map((raw) =>
      normalizeUrl(raw.replace(TRAILING_PUNCTUATION_PATTERN, ""))
    )
    .filter((url) => {
      if (!url || seen.has(url)) {
        return false;
      }
      seen.add(url);
      return true;
    });
};

const formatLinkLabel = (url) => {
  const normalized = normalizeUrl(url);
  const truncate = (value) =>
    value.length > LINK_LABEL_MAX_LENGTH
      ? `${value.slice(0, LINK_LABEL_MAX_LENGTH - 1)}…`
      : value;

  try {
    const parsed = new URL(normalized);
    const host = parsed.hostname.replace(/^www\./i, "");
    const path = parsed.pathname && parsed.pathname !== "/" ? parsed.pathname : "";
    return truncate(`${host}${path}`);
  } catch {
    const fallback = normalized.replace(PROTOCOL_PATTERN, "");
    return truncate(fallback);
  }
};

const createLinkChip = (url) => {
  const normalized = normalizeUrl(url);
  if (!normalized) {
    return null;
  }
  const anchor = document.createElement("a");
  anchor.href = normalized;
  anchor.target = "_blank";
  anchor.rel = "noopener noreferrer";
  anchor.className = "nori-link-chip";
  anchor.textContent = formatLinkLabel(normalized);
  anchor.title = normalized;
  anchor.addEventListener("click", (event) => {
    event.stopPropagation();
  });
  return anchor;
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

  const source = historyFilter
    ? historyState.filter((note) => {
        const content = note.content?.toLowerCase() || "";
        const timestampLabel = formatTimestamp(note.updatedAt || note.createdAt)
          .toLowerCase();
        return (
          content.includes(historyFilter) ||
          timestampLabel.includes(historyFilter)
        );
      })
    : historyState;

  if (!source.length) {
    const empty = document.createElement("p");
    empty.className = "nori-history-empty";
    empty.textContent = historyFilter
      ? "No notes match your search."
      : "Your saved notes will collect here once you close the overlay.";
    container.appendChild(empty);
    return;
  }

  source.forEach((note) => {
    const item = document.createElement("article");
    item.className = "nori-history-item";
    item.dataset.noteId = note.id;
    item.dataset.action = "load-note";
    item.tabIndex = 0;
    item.setAttribute("role", "button");

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

    const body = document.createElement("div");
    body.className = "nori-history-body";
    body.textContent = note.content.trim() || "write your thoughts...";

    item.append(meta, body);

    const urls = extractUrls(note.content || "");
    if (urls.length) {
      const linkList = document.createElement("div");
      linkList.className = "nori-history-links";
      urls.slice(0, HISTORY_LINK_LIMIT).forEach((url) => {
        const chip = createLinkChip(url);
        if (chip) {
          linkList.appendChild(chip);
        }
      });
      item.appendChild(linkList);
    }
    container.appendChild(item);
  });
};

const renderEditorLinks = (value = "") => {
  if (!currentOverlay) {
    return;
  }
  const container = currentOverlay.querySelector(`#${EDITOR_LINKS_ID}`);
  if (!container) {
    return;
  }
  container.textContent = "";
  const urls = extractUrls(value).slice(0, EDITOR_LINK_LIMIT);
  if (!urls.length) {
    container.classList.add("nori-editor-links--empty");
    return;
  }
  container.classList.remove("nori-editor-links--empty");
  urls.forEach((url) => {
    const chip = createLinkChip(url);
    if (chip) {
      container.appendChild(chip);
    }
  });
};

const ensureDraftHistoryEntry = (value) => {
  if (currentNoteId) {
    return;
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return;
  }
  const timestamp = new Date().toISOString();
  const draftNote = {
    id: generateNoteId(),
    content: value,
    createdAt: timestamp,
    updatedAt: timestamp,
    locked: false,
    isDraft: true,
  };
  historyState = [draftNote, ...historyState];
  currentNoteId = draftNote.id;
  renderHistoryList();
};

const removeDraftHistoryEntry = () => {
  if (!currentNoteId) {
    return;
  }
  const noteIndex = historyState.findIndex((note) => note.id === currentNoteId);
  if (noteIndex === -1) {
    return;
  }
  const target = historyState[noteIndex];
  if (!target?.isDraft) {
    return;
  }
  const updatedHistory = [...historyState];
  updatedHistory.splice(noteIndex, 1);
  historyState = updatedHistory;
  resetCurrentNoteContext();
  renderHistoryList();
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
    sidebar.classList.remove("search-active");
    const searchInput = currentOverlay.querySelector(`#${SEARCH_INPUT_ID}`);
    if (searchInput) {
      searchInput.value = "";
    }
    historyFilter = "";
    renderHistoryList();
    const editorWrapper = currentOverlay.querySelector(".nori-main");
    if (editorWrapper && !editorWrapper.dataset.pendingReveal) {
      editorWrapper.classList.remove("nori-editor-hidden");
    }
    toggle?.setAttribute("aria-expanded", "false");
  }
};

const resetCurrentNoteContext = () => {
  currentNoteId = null;
};

const persistCurrentValue = async (value) => {
  const result = await storage.local.set({ [STORAGE_KEY]: value });
  if (!result.ok) {
    console.warn("[nori] Failed to persist working note:", result.error);
  }
};

const persistHistory = async () => {
  const payload = { [HISTORY_KEY]: historyState };
  const localResult = await storage.local.set(payload);
  if (!localResult.ok) {
    console.warn("[nori] Failed to persist history locally:", localResult.error);
  }
  return storage.sync.set(payload);
};

const updateCurrentNoteInHistory = (rawValue) => {
  if (!currentNoteId) {
    return;
  }

  const noteIndex = historyState.findIndex((note) => note.id === currentNoteId);
  if (noteIndex === -1) {
    return;
  }

  const timestamp = new Date().toISOString();
  const updatedNote = {
    ...historyState[noteIndex],
    content: rawValue,
    updatedAt: timestamp,
  };

  historyState = [...historyState];
  historyState[noteIndex] = updatedNote;

  renderHistoryList();
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
        const historyResult = await persistHistory();
        handleHistoryPersistResult(historyResult);
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
        isDraft: false,
      };

      const reordered = [...historyState];
      reordered.splice(existingIndex, 1);
      reordered.unshift(updatedNote);

      historyState = reordered;
      await persistCurrentValue(rawValue);
      const historyResult = await persistHistory();
      handleHistoryPersistResult(historyResult);
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
    isDraft: false,
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
  const historyResult = await persistHistory();
  handleHistoryPersistResult(historyResult);
  renderHistoryList();
  showToast("Saved to history.");
  return true;
};

const closeOverlay = async () => {
  const overlay = document.getElementById(OVERLAY_ID);
  if (!overlay || overlay.dataset.closing === "true") {
    return;
  }

  clearPendingHistoryUpdate();

  const textarea = overlay.querySelector(`#${TEXTAREA_ID}`);
  const noteValue = textarea ? textarea.value : "";
  const canClose = await handleNoteFinalization(noteValue);

  if (!canClose) {
    textarea?.focus({ preventScroll: true });
    return;
  }

  overlay.dataset.closing = "true";
  resetCurrentNoteContext();
  historyFilter = "";
  historyLoadSequence += 1;
  const editorWrapper = overlay.querySelector(".nori-main");
  editorWrapper?.classList.remove("nori-note-flash");
  editorWrapper?.classList.remove("nori-editor-hidden");
  editorWrapper?.removeAttribute("data-pending-reveal");

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
    clearPendingHistoryUpdate();
    if (!textarea) {
      return;
    }

    const shouldFinalizeCurrent = noteId !== currentNoteId;
    if (shouldFinalizeCurrent) {
      const saved = await handleNoteFinalization(textarea.value);
      if (!saved) {
        textarea.focus({ preventScroll: true });
        return;
      }
      renderHistoryList();
    }

    const refreshedIndex = historyState.findIndex((note) => note.id === noteId);
    if (refreshedIndex === -1) {
      return;
    }
    const targetNote = historyState[refreshedIndex];

    const editorWrapper = currentOverlay?.querySelector(".nori-main");
    editorWrapper?.classList.remove("nori-note-flash");

    const sequence = ++historyLoadSequence;

    const applyLoadedNote = async () => {
      if (sequence !== historyLoadSequence) {
        return;
      }
      textarea.value = targetNote.content;
      textarea.focus({ preventScroll: true });
      currentNoteId = targetNote.id;
      await persistCurrentValue(targetNote.content);
      renderEditorLinks(targetNote.content);
      renderHistoryList();
      showToast("Loaded note into editor.");
      if (editorWrapper) {
        editorWrapper.classList.remove("nori-editor-hidden");
        editorWrapper.removeAttribute("data-pending-reveal");
      }
    };

    const sidebarElement = currentOverlay?.querySelector(`#${SIDEBAR_ID}`);
    const wasOpen = currentOverlay?.classList.contains(SIDEBAR_OPEN_CLASS);

    const waitForSidebarClose = () =>
      new Promise((resolve) => {
        if (!wasOpen || !sidebarElement) {
          resolve();
          return;
        }

        const cleanup = () => {
          sidebarElement.removeEventListener("transitionend", handler);
          resolve();
        };

        const handler = (event) => {
          if (event.target === sidebarElement && event.propertyName === "transform") {
            cleanup();
          }
        };

        sidebarElement.addEventListener("transitionend", handler);
        window.setTimeout(cleanup, ANIMATION_DURATION_MS);
      });

    if (editorWrapper) {
      if (wasOpen) {
        editorWrapper.dataset.pendingReveal = "true";
        editorWrapper.classList.add("nori-editor-hidden");
      } else {
        editorWrapper.classList.remove("nori-editor-hidden");
        editorWrapper.removeAttribute("data-pending-reveal");
      }
    }

    setSidebarState(false);

    await waitForSidebarClose();
    await applyLoadedNote();
    return;
  }

  if (action === "toggle-lock") {
    const note = historyState[noteIndex];
    const updated = { ...note, locked: !note.locked, updatedAt: note.updatedAt };
    const newHistory = [...historyState];
    newHistory.splice(noteIndex, 1, updated);
    historyState = newHistory;
    const historyResult = await persistHistory();
    handleHistoryPersistResult(historyResult);
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
    const historyResult = await persistHistory();
    handleHistoryPersistResult(historyResult);
    renderHistoryList();
    showToast("Note deleted.");
  }
};

const startNewNote = async () => {
  if (!currentOverlay) {
    return;
  }

  clearPendingHistoryUpdate();

  const textarea = currentOverlay.querySelector(`#${TEXTAREA_ID}`);
  if (!textarea) {
    return;
  }

  const trimmedValue = textarea.value.trim();
  if (!trimmedValue) {
    renderEditorLinks(textarea.value);
    textarea.focus({ preventScroll: true });
    showToast("You're already on a fresh note.");
    return;
  }

  historyLoadSequence += 1;

  const editorWrapper = textarea.closest(".nori-main");
  if (editorWrapper) {
    editorWrapper.classList.remove("nori-note-flash");
    editorWrapper.classList.remove("nori-editor-hidden");
    editorWrapper.removeAttribute("data-pending-reveal");
  }

  const saved = await handleNoteFinalization(textarea.value);
  if (!saved) {
    renderEditorLinks(textarea.value);
    textarea.focus({ preventScroll: true });
    return;
  }

  resetCurrentNoteContext();
  textarea.value = "";
  await persistCurrentValue("");
  renderEditorLinks("");
  textarea.focus({ preventScroll: true });
  renderHistoryList();
  showToast("Ready for a new note.");
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
  const mainNewNoteButton = currentOverlay.querySelector(`#${MAIN_NEW_NOTE_BUTTON_ID}`);
  const newNoteButton = currentOverlay.querySelector(`#${NEW_NOTE_BUTTON_ID}`);
  const searchButton = currentOverlay.querySelector(`#${SEARCH_BUTTON_ID}`);
  const searchPanel = currentOverlay.querySelector("#nori-search-panel");
  const searchInput = currentOverlay.querySelector(`#${SEARCH_INPUT_ID}`);
  const searchClearButton = currentOverlay.querySelector("#nori-search-clear");
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
    ensureDraftHistoryEntry(value);
    if (!value.trim()) {
      removeDraftHistoryEntry();
    }
    void persistCurrentValue(value);
    renderEditorLinks(value);

    // Update history UI in real-time without hammering Chrome Sync
    if (historyUpdateTimeout) {
      clearTimeout(historyUpdateTimeout);
    }
    historyUpdateTimeout = window.setTimeout(() => {
      updateCurrentNoteInHistory(value);
      historyUpdateTimeout = null;
    }, HISTORY_PREVIEW_DEBOUNCE_MS);
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

  historyList?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      void handleHistoryAction(event);
    }
  });

  exportButton?.addEventListener("click", () => {
    exportHistoryToMarkdown();
  });

  mainNewNoteButton?.addEventListener("click", () => {
    void startNewNote();
  });

  newNoteButton?.addEventListener("click", () => {
    void startNewNote();
  });

  searchButton?.addEventListener("click", () => {
    if (sidebar?.classList.contains("search-active")) {
      clearSearch({ refocusButton: true });
    } else {
      openSearchPanel();
    }
  });

  searchInput?.addEventListener("input", (event) => {
    const value = event.target.value.trim().toLowerCase();
    historyFilter = value;
    renderHistoryList();
  });

  searchInput?.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      clearSearch({ refocusButton: true });
    }
  });

  searchClearButton?.addEventListener("click", () => {
    clearSearch({ refocusButton: true });
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
  bindHoverToggle(newNoteButton, "top-hover");
  bindHoverToggle(searchButton, "top-hover");
  bindHoverToggle(searchClearButton, "top-hover");
  bindHoverToggle(closeButton, "top-hover");
  bindHoverToggle(sidebarClose, "top-hover");

  bindFocusToggle(historyToggle, "top-hover");
  bindFocusToggle(newNoteButton, "top-hover");
  bindFocusToggle(searchButton, "top-hover");
  bindFocusToggle(searchInput, "top-hover");
  bindFocusToggle(searchClearButton, "top-hover");
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
    if (sidebar.classList.contains("search-active")) {
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
      if (!sidebar.classList.contains("search-active")) {
        scheduleHideSidebarControls();
      }
    }
  };

  sidebarReveal?.addEventListener("mouseenter", showSidebarControls);
  sidebarReveal?.addEventListener("mouseleave", handleSidebarPointerLeave);
  sidebarHeader?.addEventListener("mouseenter", showSidebarControls);
  sidebar?.addEventListener("mouseenter", showSidebarControls);
  sidebar?.addEventListener("mouseleave", handleSidebarPointerLeave);

  const openSearchPanel = () => {
    if (!sidebar) {
      return;
    }
    sidebar.classList.add("search-active");
    showSidebarControls();
    requestAnimationFrame(() => {
      searchInput?.focus({ preventScroll: true });
    });
  };

  const clearSearch = ({ refocusButton = false, shouldRender = true } = {}) => {
    historyFilter = "";
    if (searchInput) {
      searchInput.value = "";
    }
    sidebar?.classList.remove("search-active");
    if (shouldRender) {
      renderHistoryList();
    }
    if (refocusButton) {
      searchButton?.focus({ preventScroll: true });
    }
    scheduleHideSidebarControls();
  };

  newNoteButton?.addEventListener("focus", () => showSidebarControls());
  newNoteButton?.addEventListener("blur", () => scheduleHideSidebarControls());
  searchButton?.addEventListener("focus", () => showSidebarControls());
  searchButton?.addEventListener("blur", () => scheduleHideSidebarControls());
  searchInput?.addEventListener("focus", () => showSidebarControls());
  searchInput?.addEventListener("blur", () => {
    if (!searchInput?.value) {
      clearSearch();
    }
    scheduleHideSidebarControls();
  });
  searchClearButton?.addEventListener("focus", () => showSidebarControls());
  searchClearButton?.addEventListener("blur", () => scheduleHideSidebarControls());
  sidebarClose?.addEventListener("focus", () => showSidebarControls());
  sidebarClose?.addEventListener("blur", () => scheduleHideSidebarControls());
  historyList?.addEventListener("focusin", () => scheduleHideSidebarControls());
};

const injectStyles = () => {
  // Always remove and re-add to avoid caching issues
  const existing = document.getElementById("nori-style");
  if (existing) {
    existing.remove();
  }

  const style = document.createElement("link");
  style.rel = "stylesheet";
  style.href = chrome.runtime.getURL("styles.css?v=" + Date.now());
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
  overlay.classList.remove("fade-out");
  overlay.classList.add("fade-in");
  overlay.innerHTML = `
    <div class="nori-surface">
      <aside id="${SIDEBAR_ID}" class="nori-sidebar" aria-hidden="true">
        <div class="nori-sidebar__reveal-zone" aria-hidden="true"></div>
        <header class="nori-sidebar__header">
          <h2 class="nori-sidebar__title">History</h2>
          <div class="nori-sidebar__actions">
            <button type="button" class="nori-icon-btn" id="${SEARCH_BUTTON_ID}" aria-label="Search notes">${ICON_SVGS.search}</button>
            <button type="button" id="${NEW_NOTE_BUTTON_ID}" class="nori-icon-btn" aria-label="Start a new note">${ICON_SVGS.plus}</button>
            <button type="button" class="nori-icon-btn nori-icon-btn--back" id="nori-sidebar-close" aria-label="Close history panel">${ICON_SVGS.back}</button>
          </div>
        </header>
        <div class="nori-sidebar__search" id="nori-search-panel">
          <input id="${SEARCH_INPUT_ID}" type="search" autocomplete="off" placeholder="Search notes" aria-label="Search notes" />
          <button type="button" class="nori-icon-btn nori-icon-btn--pill" id="nori-search-clear" aria-label="Clear search">✕</button>
        </div>
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
        <div class="nori-editor-links nori-editor-links--empty" id="${EDITOR_LINKS_ID}" aria-label="Links in current note"></div>
        <footer class="nori-main__footer">
          <div class="nori-footer-actions">
            <button type="button" id="${MAIN_NEW_NOTE_BUTTON_ID}" class="nori-icon-btn" aria-label="Start a new note">${ICON_SVGS.plus}</button>
            <button type="button" id="${EXPORT_BUTTON_ID}" class="nori-export-btn" aria-label="Export history as Markdown">${ICON_SVGS.export}</button>
          </div>
        </footer>
        <div class="nori-control-zone nori-control-zone--bottom" aria-hidden="true"></div>
      </div>
    </div>
    <div id="${TOAST_ID}" class="nori-toast" role="status" aria-live="polite"></div>
  `;

  document.body.appendChild(overlay);
  currentOverlay = overlay;
  resetCurrentNoteContext();

  const [syncStored, localStored] = await Promise.all([
    storage.sync.get([STORAGE_KEY, HISTORY_KEY]),
    storage.local.get([STORAGE_KEY, HISTORY_KEY]),
  ]);

  const hasLocalValue = Object.prototype.hasOwnProperty.call(
    localStored,
    STORAGE_KEY
  );
  const hasSyncValue = Object.prototype.hasOwnProperty.call(
    syncStored,
    STORAGE_KEY
  );

  const initialValue = hasLocalValue
    ? localStored[STORAGE_KEY] || ""
    : hasSyncValue
    ? syncStored[STORAGE_KEY] || ""
    : "";

  await persistCurrentValue(initialValue);

  const historyFromSync = Array.isArray(syncStored[HISTORY_KEY])
    ? syncStored[HISTORY_KEY]
    : null;
  const historyFromLocal = Array.isArray(localStored[HISTORY_KEY])
    ? localStored[HISTORY_KEY]
    : [];

  historyState = [...(historyFromSync ?? historyFromLocal ?? [])];
  void storage.local.set({ [HISTORY_KEY]: historyState });

  historyFilter = "";
  historyLoadSequence = 0;
  renderHistoryList();

  const textarea = overlay.querySelector(`#${TEXTAREA_ID}`);
  if (textarea) {
    textarea.value = initialValue;
    renderEditorLinks(initialValue);
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
