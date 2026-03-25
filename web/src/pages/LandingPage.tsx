import LandingNav from './landing/LandingNav'
import Hero from './landing/Hero'
import Problem from './landing/Problem'
import HowItWorks from './landing/HowItWorks'
import UseCases from './landing/UseCases'
import Features from './landing/Features'
import Pricing from './landing/Pricing'
import Comparison from './landing/Comparison'
import AndroidApp from './landing/AndroidApp'
import MultiTenancy from './landing/MultiTenancy'
import PoweredBy from './landing/PoweredBy'
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
        <Comparison />
        <AndroidApp />
        <MultiTenancy />
        <PoweredBy />
        <FAQ />
        <CTABanner />
      </main>
      <Footer />
    </div>
  )
}
