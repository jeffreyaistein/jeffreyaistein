# Web Chat Production Debugging

This document explains how to debug chat connectivity issues in production.

## Enable Debug Mode

Set the `NEXT_PUBLIC_DEBUG` environment variable to `true` in Vercel:

1. Go to Vercel Dashboard → Project Settings → Environment Variables
2. Add: `NEXT_PUBLIC_DEBUG` = `true`
3. Redeploy the application

**Important:** This must be set as a build-time variable (not runtime), so you need to redeploy after changing it.

## Debug Panel

When debug mode is enabled, a **Debug Panel** appears in the bottom-right corner of the chat interface. It shows:

### Environment Variables (Raw)
- `NEXT_PUBLIC_API_BASE_URL` - The single source of truth for API URLs
- `NEXT_PUBLIC_API_URL` - Legacy REST URL (if set)
- `NEXT_PUBLIC_WS_URL` - Legacy WebSocket URL (if set)

### Computed URLs
- **Source** - Which env var is being used
- **REST Base** - The REST API base URL
- **WebSocket Base** - The WebSocket base URL
- **WS Chat URL** - Full WebSocket chat endpoint
- **Session URL** - Session initialization endpoint

### Connection State
- **Status** - Current connection status (connecting/connected/disconnected/error)
- **Last Error** - Most recent error message

## Expected Values When Correct

When properly configured for production:

| Field | Expected Value |
|-------|---------------|
| NEXT_PUBLIC_API_BASE_URL | `https://jeffreyaistein.fly.dev` |
| Source | `NEXT_PUBLIC_API_BASE_URL` |
| REST Base | `https://jeffreyaistein.fly.dev` |
| WebSocket Base | `wss://jeffreyaistein.fly.dev` |
| WS Chat URL | `wss://jeffreyaistein.fly.dev/ws/chat` |
| Session URL | `https://jeffreyaistein.fly.dev/api/session` |
| Status | `connected` |

## Console Logs

When debug mode is enabled, detailed logs are printed to the browser console:

```
=== AISTEIN DEBUG INFO ===
URL Source: NEXT_PUBLIC_API_BASE_URL
NEXT_PUBLIC_API_BASE_URL (raw): https://jeffreyaistein.fly.dev
...
==========================

[useChat] URL configuration:
  Source: NEXT_PUBLIC_API_BASE_URL
  REST URL: https://jeffreyaistein.fly.dev
  WebSocket URL: wss://jeffreyaistein.fly.dev
[useChat] Initializing session at: https://jeffreyaistein.fly.dev/api/session
[useChat] Session response status: 200
[useChat] Attempting WebSocket connection to: wss://jeffreyaistein.fly.dev/ws/chat
[useChat] WebSocket connected successfully
```

## Common Issues

### "Failed to initialize session"
- **Cause:** REST API endpoint not reachable
- **Check:** Verify `NEXT_PUBLIC_API_BASE_URL` is set correctly
- **Check:** Verify the API server is running at that URL

### iOS Local Network Access Prompt
- **Cause:** Frontend is trying to connect to localhost/LAN
- **Solution:** Ensure `NEXT_PUBLIC_API_BASE_URL` is set to the production URL (not localhost)

### "Connection error" or WebSocket fails
- **Cause:** WebSocket URL scheme mismatch
- **Check:** If API is `https://`, WebSocket must be `wss://`
- **Check:** The `/ws/chat` endpoint exists on the backend

### Source shows "FALLBACK (localhost)"
- **Cause:** No API URL environment variable is configured
- **Solution:** Set `NEXT_PUBLIC_API_BASE_URL` in Vercel

## Required Vercel Environment Variables

```bash
NEXT_PUBLIC_API_BASE_URL=https://jeffreyaistein.fly.dev
NEXT_PUBLIC_DEBUG=true  # Only for debugging, remove in production
```

## Verification Checklist

After deploying with debug enabled:

1. [ ] Debug panel shows `NEXT_PUBLIC_API_BASE_URL = https://jeffreyaistein.fly.dev`
2. [ ] Source shows `NEXT_PUBLIC_API_BASE_URL` (not "FALLBACK" or "legacy")
3. [ ] WebSocket Base shows `wss://` (not `ws://`)
4. [ ] WS Chat URL shows `wss://jeffreyaistein.fly.dev/ws/chat`
5. [ ] Connection status becomes "connected" (green)
6. [ ] Sending a message works end-to-end
7. [ ] No iOS local network access prompt appears

## Disabling Debug Mode

After verifying everything works:

1. Remove or set `NEXT_PUBLIC_DEBUG` to `false` in Vercel
2. Redeploy
3. Debug panel will no longer appear
