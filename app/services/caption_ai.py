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
            # Try loading from Flask config as fallback
            try:
                self.api_key = current_app.config.get('GEMINI_API_KEY', '')
            except RuntimeError:
                pass
        if not self.api_key:
            logger.warning('GEMINI_API_KEY not set in environment variables')
            raise ValueError('GEMINI_API_KEY is required. Set it in your .env file.')
        self.client = genai.Client(api_key=self.api_key)

    def generate_caption(self, image_path, user_caption="", style="engaging", submission_id=None):
        """
        Generate an Instagram caption by analyzing the image with Gemini.
        
        Args:
            image_path: Path to the image file (or list of paths for carousel)
            user_caption: Optional user-provided caption/context
            style: Caption style - 'engaging', 'minimal', 'storytelling', 'funny', 'professional'
            submission_id: Optional submission ID for reference
        
        Returns:
            dict with 'success', 'caption', and optionally 'error'
        """
        try:
            # Build the prompt based on style
            style_instructions = {
                'engaging': 'Write an engaging, attention-grabbing caption that encourages interaction.',
                'minimal': 'Write a short, clean, and aesthetic caption. Keep it under 2 lines. Minimal but impactful.',
                'storytelling': 'Write a storytelling-style caption that creates emotion and connection.',
                'funny': 'Write a funny, witty caption with humor. Include clever wordplay or a relatable joke.',
                'professional': 'Write a professional, polished caption suitable for a brand or business.',
            }

            style_prompt = style_instructions.get(style, style_instructions['engaging'])

            # Winnipeg SPKR-style caption format
            prompt = f"""You are an expert Instagram content creator for a community page called "Sask Voice" (@sasksvoice).

Analyze this image carefully and generate a perfect Instagram caption.

{style_prompt}

IMPORTANT CAPTION FORMAT:
1. Start with the Instagram handle and submission reference:
   sasksvoice #{submission_id or '0000'} [{self._get_timestamp()}]
2. Next line: Write a clear, descriptive title based on what's in the image
   - If it's a car, mention the year, make, model, condition
   - If it's a room/house, mention the type, location, price
   - If it's a service, mention what service and contact info
   - If it's a personal post, write something engaging
3. Then include the user's message/caption as-is (if provided)
4. Add a separator line: _______________
5. End with 8-15 RELEVANT hashtags based on the image content

HASHTAG RULES:
- Hashtags MUST be specific to what's in the image
- For cars: #CarForSale #[Make][Model] #UsedCars #[City]Cars #AutoSale etc.
- For rooms: #RoomForRent #[City]Housing #RentInCanada etc.
- For services: #[ServiceType] #[City]Services etc.
- Always include: #SaskVoice #Saskatchewan #Saskatoon #Regina (pick relevant ones)
- Make hashtags feel natural and community-oriented
- Do NOT use generic hashtags like #instagood #photooftheday

{"User's original caption/message: " + user_caption if user_caption else "No additional context provided."}

Generate ONLY the caption text with hashtags. No explanations or meta-text."""

            # Upload the image and generate
            logger.info(f'Generating caption for: {image_path}')
            
            # Handle single image or list of images
            contents = [prompt]
            if isinstance(image_path, list):
                for img_path in image_path[:3]:  # Upload up to 3 images
                    if os.path.exists(img_path):
                        uploaded_file = self.client.files.upload(file=img_path)
                        contents.append(uploaded_file)
            else:
                if os.path.exists(image_path):
                    uploaded_file = self.client.files.upload(file=image_path)
                    contents.append(uploaded_file)
            
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents
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

    def generate_caption_text_only(self, user_caption="", style="engaging", submission_id=None):
        """
        Generate/enhance a caption without an image (text-only post).
        """
        try:
            prompt = f"""You are an expert Instagram content creator for a community page called "Sask Voice" (@sasksvoice).

Generate an Instagram caption based on the text below.

CAPTION FORMAT:
1. Start with: sasksvoice #{submission_id or '0000'} [{self._get_timestamp()}]
2. Next line: A clear summary/title of what the user is posting about
3. Then include the user's text as-is
4. Add separator: _______________
5. End with 8-15 RELEVANT hashtags

Original text/caption: "{user_caption}"

HASHTAG RULES:
- Hashtags must match the content (buying/selling/services/community)
- Always include: #SaskVoice #Saskatchewan
- Add city-specific: #Saskatoon #Regina #MooseJaw etc. if mentioned
- Do NOT use generic hashtags

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

    def _get_timestamp(self):
        """Get current timestamp in Winnipeg SPKR format."""
        import datetime
        now = datetime.datetime.now()
        day = now.day
        month = now.strftime('%b')
        hour = now.strftime('%I:%M%p').lower().lstrip('0')
        return f"{day} {month}, {hour}"
