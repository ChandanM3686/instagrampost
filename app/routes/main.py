"""
Main routes — public-facing submission form and pages.
"""

import os
import uuid
import logging
import traceback
import requests
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, current_app, jsonify
)
from werkzeug.utils import secure_filename
from app import db, limiter
from app.models import Submission, Payment, SystemSetting
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
    """Homepage with submission form."""
    recaptcha_key = current_app.config.get('RECAPTCHA_SITE_KEY', '')
    stripe_key = current_app.config.get('STRIPE_PUBLISHABLE_KEY', '')
    return render_template('index.html',
                           recaptcha_key=recaptcha_key,
                           stripe_key=stripe_key)


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

        # Determine promo amount
        promo_amount = 0.0
        if post_type == 'promotional':
            try:
                promo_amount = float(request.form.get('promo_amount', '1.00'))
                promo_amount = max(1.0, min(promo_amount, 2.0))  # Clamp to $1-$2
            except ValueError:
                promo_amount = 1.0

        # Create submission
        import json as json_lib
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
            status='payment_pending' if post_type == 'promotional' else 'pending'
        )
        db.session.add(submission)
        db.session.commit()

        logger.info(f'Submission created: #{submission.id} type={post_type} email={submitter_email}')

        # Run moderation checks
        try:
            engine = ModerationEngine(submission.id)
            passed, results = engine.run_all_checks()
            if not passed:
                logger.info(f'Submission {submission.id} flagged by moderation')
        except Exception as mod_err:
            logger.error(f'Moderation error (non-fatal): {mod_err}')

        # If promotional, redirect to Stripe
        if post_type == 'promotional':
            try:
                import stripe
                stripe.api_key = current_app.config['STRIPE_SECRET_KEY']

                logger.info(f'Creating Stripe checkout for submission #{submission.id}, amount=${promo_amount}')

                session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': 'usd',
                            'unit_amount': int(promo_amount * 100),
                            'product_data': {
                                'name': 'SasksVoice Promotional Post',
                                'description': f'Promotional post #{submission.id}',
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
                # Still save the submission, just mark it
                flash(f'Payment setup failed: {str(stripe_err)}. Your submission is saved.', 'error')
                return redirect(url_for('main.index'))

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
    return render_template('success.html')


@main_bp.route('/payment/success')
def payment_success():
    """Payment success redirect page."""
    session_id = request.args.get('session_id')
    if session_id:
        # Update payment status
        try:
            payment = Payment.query.filter_by(stripe_session_id=session_id).first()
            if payment:
                payment.status = 'completed'
                submission = Submission.query.get(payment.submission_id)
                if submission and submission.status == 'payment_pending':
                    submission.status = 'pending'
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


@main_bp.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@main_bp.errorhandler(413)
def too_large(e):
    flash('File too large. Maximum size is 16MB.', 'error')
    return redirect(url_for('main.index'))
