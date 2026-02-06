"""
Geometric icon drawing functions for e-ink display.

All icons render in black (0) on white (1) background at 4x supersampled resolution.
Each icon is drawn within a square bounding box of the specified size, positioned at (x, y).
"""

import math
from PIL import ImageDraw


def draw_battery_icon(draw: ImageDraw.Draw, x: int, y: int, size: int) -> None:
    """
    Draw a battery icon: tall vertical rectangle body with small terminal on top.

    Args:
        draw: PIL ImageDraw instance
        x: Left coordinate of icon bounding box
        y: Top coordinate of icon bounding box
        size: Width and height of icon bounding box
    """
    # Main battery body (tall vertical rectangle: 55% width, 90% height)
    body_width = int(size * 0.55)
    body_height = int(size * 0.9)
    body_x = x + (size - body_width) // 2
    body_y = y + (size - body_height)
    body_bbox = [body_x, body_y, body_x + body_width, body_y + body_height]
    draw.rectangle(body_bbox, outline=0, width=6)

    # Battery terminal (small rectangle on top, centered, 25% of body width)
    terminal_width = int(body_width * 0.25)
    terminal_height = int(size * 0.08)
    terminal_x = body_x + (body_width - terminal_width) // 2
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
    # Triangle roof (top 38% of size, leaving gap before body)
    roof_height = int(size * 0.38)
    roof_points = [
        (x + size // 2, y),  # Top center
        (x, y + roof_height),  # Bottom left
        (x + size, y + roof_height),  # Bottom right
    ]
    draw.polygon(roof_points, outline=0, width=6)

    # Rectangle body (offset down by 5px to create gap from roof)
    body_y = y + roof_height + 5
    body_bbox = [x + size // 6, body_y, x + size - size // 6, y + size]
    draw.rectangle(body_bbox, outline=0, width=6)


def draw_grid_icon(draw: ImageDraw.Draw, x: int, y: int, size: int) -> None:
    """
    Draw a power pylon icon: simplified transmission tower with vertical body,
    angled legs, and crossarms.

    Args:
        draw: PIL ImageDraw instance
        x: Left coordinate of icon bounding box
        y: Top coordinate of icon bounding box
        size: Width and height of icon bounding box
    """
    center_x = x + size // 2

    # Vertical tower body (center line from top to 70% down)
    tower_top_y = y + int(size * 0.1)
    tower_bottom_y = y + int(size * 0.7)
    draw.line([(center_x, tower_top_y), (center_x, tower_bottom_y)], fill=0, width=6)

    # Two angled legs at bottom (splayed outward)
    leg_spread = int(size * 0.4)
    left_leg_bottom = center_x - leg_spread
    right_leg_bottom = center_x + leg_spread
    bottom_y = y + size
    draw.line([(center_x, tower_bottom_y), (left_leg_bottom, bottom_y)], fill=0, width=6)
    draw.line([(center_x, tower_bottom_y), (right_leg_bottom, bottom_y)], fill=0, width=6)

    # Upper crossarm (horizontal)
    crossarm_y = y + int(size * 0.2)
    crossarm_width = int(size * 0.7)
    crossarm_left = center_x - crossarm_width // 2
    crossarm_right = center_x + crossarm_width // 2
    draw.line([(crossarm_left, crossarm_y), (crossarm_right, crossarm_y)], fill=0, width=5)

    # Lower crossarm (horizontal, shorter)
    crossarm2_y = y + int(size * 0.45)
    crossarm2_width = int(size * 0.5)
    crossarm2_left = center_x - crossarm2_width // 2
    crossarm2_right = center_x + crossarm2_width // 2
    draw.line([(crossarm2_left, crossarm2_y), (crossarm2_right, crossarm2_y)], fill=0, width=5)


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
