"""
Content Moderation Engine
Handles all pre-publish content checks:
- Harmful/toxic text detection
- Hate speech detection
- Spam detection
- Duplicate content detection
- Keyword blacklist checking
- Link blocking
- Image moderation
"""

import re
import json
import hashlib
import logging
try:
    from better_profanity import profanity
    profanity.load_censor_words()
    HAS_PROFANITY = True
except ImportError:
    HAS_PROFANITY = False

from app.models import BlacklistedKeyword, ModerationLog, Submission
from app import db

logger = logging.getLogger(__name__)

# Common spam patterns
SPAM_PATTERNS = [
    r'(?i)buy\s+now', r'(?i)click\s+here', r'(?i)free\s+money',
    r'(?i)make\s+\$?\d+', r'(?i)earn\s+\$?\d+', r'(?i)(viagra|cialis)',
    r'(?i)limited\s+time\s+offer', r'(?i)act\s+now', r'(?i)winner',
    r'(?i)congratulations.*won', r'(?i)100%\s+free',
]

# URL pattern
URL_PATTERN = re.compile(
    r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+|'
    r'www\.[\w\-]+\.[\w\-]+', re.IGNORECASE
)

# Hate speech keywords (minimal built-in set, admin can extend via blacklist)
HATE_INDICATORS = [
    'kill\\s+all', 'death\\s+to', 'go\\s+back\\s+to\\s+your\\s+country',
]


class ModerationEngine:
    """Pipeline to moderate content before publishing."""

    def __init__(self, submission_id):
        self.submission = Submission.query.get(submission_id)
        self.results = []
        self.total_score = 0.0
        self.flagged = False

    def run_all_checks(self):
        """Run the full moderation pipeline. Returns (passed: bool, results: list)."""
        if not self.submission:
            return False, [{'check': 'system', 'result': 'fail', 'details': 'Submission not found'}]

        caption = self.submission.caption or ''

        self._check_profanity(caption)
        self._check_hate_speech(caption)
        self._check_spam(caption)
        self._check_blacklisted_keywords(caption)
        self._check_links(caption)
        self._check_duplicate_content()
        self._check_caption_length(caption)

        # Calculate final score
        fail_count = sum(1 for r in self.results if r['result'] == 'fail')
        warn_count = sum(1 for r in self.results if r['result'] == 'warning')
        self.total_score = (fail_count * 1.0 + warn_count * 0.3)

        # Update submission
        self.submission.moderation_score = self.total_score
        self.submission.moderation_flags = json.dumps(self.results)

        if fail_count > 0:
            self.submission.status = 'flagged'
            self.flagged = True
        elif warn_count >= 3:
            self.submission.status = 'flagged'
            self.flagged = True

        db.session.commit()

        passed = not self.flagged
        return passed, self.results

    def _log_check(self, check_type, result, score=0.0, details=''):
        """Log a moderation check to the database."""
        log = ModerationLog(
            submission_id=self.submission.id,
            check_type=check_type,
            result=result,
            score=score,
            details=details
        )
        db.session.add(log)
        self.results.append({
            'check': check_type,
            'result': result,
            'score': score,
            'details': details
        })

    def _check_profanity(self, text):
        """Check for profanity/harmful text."""
        if not HAS_PROFANITY:
            self._log_check('harmful_text', 'pass', 0.0, 'Profanity check skipped (library not installed)')
            return
        if profanity.contains_profanity(text):
            censored = profanity.censor(text)
            self._log_check('harmful_text', 'fail', 1.0,
                            f'Profanity detected. Censored: {censored[:200]}')
        else:
            self._log_check('harmful_text', 'pass', 0.0, 'No profanity detected')

    def _check_hate_speech(self, text):
        """Check for hate speech patterns."""
        for pattern in HATE_INDICATORS:
            if re.search(pattern, text, re.IGNORECASE):
                self._log_check('hate_speech', 'fail', 1.0,
                                f'Hate speech pattern detected: {pattern}')
                return
        self._log_check('hate_speech', 'pass', 0.0, 'No hate speech detected')

    def _check_spam(self, text):
        """Check for spam patterns."""
        spam_matches = []
        for pattern in SPAM_PATTERNS:
            if re.search(pattern, text):
                spam_matches.append(pattern)

        if len(spam_matches) >= 2:
            self._log_check('spam', 'fail', 1.0,
                            f'Multiple spam patterns detected: {len(spam_matches)}')
        elif len(spam_matches) == 1:
            self._log_check('spam', 'warning', 0.5,
                            f'Possible spam pattern detected')
        else:
            self._log_check('spam', 'pass', 0.0, 'No spam detected')

    def _check_blacklisted_keywords(self, text):
        """Check against admin-defined blacklisted keywords."""
        blacklisted = BlacklistedKeyword.query.filter_by(is_active=True).all()
        found = []

        text_lower = text.lower()
        for bk in blacklisted:
            if bk.keyword.lower() in text_lower:
                found.append(bk.keyword)

        if found:
            self._log_check('blacklist', 'fail', 1.0,
                            f'Blacklisted keywords found: {", ".join(found)}')
        else:
            self._log_check('blacklist', 'pass', 0.0, 'No blacklisted keywords')

    def _check_links(self, text):
        """Check for URLs/links in content."""
        from app.models import SystemSetting
        block_links = SystemSetting.get('block_links', 'true')

        urls = URL_PATTERN.findall(text)
        if urls and block_links == 'true':
            self._log_check('link', 'fail', 0.8,
                            f'Links found and blocked: {len(urls)} URL(s)')
        elif urls:
            self._log_check('link', 'warning', 0.3,
                            f'Links found: {len(urls)} URL(s)')
        else:
            self._log_check('link', 'pass', 0.0, 'No links detected')

    def _check_duplicate_content(self):
        """Check for duplicate submissions based on image hash."""
        if not self.submission.image_hash:
            self._log_check('duplicate', 'pass', 0.0, 'No image hash to compare')
            return

        duplicate = Submission.query.filter(
            Submission.id != self.submission.id,
            Submission.image_hash == self.submission.image_hash,
            Submission.status.in_(['approved', 'published', 'pending'])
        ).first()

        if duplicate:
            self._log_check('duplicate', 'fail', 1.0,
                            f'Duplicate image detected (matches submission #{duplicate.id})')
        else:
            self._log_check('duplicate', 'pass', 0.0, 'No duplicate content')

    def _check_caption_length(self, text):
        """Check caption length limits."""
        from app.models import SystemSetting
        max_len = int(SystemSetting.get('max_caption_length', '2200'))

        if len(text) > max_len:
            self._log_check('caption_length', 'fail', 0.5,
                            f'Caption too long: {len(text)}/{max_len} chars')
        elif len(text) < 3:
            self._log_check('caption_length', 'warning', 0.3,
                            'Caption too short (less than 3 chars)')
        else:
            self._log_check('caption_length', 'pass', 0.0,
                            f'Caption length OK: {len(text)} chars')


def compute_image_hash(image_path):
    """Compute perceptual hash of an image for duplicate detection."""
    try:
        import imagehash
        from PIL import Image
        img = Image.open(image_path)
        return str(imagehash.phash(img))
    except Exception as e:
        logger.error(f'Image hash computation failed: {e}')
        return hashlib.md5(open(image_path, 'rb').read()).hexdigest()
