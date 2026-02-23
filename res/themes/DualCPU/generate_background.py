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

# Section separator Y positions (horizontal lines)
SEPARATORS = [54, 300, 445, 590]

# Section header band ranges (Y start, Y end) for subtle highlight
HEADER_BANDS = [
    (0, 54),      # Date/Time/Uptime header
]


def lerp_color(c1, c2, t):
    """Linear interpolation between two RGB colors."""
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def generate():
    img = Image.new("RGB", (WIDTH, HEIGHT), COLOR_TOP)
    draw = ImageDraw.Draw(img)

    # Draw vertical gradient background
    for y in range(HEIGHT):
        t = y / HEIGHT
        color = lerp_color(COLOR_TOP, COLOR_BOTTOM, t)
        draw.line([(0, y), (WIDTH, y)], fill=color)

    # Draw subtle header bands
    for y_start, y_end in HEADER_BANDS:
        for y in range(y_start, y_end):
            t = y / HEIGHT
            base = lerp_color(COLOR_TOP, COLOR_BOTTOM, t)
            highlight = lerp_color(base, SECTION_BG, 0.4)
            draw.line([(0, y), (WIDTH, y)], fill=highlight)

    # Draw separator lines
    for sy in SEPARATORS:
        # Main accent line
        draw.line([(8, sy), (WIDTH - 8, sy)], fill=ACCENT_DIM, width=1)
        # Subtle glow line below (dimmer)
        glow = tuple(max(0, c // 3) for c in ACCENT_DIM)
        draw.line([(8, sy + 1), (WIDTH - 8, sy + 1)], fill=glow, width=1)

    # Save
    import os
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "background.png")
    img.save(out_path, "PNG")
    print(f"Background saved to {out_path}")


if __name__ == "__main__":
    generate()
