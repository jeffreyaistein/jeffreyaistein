import type { Metadata } from 'next'
import { JetBrains_Mono } from 'next/font/google'
import './globals.css'

const mono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
})

export const metadata: Metadata = {
  title: 'Jeffrey AIstein',
  description: 'global elite technology reverse engineered to do good for society',
  openGraph: {
    title: 'Jeffrey AIstein',
    description: 'global elite technology reverse engineered to do good for society',
    images: [
      {
        url: 'https://pbs.twimg.com/profile_images/2018144549630349312/qQZ4A7v__400x400.jpg',
        width: 400,
        height: 400,
        alt: 'Jeffrey AIstein',
      },
    ],
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'Jeffrey AIstein',
    description: 'global elite technology reverse engineered to do good for society',
    images: ['https://pbs.twimg.com/profile_images/2018144549630349312/qQZ4A7v__400x400.jpg'],
  },
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
