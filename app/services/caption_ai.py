"""
Gemini AI Caption Generator Service
Uses Google Gemini to analyze images and generate Instagram-ready captions.

Uses the new google-genai SDK (v0.8+).
"""

import os
import logging
from google import genai
from flask import current_app

logger = logging.getLogger(__name__)


class CaptionGenerator:
    """Generate Instagram captions using Gemini AI with image analysis."""

    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY', '')
        if not self.api_key:
            logger.warning('GEMINI_API_KEY not set in environment variables')
            raise ValueError('GEMINI_API_KEY is required. Set it in your .env file.')
        self.client = genai.Client(api_key=self.api_key)

    def generate_caption(self, image_path, user_caption="", style="engaging"):
        """
        Generate an Instagram caption by analyzing the image with Gemini.
        
        Args:
            image_path: Path to the image file
            user_caption: Optional user-provided caption/context
            style: Caption style - 'engaging', 'minimal', 'storytelling', 'funny', 'professional'
        
        Returns:
            dict with 'success', 'caption', and optionally 'error'
        """
        try:
            # Build the prompt based on style
            style_instructions = {
                'engaging': 'Write an engaging, attention-grabbing Instagram caption that encourages interaction. Include a call-to-action and relevant emojis.',
                'minimal': 'Write a short, clean, and aesthetic Instagram caption. Keep it under 2 lines. Minimal but impactful.',
                'storytelling': 'Write a storytelling-style Instagram caption that creates emotion and connection. Make it personal and relatable.',
                'funny': 'Write a funny, witty Instagram caption with humor. Include clever wordplay or a relatable joke.',
                'professional': 'Write a professional, polished Instagram caption suitable for a brand or business. Keep it clean and impactful.',
            }

            style_prompt = style_instructions.get(style, style_instructions['engaging'])

            prompt = f"""You are an expert Instagram content creator. Analyze this image and generate a perfect Instagram caption.

{style_prompt}

Rules:
- Caption should be 2-5 lines max
- Include 5-10 relevant hashtags at the end
- Use emojis naturally (don't overdo it)
- Make it feel authentic, not robotic
- If the image has text, incorporate it meaningfully
- Caption should be in English

{"User's context/note: " + user_caption if user_caption else "No additional context provided."}

Generate ONLY the caption text with hashtags. No explanations or meta-text."""

            # Upload the image and generate
            logger.info(f'Generating caption for: {image_path}')
            
            uploaded_file = self.client.files.upload(file=image_path)
            
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[prompt, uploaded_file]
            )

            if response and response.text:
                caption = response.text.strip()
                # Remove any markdown formatting
                caption = caption.replace('```', '').strip()
                if caption.startswith('"') and caption.endswith('"'):
                    caption = caption[1:-1]

                logger.info(f'Caption generated ({len(caption)} chars)')
                return {'success': True, 'caption': caption}
            else:
                return {'success': False, 'error': 'Gemini returned empty response'}

        except Exception as e:
            logger.error(f'Caption generation error: {e}')
            return {'success': False, 'error': str(e)}

    def generate_caption_text_only(self, user_caption="", style="engaging"):
        """
        Generate/enhance a caption without an image (text-only).
        Used as fallback when image upload fails.
        """
        try:
            prompt = f"""You are an expert Instagram content creator. Generate an engaging Instagram caption.

Original text/caption: "{user_caption}"

Rules:
- Make it more engaging and attention-grabbing
- Keep it 2-5 lines max
- Add relevant emojis
- Add 5-10 relevant hashtags at the end
- Don't change the language

Generate ONLY the caption text. No explanations."""

            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )

            if response and response.text:
                caption = response.text.strip().replace('```', '').strip()
                if caption.startswith('"') and caption.endswith('"'):
                    caption = caption[1:-1]
                return {'success': True, 'caption': caption}
            else:
                return {'success': False, 'error': 'Gemini returned empty response'}

        except Exception as e:
            logger.error(f'Caption text generation error: {e}')
            return {'success': False, 'error': str(e)}
