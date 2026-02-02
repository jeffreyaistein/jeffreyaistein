'use client'

import { useState, useEffect } from 'react'

/**
 * Placeholder hologram component.
 * Will be replaced with Three.js implementation in Phase 7.
 */
export function HologramPlaceholder() {
  const [glitchOffset, setGlitchOffset] = useState(0)

  // Subtle glitch effect
  useEffect(() => {
    const interval = setInterval(() => {
      if (Math.random() > 0.95) {
        setGlitchOffset(Math.random() * 4 - 2)
        setTimeout(() => setGlitchOffset(0), 50)
      }
    }, 100)

    return () => clearInterval(interval)
  }, [])

  return (
    <div className="hologram-container flex items-center justify-center">
      {/* Placeholder robot silhouette */}
      <div
        className="relative transition-transform"
        style={{ transform: `translateX(${glitchOffset}px)` }}
      >
        {/* Head */}
        <div className="w-24 h-28 mx-auto border-2 border-matrix-cyan rounded-t-3xl relative">
          {/* Eyes */}
          <div className="absolute top-8 left-4 w-4 h-4 bg-matrix-cyan rounded-full animate-pulse" />
          <div className="absolute top-8 right-4 w-4 h-4 bg-matrix-cyan rounded-full animate-pulse" />
          {/* Mouth/visor line */}
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 w-12 h-1 bg-matrix-cyan opacity-50" />
        </div>

        {/* Neck */}
        <div className="w-8 h-4 mx-auto border-x-2 border-matrix-cyan/50" />

        {/* Body */}
        <div className="w-32 h-40 mx-auto border-2 border-matrix-cyan rounded-lg relative">
          {/* Chest details */}
          <div className="absolute top-4 left-1/2 -translate-x-1/2 w-16 h-8 border border-matrix-green/50 rounded" />
          <div className="absolute top-16 left-4 w-2 h-8 bg-matrix-green/30" />
          <div className="absolute top-16 right-4 w-2 h-8 bg-matrix-green/30" />
        </div>

        {/* Arms */}
        <div className="absolute top-36 -left-8 w-6 h-24 border-2 border-matrix-cyan/50 rounded-lg" />
        <div className="absolute top-36 -right-8 w-6 h-24 border-2 border-matrix-cyan/50 rounded-lg" />

        {/* Glow effect */}
        <div className="absolute inset-0 blur-xl opacity-20 bg-matrix-cyan rounded-full" />

        {/* Status text */}
        <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 text-xs text-matrix-cyan opacity-70 whitespace-nowrap">
          HOLOGRAM PLACEHOLDER
        </div>
      </div>

      {/* Floating particles */}
      {[...Array(5)].map((_, i) => (
        <div
          key={i}
          className="absolute w-1 h-1 bg-matrix-cyan rounded-full animate-pulse"
          style={{
            top: `${20 + Math.random() * 60}%`,
            left: `${20 + Math.random() * 60}%`,
            animationDelay: `${i * 0.3}s`,
          }}
        />
      ))}
    </div>
  )
}
