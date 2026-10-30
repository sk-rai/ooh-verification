/**
 * Server-side render entry for prerendering public routes.
 * Used by scripts/prerender.js at build time.
 *
 * Renders the App into a static HTML string at a given URL path using
 * StaticRouter (server-safe — no window/history access).
 * Only public, non-authenticated pages should be prerendered.
 */
import { renderToString } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { HelmetProvider, HelmetServerState } from 'react-helmet-async'
import { Suspense } from 'react'
import LandingPage from './pages/LandingPage'
import PrivacyPolicy from './pages/legal/PrivacyPolicy'
import TermsOfService from './pages/legal/TermsOfService'
import UseCases from './pages/UseCases'

// Map of public routes to their components.
// DO NOT include authenticated dashboard routes here.
const publicRoutes: Record<string, () => JSX.Element> = {
  '/': LandingPage,
  '/privacy': PrivacyPolicy,
  '/terms': TermsOfService,
  '/use-cases': UseCases,
}

export function render(url: string): { html: string; helmet: HelmetServerState } {
  const PageComponent = publicRoutes[url] || LandingPage
  const queryClient = new QueryClient()
  const helmetContext: { helmet?: HelmetServerState } = {}

  const html = renderToString(
    <HelmetProvider context={helmetContext}>
      <QueryClientProvider client={queryClient}>
        <StaticRouter location={url}>
          <Suspense fallback="">
            <PageComponent />
          </Suspense>
        </StaticRouter>
      </QueryClientProvider>
    </HelmetProvider>
  )

  return { html, helmet: helmetContext.helmet! }
}

export const routes = Object.keys(publicRoutes)
