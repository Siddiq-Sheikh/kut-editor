# Changelog

All notable changes to this project will be documented in this file.

## [Version 3.0]

### Added
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
