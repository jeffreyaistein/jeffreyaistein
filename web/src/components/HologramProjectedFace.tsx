'use client'

import { useRef, useEffect, useState, useMemo } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useGLTF, useTexture } from '@react-three/drei'
import * as THREE from 'three'

import type { AvatarState } from '@/components/HologramAvatar3D'

// Debug mode from environment
const DEBUG_ENABLED = process.env.NEXT_PUBLIC_AVATAR_DEBUG === 'true'

// Default face alignment settings (object space projection)
// Calibrated values from debug session - face aligned on mesh
const DEFAULT_SETTINGS = {
  faceScale: 0.25,       // Calibrated: mesh coords ~4x texture size
  faceOffsetX: -0.05,    // Calibrated: slight left shift
  faceOffsetY: 0.0,      // Calibrated: centered vertically
  flipX: 0.0,            // 0 = no flip, 1 = flip horizontally
  flipY: 0.0,            // 0 = no flip, 1 = flip vertically
  frontFadeStrength: 2.0, // How quickly face fades on sides (higher = sharper)
  mouthIntensity: 1.5,
  scanlineIntensity: 0.0, // Default off
  noiseIntensity: 0.0,    // Default off
}

// Projected Face Shader - projects face texture onto mesh using OBJECT SPACE
// This ensures the face stays locked to the mesh regardless of float/rotation animation
const ProjectedFaceShader = {
  uniforms: {
    time: { value: 0 },
    faceTexture: { value: null as THREE.Texture | null },
    mouthMask: { value: null as THREE.Texture | null },
    // Face alignment controls (object space)
    faceScale: { value: DEFAULT_SETTINGS.faceScale },
    faceOffsetX: { value: DEFAULT_SETTINGS.faceOffsetX },
    faceOffsetY: { value: DEFAULT_SETTINGS.faceOffsetY },
    flipX: { value: DEFAULT_SETTINGS.flipX },
    flipY: { value: DEFAULT_SETTINGS.flipY },
    // Front fade
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
    varying vec3 vObjPos;      // Object space position - stays fixed to mesh
    varying vec3 vObjNormal;   // Object space normal - for front-facing check

    void main() {
      vUv = uv;

      // Object space position - this is the key to preventing drift
      // position is already in object/local space
      vObjPos = position;

      // Object space normal (before any transforms)
      vObjNormal = normal;

      // Transform normal to view space for lighting (still needed for some effects)
      vNormal = normalize(normalMatrix * normal);

      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: `
    uniform float time;
    uniform sampler2D faceTexture;
    uniform sampler2D mouthMask;
    uniform float faceScale;
    uniform float faceOffsetX;
    uniform float faceOffsetY;
    uniform float flipX;
    uniform float flipY;
    uniform float frontFadeStrength;
    uniform float scanlineIntensity;
    uniform float noiseIntensity;
    uniform float avatarState;
    uniform float amplitude;
    uniform float mouthIntensity;

    varying vec2 vUv;
    varying vec3 vNormal;
    varying vec3 vObjPos;
    varying vec3 vObjNormal;

    // Noise function
    float noise(vec2 p) {
      return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
    }

    void main() {
      // Front-facing check using OBJECT SPACE normal
      // We want to fade out faces that point sideways or backwards in object space
      // In object space, "front" is typically -Z or +Z depending on model orientation
      // The model faces +Z in object space, so front normal should have positive Z
      float frontFacing = vObjNormal.z;

      // Apply fade strength - higher values = sharper cutoff on sides
      float fadeAlpha = pow(max(frontFacing, 0.0), frontFadeStrength);

      // Discard back-facing and heavily side-facing fragments
      if (fadeAlpha < 0.01) {
        discard;
      }

      // Calculate UV from OBJECT SPACE position
      // This maps the face texture based on the mesh's local X and Y coordinates
      // The face texture will be "painted" onto the mesh and stay locked to it
      vec2 faceUV;
      faceUV.x = vObjPos.x;
      faceUV.y = vObjPos.y;

      // Apply scale (larger scale = smaller face on mesh)
      faceUV = faceUV * faceScale;

      // Center the UV and apply offset
      faceUV = faceUV + 0.5;
      faceUV.x += faceOffsetX;
      faceUV.y += faceOffsetY;

      // Apply flip if needed
      if (flipX > 0.5) {
        faceUV.x = 1.0 - faceUV.x;
      }
      if (flipY > 0.5) {
        faceUV.y = 1.0 - faceUV.y;
      }

      // Clamp to avoid wrapping
      faceUV = clamp(faceUV, 0.0, 1.0);

      // Sample face texture
      vec4 faceColor = texture2D(faceTexture, faceUV);

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
        vec4 maskSample = texture2D(mouthMask, faceUV);
        mouthGlow = maskSample.r * mouthIntensity * amplitude;

        // Add brightness/distortion to mouth region
        color += vec3(mouthGlow * 0.3, mouthGlow * 0.2, mouthGlow * 0.1);

        // Subtle distortion in mouth area
        float distortion = sin(time * 20.0 + faceUV.y * 50.0) * 0.01 * amplitude * maskSample.r;
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

      // Optional scanlines (default off) - use object space Y for consistency
      if (scanlineIntensity > 0.0) {
        float scanline = sin(vObjPos.y * 100.0 + time * 2.0) * 0.5 + 0.5;
        scanline = mix(1.0, scanline, scanlineIntensity);
        color *= scanline;
      }

      // Optional noise (default off)
      if (noiseIntensity > 0.0) {
        float n = noise(faceUV * 100.0 + time * 5.0) * noiseIntensity;
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
      uniforms.faceScale.value = settings.faceScale
      uniforms.faceOffsetX.value = settings.faceOffsetX
      uniforms.faceOffsetY.value = settings.faceOffsetY
      uniforms.flipX.value = settings.flipX
      uniforms.flipY.value = settings.flipY
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
  selectedParam,
  state,
  amplitude,
}: {
  settings: typeof DEFAULT_SETTINGS
  selectedParam: number
  state: AvatarState
  amplitude: number
}) {
  const paramNames: (keyof typeof DEFAULT_SETTINGS)[] = [
    'faceScale',
    'faceOffsetX',
    'faceOffsetY',
    'flipX',
    'flipY',
    'frontFadeStrength',
    'mouthIntensity',
    'scanlineIntensity',
    'noiseIntensity',
  ]

  return (
    <div className="absolute top-2 left-2 text-xs text-white bg-black/70 px-3 py-2 rounded space-y-1 font-mono">
      <div className="text-cyan-400 font-bold mb-2">PROJECTED_FACE (Object Space)</div>
      <div>State: {state} | Amp: {amplitude.toFixed(2)}</div>
      <div className="border-t border-gray-600 my-2" />

      <div className="space-y-1">
        {paramNames.map((name, idx) => (
          <div key={name} className={`flex justify-between ${selectedParam === idx ? 'text-yellow-300' : ''}`}>
            <span>{idx + 1}. {name}:</span>
            <span className={selectedParam === idx ? 'text-yellow-300' : 'text-cyan-300'}>
              {settings[name].toFixed(2)}
            </span>
          </div>
        ))}
      </div>

      <div className="border-t border-gray-600 my-2" />
      <div className="text-[10px] text-gray-500">
        <div>1-9: select param | Arrows: adjust</div>
        <div>Shift: fine (0.01) | R: reset | F: toggle flip</div>
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
      'faceScale',
      'faceOffsetX',
      'faceOffsetY',
      'flipX',
      'flipY',
      'frontFadeStrength',
      'mouthIntensity',
      'scanlineIntensity',
      'noiseIntensity',
    ]

    const handleKeyDown = (e: KeyboardEvent) => {
      const step = e.shiftKey ? 0.01 : 0.05
      const key = paramKeys[selectedParam]

      switch (e.key) {
        case '1': case '2': case '3': case '4': case '5': case '6': case '7': case '8': case '9':
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
        case 'f':
        case 'F':
          // Toggle flip for flipX/flipY parameters
          if (key === 'flipX' || key === 'flipY') {
            setSettings(prev => ({
              ...prev,
              [key]: prev[key] > 0.5 ? 0.0 : 1.0,
            }))
          }
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
          selectedParam={selectedParam}
          state={state}
          amplitude={amplitude}
        />
      )}
    </div>
  )
}

// Preload assets
useGLTF.preload('/assets/models/aistein/aistein_low.glb')
