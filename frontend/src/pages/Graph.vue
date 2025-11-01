<script setup lang="ts">
/**
 * EPIC-25 Story 25.5: Code Graph Page
 * Interactive code graph visualization using Cytoscape.js
 */

import { ref, onMounted, nextTick } from 'vue'
import { useCodeGraph } from '@/composables/useCodeGraph'
import cytoscape from 'cytoscape'
import type { Core } from 'cytoscape'

const { stats, graphData, loading, error, building, buildError, fetchStats, fetchGraphData, buildGraph } = useCodeGraph()

const graphContainer = ref<HTMLElement | null>(null)
const cy = ref<Core | null>(null)
const repository = ref('CVGenerator')

// Build graph handler
const handleBuildGraph = async () => {
  await buildGraph(repository.value, 'python')
  // Refresh visualization after build
  await populateGraph()
}

// Initialize Cytoscape graph
const initGraph = async () => {
  if (!graphContainer.value) return

  // Create empty Cytoscape instance
  cy.value = cytoscape({
    container: graphContainer.value,
    style: [
      {
        selector: 'node',
        style: {
          'background-color': '#06b6d4',
          'label': 'data(label)',
          'color': '#e2e8f0',
          'text-valign': 'center',
          'text-halign': 'center',
          'font-size': '10px',
          'width': '40px',
          'height': '40px',
        }
      },
      {
        selector: 'node[type="class"]',
        style: {
          'background-color': '#3b82f6',
          'shape': 'rectangle',
        }
      },
      {
        selector: 'node[type="function"]',
        style: {
          'background-color': '#10b981',
          'shape': 'ellipse',
        }
      },
      {
        selector: 'edge',
        style: {
          'width': 2,
          'line-color': '#475569',
          'target-arrow-color': '#475569',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
        }
      }
    ],
    layout: {
      name: 'grid',
      rows: 5,
    }
  })

  // Add placeholder message if no graph data
  if (stats.value && stats.value.total_nodes === 0) {
    cy.value.add({
      group: 'nodes',
      data: { id: 'placeholder', label: 'No graph data available' }
    })
  }
}

// Populate graph with real data
const populateGraph = async () => {
  if (!cy.value) return

  // Fetch graph data
  await fetchGraphData(repository.value, 500)

  if (!graphData.value) return

  // Clear existing elements
  cy.value.elements().remove()

  // Add nodes
  if (graphData.value.nodes && graphData.value.nodes.length > 0) {
    const nodes = graphData.value.nodes.map(node => ({
      group: 'nodes' as const,
      data: {
        id: node.id,
        label: node.label,
        type: node.type
      }
    }))
    cy.value.add(nodes)
  }

  // Add edges
  if (graphData.value.edges && graphData.value.edges.length > 0) {
    const edges = graphData.value.edges.map(edge => ({
      group: 'edges' as const,
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: edge.type
      }
    }))
    cy.value.add(edges)
  }

  // Run layout if we have nodes
  if (graphData.value.nodes.length > 0) {
    cy.value.layout({
      name: 'cose',
      animate: true,
      animationDuration: 500,
      nodeRepulsion: 8000,
      idealEdgeLength: 100,
      edgeElasticity: 100,
      nestingFactor: 5,
      gravity: 80,
      numIter: 1000,
      initialTemp: 200,
      coolingFactor: 0.95,
      minTemp: 1.0
    }).run()
  }
}

// Fetch stats and initialize graph
onMounted(async () => {
  await fetchStats(repository.value)
  await nextTick()
  initGraph()
  await populateGraph()
})
</script>

<template>
  <div class="min-h-screen bg-slate-950">
    <div class="max-w-full mx-auto px-4 py-6">
      <!-- Header -->
      <div class="mb-6">
        <h1 class="text-3xl text-heading">Code Graph</h1>
        <p class="mt-2 text-sm text-gray-400">
          Visual representation of code dependencies and relationships
        </p>
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="section">
        <div class="animate-pulse">
          <div class="h-4 bg-slate-700 w-1/4 mb-4"></div>
          <div class="h-64 bg-slate-700"></div>
        </div>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="alert-error">
        <div class="flex items-start">
          <svg class="h-5 w-5 text-red-400 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
          </svg>
          <div class="ml-3">
            <h3 class="text-sm font-medium text-red-300 uppercase">Graph Error</h3>
            <p class="mt-1 text-sm text-red-400">{{ error }}</p>
          </div>
        </div>
      </div>

      <!-- Graph Stats + Visualization -->
      <div v-else-if="stats" class="space-y-4">
        <!-- Stats Cards -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <!-- Total Nodes -->
          <div class="section">
            <div class="flex items-center justify-between">
              <div>
                <p class="label">Total Nodes</p>
                <p class="text-3xl font-bold text-cyan-400">{{ stats.total_nodes }}</p>
              </div>
              <svg class="h-10 w-10 text-cyan-500/30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
          </div>

          <!-- Total Edges -->
          <div class="section">
            <div class="flex items-center justify-between">
              <div>
                <p class="label">Total Edges</p>
                <p class="text-3xl font-bold text-emerald-400">{{ stats.total_edges }}</p>
              </div>
              <svg class="h-10 w-10 text-emerald-500/30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
          </div>

          <!-- Classes -->
          <div class="section">
            <div class="flex items-center justify-between">
              <div>
                <p class="label">Classes</p>
                <p class="text-3xl font-bold text-blue-400">{{ stats.nodes_by_type.class || 0 }}</p>
              </div>
              <svg class="h-10 w-10 text-blue-500/30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
          </div>

          <!-- Functions -->
          <div class="section">
            <div class="flex items-center justify-between">
              <div>
                <p class="label">Functions</p>
                <p class="text-3xl font-bold text-purple-400">{{ stats.nodes_by_type.function || 0 }}</p>
              </div>
              <svg class="h-10 w-10 text-purple-500/30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
              </svg>
            </div>
          </div>
        </div>

        <!-- Build Error Banner -->
        <div v-if="buildError" class="alert-error">
          <div class="flex items-start">
            <svg class="h-5 w-5 text-red-400 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
            </svg>
            <div class="ml-3">
              <h3 class="text-sm font-medium text-red-300 uppercase">Build Error</h3>
              <p class="mt-1 text-sm text-red-400">{{ buildError }}</p>
            </div>
          </div>
        </div>

        <!-- Graph Visualization -->
        <div class="section">
          <div class="mb-4 flex items-center justify-between">
            <div>
              <h2 class="text-xl font-semibold text-heading">Graph Visualization</h2>
              <p class="text-sm text-gray-400 mt-1">
                Interactive visualization of code dependencies
              </p>
            </div>
            <button
              @click="handleBuildGraph"
              :disabled="building || loading"
              class="btn-primary"
            >
              <svg v-if="building" class="animate-spin -ml-1 mr-2 h-4 w-4 inline" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              {{ building ? 'Building...' : 'Build Graph' }}
            </button>
          </div>

          <!-- Cytoscape Container -->
          <div
            ref="graphContainer"
            class="w-full h-[600px] bg-slate-900 border border-slate-700 rounded"
            style="min-height: 600px;"
          ></div>

          <!-- Info Message -->
          <div v-if="stats.total_nodes === 0" class="mt-4 p-4 bg-amber-900/20 border border-amber-700/30 rounded">
            <div class="flex items-start">
              <svg class="h-5 w-5 text-amber-400 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
              </svg>
              <div class="ml-3">
                <h3 class="text-sm font-medium text-amber-300">Graph Not Built</h3>
                <p class="mt-1 text-sm text-amber-400/80">
                  The code graph has not been built yet. Click the <strong>"Build Graph"</strong> button above to analyze code dependencies and generate the graph.
                </p>
              </div>
            </div>
          </div>

          <!-- No Edges Warning -->
          <div v-else-if="stats.total_nodes > 0 && stats.total_edges === 0" class="mt-4 p-4 bg-blue-900/20 border border-blue-700/30 rounded">
            <div class="flex items-start">
              <svg class="h-5 w-5 text-blue-400 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
              </svg>
              <div class="ml-3">
                <h3 class="text-sm font-medium text-blue-300">No Dependencies Detected</h3>
                <p class="mt-1 text-sm text-blue-400/80">
                  Graph shows {{ stats.total_nodes }} nodes but no edges. This means no code dependencies (imports/calls) were detected between functions and classes.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
