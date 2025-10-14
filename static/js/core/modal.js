/**
 * Modal Manager - MnemoLite UI
 *
 * Centralized modal management with accessibility support.
 */

const ModalManager = {
    /**
     * Open a modal by ID
     * @param {string} modalId - ID of modal element
     */
    open(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) {
            console.error(`Modal not found: ${modalId}`);
            return;
        }

        // Store previously focused element
        modal.dataset.previousFocus = document.activeElement?.id || null;

        // Show modal
        modal.style.display = 'flex';
        modal.setAttribute('aria-hidden', 'false');

        // Focus first focusable element
        const firstFocusable = this._getFirstFocusable(modal);
        if (firstFocusable) {
            // Small delay to ensure display transition completes
            setTimeout(() => firstFocusable.focus(), 50);
        }

        // Trap focus within modal
        this._trapFocus(modal);

        // Close on Escape key
        this._handleEscape(modal);

        // Close on backdrop click
        this._handleBackdropClick(modal);
    },

    /**
     * Close a modal by ID
     * @param {string} modalId - ID of modal element
     */
    close(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) {
            console.error(`Modal not found: ${modalId}`);
            return;
        }

        // Hide modal
        modal.style.display = 'none';
        modal.setAttribute('aria-hidden', 'true');

        // Clear content (optional, for HTMX loaded content)
        const modalBody = modal.querySelector('#modal-body');
        if (modalBody) {
            modalBody.innerHTML = '';
        }

        // Restore focus to previously focused element
        const previousFocusId = modal.dataset.previousFocus;
        if (previousFocusId) {
            const previousElement = document.getElementById(previousFocusId);
            if (previousElement) {
                previousElement.focus();
            }
        }

        // Remove event listeners
        this._removeEventListeners(modal);
    },

    /**
     * Get first focusable element in container
     * @private
     */
    _getFirstFocusable(container) {
        const focusableSelectors = [
            'button:not([disabled])',
            '[href]',
            'input:not([disabled])',
            'select:not([disabled])',
            'textarea:not([disabled])',
            '[tabindex]:not([tabindex="-1"])'
        ];

        return container.querySelector(focusableSelectors.join(', '));
    },

    /**
     * Trap focus within modal
     * @private
     */
    _trapFocus(modal) {
        const focusableElements = modal.querySelectorAll(
            'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );

        const firstFocusable = focusableElements[0];
        const lastFocusable = focusableElements[focusableElements.length - 1];

        const handleTabKey = (e) => {
            if (e.key !== 'Tab') return;

            if (e.shiftKey) {
                // Shift + Tab
                if (document.activeElement === firstFocusable) {
                    e.preventDefault();
                    lastFocusable.focus();
                }
            } else {
                // Tab
                if (document.activeElement === lastFocusable) {
                    e.preventDefault();
                    firstFocusable.focus();
                }
            }
        };

        modal._focusTrapHandler = handleTabKey;
        modal.addEventListener('keydown', handleTabKey);
    },

    /**
     * Handle Escape key to close modal
     * @private
     */
    _handleEscape(modal) {
        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                this.close(modal.id);
            }
        };

        modal._escapeHandler = handleEscape;
        document.addEventListener('keydown', handleEscape);
    },

    /**
     * Close modal on backdrop click
     * @private
     */
    _handleBackdropClick(modal) {
        const handleClick = (e) => {
            if (e.target === modal) {
                this.close(modal.id);
            }
        };

        modal._backdropHandler = handleClick;
        modal.addEventListener('click', handleClick);
    },

    /**
     * Remove all event listeners
     * @private
     */
    _removeEventListeners(modal) {
        if (modal._focusTrapHandler) {
            modal.removeEventListener('keydown', modal._focusTrapHandler);
            delete modal._focusTrapHandler;
        }

        if (modal._escapeHandler) {
            document.removeEventListener('keydown', modal._escapeHandler);
            delete modal._escapeHandler;
        }

        if (modal._backdropHandler) {
            modal.removeEventListener('click', modal._backdropHandler);
            delete modal._backdropHandler;
        }
    }
};

// Expose to global scope for onclick handlers and HTMX
window.ModalManager = ModalManager;
window.openModal = (modalId) => ModalManager.open(modalId);
window.closeModal = (modalId) => ModalManager.close(modalId);
