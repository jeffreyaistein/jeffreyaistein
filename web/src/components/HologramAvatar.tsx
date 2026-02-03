'use client'

import { HologramAvatar3D, type AvatarState } from '@/components/HologramAvatar3D'
import { HologramCardAvatar } from '@/components/HologramCardAvatar'
import { HologramProjectedFace } from '@/components/HologramProjectedFace'

// Avatar mode from environment
const AVATAR_MODE = process.env.NEXT_PUBLIC_AVATAR_MODE || 'glb'

// Re-export types
export type { AvatarState }

interface HologramAvatarProps {
  state?: AvatarState
  amplitude?: number
  className?: string
}

/**
 * Unified hologram avatar component that switches between modes.
 *
 * Modes:
 * - glb: Full 3D GLB model with hologram shader (default)
 * - card: 2.5D card/plane with face texture and hologram effects
 * - projected_face: Face PNG projected onto GLB mesh (no hologram tint)
 *
 * Set via: NEXT_PUBLIC_AVATAR_MODE=glb|card|projected_face
 */
export function HologramAvatar({
  state = 'idle',
  amplitude = 0,
  className = '',
}: HologramAvatarProps) {
  if (AVATAR_MODE === 'card') {
    return (
      <HologramCardAvatar
        state={state}
        amplitude={amplitude}
        className={className}
      />
    )
  }

  if (AVATAR_MODE === 'projected_face') {
    return (
      <HologramProjectedFace
        state={state}
        amplitude={amplitude}
        className={className}
      />
    )
  }

  // Default to GLB mode
  return (
    <HologramAvatar3D
      state={state}
      amplitude={amplitude}
      className={className}
    />
  )
}

// Export the mode for debugging
export function getAvatarMode(): string {
  return AVATAR_MODE
}
