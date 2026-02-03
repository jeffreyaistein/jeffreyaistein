# Text-to-Speech Setup Guide

Jeffrey AIstein uses ElevenLabs for text-to-speech synthesis.

## Prerequisites

- ElevenLabs account with API access (paid plan required for API voice usage)
- Fly.io deployment for backend API

## Configuration

### 1. Create ElevenLabs API Key

1. Go to [ElevenLabs](https://elevenlabs.io) and sign in
2. Navigate to **Profile** > **API Keys**
3. Click **Create API Key**
4. Give it a name (e.g., "Jeffrey AIstein Production")
5. Copy the key immediately (it won't be shown again)

### 2. Select a Voice

1. Go to **Voices** in ElevenLabs dashboard
2. Browse the Voice Library or use your own cloned voice
3. Click on a voice to see its details
4. Copy the **Voice ID** from the URL or voice details

**Recommended voices for Jeffrey AIstein:**
- Scary/dramatic male voices work well for the AI character
- Example: "Calen Voss" - deep, authoritative male voice

### 3. Set Backend Secrets (Fly.io)

```bash
cd apps
fly secrets set ELEVENLABS_API_KEY="your-api-key-here"
fly secrets set ELEVENLABS_VOICE_ID="your-voice-id-here"
fly secrets set ENABLE_TTS="true"
```

Optional settings (with defaults):
```bash
fly secrets set ELEVENLABS_MODEL_ID="eleven_monolingual_v1"
fly secrets set ELEVENLABS_OUTPUT_FORMAT="mp3_44100_128"
fly secrets set TTS_MAX_TEXT_LENGTH="1000"
fly secrets set TTS_RATE_LIMIT_PER_MINUTE="10"
```

### 4. Deploy Backend

```bash
cd apps
fly deploy
```

### 5. Verify TTS is Working

```bash
# Check TTS status endpoint
curl https://your-app.fly.dev/api/tts/status

# Should return:
# {"enabled": true, "provider": "elevenlabs", "voice_id": "S44KQ3oL..."}

# Test TTS endpoint
curl -X POST https://your-app.fly.dev/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, I am Jeffrey AIstein."}' \
  --output test.mp3

# Play test.mp3 to verify audio
```

## Frontend Usage

The frontend automatically uses TTS when:
1. User clicks the **Voice Off** button to enable voice
2. Assistant message completes streaming
3. TTS fetches audio from `/api/tts` and plays it
4. Avatar amplitude is driven by real audio analysis

### Voice Toggle

- Voice is **OFF by default** (satisfies browser autoplay policies)
- User must click to enable voice
- Toggle appears next to the connection status indicator

## Configuration Reference

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `ELEVENLABS_API_KEY` | (required) | Your ElevenLabs API key |
| `ELEVENLABS_VOICE_ID` | (required) | Voice ID to use |
| `ENABLE_TTS` | `false` | Enable/disable TTS feature |
| `ELEVENLABS_MODEL_ID` | `eleven_monolingual_v1` | TTS model |
| `ELEVENLABS_OUTPUT_FORMAT` | `mp3_44100_128` | Audio format |
| `TTS_MAX_TEXT_LENGTH` | `1000` | Max characters per request |
| `TTS_RATE_LIMIT_PER_MINUTE` | `10` | Rate limit per IP |

## Troubleshooting

### "Free users cannot use library voices via the API"

This error means you need a paid ElevenLabs subscription. Library voices (pre-made voices) require at least the Starter plan for API access.

### TTS Error in Frontend

1. Check browser console for detailed error
2. Verify backend is deployed with correct secrets
3. Test `/api/tts/status` endpoint
4. Ensure CORS is configured for your frontend domain

### Audio Not Playing

1. Check that voice is enabled (toggle should show "Voice On")
2. Verify no browser autoplay restrictions
3. Check network tab for TTS request/response

### Rate Limited

TTS has a rate limit of 10 requests per minute per IP. If you see 429 errors, wait a minute before retrying.

## Architecture

```
Frontend                          Backend (Fly.io)
   |                                   |
   |  POST /api/tts {text}            |
   |--------------------------------->|
   |                                   |
   |                            ElevenLabs API
   |                                   |
   |  audio/mpeg (MP3 bytes)          |
   |<---------------------------------|
   |                                   |
   | WebAudio analysis                 |
   | -> amplitude for avatar           |
```

## Files

| File | Description |
|------|-------------|
| `apps/api/services/tts.py` | ElevenLabs TTS client |
| `apps/api/main.py` | `/api/tts` endpoint |
| `apps/api/config.py` | TTS configuration |
| `apps/web/src/hooks/useTTS.ts` | Frontend TTS hook |
| `apps/web/src/components/ChatInterface.tsx` | Voice toggle UI |
| `apps/web/src/hooks/useAvatarDriver.ts` | Audio amplitude analysis |
