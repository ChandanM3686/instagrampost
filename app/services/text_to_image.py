"""
Text-to-Image Generator Service
Creates stylish premium images with text for Instagram posts.
Used when users submit text-only posts without uploading an image.

Features vibrant gradient backgrounds, larger text, and eye-catching designs.
"""

import os
import uuid
import math
import random
import logging
from PIL import Image, ImageDraw, ImageFont, ImageFilter

logger = logging.getLogger(__name__)

# Instagram square post dimensions
IMG_WIDTH = 1080
IMG_HEIGHT = 1080

# Vibrant color themes for variety
COLOR_THEMES = [
    {
        'name': 'sunset',
        'bg_start': (25, 10, 40),
        'bg_end': (60, 15, 30),
        'glow1': (255, 100, 80),    # coral
        'glow2': (180, 50, 220),    # purple
        'glow3': (255, 150, 50),    # orange
        'accent': '#ff6b4a',
        'text': '#ffffff',
        'bar_colors': [(255, 100, 80), (255, 50, 100)],
    },
    {
        'name': 'ocean',
        'bg_start': (5, 15, 40),
        'bg_end': (10, 30, 55),
        'glow1': (0, 180, 255),     # cyan
        'glow2': (80, 50, 230),     # blue-purple
        'glow3': (0, 220, 180),     # teal
        'accent': '#00d4ff',
        'text': '#ffffff',
        'bar_colors': [(0, 180, 255), (0, 220, 180)],
    },
    {
        'name': 'aurora',
        'bg_start': (10, 20, 35),
        'bg_end': (15, 35, 25),
        'glow1': (100, 255, 150),   # green
        'glow2': (50, 150, 255),    # blue
        'glow3': (200, 100, 255),   # violet
        'accent': '#64ff96',
        'text': '#ffffff',
        'bar_colors': [(100, 255, 150), (50, 150, 255)],
    },
    {
        'name': 'neon_pink',
        'bg_start': (30, 5, 30),
        'bg_end': (15, 5, 40),
        'glow1': (255, 50, 150),    # hot pink
        'glow2': (150, 0, 255),     # purple
        'glow3': (255, 100, 200),   # light pink
        'accent': '#ff32a0',
        'text': '#ffffff',
        'bar_colors': [(255, 50, 150), (150, 0, 255)],
    },
    {
        'name': 'golden',
        'bg_start': (25, 15, 5),
        'bg_end': (40, 20, 10),
        'glow1': (255, 200, 50),    # gold
        'glow2': (255, 120, 30),    # amber
        'glow3': (255, 80, 60),     # warm red
        'accent': '#ffc832',
        'text': '#ffffff',
        'bar_colors': [(255, 200, 50), (255, 120, 30)],
    },
]


def _get_font(size, bold=False):
    """Try to load a nice font, fall back to default."""
    font_names = [
        # Windows
        'C:/Windows/Fonts/seguisb.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf',
        'C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',
        # Linux
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf' if bold else '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
    ]
    for font_path in font_names:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _wrap_text(text, font, max_width, draw):
    """Smart text wrapping that respects word boundaries."""
    lines = []
    paragraphs = text.split('\n')

    for paragraph in paragraphs:
        if not paragraph.strip():
            lines.append('')
            continue

        words = paragraph.split()
        current_line = ''

        for word in words:
            test_line = f'{current_line} {word}'.strip()
            bbox = draw.textbbox((0, 0), test_line, font=font)
            line_width = bbox[2] - bbox[0]

            if line_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

    return lines


def _draw_gradient_bg(draw, width, height, theme):
    """Draw a rich multi-tone gradient background."""
    bg_start = theme['bg_start']
    bg_end = theme['bg_end']
    for y in range(height):
        progress = y / height
        # Smooth curved gradient
        curve = math.sin(progress * math.pi * 0.5)
        r = int(bg_start[0] + curve * (bg_end[0] - bg_start[0]))
        g = int(bg_start[1] + curve * (bg_end[1] - bg_start[1]))
        b = int(bg_start[2] + curve * (bg_end[2] - bg_start[2]))
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def _draw_glow_orbs(img, theme):
    """Draw vibrant glowing orbs for depth and atmosphere."""
    glow_layer = Image.new('RGBA', (IMG_WIDTH, IMG_HEIGHT), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)

    # Glow 1 — top-right
    g1 = theme['glow1']
    cx1, cy1 = IMG_WIDTH - 150, -50
    for radius in range(250, 0, -2):
        alpha = int(12 * (1 - radius / 250))
        glow_draw.ellipse(
            [cx1 - radius, cy1 - radius, cx1 + radius, cy1 + radius],
            fill=(g1[0], g1[1], g1[2], alpha)
        )

    # Glow 2 — bottom-left
    g2 = theme['glow2']
    cx2, cy2 = 100, IMG_HEIGHT - 100
    for radius in range(280, 0, -2):
        alpha = int(10 * (1 - radius / 280))
        glow_draw.ellipse(
            [cx2 - radius, cy2 - radius, cx2 + radius, cy2 + radius],
            fill=(g2[0], g2[1], g2[2], alpha)
        )

    # Glow 3 — center, very subtle
    g3 = theme['glow3']
    cx3, cy3 = IMG_WIDTH // 2, IMG_HEIGHT // 2
    for radius in range(350, 0, -3):
        alpha = int(5 * (1 - radius / 350))
        glow_draw.ellipse(
            [cx3 - radius, cy3 - radius, cx3 + radius, cy3 + radius],
            fill=(g3[0], g3[1], g3[2], alpha)
        )

    # Extra accent glow — random position
    g_extra = random.choice([theme['glow1'], theme['glow2'], theme['glow3']])
    cx_e = random.randint(200, IMG_WIDTH - 200)
    cy_e = random.randint(200, IMG_HEIGHT - 200)
    for radius in range(150, 0, -2):
        alpha = int(4 * (1 - radius / 150))
        glow_draw.ellipse(
            [cx_e - radius, cy_e - radius, cx_e + radius, cy_e + radius],
            fill=(g_extra[0], g_extra[1], g_extra[2], alpha)
        )

    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=40))

    img_rgba = img.convert('RGBA')
    img_rgba = Image.alpha_composite(img_rgba, glow_layer)
    return img_rgba.convert('RGB')


def _draw_decorative_elements(draw, theme):
    """Draw geometric decorative elements with theme colors."""
    accent_color = theme['glow1']

    # Top-left corner brackets
    draw.line([(45, 45), (45, 130)], fill=(255, 255, 255, 60), width=2)
    draw.line([(45, 45), (130, 45)], fill=(255, 255, 255, 60), width=2)

    # Bottom-right corner brackets
    draw.line([(IMG_WIDTH - 45, IMG_HEIGHT - 45), (IMG_WIDTH - 45, IMG_HEIGHT - 130)],
              fill=(255, 255, 255, 60), width=2)
    draw.line([(IMG_WIDTH - 45, IMG_HEIGHT - 45), (IMG_WIDTH - 130, IMG_HEIGHT - 45)],
              fill=(255, 255, 255, 60), width=2)

    # Accent dots at corners
    dot_color = accent_color
    draw.ellipse([58, 58, 76, 76], fill=dot_color)
    draw.ellipse([IMG_WIDTH - 76, IMG_HEIGHT - 76, IMG_WIDTH - 58, IMG_HEIGHT - 58], fill=dot_color)

    # Scattered small dots/stars pattern
    for _ in range(15):
        x = random.randint(40, IMG_WIDTH - 40)
        y = random.randint(40, IMG_HEIGHT - 40)
        size = random.randint(2, 5)
        alpha_f = random.uniform(0.2, 0.6)
        c = tuple(int(v * alpha_f) for v in accent_color)
        draw.ellipse([x, y, x + size, y + size], fill=c)

    # Floating line accents
    for _ in range(4):
        y = random.randint(100, IMG_HEIGHT - 100)
        x_start = random.choice([random.randint(40, 80), random.randint(IMG_WIDTH - 80, IMG_WIDTH - 40)])
        line_len = random.randint(25, 50)
        draw.line([(x_start, y), (x_start + line_len, y)],
                  fill=(accent_color[0] // 3, accent_color[1] // 3, accent_color[2] // 3), width=1)


def _draw_accent_bar(draw, theme, y_center):
    """Draw a vibrant accent bar on the left side."""
    bar_x = 32
    bar_height = 200
    bar_top = y_center - bar_height // 2
    bar_bottom = y_center + bar_height // 2
    c1, c2 = theme['bar_colors']

    for y in range(bar_top, bar_bottom):
        progress = (y - bar_top) / (bar_bottom - bar_top)
        r = int(c1[0] + progress * (c2[0] - c1[0]))
        g = int(c1[1] + progress * (c2[1] - c1[1]))
        b = int(c1[2] + progress * (c2[2] - c1[2]))
        draw.line([(bar_x, y), (bar_x + 4, y)], fill=(r, g, b))


def generate_text_image(text, output_dir, branding_text="@sasksvoice"):
    """
    Generate a premium stylish image with text for Instagram.

    Args:
        text: The text content to display
        output_dir: Directory to save the generated image
        branding_text: Branding text shown at the bottom

    Returns:
        dict with 'success', 'filename', 'path', and optionally 'error'
    """
    try:
        # Pick a random color theme for variety
        theme = random.choice(COLOR_THEMES)

        # Create the base image
        img = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), '#0a0818')
        draw = ImageDraw.Draw(img)

        # Draw gradient background
        _draw_gradient_bg(draw, IMG_WIDTH, IMG_HEIGHT, theme)

        # Add vibrant glow orbs
        img = _draw_glow_orbs(img, theme)
        draw = ImageDraw.Draw(img)

        # Draw decorative elements
        _draw_decorative_elements(draw, theme)

        # --- Main Text (BIGGER SIZES) ---
        padding_x = 90
        max_text_width = IMG_WIDTH - (padding_x * 2)

        # Much larger font sizes for impact
        text_length = len(text)
        if text_length < 30:
            font_size = 72
        elif text_length < 60:
            font_size = 62
        elif text_length < 100:
            font_size = 52
        elif text_length < 150:
            font_size = 44
        elif text_length < 250:
            font_size = 38
        elif text_length < 400:
            font_size = 32
        else:
            font_size = 28

        main_font = _get_font(font_size, bold=True)

        # Wrap text
        lines = _wrap_text(text, main_font, max_text_width, draw)

        # Calculate total text height
        line_height = int(font_size * 1.5)
        total_text_height = len(lines) * line_height

        # Ensure text fits vertically — shrink if needed but keep minimum 26
        max_text_area_height = IMG_HEIGHT - 280
        while total_text_height > max_text_area_height and font_size > 26:
            font_size -= 2
            main_font = _get_font(font_size, bold=True)
            lines = _wrap_text(text, main_font, max_text_width, draw)
            line_height = int(font_size * 1.45)
            total_text_height = len(lines) * line_height

        # Draw accent bar aligned with text center
        text_center_y = IMG_HEIGHT // 2 - 30
        _draw_accent_bar(draw, theme, text_center_y)

        # Center text vertically
        start_y = (IMG_HEIGHT - total_text_height - 100) // 2
        start_y = max(80, start_y)

        # Draw each line of text with glow effect
        for i, line in enumerate(lines):
            y_pos = start_y + (i * line_height)
            bbox = draw.textbbox((0, 0), line, font=main_font)
            text_width = bbox[2] - bbox[0]
            x_pos = (IMG_WIDTH - text_width) // 2

            # Text shadow/glow for depth
            shadow_color = (
                theme['glow1'][0] // 8,
                theme['glow1'][1] // 8,
                theme['glow1'][2] // 8
            )
            draw.text((x_pos + 3, y_pos + 3), line, fill=shadow_color, font=main_font)
            draw.text((x_pos + 1, y_pos + 1), line, fill=(10, 10, 20), font=main_font)
            # Main text — bright white
            draw.text((x_pos, y_pos), line, fill='#ffffff', font=main_font)

        # --- Separator line with theme accent ---
        separator_y = start_y + total_text_height + 30
        separator_width = 200
        separator_x = (IMG_WIDTH - separator_width) // 2
        c1, c2 = theme['bar_colors']
        for x in range(separator_width):
            progress = x / separator_width
            fade = 1 - abs(progress - 0.5) * 2
            r = int(c1[0] * fade + c2[0] * (1 - fade))
            g = int(c1[1] * fade + c2[1] * (1 - fade))
            b = int(c1[2] * fade + c2[2] * (1 - fade))
            draw.point((separator_x + x, separator_y), fill=(r, g, b))
            draw.point((separator_x + x, separator_y + 1), fill=(r, g, b))
            draw.point((separator_x + x, separator_y + 2), fill=(r, g, b))

        # --- Website URL pill ---
        url_font = _get_font(22, bold=False)
        url_text = "sasksvoice.com"
        bbox = draw.textbbox((0, 0), url_text, font=url_font)
        url_width = bbox[2] - bbox[0]
        url_x = (IMG_WIDTH - url_width) // 2
        url_y = separator_y + 25

        pill_padding_x = 22
        pill_padding_y = 10
        pill_rect = [
            url_x - pill_padding_x, url_y - pill_padding_y,
            url_x + url_width + pill_padding_x, url_y + (bbox[3] - bbox[1]) + pill_padding_y
        ]
        draw.rounded_rectangle(pill_rect, radius=20, fill=(255, 255, 255, 15), outline=(255, 255, 255, 30))
        draw.text((url_x, url_y), url_text, fill='#c8c4d8', font=url_font)

        # --- Branding at bottom ---
        branding_font = _get_font(28, bold=True)
        bbox = draw.textbbox((0, 0), branding_text, font=branding_font)
        branding_width = bbox[2] - bbox[0]
        branding_x = (IMG_WIDTH - branding_width) // 2
        branding_y = IMG_HEIGHT - 85

        draw.text((branding_x, branding_y), branding_text, fill='#7a7590', font=branding_font)

        # --- Save ---
        os.makedirs(output_dir, exist_ok=True)
        filename = f'{uuid.uuid4().hex}_textpost.png'
        filepath = os.path.join(output_dir, filename)
        img.save(filepath, 'PNG', quality=95)

        logger.info(f'Text image generated: {filepath} ({len(text)} chars, theme={theme["name"]})')
        return {
            'success': True,
            'filename': filename,
            'path': filepath
        }

    except Exception as e:
        logger.error(f'Text-to-image generation error: {e}')
        return {
            'success': False,
            'error': str(e)
        }
