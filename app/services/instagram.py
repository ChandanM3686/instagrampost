"""
Instagram Publishing Service
Uses Instagram Graph API to publish content to Instagram Business account.

Flow:
1. Upload image to a public host (imgbb) to get a public URL
2. Create media container via Instagram Graph API
3. Wait for container to be ready
4. Publish the container
"""

import os
import time
import base64
import logging
import tempfile
import requests
from PIL import Image, ImageFilter
from flask import current_app

logger = logging.getLogger(__name__)

# Instagram Graph API base URL
GRAPH_API_BASE = 'https://graph.instagram.com/v18.0'
IMGBB_API_URL = 'https://api.imgbb.com/1/upload'


class InstagramService:
    """Service for publishing content to Instagram via Instagram Graph API."""

    def __init__(self):
        self.access_token = current_app.config['INSTAGRAM_ACCESS_TOKEN']
        self.account_id = current_app.config['INSTAGRAM_ACCOUNT_ID']

    def _api_url(self, endpoint):
        return f'{GRAPH_API_BASE}/{endpoint}'

    def is_configured(self):
        """Check if Instagram API credentials are properly configured."""
        return bool(self.access_token and self.account_id)

    def fix_aspect_ratio(self, image_path):
        """
        Fix image aspect ratio for Instagram.
        Instagram supports: 4:5 (portrait) to 1.91:1 (landscape).
        
        If the image is outside these bounds, it gets placed on a blurred
        background with proper aspect ratio.
        
        Returns the path to the fixed image (or original if already fine).
        """
        try:
            img = Image.open(image_path)
            width, height = img.size
            ratio = width / height

            # Instagram limits
            MIN_RATIO = 4 / 5      # 0.8 (tallest portrait)
            MAX_RATIO = 1.91       # widest landscape

            if MIN_RATIO <= ratio <= MAX_RATIO:
                logger.info(f'Image aspect ratio {ratio:.2f} is OK, no fix needed')
                return image_path  # Already good

            logger.info(f'Image aspect ratio {ratio:.2f} needs fixing (allowed: {MIN_RATIO:.2f} to {MAX_RATIO:.2f})')

            # Convert to RGB if needed (RGBA/P modes cause issues with JPEG)
            if img.mode in ('RGBA', 'P', 'LA'):
                img = img.convert('RGB')

            if ratio < MIN_RATIO:
                # Too tall (like a phone screenshot) → fit into 4:5
                target_ratio = MIN_RATIO
                new_width = int(height * target_ratio)
                new_height = height
            else:
                # Too wide → fit into 1.91:1
                target_ratio = MAX_RATIO
                new_width = width
                new_height = int(width / target_ratio)

            # Create blurred background
            bg = img.copy()
            bg = bg.resize((new_width, new_height), Image.LANCZOS)
            bg = bg.filter(ImageFilter.GaussianBlur(radius=30))

            # Darken the background slightly
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Brightness(bg)
            bg = enhancer.enhance(0.4)

            # Resize original to fit within the new canvas
            img_ratio = width / height
            if ratio < MIN_RATIO:
                # Fit by height
                fit_height = int(new_height * 0.9)
                fit_width = int(fit_height * img_ratio)
            else:
                # Fit by width
                fit_width = int(new_width * 0.9)
                fit_height = int(fit_width / img_ratio)

            img_resized = img.resize((fit_width, fit_height), Image.LANCZOS)

            # Center the image on the background
            x_offset = (new_width - fit_width) // 2
            y_offset = (new_height - fit_height) // 2
            bg.paste(img_resized, (x_offset, y_offset))

            # Save to temp file
            fixed_path = image_path.rsplit('.', 1)[0] + '_fixed.jpg'
            bg.save(fixed_path, 'JPEG', quality=95)
            logger.info(f'Fixed image saved: {fixed_path} ({new_width}x{new_height})')
            return fixed_path

        except Exception as e:
            logger.error(f'Failed to fix aspect ratio: {e}')
            return image_path  # Return original if fix fails

    def upload_image_to_imgbb(self, local_image_path):
        """
        Upload a local image to imgbb.com for free public hosting.
        Returns a direct public image URL that Instagram can access.
        Converts to JPEG first to ensure Instagram compatibility.
        """
        imgbb_key = current_app.config.get('IMGBB_API_KEY', '')

        if not imgbb_key:
            return {'success': False, 'error': 'IMGBB_API_KEY not set in .env. Get a free key from https://api.imgbb.com/'}

        try:
            # Convert to JPEG if needed (Instagram prefers JPEG)
            upload_path = local_image_path
            try:
                from PIL import Image as PILImage
                img = PILImage.open(local_image_path)
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                if not local_image_path.lower().endswith(('.jpg', '.jpeg')):
                    upload_path = local_image_path.rsplit('.', 1)[0] + '_upload.jpg'
                    img.save(upload_path, 'JPEG', quality=95)
                    logger.info(f'Converted image to JPEG for upload: {upload_path}')
            except Exception as conv_err:
                logger.warning(f'Image conversion warning (using original): {conv_err}')

            with open(upload_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

            response = requests.post(IMGBB_API_URL, data={
                'key': imgbb_key,
                'image': image_data,
                'expiration': 86400  # 24 hours
            }, timeout=60)

            data = response.json()
            if data.get('success'):
                # Use direct image URL — NOT the page URL
                # Instagram needs a direct link to the image file
                public_url = data['data'].get('display_url') or data['data'].get('image', {}).get('url') or data['data']['url']
                logger.info(f'Image uploaded to imgbb: {public_url}')
                return {'success': True, 'url': public_url}
            else:
                error_msg = data.get('error', {}).get('message', 'Unknown imgbb error')
                logger.error(f'imgbb upload failed: {error_msg}')
                return {'success': False, 'error': f'imgbb upload failed: {error_msg}'}
        except Exception as e:
            logger.error(f'imgbb upload error: {e}')
            return {'success': False, 'error': str(e)}

    def create_image_container(self, image_url, caption, collaborators=None):
        """
        Create a media container for an image post.
        image_url must be a publicly accessible URL.
        collaborators: optional list of Instagram usernames (max 3) to invite.
        """
        url = self._api_url(f'{self.account_id}/media')
        payload = {
            'image_url': image_url,
            'caption': caption,
            'access_token': self.access_token
        }

        # Add collaborators if provided (up to 3 usernames)
        if collaborators:
            clean_collabs = [u.strip().lstrip('@') for u in collaborators if u.strip()][:3]
            if clean_collabs:
                payload['collaborators'] = clean_collabs
                logger.info(f'Adding collaborators: {clean_collabs}')

        try:
            logger.info(f'Creating image container: account={self.account_id}, url={image_url[:50]}...')
            response = requests.post(url, data=payload, timeout=60)
            data = response.json()

            if 'id' in data:
                logger.info(f'Image container created: {data["id"]}')
                return {'success': True, 'container_id': data['id']}
            else:
                error = data.get('error', {}).get('message', str(data))
                logger.error(f'Failed to create image container: {error}')
                return {'success': False, 'error': error}
        except Exception as e:
            logger.error(f'Instagram API error: {e}')
            return {'success': False, 'error': str(e)}

    def create_video_container(self, video_url, caption):
        """Create a media container for a video (Reels) post."""
        url = self._api_url(f'{self.account_id}/media')
        payload = {
            'video_url': video_url,
            'caption': caption,
            'media_type': 'REELS',
            'access_token': self.access_token
        }

        try:
            response = requests.post(url, data=payload, timeout=60)
            data = response.json()

            if 'id' in data:
                logger.info(f'Video container created: {data["id"]}')
                return {'success': True, 'container_id': data['id']}
            else:
                error = data.get('error', {}).get('message', str(data))
                logger.error(f'Failed to create video container: {error}')
                return {'success': False, 'error': error}
        except Exception as e:
            logger.error(f'Instagram API error: {e}')
            return {'success': False, 'error': str(e)}

    def check_container_status(self, container_id):
        """Check if a media container is ready for publishing."""
        url = self._api_url(container_id)
        params = {
            'fields': 'status_code,status',
            'access_token': self.access_token
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            data = response.json()
            status = data.get('status_code', 'UNKNOWN')
            logger.info(f'Container {container_id} status: {status}')
            return status
        except Exception as e:
            logger.error(f'Container status check error: {e}')
            return 'ERROR'

    def wait_for_container(self, container_id, max_attempts=30, delay=5):
        """Wait for container to be ready (FINISHED status)."""
        for attempt in range(max_attempts):
            status = self.check_container_status(container_id)
            logger.info(f'Container {container_id} status: {status} (attempt {attempt + 1}/{max_attempts})')

            if status == 'FINISHED':
                return True
            elif status in ('ERROR', 'EXPIRED'):
                return False

            time.sleep(delay)

        logger.warning(f'Container {container_id} timed out waiting for FINISHED status')
        return False

    def publish_container(self, container_id):
        """Publish a media container to Instagram."""
        url = self._api_url(f'{self.account_id}/media_publish')
        payload = {
            'creation_id': container_id,
            'access_token': self.access_token
        }

        try:
            response = requests.post(url, data=payload, timeout=60)
            data = response.json()

            if 'id' in data:
                logger.info(f'Published to Instagram: {data["id"]}')
                return {'success': True, 'instagram_post_id': data['id']}
            else:
                error = data.get('error', {}).get('message', str(data))
                logger.error(f'Failed to publish: {error}')
                return {'success': False, 'error': error}
        except Exception as e:
            logger.error(f'Instagram publish error: {e}')
            return {'success': False, 'error': str(e)}

    def publish_image(self, image_url, caption, collaborators=None):
        """Full flow: create container → wait → publish for an image."""
        # Step 1: Create container
        container_result = self.create_image_container(image_url, caption, collaborators=collaborators)
        if not container_result['success']:
            return container_result

        container_id = container_result['container_id']

        # Step 2: Wait for container to be ready
        if not self.wait_for_container(container_id):
            return {'success': False, 'error': 'Container processing timed out or failed'}

        # Step 3: Publish
        return self.publish_container(container_id)

    def publish_video(self, video_url, caption):
        """Full flow: create container → wait → publish for a video."""
        container_result = self.create_video_container(video_url, caption)
        if not container_result['success']:
            return container_result

        container_id = container_result['container_id']

        # Videos take longer to process
        if not self.wait_for_container(container_id, max_attempts=60, delay=10):
            return {'success': False, 'error': 'Video processing timed out or failed'}

        return self.publish_container(container_id)

    def publish_from_local(self, local_image_path, caption, video_path=None, collaborators=None):
        """
        Full flow: upload local image to imgbb → create container → wait → publish.
        This handles everything automatically — one-click publish.
        collaborators: optional list of Instagram usernames to invite as collaborators.
        """
        if not self.is_configured():
            return {'success': False, 'error': 'Instagram API not configured. Set INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_ACCOUNT_ID in .env'}

        # Step 1: Fix aspect ratio if needed
        logger.info(f'Checking aspect ratio: {local_image_path}')
        fixed_image_path = self.fix_aspect_ratio(local_image_path)

        # Step 2: Upload image to imgbb for a public URL
        logger.info(f'Uploading image to imgbb: {fixed_image_path}')
        upload_result = self.upload_image_to_imgbb(fixed_image_path)
        if not upload_result['success']:
            return upload_result

        public_url = upload_result['url']
        logger.info(f'Image uploaded: {public_url}')

        # Step 3: Publish via Instagram API
        if video_path:
            # Upload video to imgbb too
            video_upload = self.upload_image_to_imgbb(video_path)
            if video_upload['success']:
                return self.publish_video(video_upload['url'], caption)
            else:
                return video_upload

        return self.publish_image(public_url, caption, collaborators=collaborators)

    def publish_carousel_from_local(self, image_paths, caption, collaborators=None):
        """
        Publish a carousel (multi-image) post from local files.
        image_paths: list of local image file paths (2-10 images).
        """
        if not self.is_configured():
            return {'success': False, 'error': 'Instagram API not configured'}

        if len(image_paths) < 2:
            return {'success': False, 'error': 'Carousel requires at least 2 images'}

        if len(image_paths) > 10:
            image_paths = image_paths[:10]

        # Step 1: Upload all images to imgbb and create child containers
        child_container_ids = []
        for i, img_path in enumerate(image_paths):
            # Fix aspect ratio
            fixed_path = self.fix_aspect_ratio(img_path)

            # Upload to imgbb
            upload_result = self.upload_image_to_imgbb(fixed_path)
            if not upload_result['success']:
                logger.error(f'Failed to upload carousel image {i+1}: {upload_result.get("error")}')
                return upload_result

            # Create child container (no caption on individual items)
            child_result = self.create_carousel_item_container(upload_result['url'])
            if not child_result['success']:
                logger.error(f'Failed to create carousel child container {i+1}: {child_result.get("error")}')
                return child_result

            child_container_ids.append(child_result['container_id'])
            logger.info(f'Carousel item {i+1}/{len(image_paths)} created: {child_result["container_id"]}')

        # Step 2: Create carousel container with all children
        carousel_result = self.create_carousel_container(child_container_ids, caption, collaborators)
        if not carousel_result['success']:
            return carousel_result

        carousel_id = carousel_result['container_id']

        # Step 3: Wait for carousel to be ready
        if not self.wait_for_container(carousel_id, max_attempts=30, delay=5):
            return {'success': False, 'error': 'Carousel processing timed out'}

        # Step 4: Publish
        return self.publish_container(carousel_id)

    def create_carousel_item_container(self, image_url):
        """Create a child container for a carousel item (no caption)."""
        url = self._api_url(f'{self.account_id}/media')
        payload = {
            'image_url': image_url,
            'is_carousel_item': 'true',
            'access_token': self.access_token
        }

        try:
            response = requests.post(url, data=payload, timeout=60)
            data = response.json()

            if 'id' in data:
                return {'success': True, 'container_id': data['id']}
            else:
                error = data.get('error', {}).get('message', str(data))
                return {'success': False, 'error': error}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def create_carousel_container(self, children_ids, caption, collaborators=None):
        """Create the parent carousel container with all child container IDs."""
        url = self._api_url(f'{self.account_id}/media')
        payload = {
            'media_type': 'CAROUSEL',
            'caption': caption,
            'children': ','.join(children_ids),
            'access_token': self.access_token
        }

        if collaborators:
            clean_collabs = [u.strip().lstrip('@') for u in collaborators if u.strip()][:3]
            if clean_collabs:
                payload['collaborators'] = clean_collabs

        try:
            logger.info(f'Creating carousel container with {len(children_ids)} items')
            response = requests.post(url, data=payload, timeout=60)
            data = response.json()

            if 'id' in data:
                logger.info(f'Carousel container created: {data["id"]}')
                return {'success': True, 'container_id': data['id']}
            else:
                error = data.get('error', {}).get('message', str(data))
                logger.error(f'Failed to create carousel container: {error}')
                return {'success': False, 'error': error}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_media_info(self, media_id):
        """Get info about a published post."""
        url = self._api_url(media_id)
        params = {
            'fields': 'id,caption,media_type,media_url,permalink,timestamp',
            'access_token': self.access_token
        }

        try:
            response = requests.get(url, params=params, timeout=15)
            return response.json()
        except Exception as e:
            logger.error(f'Get media info error: {e}')
            return None
