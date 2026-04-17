import { useState, useRef, useCallback } from 'react'

const API_BASE = import.meta.env.VITE_API_URL !== undefined
  ? import.meta.env.VITE_API_URL
  : 'http://localhost:8000'

/**
 * useAgentStream — SSE streaming hook for agent-powered features.
 *
 * Returns:
 *   messages       — [{role: 'user'|'ai', text, toolCalls?, isStreaming?}]
 *   isStreaming     — whether agent is currently responding
 *   currentToolCall — {tool, description} of the tool being executed right now
 *   sessionId      — persisted session ID for multi-turn
 *   tokenStats     — {input, output, turns} from last response
 *   send(url, body) — POST to agent endpoint, stream SSE
 *   cancel()       — abort the stream
 *   reset()        — new session
 */
export function useAgentStream() {
  const [messages, setMessages] = useState([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [currentToolCall, setCurrentToolCall] = useState(null)
  const [sessionId, setSessionId] = useState(null)
  const [tokenStats, setTokenStats] = useState(null)
  const abortRef = useRef(null)

  const send = useCallback(async (url, body = {}) => {
    if (isStreaming) return

    // Add user message
    const userMsg = { role: 'user', text: body.question || '' }
    setMessages(prev => [...prev, userMsg])
    setIsStreaming(true)
    setCurrentToolCall(null)

    // Prepare request with session
    const requestBody = {
      ...body,
      session_id: sessionId,
    }

    const abortController = new AbortController()
    abortRef.current = abortController

    // Start streaming AI message
    const aiMsgIndex = messages.length + 1 // +1 for the user message we just added
    setMessages(prev => [...prev, { role: 'ai', text: '', isStreaming: true, toolCalls: [] }])

    try {
      const response = await fetch(`${API_BASE}${url}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
        signal: abortController.signal,
        credentials: 'include',
      })

      if (!response.ok) {
        const error = await response.text()
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = {
            role: 'ai',
            text: `Error: ${response.status} — ${error}`,
            isError: true,
          }
          return updated
        })
        setIsStreaming(false)
        return
      }

      // Read session ID from header
      const respSessionId = response.headers.get('X-Session-Id')
      if (respSessionId) {
        setSessionId(respSessionId)
      }

      // Parse SSE stream
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      const toolCalls = []

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Process complete SSE events
        const events = buffer.split('\n\n')
        buffer = events.pop() // Keep incomplete event in buffer

        for (const event of events) {
          if (!event.trim()) continue

          const lines = event.split('\n')
          let eventType = ''
          let eventData = ''

          for (const line of lines) {
            if (line.startsWith('event: ')) eventType = line.slice(7)
            if (line.startsWith('data: ')) eventData = line.slice(6)
          }

          if (!eventType || !eventData) continue

          try {
            const data = JSON.parse(eventData)

            switch (eventType) {
              case 'text':
                setMessages(prev => {
                  const updated = [...prev]
                  const last = updated[updated.length - 1]
                  updated[updated.length - 1] = {
                    ...last,
                    text: (last.text || '') + (data.delta || ''),
                  }
                  return updated
                })
                break

              case 'tool_call':
                setCurrentToolCall({ tool: data.tool, description: data.description })
                toolCalls.push({ tool: data.tool, description: data.description })
                break

              case 'tool_result':
                setCurrentToolCall(null)
                // Update tool calls with result preview
                break

              case 'done':
                setTokenStats({
                  input: data.total_input_tokens,
                  output: data.total_output_tokens,
                  turns: data.turns_used,
                })
                if (data.session_id) setSessionId(data.session_id)
                // Mark message as complete
                setMessages(prev => {
                  const updated = [...prev]
                  const last = updated[updated.length - 1]
                  updated[updated.length - 1] = {
                    ...last,
                    isStreaming: false,
                    toolCalls,
                  }
                  return updated
                })
                break

              case 'error':
                setMessages(prev => {
                  const updated = [...prev]
                  const last = updated[updated.length - 1]
                  updated[updated.length - 1] = {
                    ...last,
                    text: last.text + (last.text ? '\n\n' : '') + `Error: ${data.message}`,
                    isStreaming: false,
                    isError: !last.text, // Only mark as error if no text was received
                  }
                  return updated
                })
                break

              case 'budget_warning':
                // Could show a subtle indicator
                break
            }
          } catch (parseErr) {
            // Ignore malformed events
          }
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        setMessages(prev => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          updated[updated.length - 1] = {
            ...last,
            text: last.text + '\n\n[Cancelled]',
            isStreaming: false,
          }
          return updated
        })
      } else {
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = {
            role: 'ai',
            text: `Connection error: ${err.message}`,
            isError: true,
          }
          return updated
        })
      }
    } finally {
      setIsStreaming(false)
      setCurrentToolCall(null)
      abortRef.current = null
    }
  }, [isStreaming, sessionId, messages.length])

  const cancel = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort()
    }
  }, [])

  const reset = useCallback(() => {
    setMessages([])
    setSessionId(null)
    setTokenStats(null)
    setCurrentToolCall(null)
    setIsStreaming(false)
  }, [])

  return {
    messages,
    isStreaming,
    currentToolCall,
    sessionId,
    tokenStats,
    send,
    cancel,
    reset,
  }
}
