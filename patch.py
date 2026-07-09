import os

path = r'c:\Users\Disrupt\Desktop\Siddiq\kut-editor\src\kut\editor.py'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Dialog fixes
# askopenfilename
c = c.replace(
    'return filedialog.askopenfilename(\n            parent=self._root()',
    'if getattr(self, "_is_dialog_open", False): return ""\n        self._is_dialog_open = True\n        try:\n            return filedialog.askopenfilename(\n                parent=self._root()'
)
c = c.replace(
    'filetypes=[("Video", "*.mp4 *.avi *.mov *.mkv *.wmv"), ("All", "*.*")])',
    'filetypes=[("Video", "*.mp4 *.avi *.mov *.mkv *.wmv"), ("All", "*.*")])\n        finally:\n            self._is_dialog_open = False'
)

# asksaveasfilename
c = c.replace(
    'return filedialog.asksaveasfilename(\n            parent=self._root()',
    'if getattr(self, "_is_dialog_open", False): return ""\n        self._is_dialog_open = True\n        try:\n            return filedialog.asksaveasfilename(\n                parent=self._root()'
)
c = c.replace(
    'filetypes=[("MP4", "*.mp4"), ("AVI", "*.avi")])',
    'filetypes=[("MP4", "*.mp4"), ("AVI", "*.avi")])\n        finally:\n            self._is_dialog_open = False'
)

# askdirectory and simpledialog are used inside _execute_export, _execute_export_single, _execute_batch_export
# so let's just guard those top level functions!
c = c.replace(
    'def _execute_export(self):\n        # Guard against double-clicking during active export\n        if getattr(self, "_is_exporting", False):\n            return False',
    'def _execute_export(self):\n        if getattr(self, "_is_exporting", False) or getattr(self, "_is_dialog_open", False):\n            return False\n        self._is_dialog_open = True'
)
c = c.replace(
    'self._is_exporting = False',
    'self._is_exporting = False\n            self._is_dialog_open = False'
)

c = c.replace(
    'def _execute_export_single(self, clip):\n        if getattr(self, "_is_exporting", False): return False',
    'def _execute_export_single(self, clip):\n        if getattr(self, "_is_exporting", False) or getattr(self, "_is_dialog_open", False): return False\n        self._is_dialog_open = True'
)
c = c.replace(
    'def _execute_batch_export(self):\n        if getattr(self, "_is_exporting", False): return False',
    'def _execute_batch_export(self):\n        if getattr(self, "_is_exporting", False) or getattr(self, "_is_dialog_open", False): return False\n        self._is_dialog_open = True'
)
c = c.replace(
    'def _execute_clear(self):\n        if getattr(self, "_is_exporting", False): return False',
    'def _execute_clear(self):\n        if getattr(self, "_is_exporting", False) or getattr(self, "_is_dialog_open", False): return False\n        self._is_dialog_open = True'
)

# For ask_radio inside _execute_export:
c = c.replace(
    'def ask_radio(title, prompt, options):\n            import tkinter as tk',
    'def ask_radio(title, prompt, options):\n            self._is_dialog_open = True\n            import tkinter as tk'
)
c = c.replace(
    'root.wait_window(top)\n            return result[0]',
    'root.wait_window(top)\n            self._is_dialog_open = False\n            return result[0]'
)

c = c.replace(
    'def _ask_radio(self, title, prompt, options):\n        import tkinter as tk',
    'def _ask_radio(self, title, prompt, options):\n        self._is_dialog_open = True\n        import tkinter as tk'
)
c = c.replace(
    'root.wait_window(top)\n        return result[0]',
    'root.wait_window(top)\n        self._is_dialog_open = False\n        return result[0]'
)


# 2. Thumbnail width and speed fix
c = c.replace(
    'THUMB_SIZE   = 64',
    'THUMB_SIZE   = 64\n    THUMB_W = 114\n    THUMB_H = 64'
)
c = c.replace(
    'numpy array (THUMB_SIZE, THUMB_SIZE, 3)',
    'numpy array (THUMB_H, THUMB_W, 3)'
)
c = c.replace(
    'self._thumb_queue = queue.Queue(maxsize=1024)',
    'self._thumb_queue = queue.LifoQueue(maxsize=1024)'
)
c = c.replace(
    'thumb = cv2.resize(raw, (self.THUMB_SIZE, self.THUMB_SIZE),\n                                           interpolation=cv2.INTER_NEAREST)',
    'thumb = cv2.resize(raw, (self.THUMB_W, self.THUMB_H),\n                                           interpolation=cv2.INTER_NEAREST)'
)
c = c.replace(
    'thumb = np.zeros((self.THUMB_SIZE, self.THUMB_SIZE, 3), dtype=np.uint8)',
    'thumb = np.zeros((self.THUMB_H, self.THUMB_W, 3), dtype=np.uint8)'
)

# In render timeline we need to replace how thumbs are drawn maybe? Wait, in render timeline:
# `cw = int(dur_s * px_per_s)`
# And thumbnails are repeated based on their size.
c = c.replace(
    't_w, t_h = thumb.shape[1], thumb.shape[0]',
    't_w, t_h = thumb.shape[1], thumb.shape[0]'
)
c = c.replace(
    'th_x = max(0, cx - int(c.start * px_per_s))\n                            while th_x < cw:\n                                UI.paste_image_alpha(canvas, thumb, bx1 + th_x, by1 + 16)',
    'th_x = max(0, cx - int(c.start * px_per_s))\n                            while th_x < cw:\n                                UI.paste_image_alpha(canvas, thumb, bx1 + th_x, by1 + 16)'
)
# We don't have to change render code because it uses thumb.shape[1] dynamically!

# 3. Frames math fix (for FPS)
old_fps = '''if mode == "fps":
                    val = simpledialog.askfloat("FPS", "Enter frames per second to extract:", parent=self._root(), initialvalue=1.0)
                    if not val or val <= 0: return False
                    step = max(1, int(self.master_fps / val))
                    frames_to_export = list(range(0, total, step))
                elif mode == "fixed":
                    val = simpledialog.askinteger("Fixed", "Enter total number of frames to extract:", parent=self._root(), initialvalue=100)
                    if not val or val <= 0: return False
                    step = max(1, total // val)
                    frames_to_export = list(range(0, total, step))[:val]'''

new_fps = '''if mode == "fps":
                    val = simpledialog.askfloat("FPS", "Enter frames per second to extract:", parent=self._root(), initialvalue=1.0)
                    if not val or val <= 0: return False
                    total_dur = total / (self.master_fps or 25.0)
                    val = max(1, int(total_dur * val))
                    frames_to_export = [int(i * (total - 1) / (val - 1)) for i in range(val)] if val > 1 else [0]
                elif mode == "fixed":
                    val = simpledialog.askinteger("Fixed", "Enter total number of frames to extract:", parent=self._root(), initialvalue=100)
                    if not val or val <= 0: return False
                    frames_to_export = [int(i * (total - 1) / (val - 1)) for i in range(val)] if val > 1 else [0]'''

c = c.replace(old_fps, new_fps)

with open(path, 'w', encoding='utf-8') as f:
    f.write(c)
print("Patched editor.py successfully")
