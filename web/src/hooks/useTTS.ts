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

// Debug info for TTS
interface TTSDebugInfo {
  voiceEnabled: boolean
  audioContextState: AudioContextState | 'unavailable'
  lastHttpStatus: number | null
  lastBytes: number | null
  lastPlayError: string | null
  lastAudioEnded: boolean
  amplitude: number
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

  // Real audio amplitude (0-1) from AnalyserNode
  amplitude: number

  // Audio element (for backwards compatibility)
  audioElement: HTMLAudioElement | null

  // Debug info (for NEXT_PUBLIC_DEBUG=true)
  debugInfo: TTSDebugInfo

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

  // AudioContext for unlocking audio playback and analysis
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const sourceNodeRef = useRef<MediaElementAudioSourceNode | null>(null)
  const dataArrayRef = useRef<Uint8Array | null>(null)
  const amplitudeAnimationRef = useRef<number | null>(null)
  const [realAmplitude, setRealAmplitude] = useState(0)

  // TTS state
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Debug state
  const [lastHttpStatus, setLastHttpStatus] = useState<number | null>(null)
  const [lastBytes, setLastBytes] = useState<number | null>(null)
  const [lastPlayError, setLastPlayError] = useState<string | null>(null)
  const [lastAudioEnded, setLastAudioEnded] = useState(false)

  // Audio element reference
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [audioElement, setAudioElement] = useState<HTMLAudioElement | null>(null)

  // Abort controller for cancelling requests
  const abortControllerRef = useRef<AbortController | null>(null)

  // Lock to prevent concurrent speak operations
  const speakLockRef = useRef<boolean>(false)

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
    return Math.min(1, rms * 3) // Scale and clamp to 0-1
  }, [])

  // Animation loop for amplitude while speaking
  const updateAmplitudeLoop = useCallback(() => {
    if (analyserRef.current && isSpeaking) {
      const amp = computeAmplitude()
      setRealAmplitude((prev) => prev + (amp - prev) * 0.3) // Smooth interpolation
      amplitudeAnimationRef.current = requestAnimationFrame(updateAmplitudeLoop)
    } else {
      // Decay amplitude when not speaking
      setRealAmplitude((prev) => {
        const decayed = prev * 0.85
        if (decayed > 0.01) {
          amplitudeAnimationRef.current = requestAnimationFrame(updateAmplitudeLoop)
        }
        return decayed
      })
    }
  }, [isSpeaking, computeAmplitude])

  // Start/stop amplitude animation based on speaking state
  useEffect(() => {
    if (isSpeaking && analyserRef.current) {
      amplitudeAnimationRef.current = requestAnimationFrame(updateAmplitudeLoop)
    }
    return () => {
      if (amplitudeAnimationRef.current) {
        cancelAnimationFrame(amplitudeAnimationRef.current)
      }
    }
  }, [isSpeaking, updateAmplitudeLoop])

  // Connect audio element to analyser when both are available
  useEffect(() => {
    if (audioContextRef.current && audioRef.current && !sourceNodeRef.current) {
      try {
        const analyser = audioContextRef.current.createAnalyser()
        analyser.fftSize = 1024  // Good balance of frequency/time resolution
        analyser.smoothingTimeConstant = 0.8

        const source = audioContextRef.current.createMediaElementSource(audioRef.current)
        source.connect(analyser)
        analyser.connect(audioContextRef.current.destination)

        analyserRef.current = analyser
        sourceNodeRef.current = source
        dataArrayRef.current = new Uint8Array(analyser.frequencyBinCount)

        console.log('[useTTS] Audio analyser connected, fftSize:', analyser.fftSize)
      } catch (err) {
        console.warn('[useTTS] Failed to setup audio analyser:', err)
      }
    }
  }, [voiceEnabled]) // Re-run when voice is enabled (AudioContext created)

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
        setLastAudioEnded(false)
        onStart?.()
      })

      audio.addEventListener('ended', () => {
        setIsSpeaking(false)
        setLastAudioEnded(true)
        console.log('[useTTS] Audio ended')
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

    // Wait for any in-progress speak operation to complete
    if (speakLockRef.current) {
      console.log('[useTTS] Speak already in progress, stopping previous...')
    }

    // Stop any current audio and wait for it to settle
    stop()

    // Acquire lock
    speakLockRef.current = true

    // Wait for audio element to fully reset after stop()
    await new Promise(resolve => setTimeout(resolve, 100))

    // Clear previous error and debug state
    setError(null)
    setLastPlayError(null)
    setLastHttpStatus(null)
    setLastBytes(null)
    setLastAudioEnded(false)
    setIsLoading(true)

    try {
      // Create abort controller
      abortControllerRef.current = new AbortController()

      // Determine API URL
      const baseUrl = apiBaseUrl || process.env.NEXT_PUBLIC_API_BASE_URL || ''
      const ttsUrl = `${baseUrl}/api/tts`
      console.log('[useTTS] Fetching from:', ttsUrl)

      // Fetch audio from TTS endpoint
      const response = await fetch(ttsUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text }),
        signal: abortControllerRef.current.signal,
      })

      // Track HTTP status
      setLastHttpStatus(response.status)
      console.log('[useTTS] Response status:', response.status)

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `TTS failed: ${response.status}`)
      }

      // Get audio blob
      const audioBlob = await response.blob()
      setLastBytes(audioBlob.size)
      console.log('[useTTS] Received audio blob:', audioBlob.size, 'bytes, type:', audioBlob.type)
      const audioUrl = URL.createObjectURL(audioBlob)

      // Play audio with specific error handling
      if (audioRef.current) {
        audioRef.current.src = audioUrl

        // Small delay to let the audio element settle after src change
        await new Promise(resolve => setTimeout(resolve, 50))

        try {
          await audioRef.current.play()
          console.log('[useTTS] Audio play() succeeded')
          setLastPlayError(null)
        } catch (playErr) {
          const playError = playErr as Error
          const errorName = playError.name || 'UnknownError'

          // AbortError from play() interrupted by pause() is benign - retry once
          if (errorName === 'AbortError') {
            console.log('[useTTS] play() was interrupted, retrying...')
            await new Promise(resolve => setTimeout(resolve, 100))
            try {
              await audioRef.current.play()
              console.log('[useTTS] Audio play() retry succeeded')
              setLastPlayError(null)
              return
            } catch (retryErr) {
              // Still failed after retry
              const retryError = retryErr as Error
              const errorMsg = `Play failed after retry: ${retryError.name} - ${retryError.message}`
              console.error('[useTTS] play() retry error:', errorMsg)
              setLastPlayError(errorMsg)
              setError(errorMsg)
              onError?.(errorMsg)
              return
            }
          }

          // Other play() errors
          const errorMsg = `Play failed: ${errorName} - ${playError.message}`
          console.error('[useTTS] play() error:', errorName, playError.message)
          setLastPlayError(errorMsg)
          setError(errorMsg)
          onError?.(errorMsg)
          return
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        // Request was cancelled, not an error
        return
      }

      const errorMessage = err instanceof Error ? err.message : 'TTS failed'
      console.error('[useTTS] Fetch error:', errorMessage)
      setError(errorMessage)
      onError?.(errorMessage)
    } finally {
      setIsLoading(false)
      speakLockRef.current = false
    }
  }, [voiceEnabled, apiBaseUrl, stop, onError])

  // Build debug info object
  const debugInfo: TTSDebugInfo = {
    voiceEnabled,
    audioContextState,
    lastHttpStatus,
    lastBytes,
    lastPlayError,
    lastAudioEnded,
    amplitude: realAmplitude,
  }

  return {
    voiceEnabled,
    setVoiceEnabled,
    toggleVoice,
    audioContextState,
    isSpeaking,
    isLoading,
    error,
    amplitude: realAmplitude,
    audioElement,
    debugInfo,
    speak,
    stop,
  }
}
