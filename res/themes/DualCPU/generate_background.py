#!/usr/bin/env python3
"""Generate the dark gradient background image for the DualCPU theme.
Run this script once to create background.png in the same directory.
Requires Pillow: pip install Pillow
"""
from PIL import Image, ImageDraw

WIDTH = 480
HEIGHT = 800

# Color palette
COLOR_TOP = (16, 18, 40)        # Dark navy top
COLOR_BOTTOM = (10, 12, 28)     # Slightly darker bottom
ACCENT_DIM = (0, 80, 130)       # Dim cyan accent for separator lines
ACCENT_BRIGHT = (0, 120, 180)   # Brighter cyan for panel borders
SECTION_BG = (18, 22, 50)       # Slightly lighter section header areas
PANEL_BG = (20, 24, 52)         # Subtle panel background
PANEL_BORDER = (0, 60, 100)     # Panel border color (dim cyan)

# Section separator Y positions (horizontal lines)
#   Header 0-50 | CPU 50-290 | RAM+DISK 290-460 | NET 460-620 | PING 620-800
SEPARATORS = [50, 290, 460, 620]

# Vertical divider X position (center of display)
VERT_DIV_X = 240

# Panel boxes (x1, y1, x2, y2) - rounded rect areas
#   CPU 1 panel, CPU 2 panel, RAM panel, DISK panel
CPU1_PANEL = (8, 54, 234, 285)
CPU2_PANEL = (246, 54, 472, 285)
RAM_PANEL = (8, 294, 234, 455)
DISK_PANEL = (246, 294, 472, 455)


def lerp_color(c1, c2, t):
    """Linear interpolation between two RGB colors."""
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def draw_rounded_rect(draw, box, radius, fill, outline):
    """Draw a rounded rectangle."""
    x1, y1, x2, y2 = box
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill, outline=outline)


def generate():
    img = Image.new("RGB", (WIDTH, HEIGHT), COLOR_TOP)
    draw = ImageDraw.Draw(img)

    # Draw vertical gradient background
    for y in range(HEIGHT):
        t = y / HEIGHT
        color = lerp_color(COLOR_TOP, COLOR_BOTTOM, t)
        draw.line([(0, y), (WIDTH, y)], fill=color)

    # Draw subtle header band
    for y in range(0, 50):
        t = y / HEIGHT
        base = lerp_color(COLOR_TOP, COLOR_BOTTOM, t)
        highlight = lerp_color(base, SECTION_BG, 0.4)
        draw.line([(0, y), (WIDTH, y)], fill=highlight)

    # Draw panel boxes with rounded corners
    for panel in [CPU1_PANEL, CPU2_PANEL, RAM_PANEL, DISK_PANEL]:
        draw_rounded_rect(draw, panel, radius=8, fill=PANEL_BG, outline=PANEL_BORDER)

    # Draw horizontal separator lines
    for sy in SEPARATORS:
        draw.line([(8, sy), (WIDTH - 8, sy)], fill=ACCENT_DIM, width=1)
        glow = tuple(max(0, c // 3) for c in ACCENT_DIM)
        draw.line([(8, sy + 1), (WIDTH - 8, sy + 1)], fill=glow, width=1)

    # Save
    import os
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "background.png")
    img.save(out_path, "PNG")
    print(f"Background saved to {out_path}")


if __name__ == "__main__":
    generate()
