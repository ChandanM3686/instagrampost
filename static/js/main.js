/**
 * SasksVoice — Main site JavaScript
 * Handles: navigation toggle, flash auto-dismiss, smooth scroll
 */

document.addEventListener('DOMContentLoaded', () => {
    // Mobile nav toggle
    const navToggle = document.getElementById('navToggle');
    const mobileNav = document.getElementById('mobileNav');

    if (navToggle && mobileNav) {
        navToggle.addEventListener('click', () => {
            mobileNav.classList.toggle('show');
            const icon = navToggle.querySelector('i');
            icon.className = mobileNav.classList.contains('show') ? 'bi bi-x-lg' : 'bi bi-list';
        });
    }

    // Auto-dismiss flash messages
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach((msg, idx) => {
        setTimeout(() => {
            msg.style.animation = 'flashOut 0.4s ease forwards';
            setTimeout(() => msg.remove(), 400);
        }, 5000 + idx * 500);
    });

    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const target = document.querySelector(link.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                // Close mobile nav if open
                if (mobileNav) mobileNav.classList.remove('show');
            }
        });
    });

    // Navbar scroll effect
    const navbar = document.getElementById('main-navbar');
    if (navbar) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 50) {
                navbar.style.background = 'rgba(10, 10, 15, 0.95)';
                navbar.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.3)';
            } else {
                navbar.style.background = 'rgba(10, 10, 15, 0.8)';
                navbar.style.boxShadow = 'none';
            }
        });
    }
});

// Add flash-out animation
const style = document.createElement('style');
style.textContent = `
    @keyframes flashOut {
        from { opacity: 1; transform: translateX(0); }
        to { opacity: 0; transform: translateX(40px); }
    }
`;
document.head.appendChild(style);
