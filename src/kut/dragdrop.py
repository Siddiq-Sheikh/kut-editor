import ctypes
import ctypes.wintypes
import sys

# Define constants
GWLP_WNDPROC = -4
WM_DROPFILES = 0x0233

# Correctly define types for 64-bit and 32-bit Python to avoid pointer truncation (which causes access violations)
if sys.maxsize > 2**32:
    SetWindowLongPtr = ctypes.windll.user32.SetWindowLongPtrW
    SetWindowLongPtr.argtypes = [ctypes.wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    SetWindowLongPtr.restype = ctypes.c_void_p
    GetWindowLongPtr = ctypes.windll.user32.GetWindowLongPtrW
    GetWindowLongPtr.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
    GetWindowLongPtr.restype = ctypes.c_void_p
else:
    SetWindowLongPtr = ctypes.windll.user32.SetWindowLongW
    SetWindowLongPtr.argtypes = [ctypes.wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    SetWindowLongPtr.restype = ctypes.c_void_p
    GetWindowLongPtr = ctypes.windll.user32.GetWindowLongW
    GetWindowLongPtr.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
    GetWindowLongPtr.restype = ctypes.c_void_p

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.wintypes.HWND, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)
CallWindowProc = ctypes.windll.user32.CallWindowProcW
CallWindowProc.argtypes = [ctypes.c_void_p, ctypes.wintypes.HWND, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
CallWindowProc.restype = ctypes.c_void_p

DragAcceptFiles = ctypes.windll.shell32.DragAcceptFiles
DragAcceptFiles.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.BOOL]

DragQueryFile = ctypes.windll.shell32.DragQueryFileW
DragQueryFile.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
DragQueryFile.restype = ctypes.c_uint

DragFinish = ctypes.windll.shell32.DragFinish
DragFinish.argtypes = [ctypes.c_void_p]

# Keep references to the callbacks so they are not garbage collected
_drop_callbacks = {}
_old_wndprocs = {}
_hooked_hwnds = set()

def hook_dropfiles(hwnd, callback, on_close=None):
    """
    Safely hooks the window procedure to accept file drops (WM_DROPFILES)
    without causing 64-bit access violations.
    """
    if hwnd in _hooked_hwnds:
        return
        
    old_proc = GetWindowLongPtr(hwnd, GWLP_WNDPROC)
    _old_wndprocs[hwnd] = old_proc
    
    def wndproc(hw, msg, wp, lp):
        if msg == 0x0010: # WM_CLOSE
            if on_close is not None:
                try:
                    if not on_close():
                        return 0
                except Exception as e:
                    pass
        if msg == WM_DROPFILES:
            count = DragQueryFile(wp, 0xFFFFFFFF, None, 0)
            files = []
            for i in range(count):
                length = DragQueryFile(wp, i, None, 0)
                buf = ctypes.create_unicode_buffer(length + 1)
                DragQueryFile(wp, i, buf, length + 1)
                files.append(buf.value)
            DragFinish(wp)
            try:
                callback(files)
            except Exception as e:
                print("Error in drop callback:", e)
            return 0
        return CallWindowProc(old_proc, hw, msg, wp, lp)
        
    c_wndproc = WNDPROC(wndproc)
    _drop_callbacks[hwnd] = c_wndproc
    
    DragAcceptFiles(hwnd, True)
    SetWindowLongPtr(hwnd, GWLP_WNDPROC, ctypes.cast(c_wndproc, ctypes.c_void_p))
    _hooked_hwnds.add(hwnd)
