/**
 * Monitoring Component - MnemoLite UI
 *
 * Real-time operational monitoring dashboard for MCO with:
 * - System status (operational/degraded/critical)
 * - KPI cards (critical/warning/info event counts)
 * - Timeline chart (24h event trends with ECharts)
 * - Critical events list
 * - Event distribution analysis
 * - Auto-refresh (30s interval)
 */

// Global state
let currentPeriod = '24h';
let autoRefreshInterval = null;
let timelineChart = null;

/**
 * Initialize ECharts timeline
 */
function initChart() {
    const chartDom = document.getElementById('timeline-chart');
    if (!chartDom) {
        console.error('Timeline chart container not found');
        return;
    }

    timelineChart = echarts.init(chartDom, null, {
        renderer: 'canvas'
    });

    const option = {
        backgroundColor: 'transparent',
        grid: {
            left: 50,
            right: 20,
            top: 30,
            bottom: 30
        },
        tooltip: {
            trigger: 'axis',
            backgroundColor: '#161b22',
            borderColor: '#30363d',
            borderWidth: 1,
            textStyle: {
                color: '#c9d1d9',
                fontFamily: 'Courier New, monospace',
                fontSize: 11
            }
        },
        xAxis: {
            type: 'time',
            axisLine: { lineStyle: { color: '#30363d' } },
            axisLabel: {
                color: '#8b949e',
                fontSize: 10,
                fontFamily: 'Courier New, monospace'
            },
            splitLine: {
                show: true,
                lineStyle: { color: '#21262d', type: 'dashed' }
            }
        },
        yAxis: {
            type: 'value',
            axisLine: { lineStyle: { color: '#30363d' } },
            axisLabel: {
                color: '#8b949e',
                fontSize: 10,
                fontFamily: 'Courier New, monospace'
            },
            splitLine: {
                lineStyle: { color: '#21262d', type: 'dashed' }
            }
        },
        series: [{
            name: 'Événements',
            type: 'line',
            smooth: false,
            symbol: 'circle',
            symbolSize: 6,
            lineStyle: {
                color: '#58a6ff',
                width: 2
            },
            itemStyle: {
                color: '#58a6ff',
                borderColor: '#0d1117',
                borderWidth: 2
            },
            areaStyle: {
                color: {
                    type: 'linear',
                    x: 0, y: 0, x2: 0, y2: 1,
                    colorStops: [
                        { offset: 0, color: 'rgba(88, 166, 255, 0.3)' },
                        { offset: 1, color: 'rgba(88, 166, 255, 0.05)' }
                    ]
                }
            },
            data: []
        }]
    };

    timelineChart.setOption(option);
}

/**
 * Fetch system status from API
 */
async function fetchStatus() {
    try {
        const response = await fetch('/api/monitoring/status');
        const data = await response.json();

        const banner = document.getElementById('status-banner');
        const icon = document.getElementById('status-icon');
        const text = document.getElementById('status-text');
        const timestamp = document.getElementById('status-timestamp');

        // Update status
        banner.className = `status-banner ${data.status}`;

        if (data.status === 'operational') {
            icon.textContent = '🟢';
            text.textContent = 'SYSTÈME OPÉRATIONNEL';
        } else if (data.status === 'degraded') {
            icon.textContent = '🟠';
            text.textContent = 'SYSTÈME DÉGRADÉ';
        } else if (data.status === 'critical') {
            icon.textContent = '🔴';
            text.textContent = 'SYSTÈME CRITIQUE';
        } else {
            icon.textContent = '⚪';
            text.textContent = 'STATUT INCONNU';
        }

        const date = new Date(data.timestamp);
        timestamp.textContent = `Dernière mise à jour: ${date.toLocaleString('fr-FR')}`;

        // Update KPIs
        document.getElementById('kpi-critical').textContent = data.summary.critical;
        document.getElementById('kpi-warning').textContent = data.summary.warning;
        document.getElementById('kpi-info').textContent = data.summary.info;

    } catch (error) {
        console.error('Failed to fetch status:', error);
        if (window.ErrorHandler) {
            window.ErrorHandler.showError('Erreur de chargement du statut système');
        }
    }
}

/**
 * Fetch system metrics from API
 */
async function fetchMetrics() {
    try {
        const response = await fetch('/api/monitoring/metrics');
        const data = await response.json();

        document.getElementById('kpi-dbsize').textContent = data.db_size_mb.toFixed(1);

    } catch (error) {
        console.error('Failed to fetch metrics:', error);
    }
}

/**
 * Fetch critical events from API
 */
async function fetchCriticalEvents() {
    try {
        const response = await fetch('/api/monitoring/events/critical?limit=10');
        const events = await response.json();

        const container = document.getElementById('critical-events');

        if (events.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">✓</div>
                    <div class="empty-state-text">Aucun événement critique (24h)</div>
                </div>
            `;
            return;
        }

        container.innerHTML = events.map(event => {
            const project = event.metadata?.project || 'unknown';
            const category = event.metadata?.category || 'unknown';

            return `
                <div class="event-item">
                    <div class="event-header">
                        <span class="event-severity">CRITICAL</span>
                        <span class="event-time">${event.age}</span>
                    </div>
                    <div class="event-content">${event.content}</div>
                    <div class="event-metadata">
                        <span class="event-tag">📁 ${project}</span>
                        <span class="event-tag">🏷 ${category}</span>
                    </div>
                </div>
            `;
        }).join('');

    } catch (error) {
        console.error('Failed to fetch critical events:', error);
        document.getElementById('critical-events').innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⚠</div>
                <div class="empty-state-text">Erreur de chargement</div>
            </div>
        `;
    }
}

/**
 * Fetch timeline data from API
 */
async function fetchTimeline() {
    try {
        const response = await fetch(`/api/monitoring/events/timeline?period=${currentPeriod}`);
        const data = await response.json();

        if (timelineChart && data.length > 0) {
            timelineChart.setOption({
                series: [{
                    data: data.map(d => [d.time, d.count])
                }]
            });
        }

    } catch (error) {
        console.error('Failed to fetch timeline:', error);
    }
}

/**
 * Fetch distribution data from API
 */
async function fetchDistribution() {
    try {
        const response = await fetch(`/api/monitoring/events/distribution?period=${currentPeriod}`);
        const data = await response.json();

        // Severity distribution
        const sevContainer = document.getElementById('dist-severity');
        if (data.by_severity.length > 0) {
            sevContainer.innerHTML = data.by_severity.map(item => `
                <div class="distribution-item">
                    <span class="distribution-label">${item.label}</span>
                    <span class="distribution-value">${item.count}</span>
                </div>
            `).join('');
        } else {
            sevContainer.innerHTML = '<div class="empty-state"><div class="empty-state-text">Aucune donnée</div></div>';
        }

        // Project distribution
        const projContainer = document.getElementById('dist-project');
        if (data.by_project.length > 0) {
            projContainer.innerHTML = data.by_project.map(item => `
                <div class="distribution-item">
                    <span class="distribution-label">${item.label}</span>
                    <span class="distribution-value">${item.count}</span>
                </div>
            `).join('');
        } else {
            projContainer.innerHTML = '<div class="empty-state"><div class="empty-state-text">Aucune donnée</div></div>';
        }

        // Category distribution
        const catContainer = document.getElementById('dist-category');
        if (data.by_category.length > 0) {
            catContainer.innerHTML = data.by_category.map(item => `
                <div class="distribution-item">
                    <span class="distribution-label">${item.label}</span>
                    <span class="distribution-value">${item.count}</span>
                </div>
            `).join('');
        } else {
            catContainer.innerHTML = '<div class="empty-state"><div class="empty-state-text">Aucune donnée</div></div>';
        }

    } catch (error) {
        console.error('Failed to fetch distribution:', error);
    }
}

/**
 * Refresh all monitoring data
 */
async function refreshAll() {
    await Promise.all([
        fetchStatus(),
        fetchMetrics(),
        fetchCriticalEvents(),
        fetchTimeline(),
        fetchDistribution()
    ]);
}

/**
 * Setup auto-refresh mechanism
 */
function setupAutoRefresh() {
    const checkbox = document.getElementById('auto-refresh');

    checkbox.addEventListener('change', () => {
        if (checkbox.checked) {
            autoRefreshInterval = setInterval(refreshAll, 30000);
        } else {
            if (autoRefreshInterval) {
                clearInterval(autoRefreshInterval);
                autoRefreshInterval = null;
            }
        }
    });

    // Start auto-refresh if checked
    if (checkbox.checked) {
        autoRefreshInterval = setInterval(refreshAll, 30000);
    }

    // Pause when tab not visible (performance optimization)
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            if (autoRefreshInterval) {
                clearInterval(autoRefreshInterval);
                autoRefreshInterval = null;
                console.log('[Monitoring] Auto-refresh paused (tab hidden)');
            }
        } else {
            if (checkbox.checked && !autoRefreshInterval) {
                autoRefreshInterval = setInterval(refreshAll, 30000);
                console.log('[Monitoring] Auto-refresh resumed (tab visible)');
            }
        }
    });
}

/**
 * Setup period filter buttons
 */
function setupPeriodFilters() {
    document.querySelectorAll('.filter-btn[data-period]').forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove active class from all buttons
            document.querySelectorAll('.filter-btn[data-period]').forEach(b => b.classList.remove('active'));

            // Add active class to clicked button
            btn.classList.add('active');

            // Update period and refresh data
            currentPeriod = btn.dataset.period;
            fetchTimeline();
            fetchDistribution();
        });
    });
}

/**
 * Initialize monitoring dashboard
 */
function initMonitoring() {
    initChart();
    refreshAll();
    setupAutoRefresh();
    setupPeriodFilters();
}

// Expose to global scope for onclick handlers
window.refreshAll = refreshAll;

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMonitoring);
} else {
    initMonitoring();
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    if (timelineChart) {
        timelineChart.dispose();
    }
});
