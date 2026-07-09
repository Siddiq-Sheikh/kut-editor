import cv2
import numpy as np
from .config import Theme

# UI helpers
# ---------------------------------------------------------------------------
class UI:
    @staticmethod
    def text(img, s, pos, scale=0.42, color=Theme.TEXT, thick=1, shadow=True):
        x, y = pos
        if shadow:
            cv2.putText(img, s, (x+1, y+1), cv2.FONT_HERSHEY_SIMPLEX, scale,
                        (4, 4, 6), thick + 1, cv2.LINE_AA)
        cv2.putText(img, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)

    @staticmethod
    def text_w(s, scale=0.42, thick=1):
        return cv2.getTextSize(s, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)[0][0]

    @staticmethod
    def text_h(scale=0.42, thick=1):
        return cv2.getTextSize("Ag", cv2.FONT_HERSHEY_SIMPLEX, scale, thick)[0][1]

    @staticmethod
    def rounded_rect(img, p1, p2, color, radius=6, border_color=None, border_thick=1):
        x1, y1 = p1; x2, y2 = p2
        if x2 <= x1 or y2 <= y1: return
        radius = max(0, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
        
        # Base fill
        cv2.rectangle(img, (x1 + radius, y1), (x2 - radius, y2), color, -1)
        cv2.rectangle(img, (x1, y1 + radius), (x2, y2 - radius), color, -1)
        for cx, cy in ((x1+radius, y1+radius), (x2-radius, y1+radius),
                       (x1+radius, y2-radius), (x2-radius, y2-radius)):
            cv2.circle(img, (cx, cy), radius, color, -1)
            
        # Subtle 3D Top Highlight
        highlight = tuple(min(255, c + 15) for c in color)
        cv2.line(img, (x1 + radius, y1), (x2 - radius, y1), highlight, 1)
        
        # Subtle 3D Bottom Shadow
        shadow = tuple(max(0, c - 15) for c in color)
        cv2.line(img, (x1 + radius, y2), (x2 - radius, y2), shadow, 1)

        if border_color:
            cv2.rectangle(img, (x1, y1), (x2, y2), border_color, border_thick)

    @staticmethod
    def button(img, rect, label, hovered=False, active=False, icon=None):
        x1, y1, x2, y2 = rect
        w, h = x2 - x1, y2 - y1
        if active:
            fill   = Theme.ACCENT_DARK
            border = Theme.ACCENT
        elif hovered:
            fill   = Theme.PANEL_HOVER
            border = Theme.BORDER_HI
        else:
            fill   = Theme.PANEL_ALT
            border = Theme.BORDER
        UI.rounded_rect(img, (x1, y1), (x2, y2), fill, radius=5,
                        border_color=border, border_thick=1)
        if label:
            tw = UI.text_w(label, 0.38, 1)
            th = UI.text_h(0.38)
            cx = x1 + (w - tw) // 2
            cy = y1 + (h + th) // 2
            col = Theme.TEXT_BRIGHT if active else (Theme.TEXT_BRIGHT if hovered else Theme.TEXT)
            UI.text(img, label, (cx, cy), 0.38, col, 1, shadow=False)

    @staticmethod
    def pill_button(img, rect, label, hovered=False, active=False):
        """Rounded pill-shaped button."""
        x1, y1, x2, y2 = rect
        w, h = x2 - x1, y2 - y1
        r = h // 2
        fill   = Theme.ACCENT_DARK if active else (Theme.PANEL_HOVER if hovered else Theme.PANEL_ALT)
        border = Theme.ACCENT if active else (Theme.BORDER_HI if hovered else Theme.BORDER)
        UI.rounded_rect(img, (x1, y1), (x2, y2), fill, radius=r,
                        border_color=border, border_thick=1)
        if label:
            tw = UI.text_w(label, 0.35)
            th = UI.text_h(0.35)
            cx = x1 + (w - tw) // 2
            cy = y1 + (h + th) // 2
            col = Theme.TEXT_BRIGHT if (active or hovered) else Theme.TEXT_DIM
            UI.text(img, label, (cx, cy), 0.35, col, 1, shadow=False)

    @staticmethod
    def section_header(img, x1, y1, x2, label):
        """Draw a panel section header with accent left-bar and muted label."""
        bar_h = 20
        cv2.rectangle(img, (x1, y1), (x2, y1 + bar_h), Theme.PANEL_DARK, -1)
        cv2.line(img, (x1, y1 + bar_h), (x2, y1 + bar_h), Theme.BORDER, 1)
        # Accent left bar
        cv2.rectangle(img, (x1, y1 + 4), (x1 + 2, y1 + bar_h - 4), Theme.ACCENT, -1)
        tw = UI.text_w(label, 0.30)
        ty = y1 + bar_h - 6
        UI.text(img, label, (x1 + 10, ty), 0.30, Theme.TEXT_DIM, 1, shadow=False)
        return y1 + bar_h + 1  # returns y cursor after header

    @staticmethod
    def play_icon(img, center, playing, color=Theme.TEXT_BRIGHT):
        cx, cy = center
        if playing:
            cv2.rectangle(img, (cx - 7, cy - 7), (cx - 2, cy + 7), color, -1)
            cv2.rectangle(img, (cx + 2, cy - 7), (cx + 7, cy + 7), color, -1)
        else:
            pts = np.array([[cx - 6, cy - 8], [cx - 6, cy + 8], [cx + 9, cy]], np.int32)
            cv2.fillPoly(img, [pts], color)

    @staticmethod
    def draw_trash_icon(img, cx, cy, size=10, color=Theme.DANGER):
        """Draw a simple trash-can icon centred at (cx, cy)."""
        hw = size // 2
        hh = size
        # Lid
        cv2.rectangle(img, (cx - hw - 2, cy - hh + 2), (cx + hw + 2, cy - hh + 5), color, -1)
        # Body
        cv2.rectangle(img, (cx - hw, cy - hh + 6), (cx + hw, cy + 2), color, 2)
        # Vertical lines inside body
        cv2.line(img, (cx, cy - hh + 8), (cx, cy), color, 1)
        cv2.line(img, (cx - hw + 3, cy - hh + 8), (cx - hw + 3, cy), color, 1)
        cv2.line(img, (cx + hw - 3, cy - hh + 8), (cx + hw - 3, cy), color, 1)

    @staticmethod
    def draw_scissors(img, cx, cy, size=14, color=Theme.SCISSORS):
        """Draw a downward-pointing scissor icon centred at (cx, cy)."""
        h = size
        cv2.line(img, (cx, cy), (cx - h//3, cy + h), color, 2, cv2.LINE_AA)
        cv2.line(img, (cx, cy), (cx + h//3, cy + h), color, 2, cv2.LINE_AA)
        cv2.circle(img, (cx - h//2, cy - h//2), 4, color, 2, cv2.LINE_AA)
        cv2.circle(img, (cx + h//2, cy - h//2), 4, color, 2, cv2.LINE_AA)
        cv2.line(img, (cx - h//2 + 2, cy - h//2 + 2), (cx, cy), color, 2, cv2.LINE_AA)
        cv2.line(img, (cx + h//2 - 2, cy - h//2 + 2), (cx, cy), color, 2, cv2.LINE_AA)
        cv2.circle(img, (cx, cy), 2, color, -1)

    @staticmethod
    def draw_panel_bg(img, x1, y1, x2, y2, color=None):
        """Draw a subtle panel background with border."""
        c = color or Theme.PANEL
        cv2.rectangle(img, (x1, y1), (x2, y2), c, -1)
        cv2.rectangle(img, (x1, y1), (x2, y2), Theme.BORDER, 1)

    @staticmethod
    def vline(img, x, y1, y2, color=None):
        cv2.line(img, (x, y1), (x, y2), color or Theme.BORDER, 1)

    @staticmethod
    def hline(img, x1, y, x2, color=None):
        cv2.line(img, (x1, y), (x2, y), color or Theme.BORDER, 1)

# ---------------------------------------------------------------------------
