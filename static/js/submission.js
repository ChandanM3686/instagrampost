/**
 * SPKR — Submission Form JavaScript
 * Handles: file upload preview, post type switching, character count, form validation
 */

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('submission-form');
    const imageInput = document.getElementById('image');
    const videoInput = document.getElementById('video');
    const captionInput = document.getElementById('caption');
    const charCount = document.getElementById('char-count');
    const submitBtn = document.getElementById('submit-btn');
    const promoOptions = document.getElementById('promo-options');

    // ───── Image Upload Preview ─────
    if (imageInput) {
        imageInput.addEventListener('change', function () {
            const file = this.files[0];
            if (file) {
                // Validate size
                if (file.size > 16 * 1024 * 1024) {
                    alert('Image too large. Maximum size is 16MB.');
                    this.value = '';
                    return;
                }

                // Validate type
                const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp'];
                if (!validTypes.includes(file.type)) {
                    alert('Invalid image format. Allowed: PNG, JPG, GIF, WebP');
                    this.value = '';
                    return;
                }

                const reader = new FileReader();
                reader.onload = (e) => {
                    document.getElementById('image-placeholder').style.display = 'none';
                    const preview = document.getElementById('image-preview');
                    preview.style.display = 'block';
                    document.getElementById('image-preview-img').src = e.target.result;
                };
                reader.readAsDataURL(file);
            }
        });

        // Drag and drop
        const imageZone = document.getElementById('image-upload-zone');
        if (imageZone) {
            ['dragenter', 'dragover'].forEach(event => {
                imageZone.addEventListener(event, (e) => {
                    e.preventDefault();
                    imageZone.classList.add('dragover');
                });
            });

            ['dragleave', 'drop'].forEach(event => {
                imageZone.addEventListener(event, (e) => {
                    e.preventDefault();
                    imageZone.classList.remove('dragover');
                });
            });

            imageZone.addEventListener('drop', (e) => {
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    imageInput.files = files;
                    imageInput.dispatchEvent(new Event('change'));
                }
            });
        }
    }

    // ───── Video Upload Preview ─────
    if (videoInput) {
        videoInput.addEventListener('change', function () {
            const file = this.files[0];
            if (file) {
                if (file.size > 16 * 1024 * 1024) {
                    alert('Video too large. Maximum size is 16MB.');
                    this.value = '';
                    return;
                }

                document.getElementById('video-placeholder').style.display = 'none';
                const preview = document.getElementById('video-preview');
                preview.style.display = 'flex';
                document.getElementById('video-name').textContent = file.name;
            }
        });
    }

    // ───── Character Count ─────
    if (captionInput && charCount) {
        captionInput.addEventListener('input', () => {
            const len = captionInput.value.length;
            charCount.textContent = len;
            charCount.style.color = len > 2000 ? '#ff5c6c' : len > 1800 ? '#ffb545' : '';
        });
    }

    // ───── Post Type Selection ─────
    const typeOptions = document.querySelectorAll('.type-option');
    const emailInput = document.getElementById('email');
    const emailBadge = document.getElementById('email-badge');
    const emailNote = document.getElementById('email-note');

    typeOptions.forEach(option => {
        option.addEventListener('click', () => {
            typeOptions.forEach(o => o.classList.remove('selected'));
            option.classList.add('selected');

            const radio = option.querySelector('input[type="radio"]');
            radio.checked = true;

            const isPromo = radio.value === 'promotional';

            if (promoOptions) {
                promoOptions.style.display = isPromo ? 'block' : 'none';
            }

            // Email becomes required for promo posts
            if (emailInput) {
                emailInput.required = isPromo;
            }
            if (emailBadge) {
                emailBadge.textContent = isPromo ? 'Required' : 'Optional';
                emailBadge.className = isPromo ? 'required-badge' : 'optional-badge';
            }
            if (emailNote) {
                emailNote.style.display = isPromo ? 'block' : 'none';
            }

            // Update submit button text
            if (submitBtn) {
                const btnText = submitBtn.querySelector('.btn-text');
                if (btnText) {
                    btnText.textContent = isPromo ? 'Proceed to Payment' : 'Submit Post';
                }
            }
        });
    });

    // ───── Form Submission ─────
    if (form) {
        form.addEventListener('submit', () => {
            const btnText = submitBtn.querySelector('.btn-text');
            const btnLoader = submitBtn.querySelector('.btn-loader');
            if (btnText) btnText.style.display = 'none';
            if (btnLoader) btnLoader.style.display = 'inline-flex';
            submitBtn.disabled = true;
        });
    }
});


// ───── Global Functions ─────

function removeImage() {
    const input = document.getElementById('image');
    input.value = '';
    document.getElementById('image-placeholder').style.display = 'flex';
    document.getElementById('image-preview').style.display = 'none';
}

function removeVideo() {
    const input = document.getElementById('video');
    input.value = '';
    document.getElementById('video-placeholder').style.display = 'flex';
    document.getElementById('video-preview').style.display = 'none';
}

function setAmount(btn, amount) {
    document.querySelectorAll('.amount-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('promo_amount').value = amount.toFixed(2);
}
