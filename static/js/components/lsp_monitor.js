/**
 * LSP Health Monitor (EPIC-14 Story 14.3)
 *
 * Real-time monitoring of LSP server health with Chart.js visualizations:
 * - LSP server status indicator (running/idle/error)
 * - Uptime tracking
 * - Query count metrics
 * - Cache hit rate (donut chart)
 * - Type coverage (bar chart)
 * - Auto-refresh every 30s
 */

class LSPMonitor {
    constructor() {
        this.cacheChart = null;
        this.metadataChart = null;
        this.refreshInterval = null;
        this.REFRESH_RATE_MS = 30000; // 30 seconds
    }

    /**
     * Initialize the LSP monitor
     * Sets up charts and starts auto-refresh
     * EPIC-14 Fix: Initialize charts BEFORE fetching data to prevent race condition
     */
    async init() {
        console.log('[LSP Monitor] Initializing...');

        // EPIC-14 Fix: Initialize charts FIRST (before data fetch)
        this.initCacheChart();
        this.initMetadataChart();

        // Initial data load (charts are now ready to receive data)
        await this.fetchAndUpdate();

        // Start auto-refresh
        this.startAutoRefresh();

        console.log('[LSP Monitor] Initialized successfully');
    }

    /**
     * Fetch LSP stats from API and update UI
     */
    async fetchAndUpdate() {
        try {
            const response = await fetch('/ui/lsp/stats');

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();

            // Update status indicator
            this.updateStatusIndicator(data.status);

            // Update KPIs
            this.updateKPIs(data);

            // Update charts
            this.updateCharts(data);

            // Update last indexed timestamp
            this.updateLastIndexed(data.timestamps.last_indexed);

            console.log('[LSP Monitor] Data updated successfully');

        } catch (error) {
            console.error('[LSP Monitor] Failed to fetch stats:', error);
            this.updateStatusIndicator('error');
        }
    }

    /**
     * Update LSP status indicator (running/idle/error)
     */
    updateStatusIndicator(status) {
        const indicator = document.getElementById('lsp-status-indicator');
        if (!indicator) return;

        const dot = indicator.querySelector('.status-dot');
        const text = indicator.querySelector('.status-text');

        // Remove all status classes
        dot.classList.remove('status-running', 'status-idle', 'status-error');

        // Add appropriate status class
        dot.classList.add(`status-${status}`);

        // Update text
        const statusLabels = {
            running: 'Running',
            idle: 'Idle',
            error: 'Error'
        };
        text.textContent = statusLabels[status] || 'Unknown';
    }

    /**
     * Update KPI cards with latest data
     */
    updateKPIs(data) {
        // Uptime
        const uptimeEl = document.getElementById('lsp-uptime');
        if (uptimeEl) {
            uptimeEl.textContent = data.uptime.display;
        }

        // Query Count (total chunks)
        const queryCountEl = document.getElementById('lsp-query-count');
        if (queryCountEl) {
            queryCountEl.textContent = data.query_count.total_chunks.toLocaleString();
        }

        // Cache Hit Rate
        const cacheHitRateEl = document.getElementById('lsp-cache-hit-rate');
        if (cacheHitRateEl) {
            cacheHitRateEl.textContent = `${data.cache.hit_rate}%`;

            // Color-code based on performance
            if (data.cache.hit_rate >= 80) {
                cacheHitRateEl.style.color = '#20e3b2'; // Green (good)
            } else if (data.cache.hit_rate >= 50) {
                cacheHitRateEl.style.color = '#ff9800'; // Orange (ok)
            } else {
                cacheHitRateEl.style.color = '#e74c3c'; // Red (poor)
            }
        }

        // Type Coverage
        const typeCoverageEl = document.getElementById('lsp-type-coverage');
        if (typeCoverageEl) {
            typeCoverageEl.textContent = `${data.type_coverage.percentage}%`;

            // Color-code based on coverage
            if (data.type_coverage.percentage >= 70) {
                typeCoverageEl.style.color = '#20e3b2'; // Green (good)
            } else if (data.type_coverage.percentage >= 40) {
                typeCoverageEl.style.color = '#ff9800'; // Orange (ok)
            } else {
                typeCoverageEl.style.color = '#e74c3c'; // Red (poor)
            }
        }
    }

    /**
     * Initialize Cache Performance Donut Chart
     */
    initCacheChart() {
        const canvas = document.getElementById('lsp-cache-chart');
        if (!canvas) {
            console.warn('[LSP Monitor] Cache chart canvas not found');
            return;
        }

        const ctx = canvas.getContext('2d');

        this.cacheChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Hits', 'Misses'],
                datasets: [{
                    data: [0, 0],
                    backgroundColor: [
                        'rgba(74, 144, 226, 0.8)',  // Blue for hits
                        'rgba(231, 76, 60, 0.8)'    // Red for misses
                    ],
                    borderColor: [
                        'rgba(74, 144, 226, 1)',
                        'rgba(231, 76, 60, 1)'
                    ],
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: false // Using custom legend below chart
                    },
                    tooltip: {
                        backgroundColor: 'rgba(13, 17, 23, 0.95)',
                        titleColor: '#ffffff',
                        bodyColor: '#ffffff',
                        borderColor: 'rgba(74, 144, 226, 0.5)',
                        borderWidth: 1,
                        padding: 12,
                        displayColors: true,
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.parsed || 0;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                                return `${label}: ${value.toLocaleString()} (${percentage}%)`;
                            }
                        }
                    }
                },
                cutout: '65%'
            }
        });

        console.log('[LSP Monitor] Cache chart initialized');
    }

    /**
     * Initialize LSP Metadata Coverage Bar Chart
     */
    initMetadataChart() {
        const canvas = document.getElementById('lsp-metadata-chart');
        if (!canvas) {
            console.warn('[LSP Monitor] Metadata chart canvas not found');
            return;
        }

        const ctx = canvas.getContext('2d');

        this.metadataChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Return Types', 'Signatures', 'Params'],
                datasets: [{
                    label: 'Chunks with Metadata',
                    data: [0, 0, 0],
                    backgroundColor: [
                        'rgba(32, 227, 178, 0.8)',  // Cyan for return types
                        'rgba(156, 39, 176, 0.8)',  // Purple for signatures
                        'rgba(255, 152, 0, 0.8)'    // Orange for params
                    ],
                    borderColor: [
                        'rgba(32, 227, 178, 1)',
                        'rgba(156, 39, 176, 1)',
                        'rgba(255, 152, 0, 1)'
                    ],
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: false // Using custom legend below chart
                    },
                    tooltip: {
                        backgroundColor: 'rgba(13, 17, 23, 0.95)',
                        titleColor: '#ffffff',
                        bodyColor: '#ffffff',
                        borderColor: 'rgba(74, 144, 226, 0.5)',
                        borderWidth: 1,
                        padding: 12,
                        callbacks: {
                            label: function(context) {
                                const value = context.parsed.y || 0;
                                return `Chunks: ${value.toLocaleString()}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            color: 'rgba(255, 255, 255, 0.7)',
                            callback: function(value) {
                                return value.toLocaleString();
                            }
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        }
                    },
                    x: {
                        ticks: {
                            color: 'rgba(255, 255, 255, 0.7)'
                        },
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });

        console.log('[LSP Monitor] Metadata chart initialized');
    }

    /**
     * Update chart data from API response
     */
    updateCharts(data) {
        // Update cache chart
        if (this.cacheChart) {
            this.cacheChart.data.datasets[0].data = [
                data.cache.hits,
                data.cache.misses
            ];
            this.cacheChart.update();

            // Update legend values
            document.getElementById('cache-hits').textContent = data.cache.hits.toLocaleString();
            document.getElementById('cache-misses').textContent = data.cache.misses.toLocaleString();
        }

        // Update metadata chart
        if (this.metadataChart) {
            this.metadataChart.data.datasets[0].data = [
                data.query_count.with_return_type,
                data.query_count.with_signature,
                data.query_count.with_params
            ];
            this.metadataChart.update();

            // Update legend values
            document.getElementById('metadata-return-types').textContent =
                data.query_count.with_return_type.toLocaleString();
            document.getElementById('metadata-signatures').textContent =
                data.query_count.with_signature.toLocaleString();
            document.getElementById('metadata-params').textContent =
                data.query_count.with_params.toLocaleString();
        }
    }

    /**
     * Update last indexed timestamp
     */
    updateLastIndexed(timestamp) {
        const el = document.getElementById('lsp-last-indexed');
        if (!el) return;

        if (!timestamp) {
            el.textContent = 'Never';
            return;
        }

        // Format as relative time
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) {
            el.textContent = 'Just now';
        } else if (diffMins < 60) {
            el.textContent = `${diffMins} min${diffMins > 1 ? 's' : ''} ago`;
        } else if (diffHours < 24) {
            el.textContent = `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
        } else {
            el.textContent = `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
        }
    }

    /**
     * Start auto-refresh interval
     */
    startAutoRefresh() {
        // Clear existing interval if any
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }

        // Set new interval
        this.refreshInterval = setInterval(() => {
            console.log('[LSP Monitor] Auto-refreshing...');
            this.fetchAndUpdate();
        }, this.REFRESH_RATE_MS);

        console.log(`[LSP Monitor] Auto-refresh started (${this.REFRESH_RATE_MS / 1000}s interval)`);
    }

    /**
     * Stop auto-refresh interval
     */
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
            console.log('[LSP Monitor] Auto-refresh stopped');
        }
    }

    /**
     * Destroy monitor and clean up resources
     */
    destroy() {
        console.log('[LSP Monitor] Destroying...');

        // Stop auto-refresh
        this.stopAutoRefresh();

        // Destroy charts
        if (this.cacheChart) {
            this.cacheChart.destroy();
            this.cacheChart = null;
        }

        if (this.metadataChart) {
            this.metadataChart.destroy();
            this.metadataChart = null;
        }

        console.log('[LSP Monitor] Destroyed');
    }
}

// Global instance
let lspMonitorInstance = null;

/**
 * Initialize LSP monitor when DOM is ready
 */
document.addEventListener('DOMContentLoaded', () => {
    // Check if LSP widget exists on page
    const widget = document.querySelector('.lsp-health-widget');

    if (widget) {
        lspMonitorInstance = new LSPMonitor();
        lspMonitorInstance.init();

        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            if (lspMonitorInstance) {
                lspMonitorInstance.destroy();
            }
        });
    }
});

// Export for manual initialization if needed
window.LSPMonitor = LSPMonitor;
