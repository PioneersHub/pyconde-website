/**
 * Contact Form Handler for PyConDE
 * Handles form submission with reCAPTCHA verification
 */

(function() {
  'use strict';

  // Form elements
  const form = document.getElementById('contact-form');
  const submitButton = document.getElementById('submit-button');
  const buttonText = submitButton.querySelector('.button-text');
  const buttonLoader = submitButton.querySelector('.button-loader');
  const successMessage = document.getElementById('form-success');
  const errorMessage = document.getElementById('form-error');
  const errorMessageText = document.getElementById('form-error-text');

  // Form fields
  const nameField = document.getElementById('name');
  const emailField = document.getElementById('email');
  const subjectField = document.getElementById('subject');
  const messageField = document.getElementById('message');
  const honeypotField = document.getElementById('website');

  // Character counter
  const messageCount = document.getElementById('message-count');

  // reCAPTCHA state
  let recaptchaToken = null;

  /**
   * Update character count for message field
   */
  function updateCharacterCount() {
    const count = messageField.value.length;
    messageCount.textContent = `${count} / 5000`;

    if (count > 4500) {
      messageCount.style.color = '#e54f53';
    } else {
      messageCount.style.color = '';
    }
  }

  /**
   * Callback when reCAPTCHA is successfully completed
   */
  window.onRecaptchaSuccess = function(token) {
    recaptchaToken = token;
    clearError('recaptcha');
  };

  /**
   * Callback when reCAPTCHA expires
   */
  window.onRecaptchaExpired = function() {
    recaptchaToken = null;
    showError('recaptcha', 'reCAPTCHA expired. Please verify again.');
  };

  /**
   * Show error message for a field
   */
  function showError(fieldName, message) {
    const errorElement = document.getElementById(`${fieldName}-error`);
    if (errorElement) {
      errorElement.textContent = message;
      errorElement.style.display = 'block';
    }
  }

  /**
   * Clear error message for a field
   */
  function clearError(fieldName) {
    const errorElement = document.getElementById(`${fieldName}-error`);
    if (errorElement) {
      errorElement.textContent = '';
      errorElement.style.display = 'none';
    }
  }

  /**
   * Clear all error messages
   */
  function clearAllErrors() {
    ['name', 'email', 'subject', 'message', 'recaptcha'].forEach(clearError);
    errorMessage.style.display = 'none';
  }

  /**
   * Validate email format
   */
  function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  /**
   * Validate form fields
   */
  function validateForm() {
    clearAllErrors();
    let isValid = true;

    // Validate name
    if (!nameField.value.trim()) {
      showError('name', 'Please enter your name');
      isValid = false;
    } else if (nameField.value.trim().length > 100) {
      showError('name', 'Name must be 100 characters or less');
      isValid = false;
    }

    // Validate email
    if (!emailField.value.trim()) {
      showError('email', 'Please enter your email address');
      isValid = false;
    } else if (!isValidEmail(emailField.value.trim())) {
      showError('email', 'Please enter a valid email address');
      isValid = false;
    }

    // Validate subject
    if (!subjectField.value.trim()) {
      showError('subject', 'Please enter a subject');
      isValid = false;
    } else if (subjectField.value.trim().length > 200) {
      showError('subject', 'Subject must be 200 characters or less');
      isValid = false;
    }

    // Validate message
    if (!messageField.value.trim()) {
      showError('message', 'Please enter your message');
      isValid = false;
    } else if (messageField.value.trim().length < 10) {
      showError('message', 'Message must be at least 10 characters');
      isValid = false;
    } else if (messageField.value.trim().length > 5000) {
      showError('message', 'Message must be 5000 characters or less');
      isValid = false;
    }

    // Validate reCAPTCHA
    if (!recaptchaToken) {
      showError('recaptcha', 'Please complete the reCAPTCHA verification');
      isValid = false;
    }

    return isValid;
  }

  /**
   * Set loading state
   */
  function setLoading(loading) {
    submitButton.disabled = loading;

    if (loading) {
      buttonText.style.display = 'none';
      buttonLoader.style.display = 'inline';
      submitButton.classList.add('loading');
    } else {
      buttonText.style.display = 'inline';
      buttonLoader.style.display = 'none';
      submitButton.classList.remove('loading');
    }
  }

  /**
   * Show success message
   */
  function showSuccess(message) {
    successMessage.querySelector('p').textContent = `✓ ${message}`;
    successMessage.style.display = 'block';
    errorMessage.style.display = 'none';

    // Scroll to success message
    successMessage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  /**
   * Show general error message
   */
  function showGeneralError(message) {
    errorMessageText.textContent = `✗ ${message}`;
    errorMessage.style.display = 'block';
    successMessage.style.display = 'none';

    // Scroll to error message
    errorMessage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  /**
   * Reset form to initial state
   */
  function resetForm() {
    form.reset();
    recaptchaToken = null;
    grecaptcha.reset();
    updateCharacterCount();
    clearAllErrors();
  }

  /**
   * Handle form submission
   */
  async function handleSubmit(event) {
    event.preventDefault();

    // Clear previous messages
    successMessage.style.display = 'none';
    errorMessage.style.display = 'none';

    // Validate form
    if (!validateForm()) {
      return;
    }

    // Check honeypot (should be empty)
    if (honeypotField.value) {
      console.warn('Honeypot field filled - possible bot');
      return;
    }

    // Prepare form data
    const formData = {
      name: nameField.value.trim(),
      email: emailField.value.trim(),
      subject: subjectField.value.trim(),
      message: messageField.value.trim(),
      recaptcha_token: recaptchaToken,
      honeypot: honeypotField.value
    };

    // Set loading state
    setLoading(true);

    try {
      // Submit to backend
      const response = await fetch(window.CONTACT_FORM_CONFIG.apiEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
      });

      const result = await response.json();

      if (response.ok && result.success) {
        // Success
        showSuccess(result.message);
        resetForm();
      } else {
        // Error response from server
        showGeneralError(result.message || 'Failed to send message. Please try again.');
      }
    } catch (error) {
      // Network or other error
      console.error('Form submission error:', error);
      showGeneralError(
        'Unable to send message. Please check your internet connection and try again.'
      );
    } finally {
      setLoading(false);
    }
  }

  /**
   * Initialize form
   */
  function init() {
    // Add event listeners
    form.addEventListener('submit', handleSubmit);
    messageField.addEventListener('input', updateCharacterCount);

    // Initialize character count
    updateCharacterCount();

    // Real-time validation (optional - clear errors on input)
    [nameField, emailField, subjectField, messageField].forEach(field => {
      field.addEventListener('input', function() {
        if (this.value.trim()) {
          clearError(this.id);
        }
      });
    });
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
