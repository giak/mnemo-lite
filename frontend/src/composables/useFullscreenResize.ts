import { ref, onMounted, onUnmounted, nextTick, type Ref } from 'vue'

/**
 * Composable for automatic canvas resizing in normal and fullscreen modes
 *
 * Handles:
 * - ResizeObserver for container size changes
 * - Fullscreen event listener
 * - Automatic size calculation (viewport-based when needed)
 * - Cleanup on unmount
 *
 * @param containerRef - Reference to the container element
 * @param onResize - Callback function to resize the graph/canvas with new dimensions
 * @returns Object with resize function
 */
export function useFullscreenResize(
  containerRef: Ref<HTMLElement | null | undefined>,
  onResize: (width: number, height: number) => void
) {
  let resizeObserver: ResizeObserver | null = null
  let rafId: number | null = null

  /**
   * Calculate optimal canvas dimensions from container's actual size
   * No hardcoded values - uses actual DOM dimensions
   */
  const calculateSize = () => {
    if (!containerRef.value) return null

    let width = containerRef.value.offsetWidth
    let height = containerRef.value.offsetHeight

    // Fallback to window dimensions if container not yet sized
    // This happens during initial render before layout is complete
    if (width === 0 || height === 0) {
      width = window.innerWidth - 32  // Account for some padding
      height = window.innerHeight - 200  // Account for navbar + toolbar
      console.log('[useFullscreenResize] Container not sized yet, using fallback:', { width, height })
    }

    return { width, height }
  }

  /**
   * Resize graph/canvas to fill available space
   * Throttled via requestAnimationFrame (max 60fps)
   */
  const resizeGraph = () => {
    // Cancel any pending resize
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
    }

    // Schedule resize for next animation frame
    rafId = requestAnimationFrame(() => {
      rafId = null

      const size = calculateSize()
      if (!size) return

      console.log('[useFullscreenResize] Resizing to:', {
        width: size.width,
        height: size.height,
        isFullscreen: !!document.fullscreenElement
      })

      onResize(size.width, size.height)
    })
  }

  /**
   * Handle fullscreen change events (enter/exit)
   */
  const handleFullscreenChange = () => {
    console.log('[useFullscreenResize] Fullscreen changed:', !!document.fullscreenElement)
    // Use requestAnimationFrame instead of setTimeout for reliable timing
    resizeGraph()
  }

  /**
   * Setup resize observers and listeners
   */
  const setup = async () => {
    await nextTick()

    // Watch for container size changes and resize graph
    // ResizeObserver + requestAnimationFrame = throttled, performant resize
    if (containerRef.value) {
      resizeObserver = new ResizeObserver(() => {
        resizeGraph()
      })
      resizeObserver.observe(containerRef.value)
    }

    // Listen for fullscreen changes
    document.addEventListener('fullscreenchange', handleFullscreenChange)
  }

  /**
   * Cleanup observers and listeners
   */
  const cleanup = () => {
    // Cancel any pending resize animation frame
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }

    // Remove fullscreen listener
    document.removeEventListener('fullscreenchange', handleFullscreenChange)

    // Disconnect resize observer
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
  }

  // Auto-setup on mount and cleanup on unmount
  onMounted(setup)
  onUnmounted(cleanup)

  return {
    resizeGraph,
    calculateSize
  }
}
