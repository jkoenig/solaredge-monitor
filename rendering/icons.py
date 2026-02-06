"""
Geometric icon drawing functions for e-ink display.

All icons render in black (0) on white (1) background at 4x supersampled resolution.
Each icon is drawn within a square bounding box of the specified size, positioned at (x, y).
"""

import math
from PIL import ImageDraw


def draw_battery_icon(draw: ImageDraw.Draw, x: int, y: int, size: int) -> None:
    """
    Draw a battery icon: rectangle body with small terminal on top.

    Args:
        draw: PIL ImageDraw instance
        x: Left coordinate of icon bounding box
        y: Top coordinate of icon bounding box
        size: Width and height of icon bounding box
    """
    # Main battery body (80% of height, centered)
    body_height = int(size * 0.8)
    body_y = y + (size - body_height) // 2
    body_bbox = [x, body_y, x + size, body_y + body_height]
    draw.rectangle(body_bbox, outline=0, width=6)

    # Battery terminal (small rectangle on top, centered, 20% width)
    terminal_width = int(size * 0.2)
    terminal_height = int(size * 0.1)
    terminal_x = x + (size - terminal_width) // 2
    terminal_y = y
    terminal_bbox = [terminal_x, terminal_y, terminal_x + terminal_width, terminal_y + terminal_height]
    draw.rectangle(terminal_bbox, fill=0)


def draw_house_icon(draw: ImageDraw.Draw, x: int, y: int, size: int) -> None:
    """
    Draw a house icon: triangle roof + rectangle body.

    Args:
        draw: PIL ImageDraw instance
        x: Left coordinate of icon bounding box
        y: Top coordinate of icon bounding box
        size: Width and height of icon bounding box
    """
    # Triangle roof (top 40% of size)
    roof_height = int(size * 0.4)
    roof_points = [
        (x + size // 2, y),  # Top center
        (x, y + roof_height),  # Bottom left
        (x + size, y + roof_height),  # Bottom right
    ]
    draw.polygon(roof_points, outline=0, width=6)

    # Rectangle body (bottom 60% of size)
    body_y = y + roof_height
    body_bbox = [x + size // 6, body_y, x + size - size // 6, y + size]
    draw.rectangle(body_bbox, outline=0, width=6)


def draw_grid_icon(draw: ImageDraw.Draw, x: int, y: int, size: int) -> None:
    """
    Draw a grid icon: 4 vertical + 4 horizontal lines.

    Args:
        draw: PIL ImageDraw instance
        x: Left coordinate of icon bounding box
        y: Top coordinate of icon bounding box
        size: Width and height of icon bounding box
    """
    # 4 vertical lines evenly spaced
    for i in range(4):
        line_x = x + int(i * size / 3)
        draw.line([(line_x, y), (line_x, y + size)], fill=0, width=4)

    # 4 horizontal lines evenly spaced
    for i in range(4):
        line_y = y + int(i * size / 3)
        draw.line([(x, line_y), (x + size, line_y)], fill=0, width=4)


def draw_sun_icon(draw: ImageDraw.Draw, x: int, y: int, size: int) -> None:
    """
    Draw a sun icon: filled circle center + 8 rays at 45-degree intervals.

    Args:
        draw: PIL ImageDraw instance
        x: Left coordinate of icon bounding box
        y: Top coordinate of icon bounding box
        size: Width and height of icon bounding box
    """
    center_x = x + size // 2
    center_y = y + size // 2

    # Filled circle center (40% of size)
    circle_radius = int(size * 0.2)
    circle_bbox = [
        center_x - circle_radius,
        center_y - circle_radius,
        center_x + circle_radius,
        center_y + circle_radius,
    ]
    draw.ellipse(circle_bbox, fill=0)

    # 8 rays at 0/45/90/135/180/225/270/315 degrees
    ray_inner_radius = int(size * 0.25)
    ray_outer_radius = int(size * 0.45)

    for angle_deg in [0, 45, 90, 135, 180, 225, 270, 315]:
        angle_rad = math.radians(angle_deg)
        inner_x = center_x + int(ray_inner_radius * math.cos(angle_rad))
        inner_y = center_y + int(ray_inner_radius * math.sin(angle_rad))
        outer_x = center_x + int(ray_outer_radius * math.cos(angle_rad))
        outer_y = center_y + int(ray_outer_radius * math.sin(angle_rad))
        draw.line([(inner_x, inner_y), (outer_x, outer_y)], fill=0, width=6)
