import os
import sys
import ctypes
import threading
import itertools
import bisect
from collections import OrderedDict
import time
import json
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import cv2
import numpy as np
import queue
import subprocess

from .config import Theme, resource_path, get_data_dir
from .ui import UI
from .media import VideoSource, Clip, _clip_id_counter, _clip_color_counter

# MAIN EDITOR
# ---------------------------------------------------------------------------
class Kut:
    # ---- layout constants (pixels) ----
    TOOLBAR_H    = 52          # taller toolbar
    LEFT_W       = 220         # wider media browser for thumbnails
    RIGHT_W      = 210
    TIMELINE_H   = 168
    FOOTER_H     = 26
    THUMB_SIZE   = 64
    THUMB_CACHE_MAX = 5000

    def __init__(self, video_path=None):
        self.win_name = "Kut"

        # Canvas size derived from screen (we request fullscreen later)
        self.canvas_w  = 1440
        self.canvas_h  = 900
        try:
            # Fallback size based on screen
            self.canvas_w = self._tk_root.winfo_screenwidth()
            self.canvas_h = self._tk_root.winfo_screenheight() - 80
        except Exception:
            pass

        # Derived layout
        self._recalc_layout()

        self.master_w, self.master_h, self.master_fps = 1920, 1080, 30.0  # default values for UI
        self.current_video_path = None
        self.is_dirty = False
        self._is_demo = False

        self.clips     = []
        self._sources  = []
        self.current_idx = 0
        self.clipboard = None
        self.is_playing = False
        self.status_msg = ""
        self._undo_stack, self._redo_stack = [], []

        # Clip index cache
        self._total_frames_cache = None
        self._clip_offsets       = None

        # Viewport
        self._viewport_idx = None
        self._viewport_img = None
        self._viewport_zoom = 1.0
        self._viewport_pan_x = 0
        self._viewport_pan_y = 0
        self._is_dragging_vp = False
        self._drag_vp_start_x = 0
        self._drag_vp_start_y = 0
        self._drag_vp_pan_start_x = 0
        self._drag_vp_pan_start_y = 0
        
        self._crop_mode = False
        self._is_dragging_crop = False
        self._drag_crop_idx = -1
        self._drag_crop_start_x = 0
        self._drag_crop_start_y = 0
        self._drag_crop_start_crop = None
        
        self._blur_mode = False
        self._blur_scope = "track"
        self._blur_brush_size = 40
        self._is_painting_blur = False
        self.global_blur_strokes = []
        self._mouse_x = 0
        self._mouse_y = 0
        
        # Drag and drop from left panel
        self._is_dragging_file = False
        self._drag_file_dict = None
        
        # In-place timecode edit
        self._edit_timecode_mode = False
        self._edit_timecode_str = ""

        # Timeline zoom/scroll
        self._tl_zoom   = 1.0   # pixels per frame  (base = canvas_w / total_frames)
        self._tl_scroll = 0     # left pixel offset into virtual timeline

        # Mouse state
        self._hover_id            = None
        self._hover_clip_idx      = None   # clip idx hovered in right panel
        self._is_dragging_tl      = False  # scrub drag
        self._is_dragging_mmb     = False  # middle-button pan
        self._drag_start_x        = 0
        self._drag_scroll_start   = 0
        self._drag_reorder_idx    = None   # clip being dragged for reorder
        self._drag_reorder_ghost  = None   # insertion index
        self._scissors_x          = None   # screen X of scissor hover

        # Timeline cache
        self._tl_cache       = None
        self._tl_dirty       = True

        # Thumbnail caching
        self._thumb_cache = OrderedDict()          # (source_key, frame_idx) -> numpy array (THUMB_SIZE, THUMB_SIZE, 3)
        self._thumb_pending = set()                # set of (source_key, frame_idx) currently being generated
        self._thumb_queue = queue.Queue(maxsize=1024)
        self._thumb_cache_lock = threading.Lock()
        self._worker_active = True
        self._worker_thread = threading.Thread(target=self._thumbnail_worker, daemon=True)
        self._worker_thread.start()

        # File browser thumbnails (left panel)
        self._file_thumbs   = {}   # path -> small image
        self._imported_files = []  # list of dicts {path, label, source}

        # Shortcut overlay
        self._show_help = False

        # Recent files
        self.recent_files = []
        self.recent_file_path = os.path.join(get_data_dir(), "kut_recent.json")
        self._load_recent_files()

        # Tk for dialogs
        self._tk_root = tk.Tk()
        self._tk_root.withdraw()
        # --- ADD THIS TO SET TKINTER ICON ---
        try:
            icon_file = resource_path(r"assets\kut.ico")
            self._tk_root.iconbitmap(icon_file)
        except Exception:
            pass

        cv2.namedWindow(self.win_name, cv2.WINDOW_NORMAL)
        
        # --- WINDOWS ICON & TASKBAR INTEGRATION ---
        if os.name == 'nt':
            try:
                import time # Ensure time is imported
                
                # 1. Force Windows to treat this as an independent app
                myappid = 'kut.production.engine.9' 
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

                # 2. Render a dummy frame and WAIT slightly longer
                cv2.imshow(self.win_name, np.zeros((10, 10, 3), dtype=np.uint8))
                cv2.waitKey(50)  # Increased wait time
                time.sleep(0.1)  # Give Windows UI thread a fraction of a second

                # 3. Find the window handle and set the icon
                hwnd = ctypes.windll.user32.FindWindowW(None, self.win_name)
                if hwnd:
                    icon_path = resource_path(r"assets\kut.ico")
                    # LoadImageW (LR_LOADFROMFILE = 0x00000010, IMAGE_ICON = 1)
                    hicon = ctypes.windll.user32.LoadImageW(0, icon_path, 1, 0, 0, 0x00000010)
                    if hicon:
                        ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon) # Small icon
                        ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon) # Big icon
                    
                    # Maximize window
                    ctypes.windll.user32.ShowWindow(hwnd, 3) # SW_MAXIMIZE
            except Exception:
                pass
        # -----------------------------------------------
            
        try:
            cv2.setWindowProperty(self.win_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
        except Exception:
            pass
        cv2.resizeWindow(self.win_name, self.canvas_w, self.canvas_h)
        cv2.setMouseCallback(self.win_name, self._mouse_cb)

        if video_path and os.path.exists(video_path):
            self._open_video_from_path(video_path)
        else:
            # Empty state – no demo
            pass

    # ------------------------------------------------------------------
    # Recent files management
    # ------------------------------------------------------------------
    def _load_recent_files(self):
        try:
            with open(self.recent_file_path, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    self.recent_files = [p for p in data if os.path.exists(p)]
        except Exception:
            self.recent_files = []

    def _save_recent_files(self):
        try:
            with open(self.recent_file_path, 'w') as f:
                json.dump(self.recent_files[:10], f)
        except Exception:
            pass

    def _add_recent_file(self, path):
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        if len(self.recent_files) > 10:
            self.recent_files = self.recent_files[:10]
        self._save_recent_files()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _recalc_layout(self):
        cw, ch = self.canvas_w, self.canvas_h
        lw  = self.LEFT_W
        rw  = self.RIGHT_W
        th  = self.TOOLBAR_H
        tlh = self.TIMELINE_H
        fh  = self.FOOTER_H
        vid_h = ch - th - tlh - fh
        self.layout = {
            "toolbar":   (0,  0,       cw,      th),
            "left":      (0,  th,      lw,      ch-fh),
            "viewport":  (lw, th,      cw-rw,   th+vid_h),
            "right":     (cw-rw, th,   cw,      ch-fh),
            "timeline":  (lw, th+vid_h, cw-rw,  th+vid_h+tlh),
            "footer":    (0,  ch-fh,   cw,      ch),
            "vid_h":     vid_h,
            "vid_w":     cw-lw-rw,
        }

    # ------------------------------------------------------------------
    # Clip index
    # ------------------------------------------------------------------
    def _invalidate_clip_index(self):
        self._total_frames_cache = None
        self._clip_offsets       = None

    def _rebuild_clip_index(self):
        offsets, cursor = [], 0
        for c in self.clips:
            offsets.append(cursor); cursor += len(c)
        self._clip_offsets        = offsets
        self._total_frames_cache  = cursor

    def get_total_frames(self):
        if self._total_frames_cache is None: self._rebuild_clip_index()
        return self._total_frames_cache

    def get_clip_at_playhead(self):
        total = self.get_total_frames()
        if total == 0 or not self.clips: return None, None, 0
        self.current_idx = min(self.current_idx, total-1)
        idx = bisect.bisect_right(self._clip_offsets, self.current_idx) - 1
        idx = max(0, min(idx, len(self.clips)-1))
        c   = self.clips[idx]
        return idx, c, self.current_idx - self._clip_offsets[idx]

    def _get_clip_at_frame(self, global_frame):
        """Return (clip_idx, clip, local_idx) for any global frame."""
        total = self.get_total_frames()
        if total == 0 or not self.clips: return None, None, 0
        global_frame = max(0, min(global_frame, total-1))
        idx = bisect.bisect_right(self._clip_offsets, global_frame) - 1
        idx = max(0, min(idx, len(self.clips)-1))
        return idx, self.clips[idx], global_frame - self._clip_offsets[idx]

    # ------------------------------------------------------------------
    # Undo / state
    # ------------------------------------------------------------------
    def _save_state(self):
        self._undo_stack.append([c.clone() for c in self.clips])
        if len(self._undo_stack) > 60: self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _gc_thumb_cache(self):
        live_sources = {id(s) for s in self._sources}
        with self._thumb_cache_lock:
            self._thumb_pending = {k for k in self._thumb_pending if k[0] in live_sources}

    def _mark_edit(self, push_undo=True):
        if push_undo: self._save_state()
        self.is_dirty = True
        self._tl_dirty = True
        self._invalidate_clip_index()
        self._gc_thumb_cache()

    def undo(self):
        if not self._undo_stack: return
        self._redo_stack.append([c.clone() for c in self.clips])
        self.clips = self._undo_stack.pop()
        self._mark_edit(push_undo=False)
        self.current_idx = min(self.current_idx, max(0, self.get_total_frames()-1))

    def redo(self):
        if not self._redo_stack: return
        self._undo_stack.append([c.clone() for c in self.clips])
        self.clips = self._redo_stack.pop()
        self._mark_edit(push_undo=False)
        self.current_idx = min(self.current_idx, max(0, self.get_total_frames()-1))

    # ------------------------------------------------------------------
    # Thumbnail worker (professional version)
    # ------------------------------------------------------------------
    def _get_source_key(self, source):
        """Return a hashable key for a source (path if available, else id)."""
        return source.path if hasattr(source, 'path') and source.path else id(source)

    def _thumbnail_worker(self):
        while self._worker_active:
            try:
                task = self._thumb_queue.get(timeout=0.05)
                if task is None:
                    continue
                source, frame_idx = task
                try:
                    raw = source.get_frame_for_thumbnail(frame_idx)
                    if raw is not None:
                        thumb = cv2.resize(raw, (self.THUMB_SIZE, self.THUMB_SIZE),
                                           interpolation=cv2.INTER_NEAREST)
                    else:
                        thumb = np.zeros((self.THUMB_SIZE, self.THUMB_SIZE, 3), dtype=np.uint8)
                    key = (self._get_source_key(source), frame_idx)
                    with self._thumb_cache_lock:
                        self._thumb_cache[key] = thumb
                        if len(self._thumb_cache) > self.THUMB_CACHE_MAX:
                            self._thumb_cache.popitem(last=False)
                        self._thumb_pending.discard(key)
                    self._tl_dirty = True
                except Exception:
                    key = (self._get_source_key(source), frame_idx)
                    with self._thumb_cache_lock:
                        self._thumb_pending.discard(key)
                finally:
                    self._thumb_queue.task_done()
            except queue.Empty:
                pass
            except Exception:
                pass

    def _queue_thumbnail(self, source, frame_idx):
        key = (self._get_source_key(source), frame_idx)
        with self._thumb_cache_lock:
            if key not in self._thumb_pending and key not in self._thumb_cache:
                self._thumb_pending.add(key)
                try:
                    self._thumb_queue.put_nowait((source, frame_idx))
                except queue.Full:
                    self._thumb_pending.discard(key)

    def _get_cached_thumbnail(self, source, frame_idx):
        key = (self._get_source_key(source), frame_idx)
        with self._thumb_cache_lock:
            if key in self._thumb_cache:
                self._thumb_cache.move_to_end(key)
                return self._thumb_cache[key]
        self._queue_thumbnail(source, frame_idx)
        return None

    # ------------------------------------------------------------------
    # Timecode helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _tc(frame_idx, fps):
        fps = fps if fps and fps > 0 else 25.0
        s   = frame_idx / fps
        hh  = int(s // 3600)
        mm  = int((s % 3600) // 60)
        ss  = int(s % 60)
        ff  = int(round((s - int(s)) * fps)) % max(1, int(round(fps)))
        return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"

    def _parse_tc(self, s):
        s = s.strip()
        if not s: return None
        if s.isdigit(): return int(s)
        parts = s.split(":")
        try: parts = [float(p) for p in parts]
        except ValueError: return None
        fps = self.master_fps or 25.0
        if len(parts) == 4: return int(round((parts[0]*3600+parts[1]*60+parts[2])*fps)+parts[3])
        if len(parts) == 3: return int(round((parts[0]*3600+parts[1]*60+parts[2])*fps))
        if len(parts) == 2: return int(round((parts[0]*60+parts[1])*fps))
        return None

    # ------------------------------------------------------------------
    # Timeline zoom helpers
    # ------------------------------------------------------------------
    def _tl_total_px(self):
        total = self.get_total_frames()
        if total == 0: return self.layout["vid_w"]
        tl_x1, _, tl_x2, _ = self.layout["timeline"]
        vis_w = tl_x2 - tl_x1
        base_scale = vis_w / max(1, total)
        return max(vis_w, int(total * base_scale * self._tl_zoom))

    def _frame_to_tl_x(self, frame):
        total = self.get_total_frames()
        if total == 0: return 0
        tl_x1, _, tl_x2, _ = self.layout["timeline"]
        vis_w = tl_x2 - tl_x1
        virt_w = self._tl_total_px()
        return tl_x1 + int(frame / total * virt_w) - self._tl_scroll

    def _tl_x_to_frame(self, screen_x):
        total = self.get_total_frames()
        if total == 0: return 0
        tl_x1, _, _, _ = self.layout["timeline"]
        virt_w = self._tl_total_px()
        virtual_x = (screen_x - tl_x1) + self._tl_scroll
        return max(0, min(total-1, int(virtual_x / virt_w * total)))

    def _clamp_scroll(self):
        tl_x1, _, tl_x2, _ = self.layout["timeline"]
        vis_w  = tl_x2 - tl_x1
        virt_w = self._tl_total_px()
        self._tl_scroll = max(0, min(self._tl_scroll, max(0, virt_w - vis_w)))

    def zoom_to_fit(self):
        self._tl_zoom   = 1.0
        self._tl_scroll = 0
        self._tl_dirty  = True

    # ------------------------------------------------------------------
    # Load / file ops
    # ------------------------------------------------------------------
    def _ensure_standard_mp4(self, path):
        try:
            cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1", path]
            codec = subprocess.check_output(cmd, creationflags=subprocess.CREATE_NO_WINDOW).decode().strip()
            if codec in ("hevc", "h265"):
                out_path = os.path.join(get_data_dir(), "transcoded_" + os.path.basename(path) + ".mp4")
                if os.path.exists(out_path):
                    return out_path
                self.status_msg = "Converting H.265 to MP4..."
                self.render()
                cv2.waitKey(1)
                cmd_conv = ["ffmpeg", "-y", "-i", path, "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "aac", out_path]
                subprocess.run(cmd_conv, creationflags=subprocess.CREATE_NO_WINDOW)
                self.status_msg = ""
                return out_path
        except Exception as e:
            if isinstance(e, FileNotFoundError):
                pass # ffprobe not found
            else:
                print("FFmpeg error:", e)
        return path

    def _short_label(self, path):
        name = os.path.splitext(os.path.basename(path))[0]
        return name[:16] + ("..." if len(name) > 16 else "")

    def _open_video_from_path(self, path):
        """Load a video file and add to recent files."""
        if not os.path.exists(path):
            return
        path = self._ensure_standard_mp4(path)
        try:
            source = VideoSource(path)
        except IOError:
            self._show_error(f"Could not open:\n{path}")
            return
        # Replace any existing sources
        for s in self._sources:
            s.release()
        self._sources = [source]
        self.master_w, self.master_h, self.master_fps = source.width, source.height, source.fps
        label = self._short_label(path)
        self.clips = [Clip(source, 0, source.frame_count, label=label)]
        self.current_video_path = path
        self.current_idx = 0
        self.is_dirty    = False
        self._is_demo    = False
        self.status_msg  = ""
        self._undo_stack.clear(); self._redo_stack.clear()
        self._tl_dirty     = True
        self._viewport_idx = None
        with self._thumb_cache_lock:
            self._thumb_cache.clear()
            self._thumb_pending.clear()
        self._invalidate_clip_index()
        self._register_file(path, source)
        self.zoom_to_fit()
        self._add_recent_file(path)

    def _load_video_file(self, path):
        """Legacy method – calls _open_video_from_path."""
        self._open_video_from_path(path)

    def _register_file(self, path, source):
        if any(f["path"] == path for f in self._imported_files): return
        label = self._short_label(path)
        self._imported_files.append({"path": path, "label": label, "source": source})
        mid = source.frame_count // 2
        t   = threading.Thread(target=self._gen_file_thumb,
                               args=(path, source, mid), daemon=True)
        t.start()

    def _gen_file_thumb(self, path, source, frame_idx):
        try:
            raw = source.get_frame_for_thumbnail(frame_idx)
            if raw is None or raw.size == 0: return
            # Thumb exactly matches what the card draws: (LEFT_W - 20) wide, 60 tall
            tw = max(1, self.LEFT_W - 20)
            th = 60
            thumb = cv2.resize(raw, (tw, th), interpolation=cv2.INTER_AREA)
            self._file_thumbs[path] = thumb
            self._tl_dirty = True
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------
    def _root(self):
        self._tk_root.attributes("-topmost", True)
        return self._tk_root

    def _dialog_open(self):
        return filedialog.askopenfilename(
            parent=self._root(), title="Open / Import Media",
            initialdir=os.path.expanduser("~"),
            filetypes=[("Video", "*.mp4 *.avi *.mov *.mkv *.wmv"), ("All", "*.*")])

    def _dialog_save(self):
        base = os.path.splitext(os.path.basename(
            self.current_video_path or "Sequence_01"))[0]
        return filedialog.asksaveasfilename(
            parent=self._root(), title="Export Sequence",
            initialfile=f"{base}_EXPORT.mp4",
            defaultextension=".mp4",
            filetypes=[("MP4", "*.mp4"), ("AVI", "*.avi")])

    def _show_error(self, msg):
        messagebox.showerror("Kut", msg, parent=self._root())

    def _safe_exit(self):
        if not self.is_dirty: return True
        ans = messagebox.askyesnocancel("Unsaved", "Export before closing?", parent=self._root())
        if ans is True: return self._execute_export()
        return ans is False

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    def _execute_open(self):
        if not self._safe_exit(): return
        p = self._dialog_open()
        if p: self._open_video_from_path(p)

    def _execute_import(self):
        p = self._dialog_open()
        if not p: return
        p = self._ensure_standard_mp4(p)
        if self._is_demo: self._open_video_from_path(p); return
        try: source = VideoSource(p)
        except IOError: self._show_error(f"Cannot open:\n{p}"); return
        self._sources.append(source)
        self._register_file(p, source)
        self._add_recent_file(p)

    def _execute_export(self):
        # Guard against double-clicking during active export
        if getattr(self, "_is_exporting", False):
            return False
            
        total = self.get_total_frames()
        if total == 0: return False
        
        def ask_radio(title, prompt, options):
            import tkinter as tk
            root = self._root()
            top = tk.Toplevel(root)
            top.title(title)
            top.geometry("320x180")
            
            # CRITICAL FIX: Do NOT use top.transient(root) when root is withdrawn.
            # Keep dialog topmost over OpenCV window and center it.
            top.attributes("-topmost", True)
            top.resizable(False, False)
            
            choice_var = tk.StringVar(value=options[0][1])
            tk.Label(top, text=prompt, font=("Arial", 10)).pack(pady=10)
            for text, val in options:
                tk.Radiobutton(top, text=text, variable=choice_var, value=val, font=("Arial", 10)).pack(anchor="w", padx=50)
                
            result = [None]
            def on_ok():
                result[0] = choice_var.get()
                top.destroy()
                
            btn_frame = tk.Frame(top)
            btn_frame.pack(pady=15)
            tk.Button(btn_frame, text="OK", command=on_ok, width=10).pack(side="left", padx=10)
            tk.Button(btn_frame, text="Cancel", command=top.destroy, width=10).pack(side="left", padx=10)
            
            # CRITICAL FIX: Render UI before grabbing input events
            top.update_idletasks()
            top.grab_set()
            top.focus_force()
            
            root.wait_window(top)
            return result[0]

        choice = ask_radio("Export", "Select export format:", [("Video (MP4)", "video"), ("Image Sequence (Frames)", "frames")])
        if not choice: return False
        
        self._is_exporting = True
        try:
            if choice == "video":
                target = self._dialog_save()
                if not target: return False
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(target, fourcc, self.master_fps, (self.master_w, self.master_h))
                if not writer.isOpened():
                    self._show_error("Could not create output file."); return False
                written = 0
                try:
                    for clip in self.clips:
                        for li in range(len(clip)):
                            frame = clip.get_frame(li, high_quality=True, global_blur_strokes=self.global_blur_strokes)
                            if (frame.shape[1], frame.shape[0]) != (self.master_w, self.master_h):
                                frame = cv2.resize(frame, (self.master_w, self.master_h), interpolation=cv2.INTER_CUBIC)
                            writer.write(frame)
                            written += 1
                            if written % 20 == 0 or written == total:
                                self.status_msg = f"Exporting: {written}/{total}"
                                self.render(); cv2.waitKey(1)
                finally:
                    writer.release()
                self.is_dirty = False; self.status_msg = ""; return True
                
            elif choice == "frames":
                out_dir = filedialog.askdirectory(parent=self._root(), title="Select Output Folder")
                if not out_dir: return False
                
                mode = ask_radio("Frames Export", "Select frame extraction mode:", [("Frames Per Second (FPS)", "fps"), ("Fixed Number of Frames", "fixed")])
                if not mode: return False
                
                if mode == "fps":
                    val = simpledialog.askfloat("FPS", "Enter frames per second to extract:", parent=self._root(), initialvalue=1.0)
                    if not val or val <= 0: return False
                    step = max(1, int(self.master_fps / val))
                    frames_to_export = list(range(0, total, step))
                elif mode == "fixed":
                    val = simpledialog.askinteger("Fixed", "Enter total number of frames to extract:", parent=self._root(), initialvalue=100)
                    if not val or val <= 0: return False
                    step = max(1, total // val)
                    frames_to_export = list(range(0, total, step))[:val]
                else:
                    return False
                    
                written = 0
                for gf in frames_to_export:
                    c_idx, c, l_idx = self._get_clip_at_frame(gf)
                    if c:
                        frame = c.get_frame(l_idx, high_quality=True, global_blur_strokes=self.global_blur_strokes)
                        if (frame.shape[1], frame.shape[0]) != (self.master_w, self.master_h):
                            frame = cv2.resize(frame, (self.master_w, self.master_h), interpolation=cv2.INTER_CUBIC)
                        fname = os.path.join(out_dir, f"frame_{gf:06d}.jpg")
                        cv2.imwrite(fname, frame)
                    written += 1
                    if written % 10 == 0 or written == len(frames_to_export):
                        self.status_msg = f"Exporting Frames: {written}/{len(frames_to_export)}"
                        self.render(); cv2.waitKey(1)
                self.status_msg = ""; return True
        finally:
            self._is_exporting = False

    def _execute_goto(self):
        total = self.get_total_frames()
        if total == 0: return
        val = simpledialog.askstring(
            "Go To", "Timecode HH:MM:SS:FF  or  frame number:",
            initialvalue=self._tc(self.current_idx, self.master_fps),
            parent=self._root())
        if not val: return
        f = self._parse_tc(val)
        if f is not None:
            self.current_idx = max(0, min(f, total-1))
        else:
            self._show_error(f"Invalid timecode: '{val}'")

    def _execute_split_at_frame(self, global_frame):
        c_idx, c, local_idx = self._get_clip_at_frame(global_frame)
        if c is None or local_idx <= 0 or local_idx >= len(c)-1: return
        a, b = c.split(local_idx)
        self._save_state()
        self.clips[c_idx:c_idx+1] = [a, b]
        self._mark_edit(push_undo=False)

    # ------------------------------------------------------------------
    # DRAW — Left panel  (Media Browser)
    # ------------------------------------------------------------------
    def _draw_left_panel(self, canvas):
        x1, y1, x2, y2 = self.layout["left"]
        panel_w = x2 - x1

        # Panel background
        cv2.rectangle(canvas, (x1, y1), (x2, y2), Theme.PANEL_DARK, -1)

        # Section header
        y_cursor = UI.section_header(canvas, x1, y1, x2, "MEDIA BROWSER")

        # Right border separator
        UI.vline(canvas, x2 - 1, y1, y2, Theme.BORDER)

        # ── File cards ───────────────────────────────────────────────
        CARD_PAD   = 6          # horizontal padding inside panel
        CARD_H     = 96         # card height
        CARD_INNER = 4          # inner padding
        THUMB_H    = 60         # thumbnail height in card
        THUMB_W    = panel_w - CARD_PAD * 2 - CARD_INNER * 2  # exact thumb width

        for fi, fdict in enumerate(self._imported_files):
            path  = fdict["path"]
            label = fdict["label"]

            if y_cursor + CARD_H > y2 - 4:
                break

            # Active detection
            active_src = None
            if self.clips:
                ai, _, _ = self.get_clip_at_playhead()
                if ai is not None:
                    active_src = self.clips[ai].source
            is_active = (fdict["source"] is active_src)

            # Card background
            cx1 = x1 + CARD_PAD
            cx2 = x2 - CARD_PAD
            cy1 = y_cursor
            cy2 = y_cursor + CARD_H

            bg     = Theme.PANEL_ALT if is_active else Theme.PANEL
            border = Theme.BORDER_ACT if is_active else Theme.BORDER
            UI.rounded_rect(canvas, (cx1, cy1), (cx2, cy2), bg, radius=6,
                            border_color=border, border_thick=2 if is_active else 1)

            # ── Thumbnail ────────────────────────────────────────────
            tx1 = cx1 + CARD_INNER
            ty1 = cy1 + CARD_INNER
            tx2 = cx2 - CARD_INNER
            ty2 = ty1 + THUMB_H
            actual_tw = tx2 - tx1
            actual_th = ty2 - ty1

            thumb = self._file_thumbs.get(path)
            if thumb is not None:
                # Resize to fit exactly the slot available
                try:
                    t_h, t_w = thumb.shape[:2]
                    if t_w != actual_tw or t_h != actual_th:
                        thumb_fit = cv2.resize(thumb, (actual_tw, actual_th),
                                               interpolation=cv2.INTER_AREA)
                    else:
                        thumb_fit = thumb
                    # Clamp paste region to canvas
                    p_tx1 = max(0, tx1); p_tx2 = min(canvas.shape[1], tx2)
                    p_ty1 = max(0, ty1); p_ty2 = min(canvas.shape[0], ty2)
                    s_tx1 = p_tx1 - tx1; s_tx2 = s_tx1 + (p_tx2 - p_tx1)
                    s_ty1 = p_ty1 - ty1; s_ty2 = s_ty1 + (p_ty2 - p_ty1)
                    if p_tx2 > p_tx1 and p_ty2 > p_ty1 and s_tx2 > s_tx1 and s_ty2 > s_ty1:
                        canvas[p_ty1:p_ty2, p_tx1:p_tx2] = thumb_fit[s_ty1:s_ty2, s_tx1:s_tx2]
                    # Subtle overlay border on thumbnail
                    cv2.rectangle(canvas, (tx1, ty1), (tx2, ty2), Theme.BORDER, 1)
                except Exception:
                    pass
            else:
                # Loading placeholder
                cv2.rectangle(canvas, (tx1, ty1), (tx2, ty2), Theme.PANEL_DARK, -1)
                cv2.rectangle(canvas, (tx1, ty1), (tx2, ty2), Theme.BORDER, 1)
                lw = UI.text_w("Loading...", 0.30)
                UI.text(canvas, "Loading...",
                        (tx1 + (actual_tw - lw) // 2, ty1 + actual_th // 2 + 4),
                        0.30, Theme.TEXT_DIM, shadow=False)

            # ── Label row ────────────────────────────────────────────
            label_y = ty2 + 14
            UI.text(canvas, label, (cx1 + 28, label_y), 0.32, Theme.TEXT, shadow=False)

            # ── Trash icon button ────────────────────────────────────
            trash_cx = cx2 - 14
            trash_cy = ty2 + 10
            UI.draw_trash_icon(canvas, trash_cx, trash_cy, size=8, color=Theme.DANGER)

            # Store hit rects
            fdict["rect"]     = (cx1, cy1, cx2, cy2)
            fdict["del_rect"] = (trash_cx - 10, ty2 + 1, trash_cx + 10, cy2 - 2)

            y_cursor += CARD_H + 5

        # ── Empty state ───────────────────────────────────────────────
        if not self._imported_files:
            mid_x = x1 + panel_w // 2
            mid_y = y1 + (y2 - y1) // 2 - 20
            # Film strip icon
            fs_w, fs_h = 36, 28
            fs_x1 = mid_x - fs_w // 2
            fs_y1 = mid_y - fs_h // 2
            cv2.rectangle(canvas, (fs_x1, fs_y1), (fs_x1 + fs_w, fs_y1 + fs_h), Theme.BORDER, 1)
            for hx in [fs_x1 + 4, fs_x1 + fs_w - 4]:
                for hy_off in [4, 10, 16]:
                    cv2.rectangle(canvas, (hx - 2, fs_y1 + hy_off),
                                  (hx + 2, fs_y1 + hy_off + 4), Theme.BORDER, -1)
            lw = UI.text_w("Import media", 0.32)
            UI.text(canvas, "Import media",
                    (mid_x - lw // 2, mid_y + fs_h // 2 + 20),
                    0.32, Theme.TEXT_DIM, shadow=False)

    # ------------------------------------------------------------------
    # DRAW — Right panel (Tracks)
    # ------------------------------------------------------------------
    def _draw_right_panel(self, canvas):
        x1, y1, x2, y2 = self.layout["right"]
        panel_w = x2 - x1

        # Background
        cv2.rectangle(canvas, (x1, y1), (x2, y2), Theme.PANEL_DARK, -1)
        UI.vline(canvas, x1, y1, y2, Theme.BORDER)

        # Section header
        y_cursor = UI.section_header(canvas, x1, y1, x2, "SEQUENCE")

        active_idx, _, _ = self.get_clip_at_playhead()
        CARD_H  = 62
        CARD_PAD = 6
        
        self._track_rects = []

        for idx, clip in enumerate(self.clips):
            if y_cursor + CARD_H > y2 - 4:
                break

            is_active = (idx == active_idx)
            cx1 = x1 + CARD_PAD
            cx2 = x2 - CARD_PAD
            cy1 = y_cursor
            cy2 = y_cursor + CARD_H

            bg     = Theme.PANEL_ALT if is_active else Theme.PANEL
            border = Theme.BORDER_ACT if is_active else Theme.BORDER
            UI.rounded_rect(canvas, (cx1, cy1), (cx2, cy2), bg, radius=6,
                            border_color=border, border_thick=2 if is_active else 1)

            # Color swatch strip
            sw_x1, sw_y1 = cx1 + 4, cy1 + 8
            sw_x2, sw_y2 = cx1 + 12, cy2 - 8
            UI.rounded_rect(canvas, (sw_x1, sw_y1), (sw_x2, sw_y2), clip.color, radius=2)

            # Track number badge (top-right)
            badge_lbl = f"{idx+1:02d}"
            badge_w   = UI.text_w(badge_lbl, 0.28) + 8
            bx2 = cx2 - 6
            bx1 = bx2 - badge_w
            by1 = cy1 + 6
            by2 = by1 + 14
            UI.rounded_rect(canvas, (bx1, by1), (bx2, by2), Theme.PANEL_DARK, radius=3,
                            border_color=Theme.BORDER)
            UI.text(canvas, badge_lbl, (bx1 + 4, by2 - 3), 0.28, Theme.TEXT_DIM, shadow=False)

            # Label (source filename)
            lbl_text = clip.label[:18]
            col = Theme.TEXT_BRIGHT if is_active else Theme.TEXT
            UI.text(canvas, lbl_text, (cx1 + 18, cy1 + 22), 0.33, col, shadow=False)

            # Duration
            fps = self.master_fps or 25.0
            total_s = len(clip) / fps
            mm = int(total_s // 60)
            ss = int(total_s % 60)
            ff = int(round((total_s - int(total_s)) * fps)) % max(1, int(fps))
            dur_str = f"{mm:02d}:{ss:02d}.{ff:02d}  •  {len(clip)}f"
            UI.text(canvas, dur_str, (cx1 + 18, cy1 + 42), 0.28, Theme.TEXT_DIM, shadow=False)

            # ── Trash icon button ────────────────────────────────────
            trash_cx = cx2 - 14
            trash_cy = cy2 - 14
            UI.draw_trash_icon(canvas, trash_cx, trash_cy, size=8, color=Theme.DANGER)

            # Store hit rects
            self._track_rects.append({
                "idx": idx,
                "rect": (cx1, cy1, cx2, cy2),
                "del_rect": (trash_cx - 10, trash_cy - 10, trash_cx + 10, trash_cy + 10)
            })

            y_cursor += CARD_H + 4

        if not self.clips:
            mid_x = x1 + panel_w // 2
            lw = UI.text_w("No clips", 0.32)
            UI.text(canvas, "No clips",
                    (mid_x - lw // 2, y1 + (y2 - y1) // 2),
                    0.32, Theme.TEXT_DIM, shadow=False)

    # ------------------------------------------------------------------
    # DRAW — Viewport (includes empty state)
    # ------------------------------------------------------------------
    def _draw_viewport(self, canvas):
        vx1, vy1, vx2, vy2 = self.layout["viewport"]
        vw = vx2 - vx1; vh = vy2 - vy1
        total = self.get_total_frames()

        if total > 0 and self.clips:
            _, c, local_idx = self.get_clip_at_playhead()
            if c and 0 <= local_idx < len(c):
                if self._viewport_idx != self.current_idx or self._viewport_img is None:
                    raw = c.get_frame(local_idx, ignore_crop=getattr(self, "_crop_mode", False), global_blur_strokes=self.global_blur_strokes)
                    zoom = self._viewport_zoom
                    pan_x = self._viewport_pan_x
                    pan_y = self._viewport_pan_y
                    
                    if zoom != 1.0 or pan_x != 0 or pan_y != 0:
                        zw, zh = int(vw * zoom), int(vh * zoom)
                        scaled = cv2.resize(raw, (max(1, zw), max(1, zh)), interpolation=cv2.INTER_NEAREST)
                        result = np.zeros((vh, vw, 3), dtype=np.uint8)
                        
                        cx, cy = vw // 2 + int(pan_x), vh // 2 + int(pan_y)
                        x1, y1 = cx - zw // 2, cy - zh // 2
                        x2, y2 = x1 + zw, y1 + zh
                        
                        dx1, dy1 = max(0, x1), max(0, y1)
                        dx2, dy2 = min(vw, x2), min(vh, y2)
                        
                        sx1, sy1 = dx1 - x1, dy1 - y1
                        sx2, sy2 = sx1 + (dx2 - dx1), sy1 + (dy2 - dy1)
                        
                        if dx2 > dx1 and dy2 > dy1:
                            result[dy1:dy2, dx1:dx2] = scaled[sy1:sy2, sx1:sx2]
                        self._viewport_img = result
                    else:
                        self._viewport_img = cv2.resize(raw, (vw, vh), interpolation=cv2.INTER_NEAREST)
                    
                    self._viewport_idx = self.current_idx
                canvas[vy1:vy1+vh, vx1:vx1+vw] = self._viewport_img

                # ── Crop / Blur floating pill toolbar ────────────────────
                is_crop_act = getattr(self, "_crop_mode", False)
                is_blur_act = getattr(self, "_blur_mode", False)

                pill_btn_w = 44
                pill_btn_h = 36
                pill_gap   = 4
                pill_pad   = 6
                pill_total_w = pill_btn_w * 2 + pill_gap + pill_pad * 2
                pill_total_h = pill_btn_h + pill_pad * 2
                pill_x = vx1 + vw // 2 - pill_total_w // 2
                pill_y = vy1 + 10

                # Semi-transparent pill background (blend with canvas)
                try:
                    pill_region = canvas[pill_y:pill_y+pill_total_h, pill_x:pill_x+pill_total_w]
                    blended = cv2.addWeighted(
                        pill_region, 0.35,
                        np.full_like(pill_region, Theme.PANEL_DARK), 0.65, 0)
                    canvas[pill_y:pill_y+pill_total_h, pill_x:pill_x+pill_total_w] = blended
                except Exception:
                    pass

                UI.rounded_rect(canvas, (pill_x, pill_y), (pill_x+pill_total_w, pill_y+pill_total_h),
                                Theme.PANEL_DARK, radius=8,
                                border_color=Theme.BORDER, border_thick=1)

                # Crop button
                bx_crop = pill_x + pill_pad
                by_crop = pill_y + pill_pad
                UI.rounded_rect(canvas, (bx_crop, by_crop),
                                (bx_crop+pill_btn_w, by_crop+pill_btn_h),
                                Theme.ACCENT_DARK if is_crop_act else Theme.PANEL_ALT,
                                radius=6,
                                border_color=Theme.ACCENT if is_crop_act else Theme.BORDER)
                # Crop glyph: corner handles
                ic = Theme.TEXT_BRIGHT if is_crop_act else Theme.TEXT_DIM
                mcx, mcy = bx_crop + pill_btn_w//2, by_crop + pill_btn_h//2
                cv2.rectangle(canvas, (mcx-9, mcy-8), (mcx+9, mcy+8), ic, 1)
                cv2.line(canvas, (mcx-9, mcy-8), (mcx-13, mcy-8), ic, 2)
                cv2.line(canvas, (mcx-9, mcy-8), (mcx-9, mcy-12), ic, 2)
                cv2.line(canvas, (mcx+9, mcy+8), (mcx+13, mcy+8), ic, 2)
                cv2.line(canvas, (mcx+9, mcy+8), (mcx+9, mcy+12), ic, 2)
                self._crop_btn_rect = (bx_crop, by_crop, bx_crop+pill_btn_w, by_crop+pill_btn_h)

                # Blur button
                bx_blur = bx_crop + pill_btn_w + pill_gap
                by_blur = pill_y + pill_pad
                UI.rounded_rect(canvas, (bx_blur, by_blur),
                                (bx_blur+pill_btn_w, by_blur+pill_btn_h),
                                Theme.ACCENT_DARK if is_blur_act else Theme.PANEL_ALT,
                                radius=6,
                                border_color=Theme.ACCENT if is_blur_act else Theme.BORDER)
                # Blur glyph: concentric circles
                ib = Theme.TEXT_BRIGHT if is_blur_act else Theme.TEXT_DIM
                mbc = (bx_blur + pill_btn_w//2, by_blur + pill_btn_h//2)
                cv2.circle(canvas, mbc, 10, ib, 1, cv2.LINE_AA)
                cv2.circle(canvas, mbc, 5,  ib, 1, cv2.LINE_AA)
                cv2.circle(canvas, mbc, 2,  ib, -1, cv2.LINE_AA)
                self._blur_btn_rect = (bx_blur, by_blur, bx_blur+pill_btn_w, by_blur+pill_btn_h)

                # Draw crop overlay
                if getattr(self, "_crop_mode", False):
                    crop = getattr(c, "_temp_crop", c.crop or [0.0, 0.0, 1.0, 1.0])
                    zoom = self._viewport_zoom
                    pan_x, pan_y = self._viewport_pan_x, self._viewport_pan_y
                    zw, zh = int(vw * zoom), int(vh * zoom)
                    cx, cy = vx1 + vw // 2 + int(pan_x), vy1 + vh // 2 + int(pan_y)
                    img_x1, img_y1 = cx - zw // 2, cy - zh // 2
                    
                    sx1 = img_x1 + int(crop[0] * zw)
                    sy1 = img_y1 + int(crop[1] * zh)
                    sx2 = img_x1 + int(crop[2] * zw)
                    sy2 = img_y1 + int(crop[3] * zh)
                    
                    cv2.rectangle(canvas, (max(vx1, sx1), max(vy1, sy1)), (min(vx2, sx2), min(vy2, sy2)), Theme.ACCENT, 2)
                    
                    # Corner handles
                    for hx, hy in [(sx1, sy1), (sx2, sy1), (sx1, sy2), (sx2, sy2)]:
                        if vx1 <= hx <= vx2 and vy1 <= hy <= vy2:
                            cv2.circle(canvas, (hx, hy), 6, Theme.TEXT_BRIGHT, -1)
                            cv2.circle(canvas, (hx, hy), 6, Theme.ACCENT, 2)
                            
                    UI.text(canvas, "CROP MODE: Drag corners or click & drag center. Press Enter to apply.", (vx1+10, vy1+20), 0.4, Theme.ACCENT, shadow=True)

                # Draw blur overlay
                if getattr(self, "_blur_mode", False):
                    zoom = self._viewport_zoom
                    pan_x, pan_y = self._viewport_pan_x, self._viewport_pan_y
                    zw, zh = int(vw * zoom), int(vh * zoom)
                    
                    # Brush cursor outline
                    mx, my = getattr(self, "_mouse_x", 0), getattr(self, "_mouse_y", 0)
                    if vx1 <= mx <= vx2 and vy1 <= my <= vy2:
                        cv2.circle(canvas, (mx, my), self._blur_brush_size, Theme.ACCENT, 1, cv2.LINE_AA)

                    # Controls panel
                    ctrl_w = 400
                    ctrl_h = 32
                    ctrl_x = vx1 + (vw - ctrl_w) // 2
                    ctrl_y = vy1 + 10
                    
                    # Background panel
                    UI.rounded_rect(canvas, (ctrl_x, ctrl_y), (ctrl_x + ctrl_w, ctrl_y + ctrl_h), Theme.PANEL, radius=6, border_color=Theme.BORDER)
                    UI.text(canvas, "Blur:", (ctrl_x + 10, ctrl_y + 20), 0.35, Theme.TEXT_DIM, shadow=False)
                    
                    # Scope buttons: Track, Video, Global
                    scopes = [("track", "Track"), ("video", "Video"), ("global", "Global")]
                    bx = ctrl_x + 55
                    for s_id, s_lbl in scopes:
                        is_act = (self._blur_scope == s_id)
                        bg_col = Theme.ACCENT_DARK if is_act else Theme.PANEL_ALT
                        txt_col = Theme.TEXT_BRIGHT if is_act else Theme.TEXT_DIM
                        b_w = 60
                        UI.rounded_rect(canvas, (bx, ctrl_y + 4), (bx + b_w, ctrl_y + 28), bg_col, radius=4, border_color=Theme.BORDER_HI if is_act else Theme.BORDER)
                        tw = UI.text_w(s_lbl, 0.32)
                        UI.text(canvas, s_lbl, (bx + (b_w - tw)//2, ctrl_y + 19), 0.32, txt_col, shadow=False)
                        bx += b_w + 5
                    
                    # Clear button
                    clear_rect = (ctrl_x + 255, ctrl_y + 4, ctrl_x + 315, ctrl_y + 28)
                    UI.rounded_rect(canvas, (clear_rect[0], clear_rect[1]), (clear_rect[2], clear_rect[3]), Theme.PANEL_ALT, radius=4, border_color=Theme.DANGER)
                    tw = UI.text_w("Clear", 0.32)
                    UI.text(canvas, "Clear", (clear_rect[0] + (60 - tw)//2, ctrl_y + 19), 0.32, Theme.DANGER, shadow=False)
                    
                    # Brush size text
                    size_str = f"Sz: {self._blur_brush_size}"
                    UI.text(canvas, size_str, (ctrl_x + 325, ctrl_y + 19), 0.32, Theme.TEXT, shadow=False)
                    
                    # Help instructions at the bottom of the viewport
                    UI.text(canvas, "BLUR MODE: Paint on video to blur. [ / ] changes brush size. Enter to apply.", (vx1+10, vy1+vh-15), 0.35, Theme.ACCENT, shadow=True)
            else:
                cv2.rectangle(canvas, (vx1, vy1), (vx2, vy2), Theme.PANEL_DARK, -1)
                lw = UI.text_w("SEQUENCE EMPTY", 0.65)
                UI.text(canvas, "SEQUENCE EMPTY",
                        (vx1 + (vw - lw) // 2, vy1 + vh // 2 + 8), 0.65, Theme.BORDER, shadow=False)
        else:
            # ---- EMPTY STATE ----
            cv2.rectangle(canvas, (vx1, vy1), (vx2, vy2), Theme.PANEL_DARK, -1)

            # Centered import card
            card_w = min(420, vw - 80)
            card_h = 200
            card_x1 = vx1 + (vw - card_w) // 2
            card_y1 = vy1 + (vh - card_h) // 2 - 20
            card_x2 = card_x1 + card_w
            card_y2 = card_y1 + card_h

            UI.rounded_rect(canvas, (card_x1, card_y1), (card_x2, card_y2),
                            Theme.PANEL, radius=14,
                            border_color=Theme.BORDER_HI, border_thick=2)

            # Film strip icon (centred in card)
            mid_cx = (card_x1 + card_x2) // 2
            icon_y  = card_y1 + 48
            fs_w, fs_h = 48, 36
            fx1 = mid_cx - fs_w // 2
            cv2.rectangle(canvas, (fx1, icon_y), (fx1 + fs_w, icon_y + fs_h), Theme.ACCENT, 2)
            for hx_off in [6, fs_w - 6]:
                for hy_off in [5, 13, 21]:
                    cv2.rectangle(canvas, (fx1 + hx_off - 3, icon_y + hy_off),
                                  (fx1 + hx_off + 3, icon_y + hy_off + 5), Theme.ACCENT, -1)
            cv2.line(canvas, (fx1 + 14, icon_y + 2), (fx1 + fs_w - 14, icon_y + 2), Theme.PANEL, 2)
            cv2.line(canvas, (fx1 + 14, icon_y + fs_h - 2), (fx1 + fs_w - 14, icon_y + fs_h - 2), Theme.PANEL, 2)

            # Heading
            h1 = "Import a video to begin"
            hw = UI.text_w(h1, 0.52)
            UI.text(canvas, h1, (mid_cx - hw // 2, icon_y + fs_h + 34), 0.52, Theme.TEXT_BRIGHT, shadow=True)

            # Sub-heading
            h2 = "Use the Import button or click here"
            hw2 = UI.text_w(h2, 0.36)
            UI.text(canvas, h2, (mid_cx - hw2 // 2, icon_y + fs_h + 60), 0.36, Theme.TEXT_DIM, shadow=False)

            # ---- Recent files panel (below the import card) ----
            recent_y = card_y2 + 18
            self._recent_rects = []
            if self.recent_files:
                rw = UI.text_w("RECENT", 0.28)
                UI.text(canvas, "RECENT", (mid_cx - rw // 2, recent_y), 0.28, Theme.TEXT_DIM, shadow=False)
                item_h = 30
                for i, fpath in enumerate(self.recent_files[:4]):
                    ry0 = recent_y + 14 + i * (item_h + 2)
                    ry1 = ry0 + item_h
                    if ry1 > vy2 - 10: break
                    rf_x1 = mid_cx - card_w // 2
                    rf_x2 = mid_cx + card_w // 2
                    UI.rounded_rect(canvas, (rf_x1, ry0), (rf_x2, ry1), Theme.PANEL_ALT,
                                    radius=4, border_color=Theme.BORDER)
                    lbl = os.path.basename(fpath)
                    UI.text(canvas, lbl, (rf_x1 + 12, ry1 - 8), 0.34, Theme.TEXT, shadow=False)
                    self._recent_rects.append((rf_x1, ry0, rf_x2, ry1, fpath))


        cv2.rectangle(canvas, (vx1, vy1), (vx2, vy2), Theme.BORDER, 1)

    # ------------------------------------------------------------------
    # DRAW — Timeline strip
    # ------------------------------------------------------------------
    def _build_timeline(self):
        tl_x1, tl_y1, tl_x2, tl_y2 = self.layout["timeline"]
        vis_w  = tl_x2 - tl_x1
        vis_h  = tl_y2 - tl_y1
        strip  = np.full((vis_h, vis_w, 3), Theme.BG, dtype=np.uint8)

        total  = self.get_total_frames()
        fps    = self.master_fps or 25.0
        ruler_h  = 28          # taller ruler
        clip_top = ruler_h + 2
        clip_bot = vis_h - 4

        # ---- Ruler background ----
        cv2.rectangle(strip, (0, 0), (vis_w, ruler_h), Theme.RULER_BG, -1)
        cv2.line(strip, (0, ruler_h - 1), (vis_w, ruler_h - 1), Theme.BORDER, 1)

        if total > 0:
            virt_w = self._tl_total_px()
            px_per_frame = virt_w / total
            px_per_sec = px_per_frame * fps if px_per_frame * fps > 0 else 1.0
            
            start_sec = self._tl_scroll / px_per_sec
            end_sec = (self._tl_scroll + vis_w) / px_per_sec
            secs_visible = end_sec - start_sec

            if secs_visible < 0.005:
                tick_sec = 0.0001
                fmt = lambda s: f"{s:.4f}s"
            elif secs_visible < 0.05:
                tick_sec = 0.001
                fmt = lambda s: f"{s:.3f}s"
            elif secs_visible < 0.2:
                tick_sec = 0.01
                fmt = lambda s: f"{s:.3f}s"
            elif secs_visible < 1:
                tick_sec = 0.05
                fmt = lambda s: f"{s:.2f}s"
            elif secs_visible < 5:
                tick_sec = 0.2
                fmt = lambda s: f"{s:.1f}s"
            elif secs_visible < 20:
                tick_sec = 1.0
                fmt = lambda s: f"{int(s)}s"
            elif secs_visible < 60:
                tick_sec = 5.0
                fmt = lambda s: f"{int(s)}s"
            elif secs_visible < 300: # 5 mins
                tick_sec = 15.0
                fmt = lambda s: f"{int(s//60)}m{int(s%60):02d}s"
            elif secs_visible < 1200: # 20 mins
                tick_sec = 60.0
                fmt = lambda s: f"{int(s//60)}m"
            elif secs_visible < 3600: # 1 hour
                tick_sec = 180.0
                fmt = lambda s: f"{int(s//60)}m"
            elif secs_visible < 14400: # 4 hours
                tick_sec = 600.0
                fmt = lambda s: f"{int(s/3600)}h{int((s%3600)//60):02d}m"
            else:
                tick_sec = 1800.0
                fmt = lambda s: f"{int(s/3600)}h{int((s%3600)//60):02d}m"

            import math
            first_tick = math.floor(start_sec / tick_sec) * tick_sec
            
            t = first_tick
            while t <= end_sec:
                vx = int(t * px_per_sec) - self._tl_scroll
                if -60 <= vx <= vis_w + 60:
                    # Major tick
                    cv2.line(strip, (vx, ruler_h - 10), (vx, ruler_h - 1), Theme.TEXT_DIM, 1)
                    lbl = fmt(t)
                    UI.text(strip, lbl, (vx + 3, ruler_h - 12), 0.26, Theme.TEXT_DIM, shadow=False)
                    # Minor sub-tick halfway
                    vx_half = vx + int(tick_sec * 0.5 * px_per_sec)
                    if 0 <= vx_half <= vis_w:
                        cv2.line(strip, (vx_half, ruler_h - 5), (vx_half, ruler_h - 1), Theme.BORDER, 1)
                t += tick_sec

            # Draw frame ticks and frame numbers if zoomed in enough
            if px_per_frame > 4:
                first_frame = int(self._tl_scroll / px_per_frame)
                last_frame = int((self._tl_scroll + vis_w) / px_per_frame)
                for f in range(first_frame, last_frame + 1):
                    vx = int(f * px_per_frame) - self._tl_scroll
                    if 0 <= vx <= vis_w:
                        cv2.line(strip, (vx, ruler_h - 4), (vx, ruler_h), Theme.TEXT_DIM, 1)
                        if px_per_frame > 30 and f % 5 == 0:
                            UI.text(strip, f"{f}f", (vx + 2, ruler_h - 10), 0.25, Theme.TEXT_DIM, shadow=False)

        # ---- Clips ----
        active_idx, _, _ = self.get_clip_at_playhead()
        head_h = 14
        thumb_h = (clip_bot - clip_top) - head_h

        if total > 0 and self.clips:
            virt_w = self._tl_total_px()
            for idx, c in enumerate(self.clips):
                c_len = len(c)
                if c_len == 0: continue
                off   = self._clip_offsets[idx]
                x1    = int(off / total * virt_w) - self._tl_scroll
                x2    = int((off + c_len) / total * virt_w) - self._tl_scroll
                w     = max(4, x2 - x1)

                if x2 < 0 or x1 > vis_w: continue

                cx1 = max(0, x1); cx2 = min(vis_w, x2)
                cw  = cx2 - cx1
                if cw <= 0: continue

                UI.rounded_rect(strip, (cx1+1, clip_top), (cx2-1, clip_bot),
                                 Theme.PANEL_ALT, radius=4)

                if thumb_h > 4 and cw > 0:
                    wave = c.waveform_pattern(cw, thumb_h)
                    ty1  = clip_top + head_h
                    strip[ty1:ty1+thumb_h, cx1:cx2] = wave

                # Thumbnails
                if thumb_h > 4 and w > 0:
                    tile_size = max(1, self.THUMB_SIZE)
                    tiles = max(1, w // tile_size)
                    tile_w = max(1, w // tiles)
                    for ti in range(tiles):
                        tix1 = x1 + ti * tile_w
                        tix2 = x1 + (ti+1) * tile_w
                        stx1 = max(0, tix1)
                        stx2 = min(vis_w, tix2)
                        if stx2 <= stx1:
                            continue
                        frame_frac = (ti + 0.5) / tiles
                        frame_idx = int(frame_frac * c_len)
                        if frame_idx >= c_len:
                            frame_idx = c_len - 1
                        global_frame_idx = c.start + frame_idx
                        thumb = self._get_cached_thumbnail(c.source, global_frame_idx)
                        if thumb is not None:
                            if tile_w > 1 and thumb_h > 1:
                                scaled = cv2.resize(thumb, (tile_w, thumb_h),
                                                    interpolation=cv2.INTER_NEAREST)
                                src_x1 = stx1 - tix1
                                src_x2 = src_x1 + (stx2 - stx1)
                                src_x1 = max(0, min(tile_w, src_x1))
                                src_x2 = max(0, min(tile_w, src_x2))
                                if src_x2 > src_x1:
                                    dest_w = src_x2 - src_x1
                                    ty = clip_top + head_h
                                    strip[ty:ty+thumb_h, stx1:stx1+dest_w] = scaled[:, src_x1:src_x2]

                # Header band with clip label
                header_color = c.color
                cv2.rectangle(strip, (cx1+2, clip_top), (cx2-2, clip_top+head_h), header_color, -1)
                if cw > 50:
                    lbl_str = c.label[:12]
                    UI.text(strip, lbl_str,
                            (cx1 + 6, clip_top + head_h - 3), 0.26, (15, 15, 15), shadow=False)

                is_active = (idx == active_idx)
                bdr = Theme.BORDER_ACT if is_active else Theme.BORDER
                thick = 2 if is_active else 1
                cv2.rectangle(strip, (cx1+1, clip_top), (cx2-1, clip_bot), bdr, thick)

            if self._drag_reorder_ghost is not None:
                gi = self._drag_reorder_ghost
                if 0 <= gi <= len(self.clips):
                    if gi < len(self.clips):
                        gx = int(self._clip_offsets[gi] / total * virt_w) - self._tl_scroll
                    else:
                        gx = vis_w
                    cv2.line(strip, (gx, clip_top-2), (gx, clip_bot+2), Theme.GHOST, 3)

        # ---- Playhead ----
        if total > 0:
            virt_w = self._tl_total_px()
            px = int(self.current_idx / total * virt_w) - self._tl_scroll
            if 0 <= px <= vis_w:
                # Glow line (dim)
                cv2.line(strip, (px-1, ruler_h), (px-1, vis_h), (80, 80, 80), 1)
                cv2.line(strip, (px+1, ruler_h), (px+1, vis_h), (80, 80, 80), 1)
                # Main line
                cv2.line(strip, (px, ruler_h), (px, vis_h), Theme.TEXT_BRIGHT, 1)
                # Diamond head
                pts = np.array([[px-7, ruler_h], [px+7, ruler_h],
                                [px+7, ruler_h+6], [px, ruler_h+14],
                                [px-7, ruler_h+6]], np.int32)
                cv2.fillPoly(strip, [pts], Theme.ACCENT)
                cv2.polylines(strip, [pts], True, Theme.TEXT_BRIGHT, 1)

        return strip

    # ------------------------------------------------------------------
    # DRAW — Toolbar
    # ------------------------------------------------------------------
    def _draw_toolbar(self, canvas):
        x1, y1, x2, y2 = self.layout["toolbar"]
        th = y2 - y1

        # Background with subtle bottom gradient
        cv2.rectangle(canvas, (x1, y1), (x2, y2), Theme.PANEL, -1)
        # Thin accent separator line at bottom
        cv2.line(canvas, (x1, y2 - 1), (x2, y2 - 1), Theme.BORDER, 1)
        # Very thin gold top highlight
        cv2.line(canvas, (x1, y1), (x2, y1), Theme.BORDER, 1)

        # Vertical center
        mid_y = y1 + th // 2

        # ── KUT logo ───────────────────────────────────────────────
        logo_lbl = "KUT"
        logo_w   = UI.text_w(logo_lbl, 0.55, 2)
        logo_x   = 14
        logo_y   = mid_y + 7
        # Draw logo gold bar left of text
        cv2.rectangle(canvas, (logo_x, mid_y - 10), (logo_x + 3, mid_y + 10), Theme.ACCENT, -1)
        UI.text(canvas, logo_lbl, (logo_x + 8, logo_y), 0.55, Theme.ACCENT, 2, shadow=True)

        # ── Buttons ───────────────────────────────────────────────
        bh   = 34
        by0  = mid_y - bh // 2
        by1  = by0 + bh
        bx   = logo_x + logo_w + 22

        btn_defs = [("import", "Import", 72), ("export", "Export", 72)]
        self._toolbar_btns = []

        for bid, lbl, bw in btn_defs:
            rect = (bx, by0, bx + bw, by1)
            UI.button(canvas, rect, lbl, hovered=(self._hover_id == bid))
            self._toolbar_btns.append({"id": bid, "rect": rect})
            bx += bw + 8

        # Vertical separator
        cv2.line(canvas, (bx + 4, mid_y - 10), (bx + 4, mid_y + 10), Theme.BORDER, 1)
        bx += 16

        # Play / Pause circular button
        play_r = bh // 2
        play_cx = bx + play_r
        play_cy = mid_y
        is_playing = self.is_playing
        pcol = Theme.ACCENT if is_playing else Theme.PANEL_ALT
        pbdr = Theme.ACCENT if is_playing else Theme.BORDER
        cv2.circle(canvas, (play_cx, play_cy), play_r, pcol, -1)
        cv2.circle(canvas, (play_cx, play_cy), play_r, pbdr, 1)
        UI.play_icon(canvas, (play_cx, play_cy), is_playing,
                     color=Theme.PANEL_DARK if is_playing else Theme.TEXT_BRIGHT)
        prect = (play_cx - play_r, play_cy - play_r, play_cx + play_r, play_cy + play_r)
        self._toolbar_btns.append({"id": "play", "rect": prect})
        bx += play_r * 2 + 8

        # ── Right-side info (Timecode, zoom, resolution, name) ──────────
        total  = self.get_total_frames()
        tc_end = self._tc(max(0, total - 1), self.master_fps)
        if getattr(self, "_edit_timecode_mode", False):
            tc_str = "".join(getattr(self, "_tc_edit_chars", list("00:00:00:00")))
        else:
            tc_str = self._tc(self.current_idx, self.master_fps)
        full_tc  = f"{tc_str}  /  {tc_end}"
        zoom_str = f"{self._tl_zoom:.1f}x"
        fps_str  = f"{self.master_w}×{self.master_h}  {self.master_fps:.0f}fps"
        name     = os.path.basename(self.current_video_path or "") or "Untitled"

        # Build items right-to-left
        cx = x2 - 14
        tc_scale = 0.44

        # Dirty dot
        if self.is_dirty:
            cv2.circle(canvas, (cx - 4, mid_y), 4, Theme.DANGER, -1)
            cx -= 14

        items = [
            (name,     0.35, Theme.TEXT),
            (fps_str,  0.32, Theme.TEXT_DIM),
            (zoom_str, 0.32, Theme.TEXT_DIM),
        ]
        for lbl, sc, col in items:
            tw = UI.text_w(lbl, sc)
            cx -= tw
            ty = mid_y + UI.text_h(sc) // 2
            UI.text(canvas, lbl, (cx, ty), sc, col, shadow=False)
            cx -= 6
            # separator dot
            cv2.circle(canvas, (cx - 4, mid_y), 2, Theme.BORDER, -1)
            cx -= 14

        # Timecode — styled box
        tc_tw = UI.text_w("00:00:00:00", tc_scale)
        sep_tw = UI.text_w("  /  ", tc_scale)
        tc_box_w = tc_tw * 2 + sep_tw + 24
        tc_box_h = bh
        tc_bx1 = cx - tc_box_w
        tc_bx2 = cx
        tc_by1 = mid_y - tc_box_h // 2
        tc_by2 = tc_by1 + tc_box_h
        self._tc_rect = (tc_bx1, tc_by1, tc_bx2, tc_by2)

        # Box bg (highlight when editing)
        box_fill = Theme.ACCENT_DARK if getattr(self, "_edit_timecode_mode", False) else Theme.PANEL_DARK
        box_bdr  = Theme.ACCENT if getattr(self, "_edit_timecode_mode", False) else Theme.BORDER
        UI.rounded_rect(canvas, (tc_bx1, tc_by1), (tc_bx2, tc_by2), box_fill,
                        radius=5, border_color=box_bdr)

        # Timecode text centred in box
        full_tc_w = UI.text_w(full_tc, tc_scale)
        tc_tx = tc_bx1 + (tc_box_w - full_tc_w) // 2
        tc_ty = mid_y + UI.text_h(tc_scale) // 2
        col_tc = Theme.ACCENT if not getattr(self, "_edit_timecode_mode", False) else Theme.TEXT_BRIGHT
        UI.text(canvas, full_tc, (tc_tx, tc_ty), tc_scale, col_tc, shadow=False)

        # Store exact hit rect for the editable timecode part
        self._tc_hit_rect = (tc_tx, tc_by1, tc_tx + tc_tw, tc_by2)

        # Underline active field when editing
        if getattr(self, "_edit_timecode_mode", False):
            field      = getattr(self, "_tc_edit_field", 0)
            chars      = getattr(self, "_tc_edit_chars", list("00:00:00:00"))
            prefix     = "".join(chars[:field * 3])
            pre_w      = UI.text_w(prefix, tc_scale)
            field_w    = UI.text_w("00", tc_scale)
            ul_x1 = tc_tx + pre_w
            ul_x2 = ul_x1 + field_w
            cv2.line(canvas, (ul_x1, tc_ty + 3), (ul_x2, tc_ty + 3), Theme.ACCENT, 2)


    def _hit_toolbar(self, x, y):
        for b in getattr(self, "_toolbar_btns", []):
            r = b["rect"]
            if r[0] <= x <= r[2] and r[1] <= y <= r[3]: return b["id"]
        return None

    # ------------------------------------------------------------------
    # DRAW — Footer
    # ------------------------------------------------------------------
    def _draw_footer(self, canvas):
        x1, y1, x2, y2 = self.layout["footer"]
        fh = y2 - y1
        cv2.rectangle(canvas, (x1, y1), (x2, y2), Theme.RULER_BG, -1)
        cv2.line(canvas, (x1, y1), (x2, y1), Theme.BORDER, 1)

        hints = [
            ("Space", "Play"), ("S", "Split"), ("Del", "Delete"),
            ("C/V",   "Copy/Paste"), ("F", "Fit"), ("H", "Help"),
            ("Ctrl+Z", "Undo"), ("Ctrl+Y", "Redo"),
        ]
        cx  = 10
        mid = y1 + fh // 2 + 5
        for key, desc in hints:
            # Key badge
            kw = UI.text_w(key, 0.27)
            bw = kw + 8
            bh2 = fh - 8
            bx1 = cx
            bx2 = cx + bw
            by1 = y1 + 4
            by2 = by1 + bh2
            UI.rounded_rect(canvas, (bx1, by1), (bx2, by2), Theme.PANEL_ALT,
                            radius=2, border_color=Theme.BORDER)
            UI.text(canvas, key, (bx1 + 4, by2 - 4), 0.27, Theme.ACCENT, shadow=False)
            cx = bx2 + 4
            # Description
            UI.text(canvas, desc, (cx, mid), 0.27, Theme.TEXT_DIM, shadow=False)
            cx += UI.text_w(desc, 0.27) + 14

        # Status message (right-aligned, accent)
        if self.status_msg:
            sw  = UI.text_w(self.status_msg, 0.32)
            dot_x = x2 - sw - 26
            cv2.circle(canvas, (dot_x, mid - 2), 3, Theme.ACCENT, -1)
            UI.text(canvas, self.status_msg, (dot_x + 10, mid), 0.32, Theme.ACCENT, shadow=False)


    # ------------------------------------------------------------------
    # DRAW — Help overlay
    # ------------------------------------------------------------------
    def _draw_help(self, canvas):
        ow, oh = 520, 380
        ox = (self.canvas_w - ow) // 2
        oy = (self.canvas_h - oh) // 2
        overlay = canvas[oy:oy+oh, ox:ox+ow].copy()
        cv2.addWeighted(overlay, 0.15, np.zeros_like(overlay), 0.85, 0, overlay)
        canvas[oy:oy+oh, ox:ox+ow] = overlay
        UI.rounded_rect(canvas, (ox, oy), (ox+ow, oy+oh), Theme.PANEL, radius=8,
                         border_color=Theme.BORDER_HI, border_thick=2)
        UI.text(canvas, "KEYBOARD SHORTCUTS", (ox+20, oy+28), 0.55, Theme.ACCENT)
        cv2.line(canvas, (ox+10, oy+38), (ox+ow-10, oy+38), Theme.BORDER, 1)
        rows = [
            ("Space",       "Play / Pause"),
            ("Left / Right","Step one frame"),
            ("A / D",       "Step one frame (alt)"),
            ("Home / End",  "Jump to start / end"),
            ("S",           "Split clip at playhead"),
            ("X",           "Delete current clip"),
            ("C",           "Copy current clip"),
            ("V",           "Paste clip"),
            ("G",           "Go to timecode / frame"),
            ("F",           "Zoom to fit timeline"),
            ("H",           "Toggle this help"),
            ("Ctrl+Z",      "Undo"),
            ("Ctrl+Y",      "Redo"),
            ("Ctrl+O",      "Open file"),
            ("Ctrl+I",      "Import & append"),
            ("Ctrl+E",      "Export sequence"),
            ("Mouse Wheel", "Pan timeline"),
            ("Ctrl+Wheel",  "Zoom timeline"),
            ("Esc",     "Quit"),
        ]
        col1x, col2x = ox+20, ox+200
        ry = oy + 56
        for k, d in rows:
            UI.text(canvas, k, (col1x, ry), 0.35, Theme.ACCENT, shadow=False)
            UI.text(canvas, d, (col2x, ry), 0.35, Theme.TEXT,   shadow=False)
            ry += 17
            if ry > oy+oh-20: break
        UI.text(canvas, "Press H to close", (ox+ow-180, oy+oh-12), 0.3, Theme.TEXT_DIM, shadow=False)

    # ------------------------------------------------------------------
    # DRAW — Scissor
    # ------------------------------------------------------------------
    def _draw_scissors_cursor(self, canvas):
        if self._scissors_x is None: return
        tl_x1, tl_y1, tl_x2, tl_y2 = self.layout["timeline"]
        if not (tl_x1 <= self._scissors_x <= tl_x2): return
        sx = self._scissors_x
        sy = tl_y1 - 12
        UI.draw_scissors(canvas, sx, sy, size=12, color=Theme.SCISSORS)
        for yy in range(tl_y1, tl_y2, 6):
            cv2.line(canvas, (sx, yy), (sx, min(yy+3, tl_y2)), (180, 140, 30), 1)

    # ------------------------------------------------------------------
    # RENDER
    # ------------------------------------------------------------------
    def render(self):
        try:
            r = cv2.getWindowImageRect(self.win_name)
            if r and r[2] > 400 and r[3] > 300:
                if r[2] != self.canvas_w or r[3] != self.canvas_h:
                    self.canvas_w, self.canvas_h = r[2], r[3]
                    self._recalc_layout()
                    self._tl_dirty = True
                    self._viewport_idx = None
        except Exception: pass

        canvas = np.full((self.canvas_h, self.canvas_w, 3), Theme.BG, dtype=np.uint8)

        self._draw_toolbar(canvas)
        self._draw_left_panel(canvas)
        self._draw_right_panel(canvas)
        self._draw_viewport(canvas)   # <-- new method

        if self._tl_dirty or self._tl_cache is None:
            self._rebuild_clip_index()
            self._tl_cache = self._build_timeline()
            self._tl_dirty = False
        tl_x1, tl_y1, tl_x2, tl_y2 = self.layout["timeline"]
        th = tl_y2 - tl_y1; tw = tl_x2 - tl_x1
        canvas[tl_y1:tl_y1+th, tl_x1:tl_x1+tw] = self._tl_cache[:th, :tw]
        cv2.rectangle(canvas, (tl_x1, tl_y1), (tl_x2, tl_y2), Theme.BORDER, 1)

        self._draw_scissors_cursor(canvas)
        self._draw_footer(canvas)

        if self._show_help:
            self._draw_help(canvas)

        if getattr(self, "_is_dragging_file", False) and getattr(self, "_drag_file_dict", None):
            fdict = self._drag_file_dict
            label = fdict["label"]
            path  = fdict.get("path", "")
            mx, my = getattr(self, "_mouse_x", 0), getattr(self, "_mouse_y", 0)

            # Highlight timeline drop zone
            tl_x1, tl_y1, tl_x2, tl_y2 = self.layout["timeline"]
            cv2.rectangle(canvas, (tl_x1, tl_y1), (tl_x2, tl_y2), Theme.BORDER_ACT, 2)

            # Drag card
            card_w, card_h = 190, 68
            cx0 = mx + 14
            cy0 = my + 10
            cx1e = cx0 + card_w
            cy1e = cy0 + card_h
            # Clamp to canvas
            if cx1e > self.canvas_w: cx0 = self.canvas_w - card_w - 4; cx1e = cx0 + card_w
            if cy1e > self.canvas_h: cy0 = self.canvas_h - card_h - 4; cy1e = cy0 + card_h

            UI.rounded_rect(canvas, (cx0, cy0), (cx1e, cy1e), Theme.PANEL_ALT,
                            radius=8, border_color=Theme.BORDER_ACT, border_thick=2)

            # Thumbnail in card
            thumb = self._file_thumbs.get(path)
            th_w, th_h = 100, card_h - 12
            if thumb is not None:
                try:
                    t_fit = cv2.resize(thumb, (th_w, th_h), interpolation=cv2.INTER_AREA)
                    p_x1 = max(0, cx0 + 6); p_x2 = min(canvas.shape[1], cx0 + 6 + th_w)
                    p_y1 = max(0, cy0 + 6); p_y2 = min(canvas.shape[0], cy0 + 6 + th_h)
                    s_x1 = p_x1 - (cx0 + 6); s_x2 = s_x1 + (p_x2 - p_x1)
                    s_y1 = p_y1 - (cy0 + 6); s_y2 = s_y1 + (p_y2 - p_y1)
                    if p_x2 > p_x1 and p_y2 > p_y1:
                        canvas[p_y1:p_y2, p_x1:p_x2] = t_fit[s_y1:s_y2, s_x1:s_x2]
                except Exception:
                    pass

            # Label
            lw = UI.text_w(label, 0.32)
            tx = cx0 + th_w + 12
            ty = cy0 + card_h // 2 + 5
            UI.text(canvas, label, (tx, ty), 0.32, Theme.TEXT_BRIGHT, shadow=True)
            # Sub label
            sub = "Drop on timeline"
            UI.text(canvas, sub, (tx, ty + 18), 0.27, Theme.ACCENT, shadow=False)

        cv2.imshow(self.win_name, canvas)

    # ------------------------------------------------------------------
    # MOUSE
    # ------------------------------------------------------------------
    def _in_region(self, x, y, key):
        r = self.layout[key]
        return r[0] <= x <= r[2] and r[1] <= y <= r[3]

    def _mouse_cb(self, event, x, y, flags, param):
        tl_x1, tl_y1, tl_x2, tl_y2 = self.layout["timeline"]
        vx1, vy1, vx2, vy2          = self.layout["viewport"]

        if event == cv2.EVENT_LBUTTONDBLCLK:
            lx1, ly1, lx2, ly2 = self.layout["left"]
            if lx1 <= x <= lx2 and ly1 <= y <= ly2:
                for fi, fdict in enumerate(self._imported_files):
                    rx1, ry1, rx2, ry2 = fdict.get("rect", (0,0,0,0))
                    if rx1 <= x <= rx2 and ry1 <= y <= ry2:
                        if not self._safe_exit(): return
                        src = fdict["source"]
                        lbl = fdict["label"]
                        resize_to = (self.master_w, self.master_h) if (src.width, src.height) != (self.master_w, self.master_h) else None
                        self.clips = [Clip(src, 0, src.frame_count, label=lbl, resize_to=resize_to)]
                        self.current_idx = 0
                        self._mark_edit(push_undo=True)
                        self._viewport_idx = None
                        return

        elif event == cv2.EVENT_LBUTTONDOWN:
            # Toolbar
            if y < self.layout["toolbar"][3]:
                bid = self._hit_toolbar(x, y)
                if bid == "import": self._execute_import()
                elif bid == "export": self._execute_export()
                elif bid == "play":   self.is_playing = not self.is_playing
                
                if hasattr(self, "_tc_hit_rect"):
                    tx1, ty1, tx2, ty2 = self._tc_hit_rect
                    if tx1 <= x <= tx2 and ty1 <= y <= ty2:
                        self._edit_timecode_mode = True
                        self._tc_edit_chars = list(self._tc(self.current_idx, self.master_fps).split()[0])
                        total_w = tx2 - tx1
                        char_w = total_w / 11.0
                        idx = int((x - tx1) / char_w)
                        if idx < 2: self._tc_edit_field = 0
                        elif idx < 5: self._tc_edit_field = 1
                        elif idx < 8: self._tc_edit_field = 2
                        else: self._tc_edit_field = 3
                        self._tc_type_buf = ""

                    else:
                        self._edit_timecode_mode = False
                return
            else:
                self._edit_timecode_mode = False

            # Crop / Blur icons
            if hasattr(self, "_crop_btn_rect"):
                cx1, cy1, cx2, cy2 = self._crop_btn_rect
                if cx1 <= x <= cx2 and cy1 <= y <= cy2:
                    self._crop_mode = not getattr(self, "_crop_mode", False)
                    if self._crop_mode: self._blur_mode = False
                    return
            if hasattr(self, "_blur_btn_rect"):
                bx1, by1, bx2, by2 = self._blur_btn_rect
                if bx1 <= x <= bx2 and by1 <= y <= by2:
                    self._blur_mode = not getattr(self, "_blur_mode", False)
                    if self._blur_mode: self._crop_mode = False
                    return

            # Left panel clicks
            lx1, ly1, lx2, ly2 = self.layout["left"]
            if lx1 <= x <= lx2 and ly1 <= y <= ly2:
                for fi, fdict in enumerate(self._imported_files):
                    dx1, dy1, dx2, dy2 = fdict.get("del_rect", (0,0,0,0))
                    if dx1 <= x <= dx2 and dy1 <= y <= dy2:
                        self._save_state()
                        deleted_fdict = self._imported_files.pop(fi)
                        src_to_remove = deleted_fdict["source"]
                        self.clips = [c for c in self.clips if c.source != src_to_remove]
                        self._mark_edit(push_undo=False)
                        self._tl_dirty = True
                        return
                    
                    rx1, ry1, rx2, ry2 = fdict.get("rect", (0,0,0,0))
                    if rx1 <= x <= rx2 and ry1 <= y <= ry2:
                        self._is_dragging_file = True
                        self._drag_file_dict = fdict
                        return

            # Right panel click
            rx1, ry1, rx2, ry2 = self.layout["right"]
            if ry1 <= y <= ry2 and rx1 <= x <= rx2:
                for tdict in getattr(self, "_track_rects", []):
                    dx1, dy1, dx2, dy2 = tdict["del_rect"]
                    if dx1 <= x <= dx2 and dy1 <= y <= dy2:
                        idx_to_pop = tdict["idx"]
                        if 0 <= idx_to_pop < len(self.clips):
                            self._save_state()
                            self.clips.pop(idx_to_pop)
                            self._mark_edit(push_undo=False)
                            self._tl_dirty = True
                        return
                    
                    cx1, cy1, cx2, cy2 = tdict["rect"]
                    if cx1 <= x <= cx2 and cy1 <= y <= cy2:
                        self.current_idx = self._clip_offsets[tdict["idx"]]
                        self._tl_dirty = True
                        return
                return

            # Blur controls click
            if getattr(self, "_blur_mode", False) and vy1 <= y <= vy2 and vx1 <= x <= vx2:
                vw = vx2 - vx1
                ctrl_w = 400
                ctrl_x = vx1 + (vw - ctrl_w) // 2
                ctrl_y = vy1 + 10
                
                # Check button clicks
                if ctrl_y + 4 <= y <= ctrl_y + 28:
                    if ctrl_x + 55 <= x <= ctrl_x + 115:
                        self._blur_scope = "track"
                        return
                    elif ctrl_x + 120 <= x <= ctrl_x + 180:
                        self._blur_scope = "video"
                        return
                    elif ctrl_x + 185 <= x <= ctrl_x + 245:
                        self._blur_scope = "global"
                        return
                    elif ctrl_x + 255 <= x <= ctrl_x + 315:
                        self._save_state()
                        _, c, _ = self.get_clip_at_playhead()
                        if self._blur_scope == "track" and c:
                            c.blur_strokes = []
                        elif self._blur_scope == "video" and c:
                            c.source.blur_strokes = []
                        elif self._blur_scope == "global":
                            self.global_blur_strokes = []
                        self._mark_edit(push_undo=False)
                        self._viewport_idx = None
                        return
                
                # Otherwise, start painting blur stroke
                _, c, _ = self.get_clip_at_playhead()
                if c:
                    self._is_painting_blur = True
                    zoom = self._viewport_zoom
                    pan_x, pan_y = self._viewport_pan_x, self._viewport_pan_y
                    zw, zh = int(vw * zoom), int(vh * zoom)
                    cx, cy = vx1 + vw // 2 + int(pan_x), vy1 + vh // 2 + int(pan_y)
                    img_x1, img_y1 = cx - zw // 2, cy - zh // 2
                    
                    nx = (x - img_x1) / max(1, zw)
                    ny = (y - img_y1) / max(1, zh)
                    nx = max(0.0, min(1.0, nx))
                    ny = max(0.0, min(1.0, ny))
                    
                    if c.crop and not getattr(self, "_crop_mode", False):
                        cx1, cy1, cx2, cy2 = c.crop
                        ox = cx1 + nx * (cx2 - cx1)
                        oy = cy1 + ny * (cy2 - cy1)
                        srad = (self._blur_brush_size / max(1, zw)) * (cx2 - cx1)
                    else:
                        ox = nx
                        oy = ny
                        srad = self._blur_brush_size / max(1, zw)
                        
                    if self._blur_scope == "track":
                        c.blur_strokes.append((ox, oy, srad))
                    elif self._blur_scope == "video":
                        c.source.blur_strokes.append((ox, oy, srad))
                    elif self._blur_scope == "global":
                        self.global_blur_strokes.append((ox, oy, srad))
                        
                    self._viewport_idx = None
                    return

            # Crop handles click
            if getattr(self, "_crop_mode", False) and vy1 <= y <= vy2 and vx1 <= x <= vx2:
                _, c, _ = self.get_clip_at_playhead()
                if c:
                    crop = getattr(c, "_temp_crop", c.crop or [0.0, 0.0, 1.0, 1.0])
                    vw, vh = vx2 - vx1, vy2 - vy1
                    zoom = self._viewport_zoom
                    pan_x, pan_y = self._viewport_pan_x, self._viewport_pan_y
                    zw, zh = int(vw * zoom), int(vh * zoom)
                    cx, cy = vx1 + vw // 2 + int(pan_x), vy1 + vh // 2 + int(pan_y)
                    img_x1, img_y1 = cx - zw // 2, cy - zh // 2
                    
                    sx1 = img_x1 + int(crop[0] * zw)
                    sy1 = img_y1 + int(crop[1] * zh)
                    sx2 = img_x1 + int(crop[2] * zw)
                    sy2 = img_y1 + int(crop[3] * zh)
                    
                    handles = [(0, sx1, sy1), (1, sx2, sy1), (2, sx1, sy2), (3, sx2, sy2)]
                    for idx, hx, hy in handles:
                        if abs(x - hx) < 12 and abs(y - hy) < 12:
                            self._drag_crop_idx = idx
                            self._is_dragging_crop = True
                            return
                    
                    # If click is inside the crop rect but not on handles, start box pan
                    if max(vx1, sx1) <= x <= min(vx2, sx2) and max(vy1, sy1) <= y <= min(vy2, sy2):
                        self._drag_crop_idx = 4
                        self._is_dragging_crop = True
                        self._drag_crop_start_x = x
                        self._drag_crop_start_y = y
                        self._drag_crop_start_crop = list(crop)
                        return

            # Scissor click
            if (self._scissors_x is not None
                  and tl_x1 <= x <= tl_x2
                  and (tl_y1 - 28) <= y <= tl_y1
                  and abs(x - self._scissors_x) <= 16):
                gf = self._tl_x_to_frame(x)
                self._execute_split_at_frame(gf)
                self._scissors_x = None
                return

            # Viewport click (only if no clips loaded -> treat as open drop zone)
            if vy1 <= y <= vy2 and vx1 <= x <= vx2:
                total = self.get_total_frames()
                if total == 0 or not self.clips:
                    # Check if clicked on a recent file item
                    if hasattr(self, '_recent_rects'):
                        for rx1, ry1, rx2, ry2, fpath in self._recent_rects:
                            if rx1 <= x <= rx2 and ry1 <= y <= ry2:
                                self._open_video_from_path(fpath)
                                self._recent_rects = []  # clear after click
                                return
                    # Otherwise, open file dialog
                    self._execute_import()
                    return
                else:
                    # Viewport with clips -> toggle play
                    if not getattr(self, "_crop_mode", False) and not getattr(self, "_blur_mode", False):
                        self.is_playing = not self.is_playing
                    return

            # Timeline drag
            if tl_y1 <= y <= tl_y2 and tl_x1 <= x <= tl_x2:
                self._is_dragging_tl = True
                on_name_plate = False
                if (tl_y1 + 30) <= y <= (tl_y1 + 44) and self.clips:
                    total  = self.get_total_frames()
                    virt_w = self._tl_total_px()
                    for ci, c in enumerate(self.clips):
                        off = self._clip_offsets[ci]
                        cx1 = int(off / total * virt_w) - self._tl_scroll + tl_x1
                        cx2 = int((off + len(c)) / total * virt_w) - self._tl_scroll + tl_x1
                        if cx1 <= x <= cx2:
                            self._drag_reorder_idx   = ci
                            self._drag_reorder_ghost = ci
                            on_name_plate = True
                            break
                
                if not on_name_plate:
                    gf = self._tl_x_to_frame(x)
                    self.current_idx = gf
                    self._tl_dirty   = True

        elif event == cv2.EVENT_MBUTTONDOWN:
            if tl_y1 <= y <= tl_y2:
                self._is_dragging_mmb   = True
                self._drag_start_x      = x
                self._drag_scroll_start = self._tl_scroll
            elif vy1 <= y <= vy2 and vx1 <= x <= vx2:
                self._is_dragging_vp = True
                self._drag_vp_start_x = x
                self._drag_vp_start_y = y
                self._drag_vp_pan_start_x = self._viewport_pan_x
                self._drag_vp_pan_start_y = self._viewport_pan_y

        elif event == cv2.EVENT_MOUSEMOVE:
            self._mouse_x = x
            self._mouse_y = y

            if self._is_dragging_file:
                try:
                    ctypes.windll.user32.SetCursor(ctypes.windll.user32.LoadCursorW(0, 32649)) # Hand cursor
                except Exception: pass
                return

            if getattr(self, "_is_dragging_crop", False):
                _, c, _ = self.get_clip_at_playhead()
                if c:
                    crop = list(getattr(c, "_temp_crop", c.crop or [0.0, 0.0, 1.0, 1.0]))
                    vw, vh = vx2 - vx1, vy2 - vy1
                    zoom = self._viewport_zoom
                    pan_x, pan_y = self._viewport_pan_x, self._viewport_pan_y
                    zw, zh = int(vw * zoom), int(vh * zoom)
                    cx, cy = vx1 + vw // 2 + int(pan_x), vy1 + vh // 2 + int(pan_y)
                    img_x1, img_y1 = cx - zw // 2, cy - zh // 2
                    
                    nx = (x - img_x1) / max(1, zw)
                    ny = (y - img_y1) / max(1, zh)
                    nx = max(0.0, min(1.0, nx))
                    ny = max(0.0, min(1.0, ny))
                    
                    if self._drag_crop_idx == 0:
                        crop[0] = min(nx, crop[2] - 0.01); crop[1] = min(ny, crop[3] - 0.01)
                    elif self._drag_crop_idx == 1:
                        crop[2] = max(nx, crop[0] + 0.01); crop[1] = min(ny, crop[3] - 0.01)
                    elif self._drag_crop_idx == 2:
                        crop[0] = min(nx, crop[2] - 0.01); crop[3] = max(ny, crop[1] + 0.01)
                    elif self._drag_crop_idx == 3:
                        crop[2] = max(nx, crop[0] + 0.01); crop[3] = max(ny, crop[1] + 0.01)
                    elif self._drag_crop_idx == 4:
                        pdx = x - self._drag_crop_start_x
                        pdy = y - self._drag_crop_start_y
                        dnx = pdx / max(1, zw)
                        dny = pdy / max(1, zh)
                        
                        sc = self._drag_crop_start_crop
                        cw = sc[2] - sc[0]
                        ch = sc[3] - sc[1]
                        
                        nx1 = max(0.0, min(1.0 - cw, sc[0] + dnx))
                        ny1 = max(0.0, min(1.0 - ch, sc[1] + dny))
                        
                        crop[0] = nx1
                        crop[1] = ny1
                        crop[2] = nx1 + cw
                        crop[3] = ny1 + ch
                        
                    c._temp_crop = crop
                    return

            if getattr(self, "_is_painting_blur", False):
                _, c, _ = self.get_clip_at_playhead()
                if c:
                    vw, vh = vx2 - vx1, vy2 - vy1
                    zoom = self._viewport_zoom
                    pan_x, pan_y = self._viewport_pan_x, self._viewport_pan_y
                    zw, zh = int(vw * zoom), int(vh * zoom)
                    cx, cy = vx1 + vw // 2 + int(pan_x), vy1 + vh // 2 + int(pan_y)
                    img_x1, img_y1 = cx - zw // 2, cy - zh // 2
                    
                    nx = (x - img_x1) / max(1, zw)
                    ny = (y - img_y1) / max(1, zh)
                    nx = max(0.0, min(1.0, nx))
                    ny = max(0.0, min(1.0, ny))
                    
                    if c.crop and not getattr(self, "_crop_mode", False):
                        cx1, cy1, cx2, cy2 = c.crop
                        ox = cx1 + nx * (cx2 - cx1)
                        oy = cy1 + ny * (cy2 - cy1)
                        srad = (self._blur_brush_size / max(1, zw)) * (cx2 - cx1)
                    else:
                        ox = nx
                        oy = ny
                        srad = self._blur_brush_size / max(1, zw)
                        
                    if self._blur_scope == "track":
                        c.blur_strokes.append((ox, oy, srad))
                    elif self._blur_scope == "video":
                        c.source.blur_strokes.append((ox, oy, srad))
                    elif self._blur_scope == "global":
                        self.global_blur_strokes.append((ox, oy, srad))
                        
                    self._viewport_idx = None
                    return

            if self._is_dragging_tl:
                if self._drag_reorder_idx is not None and self.clips:
                    total  = self.get_total_frames()
                    virt_w = self._tl_total_px()
                    best_gi = 0
                    best_dx = float("inf")
                    for ci in range(len(self.clips)+1):
                        if ci < len(self.clips):
                            off = self._clip_offsets[ci]
                        else:
                            off = total
                        gx = int(off / total * virt_w) - self._tl_scroll + tl_x1
                        dx = abs(x - gx)
                        if dx < best_dx:
                            best_dx = dx; best_gi = ci
                    self._drag_reorder_ghost = best_gi
                    self._tl_dirty = True
                elif tl_y1 <= y <= tl_y2:
                    gf = self._tl_x_to_frame(x)
                    self.current_idx = gf
                    self._tl_dirty   = True

            elif self._is_dragging_mmb:
                dx = self._drag_start_x - x
                self._tl_scroll = self._drag_scroll_start + dx
                self._clamp_scroll()
                self._tl_dirty = True
                
            elif getattr(self, "_is_dragging_vp", False):
                self._viewport_pan_x = self._drag_vp_pan_start_x + (x - self._drag_vp_start_x)
                self._viewport_pan_y = self._drag_vp_pan_start_y + (y - self._drag_vp_start_y)
                self._viewport_idx = None

            if y < self.layout["toolbar"][3]:
                self._hover_id = self._hit_toolbar(x, y)
            else:
                self._hover_id = None

            if tl_x1 <= x <= tl_x2 and (tl_y1 - 28) <= y <= tl_y2:
                self._scissors_x = x
            else:
                self._scissors_x = None

        elif event == cv2.EVENT_LBUTTONUP:
            if self._is_dragging_file:
                tl_x1, tl_y1, tl_x2, tl_y2 = self.layout["timeline"]
                if tl_x1 <= x <= tl_x2 and tl_y1 <= y <= tl_y2:
                    src = self._drag_file_dict["source"]
                    lbl = self._drag_file_dict["label"]
                    resize_to = (self.master_w, self.master_h) if (src.width, src.height) != (self.master_w, self.master_h) else None
                    new_clip = Clip(src, 0, src.frame_count, label=lbl, resize_to=resize_to)
                    
                    gf = self._tl_x_to_frame(x)
                    c_idx, c, _ = self._get_clip_at_frame(gf)
                    if c is None:
                        self.clips.append(new_clip)
                    else:
                        self.clips.insert(c_idx+1, new_clip)
                    self._mark_edit(push_undo=True)
                    self.current_idx = gf
                self._is_dragging_file = False
                try: ctypes.windll.user32.SetCursor(ctypes.windll.user32.LoadCursorW(0, 32512))
                except Exception: pass

            if getattr(self, "_is_dragging_crop", False):
                self._is_dragging_crop = False
            if getattr(self, "_is_painting_blur", False):
                self._is_painting_blur = False
                self._mark_edit(push_undo=True)
                self._viewport_idx = None
            
            if self._drag_reorder_idx is not None and self._drag_reorder_ghost is not None:
                src = self._drag_reorder_idx
                dst = self._drag_reorder_ghost
                if dst != src and dst != src+1 and 0 <= dst <= len(self.clips):
                    self._save_state()
                    clip = self.clips.pop(src)
                    if dst > src: dst -= 1
                    self.clips.insert(dst, clip)
                    self._mark_edit(push_undo=False)
            self._is_dragging_tl     = False
            self._drag_reorder_idx   = None
            self._drag_reorder_ghost = None

        elif event == cv2.EVENT_MBUTTONUP:
            self._is_dragging_mmb = False
            self._is_dragging_vp = False

        elif event == cv2.EVENT_MOUSEWHEEL or event == 11:
            delta_raw = (flags & 0xFFFF0000) >> 16
            if delta_raw > 32767: delta_raw -= 65536
            up = (delta_raw > 0)
            
            if event == 11: # cv2.EVENT_MOUSEHWHEEL
                right = up
                if tl_y1 <= y <= tl_y2 and tl_x1 <= x <= tl_x2:
                    self._tl_scroll += 60 if right else -60
                    self._clamp_scroll()
                    self._tl_dirty = True
                elif vy1 <= y <= vy2 and vx1 <= x <= vx2:
                    self._viewport_pan_x += -60 if right else 60
                    self._viewport_idx = None
            else:
                if tl_y1 <= y <= tl_y2 and tl_x1 <= x <= tl_x2:
                    if flags & cv2.EVENT_FLAG_CTRLKEY:
                        old_zoom = self._tl_zoom
                        factor   = 1.2 if up else (1/1.2)
                        self._tl_zoom = max(0.1, min(200.0, self._tl_zoom * factor))
                        total  = self.get_total_frames()
                        virt_w_old = max(1, int(total * (tl_x2-tl_x1) / max(1,total) * old_zoom))
                        virt_w_new = self._tl_total_px()
                        ratio  = virt_w_new / max(1, virt_w_old)
                        self._tl_scroll = int((self._tl_scroll + (x-tl_x1)) * ratio - (x-tl_x1))
                    else:
                        self._tl_scroll += -60 if up else 60
                    self._clamp_scroll()
                    self._tl_dirty = True
                elif vy1 <= y <= vy2 and vx1 <= x <= vx2:
                    if flags & cv2.EVENT_FLAG_CTRLKEY:
                        factor = 1.1 if up else (1/1.1)
                        old_zoom = self._viewport_zoom
                        self._viewport_zoom = max(1.0, min(10.0, self._viewport_zoom * factor))
                        
                        if self._viewport_zoom == 1.0:
                            self._viewport_pan_x = 0
                            self._viewport_pan_y = 0
                        else:
                            # Zoom around mouse pointer
                            vw, vh = vx2 - vx1, vy2 - vy1
                            cx, cy = vx1 + vw // 2, vy1 + vh // 2
                            dx = x - (cx + self._viewport_pan_x)
                            dy = y - (cy + self._viewport_pan_y)
                            ratio = self._viewport_zoom / old_zoom
                            self._viewport_pan_x -= dx * (ratio - 1)
                            self._viewport_pan_y -= dy * (ratio - 1)
                        self._viewport_idx = None
                    elif flags & cv2.EVENT_FLAG_SHIFTKEY:
                        self._viewport_pan_x += -60 if up else 60
                        self._viewport_idx = None
                    else:
                        self._viewport_pan_y += -60 if up else 60
                        self._viewport_idx = None

    # ------------------------------------------------------------------
    # KEYBOARD
    # ------------------------------------------------------------------
    def _handle_key(self, key, repeat=1):
        if self._edit_timecode_mode:
            if key in (13, 10): # Enter
                self._edit_timecode_mode = False
                tc_str = "".join(getattr(self, "_tc_edit_chars", list("00:00:00:00")))
                f = self._parse_tc(tc_str)
                if f is not None:
                    self.current_idx = max(0, min(f, self.get_total_frames()-1))
                    self._tl_dirty = True
            elif key == 8: # Backspace
                self._tc_type_buf = ""
                field = getattr(self, "_tc_edit_field", 0)
                if hasattr(self, "_tc_edit_chars"):
                    self._tc_edit_chars[field*3] = "0"
                    self._tc_edit_chars[field*3+1] = "0"
            elif 48 <= key <= 57: # '0'-'9'
                self._tc_type_buf = getattr(self, "_tc_type_buf", "") + chr(key)
                if len(self._tc_type_buf) > 2:
                    self._tc_type_buf = self._tc_type_buf[-2:]
                
                field = getattr(self, "_tc_edit_field", 0)
                val_str = self._tc_type_buf.zfill(2)
                if hasattr(self, "_tc_edit_chars"):
                    self._tc_edit_chars[field*3] = val_str[0]
                    self._tc_edit_chars[field*3+1] = val_str[1]
                
                if len(self._tc_type_buf) == 2:
                    if self._tc_edit_field < 3:
                        self._tc_edit_field += 1
                        self._tc_type_buf = ""
            return

        tot = self.get_total_frames()

        if key in (65361, 2424832, ord("a"), ord("A")):
            self.current_idx = max(0, self.current_idx - repeat)
        elif key in (65363, 2555904, ord("d"), ord("D")):
            self.current_idx = min(max(0, tot-1), self.current_idx + repeat)
        elif key in (65360, 2162688):
            self.current_idx = 0
        elif key in (65367, 2228224):
            self.current_idx = max(0, tot-1)

        elif key == ord(" "):
            self.is_playing = not self.is_playing

        elif key in (ord("s"), ord("S")):
            c_idx, c, local_idx = self.get_clip_at_playhead()
            if c is not None and 0 < local_idx < len(c)-1:
                a, b = c.split(local_idx)
                self._save_state()
                self.clips[c_idx:c_idx+1] = [a, b]
                self._mark_edit(push_undo=False)

        elif key in (3014656, 65535, 127, 8): # Del or Backspace
            c_idx, c, _ = self.get_clip_at_playhead()
            if c is not None and self.clips:
                self._save_state()
                self.clips.pop(c_idx)
                self._mark_edit(push_undo=False)
                self.current_idx = min(self.current_idx, max(0, self.get_total_frames()-1))

        elif key in (ord("c"), ord("C")):
            _, c, _ = self.get_clip_at_playhead()
            if c: self.clipboard = c.clone()

        elif key in (ord("v"), ord("V")) and self.clipboard:
            c_idx, c, local_idx = self.get_clip_at_playhead()
            pasted = self.clipboard.clone()
            ci = next(_clip_color_counter)
            pasted.color = Theme.CLIP_PALETTE[ci % len(Theme.CLIP_PALETTE)]
            pasted.id    = next(_clip_id_counter)
            self._save_state()
            if not self.clips or c is None: self.clips.append(pasted)
            elif local_idx == 0: self.clips.insert(c_idx, pasted)
            else: self.clips.insert(c_idx+1, pasted)
            self._mark_edit(push_undo=False)

        elif key == 26: self.undo()
        elif key == 25: self.redo()

        elif key == 9:  self._execute_import()
        elif key == 5:  self._execute_export()

        elif key in (ord("f"), ord("F")): self.zoom_to_fit()

        elif key == ord("["):
            if getattr(self, "_blur_mode", False):
                self._blur_brush_size = max(5, self._blur_brush_size - 5)
                self._viewport_idx = None
        elif key == ord("]"):
            if getattr(self, "_blur_mode", False):
                self._blur_brush_size = min(200, self._blur_brush_size + 5)
                self._viewport_idx = None

        elif key in (13, 10): # Enter
            if getattr(self, "_crop_mode", False):
                self._crop_mode = False
                _, c, _ = self.get_clip_at_playhead()
                if c and hasattr(c, "_temp_crop"):
                    c.crop = c._temp_crop
                    self._mark_edit(push_undo=True)
                    self._viewport_idx = None
            elif getattr(self, "_blur_mode", False):
                self._blur_mode = False
                self._viewport_idx = None

        elif key in (ord("h"), ord("H")): self._show_help = not self._show_help

        self._tl_dirty = True

    # ------------------------------------------------------------------
    # MAIN LOOP
    # ------------------------------------------------------------------
    def run(self):
        nav_keys = {65361, 2424832, 65363, 2555904, ord("a"), ord("A"), ord("d"), ord("D")}
        while True:
            try:
                if cv2.getWindowProperty(self.win_name, cv2.WND_PROP_VISIBLE) < 1:
                    if self._safe_exit(): break
            except Exception:
                pass
            
            self.render()
            wait_ms = 30 if self.is_playing else 16
            k = cv2.waitKeyEx(wait_ms)

            # if k in (27, ord("q"), ord("Q")):
            #     if k == 27 and (getattr(self, "_crop_mode", False) or getattr(self, "_blur_mode", False)):
            #         self._crop_mode = False
            #         self._blur_mode = False
            #         self._viewport_idx = None
            #     else:
            #         if self._safe_exit(): break

            if k != -1:
                if k in nav_keys:
                    backlog = 1
                    while True:
                        nk = cv2.waitKeyEx(1)
                        if nk == k:   backlog += 1
                        elif nk == -1: break
                        else: k = nk; break
                    self._handle_key(k, repeat=backlog)
                else:
                    self._handle_key(k)

            if self.is_playing and self.get_total_frames() > 0:
                self.current_idx = (self.current_idx + 1) % self.get_total_frames()
                self._tl_dirty = True

        self._worker_active = False
        for s in self._sources: s.release()
        cv2.destroyAllWindows()
        try: self._tk_root.destroy()
        except Exception: pass


# ---------------------------------------------------------------------------
