# Jeffrey AIstein - Brand Guide

> **Last Updated**: 2026-02-02
> **Status**: Active

---

## Brand Identity

**Name**: Jeffrey AIstein
**Tagline**: Memory-aware AGI-style agent experience
**Character**: Hyper-sarcastic, investigative AI with persistent memory

---

## Canonical Links

### Domain
- **Primary**: JeffreyAIstein.fun (pending DNS setup)
- **Current**: jeffreyaistein.fly.dev (Fly.io deployment)

### Social Media

| Platform | URL | Handle |
|----------|-----|--------|
| X (Twitter) | https://x.com/JeffreyAIstein | @JeffreyAIstein |
| TikTok | https://www.tiktok.com/@jeffrey.aistein | @jeffrey.aistein |

### API / Backend
- **Production API**: https://jeffreyaistein.fly.dev
- **Health Check**: https://jeffreyaistein.fly.dev/health/ready

---

## Configuration

Brand configuration is centralized in `apps/web/src/config/brand.ts`:

```typescript
import { brand } from '@/config/brand'

// Access social links
brand.social.x.url      // "https://x.com/JeffreyAIstein"
brand.social.tiktok.url // "https://www.tiktok.com/@jeffrey.aistein"

// Access contract info (if configured)
brand.contract.address  // From NEXT_PUBLIC_CONTRACT_ADDRESS env var
```

---

## Environment Variables

For the website (`apps/web/.env.local`):

```bash
# Contract address (Solana token)
NEXT_PUBLIC_CONTRACT_ADDRESS=

# Solana explorer base URL (optional, defaults to Solscan)
NEXT_PUBLIC_SOLANA_EXPLORER_BASE_URL=https://solscan.io/token
```

---

## Visual Identity

### Colors (Matrix Theme)
- **Primary Green**: `#00ff00` (matrix-green)
- **Secondary Cyan**: `#00ffff` (matrix-cyan)
- **Background**: `#0d0d0d` (matrix-black)

### Typography
- **Font**: JetBrains Mono (monospace)
- **Style**: All-caps for headers, cyber/hacker aesthetic

### Effects
- Digital rain background animation
- Scanline overlay
- Glowing borders
- Pulsing status indicators

---

## Voice & Tone

See `docs/PERSONA.md` for full character details.

**Key traits**:
- Hyper-sarcastic
- Provocatively irreverent
- Investigative journalist style
- Dark humor
- Never breaks character

**Hard limits**:
- No slurs or targeting protected classes
- No sexual violence jokes
- No actual illegal activity guidance

---

## Usage Guidelines

1. **Always use canonical URLs** from this document or `brand.ts`
2. **Do not hardcode** links in multiple places - use the config
3. **Maintain visual consistency** with Matrix theme
4. **Preserve character voice** in all automated content

---

## Contact

For brand inquiries, reach out via X: https://x.com/JeffreyAIstein
