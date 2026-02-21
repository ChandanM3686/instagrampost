"""
Stripe Payment Service
Handles checkout session creation and webhook processing.
"""

import time
import logging
import stripe
from flask import current_app

logger = logging.getLogger(__name__)


class PaymentService:
    """Service for Stripe payment processing."""

    def __init__(self):
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']

    def create_checkout_session(self, submission_id, amount, success_url, cancel_url):
        """
        Create a Stripe Checkout session for a promotional post.
        amount: float in dollars (e.g., 1.50)
        """
        try:
            amount_cents = int(amount * 100)

            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'unit_amount': amount_cents,
                        'product_data': {
                            'name': 'SPKR Promotional Post',
                            'description': f'Promotional post #{submission_id}',
                        },
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'submission_id': str(submission_id),
                    'post_type': 'promotional'
                },
            )

            logger.info(f'Checkout session created: {session.id} for submission {submission_id}')
            return {
                'success': True,
                'session_id': session.id,
                'checkout_url': session.url
            }

        except stripe.error.StripeError as e:
            logger.error(f'Stripe error: {e}')
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f'Payment error: {e}')
            return {'success': False, 'error': str(e)}

    @staticmethod
    def verify_webhook_signature(payload, sig_header):
        """Verify Stripe webhook signature."""
        webhook_secret = current_app.config['STRIPE_WEBHOOK_SECRET']

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            return {'success': True, 'event': event}
        except stripe.error.SignatureVerificationError as e:
            logger.error(f'Webhook signature verification failed: {e}')
            return {'success': False, 'error': 'Invalid signature'}
        except Exception as e:
            logger.error(f'Webhook error: {e}')
            return {'success': False, 'error': str(e)}

    @staticmethod
    def process_successful_payment(event):
        """Process a successful checkout session."""
        from app.models import Submission, Payment
        from app import db

        session = event['data']['object']
        submission_id = session.get('metadata', {}).get('submission_id')

        if not submission_id:
            logger.error('No submission_id in webhook metadata')
            return False

        submission = Submission.query.get(int(submission_id))
        if not submission:
            logger.error(f'Submission {submission_id} not found')
            return False

        # Update payment record
        payment = Payment.query.filter_by(stripe_session_id=session['id']).first()
        if payment:
            payment.status = 'completed'
            payment.stripe_payment_intent_id = session.get('payment_intent', '')
            payment.payer_email = session.get('customer_details', {}).get('email', '')
        else:
            # Create payment record if it doesn't exist
            payment = Payment(
                submission_id=int(submission_id),
                stripe_session_id=session['id'],
                stripe_payment_intent_id=session.get('payment_intent', ''),
                amount=session.get('amount_total', 0) / 100.0,
                currency=session.get('currency', 'usd'),
                status='completed',
                payer_email=session.get('customer_details', {}).get('email', '')
            )
            db.session.add(payment)

        # Update submission status
        if submission.status == 'payment_pending':
            submission.status = 'pending'

        db.session.commit()
        logger.info(f'Payment completed for submission {submission_id}')
        return True

    @staticmethod
    def get_payment_history(page=1, per_page=20):
        """Get paginated payment history."""
        from app.models import Payment
        return Payment.query.order_by(Payment.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
