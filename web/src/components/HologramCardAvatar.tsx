'use client'

import { useRef, useEffect, useState, useMemo } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useTexture } from '@react-three/drei'
import * as THREE from 'three'

import type { AvatarState } from '@/components/HologramAvatar3D'

// Debug mode from environment
const DEBUG_ENABLED = process.env.NEXT_PUBLIC_AVATAR_DEBUG === 'true'

// Card hologram shader - similar to 3D but optimized for 2D plane
const CardHologramShader = {
  uniforms: {
    time: { value: 0 },
    faceTexture: { value: null as THREE.Texture | null },
    mouthMask: { value: null as THREE.Texture | null },
    baseColor: { value: new THREE.Color(0x00ff88) },
    glowColor: { value: new THREE.Color(0x00ffcc) },
    scanlineIntensity: { value: 0.12 },
    flickerIntensity: { value: 0.03 },
    glitchIntensity: { value: 0.0 },
    noiseIntensity: { value: 0.08 },
    avatarState: { value: 0 }, // 0=idle, 1=listening, 2=thinking, 3=speaking
    amplitude: { value: 0.0 },
    mouthGlowIntensity: { value: 0.0 },
    // Debug offset/scale for mouth mask alignment
    maskOffsetX: { value: 0.0 },
    maskOffsetY: { value: 0.0 },
    maskScale: { value: 1.0 },
  },
  vertexShader: `
    varying vec2 vUv;
    varying vec3 vPosition;

    uniform float time;
    uniform float glitchIntensity;

    void main() {
      vUv = uv;
      vPosition = position;

      vec3 pos = position;

      // Subtle glitch displacement
      if (glitchIntensity > 0.0) {
        float glitch = sin(time * 50.0 + position.y * 10.0) * glitchIntensity;
        pos.x += glitch * step(0.98, fract(sin(time * 100.0) * 43758.5453));
      }

      gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
    }
  `,
  fragmentShader: `
    uniform float time;
    uniform sampler2D faceTexture;
    uniform sampler2D mouthMask;
    uniform vec3 baseColor;
    uniform vec3 glowColor;
    uniform float scanlineIntensity;
    uniform float flickerIntensity;
    uniform float noiseIntensity;
    uniform float avatarState;
    uniform float amplitude;
    uniform float mouthGlowIntensity;
    uniform float maskOffsetX;
    uniform float maskOffsetY;
    uniform float maskScale;

    varying vec2 vUv;
    varying vec3 vPosition;

    // Noise function
    float noise(vec2 p) {
      return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
    }

    void main() {
      // Sample face texture
      vec4 faceColor = texture2D(faceTexture, vUv);

      // Discard fully transparent pixels
      if (faceColor.a < 0.1) {
        discard;
      }

      // Scanlines
      float scanline = sin(vUv.y * 200.0 + time * 2.0) * 0.5 + 0.5;
      scanline = mix(1.0, scanline, scanlineIntensity);

      // Flicker
      float flicker = 1.0 - flickerIntensity * noise(vec2(time * 10.0, 0.0));

      // Noise overlay
      float n = noise(vUv * 100.0 + time * 5.0) * noiseIntensity;

      // State-based effects
      vec3 tintColor = baseColor;
      float statePulse = 1.0;

      if (avatarState > 0.5 && avatarState < 1.5) {
        // Listening - subtle cyan pulse
        statePulse = 0.9 + 0.1 * sin(time * 3.0);
        tintColor = mix(baseColor, vec3(0.0, 0.8, 1.0), 0.2);
      } else if (avatarState > 1.5 && avatarState < 2.5) {
        // Thinking - faster pulse, more cyan
        statePulse = 0.85 + 0.15 * sin(time * 6.0);
        tintColor = mix(baseColor, vec3(0.0, 1.0, 1.0), 0.4);
      } else if (avatarState > 2.5) {
        // Speaking - amplitude-driven intensity
        statePulse = 0.9 + amplitude * 0.2;
        tintColor = mix(baseColor, glowColor, amplitude * 0.3);
      }

      // Mouth mask glow (speaking) - sample with offset/scale
      float mouthGlow = 0.0;
      if (mouthGlowIntensity > 0.0) {
        vec2 maskUv = (vUv - 0.5) / maskScale + 0.5;
        maskUv.x += maskOffsetX;
        maskUv.y += maskOffsetY;
        vec4 maskSample = texture2D(mouthMask, maskUv);
        mouthGlow = maskSample.r * mouthGlowIntensity * amplitude;
      }

      // Edge glow effect (fake fresnel for 2D)
      float edgeDist = min(min(vUv.x, 1.0 - vUv.x), min(vUv.y, 1.0 - vUv.y));
      float edgeGlow = smoothstep(0.0, 0.15, edgeDist) * 0.3 + 0.7;

      // Combine face with hologram effects
      vec3 color = faceColor.rgb;

      // Apply hologram tint (subtle colorization)
      color = mix(color, color * tintColor, 0.3);

      // Add glow effects
      color += glowColor * (1.0 - edgeGlow) * 0.2; // Edge glow
      color += mouthGlow * glowColor; // Mouth glow when speaking

      // Apply scanlines, flicker, noise
      color *= scanline * flicker * statePulse;
      color += vec3(n * 0.5);

      // Chromatic aberration (subtle)
      float chromaShift = 0.002 * (1.0 + amplitude * 2.0);
      float r = texture2D(faceTexture, vUv + vec2(chromaShift, 0.0)).r;
      float b = texture2D(faceTexture, vUv - vec2(chromaShift, 0.0)).b;
      color.r = mix(color.r, r, 0.3);
      color.b = mix(color.b, b, 0.3);

      gl_FragColor = vec4(color, faceColor.a * flicker);
    }
  `,
}

// Props interface
interface CardAvatarProps {
  state: AvatarState
  amplitude: number
}

// The card plane component
function CardPlane({ state, amplitude }: CardAvatarProps) {
  const meshRef = useRef<THREE.Mesh>(null)
  const materialRef = useRef<THREE.ShaderMaterial | null>(null)

  // Load textures
  const faceTexture = useTexture('/assets/models/aistein/aistein_face.png')
  const mouthMaskTexture = useTexture('/assets/models/aistein/aistein_face_mouth_mask.png')

  // Configure textures
  useEffect(() => {
    if (faceTexture) {
      faceTexture.minFilter = THREE.LinearFilter
      faceTexture.magFilter = THREE.LinearFilter
    }
    if (mouthMaskTexture) {
      mouthMaskTexture.minFilter = THREE.LinearFilter
      mouthMaskTexture.magFilter = THREE.LinearFilter
    }
  }, [faceTexture, mouthMaskTexture])

  // Create shader material
  const shaderMaterial = useMemo(() => {
    const mat = new THREE.ShaderMaterial({
      uniforms: { ...CardHologramShader.uniforms },
      vertexShader: CardHologramShader.vertexShader,
      fragmentShader: CardHologramShader.fragmentShader,
      transparent: true,
      side: THREE.DoubleSide,
      depthWrite: false,
    })
    mat.uniforms.faceTexture.value = faceTexture
    mat.uniforms.mouthMask.value = mouthMaskTexture
    return mat
  }, [faceTexture, mouthMaskTexture])

  useEffect(() => {
    materialRef.current = shaderMaterial
  }, [shaderMaterial])

  // Map state to numeric value
  const stateValue = useMemo(() => {
    switch (state) {
      case 'listening': return 1
      case 'thinking': return 2
      case 'speaking': return 3
      default: return 0
    }
  }, [state])

  // Animation loop
  useFrame((_, delta) => {
    if (materialRef.current) {
      const uniforms = materialRef.current.uniforms
      uniforms.time.value += delta
      uniforms.avatarState.value = stateValue

      // Smooth amplitude interpolation
      uniforms.amplitude.value += (amplitude - uniforms.amplitude.value) * 0.15
      uniforms.mouthGlowIntensity.value = state === 'speaking' ? 2.0 : 0.0

      // Random glitch effect (more frequent when thinking)
      const glitchChance = state === 'thinking' ? 0.98 : 0.995
      if (Math.random() > glitchChance) {
        uniforms.glitchIntensity.value = 0.015
      } else {
        uniforms.glitchIntensity.value *= 0.9
      }
    }

    // Floating animation
    if (meshRef.current) {
      const time = Date.now() * 0.001
      meshRef.current.position.y = Math.sin(time * 0.8) * 0.03
      // Gentle wobble
      meshRef.current.rotation.z = Math.sin(time * 0.5) * 0.02
      meshRef.current.rotation.y = Math.sin(time * 0.3) * 0.05
    }
  })

  // Aspect ratio for the plane (based on typical portrait)
  const aspect = 1.0 // Square for now, adjust if needed

  return (
    <mesh ref={meshRef} material={shaderMaterial}>
      <planeGeometry args={[2 * aspect, 2.5]} />
    </mesh>
  )
}

// Debug overlay for mask alignment
function DebugMaskOverlay({
  maskOffset,
  maskScale,
  onOffsetChange,
  onScaleChange,
}: {
  maskOffset: { x: number; y: number }
  maskScale: number
  onOffsetChange: (x: number, y: number) => void
  onScaleChange: (scale: number) => void
}) {
  const texture = useTexture('/assets/models/aistein/aistein_face_mouth_mask.png')

  return (
    <mesh position={[0, 0, 0.01]}>
      <planeGeometry args={[2 * maskScale, 2.5 * maskScale]} />
      <meshBasicMaterial
        map={texture}
        transparent
        opacity={0.4}
        color={0xff0000}
        depthTest={false}
      />
    </mesh>
  )
}

// Scene setup
function CardScene({ state, amplitude }: CardAvatarProps) {
  const { gl } = useThree()
  const [maskOffset, setMaskOffset] = useState({ x: 0, y: 0 })
  const [maskScale, setMaskScale] = useState(1.0)

  useEffect(() => {
    gl.setClearColor(0x000000, 0)
  }, [gl])

  // Keyboard controls for debug alignment
  useEffect(() => {
    if (!DEBUG_ENABLED) return

    const handleKeyDown = (e: KeyboardEvent) => {
      const step = e.shiftKey ? 0.01 : 0.05
      switch (e.key) {
        case 'ArrowLeft':
          setMaskOffset(prev => ({ ...prev, x: prev.x - step }))
          break
        case 'ArrowRight':
          setMaskOffset(prev => ({ ...prev, x: prev.x + step }))
          break
        case 'ArrowUp':
          setMaskOffset(prev => ({ ...prev, y: prev.y + step }))
          break
        case 'ArrowDown':
          setMaskOffset(prev => ({ ...prev, y: prev.y - step }))
          break
        case '+':
        case '=':
          setMaskScale(prev => prev + 0.05)
          break
        case '-':
          setMaskScale(prev => Math.max(0.1, prev - 0.05))
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Log offset values when they change (for baking in)
  useEffect(() => {
    if (DEBUG_ENABLED) {
      console.log('[CardAvatar] Mask offset:', maskOffset, 'Scale:', maskScale)
    }
  }, [maskOffset, maskScale])

  return (
    <>
      <ambientLight intensity={0.5} />
      <pointLight position={[0, 2, 3]} intensity={0.3} color={0x00ffcc} />

      <CardPlane state={state} amplitude={amplitude} />

      {DEBUG_ENABLED && (
        <DebugMaskOverlay
          maskOffset={maskOffset}
          maskScale={maskScale}
          onOffsetChange={(x, y) => setMaskOffset({ x, y })}
          onScaleChange={setMaskScale}
        />
      )}
    </>
  )
}

// Main exported component
interface HologramCardAvatarProps {
  state?: AvatarState
  amplitude?: number
  className?: string
}

export function HologramCardAvatar({
  state = 'idle',
  amplitude = 0,
  className = '',
}: HologramCardAvatarProps) {
  const [isClient, setIsClient] = useState(false)

  useEffect(() => {
    setIsClient(true)
  }, [])

  if (!isClient) {
    return (
      <div className={`hologram-container ${className}`}>
        <div className="flex items-center justify-center h-full">
          <div className="text-matrix-cyan text-xs animate-pulse">
            Initializing hologram...
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={`hologram-container relative ${className}`}>
      <Canvas
        camera={{ position: [0, 0, 3], fov: 50 }}
        gl={{ alpha: true, antialias: true }}
        style={{ background: 'transparent' }}
      >
        <CardScene state={state} amplitude={amplitude} />
      </Canvas>

      {/* State indicator (debug) */}
      {DEBUG_ENABLED && (
        <div className="absolute top-2 left-2 text-xs text-matrix-cyan bg-black/50 px-2 py-1 rounded space-y-1">
          <div>Mode: CARD | State: {state} | Amp: {amplitude.toFixed(2)}</div>
          <div className="text-[10px] text-gray-400">
            Arrow keys: offset | +/-: scale | Shift: fine
          </div>
        </div>
      )}

      {/* Scanline overlay */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,255,136,0.03) 2px, rgba(0,255,136,0.03) 4px)',
        }}
      />
    </div>
  )
}
