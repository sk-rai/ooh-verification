import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './contexts/AuthContext'
import Login from './pages/auth/Login'
import Register from './pages/auth/Register'
import LandingPage from './pages/LandingPage'
import PrivacyPolicy from './pages/legal/PrivacyPolicy'
import TermsOfService from './pages/legal/TermsOfService'
import Dashboard from './pages/dashboard/Dashboard'
import CampaignsList from './pages/dashboard/CampaignsList'
import CreateCampaign from './pages/dashboard/CreateCampaign'
import CampaignDetails from './pages/dashboard/CampaignDetails'
import VendorsList from './pages/dashboard/VendorsList'
import CreateVendor from './pages/dashboard/CreateVendor'
import PhotoGallery from './pages/dashboard/PhotoGallery'
import Reports from './pages/dashboard/Reports'
import Subscription from './pages/dashboard/Subscription'
import MapView from './pages/dashboard/MapView'
import MapViewEnhanced from './pages/dashboard/MapViewEnhanced'
import Analytics from './pages/dashboard/Analytics'
import ProtectedRoute from './components/ProtectedRoute'
import AdminLogin from './pages/admin/AdminLogin'
import AdminDashboard from './pages/admin/AdminDashboard'

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
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Router>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
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
        </Router>
      </AuthProvider>
    </QueryClientProvider>
  )
}

export default App
