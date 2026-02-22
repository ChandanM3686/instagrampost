"""
Text-to-Image Generator Service
Creates stylish dark-background images with text for Instagram posts.
Used when users submit text-only posts without uploading an image.
"""

import os
import uuid
import textwrap
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
    # Fallback to default
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


def generate_text_image(text, output_dir, branding_text="@sasksvoice"):
    """
    Generate a stylish dark-background image with text.
    
    Args:
        text: The text content to display
        output_dir: Directory to save the generated image
        branding_text: Branding text shown at the bottom
    
    Returns:
        dict with 'success', 'filename', 'path', and optionally 'error'
    """
    try:
        # Create the image with a dark gradient background
        img = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), '#1a1a2e')
        draw = ImageDraw.Draw(img)
        
        # Draw gradient background (top-dark to bottom-slightly-lighter)
        for y in range(IMG_HEIGHT):
            # Dark navy to dark charcoal gradient
            r = int(18 + (y / IMG_HEIGHT) * 12)   # 18 → 30
            g = int(18 + (y / IMG_HEIGHT) * 12)   # 18 → 30
            b = int(35 + (y / IMG_HEIGHT) * 15)   # 35 → 50
            draw.line([(0, y), (IMG_WIDTH, y)], fill=(r, g, b))
        
        # Add subtle decorative elements
        # Top-left accent dot
        draw.ellipse([60, 60, 72, 72], fill='#e94560')
        # Bottom-right dots
        for i in range(3):
            for j in range(3):
                x = IMG_WIDTH - 100 + (j * 18)
                y_pos = IMG_HEIGHT - 200 + (i * 18)
                draw.ellipse([x, y_pos, x + 8, y_pos + 8], fill='#e94560', outline='#e94560')
        
        # Subtle corner accents
        draw.line([(40, 40), (40, 100)], fill='#333355', width=2)
        draw.line([(40, 40), (100, 40)], fill='#333355', width=2)
        draw.line([(IMG_WIDTH - 40, IMG_HEIGHT - 40), (IMG_WIDTH - 40, IMG_HEIGHT - 100)], fill='#333355', width=2)
        draw.line([(IMG_WIDTH - 40, IMG_HEIGHT - 40), (IMG_WIDTH - 100, IMG_HEIGHT - 40)], fill='#333355', width=2)
        
        # --- Main Text ---
        padding_x = 100
        max_text_width = IMG_WIDTH - (padding_x * 2)
        
        # Determine font size based on text length
        text_length = len(text)
        if text_length < 50:
            font_size = 52
        elif text_length < 100:
            font_size = 44
        elif text_length < 200:
            font_size = 36
        elif text_length < 400:
            font_size = 30
        else:
            font_size = 26
        
        main_font = _get_font(font_size, bold=False)
        
        # Wrap text
        lines = _wrap_text(text, main_font, max_text_width, draw)
        
        # Calculate total text height
        line_height = font_size + 16
        total_text_height = len(lines) * line_height
        
        # Ensure text fits vertically (leave room for branding)
        max_text_area_height = IMG_HEIGHT - 250  # top padding + bottom branding
        while total_text_height > max_text_area_height and font_size > 18:
            font_size -= 2
            main_font = _get_font(font_size, bold=False)
            lines = _wrap_text(text, main_font, max_text_width, draw)
            line_height = font_size + 14
            total_text_height = len(lines) * line_height
        
        # Center text vertically (slightly above center)
        start_y = (IMG_HEIGHT - total_text_height - 80) // 2
        start_y = max(80, start_y)
        
        # Draw each line
        for i, line in enumerate(lines):
            y_pos = start_y + (i * line_height)
            bbox = draw.textbbox((0, 0), line, font=main_font)
            text_width = bbox[2] - bbox[0]
            x_pos = (IMG_WIDTH - text_width) // 2  # Center horizontally
            
            # Draw text shadow for depth
            draw.text((x_pos + 2, y_pos + 2), line, fill='#0a0a15', font=main_font)
            # Draw main text in white
            draw.text((x_pos, y_pos), line, fill='#ffffff', font=main_font)
        
        # --- Horizontal separator line ---
        separator_y = start_y + total_text_height + 30
        separator_width = 200
        separator_x = (IMG_WIDTH - separator_width) // 2
        draw.line(
            [(separator_x, separator_y), (separator_x + separator_width, separator_y)],
            fill='#444466', width=1
        )
        
        # --- Branding text at bottom ---
        branding_font = _get_font(28, bold=True)
        bbox = draw.textbbox((0, 0), branding_text, font=branding_font)
        branding_width = bbox[2] - bbox[0]
        branding_x = (IMG_WIDTH - branding_width) // 2
        branding_y = IMG_HEIGHT - 100
        
        draw.text((branding_x, branding_y), branding_text, fill='#888899', font=branding_font)
        
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
