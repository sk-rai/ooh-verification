import { useState } from 'react'
import LandingNav from './landing/LandingNav'
import Hero from './landing/Hero'
import Problem from './landing/Problem'
import HowItWorks from './landing/HowItWorks'
import UseCases from './landing/UseCases'
import Features from './landing/Features'
import Pricing from './landing/Pricing'
import FAQ from './landing/FAQ'
import CTABanner from './landing/CTABanner'
import Footer from './landing/Footer'

const tabs = [
  { id: 'how-it-works', label: 'How It Works' },
  { id: 'use-cases', label: 'Use Cases' },
  { id: 'features', label: 'Features' },
  { id: 'pricing', label: 'Pricing' },
  { id: 'faq', label: 'FAQ' },
]

function TabContent({ activeTab }: { activeTab: string }) {
  switch (activeTab) {
    case 'how-it-works': return <HowItWorks />
    case 'use-cases': return <UseCases />
    case 'features': return <Features />
    case 'pricing': return <Pricing />
    case 'faq': return <FAQ />
    default: return <HowItWorks />
  }
}

export default function LandingPage() {
  const [activeTab, setActiveTab] = useState('how-it-works')

  return (
    <div className="min-h-screen bg-white" style={{ scrollBehavior: 'smooth' }}>
      <LandingNav />
      <main>
        <Hero />
        <Problem />

        {/* Tabbed content section */}
        <section className="border-t border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex overflow-x-auto border-b border-gray-200 -mb-px">
              {tabs.map(t => (
                <button
                  key={t.id}
                  onClick={() => setActiveTab(t.id)}
                  className={`whitespace-nowrap py-4 px-6 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === t.id
                      ? 'border-primary-600 text-primary-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
          <TabContent activeTab={activeTab} />
        </section>

        <CTABanner />
      </main>
      <Footer />
    </div>
  )
}
