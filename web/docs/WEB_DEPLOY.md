# Web App Deployment Guide

This document covers deploying the Jeffrey AIstein web app to Vercel.

## Prerequisites

- Node.js 18+
- npm or yarn
- Vercel account connected to GitHub
- API backend deployed (e.g., https://jeffreyaistein.fly.dev)

## Environment Variables

All environment variables must be set in Vercel (Settings > Environment Variables).

**Important:** These are build-time variables (prefixed with `NEXT_PUBLIC_`). Changes require a new deployment to take effect.

### Required Variables

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `NEXT_PUBLIC_API_BASE_URL` | Backend API base URL (single source of truth for REST + WebSocket) | `https://jeffreyaistein.fly.dev` |
| `NEXT_PUBLIC_CONTRACT_ADDRESS` | Solana token contract address | `69WBpgbrydCLSn3zyqAxzgrj2emGHLQJy9VdB1Xpump` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_SOLANA_EXPLORER_BASE_URL` | Base URL for Solana explorer | `https://solscan.io/token` |
| `NEXT_PUBLIC_DEBUG` | Enable chat debug panel | `false` |
| `NEXT_PUBLIC_AVATAR_DEBUG` | Enable hologram debug overlay | `false` |

## Vercel Deployment

### Initial Setup

1. **Connect GitHub Repository**
   - Go to [vercel.com](https://vercel.com)
   - Import project from GitHub
   - Select the repository

2. **Configure Build Settings**
   - Framework Preset: `Next.js`
   - Root Directory: `web` (important if using monorepo)
   - Build Command: `npm run build`
   - Output Directory: `.next`

3. **Set Environment Variables**
   ```
   NEXT_PUBLIC_API_BASE_URL=https://jeffreyaistein.fly.dev
   NEXT_PUBLIC_CONTRACT_ADDRESS=69WBpgbrydCLSn3zyqAxzgrj2emGHLQJy9VdB1Xpump
   NEXT_PUBLIC_SOLANA_EXPLORER_BASE_URL=https://solscan.io/token
   ```

4. **Deploy**
   - Click "Deploy"
   - Wait for build to complete

### Redeployment

After changing environment variables:
1. Go to Deployments tab
2. Click "..." on latest deployment
3. Select "Redeploy"

Or push a new commit to trigger automatic deployment.

## URL Computation

The web app computes URLs from `NEXT_PUBLIC_API_BASE_URL`:

| API Base URL | REST URL | WebSocket URL |
|--------------|----------|---------------|
| `https://jeffreyaistein.fly.dev` | `https://jeffreyaistein.fly.dev` | `wss://jeffreyaistein.fly.dev` |
| `http://localhost:8000` | `http://localhost:8000` | `ws://localhost:8000` |

WebSocket endpoints:
- Chat: `{WS_URL}/ws/chat`

REST endpoints:
- Session: `{REST_URL}/api/session`
- Chat: `{REST_URL}/api/chat`

## Features Requiring Configuration

### Contract Address Display
- Shows "TBD" if `NEXT_PUBLIC_CONTRACT_ADDRESS` is not set
- When set, displays address with copy button and Solscan link
- Explorer link uses `NEXT_PUBLIC_SOLANA_EXPLORER_BASE_URL`

### Social Links
Hardcoded in `src/config/brand.ts`:
- X: https://x.com/JeffreyAIstein
- TikTok: https://www.tiktok.com/@jeffrey.aistein

### Debug Panels
When enabled:
- **Chat Debug** (`NEXT_PUBLIC_DEBUG=true`): Shows API URLs, connection state
- **Avatar Debug** (`NEXT_PUBLIC_AVATAR_DEBUG=true`): Shows hologram state, mouth mask overlay

## Custom Domain Setup

See [NAMECHEAP_DOMAIN_SETUP.md](./NAMECHEAP_DOMAIN_SETUP.md) for domain configuration.

## Verification Checklist

After deployment, verify:
- [ ] Web app loads at Vercel URL
- [ ] Contract address displays (not "TBD")
- [ ] Copy button works
- [ ] Solscan link opens correct token page
- [ ] Social links (X, TikTok) work in header and footer
- [ ] Chat connects (WebSocket status shows "connected")
- [ ] Hologram loads and animates
- [ ] Messages can be sent and responses stream

## Troubleshooting

### "Failed to initialize session"
- Check `NEXT_PUBLIC_API_BASE_URL` is set correctly
- Verify API backend is running
- Check browser console for debug info (if `NEXT_PUBLIC_DEBUG=true`)

### Contract shows "TBD"
- Set `NEXT_PUBLIC_CONTRACT_ADDRESS` environment variable
- Redeploy (build-time variable)

### Hologram not loading
- Check browser supports WebGL
- Check console for Three.js errors
- Verify GLB file is in `public/assets/models/aistein/`

### iOS Local Network Prompt
- Indicates fallback to localhost
- Set `NEXT_PUBLIC_API_BASE_URL` to production URL
- Redeploy
