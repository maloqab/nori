# 🌿 Nori — Notes that Flow with You

Nori is a minimalist Chrome extension that lets you jot notes on top of any page without breaking focus. Press Option + W (Mac) or Alt + W (Windows/Linux) to summon a translucent, glassmorphic notepad overlay that remembers what you write.

## ✨ Features
- Toggle the overlay from anywhere with a single shortcut (`Option + W` / `Alt + W`)
- Glassmorphic UI with blur, soft borders, and subtle fade animations
- Auto-save notes with Chrome Sync so your thoughts follow you
- Sidebar history keeps your latest 50 notes per Chrome profile, complete with lock, delete, and quick-load controls
- Export everything to Markdown (bottom-right) before pruning or to keep a backup

## 🚀 Installation (Load Unpacked)
1. Clone or download this repository to your machine.
2. Open Chrome and visit `chrome://extensions`.
3. Enable **Developer mode** (toggle in the top-right corner).
4. Click **Load unpacked** and select the `nori` folder.
5. The extension is now ready—press the shortcut to start writing.

## 🎹 Usage
- Toggle the notepad with `Option + W` (Mac) or `Alt + W` (Windows/Linux).
- Type freely—the note auto-saves with Chrome Sync and closing the overlay snapshots it into history.
- Tap the top-left history icon to open the sidebar, load previous notes, lock favourites, or delete old ones. Locked notes survive the rolling 50-note limit.
- Use the **Export Markdown** button in the footer to download all saved notes at once.
- Click the ✕ button or press `Esc` to close the overlay; the next toggle restores your latest text.

## 🔮 Future Ideas
- AI-powered summaries of your notes
- Drag to reposition and resize the overlay
- Cross-device cloud sync integrations

## 🛠 Tech Stack
- Manifest V3
- Vanilla JavaScript content + background scripts
- Chrome Storage Sync API
- CSS glassmorphism with JetBrains Mono

## 📄 License
This project is licensed under the [MIT License](LICENSE).
