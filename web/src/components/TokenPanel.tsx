'use client'

import { useState, useEffect } from 'react'

interface TokenData {
  market_cap: number
  market_cap_formatted: string
  holders: number
  volume_24h: number
  volume_24h_formatted: string
  price: number
  meter_max: number
  meter_fill: number
  is_ath: boolean
}

export function TokenPanel() {
  const [data, setData] = useState<TokenData>({
    market_cap: 0,
    market_cap_formatted: '$0',
    holders: 0,
    volume_24h: 0,
    volume_24h_formatted: '$0',
    price: 0,
    meter_max: 1_000_000,
    meter_fill: 0,
    is_ath: false,
  })
  const [isConnected, setIsConnected] = useState(false)

  // WebSocket connection placeholder (Phase 5)
  useEffect(() => {
    // TODO: Implement real WebSocket connection in Phase 5
    const timer = setTimeout(() => setIsConnected(true), 1000)
    return () => clearTimeout(timer)
  }, [])

  const formatNumber = (num: number) => {
    if (num >= 1_000_000) return `$${(num / 1_000_000).toFixed(2)}M`
    if (num >= 1_000) return `$${(num / 1_000).toFixed(2)}K`
    return `$${num.toFixed(2)}`
  }

  return (
    <div className="stats-panel matrix-border-cyan rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold uppercase tracking-wider text-matrix-cyan">
          Token Metrics
        </h3>
        <div className="flex items-center gap-1 text-xs opacity-70">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-matrix-cyan' : 'bg-yellow-500'}`} />
          <span>{isConnected ? 'LIVE' : 'CONNECTING'}</span>
        </div>
      </div>

      {/* Metrics grid */}
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <span className="text-xs opacity-70">MARKET CAP</span>
          <span className="text-matrix-cyan font-bold">
            {data.market_cap_formatted || '--'}
          </span>
        </div>

        <div className="flex justify-between items-center">
          <span className="text-xs opacity-70">HOLDERS</span>
          <span className="text-matrix-green">
            {data.holders.toLocaleString() || '--'}
          </span>
        </div>

        <div className="flex justify-between items-center">
          <span className="text-xs opacity-70">24H VOLUME</span>
          <span className="text-matrix-green">
            {data.volume_24h_formatted || '--'}
          </span>
        </div>
      </div>

      {/* Market Cap Meter */}
      <div className="mt-4">
        <div className="flex justify-between text-xs mb-1">
          <span className="opacity-70">PROGRESS TO {formatNumber(data.meter_max)}</span>
          <span className="text-matrix-cyan">{(data.meter_fill * 100).toFixed(1)}%</span>
        </div>
        <div className="meter-track">
          <div
            className={`meter-fill ${data.is_ath ? 'ath-glow' : ''}`}
            style={{ width: `${data.meter_fill * 100}%` }}
          />
        </div>
        {data.is_ath && (
          <div className="text-center text-xs mt-1 text-matrix-cyan animate-pulse">
            ALL-TIME HIGH
          </div>
        )}
      </div>

      {/* Placeholder message */}
      <div className="mt-4 text-xs text-center opacity-50">
        Live data coming in Phase 5
      </div>
    </div>
  )
}
