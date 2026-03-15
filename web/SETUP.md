# TrustCapture Web UI - Setup Guide

## What's Been Created

✅ Complete React + TypeScript + Vite project structure
✅ Authentication pages (Login/Register)
✅ Protected routes
✅ API client with interceptors
✅ Auth context for state management
✅ TailwindCSS configuration
✅ Basic dashboard

## Installation Steps

### 1. Install Dependencies

```bash
cd web
npm install
```

This will install all required packages including:
- React 18 + TypeScript
- React Router
- React Query
- Axios
- TailwindCSS
- Plotly.js (for charts)
- Mapbox GL JS (for maps)
- Stripe SDK

### 2. Create Environment File

```bash
cp .env.example .env
```

The `.env` file should contain:
```
VITE_API_URL=http://localhost:8000
```

### 3. Start Development Server

```bash
npm run dev
```

The app will be available at: **http://localhost:3000**

### 4. Start Backend API

In another terminal:
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

## Project Structure

```
web/
├── src/
│   ├── pages/
│   │   ├── auth/
│   │   │   ├── Login.tsx
│   │   │   └── Register.tsx
│   │   └── dashboard/
│   │       └── Dashboard.tsx
│   ├── components/
│   │   └── ProtectedRoute.tsx
│   ├── contexts/
│   │   └── AuthContext.tsx
│   ├── services/
│   │   └── api.ts
│   ├── types/
│   │   └── index.ts
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── public/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

## Features Implemented

### ✅ Authentication
- Login page with email/password
- Register page with company name
- JWT token management
- Protected routes
- Auto-redirect on 401

### ✅ API Integration
- Axios client with interceptors
- Automatic token injection
- Error handling
- Base URL configuration

### ✅ Routing
- React Router v6
- Protected routes
- Auto-redirect to dashboard

### ✅ State Management
- Auth context
- React Query setup
- Local storage for tokens

## Next Steps

### Phase 1: Core Pages (Next)
1. Dashboard with statistics
2. Campaign list and creation
3. Vendor management
4. Photo gallery

### Phase 2: Reports & Analytics
1. Reports page with charts (Plotly)
2. Map visualization (Mapbox)
3. CSV/GeoJSON export
4. Dashboard widgets

### Phase 3: Advanced Features
1. Subscription management
2. Payment integration (Stripe)
3. Real-time updates
4. Notifications

## Testing the App

### 1. Register a New Account
- Go to http://localhost:3000/register
- Fill in company name, email, password
- Click "Create account"

### 2. Login
- Go to http://localhost:3000/login
- Enter email and password
- Click "Sign in"

### 3. Dashboard
- After login, you'll be redirected to /dashboard
- You should see a welcome message

## Troubleshooting

### Port Already in Use
If port 3000 is in use, edit `vite.config.ts`:
```typescript
server: {
  port: 3001, // Change to any available port
}
```

### API Connection Issues
- Make sure backend is running on port 8000
- Check `.env` file has correct API URL
- Check browser console for errors

### Build Errors
```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

## Available Scripts

```bash
npm run dev      # Start development server
npm run build    # Build for production
npm run preview  # Preview production build
npm run lint     # Run ESLint
```

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## Status

✅ Project structure created
✅ Authentication flow implemented
✅ API client configured
✅ Basic routing setup
⏳ Dashboard features (next)
⏳ Campaign management (next)
⏳ Reports & analytics (next)

Ready to start development!
