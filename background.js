chrome.commands.onCommand.addListener((command) => {
  if (command !== "toggle_nori") {
    return;
  }

  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const [activeTab] = tabs;
    if (!activeTab?.id) {
      return;
    }

    chrome.tabs.sendMessage(activeTab.id, { action: "toggleOverlay" });
  });
});
