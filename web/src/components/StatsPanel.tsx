'use client'

import { useState, useEffect } from 'react'

interface AgentStats {
  messages_processed: number
  messages_replied: number
  channel_breakdown: {
    web: number
    x: number
  }
  learning_score: number
  semantic_memories_count: number
}

export function StatsPanel() {
  const [stats, setStats] = useState<AgentStats>({
    messages_processed: 0,
    messages_replied: 0,
    channel_breakdown: { web: 0, x: 0 },
    learning_score: 0,
    semantic_memories_count: 0,
  })
  const [isConnected, setIsConnected] = useState(false)

  // WebSocket connection placeholder (Phase 6)
  useEffect(() => {
    // TODO: Implement real WebSocket connection in Phase 6
    const timer = setTimeout(() => setIsConnected(true), 1000)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div className="stats-panel matrix-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold uppercase tracking-wider text-matrix-green">
          AGI Bot Stats
        </h3>
        <div className="flex items-center gap-1 text-xs opacity-70">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-matrix-green' : 'bg-yellow-500'}`} />
          <span>{isConnected ? 'LIVE' : 'CONNECTING'}</span>
        </div>
      </div>

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
          <span className="text-xs opacity-70">MEMORIES</span>
          <span className="text-matrix-cyan font-mono">
            {stats.semantic_memories_count.toLocaleString()}
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
          <span className="text-matrix-green">{(stats.learning_score * 100).toFixed(1)}%</span>
        </div>
        <div className="meter-track border-matrix-green">
          <div
            className="h-full bg-gradient-to-r from-matrix-green to-matrix-cyan transition-all duration-500"
            style={{ width: `${stats.learning_score * 100}%` }}
          />
        </div>
        <div className="text-center text-xs mt-2 opacity-50">
          AGI METER (based on stored memories)
        </div>
      </div>

      {/* Placeholder message */}
      <div className="mt-4 text-xs text-center opacity-50">
        Live stats coming in Phase 6
      </div>
    </div>
  )
}
