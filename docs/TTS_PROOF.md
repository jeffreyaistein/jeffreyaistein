# TTS Audio Playback Verification

## Vercel Environment Setup

### Enable Debug Mode

1. Go to Vercel dashboard > jeffreyaistein project > Settings > Environment Variables
2. Add or update:
   ```
   NEXT_PUBLIC_DEBUG=true
   ```
3. Redeploy the project (Deployments > Redeploy)

### Required Environment Variables

| Variable | Value | Description |
|----------|-------|-------------|
| `NEXT_PUBLIC_API_BASE_URL` | `https://jeffreyaistein.fly.dev` | Backend API URL |
| `NEXT_PUBLIC_DEBUG` | `true` (for testing) | Show debug panel |

## Verification Steps

### Step 1: Open the Site

1. Navigate to https://jeffreyaistein.vercel.app
2. Open browser DevTools (F12) > Console tab
3. Verify debug panel appears in bottom-right corner

### Step 2: Enable Voice

1. Click the **Voice Off** button (bottom of chat area)
2. Button should change to **Voice On** with cyan styling
3. In Debug Panel, verify:
   - `voiceEnabled: true`
   - `audioContextState: running`
4. In Console, verify:
   ```
   [useTTS] setVoiceEnabled: true
   [useTTS] Created AudioContext, state: running
   [useTTS] AudioContext resumed, state: running
   ```

### Step 3: Send a Message

1. Type a message and press Enter (e.g., "Hello, who are you?")
2. Wait for assistant response to complete streaming

### Step 4: Verify TTS Fetch

1. In Console, verify:
   ```
   [useTTS] Fetching from: https://jeffreyaistein.fly.dev/api/tts
   [useTTS] Response status: 200
   [useTTS] Received audio blob: XXXXX bytes, type: audio/mpeg
   ```
2. In Debug Panel, verify:
   - `lastHttpStatus: 200`
   - `lastBytes: XXXXX` (should be > 10000)

### Step 5: Verify Audio Playback

1. Audio should play automatically after TTS fetch
2. In Console, verify:
   ```
   [useTTS] Audio play() succeeded
   ```
3. In Debug Panel, verify:
   - `lastPlayError: (none)`
   - Amplitude bar should animate during playback
   - `amplitude: 0.XXX` should show non-zero values

### Step 6: Verify Avatar Animation

1. While audio plays, watch the hologram avatar
2. Mouth mask should animate in sync with audio amplitude
3. Avatar state should be "speaking" during playback
4. After audio ends:
   - `lastAudioEnded: true`
   - Avatar returns to idle state

## Troubleshooting

### Audio Not Playing

**Check Debug Panel:**
- If `lastHttpStatus: null` - TTS request failed to send
- If `lastHttpStatus: 4XX/5XX` - Backend error, check Fly.io logs
- If `lastPlayError: NotAllowedError` - Need user gesture, click Voice button again
- If `lastPlayError: NotSupportedError` - Audio format issue

**Check Console:**
```
[useTTS] play() error: <ErrorName> <ErrorMessage>
```

### AudioContext Suspended

If `audioContextState: suspended`:
1. User must click Enable Voice button
2. Check if browser is blocking autoplay
3. Try refreshing and re-enabling voice

### No Amplitude

If amplitude stays at 0:
1. Check `[useTTS] Audio analyser connected` in console
2. Verify audio is actually playing (can you hear it?)
3. Check if CORS headers allow audio analysis

## After Verification

1. Set `NEXT_PUBLIC_DEBUG=false` in Vercel
2. Redeploy to hide debug panel in production

## Files Modified

| File | Changes |
|------|---------|
| `web/src/hooks/useTTS.ts` | Voice enable gate, AudioContext, AnalyserNode, debug info |
| `web/src/components/ChatInterface.tsx` | TTS integration, amplitude pass-through |
| `web/src/components/DebugPanel.tsx` | TTS debug section |

## Commits

- `6c064fc` - Add voice enable gate with AudioContext resume
- `4ad9b4b` - Add TTS debug info and improved error handling
- `45babbe` - Drive hologram amplitude from real TTS audio
- `f0b56b6` - Add TTS debug instrumentation
