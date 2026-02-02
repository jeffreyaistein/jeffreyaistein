import type { Metadata } from 'next'
import { JetBrains_Mono } from 'next/font/google'
import './globals.css'

const mono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
})

export const metadata: Metadata = {
  title: 'Jeffrey AIstein',
  description: 'AGI-style agent with persistent memory and holographic avatar',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={mono.variable}>
      <body className="min-h-screen bg-matrix-black text-matrix-green font-mono antialiased">
        {children}
      </body>
    </html>
  )
}
