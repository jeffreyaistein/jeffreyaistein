'use client'

import { useState, useRef, useEffect } from 'react'
import { useChat, type ConnectionStatus } from '@/hooks/useChat'
import { DebugPanel } from '@/components/DebugPanel'

// Connection status indicator component
function ConnectionIndicator({
  status,
  error,
  onReconnect,
}: {
  status: ConnectionStatus
  error?: string | null
  onReconnect?: () => void
}) {
  const statusConfig = {
    connecting: { color: 'bg-yellow-500', textColor: 'text-yellow-400', text: 'Connecting...' },
    connected: { color: 'bg-matrix-green', textColor: 'text-matrix-green', text: 'Connected' },
    disconnected: { color: 'bg-gray-500', textColor: 'text-gray-400', text: 'Disconnected' },
    error: { color: 'bg-red-500', textColor: 'text-red-400', text: 'Connection Error' },
  }

  const config = statusConfig[status]
  const isDisconnected = status === 'disconnected' || status === 'error'

  return (
    <div className="flex items-center gap-2 text-xs">
      <div className={`w-2 h-2 rounded-full ${config.color} ${status === 'connecting' ? 'animate-pulse' : ''}`} />
      <span className={config.textColor}>
        {config.text}
        {error && isDisconnected && `: ${error}`}
      </span>
      {isDisconnected && onReconnect && (
        <button
          onClick={onReconnect}
          className="text-matrix-cyan hover:underline ml-2"
        >
          Reconnect
        </button>
      )}
    </div>
  )
}

export function ChatBox() {
  const {
    messages,
    conversationId,
    connectionStatus,
    isTyping,
    error,
    sendMessage,
    retryMessage,
    connect,
  } = useChat({
    onError: (err) => console.error('Chat error:', err),
    onConversationCreated: (id) => console.log('Conversation created:', id),
  })

  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  // Focus input on mount and when connected
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    if (connectionStatus === 'connected') {
      inputRef.current?.focus()
    }
  }, [connectionStatus])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || connectionStatus !== 'connected') return

    sendMessage(input.trim())
    setInput('')
  }

  const handleRetry = (messageId: string) => {
    retryMessage(messageId)
  }

  const handleReconnect = () => {
    connect()
  }

  // Show welcome message if no messages
  const displayMessages = messages.length > 0 ? messages : [
    {
      id: 'welcome',
      role: 'assistant' as const,
      content: 'Greetings. I am Jeffrey AIstein. My neural pathways are initializing... How may I assist you today?',
      status: 'done' as const,
    },
  ]

  return (
    <div className="flex flex-col h-[400px]">
      {/* Debug panel - only shows when NEXT_PUBLIC_DEBUG=true */}
      <DebugPanel connectionStatus={connectionStatus} lastError={error} />

      {/* Error banner */}
      {error && (
        <div className="px-4 py-2 bg-red-900/50 border-b border-red-500/50 text-red-300 text-sm flex justify-between items-center">
          <span>{error}</span>
          <button
            onClick={handleReconnect}
            className="text-xs underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {displayMessages.map(message => (
          <div
            key={message.id}
            className={`chat-message p-3 rounded ${
              message.role === 'user'
                ? 'chat-message-user ml-8'
                : 'chat-message-assistant mr-8'
            }`}
          >
            <div className="flex items-start gap-2">
              <span className={`text-xs font-bold uppercase ${
                message.role === 'user' ? 'text-matrix-cyan' : 'text-matrix-green'
              }`}>
                {message.role === 'user' ? 'YOU' : 'AISTEIN'}
              </span>
              {message.status === 'sending' && (
                <span className="text-xs text-yellow-500 animate-pulse">sending...</span>
              )}
            </div>
            <p className="mt-1 text-sm leading-relaxed whitespace-pre-wrap">
              {message.content}
              {message.status === 'streaming' && (
                <span className="inline-block w-2 h-4 ml-1 bg-matrix-green animate-pulse" />
              )}
            </p>
            {message.status === 'error' && (
              <button
                onClick={() => handleRetry(message.id)}
                className="mt-2 text-xs text-red-400 hover:underline"
              >
                Retry
              </button>
            )}
          </div>
        ))}

        {isTyping && !messages.some(m => m.status === 'streaming') && (
          <div className="chat-message chat-message-assistant mr-8 p-3 rounded">
            <span className="text-xs font-bold uppercase text-matrix-green">AISTEIN</span>
            <div className="typing-indicator mt-1">
              <span className="text-matrix-green">.</span>
              <span className="text-matrix-green">.</span>
              <span className="text-matrix-green">.</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-matrix-green/30">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Enter message..."
            className="matrix-input flex-1"
            disabled={isTyping}
          />
          <button
            type="submit"
            disabled={!input.trim() || connectionStatus !== 'connected' || isTyping}
            className="matrix-button px-6"
            title={connectionStatus !== 'connected' ? 'Cannot send while disconnected' : undefined}
          >
            SEND
          </button>
        </div>
        <div className="mt-2 flex items-center justify-between">
          <ConnectionIndicator
            status={connectionStatus}
            error={error}
            onReconnect={handleReconnect}
          />
          {conversationId && (
            <span className="text-xs opacity-30 font-mono">
              {conversationId.slice(0, 8)}...
            </span>
          )}
        </div>
      </form>
    </div>
  )
}
