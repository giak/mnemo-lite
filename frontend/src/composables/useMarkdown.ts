/**
 * Markdown Rendering Composable
 * Renders Markdown content with code highlighting using marked + highlight.js
 */

import { computed, type Ref } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js/lib/core'

// Register commonly used languages
import python from 'highlight.js/lib/languages/python'
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import bash from 'highlight.js/lib/languages/bash'
import sql from 'highlight.js/lib/languages/sql'
import json from 'highlight.js/lib/languages/json'
import css from 'highlight.js/lib/languages/css'
import xml from 'highlight.js/lib/languages/xml'

hljs.registerLanguage('python', python)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('json', json)
hljs.registerLanguage('css', css)
hljs.registerLanguage('html', xml)

// Configure marked with highlight.js
marked.setOptions({
  breaks: true,
  gfm: true,
  highlight: (code: string, lang: string) => {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(code, { language: lang }).value
      } catch {
        // fall through
      }
    }
    // Auto-detect language
    try {
      return hljs.highlightAuto(code).value
    } catch {
      return code
    }
  }
})

/**
 * Render Markdown content to HTML with code highlighting
 */
export function useMarkdown(content: Ref<string> | string) {
  const renderedContent = computed(() => {
    const text = typeof content === 'string' ? content : content.value
    if (!text) return ''
    try {
      return marked.parse(text) as string
    } catch {
      return text
    }
  })

  return { renderedContent }
}
