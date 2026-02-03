/**
 * Jeffrey AIstein - Brand Configuration
 *
 * Centralized configuration for brand identity, social links, and contract info.
 * Update this file to change links across the entire site.
 */

export const brand = {
  name: "Jeffrey AIstein",
  tagline: "Memory-aware AGI-style agent experience",
  version: "0.1.0",

  // Domain (pending DNS setup)
  domain: "JeffreyAIstein.fun",

  // Social links
  social: {
    x: {
      url: "https://x.com/JeffreyAIstein",
      handle: "@JeffreyAIstein",
    },
    tiktok: {
      url: "https://www.tiktok.com/@jeffrey.aistein",
      handle: "@jeffrey.aistein",
    },
  },

  // Contract info (configured via env vars)
  contract: {
    // Read from env at runtime - see ContractSection component
    address: process.env.NEXT_PUBLIC_CONTRACT_ADDRESS || "",
    explorerBaseUrl:
      process.env.NEXT_PUBLIC_SOLANA_EXPLORER_BASE_URL ||
      "https://solscan.io/token",
  },
} as const;

// Type exports for use in components
export type SocialPlatform = keyof typeof brand.social;

/**
 * Get explorer URL for the contract address
 */
export function getExplorerUrl(address: string): string {
  return `${brand.contract.explorerBaseUrl}/${address}`;
}

/**
 * Check if contract address is configured
 */
export function hasContractAddress(): boolean {
  return brand.contract.address.length > 0;
}
