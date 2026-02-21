# SPKR — Community Content Platform

A production-ready community submission platform where users submit posts (image/video + caption) through the website, and content is published to an Instagram Business account via Meta Graph API.

---

## 🏗️ Project Structure

```
insta/
├── run.py                    # Application entry point
├── config.py                 # Configuration classes
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (DO NOT commit)
├── .env.example              # Environment template
│
├── app/
│   ├── __init__.py           # Flask app factory, extensions, seeding
│   ├── models.py             # Database models (User, Submission, Payment, etc.)
│   │
│   ├── routes/
│   │   ├── main.py           # Public routes (homepage, submit, success)
│   │   ├── admin.py          # Admin dashboard routes
│   │   ├── api.py            # REST API endpoints
│   │   └── webhook.py        # Stripe webhook handler
│   │
│   └── services/
│       ├── moderation.py     # Content moderation engine
│       ├── instagram.py      # Instagram Graph API service
│       └── payment.py        # Stripe payment service
│
├── templates/
│   ├── base.html             # Public site base template
│   ├── index.html            # Home + submission form
│   ├── success.html          # Submission success page
│   ├── payment_success.html  # Payment confirmation page
│   ├── about.html            # About page
│   ├── terms.html            # Terms of service
│   ├── 404.html              # Error page
│   │
│   └── admin/
│       ├── base.html         # Admin base template (sidebar)
│       ├── login.html        # Admin login
│       ├── dashboard.html    # Analytics dashboard
│       ├── submissions.html  # Submissions list
│       ├── submission_detail.html  # Single submission view
│       ├── payments.html     # Payment history
│       ├── blacklist.html    # Keyword blacklist manager
│       ├── settings.html     # System settings
│       └── users.html        # User management
│
├── static/
│   ├── css/
│   │   ├── main.css          # Public site styles
│   │   └── admin.css         # Admin dashboard styles
│   └── js/
│       ├── main.js           # Public site scripts
│       ├── submission.js     # Form interaction scripts
│       └── admin.js          # Admin dashboard scripts
│
├── uploads/                  # Media storage (auto-created)
│   ├── images/
│   └── videos/
│
└── logs/                     # Application logs (auto-created)
```

---

## 🚀 Quick Start (Step-by-Step Setup)

### 1. Prerequisites
- Python 3.10+
- pip
- PostgreSQL (optional, SQLite works for development)

### 2. Install Dependencies

```bash
cd insta
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy the example env and fill in your values
cp .env.example .env

# Edit .env with your API keys:
# - Meta/Instagram API credentials
# - Stripe API keys
# - reCAPTCHA keys (optional)
# - Admin credentials
```

### 4. Run the Application

```bash
python run.py
```

The app will:
- Create the SQLite database automatically
- Seed the default admin user
- Set up default system settings
- Start on http://localhost:5000

### 5. Access the Admin Dashboard

Navigate to: **http://localhost:5000/admin**

Default credentials:
- Email: `admin@spkr.local`
- Password: `admin123`

---

## 🔑 Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Flask secret key | Yes |
| `DATABASE_URL` | Database connection string | Yes |
| `META_APP_ID` | Meta App ID | For IG posting |
| `META_APP_SECRET` | Meta App Secret | For IG posting |
| `INSTAGRAM_ACCOUNT_ID` | IG Business Account ID | For IG posting |
| `INSTAGRAM_ACCESS_TOKEN` | Long-lived access token | For IG posting |
| `STRIPE_PUBLISHABLE_KEY` | Stripe public key | For payments |
| `STRIPE_SECRET_KEY` | Stripe secret key | For payments |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret | For payments |
| `RECAPTCHA_SITE_KEY` | reCAPTCHA site key | Optional |
| `RECAPTCHA_SECRET_KEY` | reCAPTCHA secret key | Optional |
| `ADMIN_EMAIL` | Default admin email | Yes |
| `ADMIN_PASSWORD` | Default admin password | Yes |

---

## 📋 API Routes

### Public
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Homepage with submission form |
| POST | `/submit` | Submit a post (rate limited: 10/hr) |
| GET | `/success` | Success page |
| GET | `/payment/success` | Payment confirmation |
| GET | `/payment/cancel` | Payment cancelled |
| GET | `/about` | About page |
| GET | `/terms` | Terms of service |

### Admin (`/admin`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/admin/login` | Admin login |
| GET | `/admin/logout` | Logout |
| GET | `/admin/` | Dashboard with analytics |
| GET | `/admin/submissions` | List all submissions |
| GET | `/admin/submissions/<id>` | Submission detail |
| POST | `/admin/submissions/<id>/approve` | Approve submission |
| POST | `/admin/submissions/<id>/reject` | Reject submission |
| POST | `/admin/submissions/<id>/publish` | Publish to Instagram |
| GET | `/admin/payments` | Payment history |
| GET | `/admin/blacklist` | Keyword blacklist |
| POST | `/admin/blacklist/add` | Add keyword |
| GET | `/admin/settings` | System settings |
| GET | `/admin/users` | User management |

### API (`/api`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/submissions/stats` | Submission statistics (JSON) |
| GET | `/api/submissions/<id>/moderation` | Moderation details (JSON) |

### Webhook (`/webhook`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/webhook/stripe` | Stripe webhook handler |

---

## 🛡️ Security Features

- **CSRF Protection**: All forms include CSRF tokens
- **Rate Limiting**: 10 submissions/hour, 200 requests/day per IP
- **Webhook Verification**: Stripe signature verification
- **Password Hashing**: bcrypt
- **IP Logging**: Stored with each submission
- **File Validation**: Extension and size checks
- **Role-Based Access**: admin, moderator, viewer roles
- **Input Sanitization**: Bleach for HTML stripping

---

## 🤖 Content Moderation Pipeline

1. **Profanity Check** — Uses `better-profanity` library
2. **Hate Speech Detection** — Pattern-based detection
3. **Spam Detection** — Common spam pattern matching
4. **Blacklisted Keywords** — Admin-configurable keyword blocking
5. **Link Blocking** — Optional URL detection and blocking
6. **Duplicate Detection** — Perceptual image hashing (pHash)
7. **Caption Length** — Configurable character limits

Posts with any **fail** result are automatically **flagged** for review.

---

## 📱 Instagram Publishing Flow

1. Admin approves a submission
2. Admin provides a public URL for the image
3. System creates a media container via Graph API
4. Polls container status until `FINISHED`
5. Publishes container to Instagram
6. Stores Instagram post ID

---

## 💳 Stripe Payment Flow

1. User selects "Promotional Post" ($1-$2)
2. System creates a Stripe Checkout session
3. User completes payment on Stripe
4. Stripe sends webhook to `/webhook/stripe`
5. System verifies signature and updates payment status
6. Submission moves to review queue with priority

---

## 🗄️ Database Schema

- **Users** — Admin accounts with roles (admin, moderator, viewer)
- **Submissions** — Content with status tracking, moderation scores, IG post IDs
- **Payments** — Stripe transaction records
- **ModerationLogs** — Per-check results for each submission
- **BlacklistedKeywords** — Admin-managed keyword blocks
- **SystemSettings** — Key-value configuration store

---

## 🚢 Production Deployment

```bash
# Use gunicorn
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 run:app

# Use PostgreSQL
DATABASE_URL=postgresql://user:pass@localhost:5432/spkr_db

# Set production config
FLASK_ENV=production
SECRET_KEY=your-long-random-secret-key
```

For Stripe webhooks in production:
```bash
# Set your webhook endpoint in Stripe Dashboard to:
https://yourdomain.com/webhook/stripe
```
