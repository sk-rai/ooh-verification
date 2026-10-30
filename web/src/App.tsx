import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { HelmetProvider } from 'react-helmet-async'
import { Suspense, lazy } from 'react'
import { AuthProvider } from './contexts/AuthContext'
import Login from './pages/auth/Login'
import Register from './pages/auth/Register'
import LandingPage from './pages/LandingPage'
import PrivacyPolicy from './pages/legal/PrivacyPolicy'
import TermsOfService from './pages/legal/TermsOfService'
import UseCases from './pages/UseCases'
import ProtectedRoute from './components/ProtectedRoute'
import AnalyticsTracker from './components/AnalyticsTracker'

// Dashboard pages lazily loaded to prevent Leaflet/Plotly/Mapbox from accessing
// window/document at module-evaluation time, which would crash the prerender.
const Dashboard = lazy(() => import('./pages/dashboard/Dashboard'))
const CampaignsList = lazy(() => import('./pages/dashboard/CampaignsList'))
const CreateCampaign = lazy(() => import('./pages/dashboard/CreateCampaign'))
const CampaignDetails = lazy(() => import('./pages/dashboard/CampaignDetails'))
const EditCampaign = lazy(() => import('./pages/dashboard/EditCampaign'))
const VendorsList = lazy(() => import('./pages/dashboard/VendorsList'))
const CreateVendor = lazy(() => import('./pages/dashboard/CreateVendor'))
const PhotoGallery = lazy(() => import('./pages/dashboard/PhotoGallery'))
const Reports = lazy(() => import('./pages/dashboard/Reports'))
const Subscription = lazy(() => import('./pages/dashboard/Subscription'))
const MapView = lazy(() => import('./pages/dashboard/MapView'))
const Tracking = lazy(() => import('./pages/dashboard/Tracking'))
const MapViewEnhanced = lazy(() => import('./pages/dashboard/MapViewEnhanced'))
const Analytics = lazy(() => import('./pages/dashboard/Analytics'))
const AdminLogin = lazy(() => import('./pages/admin/AdminLogin'))
const AdminDashboard = lazy(() => import('./pages/admin/AdminDashboard'))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

function App() {
  return (
    <HelmetProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <Router>
          <AnalyticsTracker />
          <Suspense fallback={<div className="min-h-screen bg-gray-50 flex items-center justify-center"><div className="text-gray-400 text-sm">Loading…</div></div>}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/use-cases" element={<UseCases />} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/campaigns"
              element={
                <ProtectedRoute>
                  <CampaignsList />
                </ProtectedRoute>
              }
            />
            <Route
              path="/campaigns/new"
              element={
                <ProtectedRoute>
                  <CreateCampaign />
                </ProtectedRoute>
              }
            />
            <Route
              path="/campaigns/:id"
              element={
                <ProtectedRoute>
                  <CampaignDetails />
                </ProtectedRoute>
              }
            />
            <Route
              path="/campaigns/:id/edit"
              element={
                <ProtectedRoute>
                  <EditCampaign />
                </ProtectedRoute>
              }
            />
            <Route
              path="/vendors"
              element={
                <ProtectedRoute>
                  <VendorsList />
                </ProtectedRoute>
              }
            />
            <Route
              path="/vendors/new"
              element={
                <ProtectedRoute>
                  <CreateVendor />
                </ProtectedRoute>
              }
            />
            <Route
              path="/photos"
              element={
                <ProtectedRoute>
                  <PhotoGallery />
                </ProtectedRoute>
              }
            />
            <Route
              path="/reports"
              element={
                <ProtectedRoute>
                  <Reports />
                </ProtectedRoute>
              }
            />
            <Route
              path="/subscription"
              element={
                <ProtectedRoute>
                  <Subscription />
                </ProtectedRoute>
              }
            />
            <Route
              path="/map"
              element={
                <ProtectedRoute>
                  <MapView />
                </ProtectedRoute>
              }
            />
            <Route
              path="/tracking"
                element={
                  <ProtectedRoute>
                    <Tracking />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/map-enhanced"
              element={
                <ProtectedRoute>
                  <MapViewEnhanced />
                </ProtectedRoute>
              }
            />
            <Route
              path="/analytics/:campaignCode"
              element={
                <ProtectedRoute>
                  <Analytics />
                </ProtectedRoute>
              }
            />
            <Route path="/admin/login" element={<AdminLogin />} />
            <Route path="/admin/dashboard" element={<AdminDashboard />} />
            <Route path="/admin" element={<Navigate to="/admin/dashboard" replace />} />
            <Route path="/privacy" element={<PrivacyPolicy />} />
            <Route path="/terms" element={<TermsOfService />} />
            <Route path="/" element={<LandingPage />} />
          </Routes>
          </Suspense>
        </Router>
        </AuthProvider>
      </QueryClientProvider>
    </HelmetProvider>
  )
}

export default App
