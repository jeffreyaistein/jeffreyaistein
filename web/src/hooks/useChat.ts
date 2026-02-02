'use client'

import { useState, useRef, useCallback, useEffect } from 'react'

// Types
export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  status: 'sending' | 'streaming' | 'done' | 'error'
  createdAt?: Date
}

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

interface ChatState {
  messages: Message[]
  conversationId: string | null
  connectionStatus: ConnectionStatus
  isTyping: boolean
  error: string | null
}

interface UseChatOptions {
  conversationId?: string | null
  onError?: (error: string) => void
  onConversationCreated?: (conversationId: string) => void
}

// API URLs from environment
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'

// Initialize session with the API
async function initializeSession(): Promise<boolean> {
  try {
    const response = await fetch(`${API_URL}/api/session`, {
      method: 'POST',
      credentials: 'include',
    })
    return response.ok
  } catch (error) {
    console.error('Failed to initialize session:', error)
    return false
  }
}

export function useChat(options: UseChatOptions = {}) {
  const { conversationId: initialConversationId, onError, onConversationCreated } = options

  const [state, setState] = useState<ChatState>({
    messages: [],
    conversationId: initialConversationId || null,
    connectionStatus: 'disconnected',
    isTyping: false,
    error: null,
  })

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 5

  // Helper to update state
  const updateState = useCallback((updates: Partial<ChatState>) => {
    setState(prev => ({ ...prev, ...updates }))
  }, [])

  // Add message to state
  const addMessage = useCallback((message: Message) => {
    setState(prev => ({
      ...prev,
      messages: [...prev.messages, message],
    }))
  }, [])

  // Update message in state
  const updateMessage = useCallback((id: string, updates: Partial<Message>) => {
    setState(prev => ({
      ...prev,
      messages: prev.messages.map(msg =>
        msg.id === id ? { ...msg, ...updates } : msg
      ),
    }))
  }, [])

  // Append content to a streaming message
  const appendToMessage = useCallback((id: string, delta: string) => {
    setState(prev => ({
      ...prev,
      messages: prev.messages.map(msg =>
        msg.id === id ? { ...msg, content: msg.content + delta } : msg
      ),
    }))
  }, [])

  // Connect to WebSocket
  const connect = useCallback(async () => {
    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    updateState({ connectionStatus: 'connecting', error: null })

    // Initialize session first
    const sessionOk = await initializeSession()
    if (!sessionOk) {
      updateState({
        connectionStatus: 'error',
        error: 'Failed to initialize session',
      })
      onError?.('Failed to initialize session')
      return
    }

    // Build WebSocket URL
    const wsUrl = state.conversationId
      ? `${WS_URL}/ws/chat?conversation_id=${state.conversationId}`
      : `${WS_URL}/ws/chat`

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('WebSocket connected')
        reconnectAttempts.current = 0
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          handleWebSocketMessage(data)
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        updateState({ error: 'Connection error' })
      }

      ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason)
        updateState({ connectionStatus: 'disconnected' })

        // Attempt reconnection if not a clean close
        if (event.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000)
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttempts.current++
            connect()
          }, delay)
        }
      }
    } catch (error) {
      console.error('Failed to create WebSocket:', error)
      updateState({
        connectionStatus: 'error',
        error: 'Failed to connect',
      })
    }
  }, [state.conversationId, updateState, onError])

  // Handle WebSocket messages
  const handleWebSocketMessage = useCallback((data: Record<string, unknown>) => {
    switch (data.type) {
      case 'ready':
        updateState({
          connectionStatus: 'connected',
          conversationId: data.conversation_id as string,
        })
        break

      case 'conversation_created':
        updateState({ conversationId: data.conversation_id as string })
        onConversationCreated?.(data.conversation_id as string)
        break

      case 'message_saved':
        // User message was saved successfully
        if (data.role === 'user') {
          updateMessage(data.message_id as string, { status: 'done' })
        }
        break

      case 'message_start':
        // Assistant is starting to respond
        updateState({ isTyping: true })
        addMessage({
          id: data.message_id as string,
          role: 'assistant',
          content: '',
          status: 'streaming',
          createdAt: new Date(),
        })
        break

      case 'content_delta':
        // Streaming content chunk
        appendToMessage(data.message_id as string, data.delta as string)
        break

      case 'message_end':
        // Assistant finished responding
        updateMessage(data.message_id as string, {
          content: data.content as string,
          status: 'done',
        })
        updateState({ isTyping: false })
        break

      case 'error':
        console.error('Server error:', data.message)
        updateState({
          error: data.message as string,
          isTyping: false,
        })
        onError?.(data.message as string)
        break

      case 'pong':
        // Heartbeat response
        break

      default:
        console.log('Unknown message type:', data.type)
    }
  }, [updateState, updateMessage, addMessage, appendToMessage, onConversationCreated, onError])

  // Send message
  const sendMessage = useCallback((content: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      updateState({ error: 'Not connected' })
      return
    }

    const messageId = `user-${Date.now()}`

    // Add optimistic message
    addMessage({
      id: messageId,
      role: 'user',
      content,
      status: 'sending',
      createdAt: new Date(),
    })

    // Send via WebSocket
    wsRef.current.send(JSON.stringify({
      type: 'message',
      content,
    }))
  }, [addMessage, updateState])

  // Retry failed message
  const retryMessage = useCallback((messageId: string) => {
    const message = state.messages.find(m => m.id === messageId)
    if (message && message.status === 'error') {
      // Remove the failed message
      setState(prev => ({
        ...prev,
        messages: prev.messages.filter(m => m.id !== messageId),
      }))
      // Resend
      sendMessage(message.content)
    }
  }, [state.messages, sendMessage])

  // Disconnect
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close(1000, 'User disconnect')
      wsRef.current = null
    }
    updateState({ connectionStatus: 'disconnected' })
  }, [updateState])

  // Set conversation ID
  const setConversationId = useCallback((id: string | null) => {
    updateState({ conversationId: id })
    // Reconnect with new conversation
    if (wsRef.current) {
      disconnect()
      setTimeout(connect, 100)
    }
  }, [updateState, disconnect, connect])

  // Clear messages
  const clearMessages = useCallback(() => {
    setState(prev => ({ ...prev, messages: [] }))
  }, [])

  // Auto-connect on mount
  useEffect(() => {
    connect()
    return () => {
      disconnect()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Heartbeat to keep connection alive
  useEffect(() => {
    const interval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000)
    return () => clearInterval(interval)
  }, [])

  return {
    messages: state.messages,
    conversationId: state.conversationId,
    connectionStatus: state.connectionStatus,
    isTyping: state.isTyping,
    error: state.error,
    sendMessage,
    retryMessage,
    connect,
    disconnect,
    setConversationId,
    clearMessages,
  }
}
