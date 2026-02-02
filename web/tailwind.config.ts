import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Matrix theme colors
        matrix: {
          green: '#00ff41',
          darkgreen: '#003b00',
          cyan: '#00ffcc',
          darkcyan: '#004d40',
          black: '#0d0d0d',
          darkgray: '#1a1a1a',
        },
      },
      fontFamily: {
        mono: ['var(--font-mono)', 'Consolas', 'Monaco', 'monospace'],
      },
      animation: {
        'matrix-rain': 'matrix-rain 20s linear infinite',
        'glow-pulse': 'glow-pulse 2s ease-in-out infinite',
        'scanline': 'scanline 8s linear infinite',
        'flicker': 'flicker 0.15s infinite',
      },
      keyframes: {
        'matrix-rain': {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100vh)' },
        },
        'glow-pulse': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.7' },
        },
        'scanline': {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' },
        },
        'flicker': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.95' },
        },
      },
      boxShadow: {
        'glow-cyan': '0 0 20px rgba(0, 255, 204, 0.5)',
        'glow-green': '0 0 20px rgba(0, 255, 65, 0.5)',
      },
    },
  },
  plugins: [],
}

export default config
