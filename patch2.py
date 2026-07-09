import os

path = r'c:\Users\Disrupt\Desktop\Siddiq\kut-editor\src\kut\editor.py'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

# 1. _execute_export
c = c.replace(
    'self.status_msg = "Export Completed"\n                self.status_color = (0, 255, 0)\n                def clear_status():',
    'self.status_msg = f"Export Completed: {total} frames"\n                self.status_color = (0, 255, 0)\n                def clear_status():'
)
c = c.replace(
    'self.status_msg = "Export Completed"\n                self.status_color = (0, 255, 0)\n                def clear_status_frames():',
    'self.status_msg = f"Export Completed: {len(frames_to_export)} frames"\n                self.status_color = (0, 255, 0)\n                def clear_status_frames():'
)

# 2. _execute_export_single
c = c.replace(
    'writer.release()\n                self._show_temp_status("Export Completed", (0, 255, 0))',
    'writer.release()\n                self._show_temp_status(f"Export Completed: {len(clip)} frames", (0, 255, 0))'
)
c = c.replace(
    'self.render(); cv2.waitKey(1)\n                self._show_temp_status("Export Completed", (0, 255, 0))',
    'self.render(); cv2.waitKey(1)\n                self._show_temp_status(f"Export Completed: {len(frames_to_export)} frames", (0, 255, 0))'
)

# 3. _execute_batch_export
# Initialize variable
c = c.replace(
    'self._is_exporting = True\n        try:\n            for c_idx, clip in enumerate(clips):',
    'self._is_exporting = True\n        total_exported_frames = 0\n        try:\n            for c_idx, clip in enumerate(clips):'
)
# add len(clip)
c = c.replace(
    'writer.release()\n                elif choice == "frames":',
    'writer.release()\n                        total_exported_frames += len(clip)\n                elif choice == "frames":'
)
# add len(frames_to_export)
c = c.replace(
    'self.render(); cv2.waitKey(1)\n            self._show_temp_status("Batch Export Completed", (0, 255, 0))',
    'self.render(); cv2.waitKey(1)\n                    total_exported_frames += len(frames_to_export)\n            self._show_temp_status(f"Batch Export Completed: {total_exported_frames} frames", (0, 255, 0))'
)


with open(path, 'w', encoding='utf-8') as f:
    f.write(c)

print("Patch applied for export status messages.")
