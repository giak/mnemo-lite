/**
 * HTML Utilities for XSS Prevention
 *
 * @module html_utils
 * @description Provides utilities for safe HTML manipulation and XSS prevention
 */

/**
 * Escapes HTML special characters to prevent XSS attacks
 *
 * @param {string} text - The text to escape
 * @returns {string} The escaped text safe for insertion into HTML
 *
 * @example
 * escapeHtml('<script>alert("XSS")</script>')
 * // Returns: '&lt;script&gt;alert(&quot;XSS&quot;)&lt;/script&gt;'
 */
function escapeHtml(text) {
    if (text === null || text === undefined) {
        return '';
    }

    const str = String(text);
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };

    return str.replace(/[&<>"']/g, (char) => map[char]);
}

/**
 * Safely sets text content of an element
 *
 * @param {HTMLElement} element - The DOM element
 * @param {string} text - The text to set
 */
function safeSetText(element, text) {
    if (!element) return;
    element.textContent = text;
}

/**
 * Safely creates an HTML element with text content
 *
 * @param {string} tagName - The element tag name
 * @param {string} text - The text content
 * @param {string} [className] - Optional CSS class
 * @returns {HTMLElement} The created element
 */
function safeCreateElement(tagName, text, className = null) {
    const element = document.createElement(tagName);
    if (text) {
        element.textContent = text;
    }
    if (className) {
        element.className = className;
    }
    return element;
}

/**
 * Sanitizes HTML by creating a text node (no HTML allowed)
 *
 * @param {string} html - The HTML string
 * @returns {string} The sanitized text
 */
function sanitizeToText(html) {
    const div = document.createElement('div');
    div.textContent = html;
    return div.innerHTML;
}

/**
 * Truncates text and escapes it for safe display
 *
 * @param {string} text - The text to truncate
 * @param {number} maxLength - Maximum length
 * @returns {string} The truncated and escaped text
 */
function safeTruncate(text, maxLength) {
    if (!text) return '';
    const truncated = text.length > maxLength
        ? text.substring(0, maxLength) + '...'
        : text;
    return escapeHtml(truncated);
}

// Export for ES6 modules (if needed)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        escapeHtml,
        safeSetText,
        safeCreateElement,
        sanitizeToText,
        safeTruncate
    };
}
