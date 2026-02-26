"""
Main routes — public-facing submission form and pages.
"""

import os
import uuid
import logging
import traceback
import datetime
import requests
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, current_app, jsonify, send_from_directory
)
from werkzeug.utils import secure_filename
from app import db, limiter
from app.models import Submission, Payment, SystemSetting, BlacklistedKeyword
from app.services.moderation import ModerationEngine, compute_image_hash

logger = logging.getLogger(__name__)
main_bp = Blueprint('main', __name__)


def allowed_image(filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in current_app.config['ALLOWED_IMAGE_EXTENSIONS']


def allowed_video(filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in current_app.config['ALLOWED_VIDEO_EXTENSIONS']


def verify_recaptcha(token):
    """Verify Google reCAPTCHA token."""
    secret = current_app.config['RECAPTCHA_SECRET_KEY']
    if not secret:
        return True  # Skip if not configured

    try:
        resp = requests.post('https://www.google.com/recaptcha/api/siteverify', data={
            'secret': secret,
            'response': token,
            'remoteip': request.remote_addr
        }, timeout=10)
        result = resp.json()
        return result.get('success', False)
    except Exception as e:
        logger.error(f'reCAPTCHA verification failed: {e}')
        return False


@main_bp.route('/')
def index():
    """Homepage with submission form and published posts feed."""
    recaptcha_key = current_app.config.get('RECAPTCHA_SITE_KEY', '')
    stripe_key = current_app.config.get('STRIPE_PUBLISHABLE_KEY', '')
    # Fetch recently published posts for the feed
    published_posts = Submission.query.filter_by(status='published').order_by(
        Submission.published_at.desc()
    ).limit(30).all()
    return render_template('index.html',
                           recaptcha_key=recaptcha_key,
                           stripe_key=stripe_key,
                           published_posts=published_posts)


@main_bp.route('/submit', methods=['POST'])
@limiter.limit("10 per hour")
def submit():
    """Handle submission form POST."""
    try:
        # Verify reCAPTCHA
        recaptcha_token = request.form.get('g-recaptcha-response', '')
        if current_app.config.get('RECAPTCHA_SECRET_KEY') and not verify_recaptcha(recaptcha_token):
            flash('reCAPTCHA verification failed. Please try again.', 'error')
            return redirect(url_for('main.index'))

        # Get form data
        caption = request.form.get('caption', '').strip()
        post_type = request.form.get('post_type', 'free')
        submitter_name = request.form.get('name', '').strip()
        submitter_email = request.form.get('email', '').strip()

        # Validate caption
        if not caption:
            flash('Caption is required.', 'error')
            return redirect(url_for('main.index'))

        # ── SERVER-SIDE CONTENT MODERATION — block before saving anything ──
        # 1. Profanity check
        try:
            from better_profanity import profanity
            if profanity.contains_profanity(caption):
                flash('🚫 Your content contains inappropriate language and cannot be submitted.', 'error')
                return redirect(url_for('main.index'))
        except ImportError:
            logger.warning('better_profanity not installed, skipping profanity check')

        # 2. Built-in dangerous phrases check (works without any API)
        import re as _re
        DANGEROUS_PHRASES = [
            # Drugs/illegal substances
            r'sell(?:ing)?\s+drugs?', r'buy(?:ing)?\s+drugs?', r'drug\s+deal', r'weed\s+for\s+sale',
            r'cocaine', r'heroin', r'meth(?:amphetamine)?', r'fentanyl', r'ecstasy', r'lsd',
            r'sell(?:ing)?\s+weed', r'buy(?:ing)?\s+weed', r'sell(?:ing)?\s+pills?',
            # Weapons
            r'sell(?:ing)?\s+guns?', r'buy(?:ing)?\s+guns?', r'sell(?:ing)?\s+weapons?',
            r'illegal\s+firearms?', r'buy(?:ing)?\s+firearms?',
            # Violence
            r'kill\s+(?:him|her|them|you|someone|people|all)', r'murder\s+(?:him|her|them|you|someone)',
            r'shoot(?:ing)?\s+(?:up|people|someone)', r'bomb\s+threat', r'mass\s+shooting',
            r'death\s+to', r'i\s+will\s+kill',
            # Exploitation
            r'child\s+(?:porn|exploitation)', r'human\s+trafficking', r'sex\s+trafficking',
            r'underage', r'minors?\s+for\s+sale',
            # Self-harm
            r'how\s+to\s+(?:kill|harm)\s+(?:your|my)self', r'suicide\s+method',
            # Hate speech
            r'go\s+back\s+to\s+your\s+country', r'(?:white|black)\s+suprema',
            r'ethnic\s+cleansing', r'genocide',
            # Scams
            r'send\s+(?:me\s+)?(?:your\s+)?(?:bank|credit\s+card|ssn|social\s+security)',
            r'wire\s+(?:me\s+)?money', r'nigerian?\s+prince',
        ]
        caption_lower = caption.lower()
        for pattern in DANGEROUS_PHRASES:
            if _re.search(pattern, caption_lower):
                flash('🚫 Your content contains prohibited material and cannot be submitted.', 'error')
                logger.info(f'Submission blocked by dangerous phrase: pattern={pattern}')
                return redirect(url_for('main.index'))

        # 3. Admin blacklisted keywords check
        blacklisted = BlacklistedKeyword.query.filter_by(is_active=True).all()
        for bk in blacklisted:
            if bk.keyword.lower() in caption_lower:
                flash('🚫 Your content contains a restricted word and cannot be submitted.', 'error')
                return redirect(url_for('main.index'))

        # 4. LLM-based deep content check (Gemini) — catches nuanced violations
        try:
            gemini_key = current_app.config.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY')
            if gemini_key:
                from google import genai
                import json as _json
                client = genai.Client(api_key=gemini_key)
                mod_prompt = f"""You are a strict content moderation system. Analyze this Instagram caption and determine if it violates community guidelines.

Check for: hate speech, racism, violence, threats, sexual content, harassment, bullying, illegal activities (drug selling, weapons), misinformation, self-harm references.

Caption: "{caption}"

Respond ONLY with JSON:
- Safe: {{"flagged": false}}
- Violation: {{"flagged": true, "reason": "Brief explanation"}}"""

                mod_response = client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=mod_prompt
                )
                mod_text = mod_response.text.strip()
                if mod_text.startswith('```'):
                    mod_text = mod_text.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
                mod_result = _json.loads(mod_text)
                if mod_result.get('flagged'):
                    reason = mod_result.get('reason', 'Content violates community guidelines.')
                    flash(f'🚫 {reason}', 'error')
                    logger.info(f'Submission blocked by LLM moderation: {reason}')
                    return redirect(url_for('main.index'))
        except Exception as llm_err:
            logger.error(f'LLM server-side moderation error (non-fatal): {llm_err}')
            # Don't block if LLM fails — other checks already passed

        # Email required for promotional posts (for payment tracking)
        if post_type == 'promotional' and not submitter_email:
            flash('Email is required for promotional posts (to confirm your payment).', 'error')
            return redirect(url_for('main.index'))

        # Handle images — single, multiple (carousel), or auto-generated from text
        image_files = request.files.getlist('images')
        # Filter out empty file inputs
        image_files = [f for f in image_files if f and f.filename != '']
        is_text_only = len(image_files) == 0
        image_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'images')
        os.makedirs(image_dir, exist_ok=True)

        if is_text_only:
            # ── Text-only post: auto-generate a styled image ──
            from app.services.text_to_image import generate_text_image
            result = generate_text_image(caption, image_dir)
            if not result['success']:
                flash(f'Failed to generate text image: {result.get("error", "Unknown error")}', 'error')
                return redirect(url_for('main.index'))
            image_filename = result['filename']
            image_path = result['path']
            extra_image_paths = []
            logger.info(f'Auto-generated text image: {image_filename}')
        else:
            # ── User uploaded image(s) ──
            saved_images = []
            for img_file in image_files[:10]:  # Max 10 images
                if not allowed_image(img_file.filename):
                    flash(f'Invalid image format for {img_file.filename}. Allowed: PNG, JPG, JPEG, GIF, WebP', 'error')
                    # Clean up already saved images
                    for p in saved_images:
                        if os.path.exists(p['path']):
                            os.remove(p['path'])
                    return redirect(url_for('main.index'))

                image_ext = img_file.filename.rsplit('.', 1)[-1].lower()
                img_filename = f'{uuid.uuid4().hex}.{image_ext}'
                img_path = os.path.join(image_dir, img_filename)
                img_file.save(img_path)
                saved_images.append({'filename': img_filename, 'path': img_path})

            # First image is the main/cover image
            image_filename = saved_images[0]['filename']
            image_path = saved_images[0]['path']
            # Extra images for carousel
            extra_image_paths = [f'images/{img["filename"]}' for img in saved_images[1:]]
            logger.info(f'Saved {len(saved_images)} image(s): cover={image_filename}, extras={len(extra_image_paths)}')

        # Optional video
        video_path_str = None
        video_file = request.files.get('video')
        if video_file and video_file.filename != '':
            if not allowed_video(video_file.filename):
                flash('Invalid video format. Allowed: MP4, MOV, AVI', 'error')
                os.remove(image_path)
                return redirect(url_for('main.index'))

            video_ext = video_file.filename.rsplit('.', 1)[-1].lower()
            video_filename = f'{uuid.uuid4().hex}.{video_ext}'
            video_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'videos')
            os.makedirs(video_dir, exist_ok=True)
            video_path = os.path.join(video_dir, video_filename)
            video_file.save(video_path)
            video_path_str = f'videos/{video_filename}'

        # Compute image hash for duplicate detection (only for user-uploaded images)
        img_hash = compute_image_hash(image_path) if not is_text_only else None

        # Determine promo amount — fixed $2
        promo_amount = 0.0
        if post_type == 'promotional':
            promo_amount = 2.0

        # Check auto-publish setting
        auto_publish_setting = SystemSetting.get('auto_publish', 'false')
        require_approval = SystemSetting.get('require_approval', 'false')

        # Create submission
        import json as json_lib
        # Determine initial status
        if post_type == 'promotional':
            initial_status = 'payment_pending'
        elif auto_publish_setting == 'true' and require_approval != 'true':
            initial_status = 'approved'  # Will auto-publish after moderation
        else:
            initial_status = 'pending'

        submission = Submission(
            submitter_name=submitter_name,
            submitter_email=submitter_email,
            submitter_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent', ''),
            caption=caption,
            original_caption=caption,
            image_path=f'images/{image_filename}',
            extra_images=json_lib.dumps(extra_image_paths) if extra_image_paths else None,
            video_path=video_path_str,
            image_hash=img_hash,
            post_type=post_type,
            promo_amount=promo_amount,
            status=initial_status
        )
        db.session.add(submission)
        db.session.commit()

        logger.info(f'Submission created: #{submission.id} type={post_type} status={initial_status} email={submitter_email}')

        # Run moderation checks
        try:
            engine = ModerationEngine(submission.id)
            passed, results = engine.run_all_checks()
            if not passed:
                logger.info(f'Submission {submission.id} flagged by moderation')
        except Exception as mod_err:
            logger.error(f'Moderation error (non-fatal): {mod_err}')
            passed = True  # Don't block if moderation fails

        # Auto-publish for free posts if enabled and passed moderation
        if post_type != 'promotional' and initial_status == 'approved' and passed:
            try:
                from app.services.instagram import InstagramService
                ig = InstagramService()
                if ig.is_configured():
                    # Generate AI caption
                    try:
                        from app.services.caption_ai import CaptionGenerator
                        generator = CaptionGenerator()
                        img_full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f'images/{image_filename}')
                        ai_result = generator.generate_caption(
                            image_path=img_full_path,
                            user_caption=submission.caption,
                            style='engaging',
                            submission_id=submission.id
                        )
                        if ai_result.get('success'):
                            submission.caption = ai_result['caption']
                            db.session.commit()
                    except Exception as ai_err:
                        logger.error(f'AI caption error (non-fatal): {ai_err}')

                    img_full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], submission.image_path)
                    result = ig.publish_from_local(img_full_path, submission.caption)
                    if result.get('success'):
                        submission.status = 'published'
                        submission.published_at = datetime.datetime.utcnow()
                        submission.instagram_post_id = result.get('media_id')
                        db.session.commit()
                        logger.info(f'Auto-published submission #{submission.id}')
                    else:
                        logger.error(f'Auto-publish failed for #{submission.id}: {result.get("error")}')
                else:
                    logger.warning('Instagram API not configured, skipping auto-publish')
            except Exception as pub_err:
                logger.error(f'Auto-publish error: {pub_err}')

        # If promotional, redirect to Stripe
        if post_type == 'promotional':
            try:
                import stripe
                stripe.api_key = current_app.config['STRIPE_SECRET_KEY']

                logger.info(f'Creating Stripe checkout for submission #{submission.id}, amount=$2.00')

                session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': 'usd',
                            'unit_amount': 200,  # $2.00
                            'product_data': {
                                'name': 'SasksVoice Promotional Post',
                                'description': f'Instant publish — promotional post #{submission.id}',
                            },
                        },
                        'quantity': 1,
                    }],
                    mode='payment',
                    customer_email=submitter_email,
                    success_url=url_for('main.payment_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
                    cancel_url=url_for('main.payment_cancel', _external=True),
                    metadata={
                        'submission_id': str(submission.id),
                        'post_type': 'promotional'
                    },
                )

                # Store payment record
                payment = Payment(
                    submission_id=submission.id,
                    stripe_session_id=session.id,
                    amount=promo_amount,
                    status='pending'
                )
                db.session.add(payment)
                db.session.commit()

                logger.info(f'Stripe checkout URL: {session.url}')
                return redirect(session.url)

            except Exception as stripe_err:
                logger.error(f'Stripe error: {stripe_err}')
                logger.error(traceback.format_exc())
                flash(f'Payment setup failed: {str(stripe_err)}. Your submission is saved.', 'error')
                return redirect(url_for('main.index'))

        # Determine final message based on what happened
        if submission.status == 'published':
            flash('🎉 Your post has been published to Instagram automatically!', 'success')
            return redirect(url_for('main.success', auto_published='true'))
        elif submission.status == 'approved':
            # Auto-publish was attempted but failed — still approved, admin can publish manually
            flash('✅ Your post has been approved and will be published shortly.', 'success')
            return redirect(url_for('main.success'))
        else:
            flash('Your post has been submitted successfully! It will be reviewed shortly.', 'success')
            return redirect(url_for('main.success'))

    except Exception as e:
        logger.error(f'Submission error: {e}')
        logger.error(traceback.format_exc())
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('main.index'))


@main_bp.route('/success')
def success():
    """Submission success page."""
    auto_published = request.args.get('auto_published') == 'true'
    return render_template('success.html', auto_published=auto_published)


@main_bp.route('/payment/success')
def payment_success():
    """Payment success redirect page — auto-publish promo posts."""
    session_id = request.args.get('session_id')
    if session_id:
        try:
            payment = Payment.query.filter_by(stripe_session_id=session_id).first()
            if payment:
                payment.status = 'completed'
                submission = Submission.query.get(payment.submission_id)
                if submission and submission.status == 'payment_pending':
                    # Promotional posts auto-publish immediately after payment
                    submission.status = 'approved'
                    db.session.commit()
                    logger.info(f'Payment confirmed for submission #{submission.id}, auto-publishing...')

                    # Auto-publish to Instagram
                    try:
                        from app.services.instagram import InstagramService
                        ig = InstagramService()

                        if ig.is_configured():
                            # Generate AI caption
                            try:
                                from app.services.caption_ai import CaptionGenerator
                                generator = CaptionGenerator()
                                img_path = os.path.join(
                                    current_app.config['UPLOAD_FOLDER'],
                                    submission.image_path
                                )
                                ai_result = generator.generate_caption(
                                    image_path=img_path,
                                    user_caption=submission.caption,
                                    style='engaging',
                                    submission_id=submission.id
                                )
                                if ai_result.get('success'):
                                    submission.caption = ai_result['caption']
                                    db.session.commit()
                            except Exception as ai_err:
                                logger.error(f'AI caption error (non-fatal): {ai_err}')

                            img_path = os.path.join(
                                current_app.config['UPLOAD_FOLDER'],
                                submission.image_path
                            )
                            result = ig.publish_from_local(img_path, submission.caption)
                            if result.get('success'):
                                submission.status = 'published'
                                submission.published_at = datetime.datetime.utcnow()
                                submission.instagram_post_id = result.get('media_id')
                                db.session.commit()
                                logger.info(f'Promo post #{submission.id} auto-published to Instagram!')
                            else:
                                logger.error(f'Auto-publish failed for promo #{submission.id}: {result.get("error")}')
                        else:
                            logger.warning('Instagram API not configured, promo post saved but not published')
                    except Exception as pub_err:
                        logger.error(f'Promo auto-publish error: {pub_err}')
                else:
                    db.session.commit()

                logger.info(f'Payment confirmed via redirect for session {session_id}')
        except Exception as e:
            logger.error(f'Error updating payment on redirect: {e}')

    return render_template('payment_success.html')


@main_bp.route('/payment/cancel')
def payment_cancel():
    """Payment cancelled page."""
    flash('Payment was cancelled. Your submission is saved as a draft.', 'warning')
    return redirect(url_for('main.index'))


@main_bp.route('/track')
def track_submission():
    """Track submissions by email — no login needed."""
    email = request.args.get('email', '').strip()
    submissions = []
    if email:
        submissions = Submission.query.filter_by(submitter_email=email)\
            .order_by(Submission.created_at.desc()).all()
    return render_template('track.html', email=email, submissions=submissions)


@main_bp.route('/about')
def about():
    return render_template('about.html')


@main_bp.route('/terms')
def terms():
    return render_template('terms.html')


@main_bp.route('/uploads/<path:filepath>')
def serve_public_media(filepath):
    """Serve uploaded media publicly — needed for Instagram to fetch images."""
    upload_dir = current_app.config['UPLOAD_FOLDER']
    return send_from_directory(upload_dir, filepath)


@main_bp.route('/api/check-content', methods=['POST'])
@limiter.limit("30 per minute")
def check_content():
    """Real-time content moderation using LLM (Gemini) — checks caption before submission."""
    try:
        data = request.get_json()
        caption = (data or {}).get('caption', '').strip()

        if not caption or len(caption) < 5:
            return jsonify({'flagged': False})

        # First, quick local checks (profanity, blacklist)
        from better_profanity import profanity
        if profanity.contains_profanity(caption):
            return jsonify({
                'flagged': True,
                'reason': '🚫 Your content contains inappropriate language and violates our community guidelines. Please revise your caption.'
            })

        # Check dangerous phrases (same list as server-side blocking)
        import re as _re
        DANGEROUS_PHRASES = [
            r'sell(?:ing)?\s+drugs?', r'buy(?:ing)?\s+drugs?', r'drug\s+deal', r'weed\s+for\s+sale',
            r'cocaine', r'heroin', r'meth(?:amphetamine)?', r'fentanyl', r'ecstasy', r'lsd',
            r'sell(?:ing)?\s+weed', r'buy(?:ing)?\s+weed', r'sell(?:ing)?\s+pills?',
            r'sell(?:ing)?\s+guns?', r'buy(?:ing)?\s+guns?', r'sell(?:ing)?\s+weapons?',
            r'illegal\s+firearms?', r'buy(?:ing)?\s+firearms?',
            r'kill\s+(?:him|her|them|you|someone|people|all)', r'murder\s+(?:him|her|them|you|someone)',
            r'shoot(?:ing)?\s+(?:up|people|someone)', r'bomb\s+threat', r'mass\s+shooting',
            r'death\s+to', r'i\s+will\s+kill',
            r'child\s+(?:porn|exploitation)', r'human\s+trafficking', r'sex\s+trafficking',
            r'underage', r'minors?\s+for\s+sale',
            r'how\s+to\s+(?:kill|harm)\s+(?:your|my)self', r'suicide\s+method',
            r'go\s+back\s+to\s+your\s+country', r'(?:white|black)\s+suprema',
            r'ethnic\s+cleansing', r'genocide',
            r'send\s+(?:me\s+)?(?:your\s+)?(?:bank|credit\s+card|ssn|social\s+security)',
            r'wire\s+(?:me\s+)?money', r'nigerian?\s+prince',
        ]
        caption_lower = caption.lower()
        for pattern in DANGEROUS_PHRASES:
            if _re.search(pattern, caption_lower):
                return jsonify({
                    'flagged': True,
                    'reason': '🚫 Your content contains prohibited material and cannot be submitted.'
                })

        # Check blacklisted keywords
        blacklisted = BlacklistedKeyword.query.filter_by(is_active=True).all()
        for bk in blacklisted:
            if bk.keyword.lower() in caption_lower:
                return jsonify({
                    'flagged': True,
                    'reason': f'🚫 Your content contains a restricted word ("{bk.keyword}") and cannot be submitted.'
                })

        # LLM-based deep check using Gemini
        try:
            gemini_key = current_app.config.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY')
            if gemini_key:
                from google import genai
                client = genai.Client(api_key=gemini_key)
                prompt = f"""You are a content moderation system. Analyze this Instagram caption and determine if it violates any community guidelines.

Check for:
1. Hate speech, racism, discrimination
2. Violence or threats
3. Sexual/explicit content
4. Harassment or bullying
5. Misinformation or dangerous advice
6. Illegal activities promotion
7. Self-harm or suicide references

Caption to check: "{caption}"

Respond ONLY with a JSON object:
- If safe: {{"flagged": false}}
- If violated: {{"flagged": true, "reason": "Brief explanation of the violation"}}

IMPORTANT: Respond with ONLY the JSON, no markdown or extra text."""

                response = client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=prompt
                )

                import json
                response_text = response.text.strip()
                # Clean markdown if present
                if response_text.startswith('```'):
                    response_text = response_text.split('\n', 1)[-1].rsplit('```', 1)[0].strip()

                result = json.loads(response_text)
                if result.get('flagged'):
                    return jsonify({
                        'flagged': True,
                        'reason': f"🚫 {result.get('reason', 'Content violates community guidelines.')}"
                    })
        except Exception as llm_err:
            logger.error(f'LLM moderation check error: {llm_err}')
            # Don't block submission if LLM fails

        return jsonify({'flagged': False})

    except Exception as e:
        logger.error(f'Content check error: {e}')
        return jsonify({'flagged': False})


@main_bp.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@main_bp.errorhandler(413)
def too_large(e):
    flash('File too large. Maximum size is 16MB.', 'error')
    return redirect(url_for('main.index'))
