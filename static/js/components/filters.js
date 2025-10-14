/**
 * Filters Component - MnemoLite UI
 *
 * Centralized filter management for dashboard and search pages.
 * Eliminates code duplication and provides consistent behavior.
 */

const FilterManager = {
    /**
     * Set the active period filter
     * @param {HTMLElement} button - The clicked period button
     * @param {string} value - Period value (1h, 6h, 24h, 7d, 30d, all)
     */
    setPeriod(button, value) {
        // Remove active class from all period buttons
        document.querySelectorAll('.period-btn').forEach(btn => {
            btn.classList.remove('active');
        });

        // Add active class to clicked button
        button.classList.add('active');

        // Set hidden input value and trigger HTMX
        const periodInput = document.getElementById('period-input');
        if (periodInput) {
            periodInput.value = value;

            // Trigger HTMX change event
            if (typeof htmx !== 'undefined') {
                htmx.trigger(periodInput, 'change');
            } else {
                // Fallback: dispatch native change event
                periodInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
    },

    /**
     * Clear all active filters and reset to defaults
     */
    clearAll() {
        // Reset all selects to first option
        document.querySelectorAll('#filters-form select').forEach(select => {
            select.selectedIndex = 0;
        });

        // Reset period to 'all'
        const periodInput = document.getElementById('period-input');
        if (periodInput) {
            periodInput.value = 'all';
        }

        // Update UI: remove all active states
        document.querySelectorAll('.period-btn').forEach(btn => {
            btn.classList.remove('active');
        });

        // Set 'all' button as active
        const allButton = document.querySelector('.period-btn[onclick*="all"]');
        if (allButton) {
            allButton.classList.add('active');
        }

        // Trigger HTMX update if available
        if (typeof htmx !== 'undefined' && periodInput) {
            htmx.trigger(periodInput, 'change');
        }
    },

    /**
     * Initialize filter form with dynamic options
     * @param {string} projectSelectId - ID of project select element
     * @param {string} categorySelectId - ID of category select element
     */
    async loadDynamicOptions(projectSelectId = 'filter-project', categorySelectId = 'filter-category') {
        try {
            const response = await fetch('/ui/api/filters/options');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();

            // Populate project select
            const projectSelect = document.getElementById(projectSelectId);
            if (projectSelect && data.projects) {
                this._populateSelect(projectSelect, data.projects, 'Tous les projets');
            }

            // Populate category select
            const categorySelect = document.getElementById(categorySelectId);
            if (categorySelect && data.categories) {
                this._populateSelect(categorySelect, data.categories, 'Toutes catégories');
            }
        } catch (error) {
            console.error('Failed to load filter options:', error);
            // Continue with hardcoded options (graceful degradation)
        }
    },

    /**
     * Populate a select element with options
     * @private
     */
    _populateSelect(selectElement, options, defaultLabel) {
        const currentValue = selectElement.value;
        const hasHtmxAttrs = selectElement.hasAttribute('hx-get');

        // Store HTMX attributes
        const htmxAttrs = hasHtmxAttrs ? {
            'hx-get': selectElement.getAttribute('hx-get'),
            'hx-target': selectElement.getAttribute('hx-target'),
            'hx-trigger': selectElement.getAttribute('hx-trigger'),
            'hx-include': selectElement.getAttribute('hx-include')
        } : {};

        // Clear existing options
        selectElement.innerHTML = `<option value="">${defaultLabel}</option>`;

        // Add new options
        options.forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option;
            optionElement.textContent = option;
            if (option === currentValue) {
                optionElement.selected = true;
            }
            selectElement.appendChild(optionElement);
        });

        // Restore HTMX attributes
        if (hasHtmxAttrs) {
            Object.entries(htmxAttrs).forEach(([attr, value]) => {
                if (value) selectElement.setAttribute(attr, value);
            });
        }
    }
};

// Expose to global scope for onclick handlers (backward compatibility)
window.FilterManager = FilterManager;
window.setPeriod = FilterManager.setPeriod.bind(FilterManager);
window.clearFilters = FilterManager.clearAll.bind(FilterManager);

// Auto-initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        // Check if we're on a page with filters
        if (document.getElementById('filters-form')) {
            FilterManager.loadDynamicOptions();
        }
    });
} else {
    // DOM already loaded
    if (document.getElementById('filters-form')) {
        FilterManager.loadDynamicOptions();
    }
}
