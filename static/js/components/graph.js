/**
 * Graph Component - MnemoLite UI
 *
 * Cytoscape.js graph visualization with SCADA industrial styling.
 * Manages graph rendering, layouts, filters, and interactions.
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
                            const type = ele.data('type');
                            if (type === 'event') return '#667eea';
                            if (type === 'entity') return '#f5576c';
                            if (type === 'concept') return '#00f2fe';
                            return '#20e3b2';
                        },
                        'label': 'data(label)',
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
 * Setup hover tooltips for nodes
 */
function setupHoverTooltips() {
    let tooltip = null;

    cy.on('mouseover', 'node', function(evt) {
        const node = evt.target;
        const pos = evt.renderedPosition;

        tooltip = document.createElement('div');
        tooltip.className = 'node-tooltip';
        tooltip.style.left = (pos.x + 20) + 'px';
        tooltip.style.top = (pos.y - 20) + 'px';
        tooltip.innerHTML = `
            <div class="tooltip-title">${node.data('label')}</div>
            <div class="tooltip-type">${node.data('type')}</div>
            <div class="tooltip-content">Click to view details</div>
        `;
        document.querySelector('.graph-canvas').appendChild(tooltip);
    });

    cy.on('mouseout', 'node', function() {
        if (tooltip) {
            tooltip.remove();
            tooltip = null;
        }
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
        const response = await fetch('/api/graph/nodes?limit=100');
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
    const type = data.type || 'unknown';

    icon.textContent = type === 'event' ? '📅' : type === 'entity' ? '🏢' : '💡';
    title.textContent = 'NODE DETAILS';

    let badgeClass = type;
    let html = `
        <div class="node-badge ${badgeClass}">
            ${icon.textContent} ${type}
        </div>

        <div class="detail-section">
            <div class="detail-section-title">Basic Information</div>
            <div class="detail-row">
                <div class="detail-label">Label</div>
                <div class="detail-value"><strong>${data.label || 'Unnamed'}</strong></div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Node ID</div>
                <div class="detail-value"><code>${data.id.substring(0, 16)}...</code></div>
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
                <div class="detail-label">Incoming Edges</div>
                <div class="detail-value">${node.indegree()} in</div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Outgoing Edges</div>
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
            html += `
                <div class="detail-row">
                    <div class="detail-label">${key}</div>
                    <div class="detail-value">${JSON.stringify(value)}</div>
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
    title.textContent = 'EDGE DETAILS';

    let html = `
        <div class="detail-section">
            <div class="detail-section-title">Edge Information</div>
            <div class="detail-row">
                <div class="detail-label">Relationship</div>
                <div class="detail-value"><strong>${data.label || 'related_to'}</strong></div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Edge ID</div>
                <div class="detail-value"><code>${data.id.substring(0, 16)}...</code></div>
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
                <div class="detail-value"><code>${data.source.substring(0, 16)}...</code></div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Target Node</div>
                <div class="detail-value"><code>${data.target.substring(0, 16)}...</code></div>
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

    const eventCount = cy.nodes('[type="event"]').length;
    const entityCount = cy.nodes('[type="entity"]').length;
    const conceptCount = cy.nodes('[type="concept"]').length;

    document.getElementById('count-event').textContent = eventCount;
    document.getElementById('count-entity').textContent = entityCount;
    document.getElementById('count-concept').textContent = conceptCount;
}

/**
 * Update node filters based on checkboxes
 */
function updateFilters() {
    if (!cy) return;

    const eventChecked = document.getElementById('filter-event').checked;
    const entityChecked = document.getElementById('filter-entity').checked;
    const conceptChecked = document.getElementById('filter-concept').checked;

    cy.nodes().removeClass('filtered');

    if (!eventChecked) {
        cy.nodes('[type="event"]').addClass('filtered');
    }
    if (!entityChecked) {
        cy.nodes('[type="entity"]').addClass('filtered');
    }
    if (!conceptChecked) {
        cy.nodes('[type="concept"]').addClass('filtered');
    }

    // Update filter item styling
    document.querySelector('[data-type="event"]').classList.toggle('active', eventChecked);
    document.querySelector('[data-type="entity"]').classList.toggle('active', entityChecked);
    document.querySelector('[data-type="concept"]').classList.toggle('active', conceptChecked);
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
