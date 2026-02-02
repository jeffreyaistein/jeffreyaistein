'use client'

import { useState } from 'react'
import { HologramPlaceholder } from '@/components/HologramPlaceholder'
import { ChatBox } from '@/components/ChatBox'
import { TokenPanel } from '@/components/TokenPanel'
import { StatsPanel } from '@/components/StatsPanel'
import { DigitalRain } from '@/components/DigitalRain'

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
          <div className="text-sm opacity-70">
            <span className="text-matrix-green">STATUS:</span>{' '}
            <span className="text-matrix-cyan">ONLINE</span>
          </div>
        </div>
      </header>

      {/* Main content */}
      <div className="max-w-7xl mx-auto p-4 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: Stats and Token data */}
        <div className="space-y-6">
          <TokenPanel />
          <StatsPanel />
        </div>

        {/* Center column: Hologram and Chat */}
        <div className="lg:col-span-2 space-y-6">
          {/* Hologram Avatar */}
          <div className="matrix-border-cyan rounded-lg overflow-hidden">
            <div className="p-2 border-b border-matrix-cyan/30 flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-matrix-cyan animate-pulse" />
              <span className="text-xs text-matrix-cyan uppercase tracking-wider">
                Holographic Interface
              </span>
            </div>
            <HologramPlaceholder />
          </div>

          {/* Chat Interface */}
          <div className="matrix-border rounded-lg overflow-hidden">
            <div className="p-2 border-b border-matrix-green/30 flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-matrix-green animate-pulse" />
              <span className="text-xs text-matrix-green uppercase tracking-wider">
                Neural Link Active
              </span>
            </div>
            <ChatBox />
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-matrix-green/30 p-4 mt-8">
        <div className="max-w-7xl mx-auto text-center text-xs opacity-50">
          <p>Jeffrey AIstein v0.1.0 | Phase 0 Scaffold</p>
          <p className="mt-1">Memory-aware AGI-style agent experience</p>
        </div>
      </footer>
    </main>
  )
}
