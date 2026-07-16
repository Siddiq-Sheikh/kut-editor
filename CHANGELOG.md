# Changelog

All notable changes to this project will be documented in this file.

## [Version 4.0]

### Added
- **Unified Export Dialog**: Overhauled the export flow into a single, comprehensive dialog for choosing formats (Video or Image Sequence), selecting output destinations (with context-aware file vs folder selection), and configuring frame extraction settings all in one place.
- **Background Export Processing**: Exports are now queued and processed in a non-blocking background thread. You can continue editing your timeline seamlessly while multiple exports run in the background.
- **Enhanced Downloads Panel**: Redesigned the downloads panel with a sleek circular progress loader for active exports, a built-in 'X' cancel button to abort ongoing jobs, and mouse-wheel scrolling (showing 2 items at a time).
- **Interval Extraction Mode**: Added a new "Interval (s)" mode when exporting frames, allowing you to easily extract 1 frame every X seconds, complete with a real-time calculator that shows exactly how many frames will be generated before you start.
- **Footer UI Updates**: The Downloads button in the footer now features a dynamic circular loader ring when an export is actively running.

## [Version 3.0]
- **Project Save & Load**: You can now save your full workspace (cuts, crops, edits, clips) as a `.kut` project file using the new "Save" and "Open" toolbar buttons or via `Ctrl+S` / `Ctrl+O`.
- **Intelligent Auto-Save**: A background thread auto-saves your active project every 60 seconds without freezing the UI or interrupting playback.
- **Crash Recovery**: The editor automatically detects if you crashed with unsaved work from a previous session and prompts you to recover it upon startup.
- **Precision Timeline Calculation**: Kut now strictly probes video files using `ffprobe` to determine highly accurate frame counts and millisecond durations, preventing OpenCV's known VFR (Variable Frame Rate) truncation bugs.
- **Enhanced Toolbar UI**: Reorganized the top toolbar into separated **VIDEO** (Import/Export) and **PROJECT** (Open/Save) categories with floating labels for better clarity.

### Fixed
- **OpenCV Screenshot Bug**: Disabled default OpenCV GUI hotkeys so that `Ctrl+S` correctly saves your project instead of capturing an empty `.jpg` screenshot.
- **Left Panel Thumbnail Bug**: Fixed an issue where the left panel media bin wouldn't populate with thumbnails after a project state was loaded.

## [Version 2.1]

### Added
- **Drag and Drop Video Import**: Seamlessly drag and drop video files (`.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`, `.ts`) directly from your folders into the Kut editor window. Videos are automatically imported into the left panel's media bin without needing to go through the traditional file dialog.
- Removed external `windnd` dependency and implemented a robust, native 64-bit safe `ctypes` wrapper to handle Windows file drop events flawlessly without crashing.
- **Improved Frames Export Naming**: Exported frames are now sequentially named using the original video's filename (e.g., `Sequence_001.jpg`, `Sequence_002.jpg`).
- **Export Notification**: Added a green "Export Completed" confirmation message that briefly appears upon successful export.

### Fixed
- **Unsaved Changes Prompt**: The "Export before closing?" prompt now properly only appears when actual edits (splits, cuts, etc.) have been made to the video, instead of incorrectly triggering simply when a video is loaded from the media bin.
