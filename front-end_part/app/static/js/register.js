document.getElementById('registerForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const REDIRECT_DELAY_MS = 900;

    const email = document.getElementById('email');
    const password = document.getElementById('password');
    const confirmPassword = document.getElementById('confirm_password');
    const emailError = document.getElementById('emailError');
    const passwordError = document.getElementById('passwordError');
    const confirmError = document.getElementById('confirmError');
    const errorMessage = document.getElementById('errorMessage');
    const successMessage = document.getElementById('successMessage');
    const registerButton = document.querySelector('#registerForm button[type="submit"]');
    const registerButtonLabel = registerButton ? registerButton.querySelector('span') : null;

    // Hide messages
    errorMessage.style.display = 'none';
    successMessage.style.display = 'none';

    // Reset button state
    if (registerButton) {
        registerButton.disabled = false;
        registerButton.style.opacity = '1';
        registerButton.style.cursor = 'pointer';
    }
    if (registerButtonLabel) {
        registerButtonLabel.textContent = 'Register';
    }

    // Clear all error classes
    email.classList.remove('error-input');
    password.classList.remove('error-input');
    confirmPassword.classList.remove('error-input');
    emailError.textContent = '';
    passwordError.textContent = '';
    confirmError.textContent = '';

    // Client-side validation
    let hasError = false;
    const passwordRule = /^(?=.*[A-Z])(?=.*[^A-Za-z0-9]).{6,}$/;

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
    } else if (password.value.length < 6) {
        passwordError.textContent = 'Password must be at least 6 characters';
        password.classList.add('error-input');
        hasError = true;
    } else if (!passwordRule.test(password.value)) {
        passwordError.textContent = 'Must include at least one uppercase letter and one special character';
        password.classList.add('error-input');
        hasError = true;
    }

    if (!confirmPassword.value) {
        confirmError.textContent = 'Please confirm your password';
        confirmPassword.classList.add('error-input');
        hasError = true;
    } else if (password.value !== confirmPassword.value) {
        confirmError.textContent = 'Passwords do not match';
        confirmPassword.classList.add('error-input');
        password.classList.add('error-input');
        hasError = true;
    }

    if (hasError) {
        return;
    }

    // Show immediate progress feedback (no silent pause after click)
    successMessage.textContent = 'Registering...';
    successMessage.style.display = 'block';
    if (registerButton) {
        registerButton.disabled = true;
        registerButton.style.opacity = '0.75';
        registerButton.style.cursor = 'not-allowed';
    }
    if (registerButtonLabel) {
        registerButtonLabel.textContent = 'Registering...';
    }

    try {
        const response = await fetch('/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                email: email.value,
                password: password.value,
                confirm_password: confirmPassword.value
            })
        });

        const data = await response.json();

        if (data.success) {
            successMessage.textContent = data.message || 'Registration successful! Redirecting...';
            successMessage.style.display = 'block';
            if (registerButtonLabel) {
                registerButtonLabel.textContent = 'Success';
            }

            // Clear form
            document.getElementById('registerForm').reset();

            // Small pause so user can see success message, then redirect
            setTimeout(() => {
                window.location.href = '/login';
            }, REDIRECT_DELAY_MS);
        } else {
            successMessage.style.display = 'none';
            if (registerButton) {
                registerButton.disabled = false;
                registerButton.style.opacity = '1';
                registerButton.style.cursor = 'pointer';
            }
            if (registerButtonLabel) {
                registerButtonLabel.textContent = 'Register';
            }

            if (data.message.toLowerCase().includes('email')) {
                emailError.textContent = data.message;
                email.classList.add('error-input');
            } else {
                errorMessage.textContent = data.message;
                errorMessage.style.display = 'block';
            }
        }
    } catch (error) {
        console.error('Error:', error);
        successMessage.style.display = 'none';
        if (registerButton) {
            registerButton.disabled = false;
            registerButton.style.opacity = '1';
            registerButton.style.cursor = 'pointer';
        }
        if (registerButtonLabel) {
            registerButtonLabel.textContent = 'Register';
        }
        errorMessage.textContent = 'An error occurred. Please try again.';
        errorMessage.style.display = 'block';
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

document.getElementById('confirm_password').addEventListener('input', () => {
    document.getElementById('confirm_password').classList.remove('error-input');
    document.getElementById('confirmError').textContent = '';
});

// Email validation helper
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

document.querySelectorAll('.password-toggle').forEach((toggleButton) => {
    toggleButton.addEventListener('click', () => {
        const targetId = toggleButton.getAttribute('data-target');
        const targetInput = document.getElementById(targetId);

        if (!targetInput) {
            return;
        }

        const isPassword = targetInput.type === 'password';
        targetInput.type = isPassword ? 'text' : 'password';
        toggleButton.classList.toggle('lamp-on', isPassword);
        toggleButton.classList.toggle('lamp-off', !isPassword);
        toggleButton.setAttribute('aria-label', isPassword ? 'Hide password' : 'Show password');
    });
});
