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
SECTION_BG = (18, 22, 50)       # Slightly lighter section header areas
PANEL_BG = (20, 24, 52)         # Subtle panel background
PANEL_BORDER = (0, 60, 100)     # Panel border color (dim cyan)
DIVIDER_COLOR = (0, 50, 85)     # Very subtle divider below titles

# Section separator Y positions (horizontal full-width lines)
#   Header 0-50 | CPU 50-280 | RAM 280-358 | DISK 358-520 | NET+PING 520-800
SEPARATORS = [50, 280, 358, 520]

# Panel boxes (x1, y1, x2, y2)
CPU1_PANEL = (8, 54, 234, 276)
CPU2_PANEL = (246, 54, 472, 276)
RAM_PANEL = (8, 284, 472, 354)
DISK_PANEL = (8, 362, 472, 516)
NET_PING_PANEL = (8, 524, 472, 796)


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
    for panel in [CPU1_PANEL, CPU2_PANEL, RAM_PANEL, DISK_PANEL, NET_PING_PANEL]:
        draw_rounded_rect(draw, panel, radius=8, fill=PANEL_BG, outline=PANEL_BORDER)

    # Sub-label dividers (inside panels, below titles)
    for x1, y, x2 in [
        (22, 81, 220),     # CPU1 title divider
        (260, 81, 458),    # CPU2 title divider
        (22, 308, 458),    # RAM title divider
        (22, 388, 458),    # DISK title divider
        (22, 548, 458),    # NET title divider
    ]:
        draw.line([(x1, y), (x2, y)], fill=DIVIDER_COLOR, width=1)

    # DISK internal vertical divider (between R and W columns)
    draw.line([(240, 434), (240, 510)], fill=ACCENT_DIM, width=1)

    # NET+PING internal dividers
    # Vertical between UP and DL columns
    draw.line([(240, 554), (240, 658)], fill=ACCENT_DIM, width=1)
    # Horizontal between NET and PING
    glow = tuple(max(0, c // 3) for c in ACCENT_DIM)
    draw.line([(22, 666), (458, 666)], fill=ACCENT_DIM, width=1)
    draw.line([(22, 667), (458, 667)], fill=glow, width=1)

    # Draw horizontal full-width separator lines
    for sy in SEPARATORS:
        draw.line([(8, sy), (WIDTH - 8, sy)], fill=ACCENT_DIM, width=1)
        draw.line([(8, sy + 1), (WIDTH - 8, sy + 1)], fill=glow, width=1)

    # Save
    import os
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "background.png")
    img.save(out_path, "PNG")
    print(f"Background saved to {out_path}")


if __name__ == "__main__":
    generate()
