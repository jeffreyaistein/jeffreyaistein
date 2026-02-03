'use client'

import { ChatInterface } from '@/components/ChatInterface'
import { TokenPanel } from '@/components/TokenPanel'
import { StatsPanel } from '@/components/StatsPanel'
import { ContractSection } from '@/components/ContractSection'
import { DigitalRain } from '@/components/DigitalRain'
import { SocialLinks } from '@/components/SocialLinks'
import { brand } from '@/config/brand'

export default function Home() {
  return (
    <main className="min-h-screen relative">
      {/* Background digital rain effect */}
      <DigitalRain />

      {/* Scanline overlay */}
      <div className="scanline-overlay" />

      {/* Header */}
      <header className="border-b border-matrix-green/30 p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <h1 className="text-2xl matrix-text-cyan font-bold tracking-wider">
            JEFFREY AISTEIN
          </h1>
          <div className="flex items-center gap-6">
            <SocialLinks />
            <div className="text-sm opacity-70">
              <span className="text-matrix-green">STATUS:</span>{' '}
              <span className="text-matrix-cyan">ONLINE</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <div className="max-w-7xl mx-auto p-4 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: Contract, Token, and Stats */}
        <div className="space-y-6">
          <ContractSection />
          <TokenPanel />
          <StatsPanel />
        </div>

        {/* Center column: Hologram and Chat (integrated) */}
        <div className="lg:col-span-2">
          <ChatInterface />
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-matrix-green/30 p-4 mt-8">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="text-xs opacity-50">
              <p>{brand.name} v{brand.version}</p>
              <p className="mt-1">{brand.tagline}</p>
            </div>
            <SocialLinks showLabels />
          </div>
        </div>
      </footer>
    </main>
  )
}
