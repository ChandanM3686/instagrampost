"""
Admin dashboard routes.
"""

import os
import json
import logging
import datetime
import bcrypt
from functools import wraps
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, current_app, send_from_directory, jsonify
)
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import (
    User, Submission, Payment, ModerationLog,
    BlacklistedKeyword, SystemSetting
)

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    """Decorator: require admin or moderator role."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role not in ('admin', 'moderator'):
            flash('Access denied.', 'error')
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated


def admin_only(f):
    """Decorator: require admin role only."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('admin.dashboard'))
        return f(*args, **kwargs)
    return decorated


# ───────────── Auth ─────────────

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            login_user(user, remember=True)
            logger.info(f'Admin login: {email}')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Invalid credentials.', 'error')

    return render_template('admin/login.html')


@admin_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('admin.login'))


# ───────────── Dashboard ─────────────

@admin_bp.route('/')
@admin_required
def dashboard():
    """Main admin dashboard with analytics."""
    total_submissions = Submission.query.count()
    pending_count = Submission.query.filter_by(status='pending').count()
    approved_count = Submission.query.filter_by(status='approved').count()
    published_count = Submission.query.filter_by(status='published').count()
    rejected_count = Submission.query.filter_by(status='rejected').count()
    flagged_count = Submission.query.filter_by(status='flagged').count()

    free_count = Submission.query.filter_by(post_type='free').count()
    paid_count = Submission.query.filter_by(post_type='promotional').count()

    total_revenue = db.session.query(db.func.sum(Payment.amount)).filter_by(status='completed').scalar() or 0

    recent_submissions = Submission.query.order_by(Submission.created_at.desc()).limit(10).all()

    return render_template('admin/dashboard.html',
                           total_submissions=total_submissions,
                           pending_count=pending_count,
                           approved_count=approved_count,
                           published_count=published_count,
                           rejected_count=rejected_count,
                           flagged_count=flagged_count,
                           free_count=free_count,
                           paid_count=paid_count,
                           total_revenue=total_revenue,
                           recent_submissions=recent_submissions)


# ───────────── Submissions ─────────────

@admin_bp.route('/submissions')
@admin_required
def submissions():
    """View all submissions with filtering."""
    status_filter = request.args.get('status', 'all')
    type_filter = request.args.get('type', 'all')
    page = request.args.get('page', 1, type=int)

    query = Submission.query

    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    if type_filter != 'all':
        query = query.filter_by(post_type=type_filter)

    submissions = query.order_by(Submission.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template('admin/submissions.html',
                           submissions=submissions,
                           current_status=status_filter,
                           current_type=type_filter)


@admin_bp.route('/submissions/<int:sub_id>')
@admin_required
def submission_detail(sub_id):
    """View single submission details."""
    submission = Submission.query.get_or_404(sub_id)
    mod_logs = ModerationLog.query.filter_by(submission_id=sub_id).all()
    return render_template('admin/submission_detail.html',
                           submission=submission,
                           mod_logs=mod_logs)


@admin_bp.route('/submissions/<int:sub_id>/approve', methods=['POST'])
@admin_required
def approve_submission(sub_id):
    """Approve a submission."""
    submission = Submission.query.get_or_404(sub_id)
    new_caption = request.form.get('caption', '').strip()

    if new_caption:
        submission.caption = new_caption

    submission.status = 'approved'
    submission.reviewed_by = current_user.id
    db.session.commit()

    flash(f'Submission #{sub_id} approved.', 'success')
    logger.info(f'Submission #{sub_id} approved by {current_user.email}')
    return redirect(url_for('admin.submission_detail', sub_id=sub_id))


@admin_bp.route('/submissions/<int:sub_id>/reject', methods=['POST'])
@admin_required
def reject_submission(sub_id):
    """Reject a submission."""
    submission = Submission.query.get_or_404(sub_id)
    submission.status = 'rejected'
    submission.reviewed_by = current_user.id
    db.session.commit()

    flash(f'Submission #{sub_id} rejected.', 'warning')
    logger.info(f'Submission #{sub_id} rejected by {current_user.email}')
    return redirect(url_for('admin.submission_detail', sub_id=sub_id))


# ───────────── AI Caption Generation ─────────────

@admin_bp.route('/submissions/<int:sub_id>/generate-caption', methods=['POST'])
@admin_required
def generate_caption(sub_id):
    """Generate an AI caption for a submission using Gemini."""
    submission = Submission.query.get_or_404(sub_id)

    try:
        from app.services.caption_ai import CaptionGenerator
        generator = CaptionGenerator()

        style = request.form.get('caption_style', 'engaging')
        image_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            submission.image_path
        )

        if not os.path.exists(image_path):
            return jsonify({'success': False, 'error': 'Image file not found'}), 400

        # Generate caption from image
        result = generator.generate_caption(
            image_path=image_path,
            user_caption=submission.caption or '',
            style=style
        )

        if result['success']:
            logger.info(f'AI caption generated for submission #{sub_id}')
            return jsonify({'success': True, 'caption': result['caption']})
        else:
            return jsonify({'success': False, 'error': result['error']}), 400

    except Exception as e:
        logger.error(f'Caption generation error for #{sub_id}: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/submissions/<int:sub_id>/enhance-caption', methods=['POST'])
@admin_required
def enhance_caption(sub_id):
    """Enhance an existing caption using Gemini AI."""
    submission = Submission.query.get_or_404(sub_id)

    try:
        from app.services.caption_ai import CaptionGenerator
        generator = CaptionGenerator()

        current_caption = request.form.get('current_caption', submission.caption or '')
        image_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            submission.image_path
        )

        result = generator.enhance_caption(
            existing_caption=current_caption,
            image_path=image_path if os.path.exists(image_path) else None
        )

        if result['success']:
            return jsonify({'success': True, 'caption': result['caption']})
        else:
            return jsonify({'success': False, 'error': result['error']}), 400

    except Exception as e:
        logger.error(f'Caption enhance error for #{sub_id}: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/submissions/<int:sub_id>/publish', methods=['POST'])
@admin_required
def publish_submission(sub_id):
    """Publish a submission to Instagram with auto-generated AI caption."""
    submission = Submission.query.get_or_404(sub_id)

    if submission.status not in ('approved', 'pending', 'flagged'):
        flash('Submission must be approved first.', 'error')
        return redirect(url_for('admin.submission_detail', sub_id=sub_id))

    try:
        from app.services.instagram import InstagramService
        ig = InstagramService()

        if not ig.is_configured():
            flash('Instagram API not configured. Add INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_ACCOUNT_ID to your .env file.', 'error')
            return redirect(url_for('admin.submission_detail', sub_id=sub_id))

        # Get image path
        local_image_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            submission.image_path
        )

        if not os.path.exists(local_image_path):
            flash('Image file not found on server.', 'error')
            return redirect(url_for('admin.submission_detail', sub_id=sub_id))

        # ── Auto-generate caption using Gemini AI ──
        use_auto_caption = 'auto_caption' in request.form
        caption_style = request.form.get('caption_style', 'engaging')
        final_caption = submission.caption or ''

        if use_auto_caption:
            try:
                from app.services.caption_ai import CaptionGenerator
                generator = CaptionGenerator()
                
                logger.info(f'Auto-generating caption for submission #{sub_id} (style: {caption_style})')
                result = generator.generate_caption(
                    image_path=local_image_path,
                    user_caption=submission.caption or '',
                    style=caption_style
                )

                if result['success']:
                    final_caption = result['caption']
                    # Save the AI caption to the submission
                    submission.caption = final_caption
                    db.session.commit()
                    logger.info(f'AI caption generated for #{sub_id}')
                    flash(f'🤖 AI caption generated successfully!', 'info')
                else:
                    logger.warning(f'AI caption failed for #{sub_id}: {result.get("error")}. Using original caption.')
                    flash(f'⚠️ AI caption failed ({result.get("error", "unknown")}), using original caption.', 'warning')
            except Exception as caption_err:
                logger.warning(f'AI caption error for #{sub_id}: {caption_err}. Using original caption.')
                flash(f'⚠️ AI caption unavailable, using original caption.', 'warning')

        # ── Check for manual URL override ──
        manual_image_url = request.form.get('image_url', '').strip()

        if manual_image_url:
            if submission.video_path:
                video_url = request.form.get('video_url', '')
                result = ig.publish_video(video_url, final_caption)
            else:
                result = ig.publish_image(manual_image_url, final_caption)
        else:
            # Auto-publish from local file
            video_path = None
            if submission.video_path:
                video_path = os.path.join(
                    current_app.config['UPLOAD_FOLDER'],
                    submission.video_path
                )

            result = ig.publish_from_local(local_image_path, final_caption, video_path)

        if result['success']:
            submission.status = 'published'
            submission.instagram_post_id = result.get('instagram_post_id', '')
            submission.published_at = datetime.datetime.utcnow()
            db.session.commit()

            flash(f'✅ Published to Instagram! Post ID: {submission.instagram_post_id}', 'success')
            logger.info(f'Submission #{sub_id} published to Instagram')
        else:
            flash(f'Instagram publishing failed: {result.get("error", "Unknown error")}', 'error')
            logger.error(f'Instagram publish failed for #{sub_id}: {result}')

    except Exception as e:
        flash(f'Publishing error: {str(e)}', 'error')
        logger.error(f'Publish error for #{sub_id}: {e}', exc_info=True)

    return redirect(url_for('admin.submission_detail', sub_id=sub_id))


# ───────────── Payments ─────────────

@admin_bp.route('/payments')
@admin_required
def payments():
    """View payment history."""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')

    query = Payment.query
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)

    payments = query.order_by(Payment.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    total_revenue = db.session.query(db.func.sum(Payment.amount)).filter_by(status='completed').scalar() or 0

    return render_template('admin/payments.html',
                           payments=payments,
                           total_revenue=total_revenue,
                           current_status=status_filter)


# ───────────── Blacklist ─────────────

@admin_bp.route('/blacklist')
@admin_required
def blacklist():
    """Manage blacklisted keywords."""
    keywords = BlacklistedKeyword.query.order_by(BlacklistedKeyword.created_at.desc()).all()
    return render_template('admin/blacklist.html', keywords=keywords)


@admin_bp.route('/blacklist/add', methods=['POST'])
@admin_required
def add_blacklist():
    """Add a keyword to blacklist."""
    keyword = request.form.get('keyword', '').strip().lower()
    category = request.form.get('category', 'general')

    if not keyword:
        flash('Keyword cannot be empty.', 'error')
        return redirect(url_for('admin.blacklist'))

    existing = BlacklistedKeyword.query.filter_by(keyword=keyword).first()
    if existing:
        flash('Keyword already exists.', 'warning')
        return redirect(url_for('admin.blacklist'))

    bk = BlacklistedKeyword(
        keyword=keyword,
        category=category,
        added_by=current_user.id
    )
    db.session.add(bk)
    db.session.commit()

    flash(f'Keyword "{keyword}" added to blacklist.', 'success')
    return redirect(url_for('admin.blacklist'))


@admin_bp.route('/blacklist/<int:bk_id>/delete', methods=['POST'])
@admin_required
def delete_blacklist(bk_id):
    """Remove a keyword from blacklist."""
    bk = BlacklistedKeyword.query.get_or_404(bk_id)
    db.session.delete(bk)
    db.session.commit()

    flash(f'Keyword "{bk.keyword}" removed.', 'success')
    return redirect(url_for('admin.blacklist'))


@admin_bp.route('/blacklist/<int:bk_id>/toggle', methods=['POST'])
@admin_required
def toggle_blacklist(bk_id):
    """Toggle keyword active status."""
    bk = BlacklistedKeyword.query.get_or_404(bk_id)
    bk.is_active = not bk.is_active
    db.session.commit()

    status = 'activated' if bk.is_active else 'deactivated'
    flash(f'Keyword "{bk.keyword}" {status}.', 'success')
    return redirect(url_for('admin.blacklist'))


# ───────────── Settings ─────────────

@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_only
def settings():
    """System settings management."""
    if request.method == 'POST':
        for key in request.form:
            if key.startswith('setting_'):
                setting_key = key.replace('setting_', '')
                SystemSetting.set(setting_key, request.form[key])

        flash('Settings updated.', 'success')
        return redirect(url_for('admin.settings'))

    all_settings = SystemSetting.query.all()
    settings_dict = {s.key: s.value for s in all_settings}

    return render_template('admin/settings.html', settings=settings_dict)


# ───────────── Users ─────────────

@admin_bp.route('/users')
@admin_only
def users():
    """Manage admin users."""
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/users/add', methods=['POST'])
@admin_only
def add_user():
    """Add a new admin user."""
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'viewer')

    if not email or not password:
        flash('Email and password are required.', 'error')
        return redirect(url_for('admin.users'))

    existing = User.query.filter_by(email=email).first()
    if existing:
        flash('User already exists.', 'warning')
        return redirect(url_for('admin.users'))

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    user = User(
        email=email,
        password_hash=hashed.decode('utf-8'),
        role=role,
        is_active=True
    )
    db.session.add(user)
    db.session.commit()

    flash(f'User {email} created with role: {role}', 'success')
    return redirect(url_for('admin.users'))


# ───────────── Media serving ─────────────

@admin_bp.route('/media/<path:filepath>')
@admin_required
def serve_media(filepath):
    """Serve uploaded media for admin preview."""
    upload_dir = current_app.config['UPLOAD_FOLDER']
    return send_from_directory(upload_dir, filepath)
