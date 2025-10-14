/**
 * Global Error Handler - MnemoLite UI
 *
 * Centralized error handling for HTMX, fetch, and JavaScript errors.
 */

const ErrorHandler = {
    /**
     * Initialize error handlers
     */
    init() {
        this._setupHTMXErrorHandlers();
        this._setupGlobalErrorHandler();
        this._setupUnhandledRejectionHandler();
    },

    /**
     * Show error notification to user
     * @param {string} message - Error message
     * @param {Object} options - Notification options
     */
    showError(message, options = {}) {
        const {
            duration = 5000,
            canRetry = false,
            retryCallback = null
        } = options;

        // Create notification element
        const notification = document.createElement('div');
        notification.className = 'error-notification';
        notification.setAttribute('role', 'alert');
        notification.setAttribute('aria-live', 'assertive');

        notification.innerHTML = `
            <div class="error-notification-content">
                <span class="error-notification-icon">⚠</span>
                <span class="error-notification-message">${message}</span>
                ${canRetry && retryCallback ? `
                    <button class="error-notification-retry" aria-label="Réessayer">
                        Réessayer
                    </button>
                ` : ''}
                <button class="error-notification-close" aria-label="Fermer">×</button>
            </div>
        `;

        // Add to DOM
        let container = document.getElementById('notification-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notification-container';
            container.className = 'notification-container';
            document.body.appendChild(container);
        }
        container.appendChild(notification);

        // Handle retry button
        if (canRetry && retryCallback) {
            const retryBtn = notification.querySelector('.error-notification-retry');
            retryBtn.addEventListener('click', () => {
                retryCallback();
                notification.remove();
            });
        }

        // Handle close button
        const closeBtn = notification.querySelector('.error-notification-close');
        closeBtn.addEventListener('click', () => {
            notification.remove();
        });

        // Auto-remove after duration
        if (duration > 0) {
            setTimeout(() => {
                if (notification.parentElement) {
                    notification.remove();
                }
            }, duration);
        }

        // Animate in
        requestAnimationFrame(() => {
            notification.classList.add('show');
        });
    },

    /**
     * Setup HTMX error handlers
     * @private
     */
    _setupHTMXErrorHandlers() {
        // Response errors (4xx, 5xx)
        document.addEventListener('htmx:responseError', (event) => {
            const { detail } = event;
            console.error('HTMX Response Error:', detail);

            let message = 'Erreur lors du chargement des données.';

            if (detail.xhr) {
                const status = detail.xhr.status;
                if (status === 404) {
                    message = 'Ressource introuvable.';
                } else if (status === 500) {
                    message = 'Erreur serveur. Veuillez réessayer.';
                } else if (status === 403) {
                    message = 'Accès refusé.';
                } else if (status >= 400 && status < 500) {
                    message = 'Requête invalide.';
                }
            }

            this.showError(message, {
                canRetry: true,
                retryCallback: () => {
                    // Retry the HTMX request
                    htmx.trigger(detail.elt, detail.requestConfig.verb);
                }
            });
        });

        // Network errors (timeout, connection refused)
        document.addEventListener('htmx:sendError', (event) => {
            const { detail } = event;
            console.error('HTMX Network Error:', detail);

            this.showError('Erreur réseau. Vérifiez votre connexion.', {
                canRetry: true,
                retryCallback: () => {
                    htmx.trigger(detail.elt, detail.requestConfig.verb);
                }
            });
        });

        // Request timeout
        document.addEventListener('htmx:timeout', (event) => {
            const { detail } = event;
            console.error('HTMX Timeout:', detail);

            this.showError('La requête a expiré. Réessayez.', {
                canRetry: true,
                retryCallback: () => {
                    htmx.trigger(detail.elt, detail.requestConfig.verb);
                }
            });
        });
    },

    /**
     * Setup global JavaScript error handler
     * @private
     */
    _setupGlobalErrorHandler() {
        window.addEventListener('error', (event) => {
            console.error('Global Error:', event.error);

            // Don't show notification for every JS error in production
            // (could be too noisy), but log it
            if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                this.showError(`Erreur JavaScript: ${event.message}`, {
                    duration: 8000
                });
            }
        });
    },

    /**
     * Setup unhandled promise rejection handler
     * @private
     */
    _setupUnhandledRejectionHandler() {
        window.addEventListener('unhandledrejection', (event) => {
            console.error('Unhandled Promise Rejection:', event.reason);

            // Show user-friendly error
            this.showError('Une erreur inattendue s\'est produite.', {
                duration: 5000
            });
        });
    },

    /**
     * Wrapper for fetch with error handling
     * @param {string} url - URL to fetch
     * @param {Object} options - Fetch options
     * @returns {Promise<any>} Response data
     */
    async fetchWithErrorHandling(url, options = {}) {
        try {
            const response = await fetch(url, options);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Fetch Error:', error);

            this.showError(`Erreur: ${error.message}`, {
                canRetry: true,
                retryCallback: () => this.fetchWithErrorHandling(url, options)
            });

            throw error;
        }
    }
};

// Auto-initialize
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        ErrorHandler.init();
    });
} else {
    ErrorHandler.init();
}

// Expose to global scope
window.ErrorHandler = ErrorHandler;

// Add CSS for error notifications dynamically
const style = document.createElement('style');
style.textContent = `
.notification-container {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-width: 400px;
}

.error-notification {
    background: #161b22;
    border: 1px solid #f85149;
    border-left: 3px solid #f85149;
    padding: 16px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
    opacity: 0;
    transform: translateX(400px);
    transition: all 0.3s ease;
}

.error-notification.show {
    opacity: 1;
    transform: translateX(0);
}

.error-notification-content {
    display: flex;
    align-items: center;
    gap: 12px;
}

.error-notification-icon {
    font-size: 20px;
    color: #f85149;
    flex-shrink: 0;
}

.error-notification-message {
    flex: 1;
    font-size: 13px;
    color: #c9d1d9;
    line-height: 1.4;
}

.error-notification-retry {
    background: #21262d;
    border: 1px solid #30363d;
    color: #58a6ff;
    padding: 6px 12px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    cursor: pointer;
    transition: all 0.08s ease;
    flex-shrink: 0;
}

.error-notification-retry:hover {
    border-color: #58a6ff;
    background: rgba(88, 166, 255, 0.1);
}

.error-notification-close {
    background: transparent;
    border: none;
    color: #8b949e;
    font-size: 20px;
    font-weight: 700;
    cursor: pointer;
    padding: 0;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: color 0.08s ease;
    flex-shrink: 0;
}

.error-notification-close:hover {
    color: #f85149;
}
`;
document.head.appendChild(style);
