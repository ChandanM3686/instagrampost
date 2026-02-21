"""
Webhook routes — Stripe payment webhooks.
"""

import logging
from flask import Blueprint, request, jsonify
from app.services.payment import PaymentService

logger = logging.getLogger(__name__)
webhook_bp = Blueprint('webhook', __name__)


@webhook_bp.route('/stripe', methods=['POST'])
def stripe_webhook():
    """
    Handle Stripe webhook events.
    This endpoint is CSRF-exempt (see app/__init__.py).
    """
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature', '')

    if not sig_header:
        logger.warning('Stripe webhook received without signature')
        return jsonify({'error': 'No signature'}), 400

    result = PaymentService.verify_webhook_signature(payload, sig_header)

    if not result['success']:
        logger.warning(f'Stripe webhook signature verification failed')
        return jsonify({'error': result['error']}), 400

    event = result['event']
    event_type = event.get('type', '')

    logger.info(f'Stripe webhook event: {event_type}')

    if event_type == 'checkout.session.completed':
        PaymentService.process_successful_payment(event)
    elif event_type == 'checkout.session.expired':
        _handle_expired_session(event)
    elif event_type == 'charge.refunded':
        _handle_refund(event)

    return jsonify({'status': 'ok'}), 200


def _handle_expired_session(event):
    """Handle expired checkout sessions."""
    from app.models import Payment, Submission
    from app import db

    session = event['data']['object']
    payment = Payment.query.filter_by(
        stripe_session_id=session['id']
    ).first()

    if payment:
        payment.status = 'failed'
        submission = Submission.query.get(payment.submission_id)
        if submission and submission.status == 'payment_pending':
            submission.status = 'pending'  # Allow resubmission
        db.session.commit()
        logger.info(f'Payment expired for session {session["id"]}')


def _handle_refund(event):
    """Handle refund events."""
    from app.models import Payment
    from app import db

    charge = event['data']['object']
    payment = Payment.query.filter_by(
        stripe_charge_id=charge.get('id')
    ).first()

    if payment:
        payment.status = 'refunded'
        db.session.commit()
        logger.info(f'Payment refunded: {charge["id"]}')
