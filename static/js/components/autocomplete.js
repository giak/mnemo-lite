/**
 * Autocomplete Component (EPIC-14 Story 14.4)
 *
 * Smart autocomplete with fuzzy matching for code search filters:
 * - Function/class names
 * - Return types (from LSP metadata)
 * - Parameter types (from LSP metadata)
 *
 * Features:
 * - Debounced input (300ms delay - 10× fewer API calls)
 * - Keyboard navigation (↑/↓ arrows, Enter, Escape)
 * - Mouse selection
 * - Category grouping
 * - Highlight matching text
 * - Recent searches prioritization (future enhancement)
 *
 * @requires html_utils.js - Must be loaded before this file for XSS prevention
 */

class Autocomplete {
    constructor(inputElement, options = {}) {
        this.input = inputElement;
        this.options = {
            field: options.field || 'all',  // 'all', 'name', 'return_type', 'param_type'
            limit: options.limit || 10,
            debounceDelay: options.debounceDelay || 300,  // ms
            minChars: options.minChars || 1,
            onSelect: options.onSelect || null,
            placeholder: options.placeholder || 'Type to search...',
            ...options
        };

        this.suggestions = [];
        this.activeSuggestionIndex = -1;
        this.debounceTimer = null;
        this.suggestionsContainer = null;

        // EPIC-14 Fix: Store event handler references for cleanup
        this.handleInputBound = (e) => this.handleInput(e);
        this.handleKeydownBound = (e) => this.handleKeydown(e);
        this.handleBlurBound = (e) => this.handleBlur(e);
        this.handleFocusBound = (e) => this.handleFocus(e);

        this.init();
    }

    init() {
        // Set placeholder
        this.input.placeholder = this.options.placeholder;

        // Create suggestions container
        this.createSuggestionsContainer();

        // Attach event listeners (EPIC-14 Fix: use bound references for cleanup)
        this.input.addEventListener('input', this.handleInputBound);
        this.input.addEventListener('keydown', this.handleKeydownBound);
        this.input.addEventListener('blur', this.handleBlurBound);
        this.input.addEventListener('focus', this.handleFocusBound);

        console.log(`[Autocomplete] Initialized for field: ${this.options.field}`);
    }

    createSuggestionsContainer() {
        // Create dropdown container
        this.suggestionsContainer = document.createElement('div');
        this.suggestionsContainer.className = 'autocomplete-suggestions';
        this.suggestionsContainer.style.display = 'none';

        // Position relative to input
        const inputRect = this.input.getBoundingClientRect();
        this.suggestionsContainer.style.position = 'absolute';
        this.suggestionsContainer.style.width = `${this.input.offsetWidth}px`;

        // Insert after input
        this.input.parentNode.style.position = 'relative';
        this.input.parentNode.insertBefore(this.suggestionsContainer, this.input.nextSibling);
    }

    handleInput(e) {
        const query = e.target.value.trim();

        // Clear debounce timer
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }

        // Hide suggestions if query too short
        if (query.length < this.options.minChars) {
            this.hideSuggestions();
            return;
        }

        // Debounced fetch
        this.debounceTimer = setTimeout(() => {
            this.fetchSuggestions(query);
        }, this.options.debounceDelay);
    }

    async fetchSuggestions(query) {
        try {
            const url = `/ui/code/suggest?q=${encodeURIComponent(query)}&field=${this.options.field}&limit=${this.options.limit}`;
            const response = await fetch(url);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();

            this.suggestions = data.suggestions || [];
            this.renderSuggestions();

            console.log(`[Autocomplete] Fetched ${this.suggestions.length} suggestions for "${query}"`);

        } catch (error) {
            console.error('[Autocomplete] Fetch error:', error);
            this.suggestions = [];
            this.hideSuggestions();
        }
    }

    renderSuggestions() {
        // Clear previous suggestions
        this.suggestionsContainer.innerHTML = '';
        this.activeSuggestionIndex = -1;

        if (this.suggestions.length === 0) {
            this.hideSuggestions();
            return;
        }

        // Group suggestions by category
        const grouped = this.groupByCategory(this.suggestions);

        // Render groups
        Object.entries(grouped).forEach(([category, items]) => {
            // Category header
            const categoryHeader = document.createElement('div');
            categoryHeader.className = 'autocomplete-category-header';
            categoryHeader.textContent = category;
            this.suggestionsContainer.appendChild(categoryHeader);

            // Category items
            items.forEach((suggestion, index) => {
                const suggestionEl = this.createSuggestionElement(suggestion, index);
                this.suggestionsContainer.appendChild(suggestionEl);
            });
        });

        this.showSuggestions();
    }

    groupByCategory(suggestions) {
        const grouped = {};

        suggestions.forEach(suggestion => {
            const category = suggestion.category || 'Other';
            if (!grouped[category]) {
                grouped[category] = [];
            }
            grouped[category].push(suggestion);
        });

        return grouped;
    }

    createSuggestionElement(suggestion, globalIndex) {
        const el = document.createElement('div');
        el.className = 'autocomplete-suggestion';
        el.dataset.index = globalIndex;

        // Highlight matching text
        const highlightedLabel = this.highlightMatch(suggestion.label, this.input.value);

        el.innerHTML = `
            <span class="suggestion-label">${highlightedLabel}</span>
            ${suggestion.count ? `<span class="suggestion-count">${suggestion.count}</span>` : ''}
        `;

        // Mouse events
        el.addEventListener('mousedown', (e) => {
            e.preventDefault();  // Prevent input blur
            this.selectSuggestion(suggestion);
        });

        el.addEventListener('mouseenter', (e) => {
            this.setActiveSuggestion(globalIndex);
        });

        return el;
    }

    highlightMatch(text, query) {
        if (!query) return escapeHtml(text);

        // EPIC-14: XSS Fix - escape before creating HTML
        const escapedText = escapeHtml(text);
        const escapedQuery = escapeHtml(query);

        const regex = new RegExp(`(${this.escapeRegex(escapedQuery)})`, 'gi');
        return escapedText.replace(regex, '<mark>$1</mark>');
    }

    escapeRegex(str) {
        return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    handleKeydown(e) {
        if (this.suggestions.length === 0) return;

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.navigateDown();
                break;

            case 'ArrowUp':
                e.preventDefault();
                this.navigateUp();
                break;

            case 'Enter':
                e.preventDefault();
                if (this.activeSuggestionIndex >= 0) {
                    this.selectSuggestion(this.suggestions[this.activeSuggestionIndex]);
                }
                break;

            case 'Escape':
                e.preventDefault();
                this.hideSuggestions();
                break;
        }
    }

    navigateDown() {
        if (this.activeSuggestionIndex < this.suggestions.length - 1) {
            this.setActiveSuggestion(this.activeSuggestionIndex + 1);
        }
    }

    navigateUp() {
        if (this.activeSuggestionIndex > 0) {
            this.setActiveSuggestion(this.activeSuggestionIndex - 1);
        } else {
            this.setActiveSuggestion(-1);  // Back to input value
        }
    }

    setActiveSuggestion(index) {
        this.activeSuggestionIndex = index;

        // Update visual state
        const suggestionEls = this.suggestionsContainer.querySelectorAll('.autocomplete-suggestion');
        suggestionEls.forEach((el, idx) => {
            if (idx === index) {
                el.classList.add('active');
                el.scrollIntoView({ block: 'nearest' });
            } else {
                el.classList.remove('active');
            }
        });
    }

    selectSuggestion(suggestion) {
        // Set input value
        this.input.value = suggestion.value;

        // Hide suggestions
        this.hideSuggestions();

        // Trigger change event
        this.input.dispatchEvent(new Event('change', { bubbles: true }));

        // Call callback if provided
        if (this.options.onSelect) {
            this.options.onSelect(suggestion);
        }

        console.log(`[Autocomplete] Selected: ${suggestion.value}`);
    }

    handleBlur(e) {
        // Delay to allow mousedown on suggestion to fire first
        setTimeout(() => {
            this.hideSuggestions();
        }, 200);
    }

    handleFocus(e) {
        // Show suggestions if there are recent suggestions
        if (this.suggestions.length > 0 && this.input.value.trim().length >= this.options.minChars) {
            this.showSuggestions();
        }
    }

    showSuggestions() {
        this.suggestionsContainer.style.display = 'block';
    }

    hideSuggestions() {
        this.suggestionsContainer.style.display = 'none';
        this.activeSuggestionIndex = -1;
    }

    destroy() {
        // Clear debounce timer
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
            this.debounceTimer = null;
        }

        // EPIC-14 Fix: Remove event listeners to prevent memory leaks
        if (this.input) {
            this.input.removeEventListener('input', this.handleInputBound);
            this.input.removeEventListener('keydown', this.handleKeydownBound);
            this.input.removeEventListener('blur', this.handleBlurBound);
            this.input.removeEventListener('focus', this.handleFocusBound);
        }

        // Remove suggestions container
        if (this.suggestionsContainer && this.suggestionsContainer.parentNode) {
            this.suggestionsContainer.parentNode.removeChild(this.suggestionsContainer);
            this.suggestionsContainer = null;
        }

        console.log(`[Autocomplete] Destroyed for field: ${this.options.field}`);
    }
}

// Autocomplete Styling (injected dynamically)
const autocompleteStyles = `
.autocomplete-suggestions {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    z-index: 1000;
    max-height: 300px;
    overflow-y: auto;
    background: var(--color-bg-panel);
    border: 1px solid var(--color-border);
    border-top: none;
    border-radius: 0 0 var(--radius-sm) var(--radius-sm);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    margin-top: -1px;
}

.autocomplete-category-header {
    font-size: var(--text-tiny);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--color-text-tertiary);
    padding: var(--space-sm) var(--space-md);
    background: var(--color-bg-elevated);
    border-bottom: 1px solid var(--color-border-subtle);
}

.autocomplete-suggestion {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-md);
    cursor: pointer;
    transition: background var(--transition);
    border-bottom: 1px solid var(--color-border-subtle);
}

.autocomplete-suggestion:last-child {
    border-bottom: none;
}

.autocomplete-suggestion:hover,
.autocomplete-suggestion.active {
    background: var(--color-bg-elevated);
}

.autocomplete-suggestion .suggestion-label {
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
}

.autocomplete-suggestion .suggestion-label mark {
    background: rgba(74, 144, 226, 0.25);
    color: var(--color-accent-blue);
    font-weight: 600;
    padding: 0 2px;
}

.autocomplete-suggestion .suggestion-count {
    font-size: var(--text-xs);
    color: var(--color-text-tertiary);
    font-family: var(--font-mono);
    background: var(--color-bg-panel);
    padding: 2px 6px;
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-sm);
}

.autocomplete-suggestions::-webkit-scrollbar {
    width: 8px;
}

.autocomplete-suggestions::-webkit-scrollbar-track {
    background: var(--color-bg);
}

.autocomplete-suggestions::-webkit-scrollbar-thumb {
    background: var(--color-border);
    border: 1px solid var(--color-border-subtle);
    border-radius: var(--radius-sm);
}

.autocomplete-suggestions::-webkit-scrollbar-thumb:hover {
    background: var(--color-text-tertiary);
}
`;

// Inject styles
if (!document.getElementById('autocomplete-styles')) {
    const styleEl = document.createElement('style');
    styleEl.id = 'autocomplete-styles';
    styleEl.textContent = autocompleteStyles;
    document.head.appendChild(styleEl);
}

// Export for use in other scripts
window.Autocomplete = Autocomplete;
