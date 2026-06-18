function clearLoginMessages() {
    const errorMessage = document.getElementById('errorMessage');
    const successMessage = document.getElementById('successMessage');
    const resendMessage = document.getElementById('resendMessage');

    errorMessage.style.display = 'none';
    successMessage.style.display = 'none';
    resendMessage.style.display = 'none';
}

async function requestVerificationResend(emailValue) {
    const errorMessage = document.getElementById('errorMessage');
    const successMessage = document.getElementById('successMessage');
    const resendMessage = document.getElementById('resendMessage');

    clearLoginMessages();
    resendMessage.textContent = 'Sending verification email...';
    resendMessage.style.display = 'block';

    try {
        const response = await fetch('/resend-verification', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                email: emailValue
            })
        });

        const data = await response.json();

        if (data.success) {
            successMessage.textContent = data.message;
            successMessage.style.display = 'block';
            resendMessage.style.display = 'none';
        } else {
            errorMessage.textContent = data.message;
            errorMessage.style.display = 'block';
            resendMessage.style.display = 'none';
        }
    } catch (error) {
        console.error('Error:', error);
        errorMessage.textContent = 'An error occurred. Please try again.';
        errorMessage.style.display = 'block';
        resendMessage.style.display = 'none';
    }
}

document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const email = document.getElementById('email');
    const password = document.getElementById('password');
    const errorMessage = document.getElementById('errorMessage');
    const successMessage = document.getElementById('successMessage');
    const resendMessage = document.getElementById('resendMessage');
    const emailError = document.getElementById('emailError');
    const passwordError = document.getElementById('passwordError');

    // Clear previous messages and error states
    clearLoginMessages();
    email.classList.remove('error-input');
    password.classList.remove('error-input');
    emailError.textContent = '';
    passwordError.textContent = '';

    // Client validation
    let hasError = false;

    if (!email.value.trim()) {
        emailError.textContent = 'Email is required';
        email.classList.add('error-input');
        hasError = true;
    } else if (!isValidEmail(email.value)) {
        emailError.textContent = 'Please enter a valid email address';
        email.classList.add('error-input');
        hasError = true;
    }

    if (!password.value) {
        passwordError.textContent = 'Password is required';
        password.classList.add('error-input');
        hasError = true;
    } else if (password.value.length < 1) {
        passwordError.textContent = 'Password is too short';
        password.classList.add('error-input');
        hasError = true;
    }

    if (hasError) {
        return;
    }

    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                email: email.value,
                password: password.value
            })
        });

        const data = await response.json();

        if (data.success) {
            // Reset theme to light mode for new login
            localStorage.removeItem('theme');
            window.location.href = data.redirect;
        } else {
            // Show server error
            errorMessage.textContent = data.message;
            errorMessage.style.display = 'block';

            // Mark fields as error if it's a credential issue
            if (data.message.toLowerCase().includes('invalid')) {
                email.classList.add('error-input');
                password.classList.add('error-input');
                errorMessage.textContent = 'Invalid email or password';
            }

            if (data.message.toLowerCase().includes('verify')) {
                resendMessage.innerHTML = 'Didn\'t receive the email? <a href="#" id="resendVerification" style="color: #2a1406; text-decoration: underline; font-weight: bold;">Resend verification email</a>.';
                resendMessage.style.display = 'block';

                const dynResendBtn = document.getElementById('resendVerification');
                if (dynResendBtn) {
                    dynResendBtn.addEventListener('click', async (e) => {
                        e.preventDefault();
                        const emailInput = document.getElementById('email');
                        if (emailInput && emailInput.value.trim()) {
                            await requestVerificationResend(emailInput.value.trim());
                        } else {
                            const emailError = document.getElementById('emailError');
                            if (emailError) {
                                emailError.textContent = 'Email is required to resend verification link.';
                            }
                        }
                    });
                }
            }
        }
    } catch (error) {
        console.error('Error:', error);
        errorMessage.textContent = 'An error occurred. Please try again.';
        errorMessage.style.display = 'block';
    }
});

const resendVerificationBtn = document.getElementById('resendVerification');
if (resendVerificationBtn) {
    resendVerificationBtn.addEventListener('click', async () => {
        const email = document.getElementById('email');
        const errorMessage = document.getElementById('errorMessage');
        const successMessage = document.getElementById('successMessage');
        const resendMessage = document.getElementById('resendMessage');
        const emailError = document.getElementById('emailError');

        clearLoginMessages();
        emailError.textContent = '';
        email.classList.remove('error-input');

        if (!email.value.trim()) {
            emailError.textContent = 'Email is required';
            email.classList.add('error-input');
            return;
        }

        if (!isValidEmail(email.value)) {
            emailError.textContent = 'Please enter a valid email address';
            email.classList.add('error-input');
            return;
        }

        await requestVerificationResend(email.value);
    });
}

window.addEventListener('DOMContentLoaded', () => {
    const emailInput = document.getElementById('email');
    const pendingEmail = localStorage.getItem('pendingVerificationEmail');
    const pendingAt = Number(localStorage.getItem('pendingVerificationAt') || '0');
    const maxAgeMs = 10 * 60 * 1000;

    if (!pendingEmail) {
        return;
    }

    const isFresh = pendingAt && (Date.now() - pendingAt) <= maxAgeMs;
    localStorage.removeItem('pendingVerificationEmail');
    localStorage.removeItem('pendingVerificationAt');

    if (!isFresh) {
        return;
    }

    if (emailInput && !emailInput.value) {
        emailInput.value = pendingEmail;
    }

    // IMPORTANT: Do NOT auto-trigger resend here.
    // The registration flow already sends a verification email.
    // Auto-calling /resend-verification causes duplicate emails.
    const resendMessage = document.getElementById('resendMessage');
    if (resendMessage) {
        // Automatic verification notice removed per UX request.
        // Do not show the 'We sent a verification email...' message here.
    }
});

// Clear error state when user starts typing
document.getElementById('email').addEventListener('input', () => {
    document.getElementById('email').classList.remove('error-input');
    document.getElementById('emailError').textContent = '';
});

document.getElementById('password').addEventListener('input', () => {
    document.getElementById('password').classList.remove('error-input');
    document.getElementById('passwordError').textContent = '';
});

// Email validation helper
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}
