'use client'

import { useState, useEffect } from 'react'

interface AgentStats {
  state: 'indexing' | 'live'
  messages_processed: number
  messages_replied: number
  total_conversations: number
  channel_breakdown: {
    web: number
    x: number
  }
  learning_score: number
  updated_at: string | null
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || ''

export function StatsPanel() {
  const [stats, setStats] = useState<AgentStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Fetch agent stats from backend
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/stats/agent`)
        if (!response.ok) throw new Error('Failed to fetch stats')
        const data = await response.json()
        setStats(data)
        setError(null)
      } catch (err) {
        console.error('Agent stats error:', err)
        setError('Failed to load')
      } finally {
        setIsLoading(false)
      }
    }

    fetchStats()
    // Refresh every 30 seconds
    const interval = setInterval(fetchStats, 30000)
    return () => clearInterval(interval)
  }, [])

  // Format timestamp
  const formatTime = (isoString: string | null) => {
    if (!isoString) return 'Never'
    const date = new Date(isoString)
    return date.toLocaleString()
  }

  const isLive = stats?.state === 'live'

  return (
    <div className="stats-panel matrix-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold uppercase tracking-wider text-matrix-green">
          AGI Bot Stats
        </h3>
        <div className="flex items-center gap-1 text-xs opacity-70">
          {isLoading ? (
            <>
              <div className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" />
              <span>LOADING</span>
            </>
          ) : error ? (
            <>
              <div className="w-2 h-2 rounded-full bg-red-500" />
              <span>ERROR</span>
            </>
          ) : (
            <>
              <div className="w-2 h-2 rounded-full bg-matrix-green" />
              <span>LIVE</span>
            </>
          )}
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="text-center py-6">
          <p className="text-xs text-red-400">{error}</p>
        </div>
      )}

      {/* Live data */}
      {stats && !error && (
        <>
          {/* Stats grid */}
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-xs opacity-70">MESSAGES IN</span>
              <span className="text-matrix-green font-mono">
                {stats.messages_processed.toLocaleString()}
              </span>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-xs opacity-70">MESSAGES OUT</span>
              <span className="text-matrix-green font-mono">
                {stats.messages_replied.toLocaleString()}
              </span>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-xs opacity-70">CONVERSATIONS</span>
              <span className="text-matrix-cyan font-mono">
                {stats.total_conversations.toLocaleString()}
              </span>
            </div>
          </div>

          {/* Channel breakdown */}
          <div className="mt-4 pt-4 border-t border-matrix-green/30">
            <div className="text-xs opacity-70 mb-2">CHANNEL BREAKDOWN</div>
            <div className="flex gap-4 text-xs">
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 bg-matrix-green rounded-full" />
                <span>WEB: {stats.channel_breakdown.web}</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 bg-matrix-cyan rounded-full" />
                <span>X: {stats.channel_breakdown.x}</span>
              </div>
            </div>
          </div>

          {/* AGI Meter */}
          <div className="mt-4 pt-4 border-t border-matrix-green/30">
            <div className="flex justify-between text-xs mb-2">
              <span className="opacity-70">LEARNING PROGRESS</span>
              <span className="text-matrix-green">{stats.learning_score}%</span>
            </div>
            <div className="meter-track border-matrix-green">
              <div
                className="h-full bg-gradient-to-r from-matrix-green to-matrix-cyan transition-all duration-500"
                style={{ width: `${stats.learning_score}%` }}
              />
            </div>
            <div className="text-center text-xs mt-2 opacity-50">
              AGI METER (based on interactions)
            </div>
          </div>

          {/* Last updated */}
          <div className="mt-4 text-xs text-center opacity-50">
            Last updated: {formatTime(stats.updated_at)}
          </div>
        </>
      )}
    </div>
  )
}
