# 🎬 Kut Video Editor - Features & Functionalities

Kut is a lightweight, OpenCV-based video editor tailored for speed, simplicity, and ease of use. Below is a comprehensive list of all functionalities available in the editor.

## 📂 1. Media Management
* **Drag and Drop Import:** Seamlessly drag and drop video files (`.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`, `.ts`) directly into the app window to import them.
* **Media Bin (Left Panel):** A dedicated area that stores and displays thumbnails of all imported video assets for your current project.
* **Recent Projects:** Kut automatically tracks and saves your recent projects so you can easily pick up where you left off.
* **Double-Click to Load:** Instantly start a new timeline session by double-clicking any video in the media bin.

## ✂️ 2. Core Video Editing
* **Timeline Editing:** A visual, bottom-anchored timeline that displays all your clips in sequence.
* **Split Clips:** Quickly cut clips at the current playhead by pressing `C` or clicking the scissors icon. 
* **Delete Clips:** Remove unwanted segments by selecting a clip and hitting `Del` or `Backspace`.
* **Reorder Clips:** Click and drag any clip in the timeline to reorder your sequence effortlessly.
* **Undo & Redo:** Full history tracking allows you to revert edits using `Ctrl+Z` and re-apply them with `Ctrl+Y`.

## 🎨 3. Advanced Tools
* **Visual Cropping:** Activate crop mode to visually drag and adjust the framing of your clips directly on the canvas preview.
* **Blur Tool (Paint):** Protect privacy or hide elements by painting a blur directly onto the video. You can adjust the brush size and apply the blur globally across a track or just to a specific clip.

## ⏯️ 4. Playback & Navigation
* **Real-time Preview:** High-performance, real-time video playback using OpenCV.
* **Timeline Scrubbing:** Click and drag across the timeline or use your mouse wheel to quickly seek through your footage.
* **Precision Timecodes & Container Parsing:** View your exact frame/time position. Kut uses strict `ffprobe` container parsing for flawless frame accuracy, bypassing common Variable Frame Rate (VFR) truncation bugs. Click the timecode display to manually type and jump to a specific time.
* **Zoomable Timeline:** Zoom in for precise frame-by-frame cuts, or zoom out to see your entire project.

## 💾 5. Exporting & Saving
* **Project Save & Load:** Save your complete workspace (timeline cuts, edits, and crop/blur states) to a `.kut` project file using `Ctrl+S`. Load existing projects using `Ctrl+O` or the top toolbar.
* **Intelligent Auto-Save:** Automatically saves your work in the background every 60 seconds without freezing the UI or interrupting playback.
* **Crash Recovery:** Instantly detects if the application previously closed with unsaved edits and prompts you to recover your exact session upon startup.
* **Smart Exporter:** Export your final composed sequence as a standard `.mp4` video file using the dedicated Video Export button.
* **Unsaved Changes Protection:** Prevents accidental data loss by prompting you to save your project before opening a new one or closing the application.

---

### ⌨️ Default Keyboard Shortcuts
| Shortcut | Action |
| --- | --- |
| `Space` | Play / Pause |
| `C` | Split clip at current playhead |
| `Del` / `Backspace` | Delete selected clip |
| `Ctrl + S` | Save current project |
| `Ctrl + O` | Open a `.kut` project |
| `Ctrl + Z` | Undo last action |
| `Ctrl + Y` | Redo last action |
| `Mouse Wheel` | Scroll timeline / Zoom (with modifiers) |
| `Middle Mouse Drag` | Pan across the timeline |
