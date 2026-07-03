import os
import sys
import ctypes

# OS-LEVEL HIGH-DPI OVERRIDE
# ---------------------------------------------------------------------------
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
    
# ---------------------------------------------------------------------------
# System Paths
# ---------------------------------------------------------------------------
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_data_dir():
    """Get the directory for saving persistent data (next to the exe)."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        base_dir = os.path.dirname(sys.executable)
    else:
        # Running as script
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

# ---------------------------------------------------------------------------
# THEME
# ---------------------------------------------------------------------------
class Theme:
    BG           = (10,  10,  14)    # near-black canvas
    PANEL        = (18,  18,  24)    # primary panel
    PANEL_ALT    = (26,  26,  34)    # slightly lighter panel
    PANEL_DARK   = (12,  12,  16)    # darker inset
    PANEL_HOVER  = (34,  34,  44)    # hover state
    BORDER       = (42,  42,  56)    # subtle border
    BORDER_HI    = (255, 185, 40)    # gold accent border
    BORDER_ACT   = (80,  170, 255)   # active / blue
    TEXT         = (215, 215, 225)   # primary text
    TEXT_DIM     = (110, 110, 125)   # secondary text
    TEXT_BRIGHT  = (255, 255, 255)   # bright white
    ACCENT       = (255, 185, 40)    # warm gold
    ACCENT_DARK  = (90,  62,  8)     # dark gold fill
    DANGER       = (230, 65,  65)    # red
    OK           = (80,  210, 110)   # green
    RULER_BG     = (8,   8,   12)    # timeline ruler
    PLAYHEAD     = (255, 255, 255)
    GHOST        = (80,  80,  255)
    SCISSORS     = (30,  30,  255)
    SHADOW       = (0,   0,   0)     # drop shadows

    CLIP_PALETTE = [
        (210, 140,  70),   # warm amber
        (130,  95, 215),   # indigo
        ( 70, 185, 115),   # sage green
        ( 60, 145, 225),   # sky blue
        (215,  95,  85),   # coral
        (155, 205,  70),   # lime
        (205,  85, 165),   # magenta
        ( 80, 195, 195),   # teal
        (225, 160,  55),   # gold
        ( 95, 125, 215),   # periwinkle
    ]

# ---------------------------------------------------------------------------
