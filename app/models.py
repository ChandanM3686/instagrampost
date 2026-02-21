import datetime
from flask_login import UserMixin
from app import db


class User(UserMixin, db.Model):
    """Admin users for the dashboard."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='viewer')  # admin, moderator, viewer
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def __repr__(self):
        return f'<User {self.email}>'


class Submission(db.Model):
    """User content submissions."""
    __tablename__ = 'submissions'

    id = db.Column(db.Integer, primary_key=True)
    # Submitter info
    submitter_name = db.Column(db.String(100), nullable=True)
    submitter_email = db.Column(db.String(255), nullable=True)
    submitter_ip = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)

    # Content
    caption = db.Column(db.Text, nullable=False)
    original_caption = db.Column(db.Text, nullable=True)
    image_path = db.Column(db.String(500), nullable=False)
    video_path = db.Column(db.String(500), nullable=True)
    image_hash = db.Column(db.String(64), nullable=True)

    # Post type
    post_type = db.Column(db.String(20), nullable=False, default='free')  # free, promotional
    promo_amount = db.Column(db.Float, nullable=True, default=0.0)

    # Status
    status = db.Column(db.String(20), nullable=False, default='pending')
    # pending, approved, rejected, published, flagged, payment_pending

    # Moderation
    moderation_score = db.Column(db.Float, nullable=True, default=0.0)
    moderation_flags = db.Column(db.Text, nullable=True)  # JSON string
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Instagram
    instagram_post_id = db.Column(db.String(100), nullable=True)
    instagram_media_url = db.Column(db.String(500), nullable=True)
    published_at = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    payment = db.relationship('Payment', backref='submission', uselist=False, lazy=True)
    moderation_logs = db.relationship('ModerationLog', backref='submission', lazy=True)
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])

    def __repr__(self):
        return f'<Submission {self.id} - {self.status}>'

    @property
    def is_paid(self):
        return self.post_type == 'promotional' and self.payment and self.payment.status == 'completed'

    @property
    def can_publish(self):
        if self.post_type == 'promotional':
            return self.status == 'approved' and self.is_paid
        return self.status == 'approved'


class Payment(db.Model):
    """Payment records for promotional posts."""
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False)

    stripe_session_id = db.Column(db.String(255), nullable=True, index=True)
    stripe_payment_intent_id = db.Column(db.String(255), nullable=True)
    stripe_charge_id = db.Column(db.String(255), nullable=True)

    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='usd')
    status = db.Column(db.String(20), nullable=False, default='pending')
    # pending, completed, failed, refunded

    payer_email = db.Column(db.String(255), nullable=True)
    metadata_json = db.Column(db.Text, nullable=True)  # JSON

    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def __repr__(self):
        return f'<Payment {self.id} - {self.status} - ${self.amount}>'


class ModerationLog(db.Model):
    """Logs for content moderation actions."""
    __tablename__ = 'moderation_logs'

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False)

    check_type = db.Column(db.String(50), nullable=False)
    # harmful_text, hate_speech, spam, duplicate, blacklist, link, image
    result = db.Column(db.String(20), nullable=False)  # pass, fail, warning
    score = db.Column(db.Float, nullable=True)
    details = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f'<ModerationLog {self.check_type} - {self.result}>'


class BlacklistedKeyword(db.Model):
    """Keywords blocked from submissions."""
    __tablename__ = 'blacklisted_keywords'

    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.String(100), nullable=False, unique=True, index=True)
    category = db.Column(db.String(50), default='general')  # general, hate, spam, adult
    added_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f'<BlacklistedKeyword {self.keyword}>'


class SystemSetting(db.Model):
    """Application settings manageable from admin."""
    __tablename__ = 'system_settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def __repr__(self):
        return f'<SystemSetting {self.key}={self.value}>'

    @staticmethod
    def get(key, default=None):
        setting = SystemSetting.query.filter_by(key=key).first()
        return setting.value if setting else default

    @staticmethod
    def set(key, value):
        setting = SystemSetting.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = SystemSetting(key=key, value=value)
            db.session.add(setting)
        db.session.commit()
