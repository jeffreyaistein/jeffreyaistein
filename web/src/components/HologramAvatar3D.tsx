'use client'

import { useRef, useEffect, useState, useCallback, useMemo } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useGLTF, useTexture } from '@react-three/drei'
import * as THREE from 'three'

// Avatar states
export type AvatarState = 'idle' | 'listening' | 'thinking' | 'speaking'

// Props for controlling the avatar externally
export interface AvatarDriverProps {
  state: AvatarState
  amplitude: number // 0-1 for mouth animation
}

// Debug mode from environment
const DEBUG_ENABLED = process.env.NEXT_PUBLIC_AVATAR_DEBUG === 'true'

// Hologram shader material
const HologramShaderMaterial = {
  uniforms: {
    time: { value: 0 },
    baseColor: { value: new THREE.Color(0x00ff88) },
    glowColor: { value: new THREE.Color(0x00ffcc) },
    scanlineIntensity: { value: 0.15 },
    flickerIntensity: { value: 0.05 },
    glitchIntensity: { value: 0.0 },
    noiseIntensity: { value: 0.1 },
    fresnelPower: { value: 2.0 },
    avatarState: { value: 0 }, // 0=idle, 1=listening, 2=thinking, 3=speaking
    amplitude: { value: 0.0 },
    mouthMask: { value: null as THREE.Texture | null },
    mouthGlowIntensity: { value: 0.0 },
  },
  vertexShader: `
    varying vec2 vUv;
    varying vec3 vNormal;
    varying vec3 vPosition;
    varying vec3 vWorldPosition;

    uniform float time;
    uniform float glitchIntensity;

    void main() {
      vUv = uv;
      vNormal = normalize(normalMatrix * normal);
      vPosition = position;

      vec3 pos = position;

      // Subtle glitch displacement
      if (glitchIntensity > 0.0) {
        float glitch = sin(time * 50.0 + position.y * 10.0) * glitchIntensity;
        pos.x += glitch * step(0.98, fract(sin(time * 100.0) * 43758.5453));
      }

      vec4 worldPos = modelMatrix * vec4(pos, 1.0);
      vWorldPosition = worldPos.xyz;

      gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
    }
  `,
  fragmentShader: `
    uniform float time;
    uniform vec3 baseColor;
    uniform vec3 glowColor;
    uniform float scanlineIntensity;
    uniform float flickerIntensity;
    uniform float noiseIntensity;
    uniform float fresnelPower;
    uniform float avatarState;
    uniform float amplitude;
    uniform sampler2D mouthMask;
    uniform float mouthGlowIntensity;

    varying vec2 vUv;
    varying vec3 vNormal;
    varying vec3 vPosition;
    varying vec3 vWorldPosition;

    // Noise function
    float noise(vec2 p) {
      return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
    }

    void main() {
      // Base fresnel effect for hologram edge glow
      vec3 viewDir = normalize(cameraPosition - vWorldPosition);
      float fresnel = pow(1.0 - max(dot(viewDir, vNormal), 0.0), fresnelPower);

      // Scanlines
      float scanline = sin(vWorldPosition.y * 100.0 + time * 2.0) * 0.5 + 0.5;
      scanline = mix(1.0, scanline, scanlineIntensity);

      // Flicker
      float flicker = 1.0 - flickerIntensity * noise(vec2(time * 10.0, 0.0));

      // Noise overlay
      float n = noise(vUv * 100.0 + time * 5.0) * noiseIntensity;

      // State-based color modulation
      vec3 stateColor = baseColor;
      float statePulse = 1.0;

      if (avatarState > 0.5 && avatarState < 1.5) {
        // Listening - subtle cyan pulse
        statePulse = 0.9 + 0.1 * sin(time * 3.0);
        stateColor = mix(baseColor, vec3(0.0, 0.8, 1.0), 0.3);
      } else if (avatarState > 1.5 && avatarState < 2.5) {
        // Thinking - faster pulse, more cyan
        statePulse = 0.85 + 0.15 * sin(time * 6.0);
        stateColor = mix(baseColor, vec3(0.0, 1.0, 1.0), 0.5);
      } else if (avatarState > 2.5) {
        // Speaking - amplitude-driven intensity
        statePulse = 0.9 + amplitude * 0.2;
        stateColor = mix(baseColor, glowColor, amplitude * 0.5);
      }

      // Mouth mask glow (speaking)
      float mouthGlow = 0.0;
      if (mouthGlowIntensity > 0.0) {
        vec4 maskSample = texture2D(mouthMask, vUv);
        mouthGlow = maskSample.r * mouthGlowIntensity * amplitude;
      }

      // Combine all effects
      vec3 color = stateColor;
      color += glowColor * fresnel * 0.5;
      color += mouthGlow * glowColor;
      color *= scanline * flicker * statePulse;
      color += n;

      // Alpha based on fresnel and state
      float alpha = 0.7 + fresnel * 0.3;
      alpha *= flicker;

      gl_FragColor = vec4(color, alpha);
    }
  `,
}

// The 3D model component
function AvatarModel({ state, amplitude }: AvatarDriverProps) {
  const groupRef = useRef<THREE.Group>(null)
  const materialRef = useRef<THREE.ShaderMaterial | null>(null)

  // Load the GLB model
  const { scene } = useGLTF('/assets/models/aistein/aistein_low.glb')

  // Load mouth mask texture
  const mouthMaskTexture = useTexture('/assets/models/aistein/aistein_mouth_mask.png')

  // Clone the scene to avoid modifying the cached version
  const clonedScene = useMemo(() => {
    const clone = scene.clone(true)

    // Compute vertex normals if they look flat
    clone.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        if (child.geometry) {
          child.geometry.computeVertexNormals()
        }
      }
    })

    return clone
  }, [scene])

  // Create shader material
  const shaderMaterial = useMemo(() => {
    const mat = new THREE.ShaderMaterial({
      uniforms: { ...HologramShaderMaterial.uniforms },
      vertexShader: HologramShaderMaterial.vertexShader,
      fragmentShader: HologramShaderMaterial.fragmentShader,
      transparent: true,
      side: THREE.DoubleSide,
      depthWrite: false,
    })
    mat.uniforms.mouthMask.value = mouthMaskTexture
    return mat
  }, [mouthMaskTexture])

  // Apply material to all meshes in the scene
  useEffect(() => {
    clonedScene.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        child.material = shaderMaterial
      }
    })
    materialRef.current = shaderMaterial
  }, [clonedScene, shaderMaterial])

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
      const targetAmplitude = amplitude
      uniforms.amplitude.value += (targetAmplitude - uniforms.amplitude.value) * 0.1
      uniforms.mouthGlowIntensity.value = state === 'speaking' ? 1.5 : 0.0

      // Random glitch effect
      if (Math.random() > 0.995) {
        uniforms.glitchIntensity.value = 0.02
      } else {
        uniforms.glitchIntensity.value *= 0.9
      }
    }

    // Subtle floating animation
    if (groupRef.current) {
      groupRef.current.position.y = Math.sin(Date.now() * 0.001) * 0.05
      groupRef.current.rotation.y += delta * 0.1
    }
  })

  return (
    <group ref={groupRef}>
      <primitive object={clonedScene} scale={1.5} position={[0, -1.2, 0]} />
    </group>
  )
}

// Debug overlay to show mouth mask alignment
function DebugMouthMaskOverlay() {
  const texture = useTexture('/assets/models/aistein/aistein_mouth_mask.png')

  return (
    <mesh position={[0, 0, 1]}>
      <planeGeometry args={[2, 2]} />
      <meshBasicMaterial map={texture} transparent opacity={0.3} />
    </mesh>
  )
}

// Scene setup with lighting and effects
function Scene({ state, amplitude }: AvatarDriverProps) {
  const { gl } = useThree()

  useEffect(() => {
    gl.setClearColor(0x000000, 0)
  }, [gl])

  return (
    <>
      {/* Ambient light for base visibility */}
      <ambientLight intensity={0.2} color={0x00ff88} />

      {/* Point lights for hologram effect */}
      <pointLight position={[0, 2, 2]} intensity={0.5} color={0x00ffcc} />
      <pointLight position={[0, -2, -2]} intensity={0.3} color={0x00ff88} />

      {/* The avatar model */}
      <AvatarModel state={state} amplitude={amplitude} />

      {/* Debug overlay */}
      {DEBUG_ENABLED && <DebugMouthMaskOverlay />}
    </>
  )
}

// Error boundary fallback
function WebGLFallback() {
  return (
    <div className="flex items-center justify-center h-full text-matrix-cyan text-sm">
      <p>WebGL not available. Hologram disabled.</p>
    </div>
  )
}

// Main exported component
interface HologramAvatar3DProps {
  state?: AvatarState
  amplitude?: number
  className?: string
}

export function HologramAvatar3D({
  state = 'idle',
  amplitude = 0,
  className = '',
}: HologramAvatar3DProps) {
  const [webglSupported, setWebglSupported] = useState(true)
  const [isClient, setIsClient] = useState(false)

  // Check for WebGL support
  useEffect(() => {
    setIsClient(true)
    try {
      const canvas = document.createElement('canvas')
      const hasWebGL = !!(
        window.WebGLRenderingContext &&
        (canvas.getContext('webgl') || canvas.getContext('experimental-webgl'))
      )
      setWebglSupported(hasWebGL)
    } catch {
      setWebglSupported(false)
    }
  }, [])

  // Server-side rendering placeholder
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

  // WebGL not supported fallback
  if (!webglSupported) {
    return <WebGLFallback />
  }

  return (
    <div className={`hologram-container relative ${className}`}>
      <Canvas
        camera={{ position: [0, 0, 3], fov: 50 }}
        gl={{ alpha: true, antialias: true }}
        style={{ background: 'transparent' }}
      >
        <Scene state={state} amplitude={amplitude} />
      </Canvas>

      {/* State indicator (debug) */}
      {DEBUG_ENABLED && (
        <div className="absolute top-2 left-2 text-xs text-matrix-cyan bg-black/50 px-2 py-1 rounded">
          State: {state} | Amp: {amplitude.toFixed(2)}
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

// Preload assets
useGLTF.preload('/assets/models/aistein/aistein_low.glb')
