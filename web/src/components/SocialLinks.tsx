'use client'

import { brand } from '@/config/brand'

// Simple SVG icons for social platforms
const XIcon = () => (
  <svg
    viewBox="0 0 24 24"
    fill="currentColor"
    className="w-5 h-5"
    aria-hidden="true"
  >
    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
  </svg>
)

const TikTokIcon = () => (
  <svg
    viewBox="0 0 24 24"
    fill="currentColor"
    className="w-5 h-5"
    aria-hidden="true"
  >
    <path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-5.2 1.74 2.89 2.89 0 012.31-4.64 2.93 2.93 0 01.88.13V9.4a6.84 6.84 0 00-1-.05A6.33 6.33 0 005 20.1a6.34 6.34 0 0010.86-4.43v-7a8.16 8.16 0 004.77 1.52v-3.4a4.85 4.85 0 01-1-.1z" />
  </svg>
)

interface SocialLinksProps {
  className?: string
  showLabels?: boolean
}

export function SocialLinks({ className = '', showLabels = false }: SocialLinksProps) {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      {/* X (Twitter) */}
      <a
        href={brand.social.x.url}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-1.5 text-matrix-green hover:text-matrix-cyan transition-colors"
        title={`Follow on X ${brand.social.x.handle}`}
      >
        <XIcon />
        {showLabels && (
          <span className="text-xs">{brand.social.x.handle}</span>
        )}
      </a>

      {/* TikTok */}
      <a
        href={brand.social.tiktok.url}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-1.5 text-matrix-green hover:text-matrix-cyan transition-colors"
        title={`Follow on TikTok ${brand.social.tiktok.handle}`}
      >
        <TikTokIcon />
        {showLabels && (
          <span className="text-xs">{brand.social.tiktok.handle}</span>
        )}
      </a>
    </div>
  )
}
