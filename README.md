# Kut Video Editor

A lightweight, OpenCV-based static video editor that handles clip editing, timecodes, and playback.

## Structure
- `src/kut/` - The main Python package.
- `assets/` - Static files like icons.
- `build.py` - Script to generate the executable using PyInstaller.

## Running from source
1. Install requirements:
   ```cmd
   pip install -r requirements.txt
   ```
2. Run the editor:
   ```cmd
   python -m kut
   ```

## Building Executable
Run the `build.py` script:
```cmd
python build.py
```
The resulting executable will be in the `dist/` folder.
