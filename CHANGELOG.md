# Changelog

All notable changes to this project will be documented in this file.

## [Version 2.1]

### Added
- **Drag and Drop Video Import**: Seamlessly drag and drop video files (`.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`, `.ts`) directly from your folders into the Kut editor window. Videos are automatically imported into the left panel's media bin without needing to go through the traditional file dialog.
- Removed external `windnd` dependency and implemented a robust, native 64-bit safe `ctypes` wrapper to handle Windows file drop events flawlessly without crashing.
- **Improved Frames Export Naming**: Exported frames are now sequentially named using the original video's filename (e.g., `Sequence_001.jpg`, `Sequence_002.jpg`).
- **Export Notification**: Added a green "Export Completed" confirmation message that briefly appears upon successful export.

### Fixed
- **Unsaved Changes Prompt**: The "Export before closing?" prompt now properly only appears when actual edits (splits, cuts, etc.) have been made to the video, instead of incorrectly triggering simply when a video is loaded from the media bin.
