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
    BG           = (8,   8,   11)    # Deeper, richer black canvas
    PANEL        = (20,  20,  26)    # Primary panel (slightly tinted)
    PANEL_ALT    = (28,  28,  36)    # Lighter panel 
    PANEL_DARK   = (14,  14,  18)    # Darker inset
    PANEL_HOVER  = (40,  40,  50)    # Responsive hover state
    BORDER       = (45,  45,  60)    # Subtle modern border
    BORDER_HI    = (255, 195, 60)    # Vibrant gold accent border
    BORDER_ACT   = (90,  180, 255)   # Vibrant active / blue
    TEXT         = (225, 225, 235)   # Crisp primary text
    TEXT_DIM     = (125, 125, 140)   # Clean secondary text
    TEXT_BRIGHT  = (255, 255, 255)   # Pure white
    ACCENT       = (255, 195, 60)    # Warm, bright gold
    ACCENT_DARK  = (100, 70,  10)    # Deep gold fill
    DANGER       = (240, 75,  75)    # Punchy red
    OK           = (85,  220, 120)   # Vibrant green
    RULER_BG     = (10,  10,  14)    # Timeline ruler base
    PLAYHEAD     = (255, 255, 255)
    GHOST        = (90,  90,  255)
    SCISSORS     = (40,  40,  255)
    SHADOW       = (0,   0,   0)     # Drop shadows

    CLIP_PALETTE = [
        (220, 150,  75),   # Warm amber
        (140, 105, 225),   # Indigo
        ( 80, 195, 125),   # Sage green
        ( 70, 155, 235),   # Sky blue
        (225, 105,  95),   # Coral
        (165, 215,  80),   # Lime
        (215,  95, 175),   # Magenta
        ( 90, 205, 205),   # Teal
        (235, 170,  65),   # Gold
        (105, 135, 225),   # Periwinkle
    ]

# ---------------------------------------------------------------------------
