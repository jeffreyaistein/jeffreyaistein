# Avatar Mode Configuration

Jeffrey AIstein supports three avatar rendering modes that can be switched via environment variable.

## Avatar Modes

### GLB Mode (Default)

Full 3D GLB model with green hologram shader effects.

- **File**: `HologramAvatar3D.tsx`
- **Model**: `/assets/models/aistein/aistein_low.glb` (724KB)
- **Mouth Mask**: `/assets/models/aistein/aistein_mouth_mask.png` (15KB)

Features:
- Full 3D model rotation and floating animation
- Fresnel edge glow
- Scanlines and noise overlay
- Chromatic aberration
- Mouth mask speaking animation driven by amplitude
- Green hologram tint

### Card Mode

2.5D card/plane avatar using a face texture with hologram effects.

- **File**: `HologramCardAvatar.tsx`
- **Face Texture**: `/assets/models/aistein/aistein_face.png` (903KB)
- **Mouth Mask**: `/assets/models/aistein/aistein_face_mouth_mask.png` (9.6KB)

Features:
- 2D plane with face texture
- Same hologram effects as GLB (scanlines, noise, flicker, chromatic aberration)
- Lighter weight rendering
- Mouth mask glow effect during speaking
- Debug overlay for mask alignment

### Projected Face Mode

Face PNG projected onto the 3D GLB mesh surface (no hologram tint).

- **File**: `HologramProjectedFace.tsx`
- **Model**: `/assets/models/aistein/aistein_low.glb` (724KB)
- **Face Texture**: `/assets/models/aistein/aistein_face.png` (903KB)
- **Mouth Mask**: `/assets/models/aistein/aistein_face_mouth_mask.png` (9.6KB)

Features:
- Face texture projected from camera view onto 3D mesh
- Natural face colors (no green hologram tint)
- Front-facing fade: projection strongest on front, fades on sides/back
- Mouth mask projection for speaking animation (brightness/distortion in mouth region)
- Optional scanlines and noise (default off)
- Debug controls for projection tuning

## Configuration

Set the `NEXT_PUBLIC_AVATAR_MODE` environment variable:

```bash
# Use GLB mode (default) - green hologram
NEXT_PUBLIC_AVATAR_MODE=glb

# Use Card mode - 2.5D hologram
NEXT_PUBLIC_AVATAR_MODE=card

# Use Projected Face mode - face on 3D mesh
NEXT_PUBLIC_AVATAR_MODE=projected_face
```

### Local Development

Add to `.env.local`:

```
NEXT_PUBLIC_AVATAR_MODE=card
```

### Vercel Production

Set in Vercel Project Settings > Environment Variables:

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_AVATAR_MODE` | `glb` or `card` |

**Note:** This is a build-time variable. Changes require a redeploy.

## Debug Mode

Enable debug overlay to see avatar state and mask alignment controls:

```bash
NEXT_PUBLIC_AVATAR_DEBUG=true
```

### Card Mode Debug Controls

When debug mode is enabled in card mode, keyboard controls are available:

| Key | Action |
|-----|--------|
| Arrow Left/Right | Adjust mask X offset |
| Arrow Up/Down | Adjust mask Y offset |
| `+` / `=` | Increase mask scale |
| `-` | Decrease mask scale |
| Shift + Arrow | Fine adjustment (0.01 instead of 0.05) |

Mask offset values are logged to console for baking into the shader.

### Projected Face Debug Controls

When debug mode is enabled in projected_face mode, keyboard controls are available:

| Key | Action |
|-----|--------|
| `1` | Select projectionScale |
| `2` | Select projectionOffsetX |
| `3` | Select projectionOffsetY |
| `4` | Select frontFadeStrength |
| `5` | Select mouthIntensity |
| `6` | Select scanlineIntensity |
| `7` | Select noiseIntensity |
| Arrow Up/Right | Increase selected parameter |
| Arrow Down/Left | Decrease selected parameter |
| Shift + Arrow | Fine adjustment (0.01 instead of 0.05) |
| `R` | Reset all parameters to defaults |

**Default Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| projectionScale | 0.85 | Scale of the projected texture |
| projectionOffsetX | 0.0 | Horizontal offset |
| projectionOffsetY | 0.15 | Vertical offset |
| frontFadeStrength | 2.5 | How quickly projection fades on sides (higher = sharper) |
| mouthIntensity | 1.5 | Brightness boost in mouth region when speaking |
| scanlineIntensity | 0.0 | Scanline effect strength (0 = off) |
| noiseIntensity | 0.0 | Noise overlay strength (0 = off) |

Parameter values are logged to console for baking into the shader.

## Avatar States

Both modes support the same avatar states:

| State | Description | Visual Effect |
|-------|-------------|---------------|
| `idle` | No activity | Subtle green glow |
| `listening` | User sent message | Cyan pulse |
| `thinking` | Assistant streaming | Faster cyan pulse |
| `speaking` | TTS playing | Amplitude-driven glow + mouth animation |

## Component Architecture

```
ChatInterface.tsx
  └── HologramSection
        └── HologramAvatar (mode switcher)
              ├── HologramAvatar3D (when mode=glb)
              └── HologramCardAvatar (when mode=card)
```

The `HologramAvatar` component reads `NEXT_PUBLIC_AVATAR_MODE` and renders the appropriate avatar component.

## Files

| File | Description |
|------|-------------|
| `src/components/HologramAvatar.tsx` | Mode switcher component |
| `src/components/HologramAvatar3D.tsx` | GLB 3D avatar (green hologram) |
| `src/components/HologramCardAvatar.tsx` | Card 2.5D avatar |
| `src/components/HologramProjectedFace.tsx` | Projected face on 3D mesh |
| `src/hooks/useAvatarDriver.ts` | State driver + audio analysis |
| `public/assets/models/aistein/` | Avatar assets |

## Switching Between Modes

1. Update `NEXT_PUBLIC_AVATAR_MODE` environment variable
2. Rebuild the application (`npm run build`)
3. Deploy

The mode is determined at build time, so hot-reloading won't switch modes during development. Restart the dev server after changing the env var.
