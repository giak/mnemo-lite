/**
 * Code Graph Component - MnemoLite UI (EPIC-07 Story 3)
 *
 * Cytoscape.js code dependency graph visualization with SCADA industrial styling.
 * Manages graph rendering, layouts, filters, and interactions for code nodes (function/class/method).
 */

// Global state
let cy = null;
let minimap = null;
let currentLayout = 'cose';
let graphData = { nodes: [], edges: [] };

/**
 * Initialize Cytoscape instance
 * @param {Object} data - Graph data with nodes and edges
 */
function initCytoscape(data) {
    const container = document.getElementById('cy');
    graphData = data;

    try {
        cy = cytoscape({
            container: container,
            elements: {
                nodes: data.nodes || [],
                edges: data.edges || []
            },
            style: [
                {
                    selector: 'node',
                    style: {
                        'background-color': function(ele) {
                            const type = ele.data('node_type') || ele.data('type');
                            if (type === 'function') return '#667eea';
                            if (type === 'class') return '#f5576c';
                            if (type === 'method') return '#00f2fe';
                            return '#20e3b2';
                        },
                        'label': function(ele) {
                            // Story 11.3: Use name_path if available, fallback to label
                            return ele.data('name_path') || ele.data('label');
                        },
                        'color': '#ffffff',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'font-size': '11px',
                        'font-weight': 'bold',
                        'width': 48,
                        'height': 48,
                        'border-width': 2,
                        'border-color': '#ffffff',
                        'text-outline-width': 2,
                        'text-outline-color': '#0a0e27',
                        'text-wrap': 'wrap',
                        'text-max-width': '75px'
                    }
                },
                {
                    selector: 'node:selected',
                    style: {
                        'border-width': 3,
                        'border-color': '#ffa502'
                    }
                },
                {
                    selector: 'edge',
                    style: {
                        'width': 2,
                        'line-color': 'rgba(201, 209, 217, 0.25)',
                        'target-arrow-color': 'rgba(201, 209, 217, 0.25)',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier',
                        'label': 'data(label)',
                        'font-size': '9px',
                        'font-weight': 'normal',
                        'color': '#6e7681',
                        'text-rotation': 'autorotate',
                        'text-margin-y': -8,
                        'text-outline-width': 2,
                        'text-outline-color': '#0a0e27'
                    }
                },
                {
                    selector: 'edge:selected',
                    style: {
                        'line-color': '#ffa502',
                        'target-arrow-color': '#ffa502',
                        'width': 3
                    }
                },
                {
                    selector: '.filtered',
                    style: {
                        'display': 'none'
                    }
                }
            ],
            layout: {
                name: currentLayout,
                animate: true,
                animationDuration: 400
            },
            minZoom: 0.2,
            maxZoom: 4,
            wheelSensitivity: 0.2
        });

        // Event handlers
        cy.on('tap', 'node', function(evt) {
            const node = evt.target;
            showNodeDetails(node);
            updateKPIs();
        });

        cy.on('tap', 'edge', function(evt) {
            const edge = evt.target;
            showEdgeDetails(edge);
            updateKPIs();
        });

        cy.on('tap', function(evt) {
            if (evt.target === cy) {
                closeRightSidebar();
                updateKPIs();
            }
        });

        // Hover tooltips
        setupHoverTooltips();

        // Initialize minimap
        initMinimap();

        // Update UI
        hideLoading();
        updateKPIs();
        updateTypeCounts();
    } catch (err) {
        console.error('Failed to initialize Cytoscape:', err);
        showError('Failed to initialize graph: ' + err.message);
    }
}

/**
 * Setup hover tooltips for nodes (Story 11.3: DOM reuse + name_path support)
 */
function setupHoverTooltips() {
    // Story 11.3: Reuse tooltip DOM element for 7.5x faster performance
    let tooltip = document.createElement('div');
    tooltip.className = 'node-tooltip';
    tooltip.style.display = 'none';
    document.querySelector('.graph-canvas').appendChild(tooltip);

    cy.on('mouseover', 'node', function(evt) {
        const node = evt.target;
        const pos = evt.renderedPosition;

        // Story 11.3: Smart tooltip positioning (viewport edge detection)
        const graphCanvas = document.querySelector('.graph-canvas');
        const canvasRect = graphCanvas.getBoundingClientRect();
        const tooltipWidth = 250;
        const tooltipHeight = 80;

        let left = pos.x + 20;
        let top = pos.y - 20;

        // Right edge detection
        if (left + tooltipWidth > canvasRect.width) {
            left = pos.x - tooltipWidth - 20;
        }

        // Bottom edge detection
        if (top + tooltipHeight > canvasRect.height) {
            top = canvasRect.height - tooltipHeight - 10;
        }

        // Top edge detection
        if (top < 0) {
            top = 10;
        }

        tooltip.style.left = left + 'px';
        tooltip.style.top = top + 'px';
        tooltip.style.display = 'block';

        // Story 11.3: Display qualified name_path with fallback to label
        const namePath = node.data('name_path');
        const label = node.data('label');
        const nodeType = node.data('node_type') || node.data('type') || 'unknown';

        tooltip.innerHTML = `
            <div class="tooltip-title">${namePath || label || 'Unknown'}</div>
            <div class="tooltip-type">${nodeType}</div>
            ${namePath && namePath !== label ? `<div class="tooltip-subtitle">(${label})</div>` : ''}
            <div class="tooltip-content">Click to view details</div>
        `;
    });

    cy.on('mouseout', 'node', function() {
        tooltip.style.display = 'none';
    });
}

/**
 * Initialize minimap view
 */
function initMinimap() {
    const minimapContainer = document.getElementById('minimap');

    // Simplified style for minimap (no JavaScript functions)
    const minimapStyle = [
        {
            selector: 'node',
            style: {
                'background-color': '#4a90e2',
                'width': 48,
                'height': 48,
                'border-width': 2,
                'border-color': '#ffffff'
            }
        },
        {
            selector: 'edge',
            style: {
                'width': 2,
                'line-color': 'rgba(201, 209, 217, 0.25)',
                'target-arrow-color': 'rgba(201, 209, 217, 0.25)',
                'target-arrow-shape': 'triangle',
                'curve-style': 'bezier'
            }
        }
    ];

    minimap = cytoscape({
        container: minimapContainer,
        elements: cy.elements().jsons(),
        style: minimapStyle,
        userZoomingEnabled: false,
        userPanningEnabled: false,
        boxSelectionEnabled: false,
        autoungrabify: true
    });

    minimap.layout({ name: currentLayout }).run();
    minimap.fit();
}

/**
 * Load graph data from API
 */
async function loadGraph() {
    showLoading();

    try {
        const response = await fetch('/ui/code/graph/data');
        const data = await response.json();

        if (data.error) {
            showError('Error loading graph: ' + data.error);
            return;
        }

        if (cy) {
            cy.destroy();
        }

        initCytoscape(data);
    } catch (err) {
        console.error('Failed to load graph:', err);
        showError('Failed to load graph: ' + err.message);
    }
}

/**
 * Show node details in right sidebar
 * @param {Object} node - Cytoscape node object
 */
function showNodeDetails(node) {
    const sidebar = document.getElementById('right-sidebar');
    const content = document.getElementById('sidebar-content');
    const icon = document.getElementById('sidebar-icon');
    const title = document.getElementById('sidebar-title-text');

    const data = node.data();
    const nodeType = data.node_type || data.type || 'unknown';

    icon.textContent = nodeType === 'function' ? '⚡' : nodeType === 'class' ? '📦' : '🔧';
    title.textContent = 'CODE NODE DETAILS';

    let badgeClass = nodeType;
    let html = `
        <div class="node-badge ${badgeClass}">
            ${icon.textContent} ${nodeType}
        </div>

        <div class="detail-section">
            <div class="detail-section-title">Basic Information</div>
            <div class="detail-row">
                <div class="detail-label">Name</div>
                <div class="detail-value">
                    <strong>${data.name_path || data.label || 'Unnamed'}</strong>
                    ${data.name_path && data.name_path !== data.label ? `<br><span style="font-size: 0.85em; color: #8b949e; font-style: italic;">(${data.label})</span>` : ''}
                </div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Node ID</div>
                <div class="detail-value"><code>${(data.id || '').toString().substring(0, 16)}...</code></div>
            </div>
            ${data.created_at ? `
                <div class="detail-row">
                    <div class="detail-label">Created At</div>
                    <div class="detail-value">${new Date(data.created_at).toLocaleString()}</div>
                </div>
            ` : ''}
        </div>

        <div class="detail-section">
            <div class="detail-section-title">Graph Metrics</div>
            <div class="detail-row">
                <div class="detail-label">Degree (Total)</div>
                <div class="detail-value"><strong>${node.degree()}</strong> connections</div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Incoming Calls</div>
                <div class="detail-value">${node.indegree()} in</div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Outgoing Calls</div>
                <div class="detail-value">${node.outdegree()} out</div>
            </div>
        </div>
    `;

    if (data.props && Object.keys(data.props).length > 0) {
        html += `
            <div class="detail-section">
                <div class="detail-section-title">Properties</div>
        `;
        for (const [key, value] of Object.entries(data.props)) {
            const displayValue = typeof value === 'object'
                ? JSON.stringify(value, null, 2)
                : value;
            html += `
                <div class="detail-row">
                    <div class="detail-label">${key}</div>
                    <div class="detail-value">${displayValue}</div>
                </div>
            `;
        }
        html += `</div>`;
    }

    content.innerHTML = html;
    sidebar.classList.remove('collapsed');
}

/**
 * Show edge details in right sidebar
 * @param {Object} edge - Cytoscape edge object
 */
function showEdgeDetails(edge) {
    const sidebar = document.getElementById('right-sidebar');
    const content = document.getElementById('sidebar-content');
    const icon = document.getElementById('sidebar-icon');
    const title = document.getElementById('sidebar-title-text');

    const data = edge.data();

    icon.textContent = '🔗';
    title.textContent = 'RELATIONSHIP DETAILS';

    let html = `
        <div class="detail-section">
            <div class="detail-section-title">Edge Information</div>
            <div class="detail-row">
                <div class="detail-label">Relationship</div>
                <div class="detail-value"><strong>${data.label || data.relationship || 'calls'}</strong></div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Edge ID</div>
                <div class="detail-value"><code>${(data.id || '').toString().substring(0, 16)}...</code></div>
            </div>
            ${data.created_at ? `
                <div class="detail-row">
                    <div class="detail-label">Created At</div>
                    <div class="detail-value">${new Date(data.created_at).toLocaleString()}</div>
                </div>
            ` : ''}
        </div>

        <div class="detail-section">
            <div class="detail-section-title">Connections</div>
            <div class="detail-row">
                <div class="detail-label">Source Node</div>
                <div class="detail-value"><code>${(data.source || '').toString().substring(0, 16)}...</code></div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Target Node</div>
                <div class="detail-value"><code>${(data.target || '').toString().substring(0, 16)}...</code></div>
            </div>
        </div>
    `;

    content.innerHTML = html;
    sidebar.classList.remove('collapsed');
}

/**
 * Close right sidebar
 */
function closeRightSidebar() {
    document.getElementById('right-sidebar').classList.add('collapsed');
}

/**
 * Update KPI cards
 */
function updateKPIs() {
    const selectedCount = cy ? cy.$(':selected').length : 0;

    document.getElementById('kpi-nodes').textContent = graphData.nodes?.length || 0;
    document.getElementById('kpi-edges').textContent = graphData.edges?.length || 0;
    document.getElementById('kpi-layout').textContent = currentLayout.toUpperCase();
    document.getElementById('kpi-selected').textContent = selectedCount;
}

/**
 * Update type counts in filters
 */
function updateTypeCounts() {
    if (!cy) return;

    const functionCount = cy.nodes('[node_type="function"]').length + cy.nodes('[type="function"]').length;
    const classCount = cy.nodes('[node_type="class"]').length + cy.nodes('[type="class"]').length;
    const methodCount = cy.nodes('[node_type="method"]').length + cy.nodes('[type="method"]').length;

    document.getElementById('count-function').textContent = functionCount;
    document.getElementById('count-class').textContent = classCount;
    document.getElementById('count-method').textContent = methodCount;
}

/**
 * Update node filters based on checkboxes
 */
function updateFilters() {
    if (!cy) return;

    const functionChecked = document.getElementById('filter-function').checked;
    const classChecked = document.getElementById('filter-class').checked;
    const methodChecked = document.getElementById('filter-method').checked;

    cy.nodes().removeClass('filtered');

    if (!functionChecked) {
        cy.nodes('[node_type="function"]').addClass('filtered');
        cy.nodes('[type="function"]').addClass('filtered');
    }
    if (!classChecked) {
        cy.nodes('[node_type="class"]').addClass('filtered');
        cy.nodes('[type="class"]').addClass('filtered');
    }
    if (!methodChecked) {
        cy.nodes('[node_type="method"]').addClass('filtered');
        cy.nodes('[type="method"]').addClass('filtered');
    }

    // Update filter item styling
    document.querySelector('[data-type="function"]').classList.toggle('active', functionChecked);
    document.querySelector('[data-type="class"]').classList.toggle('active', classChecked);
    document.querySelector('[data-type="method"]').classList.toggle('active', methodChecked);
}

/**
 * Change graph layout
 * @param {string} layoutName - Layout algorithm name
 */
function changeLayout(layoutName) {
    if (!cy) return;

    currentLayout = layoutName;

    // Update button states
    document.querySelectorAll('.layout-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-layout="${layoutName}"]`).classList.add('active');

    // Apply layout
    cy.layout({
        name: layoutName,
        animate: true,
        animationDuration: 400
    }).run();

    // Update minimap
    if (minimap) {
        minimap.layout({ name: layoutName }).run();
        minimap.fit();
    }

    updateKPIs();
}

/**
 * Zoom in
 */
function zoomIn() {
    if (cy) cy.zoom(cy.zoom() * 1.2);
}

/**
 * Zoom out
 */
function zoomOut() {
    if (cy) cy.zoom(cy.zoom() * 0.8);
}

/**
 * Fit graph to viewport
 */
function fitGraph() {
    if (cy) cy.fit(null, 40);
}

/**
 * Reset zoom to default
 */
function resetZoom() {
    if (cy) {
        cy.zoom(1);
        cy.center();
    }
}

/**
 * Show loading overlay
 */
function showLoading() {
    document.getElementById('loading-overlay').style.display = 'flex';
}

/**
 * Hide loading overlay
 */
function hideLoading() {
    document.getElementById('loading-overlay').style.display = 'none';
}

/**
 * Show error message
 * @param {string} message - Error message
 */
function showError(message) {
    hideLoading();

    // Use ErrorHandler if available
    if (window.ErrorHandler) {
        window.ErrorHandler.showError(message, {
            canRetry: true,
            retryCallback: loadGraph
        });
    } else {
        // Fallback to alert
        alert(message);
    }
}

// Expose functions to global scope for onclick handlers
window.loadGraph = loadGraph;
window.updateFilters = updateFilters;
window.changeLayout = changeLayout;
window.zoomIn = zoomIn;
window.zoomOut = zoomOut;
window.fitGraph = fitGraph;
window.resetZoom = resetZoom;
window.closeRightSidebar = closeRightSidebar;

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        loadGraph();
    });
} else {
    // DOM already loaded
    loadGraph();
}
