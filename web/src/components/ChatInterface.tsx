'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { useChat, type ConnectionStatus } from '@/hooks/useChat'
import { useAvatarDriver } from '@/hooks/useAvatarDriver'
import { useTTS } from '@/hooks/useTTS'
import { HologramAvatar, getAvatarMode } from '@/components/HologramAvatar'
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

// Hologram wrapper with state-aware rendering
function HologramSection({
  connectionStatus,
  isTyping,
  isSpeaking,
  ttsAmplitude,
}: {
  connectionStatus: ConnectionStatus
  isTyping: boolean
  isSpeaking: boolean
  ttsAmplitude: number
}) {
  const avatarDriver = useAvatarDriver({
    connectionStatus,
    isTyping,
    isSpeaking,
  })

  // Use TTS amplitude when speaking, otherwise use avatar driver's amplitude
  const displayAmplitude = isSpeaking ? ttsAmplitude : avatarDriver.amplitude

  return (
    <div className="matrix-border-cyan rounded-lg overflow-hidden">
      <div className="p-2 border-b border-matrix-cyan/30 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-matrix-cyan animate-pulse" />
          <span className="text-xs text-matrix-cyan uppercase tracking-wider">
            Holographic Interface
          </span>
        </div>
        <span className="text-[10px] text-matrix-cyan/50 uppercase">
          {getAvatarMode().toUpperCase()} | {avatarDriver.state}
        </span>
      </div>
      <div className="h-[300px]">
        <HologramAvatar
          state={avatarDriver.state}
          amplitude={displayAmplitude}
        />
      </div>
    </div>
  )
}

// Voice toggle button component
function VoiceToggle({
  enabled,
  onToggle,
  isLoading,
}: {
  enabled: boolean
  onToggle: () => void
  isLoading: boolean
}) {
  return (
    <button
      onClick={onToggle}
      disabled={isLoading}
      className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs transition-colors ${
        enabled
          ? 'bg-matrix-cyan/20 text-matrix-cyan border border-matrix-cyan/50'
          : 'bg-gray-800/50 text-gray-400 border border-gray-600/50 hover:border-gray-500'
      } ${isLoading ? 'opacity-50 cursor-wait' : ''}`}
      title={enabled ? 'Voice enabled - click to disable' : 'Click to enable voice'}
    >
      {/* Speaker icon */}
      <svg
        className="w-3.5 h-3.5"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        {enabled ? (
          <>
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15.536 8.464a5 5 0 010 7.072M18.364 5.636a9 9 0 010 12.728M11 5L6 9H2v6h4l5 4V5z"
            />
          </>
        ) : (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"
          />
        )}
      </svg>
      <span className="uppercase tracking-wide">
        {isLoading ? 'Loading...' : enabled ? 'Voice On' : 'Voice Off'}
      </span>
    </button>
  )
}

// Chat messages section
function ChatSection({
  messages,
  conversationId,
  connectionStatus,
  isTyping,
  error,
  onSendMessage,
  onRetryMessage,
  onReconnect,
  voiceEnabled,
  voiceLoading,
  onVoiceToggle,
  ttsError,
  ttsDebugInfo,
}: {
  messages: Array<{
    id: string
    role: 'user' | 'assistant' | 'system'
    content: string
    status: 'sending' | 'streaming' | 'done' | 'error'
  }>
  conversationId: string | null
  connectionStatus: ConnectionStatus
  isTyping: boolean
  error: string | null
  onSendMessage: (content: string) => void
  onRetryMessage: (id: string) => void
  onReconnect: () => void
  voiceEnabled: boolean
  voiceLoading: boolean
  onVoiceToggle: () => void
  ttsError: string | null
  ttsDebugInfo?: {
    voiceEnabled: boolean
    audioContextState: AudioContextState | 'unavailable'
    lastHttpStatus: number | null
    lastBytes: number | null
    lastPlayError: string | null
    lastAudioEnded: boolean
    amplitude: number
  }
}) {
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || connectionStatus !== 'connected') return

    onSendMessage(input.trim())
    setInput('')
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
    <div className="matrix-border rounded-lg overflow-hidden">
      <div className="p-2 border-b border-matrix-green/30 flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-matrix-green animate-pulse" />
        <span className="text-xs text-matrix-green uppercase tracking-wider">
          Neural Link Active
        </span>
      </div>

      <div className="flex flex-col h-[400px]">
        {/* Debug panel - only shows when NEXT_PUBLIC_DEBUG=true */}
        <DebugPanel connectionStatus={connectionStatus} lastError={error} ttsDebugInfo={ttsDebugInfo} />

        {/* Error banner */}
        {error && (
          <div className="px-4 py-2 bg-red-900/50 border-b border-red-500/50 text-red-300 text-sm flex justify-between items-center">
            <span>{error}</span>
            <button
              onClick={onReconnect}
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
                  onClick={() => onRetryMessage(message.id)}
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
            <div className="flex items-center gap-3">
              <ConnectionIndicator
                status={connectionStatus}
                error={error}
                onReconnect={onReconnect}
              />
              <VoiceToggle
                enabled={voiceEnabled}
                onToggle={onVoiceToggle}
                isLoading={voiceLoading}
              />
            </div>
            <div className="flex items-center gap-2">
              {ttsError && (
                <span className="text-xs text-red-400" title={ttsError}>
                  TTS Error
                </span>
              )}
              {conversationId && (
                <span className="text-xs opacity-30 font-mono">
                  {conversationId.slice(0, 8)}...
                </span>
              )}
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}

/**
 * Combined chat interface with hologram integration.
 * This component manages the shared state between chat and avatar.
 */
export function ChatInterface() {
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

  // TTS hook for real voice synthesis
  const {
    voiceEnabled,
    toggleVoice,
    isSpeaking,
    isLoading: ttsLoading,
    error: ttsError,
    amplitude: ttsAmplitude,
    debugInfo: ttsDebugInfo,
    speak,
  } = useTTS({
    onError: (err) => console.error('TTS error:', err),
  })

  // Track when assistant message completes to trigger TTS
  const lastMessageRef = useRef<string | null>(null)

  useEffect(() => {
    // When a new assistant message finishes streaming, speak it
    const lastMessage = messages[messages.length - 1]
    if (
      lastMessage &&
      lastMessage.role === 'assistant' &&
      lastMessage.status === 'done' &&
      lastMessage.id !== lastMessageRef.current
    ) {
      lastMessageRef.current = lastMessage.id
      // Speak the message (respects voiceEnabled internally)
      speak(lastMessage.content)
    }
  }, [messages, speak])

  const handleReconnect = useCallback(() => {
    connect()
  }, [connect])

  return (
    <div className="space-y-6">
      {/* Hologram Avatar */}
      <HologramSection
        connectionStatus={connectionStatus}
        isTyping={isTyping}
        isSpeaking={isSpeaking}
        ttsAmplitude={ttsAmplitude}
      />

      {/* Chat Interface */}
      <ChatSection
        messages={messages}
        conversationId={conversationId}
        connectionStatus={connectionStatus}
        isTyping={isTyping}
        error={error}
        onSendMessage={sendMessage}
        onRetryMessage={retryMessage}
        onReconnect={handleReconnect}
        voiceEnabled={voiceEnabled}
        voiceLoading={ttsLoading}
        onVoiceToggle={toggleVoice}
        ttsError={ttsError}
        ttsDebugInfo={ttsDebugInfo}
      />
    </div>
  )
}
