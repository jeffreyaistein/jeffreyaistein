'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import type { AvatarState } from '@/components/HologramAvatar3D'
import type { ConnectionStatus } from '@/hooks/useChat'

interface UseAvatarDriverOptions {
  connectionStatus: ConnectionStatus
  isTyping: boolean
  isSpeaking?: boolean
  audioElement?: HTMLAudioElement | null
}

interface AvatarDriverState {
  state: AvatarState
  amplitude: number
}

/**
 * Hook to drive avatar state based on chat events and audio analysis.
 *
 * State mapping:
 * - idle: No activity, connected or disconnected
 * - listening: User is typing or has just sent a message
 * - thinking: Assistant is generating response (streaming)
 * - speaking: TTS audio is playing (or simulated)
 */
export function useAvatarDriver(options: UseAvatarDriverOptions): AvatarDriverState {
  const { connectionStatus, isTyping, isSpeaking = false, audioElement } = options

  const [avatarState, setAvatarState] = useState<AvatarState>('idle')
  const [amplitude, setAmplitude] = useState(0)

  // Audio analysis refs
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const dataArrayRef = useRef<Uint8Array | null>(null)
  const animationFrameRef = useRef<number | null>(null)
  const sourceConnectedRef = useRef(false)

  // Simulated amplitude for speaking without real audio
  const simulatedAmplitudeRef = useRef(0)

  // Compute RMS amplitude from analyser
  const computeAmplitude = useCallback(() => {
    if (!analyserRef.current || !dataArrayRef.current) return 0

    analyserRef.current.getByteTimeDomainData(dataArrayRef.current)
    const data = dataArrayRef.current

    let sum = 0
    for (let i = 0; i < data.length; i++) {
      const normalized = (data[i] - 128) / 128
      sum += normalized * normalized
    }

    const rms = Math.sqrt(sum / data.length)
    return Math.min(1, rms * 3) // Scale and clamp
  }, [])

  // Setup audio analysis
  const setupAudioAnalysis = useCallback((audio: HTMLAudioElement) => {
    if (sourceConnectedRef.current) return

    try {
      // Create audio context
      const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
      if (!AudioContextClass) return

      const audioContext = new AudioContextClass()
      const analyser = audioContext.createAnalyser()
      analyser.fftSize = 256
      analyser.smoothingTimeConstant = 0.8

      // Connect audio element to analyser
      const source = audioContext.createMediaElementSource(audio)
      source.connect(analyser)
      analyser.connect(audioContext.destination)

      audioContextRef.current = audioContext
      analyserRef.current = analyser
      dataArrayRef.current = new Uint8Array(analyser.frequencyBinCount)
      sourceConnectedRef.current = true
    } catch (error) {
      console.warn('[useAvatarDriver] Audio analysis setup failed:', error)
    }
  }, [])

  // Animation loop for amplitude
  const updateAmplitude = useCallback(() => {
    if (isSpeaking && analyserRef.current) {
      // Real audio analysis
      const amp = computeAmplitude()
      setAmplitude((prev) => prev + (amp - prev) * 0.3) // Smooth interpolation
    } else if (isSpeaking) {
      // Simulated amplitude when no real audio
      simulatedAmplitudeRef.current += 0.15
      const simulated = (Math.sin(simulatedAmplitudeRef.current) * 0.5 + 0.5) *
                       (0.3 + Math.random() * 0.4)
      setAmplitude((prev) => prev + (simulated - prev) * 0.3)
    } else {
      // Decay amplitude when not speaking
      setAmplitude((prev) => prev * 0.9)
    }

    animationFrameRef.current = requestAnimationFrame(updateAmplitude)
  }, [isSpeaking, computeAmplitude])

  // Setup audio element connection
  useEffect(() => {
    if (audioElement && !sourceConnectedRef.current) {
      setupAudioAnalysis(audioElement)
    }
  }, [audioElement, setupAudioAnalysis])

  // Start/stop amplitude animation
  useEffect(() => {
    animationFrameRef.current = requestAnimationFrame(updateAmplitude)

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  }, [updateAmplitude])

  // Cleanup audio context
  useEffect(() => {
    return () => {
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close()
      }
    }
  }, [])

  // Determine avatar state based on chat state
  useEffect(() => {
    if (isSpeaking) {
      setAvatarState('speaking')
    } else if (isTyping) {
      setAvatarState('thinking')
    } else if (connectionStatus === 'connecting') {
      setAvatarState('thinking')
    } else if (connectionStatus === 'connected') {
      setAvatarState('idle')
    } else {
      setAvatarState('idle')
    }
  }, [connectionStatus, isTyping, isSpeaking])

  return {
    state: avatarState,
    amplitude,
  }
}

/**
 * Standalone hook for simulating speech amplitude.
 * Use this when TTS is not yet implemented.
 */
export function useSimulatedSpeech() {
  const [isSpeaking, setIsSpeaking] = useState(false)
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)

  const startSpeaking = useCallback((durationMs: number = 3000) => {
    setIsSpeaking(true)
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
    timeoutRef.current = setTimeout(() => {
      setIsSpeaking(false)
    }, durationMs)
  }, [])

  const stopSpeaking = useCallback(() => {
    setIsSpeaking(false)
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
  }, [])

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [])

  return {
    isSpeaking,
    startSpeaking,
    stopSpeaking,
  }
}
