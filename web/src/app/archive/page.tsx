'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { DigitalRain } from '@/components/DigitalRain'
import { SocialLinks } from '@/components/SocialLinks'
import { brand } from '@/config/brand'

// Types
interface ConversationItem {
  id: string
  title: string
  preview: string
  message_count: number
  created_at: string | null
  last_active_at: string | null
}

interface ConversationListResponse {
  items: ConversationItem[]
  page: number
  page_size: number
  total_count: number
  total_pages: number
  has_prev: boolean
  has_next: boolean
}

interface MessageItem {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at: string | null
}

interface ConversationDetailResponse {
  id: string
  title: string
  created_at: string | null
  messages: MessageItem[]
  message_count: number
}

// API base URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || ''

export default function ArchivePage() {
  // List state
  const [conversations, setConversations] = useState<ConversationItem[]>([])
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Detail state
  const [selectedConversation, setSelectedConversation] = useState<ConversationDetailResponse | null>(null)
  const [isLoadingDetail, setIsLoadingDetail] = useState(false)

  // Fetch conversations
  const fetchConversations = useCallback(async (pageNum: number) => {
    setIsLoading(true)
    setError(null)

    try {
      const res = await fetch(`${API_BASE_URL}/api/archive/conversations?page=${pageNum}&page_size=20`)

      if (!res.ok) {
        throw new Error(`Failed to load conversations`)
      }

      const data: ConversationListResponse = await res.json()
      setConversations(data.items)
      setPage(data.page)
      setTotalPages(data.total_pages)
      setTotalCount(data.total_count)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load archive')
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Fetch conversation detail
  const fetchConversationDetail = useCallback(async (id: string) => {
    setIsLoadingDetail(true)

    try {
      const res = await fetch(`${API_BASE_URL}/api/archive/conversations/${id}`)

      if (!res.ok) {
        throw new Error(`Failed to load conversation`)
      }

      const data: ConversationDetailResponse = await res.json()
      setSelectedConversation(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load conversation')
    } finally {
      setIsLoadingDetail(false)
    }
  }, [])

  // Load conversations on mount
  useEffect(() => {
    fetchConversations(1)
  }, [fetchConversations])

  // Format date
  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return ''
    try {
      const date = new Date(dateStr)
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return ''
    }
  }

  // Format relative time
  const formatRelativeTime = (dateStr: string | null) => {
    if (!dateStr) return ''
    try {
      const date = new Date(dateStr)
      const now = new Date()
      const diff = now.getTime() - date.getTime()
      const minutes = Math.floor(diff / 60000)
      const hours = Math.floor(diff / 3600000)
      const days = Math.floor(diff / 86400000)

      if (minutes < 60) return `${minutes}m ago`
      if (hours < 24) return `${hours}h ago`
      if (days < 7) return `${days}d ago`
      return formatDate(dateStr)
    } catch {
      return ''
    }
  }

  // Handle page change
  const goToPage = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages) {
      fetchConversations(newPage)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  // Render pagination
  const renderPagination = () => {
    const pages: (number | string)[] = []
    const maxVisible = 5

    if (totalPages <= maxVisible) {
      for (let i = 1; i <= totalPages; i++) pages.push(i)
    } else {
      if (page <= 3) {
        pages.push(1, 2, 3, 4, '...', totalPages)
      } else if (page >= totalPages - 2) {
        pages.push(1, '...', totalPages - 3, totalPages - 2, totalPages - 1, totalPages)
      } else {
        pages.push(1, '...', page - 1, page, page + 1, '...', totalPages)
      }
    }

    return (
      <div className="flex items-center justify-center gap-2 mt-8">
        <button
          onClick={() => goToPage(page - 1)}
          disabled={page === 1}
          className="px-3 py-2 border border-matrix-green/30 rounded hover:bg-matrix-green/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          Prev
        </button>
        {pages.map((p, i) => (
          <button
            key={i}
            onClick={() => typeof p === 'number' && goToPage(p)}
            disabled={p === '...'}
            className={`w-10 h-10 rounded transition-colors ${
              p === page
                ? 'bg-matrix-green/30 border border-matrix-green text-matrix-green'
                : p === '...'
                ? 'cursor-default'
                : 'border border-matrix-green/30 hover:bg-matrix-green/10'
            }`}
          >
            {p}
          </button>
        ))}
        <button
          onClick={() => goToPage(page + 1)}
          disabled={page === totalPages}
          className="px-3 py-2 border border-matrix-green/30 rounded hover:bg-matrix-green/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          Next
        </button>
      </div>
    )
  }

  // Conversation detail view
  if (selectedConversation) {
    return (
      <main className="min-h-screen relative">
        <DigitalRain />
        <div className="scanline-overlay" />

        {/* Header */}
        <header className="border-b border-matrix-green/30 p-4">
          <div className="max-w-4xl mx-auto flex items-center justify-between">
            <Link href="/" className="text-2xl matrix-text-cyan font-bold tracking-wider hover:opacity-80">
              JEFFREY AISTEIN
            </Link>
            <SocialLinks />
          </div>
        </header>

        {/* Content */}
        <div className="max-w-4xl mx-auto p-4">
          {/* Back button */}
          <button
            onClick={() => setSelectedConversation(null)}
            className="mb-6 text-matrix-cyan hover:underline flex items-center gap-2"
          >
            <span>&larr;</span>
            <span>Back to Archive</span>
          </button>

          {/* Conversation header */}
          <div className="mb-6 p-4 matrix-border rounded-lg">
            <h1 className="text-xl font-bold text-matrix-green mb-2">
              {selectedConversation.title}
            </h1>
            <div className="text-sm text-matrix-green/60">
              {formatDate(selectedConversation.created_at)} &bull; {selectedConversation.message_count} messages
            </div>
          </div>

          {/* Messages */}
          <div className="space-y-4">
            {selectedConversation.messages.map((msg) => (
              <div
                key={msg.id}
                className={`p-4 rounded-lg ${
                  msg.role === 'user'
                    ? 'matrix-border-cyan bg-matrix-cyan/5 ml-8'
                    : 'matrix-border bg-matrix-green/5 mr-8'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className={`text-xs font-bold uppercase tracking-wider ${
                    msg.role === 'user' ? 'text-matrix-cyan' : 'text-matrix-green'
                  }`}>
                    {msg.role === 'user' ? 'VISITOR' : 'AISTEIN'}
                  </span>
                  <span className="text-xs text-matrix-green/40">
                    {formatDate(msg.created_at)}
                  </span>
                </div>
                <p className="text-sm leading-relaxed whitespace-pre-wrap">
                  {msg.content}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <footer className="border-t border-matrix-green/30 p-4 mt-8">
          <div className="max-w-4xl mx-auto text-center">
            <Link href="/" className="text-matrix-cyan hover:underline">
              Chat with AIstein &rarr;
            </Link>
          </div>
        </footer>
      </main>
    )
  }

  // List view
  return (
    <main className="min-h-screen relative">
      <DigitalRain />
      <div className="scanline-overlay" />

      {/* Header */}
      <header className="border-b border-matrix-green/30 p-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <Link href="/" className="text-2xl matrix-text-cyan font-bold tracking-wider hover:opacity-80">
            JEFFREY AISTEIN
          </Link>
          <SocialLinks />
        </div>
      </header>

      {/* Content */}
      <div className="max-w-4xl mx-auto p-4">
        {/* Title */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-matrix-green mb-2">
            CONVERSATION ARCHIVE
          </h1>
          <p className="text-matrix-green/60">
            {totalCount} conversations with visitors
          </p>
        </div>

        {/* Error */}
        {error && (
          <div className="text-center py-8 text-red-400">
            {error}
          </div>
        )}

        {/* Loading */}
        {isLoading ? (
          <div className="text-center py-16">
            <div className="inline-block w-8 h-8 border-2 border-matrix-green/30 border-t-matrix-green rounded-full animate-spin" />
            <p className="mt-4 text-matrix-green/60">Loading archive...</p>
          </div>
        ) : conversations.length === 0 ? (
          <div className="text-center py-16 text-matrix-green/60">
            <p>No conversations yet.</p>
            <Link href="/" className="text-matrix-cyan hover:underline mt-4 inline-block">
              Start a conversation &rarr;
            </Link>
          </div>
        ) : (
          <>
            {/* Conversation list */}
            <div className="space-y-3">
              {conversations.map((conv) => (
                <button
                  key={conv.id}
                  onClick={() => fetchConversationDetail(conv.id)}
                  className="w-full text-left p-4 matrix-border rounded-lg hover:bg-matrix-green/5 transition-colors group"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <h2 className="font-bold text-matrix-green group-hover:text-matrix-cyan transition-colors truncate">
                        {conv.title}
                      </h2>
                      <p className="text-sm text-matrix-green/50 mt-1 line-clamp-2">
                        {conv.preview}
                      </p>
                    </div>
                    <div className="flex-shrink-0 text-right text-xs text-matrix-green/40">
                      <div>{conv.message_count} msgs</div>
                      <div className="mt-1">{formatRelativeTime(conv.last_active_at)}</div>
                    </div>
                  </div>
                </button>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && renderPagination()}

            {/* Loading detail overlay */}
            {isLoadingDetail && (
              <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
                <div className="text-center">
                  <div className="inline-block w-12 h-12 border-2 border-matrix-green/30 border-t-matrix-green rounded-full animate-spin" />
                  <p className="mt-4 text-matrix-green">Loading conversation...</p>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer */}
      <footer className="border-t border-matrix-green/30 p-4 mt-8">
        <div className="max-w-4xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="text-xs opacity-50">
            <p>{brand.name} v{brand.version}</p>
          </div>
          <Link href="/" className="text-matrix-cyan hover:underline text-sm">
            Chat with AIstein &rarr;
          </Link>
        </div>
      </footer>
    </main>
  )
}
