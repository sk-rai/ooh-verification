import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor to handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const currentPath = window.location.pathname
      localStorage.removeItem('token')
      // Don't redirect if already on auth pages to avoid redirect loops
      if (currentPath !== '/login' && currentPath !== '/register' && !currentPath.startsWith('/admin')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api


// Bulk Operations API
export const bulkOperations = {
  // Download CSV templates
  downloadCampaignsTemplate: () =>
    api.get('/api/bulk/campaigns/template', { responseType: 'blob' }),
  
  downloadVendorsTemplate: () =>
    api.get('/api/bulk/vendors/template', { responseType: 'blob' }),
  
  downloadAssignmentsTemplate: () =>
    api.get('/api/bulk/assignments/template', { responseType: 'blob' }),

  // Upload CSV files
  uploadCampaigns: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/api/bulk/campaigns', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  uploadVendors: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/api/bulk/vendors', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  uploadAssignments: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/api/bulk/assignments', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}
