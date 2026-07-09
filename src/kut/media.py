import threading
import itertools
import cv2
import numpy as np
from collections import OrderedDict
from .config import Theme

# VIDEO SOURCE
# ---------------------------------------------------------------------------
class VideoSource:
    CACHE_SIZE = 128

    def __init__(self, path):
        self.path = path
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise IOError(f"Cannot open: {path}")
        self.width  = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        raw_fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.fps = float(raw_fps) if raw_fps and raw_fps > 0 and not np.isnan(raw_fps) else 25.0
        count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.frame_count = count if count > 0 else 10000
        self._next_read_idx = 0
        self._cache = OrderedDict()
        self._lock = threading.Lock()
        self._blank_frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        self._thumb_cap = None
        self._thumb_lock = threading.Lock()
        self._thumb_next_idx = -1
        self.blur_strokes = []

    def _push_cache(self, idx, frame):
        self._cache[idx] = frame
        if len(self._cache) > self.CACHE_SIZE:
            self._cache.popitem(last=False)

    def get_frame(self, idx):
        idx = max(0, min(idx, self.frame_count-1))
        with self._lock:
            if idx in self._cache:
                self._cache.move_to_end(idx); return self._cache[idx]
            delta = idx - self._next_read_idx
            if 0 <= delta <= 12:
                for _ in range(delta): self.cap.read()
                ok, frame = self.cap.read()
                self._next_read_idx = idx+1
                res = frame if (ok and frame is not None) else self._blank_frame
                self._push_cache(idx, res); return res
            if idx < self._next_read_idx:
                chunk_start = max(0, idx-30)
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, chunk_start)
                for i in range(chunk_start, idx+1):
                    ok, f = self.cap.read()
                    if ok and f is not None: self._push_cache(i, f)
                self._next_read_idx = idx+1
                return self._cache.get(idx, self._blank_frame)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = self.cap.read()
            self._next_read_idx = idx+1
            res = frame if (ok and frame is not None) else self._blank_frame
            self._push_cache(idx, res); return res

    def get_frame_for_thumbnail(self, idx):
        idx = max(0, min(idx, self.frame_count-1))
        with self._thumb_lock:
            if self._thumb_cap is None:
                self._thumb_cap = cv2.VideoCapture(self.path)
            cap = self._thumb_cap
            if idx != self._thumb_next_idx:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            self._thumb_next_idx = idx+1
            return frame if (ok and frame is not None) else self._blank_frame

    def release(self):
        try: self.cap.release()
        except Exception: pass
        try:
            if self._thumb_cap is not None: self._thumb_cap.release()
        except Exception: pass


# ---------------------------------------------------------------------------
# CLIP
# ---------------------------------------------------------------------------
_clip_id_counter = itertools.count(1)
_clip_color_counter = itertools.count(0)


class Clip:
    def __init__(self, source, start, end, label="Clip",
                 resize_to=None, color=None, clip_id=None, crop=None):
        self.source     = source
        self.start      = start
        self.end        = end
        self.label      = label
        self.resize_to  = resize_to
        self.crop       = crop
        if color is not None:
            self.color = color
        else:
            ci = next(_clip_color_counter)
            self.color = Theme.CLIP_PALETTE[ci % len(Theme.CLIP_PALETTE)]
        self.id = clip_id if clip_id is not None else next(_clip_id_counter)
        self.blur_strokes = []

    def __len__(self): return max(0, self.end-self.start)

    def get_frame(self, local_idx, high_quality=False, ignore_crop=False, ignore_blur=False, global_blur_strokes=None):
        frame = self.source.get_frame(self.start+local_idx)
        
        # Apply blur on the original uncropped frame
        if not ignore_blur:
            strokes = []
            if hasattr(self, "blur_strokes") and self.blur_strokes:
                strokes.extend(self.blur_strokes)
            if hasattr(self.source, "blur_strokes") and self.source.blur_strokes:
                strokes.extend(self.source.blur_strokes)
            if global_blur_strokes:
                strokes.extend(global_blur_strokes)
                
            if strokes:
                h, w = frame.shape[:2]
                mask = np.zeros((h, w), dtype=np.uint8)
                for sx, sy, srad in strokes:
                    px = int(sx * w)
                    py = int(sy * h)
                    prad = int(srad * max(w, h))
                    cv2.circle(mask, (px, py), prad, 255, -1)
                
                if np.any(mask > 0):
                    mask_blur_sz = max(5, int(max(w, h) * 0.01) | 1)
                    mask = cv2.GaussianBlur(mask, (mask_blur_sz, mask_blur_sz), 0)
                    
                    frame_blur_sz = max(5, int(max(w, h) * 0.03) | 1)
                    blurred = cv2.GaussianBlur(frame, (frame_blur_sz, frame_blur_sz), 0)
                    
                    mask_3d = np.expand_dims(mask / 255.0, axis=2)
                    frame = (frame * (1.0 - mask_3d) + blurred * mask_3d).astype(np.uint8)

        # Apply crop
        if self.crop and not ignore_crop:
            cx1, cy1, cx2, cy2 = self.crop
            h, w = frame.shape[:2]
            x1, y1 = int(cx1 * w), int(cy1 * h)
            x2, y2 = int(cx2 * w), int(cy2 * h)
            # Ensure safe bounds
            x1, y1 = max(0, min(w, x1)), max(0, min(h, y1))
            x2, y2 = max(0, min(w, x2)), max(0, min(h, y2))
            if y2 > y1 and x2 > x1:
                masked = np.zeros_like(frame)
                masked[y1:y2, x1:x2] = frame[y1:y2, x1:x2]
                frame = masked
        
        if self.resize_to and (frame.shape[1], frame.shape[0]) != self.resize_to:
            mode = cv2.INTER_CUBIC if high_quality else cv2.INTER_NEAREST
            return cv2.resize(frame, self.resize_to, interpolation=mode)
        return frame

    def get_thumbnail_frame(self, local_idx):
        src = self.source
        getter = getattr(src, "get_frame_for_thumbnail", None) or src.get_frame
        return getter(self.start+local_idx)

    def split(self, local_idx):
        # Left child gets parent color, right child gets new color
        col1 = self.color
        ci2 = next(_clip_color_counter)
        col2 = Theme.CLIP_PALETTE[ci2 % len(Theme.CLIP_PALETTE)]

        lbl_a = f"{self.label}_1"
        lbl_b = f"{self.label}_2"

        a = Clip(self.source, self.start, self.start + local_idx,
                lbl_a, self.resize_to, col1, crop=self.crop)
        b = Clip(self.source, self.start + local_idx, self.end,
                lbl_b, self.resize_to, col2, crop=self.crop)
        a.blur_strokes = list(self.blur_strokes)
        b.blur_strokes = list(self.blur_strokes)
        return a, b

    def clone(self):
        c = Clip(self.source, self.start, self.end,
                    self.label, self.resize_to, self.color, clip_id=self.id, crop=self.crop)
        c.blur_strokes = list(self.blur_strokes)
        return c

    def waveform_pattern(self, width, height):
        """Cheap deterministic 'waveform' bar for visual rhythm — seeded by
        clip id so it never changes for the same clip."""
        rng = np.random.RandomState(self.id & 0xFFFF)
        bar = np.zeros((height, width, 3), dtype=np.uint8)
        n_bars = max(1, width // 3)
        bar_w = max(1, width // n_bars)
        base = tuple(max(20, c//3) for c in self.color)
        for i in range(n_bars):
            h_frac = float(rng.rand())
            bh = int(h_frac * height)
            x1 = i * bar_w
            x2 = min(width, x1 + bar_w - 1)
            y1 = height - bh
            if bh > 0:
                cv2.rectangle(bar, (x1, y1), (x2, height), base, -1)
        return bar


# ---------------------------------------------------------------------------
