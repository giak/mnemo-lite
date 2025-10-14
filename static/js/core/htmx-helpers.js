/**
 * HTMX Helpers - MnemoLite UI
 *
 * Standardized patterns and utilities for HTMX interactions.
 * Eliminates inconsistent HTMX attribute patterns across templates.
 *
 * USAGE:
 * Add data-attributes to elements instead of manually writing hx-* attributes.
 *
 * Example:
 *   <div data-htmx-filter-form
 *        data-target="#results"
 *        data-url="/api/data">
 *     <select name="category">...</select>
 *     <input name="period">
 *   </div>
 *
 * This automatically configures all inputs/selects inside to trigger HTMX updates.
 */

const HTMXHelpers = {
    /**
     * Initialize all HTMX helpers on page load
     */
    init() {
        this.initFilterForms();
        this.initAutoUpdateElements();
        this.initLoadingIndicators();
    },

    /**
     * Initialize filter forms with standardized HTMX behavior
     *
     * Pattern: [data-htmx-filter-form]
     * Auto-configures all inputs/selects inside to trigger updates on change
     */
    initFilterForms() {
        document.querySelectorAll('[data-htmx-filter-form]').forEach(container => {
            const target = container.dataset.target || '#results';
            const url = container.dataset.url;
            const include = container.dataset.include || '[data-htmx-filter-form]';

            if (!url) {
                console.warn('HTMX filter form missing data-url:', container);
                return;
            }

            // Configure all inputs and selects
            container.querySelectorAll('input, select').forEach(input => {
                // Skip if already configured
                if (input.hasAttribute('hx-get')) return;

                input.setAttribute('hx-get', url);
                input.setAttribute('hx-target', target);
                input.setAttribute('hx-trigger', 'change');
                input.setAttribute('hx-include', `closest ${include}`);
            });

            // Process HTMX for newly added attributes
            if (typeof htmx !== 'undefined') {
                htmx.process(container);
            }
        });
    },

    /**
     * Initialize auto-update elements
     *
     * Pattern: [data-htmx-auto-update]
     * Polls server at specified interval
     *
     * Example:
     *   <div data-htmx-auto-update
     *        data-url="/api/status"
     *        data-interval="30s">
     *   </div>
     */
    initAutoUpdateElements() {
        document.querySelectorAll('[data-htmx-auto-update]').forEach(element => {
            const url = element.dataset.url;
            const interval = element.dataset.interval || '30s';

            if (!url) {
                console.warn('HTMX auto-update missing data-url:', element);
                return;
            }

            element.setAttribute('hx-get', url);
            element.setAttribute('hx-trigger', `every ${interval}`);
            element.setAttribute('hx-swap', 'innerHTML');

            if (typeof htmx !== 'undefined') {
                htmx.process(element);
            }
        });
    },

    /**
     * Initialize loading indicators
     *
     * Pattern: [data-htmx-loading]
     * Shows/hides loading state during HTMX requests
     *
     * Example:
     *   <div data-htmx-loading>Loading...</div>
     */
    initLoadingIndicators() {
        // Show loading indicators on HTMX requests
        document.addEventListener('htmx:beforeRequest', (event) => {
            const indicator = event.target.querySelector('[data-htmx-loading]');
            if (indicator) {
                indicator.style.display = 'block';
                indicator.setAttribute('aria-busy', 'true');
            }
        });

        // Hide loading indicators after requests complete
        document.addEventListener('htmx:afterRequest', (event) => {
            const indicator = event.target.querySelector('[data-htmx-loading]');
            if (indicator) {
                indicator.style.display = 'none';
                indicator.setAttribute('aria-busy', 'false');
            }
        });
    },

    /**
     * Standardized HTMX configuration for common patterns
     */
    patterns: {
        /**
         * Filter form pattern
         * @param {HTMLElement} container - Container element
         * @param {string} url - Target URL
         * @param {string} target - Target selector
         */
        filterForm(container, url, target = '#results') {
            container.setAttribute('data-htmx-filter-form', '');
            container.setAttribute('data-url', url);
            container.setAttribute('data-target', target);
            HTMXHelpers.initFilterForms();
        },

        /**
         * Auto-refresh pattern
         * @param {HTMLElement} element - Element to refresh
         * @param {string} url - Source URL
         * @param {string} interval - Refresh interval (e.g., "30s", "1m")
         */
        autoRefresh(element, url, interval = '30s') {
            element.setAttribute('data-htmx-auto-update', '');
            element.setAttribute('data-url', url);
            element.setAttribute('data-interval', interval);
            HTMXHelpers.initAutoUpdateElements();
        },

        /**
         * Load more / pagination pattern
         * @param {HTMLElement} button - Load more button
         * @param {string} url - Next page URL
         * @param {string} target - Target selector
         */
        loadMore(button, url, target) {
            button.setAttribute('hx-get', url);
            button.setAttribute('hx-target', target);
            button.setAttribute('hx-swap', 'beforeend');
            button.setAttribute('hx-indicator', '.htmx-indicator');

            if (typeof htmx !== 'undefined') {
                htmx.process(button);
            }
        },

        /**
         * Modal trigger pattern
         * @param {HTMLElement} trigger - Element that opens modal
         * @param {string} url - Content URL
         * @param {string} modalId - Modal element ID
         */
        modalTrigger(trigger, url, modalId = 'modal') {
            trigger.setAttribute('hx-get', url);
            trigger.setAttribute('hx-target', `#${modalId} #modal-body`);
            trigger.setAttribute('hx-swap', 'innerHTML');

            // Open modal after content loads
            trigger.addEventListener('htmx:afterRequest', () => {
                if (window.ModalManager) {
                    window.ModalManager.open(modalId);
                }
            });

            if (typeof htmx !== 'undefined') {
                htmx.process(trigger);
            }
        }
    }
};

// Auto-initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        HTMXHelpers.init();
    });
} else {
    HTMXHelpers.init();
}

// Re-initialize after HTMX swaps
if (typeof htmx !== 'undefined') {
    document.addEventListener('htmx:afterSwap', () => {
        HTMXHelpers.init();
    });
}

// Expose to global scope
window.HTMXHelpers = HTMXHelpers;
