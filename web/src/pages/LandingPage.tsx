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

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white" style={{ scrollBehavior: 'smooth' }}>
      <LandingNav />
      <main>
        <Hero />
        <Problem />
        <HowItWorks />
        <UseCases />
        <Features />
        <Pricing />
        <FAQ />
        <CTABanner />
      </main>
      <Footer />
    </div>
  )
}
