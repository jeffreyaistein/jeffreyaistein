'use client'

import { useRef, useEffect, useState, useMemo } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useGLTF, useTexture } from '@react-three/drei'
import * as THREE from 'three'

import type { AvatarState } from '@/components/HologramAvatar3D'

// Debug mode from environment
const DEBUG_ENABLED = process.env.NEXT_PUBLIC_AVATAR_DEBUG === 'true'

// Default projection settings
const DEFAULT_SETTINGS = {
  projectionScale: 0.85,
  projectionOffsetX: 0.0,
  projectionOffsetY: 0.15,
  frontFadeStrength: 2.5,
  mouthIntensity: 1.5,
  scanlineIntensity: 0.0, // Default off
  noiseIntensity: 0.0, // Default off
}

// Projected Face Shader - projects face texture from front onto mesh
const ProjectedFaceShader = {
  uniforms: {
    time: { value: 0 },
    faceTexture: { value: null as THREE.Texture | null },
    mouthMask: { value: null as THREE.Texture | null },
    // Projection controls
    projectionScale: { value: DEFAULT_SETTINGS.projectionScale },
    projectionOffsetX: { value: DEFAULT_SETTINGS.projectionOffsetX },
    projectionOffsetY: { value: DEFAULT_SETTINGS.projectionOffsetY },
    frontFadeStrength: { value: DEFAULT_SETTINGS.frontFadeStrength },
    // Effects
    scanlineIntensity: { value: DEFAULT_SETTINGS.scanlineIntensity },
    noiseIntensity: { value: DEFAULT_SETTINGS.noiseIntensity },
    // Avatar state
    avatarState: { value: 0 },
    amplitude: { value: 0.0 },
    mouthIntensity: { value: DEFAULT_SETTINGS.mouthIntensity },
  },
  vertexShader: `
    varying vec2 vUv;
    varying vec3 vNormal;
    varying vec3 vPosition;
    varying vec3 vWorldPosition;
    varying vec4 vProjectedPos;

    void main() {
      vUv = uv;
      vNormal = normalize(normalMatrix * normal);
      vPosition = position;

      vec4 worldPos = modelMatrix * vec4(position, 1.0);
      vWorldPosition = worldPos.xyz;

      // Pass projected position for front projection calculation
      vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
      vProjectedPos = projectionMatrix * mvPosition;

      gl_Position = vProjectedPos;
    }
  `,
  fragmentShader: `
    uniform float time;
    uniform sampler2D faceTexture;
    uniform sampler2D mouthMask;
    uniform float projectionScale;
    uniform float projectionOffsetX;
    uniform float projectionOffsetY;
    uniform float frontFadeStrength;
    uniform float scanlineIntensity;
    uniform float noiseIntensity;
    uniform float avatarState;
    uniform float amplitude;
    uniform float mouthIntensity;

    varying vec2 vUv;
    varying vec3 vNormal;
    varying vec3 vPosition;
    varying vec3 vWorldPosition;
    varying vec4 vProjectedPos;

    // Noise function
    float noise(vec2 p) {
      return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
    }

    void main() {
      // Calculate view direction
      vec3 viewDir = normalize(cameraPosition - vWorldPosition);

      // Front-facing factor: how much the surface faces the camera
      // 1.0 = directly facing, 0.0 = perpendicular, negative = facing away
      float frontFacing = dot(vNormal, viewDir);

      // Apply fade strength - higher values = sharper cutoff on sides
      float fadeAlpha = pow(max(frontFacing, 0.0), frontFadeStrength);

      // Discard back-facing and heavily side-facing fragments
      if (fadeAlpha < 0.01) {
        discard;
      }

      // Calculate projected UV coordinates (front projection like a projector)
      // Use clip space position, convert from [-1,1] to [0,1]
      vec2 projectedUV = vProjectedPos.xy / vProjectedPos.w;
      projectedUV = projectedUV * 0.5 + 0.5;

      // Apply scale and offset
      projectedUV = (projectedUV - 0.5) / projectionScale + 0.5;
      projectedUV.x += projectionOffsetX;
      projectedUV.y += projectionOffsetY;

      // Clamp to avoid wrapping
      projectedUV = clamp(projectedUV, 0.0, 1.0);

      // Sample face texture
      vec4 faceColor = texture2D(faceTexture, projectedUV);

      // If outside texture or transparent, fade out
      if (faceColor.a < 0.1) {
        discard;
      }

      // Start with face color (no green tint)
      vec3 color = faceColor.rgb;

      // Mouth mask for speaking animation
      float mouthGlow = 0.0;
      if (avatarState > 2.5 && amplitude > 0.0) {
        // Speaking state
        vec4 maskSample = texture2D(mouthMask, projectedUV);
        mouthGlow = maskSample.r * mouthIntensity * amplitude;

        // Add brightness/distortion to mouth region
        color += vec3(mouthGlow * 0.3, mouthGlow * 0.2, mouthGlow * 0.1);

        // Subtle distortion in mouth area
        float distortion = sin(time * 20.0 + projectedUV.y * 50.0) * 0.01 * amplitude * maskSample.r;
        color += vec3(distortion);
      }

      // State-based subtle effects
      float statePulse = 1.0;
      if (avatarState > 0.5 && avatarState < 1.5) {
        // Listening - very subtle pulse
        statePulse = 0.95 + 0.05 * sin(time * 3.0);
      } else if (avatarState > 1.5 && avatarState < 2.5) {
        // Thinking - slightly more noticeable
        statePulse = 0.92 + 0.08 * sin(time * 5.0);
      } else if (avatarState > 2.5) {
        // Speaking - amplitude-driven
        statePulse = 0.95 + amplitude * 0.1;
      }

      color *= statePulse;

      // Optional scanlines (default off)
      if (scanlineIntensity > 0.0) {
        float scanline = sin(vWorldPosition.y * 100.0 + time * 2.0) * 0.5 + 0.5;
        scanline = mix(1.0, scanline, scanlineIntensity);
        color *= scanline;
      }

      // Optional noise (default off)
      if (noiseIntensity > 0.0) {
        float n = noise(projectedUV * 100.0 + time * 5.0) * noiseIntensity;
        color += vec3(n * 0.5);
      }

      // Final alpha: combine face alpha with fade
      float alpha = faceColor.a * fadeAlpha;

      gl_FragColor = vec4(color, alpha);
    }
  `,
}

// Props interface
interface ProjectedFaceProps {
  state: AvatarState
  amplitude: number
  settings: typeof DEFAULT_SETTINGS
}

// The 3D model with projected face
function ProjectedFaceModel({ state, amplitude, settings }: ProjectedFaceProps) {
  const groupRef = useRef<THREE.Group>(null)
  const materialRef = useRef<THREE.ShaderMaterial | null>(null)

  // Load the GLB model
  const { scene } = useGLTF('/assets/models/aistein/aistein_low.glb')

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

  // Clone the scene
  const clonedScene = useMemo(() => {
    const clone = scene.clone(true)
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
      uniforms: { ...ProjectedFaceShader.uniforms },
      vertexShader: ProjectedFaceShader.vertexShader,
      fragmentShader: ProjectedFaceShader.fragmentShader,
      transparent: true,
      side: THREE.FrontSide,
      depthWrite: true,
    })
    mat.uniforms.faceTexture.value = faceTexture
    mat.uniforms.mouthMask.value = mouthMaskTexture
    return mat
  }, [faceTexture, mouthMaskTexture])

  // Apply material to all meshes
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

  // Update uniforms from settings
  useEffect(() => {
    if (materialRef.current) {
      const uniforms = materialRef.current.uniforms
      uniforms.projectionScale.value = settings.projectionScale
      uniforms.projectionOffsetX.value = settings.projectionOffsetX
      uniforms.projectionOffsetY.value = settings.projectionOffsetY
      uniforms.frontFadeStrength.value = settings.frontFadeStrength
      uniforms.mouthIntensity.value = settings.mouthIntensity
      uniforms.scanlineIntensity.value = settings.scanlineIntensity
      uniforms.noiseIntensity.value = settings.noiseIntensity
    }
  }, [settings])

  // Animation loop
  useFrame((_, delta) => {
    if (materialRef.current) {
      const uniforms = materialRef.current.uniforms
      uniforms.time.value += delta
      uniforms.avatarState.value = stateValue

      // Smooth amplitude interpolation
      uniforms.amplitude.value += (amplitude - uniforms.amplitude.value) * 0.15
    }

    // Subtle floating animation
    if (groupRef.current) {
      const time = Date.now() * 0.001
      groupRef.current.position.y = Math.sin(time * 0.8) * 0.03
      // Very subtle rotation
      groupRef.current.rotation.y = Math.sin(time * 0.3) * 0.05
    }
  })

  return (
    <group ref={groupRef}>
      <primitive object={clonedScene} scale={1.5} position={[0, -1.2, 0]} />
    </group>
  )
}

// Scene setup
function ProjectedFaceScene({ state, amplitude, settings }: ProjectedFaceProps) {
  const { gl } = useThree()

  useEffect(() => {
    gl.setClearColor(0x000000, 0)
  }, [gl])

  return (
    <>
      {/* Subtle ambient light */}
      <ambientLight intensity={0.8} />

      {/* Front light to illuminate the face */}
      <directionalLight position={[0, 0, 5]} intensity={0.5} />

      {/* The avatar model */}
      <ProjectedFaceModel state={state} amplitude={amplitude} settings={settings} />
    </>
  )
}

// Debug controls panel
function DebugControls({
  settings,
  onSettingsChange,
  state,
  amplitude,
}: {
  settings: typeof DEFAULT_SETTINGS
  onSettingsChange: (settings: typeof DEFAULT_SETTINGS) => void
  state: AvatarState
  amplitude: number
}) {
  const handleChange = (key: keyof typeof DEFAULT_SETTINGS, delta: number) => {
    onSettingsChange({
      ...settings,
      [key]: Math.round((settings[key] + delta) * 100) / 100,
    })
  }

  return (
    <div className="absolute top-2 left-2 text-xs text-white bg-black/70 px-3 py-2 rounded space-y-1 font-mono">
      <div className="text-cyan-400 font-bold mb-2">PROJECTED_FACE Debug</div>
      <div>State: {state} | Amp: {amplitude.toFixed(2)}</div>
      <div className="border-t border-gray-600 my-2" />
      <div className="text-gray-400 text-[10px] mb-1">Arrow keys adjust selected, +/- for scale</div>

      <div className="space-y-1">
        <div className="flex justify-between">
          <span>projScale:</span>
          <span className="text-cyan-300">{settings.projectionScale.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span>projOffsetX:</span>
          <span className="text-cyan-300">{settings.projectionOffsetX.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span>projOffsetY:</span>
          <span className="text-cyan-300">{settings.projectionOffsetY.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span>frontFade:</span>
          <span className="text-cyan-300">{settings.frontFadeStrength.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span>mouthIntensity:</span>
          <span className="text-cyan-300">{settings.mouthIntensity.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span>scanlines:</span>
          <span className="text-cyan-300">{settings.scanlineIntensity.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span>noise:</span>
          <span className="text-cyan-300">{settings.noiseIntensity.toFixed(2)}</span>
        </div>
      </div>

      <div className="border-t border-gray-600 my-2" />
      <div className="text-[10px] text-gray-500">
        <div>1-7: select param | Arrows: adjust</div>
        <div>Shift: fine (0.01) | R: reset</div>
      </div>
    </div>
  )
}

// Main exported component
interface HologramProjectedFaceProps {
  state?: AvatarState
  amplitude?: number
  className?: string
}

export function HologramProjectedFace({
  state = 'idle',
  amplitude = 0,
  className = '',
}: HologramProjectedFaceProps) {
  const [isClient, setIsClient] = useState(false)
  const [settings, setSettings] = useState(DEFAULT_SETTINGS)
  const [selectedParam, setSelectedParam] = useState(0)

  useEffect(() => {
    setIsClient(true)
  }, [])

  // Keyboard controls for debug mode
  useEffect(() => {
    if (!DEBUG_ENABLED) return

    const paramKeys: (keyof typeof DEFAULT_SETTINGS)[] = [
      'projectionScale',
      'projectionOffsetX',
      'projectionOffsetY',
      'frontFadeStrength',
      'mouthIntensity',
      'scanlineIntensity',
      'noiseIntensity',
    ]

    const handleKeyDown = (e: KeyboardEvent) => {
      const step = e.shiftKey ? 0.01 : 0.05
      const key = paramKeys[selectedParam]

      switch (e.key) {
        case '1': case '2': case '3': case '4': case '5': case '6': case '7':
          setSelectedParam(parseInt(e.key) - 1)
          break
        case 'ArrowUp':
        case 'ArrowRight':
          setSettings(prev => ({
            ...prev,
            [key]: Math.round((prev[key] + step) * 100) / 100,
          }))
          break
        case 'ArrowDown':
        case 'ArrowLeft':
          setSettings(prev => ({
            ...prev,
            [key]: Math.round((prev[key] - step) * 100) / 100,
          }))
          break
        case 'r':
        case 'R':
          setSettings(DEFAULT_SETTINGS)
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [selectedParam])

  // Log settings changes for baking
  useEffect(() => {
    if (DEBUG_ENABLED) {
      console.log('[ProjectedFace] Settings:', settings)
    }
  }, [settings])

  if (!isClient) {
    return (
      <div className={`hologram-container ${className}`}>
        <div className="flex items-center justify-center h-full">
          <div className="text-cyan-400 text-xs animate-pulse">
            Initializing projection...
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
        <ProjectedFaceScene state={state} amplitude={amplitude} settings={settings} />
      </Canvas>

      {/* Debug controls */}
      {DEBUG_ENABLED && (
        <DebugControls
          settings={settings}
          onSettingsChange={setSettings}
          state={state}
          amplitude={amplitude}
        />
      )}
    </div>
  )
}

// Preload assets
useGLTF.preload('/assets/models/aistein/aistein_low.glb')
