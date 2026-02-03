'use client'

import { useState, useEffect } from 'react'

/**
 * Debug panel for diagnosing connection issues in production.
 * Only visible when NEXT_PUBLIC_DEBUG=true
 *
 * Shows:
 * - Raw environment variable values
 * - Computed REST and WebSocket URLs
 * - Connection state and errors
 */

// Get raw env values (will be replaced at build time by Next.js)
const RAW_API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL
const RAW_API_URL = process.env.NEXT_PUBLIC_API_URL
const RAW_WS_URL = process.env.NEXT_PUBLIC_WS_URL
const DEBUG_ENABLED = process.env.NEXT_PUBLIC_DEBUG === 'true'

// Determine URL source for display
function getUrlSource(): string {
  if (RAW_API_BASE_URL) return 'NEXT_PUBLIC_API_BASE_URL'
  if (RAW_API_URL && RAW_WS_URL) return 'legacy (separate URLs)'
  return 'FALLBACK (localhost)'
}

// Compute URLs from base (the correct way)
function computeUrls(baseUrl: string | undefined) {
  if (!baseUrl) {
    return {
      restUrl: null,
      wsUrl: null,
      error: 'NEXT_PUBLIC_API_BASE_URL is not set',
    }
  }

  // Normalize: remove trailing slash
  const normalized = baseUrl.replace(/\/$/, '')

  // Compute WebSocket URL
  let wsUrl: string
  if (normalized.startsWith('https://')) {
    wsUrl = normalized.replace('https://', 'wss://')
  } else if (normalized.startsWith('http://')) {
    wsUrl = normalized.replace('http://', 'ws://')
  } else {
    return {
      restUrl: normalized,
      wsUrl: null,
      error: `Invalid URL scheme: ${normalized}`,
    }
  }

  return {
    restUrl: normalized,
    wsUrl: wsUrl,
    error: null,
  }
}

interface DebugPanelProps {
  connectionStatus?: string
  lastError?: string | null
}

export function DebugPanel({ connectionStatus, lastError }: DebugPanelProps) {
  const [isExpanded, setIsExpanded] = useState(true)

  // Compute URLs
  const computed = computeUrls(RAW_API_BASE_URL)
  const urlSource = getUrlSource()

  // Log debug info on mount
  useEffect(() => {
    if (!DEBUG_ENABLED) return

    console.log('=== AISTEIN DEBUG INFO ===')
    console.log('URL Source:', urlSource)
    console.log('NEXT_PUBLIC_API_BASE_URL (raw):', RAW_API_BASE_URL ?? '(not set)')
    console.log('NEXT_PUBLIC_API_URL (raw):', RAW_API_URL ?? '(not set)')
    console.log('NEXT_PUBLIC_WS_URL (raw):', RAW_WS_URL ?? '(not set)')
    console.log('Computed REST URL:', computed.restUrl ?? '(error)')
    console.log('Computed WS URL:', computed.wsUrl ?? '(error)')
    console.log('WS Chat URL:', computed.wsUrl ? `${computed.wsUrl}/ws/chat` : '(error)')
    console.log('Session URL:', computed.restUrl ? `${computed.restUrl}/api/session` : '(error)')
    if (computed.error) {
      console.error('URL computation error:', computed.error)
    }
    console.log('==========================')
  }, [computed.restUrl, computed.wsUrl, computed.error, urlSource])

  // Don't render if debug not enabled
  if (!DEBUG_ENABLED) {
    return null
  }

  // Helper to render value with status color
  const renderValue = (value: string | null | undefined, fallback: string = '(not set)') => {
    if (!value) {
      return <span className="text-red-400">{fallback}</span>
    }
    return <span className="text-matrix-green">{value}</span>
  }

  const statusColor = {
    connecting: 'text-yellow-400',
    connected: 'text-matrix-green',
    disconnected: 'text-gray-400',
    error: 'text-red-400',
  }[connectionStatus ?? 'disconnected'] ?? 'text-gray-400'

  return (
    <div className="fixed bottom-4 right-4 z-50 max-w-md">
      <div className="bg-black/90 border border-matrix-cyan rounded-lg shadow-lg overflow-hidden">
        {/* Header */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full px-3 py-2 flex items-center justify-between bg-matrix-cyan/20 hover:bg-matrix-cyan/30 transition-colors"
        >
          <span className="text-xs font-bold text-matrix-cyan uppercase tracking-wider">
            Debug Panel
          </span>
          <span className="text-matrix-cyan">{isExpanded ? '▼' : '▲'}</span>
        </button>

        {/* Content */}
        {isExpanded && (
          <div className="p-3 space-y-2 text-xs font-mono">
            {/* Environment Variables */}
            <div className="space-y-1">
              <div className="text-gray-400 uppercase text-[10px]">Environment Variables</div>
              <div className="pl-2 space-y-1">
                <div>
                  <span className="text-gray-500">NEXT_PUBLIC_API_BASE_URL: </span>
                  {renderValue(RAW_API_BASE_URL)}
                </div>
                <div>
                  <span className="text-gray-500">NEXT_PUBLIC_API_URL: </span>
                  {renderValue(RAW_API_URL)}
                </div>
                <div>
                  <span className="text-gray-500">NEXT_PUBLIC_WS_URL: </span>
                  {renderValue(RAW_WS_URL)}
                </div>
              </div>
            </div>

            {/* Computed URLs */}
            <div className="space-y-1 border-t border-gray-700 pt-2">
              <div className="text-gray-400 uppercase text-[10px]">Computed URLs</div>
              <div className="pl-2 space-y-1">
                <div>
                  <span className="text-gray-500">Source: </span>
                  <span className={urlSource.includes('FALLBACK') ? 'text-red-400' : 'text-matrix-cyan'}>
                    {urlSource}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500">REST Base: </span>
                  {renderValue(computed.restUrl)}
                </div>
                <div>
                  <span className="text-gray-500">WebSocket Base: </span>
                  {renderValue(computed.wsUrl)}
                </div>
                <div>
                  <span className="text-gray-500">WS Chat URL: </span>
                  {computed.wsUrl ? (
                    <span className="text-matrix-green">{computed.wsUrl}/ws/chat</span>
                  ) : (
                    <span className="text-red-400">(error)</span>
                  )}
                </div>
                <div>
                  <span className="text-gray-500">Session URL: </span>
                  {computed.restUrl ? (
                    <span className="text-matrix-green">{computed.restUrl}/api/session</span>
                  ) : (
                    <span className="text-red-400">(error)</span>
                  )}
                </div>
              </div>
            </div>

            {/* Computation Error */}
            {computed.error && (
              <div className="border-t border-red-700 pt-2">
                <div className="text-red-400 uppercase text-[10px]">Error</div>
                <div className="pl-2 text-red-400">{computed.error}</div>
              </div>
            )}

            {/* Connection State */}
            <div className="space-y-1 border-t border-gray-700 pt-2">
              <div className="text-gray-400 uppercase text-[10px]">Connection State</div>
              <div className="pl-2 space-y-1">
                <div>
                  <span className="text-gray-500">Status: </span>
                  <span className={statusColor}>{connectionStatus ?? 'unknown'}</span>
                </div>
                {lastError && (
                  <div>
                    <span className="text-gray-500">Last Error: </span>
                    <span className="text-red-400">{lastError}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Warnings */}
            {(!RAW_API_BASE_URL && (RAW_API_URL || RAW_WS_URL)) && (
              <div className="border-t border-yellow-700 pt-2">
                <div className="text-yellow-400 uppercase text-[10px]">Warning</div>
                <div className="pl-2 text-yellow-400">
                  Using legacy env vars. Set NEXT_PUBLIC_API_BASE_URL instead.
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// Export computed URL helper for use in other components
export function getApiUrls() {
  const base = RAW_API_BASE_URL
  const computed = computeUrls(base)

  return {
    apiBaseUrl: computed.restUrl,
    wsBaseUrl: computed.wsUrl,
    error: computed.error,
    isDebugEnabled: DEBUG_ENABLED,
  }
}
