/**
 * Code Graph Component - MnemoLite UI (EPIC-07 Story 3)
 *
 * Cytoscape.js code dependency graph visualization with SCADA industrial styling.
 * Manages graph rendering, layouts, filters, and interactions for code nodes (function/class/method).
 *
 * @requires html_utils.js - Must be loaded before this file for XSS prevention
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
 * EPIC-14 Story 14.2: Enhanced Graph Tooltips with Performance & LSP Metadata
 *
 * Features:
 * - Debounced hover (16ms = 60fps target)
 * - LSP metadata display (return_type, signature, param_types)
 * - Tooltip pooling (DOM reuse)
 * - Smart positioning (viewport edge detection)
 */
function setupHoverTooltips() {
    // Tooltip pooling: Reuse single tooltip DOM element
    let tooltip = document.createElement('div');
    tooltip.className = 'node-tooltip';
    tooltip.style.display = 'none';
    document.querySelector('.graph-canvas').appendChild(tooltip);

    // Debouncing state
    let hoverTimeout = null;
    let hideTimeout = null;
    const HOVER_DELAY_MS = 16; // 16ms = 60fps target
    const HIDE_DELAY_MS = 100; // Slight delay before hiding

    /**
     * Show tooltip for node (debounced)
     * @param {Object} node - Cytoscape node
     * @param {Object} pos - Rendered position
     */
    function showTooltip(node, pos) {
        // Clear any pending hide
        if (hideTimeout) {
            clearTimeout(hideTimeout);
            hideTimeout = null;
        }

        // Clear any pending hover
        if (hoverTimeout) {
            clearTimeout(hoverTimeout);
        }

        // Debounce: Wait 16ms before showing tooltip (60fps)
        hoverTimeout = setTimeout(() => {
            updateTooltipContent(node);
            positionTooltip(pos);
            tooltip.style.display = 'block';
            tooltip.style.opacity = '1';
        }, HOVER_DELAY_MS);
    }

    /**
     * Hide tooltip (debounced)
     */
    function hideTooltip() {
        // Clear any pending show
        if (hoverTimeout) {
            clearTimeout(hoverTimeout);
            hoverTimeout = null;
        }

        // Debounce: Wait before hiding to prevent flicker
        hideTimeout = setTimeout(() => {
            tooltip.style.opacity = '0';
            setTimeout(() => {
                tooltip.style.display = 'none';
            }, 100); // Fade out animation
        }, HIDE_DELAY_MS);
    }

    /**
     * Update tooltip content with node data + LSP metadata
     * @param {Object} node - Cytoscape node
     */
    function updateTooltipContent(node) {
        const data = node.data();

        // Basic node info
        const namePath = data.name_path;
        const label = data.label;
        const nodeType = data.node_type || data.type || 'unknown';

        // LSP metadata (from EPIC-13)
        const props = data.props || {};
        const chunkData = props.chunk_id || {};
        const metadata = chunkData.metadata || {};

        const returnType = metadata.return_type;
        const signature = metadata.signature;
        const paramTypes = metadata.param_types;
        const docstring = metadata.docstring;

        // Build HTML (EPIC-14: XSS Fix - all user data escaped)
        let html = `
            <div class="tooltip-title">${escapeHtml(namePath || label || 'Unknown')}</div>
            <div class="tooltip-type">${escapeHtml(nodeType)}</div>
            ${namePath && namePath !== label ? `<div class="tooltip-subtitle">(${escapeHtml(label)})</div>` : ''}
        `;

        // EPIC-14 Story 14.2: LSP Metadata Section
        if (returnType || signature || paramTypes) {
            html += `<div class="tooltip-divider"></div>`;

            // Return type badge (EPIC-14: XSS Fix)
            if (returnType) {
                const badgeClass = getTypeBadgeClass(returnType);
                html += `
                    <div class="tooltip-lsp-section">
                        <span class="tooltip-lsp-label">Returns:</span>
                        <span class="tooltip-type-badge ${escapeHtml(badgeClass)}">${escapeHtml(simplifyType(returnType))}</span>
                    </div>
                `;
            }

            // Signature (abbreviated) (EPIC-14: XSS Fix)
            if (signature) {
                const shortSig = abbreviateSignature(signature);
                html += `
                    <div class="tooltip-lsp-section">
                        <code class="tooltip-signature">${escapeHtml(shortSig)}</code>
                    </div>
                `;
            }

            // Param count (if available)
            if (paramTypes && Object.keys(paramTypes).length > 0) {
                const paramCount = Object.keys(paramTypes).length;
                html += `
                    <div class="tooltip-lsp-section tooltip-params">
                        <span class="tooltip-lsp-label">${paramCount} param${paramCount > 1 ? 's' : ''}</span>
                    </div>
                `;
            }
        }

        html += `<div class="tooltip-footer">Click to view full details</div>`;

        tooltip.innerHTML = html;
    }

    /**
     * Position tooltip with viewport edge detection
     * @param {Object} pos - Rendered position {x, y}
     */
    function positionTooltip(pos) {
        const graphCanvas = document.querySelector('.graph-canvas');
        const canvasRect = graphCanvas.getBoundingClientRect();

        // Tooltip dimensions (estimated, will be adjusted by CSS)
        const tooltipWidth = 280; // Increased for LSP metadata
        const tooltipHeight = 140; // Increased for LSP metadata

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
    }

    /**
     * Get CSS class for type badge based on type complexity
     * @param {string} type - Type string
     * @returns {string} CSS class
     */
    function getTypeBadgeClass(type) {
        if (!type) return 'type-unknown';

        // Primitive types → blue
        if (['int', 'str', 'float', 'bool', 'None'].includes(type)) {
            return 'type-primitive';
        }

        // Collections → orange
        if (type.startsWith('List[') || type.startsWith('Dict[') || type.startsWith('Set[')) {
            return 'type-collection';
        }

        // Optional → cyan
        if (type.startsWith('Optional[') || type.startsWith('Union[')) {
            return 'type-optional';
        }

        // Complex → purple
        return 'type-complex';
    }

    /**
     * Simplify long type names for tooltip display
     * @param {string} type - Full type string
     * @returns {string} Simplified type
     */
    function simplifyType(type) {
        if (!type) return '?';

        // Truncate very long types
        if (type.length > 30) {
            return type.substring(0, 27) + '...';
        }

        return type;
    }

    /**
     * Abbreviate function signature for tooltip
     * @param {string} signature - Full signature
     * @returns {string} Abbreviated signature
     */
    function abbreviateSignature(signature) {
        if (!signature) return '';

        // If short enough, return as-is
        if (signature.length <= 40) {
            return signature;
        }

        // Extract function name and simplify params
        const match = signature.match(/^([^(]+)\(([^)]*)\)/);
        if (match) {
            const funcName = match[1];
            const params = match[2];

            // Count params
            const paramCount = params.split(',').filter(p => p.trim()).length;

            // Show abbreviated form
            return `${funcName}(${paramCount} param${paramCount > 1 ? 's' : ''})`;
        }

        // Fallback: truncate
        return signature.substring(0, 37) + '...';
    }

    // Event handlers with debouncing
    cy.on('mouseover', 'node', function(evt) {
        const node = evt.target;
        const pos = evt.renderedPosition;
        showTooltip(node, pos);
    });

    cy.on('mouseout', 'node', function() {
        hideTooltip();
    });

    // Also hide on pan/zoom (performance)
    cy.on('pan zoom', function() {
        if (tooltip.style.display === 'block') {
            hideTooltip();
        }
    });

    console.log('[GraphTooltips] EPIC-14 Story 14.2 initialized - Debounced hover @ 16ms');
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
    // EPIC-14: XSS Fix - all user data escaped
    let html = `
        <div class="node-badge ${escapeHtml(badgeClass)}">
            ${icon.textContent} ${escapeHtml(nodeType)}
        </div>

        <div class="detail-section">
            <div class="detail-section-title">Basic Information</div>
            <div class="detail-row">
                <div class="detail-label">Name</div>
                <div class="detail-value">
                    <strong>${escapeHtml(data.name_path || data.label || 'Unnamed')}</strong>
                    ${data.name_path && data.name_path !== data.label ? `<br><span style="font-size: 0.85em; color: #8b949e; font-style: italic;">(${escapeHtml(data.label)})</span>` : ''}
                </div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Node ID</div>
                <div class="detail-value"><code>${escapeHtml((data.id || '').toString().substring(0, 16))}...</code></div>
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

    // EPIC-14: XSS Fix - escape all properties
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
                    <div class="detail-label">${escapeHtml(key)}</div>
                    <div class="detail-value">${escapeHtml(displayValue)}</div>
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

    // EPIC-14: XSS Fix - all user data escaped
    let html = `
        <div class="detail-section">
            <div class="detail-section-title">Edge Information</div>
            <div class="detail-row">
                <div class="detail-label">Relationship</div>
                <div class="detail-value"><strong>${escapeHtml(data.label || data.relationship || 'calls')}</strong></div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Edge ID</div>
                <div class="detail-value"><code>${escapeHtml((data.id || '').toString().substring(0, 16))}...</code></div>
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
                <div class="detail-value"><code>${escapeHtml((data.source || '').toString().substring(0, 16))}...</code></div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Target Node</div>
                <div class="detail-value"><code>${escapeHtml((data.target || '').toString().substring(0, 16))}...</code></div>
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

/**
 * ============================================================
 * EPIC-14 Story 14.5: Graph Legend Toggle & Type Simplification
 * ============================================================
 */

/**
 * Toggle legend visibility with smooth animation
 */
function toggleLegend() {
    const legendContent = document.getElementById('legend-content');
    const toggleIcon = document.getElementById('legend-toggle-icon');

    if (legendContent.classList.contains('collapsed')) {
        // Expand
        legendContent.classList.remove('collapsed');
        toggleIcon.classList.remove('collapsed');
    } else {
        // Collapse
        legendContent.classList.add('collapsed');
        toggleIcon.classList.add('collapsed');
    }
}

/**
 * Simplify type annotations for compact display
 * @param {string} typeStr - Type annotation (e.g., "Optional[List[int]]")
 * @param {number} maxLength - Maximum length before truncation (default: 40)
 * @returns {string} - Simplified type string
 */
function simplifyType(typeStr, maxLength = 40) {
    if (!typeStr) return 'Any';

    let simplified = typeStr;

    // Abbreviate common types
    const abbreviations = {
        'Optional': 'Opt',
        'List': '[]',
        'Dict': '{}',
        'Tuple': '()',
        'Union': '|',
    };

    // Apply abbreviations
    for (const [full, abbr] of Object.entries(abbreviations)) {
        simplified = simplified.replace(new RegExp(full, 'g'), abbr);
    }

    // Truncate if too long
    if (simplified.length > maxLength) {
        simplified = simplified.substring(0, maxLength - 3) + '...';
    }

    return simplified;
}

/**
 * Get type badge HTML with simplified display and full type tooltip
 * @param {string} type - Type annotation
 * @param {string} badgeClass - CSS class for badge color
 * @returns {string} - HTML string for type badge
 */
function getTypeBadgeHTML(type, badgeClass = 'type-primitive') {
    if (!type) return '';

    const simplified = simplifyType(type, 30);
    const fullType = type;

    // Only add tooltip if type was simplified
    const tooltip = simplified !== fullType ? `title="${fullType}"` : '';

    return `<span class="type-badge ${badgeClass}" ${tooltip}>${simplified}</span>`;
}

/**
 * EPIC-14 Fix: Cleanup function to prevent memory leaks
 * Removes all event listeners and destroys Cytoscape instance
 */
function destroyGraph() {
    if (cy) {
        // Remove all event listeners
        cy.off('tap');
        cy.off('mouseover');
        cy.off('mouseout');
        cy.off('pan');
        cy.off('zoom');

        // Destroy Cytoscape instance
        cy.destroy();
        cy = null;

        console.log('[CodeGraph] Graph destroyed and cleaned up');
    }

    if (minimap) {
        minimap = null;
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
window.toggleLegend = toggleLegend;  // EPIC-14 Story 14.5
window.simplifyType = simplifyType;  // EPIC-14 Story 14.5
window.getTypeBadgeHTML = getTypeBadgeHTML;  // EPIC-14 Story 14.5
window.destroyGraph = destroyGraph;  // EPIC-14 Fix: Cleanup function

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        loadGraph();
    });
} else {
    // DOM already loaded
    loadGraph();
}
