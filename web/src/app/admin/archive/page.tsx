'use client'

import { useState, useEffect, useCallback } from 'react'

// Types
interface ConversationItem {
  id: string
  title: string | null
  created_at: string | null
  last_active_at: string | null
  message_count: number
  snippet: string
}

interface ConversationListResponse {
  items: ConversationItem[]
  page: number
  page_size: number
  total_count: number
  has_next: boolean
}

interface MessageItem {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at: string | null
  metadata: Record<string, unknown>
}

interface ConversationDetailResponse {
  conversation: {
    id: string
    title: string | null
    created_at: string | null
    last_active_at: string | null
  }
  items: MessageItem[]
  page: number
  page_size: number
  total_count: number
  has_next: boolean
}

// API base URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || ''

// LocalStorage key for admin key
const ADMIN_KEY_STORAGE = 'aistein_admin_key'

export default function AdminArchivePage() {
  // Admin key state
  const [adminKey, setAdminKey] = useState('')
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)

  // Conversation list state
  const [conversations, setConversations] = useState<ConversationItem[]>([])
  const [page, setPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const [hasNext, setHasNext] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [listError, setListError] = useState<string | null>(null)

  // Conversation detail state
  const [selectedConversation, setSelectedConversation] = useState<string | null>(null)
  const [messages, setMessages] = useState<MessageItem[]>([])
  const [conversationMeta, setConversationMeta] = useState<ConversationDetailResponse['conversation'] | null>(null)
  const [messagesPage, setMessagesPage] = useState(1)
  const [messagesTotalCount, setMessagesTotalCount] = useState(0)
  const [messagesHasNext, setMessagesHasNext] = useState(false)
  const [isLoadingMessages, setIsLoadingMessages] = useState(false)
  const [messagesError, setMessagesError] = useState<string | null>(null)

  const PAGE_SIZE = 50

  // Load admin key from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem(ADMIN_KEY_STORAGE)
    if (saved) {
      setAdminKey(saved)
    }
  }, [])

  // Fetch conversations
  const fetchConversations = useCallback(async (pageNum: number, search?: string) => {
    if (!adminKey) return

    setIsLoading(true)
    setListError(null)

    try {
      const params = new URLSearchParams({
        page: pageNum.toString(),
        page_size: PAGE_SIZE.toString(),
      })
      if (search) {
        params.set('q', search)
      }

      const res = await fetch(`${API_BASE_URL}/api/admin/conversations?${params}`, {
        headers: {
          'X-Admin-Key': adminKey,
        },
      })

      if (res.status === 401) {
        setAuthError('Invalid admin key')
        setIsAuthenticated(false)
        return
      }

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      }

      const data: ConversationListResponse = await res.json()
      setConversations(data.items)
      setPage(data.page)
      setTotalCount(data.total_count)
      setHasNext(data.has_next)
      setIsAuthenticated(true)
      setAuthError(null)
    } catch (err) {
      setListError(err instanceof Error ? err.message : 'Failed to fetch conversations')
    } finally {
      setIsLoading(false)
    }
  }, [adminKey])

  // Fetch messages for a conversation
  const fetchMessages = useCallback(async (conversationId: string, pageNum: number) => {
    if (!adminKey) return

    setIsLoadingMessages(true)
    setMessagesError(null)

    try {
      const params = new URLSearchParams({
        page: pageNum.toString(),
        page_size: '100',
        order: 'asc',
      })

      const res = await fetch(`${API_BASE_URL}/api/admin/conversations/${conversationId}/messages?${params}`, {
        headers: {
          'X-Admin-Key': adminKey,
        },
      })

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      }

      const data: ConversationDetailResponse = await res.json()
      setMessages(pageNum === 1 ? data.items : [...messages, ...data.items])
      setConversationMeta(data.conversation)
      setMessagesPage(data.page)
      setMessagesTotalCount(data.total_count)
      setMessagesHasNext(data.has_next)
    } catch (err) {
      setMessagesError(err instanceof Error ? err.message : 'Failed to fetch messages')
    } finally {
      setIsLoadingMessages(false)
    }
  }, [adminKey, messages])

  // Handle login
  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault()
    if (!adminKey.trim()) return
    localStorage.setItem(ADMIN_KEY_STORAGE, adminKey)
    fetchConversations(1, searchQuery)
  }

  // Handle logout
  const handleLogout = () => {
    localStorage.removeItem(ADMIN_KEY_STORAGE)
    setAdminKey('')
    setIsAuthenticated(false)
    setConversations([])
    setSelectedConversation(null)
    setMessages([])
  }

  // Handle search
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    fetchConversations(1, searchQuery)
  }

  // Handle conversation click
  const handleConversationClick = (conversationId: string) => {
    setSelectedConversation(conversationId)
    setMessages([])
    setMessagesPage(1)
    fetchMessages(conversationId, 1)
  }

  // Handle back to list
  const handleBackToList = () => {
    setSelectedConversation(null)
    setMessages([])
    setConversationMeta(null)
  }

  // Format date
  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'N/A'
    try {
      return new Date(dateStr).toLocaleString()
    } catch {
      return dateStr
    }
  }

  // Login form
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-black text-matrix-green p-8 font-mono">
        <div className="max-w-md mx-auto">
          <h1 className="text-2xl font-bold mb-8 text-center">
            CONVERSATION ARCHIVE
          </h1>
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm mb-2 text-matrix-green/70">
                Admin Key
              </label>
              <input
                type="password"
                value={adminKey}
                onChange={(e) => setAdminKey(e.target.value)}
                className="w-full bg-black border border-matrix-green/50 rounded px-4 py-2 text-matrix-green focus:outline-none focus:border-matrix-green"
                placeholder="Enter admin key..."
                autoComplete="off"
              />
            </div>
            {authError && (
              <div className="text-red-500 text-sm">{authError}</div>
            )}
            <button
              type="submit"
              disabled={!adminKey.trim()}
              className="w-full bg-matrix-green/20 border border-matrix-green rounded px-4 py-2 text-matrix-green hover:bg-matrix-green/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading ? 'AUTHENTICATING...' : 'ACCESS ARCHIVE'}
            </button>
          </form>
        </div>
      </div>
    )
  }

  // Conversation detail view
  if (selectedConversation) {
    return (
      <div className="min-h-screen bg-black text-matrix-green p-4 md:p-8 font-mono">
        <div className="max-w-4xl mx-auto">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <button
              onClick={handleBackToList}
              className="text-matrix-cyan hover:underline"
            >
              &larr; Back to list
            </button>
            <button
              onClick={handleLogout}
              className="text-red-400 hover:underline text-sm"
            >
              Logout
            </button>
          </div>

          {/* Conversation meta */}
          {conversationMeta && (
            <div className="mb-6 p-4 border border-matrix-green/30 rounded">
              <h2 className="text-lg font-bold mb-2">
                {conversationMeta.title || 'Untitled Conversation'}
              </h2>
              <div className="text-sm text-matrix-green/70 space-y-1">
                <div>ID: {conversationMeta.id}</div>
                <div>Created: {formatDate(conversationMeta.created_at)}</div>
                <div>Last Active: {formatDate(conversationMeta.last_active_at)}</div>
                <div>Messages: {messagesTotalCount}</div>
              </div>
            </div>
          )}

          {/* Messages */}
          {messagesError && (
            <div className="text-red-500 mb-4">{messagesError}</div>
          )}

          <div className="space-y-4">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`p-4 rounded border ${
                  msg.role === 'user'
                    ? 'border-matrix-cyan/50 bg-matrix-cyan/5 ml-8'
                    : 'border-matrix-green/50 bg-matrix-green/5 mr-8'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className={`text-xs font-bold uppercase ${
                    msg.role === 'user' ? 'text-matrix-cyan' : 'text-matrix-green'
                  }`}>
                    {msg.role === 'user' ? 'USER' : 'AISTEIN'}
                  </span>
                  <span className="text-xs text-matrix-green/50">
                    {formatDate(msg.created_at)}
                  </span>
                </div>
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              </div>
            ))}
          </div>

          {/* Load more messages */}
          {messagesHasNext && (
            <div className="mt-6 text-center">
              <button
                onClick={() => fetchMessages(selectedConversation, messagesPage + 1)}
                disabled={isLoadingMessages}
                className="px-4 py-2 border border-matrix-green/50 rounded hover:bg-matrix-green/10 disabled:opacity-50"
              >
                {isLoadingMessages ? 'Loading...' : 'Load More Messages'}
              </button>
            </div>
          )}

          {isLoadingMessages && messages.length === 0 && (
            <div className="text-center py-8 text-matrix-green/50">
              Loading messages...
            </div>
          )}
        </div>
      </div>
    )
  }

  // Conversation list view
  return (
    <div className="min-h-screen bg-black text-matrix-green p-4 md:p-8 font-mono">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl md:text-2xl font-bold">
            CONVERSATION ARCHIVE
          </h1>
          <button
            onClick={handleLogout}
            className="text-red-400 hover:underline text-sm"
          >
            Logout
          </button>
        </div>

        {/* Search */}
        <form onSubmit={handleSearch} className="mb-6 flex gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1 bg-black border border-matrix-green/50 rounded px-4 py-2 text-matrix-green focus:outline-none focus:border-matrix-green"
            placeholder="Search conversations..."
          />
          <button
            type="submit"
            className="px-4 py-2 bg-matrix-green/20 border border-matrix-green rounded hover:bg-matrix-green/30 transition-colors"
          >
            Search
          </button>
        </form>

        {/* Stats */}
        <div className="mb-4 text-sm text-matrix-green/70">
          Total: {totalCount} conversations | Page {page} | Showing {conversations.length}
        </div>

        {/* Error */}
        {listError && (
          <div className="text-red-500 mb-4">{listError}</div>
        )}

        {/* Conversation list */}
        {isLoading ? (
          <div className="text-center py-8 text-matrix-green/50">
            Loading conversations...
          </div>
        ) : conversations.length === 0 ? (
          <div className="text-center py-8 text-matrix-green/50">
            No conversations found
          </div>
        ) : (
          <div className="space-y-2">
            {conversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => handleConversationClick(conv.id)}
                className="w-full text-left p-4 border border-matrix-green/30 rounded hover:border-matrix-green/60 hover:bg-matrix-green/5 transition-colors"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="font-bold truncate">
                      {conv.title || 'Untitled'}
                    </div>
                    <div className="text-sm text-matrix-green/50 truncate mt-1">
                      {conv.snippet || 'No messages'}
                    </div>
                  </div>
                  <div className="text-right text-xs text-matrix-green/50 flex-shrink-0">
                    <div>{conv.message_count} msgs</div>
                    <div className="mt-1">
                      {formatDate(conv.last_active_at)}
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}

        {/* Pagination */}
        <div className="mt-6 flex items-center justify-center gap-4">
          <button
            onClick={() => fetchConversations(page - 1, searchQuery)}
            disabled={page <= 1 || isLoading}
            className="px-4 py-2 border border-matrix-green/50 rounded hover:bg-matrix-green/10 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <span className="text-sm">Page {page}</span>
          <button
            onClick={() => fetchConversations(page + 1, searchQuery)}
            disabled={!hasNext || isLoading}
            className="px-4 py-2 border border-matrix-green/50 rounded hover:bg-matrix-green/10 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  )
}
