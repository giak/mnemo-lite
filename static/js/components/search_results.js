/**
 * EPIC-14 Story 14.1: Enhanced Search Results with Performance & UX
 *
 * Features:
 * - Progressive disclosure (expand/collapse cards)
 * - Keyboard navigation (j/k/Enter/c/o)
 * - Copy-to-clipboard
 * - Focus management
 * - Virtual scrolling (for 1000+ results)
 * - ARIA accessibility
 *
 * @version 1.0.0
 * @date 2025-10-22
 */

class SearchResultsManager {
    constructor() {
        this.container = null;
        this.cards = [];
        this.activeIndex = -1;
        this.expandedCards = new Set();

        // Performance: Track visible cards for virtual scrolling
        this.observer = null;
        this.virtualScrollEnabled = false;

        // EPIC-14 Fix: Store event handler reference for cleanup
        this.keydownHandler = null;

        this.init();
    }

    /**
     * Initialize search results manager
     */
    init() {
        // Wait for DOM ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setup());
        } else {
            this.setup();
        }

        // Re-initialize when HTMX loads new results
        document.body.addEventListener('htmx:afterSettle', (event) => {
            if (event.detail.target.id === 'code-results-container' ||
                event.detail.target.closest('#code-results-container')) {
                this.setup();
            }
        });
    }

    /**
     * Setup search results interactions
     */
    setup() {
        this.container = document.getElementById('code-results-container');
        if (!this.container) return;

        this.cards = Array.from(this.container.querySelectorAll('.code-card'));

        if (this.cards.length === 0) return;

        // Enable virtual scrolling for 50+ results
        if (this.cards.length > 50) {
            this.enableVirtualScrolling();
        }

        // Setup event listeners
        this.setupCardListeners();
        this.setupKeyboardNavigation();
        this.setupCopyButtons();

        console.log(`[SearchResults] Initialized with ${this.cards.length} cards`);
    }

    /**
     * Setup expand/collapse listeners for each card
     */
    setupCardListeners() {
        this.cards.forEach((card, index) => {
            const expandBtn = card.querySelector('.expand-btn');
            const body = card.querySelector('.code-body');

            if (!expandBtn || !body) return;

            // Click on expand button
            expandBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleCard(index);
            });

            // Click anywhere on card header (but not body)
            const header = card.querySelector('.code-header');
            header.addEventListener('click', (e) => {
                // Don't expand if clicking on type badge or other interactive elements
                if (e.target.closest('.expand-btn') ||
                    e.target.closest('.type-badge') ||
                    e.target.closest('.copy-btn')) {
                    return;
                }
                this.toggleCard(index);
            });

            // Focus on card
            card.addEventListener('focus', () => {
                this.setActiveCard(index);
            });
        });
    }

    /**
     * Toggle card expand/collapse
     * @param {number} index - Card index
     */
    toggleCard(index) {
        const card = this.cards[index];
        const expandBtn = card.querySelector('.expand-btn');
        const body = card.querySelector('.code-body');

        if (!expandBtn || !body) return;

        const isExpanded = expandBtn.getAttribute('aria-expanded') === 'true';

        if (isExpanded) {
            // Collapse
            expandBtn.setAttribute('aria-expanded', 'false');
            expandBtn.setAttribute('aria-label', 'Expand details');
            body.setAttribute('aria-hidden', 'true');
            body.hidden = true;
            card.classList.remove('expanded');
            this.expandedCards.delete(index);
        } else {
            // Expand
            expandBtn.setAttribute('aria-expanded', 'true');
            expandBtn.setAttribute('aria-label', 'Collapse details');
            body.setAttribute('aria-hidden', 'false');
            body.hidden = false;
            card.classList.add('expanded');
            this.expandedCards.add(index);

            // Focus management: move focus to expanded content
            // Small delay to allow animation to start
            setTimeout(() => {
                const firstFocusable = body.querySelector('button, a, [tabindex="0"]');
                if (firstFocusable) {
                    // Don't steal focus automatically - let user tab into it
                    // This is better for accessibility
                }
            }, 100);
        }

        console.log(`[SearchResults] Toggled card ${index}: ${!isExpanded ? 'expanded' : 'collapsed'}`);
    }

    /**
     * Set active card (keyboard navigation)
     * @param {number} index - Card index
     */
    setActiveCard(index) {
        // Remove active class from all cards
        this.cards.forEach(c => c.classList.remove('active'));

        // Add active class to new card
        if (index >= 0 && index < this.cards.length) {
            this.activeIndex = index;
            const card = this.cards[index];
            card.classList.add('active');
            card.focus();

            // Scroll into view if needed
            card.scrollIntoView({
                behavior: 'smooth',
                block: 'nearest'
            });
        }
    }

    /**
     * Setup keyboard navigation (j/k/Enter/c/o)
     * EPIC-14 Fix: Store handler reference for cleanup
     */
    setupKeyboardNavigation() {
        // Remove old listener if exists
        if (this.keydownHandler) {
            document.removeEventListener('keydown', this.keydownHandler);
        }

        // Create and store new handler
        this.keydownHandler = (e) => {
            // Only handle shortcuts when not typing in input/textarea
            if (e.target.matches('input, textarea, select')) {
                return;
            }

            // Get current active card
            const activeCard = this.cards[this.activeIndex];

            switch(e.key.toLowerCase()) {
                case 'j': // Next card
                    e.preventDefault();
                    this.navigateNext();
                    break;

                case 'k': // Previous card
                    e.preventDefault();
                    this.navigatePrevious();
                    break;

                case 'enter': // Expand/collapse current card
                    if (this.activeIndex >= 0) {
                        e.preventDefault();
                        this.toggleCard(this.activeIndex);
                    }
                    break;

                case 'c': // Copy signature of active card
                    if (this.activeIndex >= 0 && activeCard) {
                        e.preventDefault();
                        const copyBtn = activeCard.querySelector('.copy-btn');
                        if (copyBtn) {
                            copyBtn.click();
                        }
                    }
                    break;

                case 'o': // Open (expand) all cards
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.expandAll();
                    }
                    break;

                case 'escape': // Collapse all cards
                    e.preventDefault();
                    this.collapseAll();
                    break;
            }
        };

        document.addEventListener('keydown', this.keydownHandler);

        console.log('[SearchResults] Keyboard navigation enabled (j/k/Enter/c/o/Escape)');
    }

    /**
     * Navigate to next card
     */
    navigateNext() {
        if (this.cards.length === 0) return;

        const nextIndex = this.activeIndex < this.cards.length - 1
            ? this.activeIndex + 1
            : this.activeIndex;

        this.setActiveCard(nextIndex);
    }

    /**
     * Navigate to previous card
     */
    navigatePrevious() {
        if (this.cards.length === 0) return;

        const prevIndex = this.activeIndex > 0
            ? this.activeIndex - 1
            : 0;

        this.setActiveCard(prevIndex);
    }

    /**
     * Expand all cards
     */
    expandAll() {
        this.cards.forEach((_, index) => {
            const expandBtn = this.cards[index].querySelector('.expand-btn');
            if (expandBtn && expandBtn.getAttribute('aria-expanded') === 'false') {
                this.toggleCard(index);
            }
        });
        console.log('[SearchResults] Expanded all cards');
    }

    /**
     * Collapse all cards
     */
    collapseAll() {
        this.cards.forEach((_, index) => {
            const expandBtn = this.cards[index].querySelector('.expand-btn');
            if (expandBtn && expandBtn.getAttribute('aria-expanded') === 'true') {
                this.toggleCard(index);
            }
        });
        console.log('[SearchResults] Collapsed all cards');
    }

    /**
     * Setup copy-to-clipboard buttons
     */
    setupCopyButtons() {
        const copyButtons = this.container.querySelectorAll('.copy-btn');

        copyButtons.forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation(); // Don't trigger card toggle

                const textToCopy = btn.getAttribute('data-copy');
                if (!textToCopy) return;

                try {
                    await navigator.clipboard.writeText(textToCopy);

                    // Visual feedback
                    btn.classList.add('copied');
                    const originalText = btn.querySelector('.copy-text').textContent;

                    setTimeout(() => {
                        btn.classList.remove('copied');
                    }, 2000);

                    console.log('[SearchResults] Copied to clipboard:', textToCopy.substring(0, 50) + '...');
                } catch (err) {
                    console.error('[SearchResults] Failed to copy:', err);

                    // Fallback: Create temporary textarea
                    const textarea = document.createElement('textarea');
                    textarea.value = textToCopy;
                    textarea.style.position = 'absolute';
                    textarea.style.left = '-9999px';
                    document.body.appendChild(textarea);
                    textarea.select();
                    try {
                        document.execCommand('copy');
                        btn.classList.add('copied');
                        setTimeout(() => btn.classList.remove('copied'), 2000);
                    } catch (e) {
                        console.error('[SearchResults] Fallback copy failed:', e);
                    }
                    document.body.removeChild(textarea);
                }
            });
        });

        console.log(`[SearchResults] Setup ${copyButtons.length} copy buttons`);
    }

    /**
     * Enable virtual scrolling for performance with 1000+ results
     * Uses Intersection Observer API to only render visible cards
     */
    enableVirtualScrolling() {
        if (!('IntersectionObserver' in window)) {
            console.warn('[SearchResults] IntersectionObserver not supported, virtual scrolling disabled');
            return;
        }

        const options = {
            root: null, // viewport
            rootMargin: '200px', // Load 200px before entering viewport
            threshold: 0
        };

        // EPIC-14 Fix: Store original content for restoration
        this.observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                const card = entry.target;
                const body = card.querySelector('.code-body');

                if (entry.isIntersecting) {
                    // Card entering viewport - restore content if cleared
                    card.style.opacity = '1';

                    if (body && body.dataset.originalContent && body.innerHTML === '') {
                        body.innerHTML = body.dataset.originalContent;
                    }
                } else {
                    // Card leaving viewport - can collapse to save memory
                    // Only collapse if not expanded by user
                    const index = this.cards.indexOf(card);
                    if (!this.expandedCards.has(index)) {
                        // Keep header visible, but can defer body rendering
                        if (body && body.hasAttribute('data-deferred')) {
                            // Store original content before clearing
                            if (!body.dataset.originalContent) {
                                body.dataset.originalContent = body.innerHTML;
                            }
                            body.innerHTML = ''; // Clear to save memory
                        }
                    }
                }
            });
        }, options);

        // Observe all cards
        this.cards.forEach(card => {
            this.observer.observe(card);
        });

        this.virtualScrollEnabled = true;
        console.log(`[SearchResults] Virtual scrolling enabled for ${this.cards.length} cards`);
    }

    /**
     * Cleanup observers and event listeners on destroy
     * EPIC-14 Fix: Prevent memory leaks
     */
    destroy() {
        // Disconnect intersection observer
        if (this.observer) {
            this.observer.disconnect();
            this.observer = null;
        }

        // Remove keyboard event listener
        if (this.keydownHandler) {
            document.removeEventListener('keydown', this.keydownHandler);
            this.keydownHandler = null;
        }

        console.log('[SearchResults] Cleanup complete');
    }
}

// Initialize search results manager globally
window.searchResultsManager = new SearchResultsManager();

console.log('[SearchResults] Module loaded - EPIC-14 Story 14.1');
