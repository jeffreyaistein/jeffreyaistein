'use client'

import { useState } from 'react'
import { brand, getExplorerUrl, hasContractAddress } from '@/config/brand'

// Copy icon
const CopyIcon = () => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    className="w-4 h-4"
    aria-hidden="true"
  >
    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
    <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
  </svg>
)

// Check icon (for copied state)
const CheckIcon = () => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    className="w-4 h-4"
    aria-hidden="true"
  >
    <polyline points="20 6 9 17 4 12" />
  </svg>
)

// External link icon
const ExternalLinkIcon = () => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    className="w-4 h-4"
    aria-hidden="true"
  >
    <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" />
    <polyline points="15 3 21 3 21 9" />
    <line x1="10" y1="14" x2="21" y2="3" />
  </svg>
)

export function ContractSection() {
  const [copied, setCopied] = useState(false)
  const hasAddress = hasContractAddress()
  const address = brand.contract.address

  const handleCopy = async () => {
    if (!hasAddress) return

    try {
      await navigator.clipboard.writeText(address)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  return (
    <div className="matrix-border rounded-lg overflow-hidden">
      <div className="p-2 border-b border-matrix-green/30 flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-matrix-green" />
        <span className="text-xs text-matrix-green uppercase tracking-wider">
          Contract Address
        </span>
      </div>

      <div className="p-4 bg-matrix-black/50">
        {hasAddress ? (
          <div className="space-y-3">
            {/* Address display */}
            <div className="flex items-center gap-2">
              <code className="flex-1 text-sm text-matrix-cyan font-mono break-all">
                {address}
              </code>
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-3">
              {/* Copy button */}
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-matrix-green border border-matrix-green/50 rounded hover:bg-matrix-green/10 transition-colors"
                title="Copy to clipboard"
              >
                {copied ? <CheckIcon /> : <CopyIcon />}
                <span>{copied ? 'Copied!' : 'Copy'}</span>
              </button>

              {/* Explorer link */}
              <a
                href={getExplorerUrl(address)}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-matrix-cyan border border-matrix-cyan/50 rounded hover:bg-matrix-cyan/10 transition-colors"
                title="View on Solscan"
              >
                <ExternalLinkIcon />
                <span>View on Explorer</span>
              </a>
            </div>
          </div>
        ) : (
          /* TBD state */
          <div className="text-center py-2">
            <span className="text-matrix-green/50 text-sm">TBD</span>
            <p className="text-xs text-matrix-green/30 mt-1">
              Contract address coming soon
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
