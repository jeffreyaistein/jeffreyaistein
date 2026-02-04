'use client'

import { useState, useEffect } from 'react'

interface TokenData {
  state: 'indexing' | 'live'
  market_cap: number
  market_cap_formatted: string
  holders: number
  volume_24h: number
  volume_24h_formatted: string
  price: number
  meter_max: number
  meter_fill: number
  is_ath: boolean
  updated_at: string | null
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || ''

export function TokenPanel() {
  const [data, setData] = useState<TokenData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Fetch token metrics from backend
  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/token/metrics`)
        if (!response.ok) throw new Error('Failed to fetch token metrics')
        const metrics = await response.json()
        setData(metrics)
        setError(null)
      } catch (err) {
        console.error('Token metrics error:', err)
        setError('Failed to load')
      } finally {
        setIsLoading(false)
      }
    }

    fetchMetrics()
    // Refresh every 30 seconds
    const interval = setInterval(fetchMetrics, 30000)
    return () => clearInterval(interval)
  }, [])

  const formatNumber = (num: number) => {
    if (num >= 1_000_000) return `$${(num / 1_000_000).toFixed(2)}M`
    if (num >= 1_000) return `$${(num / 1_000).toFixed(2)}K`
    return `$${num.toFixed(2)}`
  }

  const isIndexing = !data || data.state === 'indexing'
  const isLive = data?.state === 'live'

  return (
    <div className="stats-panel matrix-border-cyan rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold uppercase tracking-wider text-matrix-cyan">
          Token Metrics
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
          ) : isIndexing ? (
            <>
              <div className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" />
              <span>INDEXING</span>
            </>
          ) : (
            <>
              <div className="w-2 h-2 rounded-full bg-matrix-cyan" />
              <span>LIVE</span>
            </>
          )}
        </div>
      </div>

      {/* Indexing state */}
      {isIndexing && !isLoading && !error && (
        <div className="text-center py-6">
          <div className="text-matrix-cyan animate-pulse mb-2">◈</div>
          <p className="text-xs opacity-70">Indexing token data...</p>
          <p className="text-xs opacity-50 mt-1">On-chain metrics coming soon</p>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="text-center py-6">
          <p className="text-xs text-red-400">{error}</p>
        </div>
      )}

      {/* Live data */}
      {isLive && data && (
        <>
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
                {data.holders ? data.holders.toLocaleString() : 'n/a'}
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
        </>
      )}
    </div>
  )
}
