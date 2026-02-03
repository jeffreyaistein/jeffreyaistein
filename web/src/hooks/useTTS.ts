'use client'

import { useState, useCallback, useRef, useEffect } from 'react'

// localStorage key for voice preference
const VOICE_ENABLED_KEY = 'tts_voice_enabled'

interface UseTTSOptions {
  apiBaseUrl?: string
  onError?: (error: string) => void
  onStart?: () => void
  onEnd?: () => void
}

interface UseTTSReturn {
  // Voice toggle (user must enable)
  voiceEnabled: boolean
  setVoiceEnabled: (enabled: boolean) => void
  toggleVoice: () => void

  // AudioContext state (for debug)
  audioContextState: AudioContextState | 'unavailable'

  // TTS state
  isSpeaking: boolean
  isLoading: boolean
  error: string | null

  // Audio element for amplitude analysis
  audioElement: HTMLAudioElement | null

  // Speak text
  speak: (text: string) => Promise<void>
  stop: () => void
}

// Load voice preference from localStorage
function loadVoiceEnabled(): boolean {
  if (typeof window === 'undefined') return false
  try {
    return localStorage.getItem(VOICE_ENABLED_KEY) === 'true'
  } catch {
    return false
  }
}

// Save voice preference to localStorage
function saveVoiceEnabled(enabled: boolean): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(VOICE_ENABLED_KEY, enabled ? 'true' : 'false')
  } catch {
    // Ignore storage errors
  }
}

/**
 * Hook for Text-to-Speech with ElevenLabs.
 *
 * Voice must be explicitly enabled by user to satisfy browser autoplay policies.
 * On enable, creates AudioContext and calls resume() to unlock audio.
 */
export function useTTS(options: UseTTSOptions = {}): UseTTSReturn {
  const { apiBaseUrl, onError, onStart, onEnd } = options

  // Voice toggle - load from localStorage, default off
  const [voiceEnabled, setVoiceEnabledState] = useState(false)
  const [audioContextState, setAudioContextState] = useState<AudioContextState | 'unavailable'>('unavailable')

  // AudioContext for unlocking audio playback
  const audioContextRef = useRef<AudioContext | null>(null)

  // TTS state
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Audio element reference
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [audioElement, setAudioElement] = useState<HTMLAudioElement | null>(null)

  // Abort controller for cancelling requests
  const abortControllerRef = useRef<AbortController | null>(null)

  // Load voice preference from localStorage on mount
  useEffect(() => {
    const saved = loadVoiceEnabled()
    if (saved) {
      // Don't auto-enable - user must click again after refresh
      // This ensures we always have a user gesture for AudioContext
      console.log('[useTTS] Voice was previously enabled, user must re-enable')
    }
  }, [])

  // Create audio element on mount (client-side only)
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const audio = new Audio()
      audio.crossOrigin = 'anonymous' // Enable CORS for audio analysis

      audio.addEventListener('play', () => {
        setIsSpeaking(true)
        onStart?.()
      })

      audio.addEventListener('ended', () => {
        setIsSpeaking(false)
        onEnd?.()
      })

      audio.addEventListener('pause', () => {
        setIsSpeaking(false)
      })

      audio.addEventListener('error', (e) => {
        console.error('[useTTS] Audio error:', e)
        setIsSpeaking(false)
        setError('Audio playback failed')
        onError?.('Audio playback failed')
      })

      audioRef.current = audio
      setAudioElement(audio)
    }

    return () => {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current.src = ''
      }
      // Close AudioContext on unmount
      if (audioContextRef.current) {
        audioContextRef.current.close()
      }
    }
  }, [onStart, onEnd, onError])

  // Set voice enabled with localStorage persistence and AudioContext resume
  const setVoiceEnabled = useCallback(async (enabled: boolean) => {
    console.log('[useTTS] setVoiceEnabled:', enabled)

    if (enabled) {
      // Create or resume AudioContext (requires user gesture)
      try {
        if (!audioContextRef.current) {
          const AudioContextClass = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
          if (AudioContextClass) {
            audioContextRef.current = new AudioContextClass()
            console.log('[useTTS] Created AudioContext, state:', audioContextRef.current.state)
          }
        }

        if (audioContextRef.current) {
          // Resume AudioContext (critical for iOS/Safari)
          await audioContextRef.current.resume()
          console.log('[useTTS] AudioContext resumed, state:', audioContextRef.current.state)
          setAudioContextState(audioContextRef.current.state)
        }
      } catch (err) {
        console.error('[useTTS] Failed to resume AudioContext:', err)
        setError('Failed to enable audio')
        onError?.('Failed to enable audio')
        return
      }
    }

    setVoiceEnabledState(enabled)
    saveVoiceEnabled(enabled)
    setError(null)
  }, [onError])

  // Toggle voice (wraps setVoiceEnabled)
  const toggleVoice = useCallback(() => {
    setVoiceEnabled(!voiceEnabled)
  }, [voiceEnabled, setVoiceEnabled])

  // Stop speaking
  const stop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
    }
    setIsSpeaking(false)
    setIsLoading(false)
  }, [])

  // Speak text
  const speak = useCallback(async (text: string) => {
    // Don't speak if voice is disabled
    if (!voiceEnabled) {
      return
    }

    // Stop any current audio
    stop()

    // Clear previous error
    setError(null)
    setIsLoading(true)

    try {
      // Create abort controller
      abortControllerRef.current = new AbortController()

      // Determine API URL
      const baseUrl = apiBaseUrl || process.env.NEXT_PUBLIC_API_BASE_URL || ''
      const ttsUrl = `${baseUrl}/api/tts`

      // Fetch audio from TTS endpoint
      const response = await fetch(ttsUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text }),
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `TTS failed: ${response.status}`)
      }

      // Get audio blob
      const audioBlob = await response.blob()
      const audioUrl = URL.createObjectURL(audioBlob)

      // Play audio
      if (audioRef.current) {
        audioRef.current.src = audioUrl
        await audioRef.current.play()
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        // Request was cancelled, not an error
        return
      }

      const errorMessage = err instanceof Error ? err.message : 'TTS failed'
      console.error('[useTTS] Error:', errorMessage)
      setError(errorMessage)
      onError?.(errorMessage)
    } finally {
      setIsLoading(false)
    }
  }, [voiceEnabled, apiBaseUrl, stop, onError])

  return {
    voiceEnabled,
    setVoiceEnabled,
    toggleVoice,
    audioContextState,
    isSpeaking,
    isLoading,
    error,
    audioElement,
    speak,
    stop,
  }
}
