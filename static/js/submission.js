/**
 * SPKR — Submission Form JavaScript
 * Handles: multi-image upload preview, post type switching, character count, form validation
 */

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('submission-form');
    const imagesInput = document.getElementById('images');
    const videoInput = document.getElementById('video');
    const captionInput = document.getElementById('caption');
    const charCount = document.getElementById('char-count');
    const submitBtn = document.getElementById('submit-btn');
    const promoOptions = document.getElementById('promo-options');

    // ───── Multi-Image Upload Preview ─────
    if (imagesInput) {
        imagesInput.addEventListener('change', function () {
            const files = Array.from(this.files);
            if (files.length === 0) return;

            // Validate total count
            if (files.length > 10) {
                alert('Maximum 10 images allowed. Please select fewer images.');
                this.value = '';
                return;
            }

            // Validate each file
            const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp'];
            for (const file of files) {
                if (file.size > 16 * 1024 * 1024) {
                    alert(`Image "${file.name}" is too large. Maximum size is 16MB.`);
                    this.value = '';
                    return;
                }
                if (!validTypes.includes(file.type)) {
                    alert(`Invalid format for "${file.name}". Allowed: PNG, JPG, GIF, WebP`);
                    this.value = '';
                    return;
                }
            }

            // Show preview grid
            const placeholder = document.getElementById('image-placeholder');
            const grid = document.getElementById('image-preview-grid');
            const clearBtn = document.getElementById('clear-images-btn');

            placeholder.style.display = 'none';
            grid.style.display = 'grid';
            grid.innerHTML = '';
            if (clearBtn) clearBtn.style.display = 'inline-flex';

            files.forEach((file, index) => {
                const reader = new FileReader();
                reader.onload = (e) => {
                    const item = document.createElement('div');
                    item.className = 'preview-grid-item';
                    item.innerHTML = `
                        <img src="${e.target.result}" alt="Preview ${index + 1}">
                        ${index === 0 ? '<span class="cover-badge">Cover</span>' : ''}
                        <span class="image-count-badge">${index + 1}</span>
                    `;
                    grid.appendChild(item);
                };
                reader.readAsDataURL(file);
            });

            // Show count indicator
            if (files.length > 1) {
                const countInfo = document.createElement('div');
                countInfo.className = 'upload-count-info';
                countInfo.innerHTML = `<i class="bi bi-images"></i> ${files.length} images selected — will be posted as a carousel`;
                grid.appendChild(countInfo);
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
                    imagesInput.files = files;
                    imagesInput.dispatchEvent(new Event('change'));
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

function clearAllImages() {
    const input = document.getElementById('images');
    if (input) input.value = '';
    document.getElementById('image-placeholder').style.display = 'flex';
    const grid = document.getElementById('image-preview-grid');
    if (grid) {
        grid.style.display = 'none';
        grid.innerHTML = '';
    }
    const clearBtn = document.getElementById('clear-images-btn');
    if (clearBtn) clearBtn.style.display = 'none';
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
