"""
API routes for AJAX calls and external integrations.
"""

import logging
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required
from app import db
from app.models import Submission, Payment, SystemSetting

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)


@api_bp.route('/submissions/stats')
@login_required
def submission_stats():
    """Get submission statistics for dashboard charts."""
    total = Submission.query.count()
    pending = Submission.query.filter_by(status='pending').count()
    approved = Submission.query.filter_by(status='approved').count()
    published = Submission.query.filter_by(status='published').count()
    rejected = Submission.query.filter_by(status='rejected').count()
    flagged = Submission.query.filter_by(status='flagged').count()

    free = Submission.query.filter_by(post_type='free').count()
    paid = Submission.query.filter_by(post_type='promotional').count()

    revenue = db.session.query(
        db.func.sum(Payment.amount)
    ).filter_by(status='completed').scalar() or 0

    return jsonify({
        'total': total,
        'pending': pending,
        'approved': approved,
        'published': published,
        'rejected': rejected,
        'flagged': flagged,
        'free': free,
        'paid': paid,
        'revenue': float(revenue)
    })


@api_bp.route('/submissions/<int:sub_id>/moderation')
@login_required
def submission_moderation(sub_id):
    """Get moderation details for a submission."""
    submission = Submission.query.get_or_404(sub_id)

    import json
    flags = json.loads(submission.moderation_flags) if submission.moderation_flags else []

    return jsonify({
        'submission_id': sub_id,
        'score': submission.moderation_score,
        'status': submission.status,
        'flags': flags
    })


@api_bp.route('/settings/<key>', methods=['GET'])
@login_required
def get_setting(key):
    """Get a system setting value."""
    value = SystemSetting.get(key)
    if value is None:
        return jsonify({'error': 'Setting not found'}), 404
    return jsonify({'key': key, 'value': value})
