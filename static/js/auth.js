// Функции для аутентификации
document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
    
    if (registerForm) {
        registerForm.addEventListener('submit', handleRegister);
    }
    
    // Валидация форм
    initFormValidation();
});

function initFormValidation() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        const inputs = form.querySelectorAll('input[required]');
        
        inputs.forEach(input => {
            input.addEventListener('blur', validateField);
            input.addEventListener('input', clearFieldError);
        });
    });
}

function validateField(e) {
    const field = e.target;
    const value = field.value.trim();
    const fieldName = field.name;
    
    clearFieldError({ target: field });
    
    let isValid = true;
    let errorMessage = '';
    
    switch (fieldName) {
        case 'username':
            if (value.length < 3) {
                isValid = false;
                errorMessage = 'Username must be at least 3 characters';
            }
            break;
            
        case 'email':
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(value)) {
                isValid = false;
                errorMessage = 'Please enter a valid email address';
            }
            break;
            
        case 'password':
            if (value.length < 6) {
                isValid = false;
                errorMessage = 'Password must be at least 6 characters';
            }
            break;
            
        case 'confirm_password':
            const password = field.form.querySelector('input[name="password"]').value;
            if (value !== password) {
                isValid = false;
                errorMessage = 'Passwords do not match';
            }
            break;
    }
    
    if (!isValid) {
        showFieldError(field, errorMessage);
    }
    
    return isValid;
}

function showFieldError(field, message) {
    field.classList.add('error');
    
    let errorElement = field.parentNode.querySelector('.field-error');
    if (!errorElement) {
        errorElement = document.createElement('div');
        errorElement.className = 'field-error';
        field.parentNode.appendChild(errorElement);
    }
    
    errorElement.textContent = message;
    errorElement.style.display = 'block';
}

function clearFieldError(e) {
    const field = e.target;
    field.classList.remove('error');
    
    const errorElement = field.parentNode.querySelector('.field-error');
    if (errorElement) {
        errorElement.style.display = 'none';
    }
}

async function handleLogin(e) {
    e.preventDefault();
    
    const form = e.target;
    const formData = new FormData(form);
    
    // Валидация полей
    const inputs = form.querySelectorAll('input[required]');
    let allValid = true;
    
    inputs.forEach(input => {
        if (!validateField({ target: input })) {
            allValid = false;
        }
    });
    
    if (!allValid) {
        showNotification('Please fix the errors in the form', 'error');
        return;
    }
    
    // Отправка формы
    try {
        const response = await fetch('/login', {
            method: 'POST',
            body: formData
        });
        
        if (response.redirected) {
            window.location.href = response.url;
        } else {
            const data = await response.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(data, 'text/html');
            const error = doc.querySelector('.alert-error');
            
            if (error) {
                showNotification(error.textContent, 'error');
            }
        }
    } catch (error) {
        showNotification('An error occurred. Please try again.', 'error');
    }
}

async function handleRegister(e) {
    e.preventDefault();
    
    const form = e.target;
    const formData = new FormData(form);
    
    // Валидация полей
    const inputs = form.querySelectorAll('input[required]');
    let allValid = true;
    
    inputs.forEach(input => {
        if (!validateField({ target: input })) {
            allValid = false;
        }
    });
    
    if (!allValid) {
        showNotification('Please fix the errors in the form', 'error');
        return;
    }
    
    // Проверка совпадения паролей
    const password = form.querySelector('input[name="password"]').value;
    const confirmPassword = form.querySelector('input[name="confirm_password"]').value;
    
    if (password !== confirmPassword) {
        showNotification('Passwords do not match', 'error');
        return;
    }
    
    // Отправка формы
    try {
        const response = await fetch('/register', {
            method: 'POST',
            body: formData
        });
        
        if (response.redirected) {
            window.location.href = response.url;
        } else {
            const data = await response.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(data, 'text/html');
            const error = doc.querySelector('.alert-error');
            
            if (error) {
                showNotification(error.textContent, 'error');
            }
        }
    } catch (error) {
        showNotification('An error occurred. Please try again.', 'error');
    }
}

// Добавляем стили для ошибок
const authStyle = document.createElement('style');
authStyle.textContent = `
    .field-error {
        color: #dc3545;
        font-size: 0.875rem;
        margin-top: 0.25rem;
        display: none;
    }
    
    input.error {
        border-color: #dc3545 !important;
    }
    
    .alert-error {
        background: #f8d7da;
        color: #721c24;
        padding: 0.75rem 1.25rem;
        border: 1px solid #f5c6cb;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
`;
document.head.appendChild(authStyle);
