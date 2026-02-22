"""
Text-to-Image Generator Service
Creates stylish premium dark-background images with text for Instagram posts.
Used when users submit text-only posts without uploading an image.
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


def _draw_gradient_bg(draw, width, height):
    """Draw a premium multi-tone gradient background."""
    for y in range(height):
        progress = y / height
        # Deep navy → rich dark purple gradient
        r = int(10 + progress * 18)
        g = int(8 + progress * 12)
        b = int(30 + progress * 25)
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def _draw_glow_orbs(img, draw):
    """Draw soft glowing orbs for depth and atmosphere."""
    # Create a separate layer for glow effects
    glow_layer = Image.new('RGBA', (IMG_WIDTH, IMG_HEIGHT), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)

    # Top-right warm glow (coral/pink)
    for radius in range(180, 0, -2):
        alpha = int(6 * (1 - radius / 180))
        glow_draw.ellipse(
            [IMG_WIDTH - 200 - radius, -100 - radius,
             IMG_WIDTH - 200 + radius, -100 + radius],
            fill=(233, 69, 96, alpha)
        )

    # Bottom-left cool glow (blue/teal)
    for radius in range(220, 0, -2):
        alpha = int(5 * (1 - radius / 220))
        glow_draw.ellipse(
            [80 - radius, IMG_HEIGHT - 150 - radius,
             80 + radius, IMG_HEIGHT - 150 + radius],
            fill=(64, 120, 230, alpha)
        )

    # Center subtle purple glow
    center_x, center_y = IMG_WIDTH // 2, IMG_HEIGHT // 2 - 40
    for radius in range(300, 0, -3):
        alpha = int(3 * (1 - radius / 300))
        glow_draw.ellipse(
            [center_x - radius, center_y - radius,
             center_x + radius, center_y + radius],
            fill=(120, 80, 200, alpha)
        )

    # Blur the glow layer for softness
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=30))

    # Composite onto main image
    img_rgba = img.convert('RGBA')
    img_rgba = Image.alpha_composite(img_rgba, glow_layer)
    return img_rgba.convert('RGB')


def _draw_decorative_elements(draw):
    """Draw subtle geometric decorative elements."""
    # Top-left corner accent
    draw.line([(50, 50), (50, 120)], fill=(255, 255, 255, 40), width=1)
    draw.line([(50, 50), (120, 50)], fill=(255, 255, 255, 40), width=1)

    # Bottom-right corner accent
    draw.line([(IMG_WIDTH - 50, IMG_HEIGHT - 50), (IMG_WIDTH - 50, IMG_HEIGHT - 120)],
              fill=(255, 255, 255, 40), width=1)
    draw.line([(IMG_WIDTH - 50, IMG_HEIGHT - 50), (IMG_WIDTH - 120, IMG_HEIGHT - 50)],
              fill=(255, 255, 255, 40), width=1)

    # Accent dot (coral/pink)
    draw.ellipse([65, 65, 79, 79], fill='#e94560')

    # Dot grid pattern (bottom-right area)
    for i in range(4):
        for j in range(4):
            x = IMG_WIDTH - 120 + (j * 16)
            y_pos = IMG_HEIGHT - 220 + (i * 16)
            draw.ellipse([x, y_pos, x + 5, y_pos + 5], fill='#e94560')

    # Thin horizontal lines as subtle texture
    for i in range(3):
        y = 200 + i * 300
        x_start = random.randint(40, 100)
        line_len = random.randint(30, 60)
        alpha_color = (255, 255, 255)
        draw.line([(x_start, y), (x_start + line_len, y)],
                  fill=(60, 60, 90), width=1)


def _draw_vertical_accent_bar(draw):
    """Draw a thin colored accent bar on the left side."""
    bar_x = 35
    bar_top = IMG_HEIGHT // 2 - 120
    bar_bottom = IMG_HEIGHT // 2 + 120
    # Gradient bar from coral to purple
    for y in range(bar_top, bar_bottom):
        progress = (y - bar_top) / (bar_bottom - bar_top)
        r = int(233 - progress * 100)
        g = int(69 + progress * 30)
        b = int(96 + progress * 130)
        draw.line([(bar_x, y), (bar_x + 3, y)], fill=(r, g, b))


def generate_text_image(text, output_dir, branding_text="@sasksvoice"):
    """
    Generate a premium stylish dark-background image with text.

    Args:
        text: The text content to display
        output_dir: Directory to save the generated image
        branding_text: Branding text shown at the bottom

    Returns:
        dict with 'success', 'filename', 'path', and optionally 'error'
    """
    try:
        # Create the base image
        img = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), '#0a0818')
        draw = ImageDraw.Draw(img)

        # Draw gradient background
        _draw_gradient_bg(draw, IMG_WIDTH, IMG_HEIGHT)

        # Add atmospheric glow orbs
        img = _draw_glow_orbs(img, draw)
        draw = ImageDraw.Draw(img)

        # Draw decorative elements
        _draw_decorative_elements(draw)

        # Draw vertical accent bar
        _draw_vertical_accent_bar(draw)

        # --- Main Text ---
        padding_x = 110
        max_text_width = IMG_WIDTH - (padding_x * 2)

        # Determine font size based on text length
        text_length = len(text)
        if text_length < 50:
            font_size = 50
        elif text_length < 100:
            font_size = 42
        elif text_length < 200:
            font_size = 35
        elif text_length < 400:
            font_size = 28
        else:
            font_size = 24

        main_font = _get_font(font_size, bold=False)

        # Wrap text
        lines = _wrap_text(text, main_font, max_text_width, draw)

        # Calculate total text height
        line_height = font_size + 18
        total_text_height = len(lines) * line_height

        # Ensure text fits vertically
        max_text_area_height = IMG_HEIGHT - 280
        while total_text_height > max_text_area_height and font_size > 18:
            font_size -= 2
            main_font = _get_font(font_size, bold=False)
            lines = _wrap_text(text, main_font, max_text_width, draw)
            line_height = font_size + 16
            total_text_height = len(lines) * line_height

        # Center text vertically (slightly above center)
        start_y = (IMG_HEIGHT - total_text_height - 100) // 2
        start_y = max(90, start_y)

        # Draw each line of text
        for i, line in enumerate(lines):
            y_pos = start_y + (i * line_height)
            bbox = draw.textbbox((0, 0), line, font=main_font)
            text_width = bbox[2] - bbox[0]
            x_pos = (IMG_WIDTH - text_width) // 2

            # Subtle shadow for depth
            draw.text((x_pos + 2, y_pos + 2), line, fill=(5, 5, 20), font=main_font)
            # Main text - warm white
            draw.text((x_pos, y_pos), line, fill='#f0eef5', font=main_font)

        # --- Separator line with gradient ---
        separator_y = start_y + total_text_height + 35
        separator_width = 160
        separator_x = (IMG_WIDTH - separator_width) // 2
        for x in range(separator_width):
            progress = x / separator_width
            r = int(233 * (1 - abs(progress - 0.5) * 2))
            g = int(69 * (1 - abs(progress - 0.5) * 2))
            b = int(96 + 80 * (1 - abs(progress - 0.5) * 2))
            draw.point((separator_x + x, separator_y), fill=(r, g, b))
            draw.point((separator_x + x, separator_y + 1), fill=(r, g, b))

        # --- Website URL ---
        url_font = _get_font(22, bold=False)
        url_text = "sasksvoice.com"
        bbox = draw.textbbox((0, 0), url_text, font=url_font)
        url_width = bbox[2] - bbox[0]
        url_x = (IMG_WIDTH - url_width) // 2
        url_y = separator_y + 25

        # URL with subtle pill background
        pill_padding_x = 20
        pill_padding_y = 8
        pill_rect = [
            url_x - pill_padding_x, url_y - pill_padding_y,
            url_x + url_width + pill_padding_x, url_y + (bbox[3] - bbox[1]) + pill_padding_y
        ]
        draw.rounded_rectangle(pill_rect, radius=20, fill=(255, 255, 255, 15), outline=(255, 255, 255, 30))
        # Link icon
        link_icon_font = _get_font(16, bold=False)
        draw.text((url_x - 5, url_y + 2), "🔗", font=link_icon_font)
        draw.text((url_x + 18, url_y), url_text, fill='#c8c4d8', font=url_font)

        # --- Branding text at bottom ---
        branding_font = _get_font(26, bold=True)
        bbox = draw.textbbox((0, 0), branding_text, font=branding_font)
        branding_width = bbox[2] - bbox[0]
        branding_x = (IMG_WIDTH - branding_width) // 2
        branding_y = IMG_HEIGHT - 90

        draw.text((branding_x, branding_y), branding_text, fill='#7a7590', font=branding_font)

        # --- Save the image ---
        os.makedirs(output_dir, exist_ok=True)
        filename = f'{uuid.uuid4().hex}_textpost.png'
        filepath = os.path.join(output_dir, filename)
        img.save(filepath, 'PNG', quality=95)

        logger.info(f'Text image generated: {filepath} ({len(text)} chars)')
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
