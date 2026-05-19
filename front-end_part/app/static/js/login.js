document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const email = document.getElementById('email');
    const password = document.getElementById('password');
    const errorMessage = document.getElementById('errorMessage');
    const successMessage = document.getElementById('successMessage');
    const emailError = document.getElementById('emailError');
    const passwordError = document.getElementById('passwordError');

    // Clear previous messages and error states
    errorMessage.style.display = 'none';
    successMessage.style.display = 'none';
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
        }
    } catch (error) {
        console.error('Error:', error);
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

// Email validation helper
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}
