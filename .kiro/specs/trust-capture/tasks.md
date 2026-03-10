# Implementation Plan: TrustCapture - Dual-Platform Photo Verification System

## Overview

This implementation plan breaks down the TrustCapture system into discrete, testable tasks across three main components:
1. Backend Services (Python/FastAPI)
2. Web Application (React/TypeScript)
3. Android Application (Kotlin)

The plan follows an incremental approach where each task builds on previous work, with checkpoints to ensure quality and integration. Tasks are organized by component and phase, with clear dependencies and requirements traceability.

## Phase 1: Backend Foundation

- [x] 1. Set up backend project structure and core infrastructure
  - Initialize FastAPI project with Python 3.11+
  - Configure SQLAlchemy 2.0 with async support
  - Set up Alembic for database migrations
  - Configure environment variables and secrets management
  - Create Docker and docker-compose files for local development
  - Set up pytest with async support and coverage reporting
  - _Requirements: 20_

- [x] 2. Implement database schema and models
  - [ ] 2.1 Create PostgreSQL database schema
    - Create clients table with subscription fields
    - Create vendors table with device registration fields
    - Create campaigns table with status tracking
    - Create location_profiles table with sensor expectations
    - Create campaign_vendor_assignments junction table
    - Create photos table with verification status
    - Create sensor_data table with JSONB fields for WiFi/cell data
    - Create photo_signatures table
    - Create subscriptions table with Stripe integration fields
    - Add indexes for performance optimization
    - _Requirements: 1.1, 1.2, 1.3, 18.1, 18.2, 18.3, 18.4, 18.5_

  - [ ] 2.2 Create SQLAlchemy ORM models
    - Define Client, Vendor, Campaign, LocationProfile models
    - Define Photo, SensorData, PhotoSignature models
    - Define Subscription model with tier enum
    - Add relationships and foreign keys
    - Implement model validation with Pydantic
    - _Requirements: 1.1, 18.1_

  - [ ]* 2.3 Write property test for round-trip configuration parsing
    - **Property 1: Round-Trip Configuration Parsing**
    - **Validates: Requirements 25.4**

  - [ ] 2.4 Create initial database migration
    - Generate Alembic migration from models
    - Test migration up and down
    - Add seed data for development
    - _Requirements: 20_

- [x] 3. Implement authentication and authorization
  - [ ] 3.1 Create JWT authentication for web clients
    - Implement password hashing with bcrypt
    - Create login endpoint with JWT token generation
    - Create token validation middleware
    - Implement refresh token mechanism
    - _Requirements: 1.1, 1.2_

  - [ ] 3.2 Create vendor authentication system
    - Implement vendor ID + phone number authentication
    - Create OTP generation and validation
    - Integrate Twilio for SMS delivery
    - Implement device registration with public key storage
    - _Requirements: 1.1, 1.4_

  - [ ]* 3.3 Write unit tests for authentication flows
    - Test password hashing and verification
    - Test JWT token generation and validation
    - Test OTP generation and expiration
    - Test invalid credentials handling
    - _Requirements: 1.1, 1.2, 1.4_

- [x] 4. Implement client management API
  - [ ] 4.1 Create client registration endpoint
    - Implement POST /api/clients/register
    - Validate email format and password strength
    - Check for duplicate email addresses
    - Send welcome email via SendGrid
    - Return client response with JWT token
    - _Requirements: 1.1, 1.2_

  - [ ] 4.2 Create client login endpoint
    - Implement POST /api/clients/login
    - Validate credentials against database
    - Generate JWT token with 7-day expiration
    - Return token and client details
    - _Requirements: 1.1, 1.2_

  - [ ]* 4.3 Write integration tests for client endpoints
    - Test successful registration flow
    - Test duplicate email rejection
    - Test login with valid/invalid credentials
    - Test JWT token validation
    - _Requirements: 1.1, 1.2_

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement vendor management API
  - [ ] 6.1 Create vendor CRUD endpoints
    - Implement POST /api/vendors (create vendor with ID generation)
    - Implement GET /api/vendors (list vendors for client)
    - Implement PATCH /api/vendors/{vendor_id} (update vendor)
    - Implement PATCH /api/vendors/{vendor_id}/deactivate
    - Generate 6-character alphanumeric vendor IDs
    - Send SMS with vendor ID and app download link
    - _Requirements: 1.1, 1.2, 1.3_

  - [ ]* 6.2 Write unit tests for vendor ID generation
    - Test vendor ID format (6 chars, alphanumeric)
    - Test uniqueness of generated IDs
    - Test collision handling
    - _Requirements: 1.1, 12.1_

  - [ ]* 6.3 Write integration tests for vendor endpoints
    - Test vendor creation and SMS delivery
    - Test vendor listing with filtering
    - Test vendor deactivation
    - Test authorization (client can only access their vendors)
    - _Requirements: 1.1, 1.2, 1.3_

- [x] 7. Implement campaign management API
  - [ ] 7.1 Create campaign CRUD endpoints
    - Implement POST /api/campaigns (create campaign)
    - Implement GET /api/campaigns (list campaigns)
    - Implement GET /api/campaigns/{campaign_id} (get campaign details)
    - Implement PATCH /api/campaigns/{campaign_id} (update campaign)
    - Generate campaign codes with format validation
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 12.1_

  - [ ] 7.2 Create location profile management
    - Implement location profile creation within campaign
    - Store expected GPS coordinates with 7 decimal precision
    - Store expected WiFi BSSIDs array
    - Store expected cell tower IDs array
    - Store environmental sensor ranges (pressure, light)
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ] 7.3 Create campaign-vendor assignment endpoints
    - Implement POST /api/campaigns/{campaign_id}/vendors (assign vendors)
    - Implement DELETE /api/campaigns/{campaign_id}/vendors/{vendor_id}
    - Send SMS notifications to assigned vendors
    - _Requirements: 1.1, 1.3_

  - [ ]* 7.4 Write property test for campaign code format
    - **Property 12: Campaign Code Format Invariant**
    - **Validates: Requirements 1.1, 12.1**

  - [ ]* 7.5 Write integration tests for campaign endpoints
    - Test campaign creation with location profile
    - Test vendor assignment and notifications
    - Test campaign listing and filtering
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement cryptographic verification services
  - [x] 9.1 Create photo signature verification service
    - Implement signature verification using RSA/ECDSA
    - Validate signature matches photo hash
    - Validate timestamp within 5-minute window
    - Validate location hash matches sensor data
    - Store public keys from vendor devices
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.7, 27.1, 27.2, 27.3, 27.4, 27.5_

  - [ ]* 9.2 Write property test for signature verification
    - **Property 3: Photo Signature Verification Inverse**
    - **Validates: Requirements 8.7, 27.6**

  - [ ]* 9.3 Write property test for signature tamper detection
    - **Property 13: Photo Signature Tamper Detection**
    - **Validates: Requirements 8.1, 8.7, 27.3**

  - [x] 9.4 Create location hash validation service
    - Implement SHA-256 hash generation from sensor data
    - Include GPS, WiFi BSSIDs, cell tower IDs in hash
    - Use cryptographic salt from device key
    - _Requirements: 6.5, 28.1, 28.2, 28.3_

  - [ ]* 9.5 Write property test for location hash determinism
    - **Property 4: Location Hash Determinism**
    - **Validates: Requirements 6.5, 28.1**

  - [ ]* 9.6 Write property test for location hash uniqueness
    - **Property 5: Location Hash Uniqueness**
    - **Validates: Requirements 28.4, 28.5**

- [x] 10. Implement location profile matching service
  - [x] 10.1 Create location profile matcher
    - Compare captured GPS against expected coordinates
    - Calculate distance using Haversine formula
    - Match WiFi BSSIDs (require at least 3 matches)
    - Match cell tower IDs
    - Match environmental sensor ranges (pressure, light)
    - Calculate match confidence score (0-100)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_

  - [ ]* 10.2 Write property test for match score range
    - **Property 15: Location Profile Match Score Range**
    - **Validates: Requirements 7.7, 7.8**

  - [ ]* 10.3 Write unit tests for location matching
    - Test GPS distance calculation accuracy
    - Test WiFi BSSID matching logic
    - Test cell tower matching
    - Test confidence score calculation
    - Test edge cases (missing sensors, partial matches)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [x] 11. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Implement photo upload and storage API
  - [x] 12.1 Create photo upload endpoint
    - Implement POST /api/photos/upload
    - Accept multipart form data with photo and metadata
    - Validate photo format (JPEG) and size (max 5MB)
    - Parse sensor data JSON payload
    - Parse photo signature
    - Verify signature before accepting upload
    - _Requirements: 9.1, 9.2, 9.7, 21.1, 21.5_

  - [x] 12.2 Integrate AWS S3 for photo storage
    - Configure boto3 S3 client
    - Upload photos to S3 with unique keys
    - Generate thumbnail images (200x200)
    - Store thumbnail in S3
    - Enable S3 versioning for tamper protection
    - _Requirements: 9.1, 9.3_

  - [x] 12.3 Create photo metadata storage
    - Store photo record in PostgreSQL
    - Store sensor data in sensor_data table
    - Store signature in photo_signatures table
    - Link photo to campaign and vendor
    - Set initial verification status to 'pending'
    - _Requirements: 9.1, 9.7, 9.8_

  - [x] 12.4 Implement photo verification workflow
    - Verify signature validity
    - Match location profile if defined
    - Calculate distance from expected location
    - Update verification status (verified/flagged/rejected)
    - Store match result and confidence score
    - _Requirements: 7.5, 7.6, 27.1, 27.2, 27.3_

  - [ ]* 12.5 Write integration tests for photo upload
    - Test successful upload with valid signature
    - Test upload rejection with invalid signature
    - Test location profile matching
    - Test S3 storage and thumbnail generation
    - _Requirements: 9.1, 9.2, 9.7, 9.8_

- [x] 13. Implement audit logging system
  - [x] 13.1 Create DynamoDB audit log table
    - Configure DynamoDB table with append-only permissions
    - Define audit record schema
    - Implement hash chaining for immutability
    - _Requirements: 10.1, 10.2, 10.3, 10.5, 10.6_

  - [x] 13.2 Create audit logger service
    - Log photo capture events to DynamoDB
    - Include vendor ID, photo ID, timestamp, sensor data
    - Include signature and device info
    - Calculate and store previous record hash
    - Add audit flags (rooted device, emulator, etc.)
    - _Requirements: 10.1, 10.2, 10.4, 10.7_

  - [ ]* 13.3 Write property test for audit record immutability
    - **Property 14: Audit Record Immutability**
    - **Validates: Requirements 10.6, 10.7**

  - [ ]* 13.4 Write property test for timestamp ordering
    - **Property 8: Timestamp Ordering Invariant**
    - **Validates: Requirements 10.7**

- [x] 14. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Implement subscription and payment integration
  - [ ] 15.1 Create Stripe integration
    - Configure Stripe API with secret key
    - Implement POST /api/subscriptions/create-checkout
    - Implement webhook handler for subscription events
    - Handle subscription.created, subscription.updated, subscription.deleted
    - Update client subscription tier in database
    - _Requirements: 1.1, 1.2_

  - [ ] 15.2 Create subscription management endpoints
    - Implement GET /api/subscriptions/current (get client subscription)
    - Implement POST /api/subscriptions/upgrade (upgrade tier)
    - Implement POST /api/subscriptions/cancel
    - Implement quota checking middleware
    - _Requirements: 1.1, 1.2_

  - [ ] 15.3 Implement usage tracking
    - Track photos uploaded per month per client
    - Implement quota enforcement (50 for free tier)
    - Reset counters on subscription renewal
    - _Requirements: 1.1, 1.2_

  - [ ]* 15.4 Write integration tests for payment flow
    - Test subscription creation with Stripe
    - Test webhook handling
    - Test quota enforcement
    - Test tier upgrades and downgrades
    - _Requirements: 1.1, 1.2_

- [x] 16. Implement report generation API
  - [x] 16.1 Create CSV export endpoint
    - Implement GET /api/campaigns/{campaign_id}/export/csv
    - Query photos with sensor data for campaign
    - Generate CSV with all photo metadata
    - Include GPS coordinates with 7 decimal precision
    - Include sensor counts and verification status
    - Return CSV file with proper headers
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 7.1_

  - [x] 16.2 Create GeoJSON export endpoint
    - Implement GET /api/campaigns/{campaign_id}/export/geojson
    - Generate GeoJSON FeatureCollection
    - Create Point features for each photo
    - Include photo metadata in properties
    - Return GeoJSON with proper MIME type
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 16.3 Create PDF report generation
    - Integrate ReportLab or WeasyPrint
    - Generate campaign summary report
    - Include statistics, map visualization, photo grid
    - Add verification status charts
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ]* 16.4 Write integration tests for report generation
    - Test CSV export format and content
    - Test GeoJSON export structure
    - Test PDF generation
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 17. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 19. Implement Campaign Locations & Geocoding
  - [x] 19.1 Create campaign locations model
    - Implement CampaignLocation model with location data
    - Support multiple locations per campaign (unlimited)
    - Store address, coordinates, verification radius
    - Add foreign key relationship to campaigns
    - Create database migration 004_campaign_locations
    - _Requirements: 1.5, 17.1, 17.2_

  - [x] 19.2 Implement geocoding service
    - Integrate Google Maps Geocoding API
    - Implement OpenStreetMap Nominatim as fallback
    - Forward geocoding: address → coordinates
    - Reverse geocoding: coordinates → address
    - Extract address components (city, state, country, postal code)
    - Handle API errors and rate limiting
    - _Requirements: 17.3, 17.4, 18.1, 18.2_

  - [x] 19.3 Create location verification service
    - Implement Haversine distance calculation
    - Verify photo location against campaign locations
    - Find nearest location to photo coordinates
    - Check if photo is within verification radius
    - Configurable radius per location (10m - 10km)
    - Return verification result with distance
    - _Requirements: 17.1, 17.2, 17.3_

  - [x] 19.4 Create campaign locations API endpoints
    - Implement POST /api/campaigns/{id}/locations (add location)
    - Implement GET /api/campaigns/{id}/locations (list locations)
    - Implement GET /api/campaigns/{id}/locations/{loc_id} (get location)
    - Implement PATCH /api/campaigns/{id}/locations/{loc_id} (update location)
    - Implement DELETE /api/campaigns/{id}/locations/{loc_id} (delete location)
    - Implement POST /api/geocoding/forward (address → coordinates)
    - Implement POST /api/geocoding/reverse (coordinates → address)
    - Implement POST /api/geocoding/verify (verify photo location)
    - Implement GET /api/geocoding/nearest (find nearest location)
    - Implement GET /api/geocoding/distance (calculate distance)
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 18.1, 18.2_

  - [x]* 19.5 Write integration tests for campaign locations
    - Test location CRUD operations
    - Test geocoding forward and reverse
    - Test location verification
    - Test distance calculations
    - Test nearest location detection
    - _Requirements: 17.1, 17.2, 17.3, 17.4_

- [x] 20. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Phase 2: Web Application (Client Portal)

- [ ] 18. Set up web application project
  - Initialize React 18+ project with TypeScript and Vite
  - Configure ESLint and Prettier
  - Set up React Router v6
  - Configure Material-UI (MUI) theme
  - Set up TanStack Query for data fetching
  - Configure Axios for API calls
  - Create environment configuration for API URLs
  - _Requirements: 20_

- [ ] 19. Implement authentication UI
  - [ ] 19.1 Create login page
    - Build login form with email and password fields
    - Implement form validation with React Hook Form + Zod
    - Handle JWT token storage in httpOnly cookies
    - Implement error handling for invalid credentials
    - Add "Forgot Password" link
    - _Requirements: 1.1, 1.2_

  - [ ] 19.2 Create registration page
    - Build registration form with email, password, company details
    - Add password strength indicator
    - Implement email format validation
    - Handle duplicate email errors
    - Redirect to subscription selection after registration
    - _Requirements: 1.1, 1.2_

  - [ ] 19.3 Create protected route wrapper
    - Implement authentication check for protected routes
    - Redirect to login if not authenticated
    - Validate JWT token expiration
    - _Requirements: 1.1, 1.2_

  - [ ]* 19.4 Write component tests for authentication
    - Test login form validation
    - Test registration form validation
    - Test protected route behavior
    - _Requirements: 1.1, 1.2_

- [ ] 20. Implement subscription selection UI
  - [ ] 20.1 Create subscription tier comparison page
    - Display Free, Pro, Enterprise tier cards
    - Show feature comparison table
    - Add monthly/annual toggle with discount display
    - Implement "Start Free Trial" button for Pro tier
    - _Requirements: 1.1, 1.2_

  - [ ] 20.2 Integrate Stripe Checkout
    - Initialize Stripe.js in React
    - Create checkout session on tier selection
    - Redirect to Stripe hosted checkout
    - Handle success/cancel redirects
    - _Requirements: 1.1, 1.2_

  - [ ]* 20.3 Write integration tests for subscription flow
    - Test tier selection UI
    - Test Stripe checkout initialization
    - Test redirect handling
    - _Requirements: 1.1, 1.2_

- [ ] 21. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 22. Implement client dashboard
  - [ ] 22.1 Create dashboard layout
    - Build responsive dashboard layout with MUI Grid
    - Add navigation sidebar with menu items
    - Create header with user profile and logout
    - Implement breadcrumb navigation
    - _Requirements: 1.1_

  - [ ] 22.2 Create dashboard overview cards
    - Display total vendors count
    - Display active campaigns count
    - Display photos captured count
    - Display verification success rate
    - Add recent activity feed
    - _Requirements: 1.1, 1.2_

  - [ ] 22.3 Create quick action buttons
    - Add "Add Vendor" button
    - Add "Create Campaign" button
    - Add "View Reports" button
    - _Requirements: 1.1, 1.2, 1.3_

  - [ ]* 22.4 Write component tests for dashboard
    - Test dashboard layout rendering
    - Test statistics display
    - Test quick action buttons
    - _Requirements: 1.1, 1.2_

- [ ] 23. Implement vendor management UI
  - [ ] 23.1 Create vendor list page
    - Build DataGrid with vendor list
    - Display vendor ID, name, phone, status, last active
    - Add search and filter functionality
    - Implement pagination
    - Add "Add Vendor" button
    - _Requirements: 1.1, 1.2, 1.3_

  - [ ] 23.2 Create add/edit vendor dialog
    - Build form with name, phone, email fields
    - Implement form validation
    - Show generated vendor ID after creation
    - Display SMS delivery confirmation
    - _Requirements: 1.1, 1.2, 1.3_

  - [ ] 23.3 Implement vendor actions
    - Add edit button for each vendor
    - Add deactivate button with confirmation dialog
    - Implement bulk operations (export, deactivate multiple)
    - _Requirements: 1.1, 1.2, 1.3_

  - [ ]* 23.4 Write component tests for vendor management
    - Test vendor list rendering
    - Test add vendor dialog
    - Test vendor actions
    - _Requirements: 1.1, 1.2, 1.3_

- [ ] 24. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 25. Implement campaign management UI
  - [ ] 25.1 Create campaign list page
    - Build campaign list with filters (active, completed, cancelled)
    - Display campaign name, code, type, dates, photo count
    - Add search functionality
    - Implement "Create Campaign" button
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ] 25.2 Create campaign creation wizard
    - Build multi-step wizard with stepper component
    - Step 1: Basic info (name, type, dates)
    - Step 2: Location profile (GPS, WiFi, cell towers, environmental sensors)
    - Step 3: Assign vendors from list
    - Step 4: Review and create
    - Generate campaign code automatically
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 7.1, 7.2, 7.3, 7.4_

  - [ ] 25.3 Create campaign detail page
    - Display campaign information
    - Show assigned vendors list
    - Display location profile details
    - Show campaign statistics
    - Add "View Photos" button
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ]* 25.4 Write component tests for campaign management
    - Test campaign list rendering
    - Test wizard navigation
    - Test campaign creation flow
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ] 26. Implement photo gallery UI
  - [ ] 26.1 Create photo gallery grid view
    - Build responsive image grid with MUI ImageList
    - Display photo thumbnails with metadata overlay
    - Show capture timestamp and verification status
    - Add filters (date range, vendor, status)
    - Implement infinite scroll or pagination
    - _Requirements: 1.1, 1.2, 3.1, 3.2_

  - [ ] 26.2 Create photo detail modal
    - Display full-size photo with watermark
    - Show sensor data (GPS, WiFi, cell, environmental)
    - Display verification status and match score
    - Show distance from expected location
    - Add actions (approve, flag, reject)
    - _Requirements: 1.1, 1.2, 3.1, 3.2, 3.3, 7.5, 7.6, 7.7_

  - [ ] 26.3 Implement view mode toggle
    - Add toggle between grid view and map view
    - Persist view preference in local storage
    - _Requirements: 1.1, 1.2_

  - [ ]* 26.4 Write component tests for photo gallery
    - Test grid rendering
    - Test photo detail modal
    - Test filters and search
    - _Requirements: 1.1, 1.2, 3.1, 3.2_

- [ ] 27. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 28. Implement map visualization
  - [ ] 28.1 Integrate Mapbox or Leaflet
    - Choose map library (Leaflet for Free tier, Mapbox for Pro/Enterprise)
    - Initialize map component with React
    - Configure map tiles and styling
    - Set up map controls (zoom, pan, layers)
    - _Requirements: 1.1, 1.2_

  - [ ] 28.2 Create photo markers on map
    - Plot photo locations as markers
    - Color-code markers by verification status (green/yellow/red)
    - Implement marker clustering for dense areas
    - Add expected location marker if location profile defined
    - Draw distance circles around expected location
    - _Requirements: 1.1, 1.2, 3.1, 3.2, 7.1_

  - [ ] 28.3 Implement map interactions
    - Show photo preview popup on marker click
    - Implement zoom to fit all markers
    - Add layer toggles (satellite, terrain, street)
    - Add distance measurement tool
    - _Requirements: 1.1, 1.2, 3.1, 3.2_

  - [ ]* 28.4 Write component tests for map visualization
    - Test map initialization
    - Test marker rendering
    - Test marker interactions
    - _Requirements: 1.1, 1.2, 3.1, 3.2_

- [ ] 29. Implement reports and analytics UI
  - [ ] 29.1 Create campaign report page
    - Display campaign statistics cards
    - Show verification success rate chart
    - Display photos per vendor chart
    - Show timeline chart (photos over time)
    - Calculate and display distance metrics
    - _Requirements: 1.1, 1.2, 3.1, 3.2, 3.3, 3.4_

  - [ ] 29.2 Create export functionality
    - Add "Export CSV" button with download
    - Add "Export GeoJSON" button with download
    - Add "Generate PDF Report" button
    - Show export progress indicator
    - Handle export errors gracefully
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ] 29.3 Integrate Recharts for visualizations
    - Create bar chart for photos per vendor
    - Create line chart for photos over time
    - Create pie chart for verification status distribution
    - Add interactive tooltips
    - _Requirements: 1.1, 1.2, 3.1, 3.2_

  - [ ]* 29.4 Write component tests for reports
    - Test report page rendering
    - Test chart rendering
    - Test export functionality
    - _Requirements: 1.1, 1.2, 3.1, 3.2, 3.3, 3.4_

- [ ] 30. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 31. Implement settings and account management UI
  - [ ] 31.1 Create settings page layout
    - Build tabbed settings interface
    - Add tabs for Account, Subscription, Billing, API Keys, Team
    - _Requirements: 1.1, 1.2_

  - [ ] 31.2 Create account settings tab
    - Display email (read-only)
    - Add company name edit field
    - Add phone number edit field
    - Add change password form
    - Implement save changes functionality
    - _Requirements: 1.1, 1.2_

  - [ ] 31.3 Create subscription management tab
    - Display current subscription tier
    - Show usage statistics (photos this month, storage used)
    - Add "Upgrade" button with tier comparison
    - Add "Cancel Subscription" button with confirmation
    - Display billing history
    - _Requirements: 1.1, 1.2_

  - [ ] 31.4 Create API keys tab (Pro/Enterprise)
    - Display API key with copy button
    - Add "Regenerate API Key" button
    - Show API usage statistics
    - Display API documentation link
    - _Requirements: 1.1, 1.2_

  - [ ]* 31.5 Write component tests for settings
    - Test settings page rendering
    - Test account updates
    - Test subscription management
    - _Requirements: 1.1, 1.2_

- [ ] 32. Implement responsive design and accessibility
  - [ ] 32.1 Ensure mobile responsiveness
    - Test all pages on mobile breakpoints
    - Adjust layouts for tablet and mobile
    - Implement mobile navigation drawer
    - _Requirements: 20_

  - [ ] 32.2 Implement accessibility features
    - Add ARIA labels to all interactive elements
    - Ensure keyboard navigation works
    - Test with screen readers
    - Verify color contrast ratios (WCAG AA)
    - Add focus indicators
    - _Requirements: 20_

  - [ ]* 32.3 Write accessibility tests
    - Test keyboard navigation
    - Test ARIA labels
    - Test focus management
    - _Requirements: 20_

- [ ] 33. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.


## Phase 2.5: Multi-Tenancy and White-Label Architecture

- [ ] 20. Implement multi-tenancy and white-label architecture
  - **Spec Location**: `.kiro/specs/multi-tenant-whitelabel/`
  - **Requirements**: 27 requirements (Req 20.1-20.27)
  - **Correctness Properties**: 39 properties
  - **Duration**: 10 weeks (4 phases)
  - **Priority**: High - Prerequisite for Android development
  
  **Overview**: Add multi-tenancy and white-labeling capabilities to enable verification agencies to use TrustCapture under their own brand. Supports both SaaS multi-tenant (shared infrastructure) and dedicated instance (isolated) deployment models.
  
  **Business Value**: 
  - Enable white-label partnerships with verification agencies
  - Create recurring revenue stream ($500-5,000/month per client)
  - Position TrustCapture as a platform, not just a product
  - Scale to multiple clients without proportional infrastructure costs
  
  **Implementation Phases**:
  
  - [ ] 20.1 Phase 1: Backend Multi-Tenancy (Weeks 1-3)
    - Create tenant_config database table
    - Implement tenant context middleware
    - Build branding API endpoints (GET, PUT, POST)
    - Create email template system with tenant branding
    - Implement rate limiting per tenant
    - Enhance audit logging with tenant context
    - Verify data isolation between tenants
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.7, 20.8_
    - _Properties: 1-25_
    - _Deliverables: Database migration, branding API, tenant middleware, tests passing_
  
  - [ ] 20.2 Phase 2: Frontend Dynamic Theming (Weeks 4-5)
    - Create Theme Context Provider (React)
    - Implement branding API integration
    - Add CSS custom properties for dynamic theming
    - Replace hardcoded branding with dynamic values
    - Implement custom domain support
    - Add theme caching in browser storage
    - _Requirements: 20.9, 20.10_
    - _Properties: 26-29_
    - _Deliverables: Dynamic theming working, custom domains supported, tests passing_
  
  - [ ] 20.3 Phase 3: Android White-Label (Weeks 6-8)
    - Setup Gradle product flavors (build variants)
    - Create flavor directory structure
    - Add flavor-specific resources (colors, icons, strings)
    - Implement dynamic theme loading from API
    - Configure separate package names per flavor
    - Create build automation scripts
    - Setup CI/CD for multiple flavors
    - _Requirements: 20.11, 20.12, 20.13, 20.14_
    - _Properties: 31-32_
    - _Deliverables: Multiple APKs buildable, dynamic theming functional, automation complete_
  
  - [ ] 20.4 Phase 4: Deployment & Automation (Weeks 9-10)
    - Create Docker Compose configurations (multi-tenant and dedicated)
    - Develop Terraform modules for both deployment models
    - Setup monitoring (Prometheus + Grafana)
    - Create tenant onboarding CLI tool
    - Update CI/CD pipeline for tenant deployments
    - Write deployment documentation
    - _Requirements: 20.15, 20.16, 20.17, 20.18, 20.19, 20.22, 20.23, 20.24, 20.25, 20.26_
    - _Properties: 30, 33-39_
    - _Deliverables: Deployment automation complete, monitoring configured, documentation finished_
  
  - [ ] 20.5 Checkpoint - Multi-tenancy complete
    - Verify all 19 tasks complete (see `.kiro/specs/multi-tenant-whitelabel/tasks.md`)
    - Verify all 39 correctness properties passing
    - Verify can onboard new tenant in 1-2 weeks
    - Verify each tenant sees their own branding
    - Verify data isolation through automated tests
    - Verify no performance degradation with 10+ tenants
    - Verify documentation complete
    - Ask the user if questions arise before proceeding to Android development

  **Success Criteria**:
  - Can onboard new white-label client in 1-2 weeks
  - Each tenant sees their own branding throughout the app
  - Data isolation verified through automated tests
  - Single codebase serves all tenants
  - Android app can be built with different branding per client
  - No performance degradation with 10+ tenants
  - Deployment automation works for both SaaS and dedicated models

  **Files Created**:
  - `.kiro/specs/multi-tenant-whitelabel/requirements.md` (27 requirements)
  - `.kiro/specs/multi-tenant-whitelabel/design.md` (1,899 lines, 39 properties)
  - `.kiro/specs/multi-tenant-whitelabel/tasks.md` (19 tasks, 70+ sub-tasks)

  **Reference Documents**:
  - `WHITELABEL_ARCHITECTURE_ANALYSIS.md` - Feasibility analysis
  - `TASK20_COMPLETE_SPEC_SUMMARY.md` - Complete spec summary

  **Note**: Phase 1 (Backend Multi-Tenancy) must complete before starting Android development (Phase 3) to ensure Android is built with white-label support from day 1.

## Phase 3: Android Application (Vendor App)

- [ ] 34. Set up Android project structure
  - Initialize Android project with Kotlin and Jetpack Compose
  - Configure Gradle with Kotlin DSL
  - Set minimum SDK to API 26 (Android 8.0)
  - Set target SDK to API 34 (Android 14)
  - Configure Hilt for dependency injection
  - Set up Room database with SQLCipher encryption
  - Configure Retrofit and OkHttp for networking
  - Set up JUnit 5 and Mockk for testing
  - Configure Kotest for property-based testing
  - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5_

- [ ] 35. Implement permission management
  - [ ] 35.1 Create permission request flow
    - Request camera permission with rationale dialog
    - Request location permission (fine and coarse)
    - Request WiFi scanning permission (ACCESS_FINE_LOCATION)
    - Request phone state permission for cell tower data
    - Implement permission denied handling
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6_

  - [ ] 35.2 Create permission rationale dialogs
    - Explain camera permission for photo capture
    - Explain location permission for GPS verification
    - Explain WiFi permission for network fingerprinting
    - Explain phone state permission for cell tower data
    - _Requirements: 15.1, 15.2, 15.6_

  - [ ]* 35.3 Write property test for permission request idempotence
    - **Property 18: Permission Request Idempotence**
    - **Validates: Requirements 15.1, 15.2, 15.3, 15.4**

  - [ ]* 35.4 Write unit tests for permission handling
    - Test permission request flow
    - Test rationale display logic
    - Test permission denied handling
    - _Requirements: 15.1, 15.2, 15.3, 15.4_

- [ ] 36. Implement Android Keystore integration
  - [ ] 36.1 Create cryptographic key management
    - Generate RSA-2048 or ECDSA P-256 key pair on first launch
    - Store keys in Android Keystore with hardware backing
    - Configure StrongBox security when available
    - Set key usage restrictions to signing only
    - Require user authentication for key usage (if biometric available)
    - Export public key for server registration
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_

  - [ ]* 36.2 Write property test for key uniqueness
    - **Property 20: Cryptographic Key Uniqueness**
    - **Validates: Requirements 12.1, 12.7**

  - [ ]* 36.3 Write unit tests for Keystore operations
    - Test key generation
    - Test hardware backing detection
    - Test key export
    - Test fallback to software keys
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_

- [ ] 37. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 38. Implement sensor data collection layer
  - [ ] 38.1 Create GPS sensor implementation
    - Implement LocationProvider interface using FusedLocationProviderClient
    - Request location with high accuracy mode
    - Capture latitude, longitude with 7 decimal precision
    - Capture altitude, accuracy, provider type, satellite count
    - Wait up to 30 seconds for GPS lock
    - Display warning if accuracy > 50 meters
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 30.1, 30.2, 30.3, 30.4, 30.5, 30.6_

  - [ ]* 38.2 Write property test for GPS precision preservation
    - **Property 7: GPS Coordinate Precision Preservation**
    - **Validates: Requirements 3.1, 3.7, 30.1, 30.2**

  - [ ] 38.3 Create WiFi scanner implementation
    - Implement WiFiScanner interface using WifiManager
    - Scan for nearby WiFi networks
    - Capture SSID, BSSID, signal strength (dBm), frequency
    - Capture at least 5 networks when available
    - Handle hidden networks (BSSID only)
    - Complete scanning within 3 seconds
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [ ] 38.4 Create cell tower scanner implementation
    - Implement CellTowerScanner interface using TelephonyManager
    - Capture Cell ID, LAC, MCC, MNC
    - Capture signal strength and network type (LTE, 5G, etc.)
    - Complete data retrieval within 2 seconds
    - Handle unavailable data gracefully
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [ ] 38.5 Create environmental sensor implementations
    - Implement BarometerSensor for pressure and altitude
    - Implement AmbientLightSensor for illuminance (lux)
    - Implement MagnetometerSensor for magnetic field (x, y, z, magnitude)
    - Implement MotionSensor for hand tremor detection (8-12Hz)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 38.6 Write unit tests for sensor implementations
    - Test GPS data capture and formatting
    - Test WiFi scanning and parsing
    - Test cell tower data extraction
    - Test environmental sensor readings
    - Test error handling for unavailable sensors
    - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 5.1, 5.2_

- [ ] 39. Implement location triangulation service
  - [ ] 39.1 Create sensor data aggregation
    - Implement LocationTriangulator interface
    - Collect GPS, WiFi, cell tower, environmental sensor data
    - Combine into SensorDataPackage
    - Calculate location confidence score based on sensor agreement
    - Flag discrepancies (e.g., GPS outdoor but WiFi indoor)
    - Preserve raw sensor data for forensic analysis
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 11.1_

  - [ ] 39.2 Create location hash generation
    - Generate SHA-256 hash from combined sensor data
    - Include GPS coordinates, WiFi BSSIDs, cell tower IDs
    - Use cryptographic salt from device key
    - Ensure deterministic hash generation
    - _Requirements: 6.5, 28.1, 28.2, 28.3_

  - [ ]* 39.3 Write property test for sensor data completeness
    - **Property 11: Sensor Data Completeness**
    - **Validates: Requirements 6.1, 6.4, 11.1**

  - [ ]* 39.4 Write unit tests for triangulation
    - Test sensor data aggregation
    - Test confidence score calculation
    - Test discrepancy detection
    - Test location hash generation
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [ ] 40. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 41. Implement photo capture module
  - [ ] 41.1 Create camera integration
    - Implement PhotoCaptureModule interface using CameraX
    - Access rear camera only (block front camera)
    - Display live camera preview within 2 seconds
    - Block access to device gallery and photo picker
    - Prevent screenshots during camera operation
    - Handle camera unavailable errors
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ] 41.2 Implement photo capture logic
    - Capture photo in JPEG format with 85% quality
    - Capture at device's maximum resolution (up to 4K)
    - Preserve EXIF metadata
    - Limit file size to 5MB through quality adjustment
    - Complete capture within 5 seconds
    - _Requirements: 16.1, 21.1, 21.2, 21.3, 21.4, 21.5, 21.6_

  - [ ]* 41.3 Write unit tests for camera module
    - Test rear camera enforcement
    - Test photo capture flow
    - Test quality and size constraints
    - Test error handling
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 16.1, 21.1, 21.2_

- [ ] 42. Implement watermark generation
  - [ ] 42.1 Create watermark overlay
    - Implement WatermarkGenerator interface
    - Overlay GPS coordinates (7 decimal places)
    - Overlay timestamp in ISO 8601 format
    - Overlay campaign code
    - Position in bottom 15% of image
    - Use semi-transparent black background
    - Use monospace font at minimum 14sp
    - Burn into JPEG pixel data (not EXIF)
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

  - [ ]* 42.2 Write property test for watermark position
    - **Property 19: Watermark Position Invariant**
    - **Validates: Requirements 11.2, 11.7**

  - [ ]* 42.3 Write property test for watermark persistence
    - **Property 6: Watermark Persistence Under Compression**
    - **Validates: Requirements 11.6, 11.7, 29.1, 29.2**

  - [ ]* 42.4 Write unit tests for watermark generation
    - Test watermark content formatting
    - Test watermark positioning
    - Test watermark readability
    - Test compression resistance
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

- [ ] 43. Implement cryptographic signing
  - [ ] 43.1 Create photo signature generation
    - Implement CryptoSigner interface
    - Generate SHA-256 hash of photo bytes
    - Sign hash with private key from Android Keystore
    - Include timestamp, location hash, device ID in signature
    - Use RSA-2048 or ECDSA P-256 algorithm
    - Complete signing within 500ms
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 16.4_

  - [ ]* 43.2 Write unit tests for signature generation
    - Test signature generation
    - Test signature format
    - Test signature uniqueness
    - Test performance (< 500ms)
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.6, 16.4_

- [ ] 44. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 45. Implement encryption and local storage
  - [ ] 45.1 Create encryption manager
    - Implement EncryptionManager interface
    - Encrypt photos using AES-256-GCM
    - Use keys from Android Keystore
    - Generate unique IV for each encryption
    - Store encrypted photos in app-private storage
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_

  - [ ]* 45.2 Write property test for encryption inverse
    - **Property 9: Encryption Inverse**
    - **Validates: Requirements 13.1, 13.2, 13.4**

  - [ ] 45.3 Create Room database entities
    - Define PhotoEntity with upload status
    - Define CampaignEntity with configuration
    - Define UserEntity with subscription info
    - Define AuditEntity with sync status
    - Configure SQLCipher encryption for database
    - _Requirements: 13.1, 13.2, 13.4_

  - [ ] 45.4 Create repository layer
    - Implement PhotoRepository for local photo storage
    - Implement CampaignRepository for campaign caching
    - Implement UserRepository for user data
    - Implement AuditRepository for audit logs
    - _Requirements: 13.1, 13.2, 13.4_

  - [ ]* 45.5 Write unit tests for encryption and storage
    - Test encryption/decryption round-trip
    - Test database operations
    - Test repository methods
    - _Requirements: 13.1, 13.2, 13.4_

- [ ] 46. Implement upload manager
  - [ ] 46.1 Create upload service
    - Implement UploadManager interface
    - Upload photo with multipart form data
    - Include signature and sensor data in payload
    - Use TLS 1.3 with certificate pinning
    - Delete photo from device after successful upload
    - Return upload receipt with server signature
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8_

  - [ ] 46.2 Implement retry logic
    - Retry failed uploads with exponential backoff (1s, 2s, 4s)
    - Limit to 3 retry attempts
    - Queue for later if all retries fail
    - Notify user of upload status
    - _Requirements: 9.4, 9.5, 22.1, 22.2, 22.3_

  - [ ]* 46.3 Write property test for retry exponential backoff
    - **Property 17: Upload Retry Exponential Backoff**
    - **Validates: Requirements 9.4, 22.1**

  - [ ] 46.3 Implement offline queue
    - Queue photos when network unavailable
    - Encrypt queued photos with AES-256-GCM
    - Limit queue to 50 photos maximum
    - Display pending uploads count in UI
    - Auto-upload when network restored (FIFO order)
    - Preserve original capture timestamp
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7_

  - [ ]* 46.4 Write property test for upload queue FIFO ordering
    - **Property 10: Upload Queue FIFO Ordering**
    - **Validates: Requirements 13.4, 13.7**

  - [ ]* 46.5 Write integration tests for upload manager
    - Test successful upload flow
    - Test retry logic
    - Test offline queueing
    - Test FIFO ordering
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 13.1, 13.4_

- [ ] 47. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 48. Implement campaign validation
  - [ ] 48.1 Create campaign validator
    - Implement CampaignValidator interface
    - Validate campaign code format (alphanumeric with hyphens)
    - Send validation request to server
    - Parse campaign configuration JSON
    - Cache validated campaigns locally
    - Handle network timeout (3 seconds)
    - Queue validation for retry if offline
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 25.1, 25.2, 25.5, 25.6_

  - [ ] 48.2 Implement configuration parser
    - Parse campaign configuration JSON to CampaignConfig object
    - Validate required fields (campaign_id, type, expiration_date)
    - Reject configurations with unknown fields
    - Format Configuration objects back to JSON (pretty printer)
    - _Requirements: 25.1, 25.2, 25.3, 25.5, 25.6_

  - [ ]* 48.3 Write property test for round-trip configuration parsing
    - **Property 1: Round-Trip Configuration Parsing**
    - **Validates: Requirements 25.4**

  - [ ]* 48.4 Write unit tests for campaign validation
    - Test campaign code format validation
    - Test server validation
    - Test configuration parsing
    - Test error handling
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 25.1, 25.2, 25.3_

- [ ] 49. Implement security features
  - [ ] 49.1 Create root detection
    - Check for Magisk, SuperSU, and other root management apps
    - Check for common root indicators in file system
    - Display warning if rooted device detected
    - Flag audit records from rooted devices
    - Allow continued use with warning
    - _Requirements: 23.1, 23.2, 23.3, 23.4, 23.5, 23.6_

  - [ ] 49.2 Implement SafetyNet attestation
    - Integrate Google Play Services SafetyNet API
    - Verify device integrity
    - Include attestation result in audit records
    - Handle attestation failures gracefully
    - _Requirements: 23.5, 23.6_

  - [ ] 49.3 Create emulator detection
    - Detect Android Studio emulator environment
    - Display "EMULATOR MODE" indicator
    - Use mock sensor data in emulator
    - Flag audit records from emulator
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7_

  - [ ]* 49.4 Write unit tests for security features
    - Test root detection logic
    - Test emulator detection
    - Test SafetyNet integration
    - _Requirements: 19.1, 19.2, 23.1, 23.2, 23.3_

- [ ] 50. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 51. Implement UI screens with Jetpack Compose
  - [ ] 51.1 Create vendor login screen
    - Build login form with phone number and vendor ID inputs
    - Implement OTP verification flow
    - Display error messages for invalid credentials
    - Handle device registration on first login
    - Navigate to campaign selection on success
    - _Requirements: 1.1, 1.4, 15.1, 15.2, 17.3_

  - [ ] 51.2 Create campaign selection screen
    - Display list of assigned campaigns
    - Show campaign name, code, type, dates
    - Implement campaign code entry field
    - Add QR code scanner button
    - Navigate to camera screen on selection
    - _Requirements: 1.1, 1.3, 1.4_

  - [ ] 51.3 Create camera screen
    - Display full-screen camera preview
    - Show sensor status indicators (GPS, WiFi, Cell, Light, Altitude)
    - Update sensor status every 1 second
    - Display warnings for low GPS accuracy
    - Show large centered capture button
    - Display instruction text overlay
    - Add back button and settings button
    - _Requirements: 2.1, 2.2, 2.3, 3.3, 16.1, 16.2, 16.3, 17.1_

  - [ ] 51.4 Create photo review screen
    - Display captured photo with watermark
    - Show sensor data summary (expandable)
    - Display verification status indicator
    - Add "Retake" button (left)
    - Add "Submit" button (right, primary)
    - Navigate to upload progress on submit
    - _Requirements: 11.1, 11.2, 16.1, 16.5_

  - [ ] 51.5 Create upload progress screen
    - Display progress bar (0-100%)
    - Show status text (Encrypting, Uploading, Verifying)
    - Display photo thumbnail
    - Add cancel button (queues for later)
    - Show network speed indicator
    - Navigate to success screen on completion
    - _Requirements: 9.1, 9.6, 16.1, 17.6_

  - [ ] 51.6 Create success/dashboard screen
    - Display success message with checkmark animation
    - Show photo count for current campaign
    - Add "Capture Another" button
    - Display pending uploads indicator
    - Show recent photos grid (thumbnails)
    - _Requirements: 13.3, 16.1_

  - [ ] 51.7 Create settings screen
    - Build settings with sections (Account, Camera, Sensors, Upload, Privacy, Advanced)
    - Display account info (email, subscription tier, usage stats)
    - Add camera settings (quality, flash mode, grid overlay)
    - Add sensor settings (required sensors, GPS threshold, WiFi timeout)
    - Add upload settings (auto-upload, WiFi only, retry attempts)
    - Add privacy settings (biometric auth, auto-delete, diagnostic data)
    - Add advanced settings (developer mode, device info, public key, clear cache)
    - _Requirements: 15.1, 15.2, 16.1, 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7_

  - [ ]* 51.8 Write UI tests for screens
    - Test login flow
    - Test campaign selection
    - Test camera screen interactions
    - Test photo review and submission
    - Test settings changes
    - _Requirements: 1.1, 1.3, 1.4, 2.1, 2.2, 16.1_

- [ ] 52. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 53. Implement battery optimization
  - [ ] 53.1 Create GPS power management
    - Use low-power location mode when camera not active
    - Switch to high-accuracy mode when camera displayed
    - Cache location data for 30 seconds
    - Reuse cached location if accuracy within 10 meters
    - Release location resources within 5 seconds after capture
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_

  - [ ]* 53.2 Write property test for battery usage monotonicity
    - **Property 16: Battery Usage Monotonicity**
    - **Validates: Requirements 14.6**

  - [ ]* 53.3 Write unit tests for power management
    - Test location mode switching
    - Test location caching
    - Test resource release
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

- [ ] 54. Implement error handling and user feedback
  - [ ] 54.1 Create error message system
    - Display "GPS accuracy too low - move to open area" for low accuracy
    - Display "Upload failed - photo saved for retry" for network errors
    - Display "Camera permission required - enable in settings" for denied permission
    - Display "Device security not supported" for unavailable Keystore
    - Log errors and continue with available sensors
    - Display progress indicators during uploads
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7_

  - [ ]* 54.2 Write unit tests for error handling
    - Test error message display
    - Test graceful degradation
    - Test progress indicators
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7_

- [ ] 55. Implement multi-domain campaign configuration
  - [ ] 55.1 Create campaign type handlers
    - Handle construction campaigns (require safety compliance tags)
    - Handle insurance campaigns (allow multiple photos per claim)
    - Handle delivery campaigns (capture recipient signature)
    - Handle healthcare campaigns (enforce HIPAA-compliant encryption)
    - Handle property management campaigns (room-by-room organization)
    - Retrieve campaign configuration from server during validation
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.6, 18.7_

  - [ ]* 55.2 Write unit tests for campaign types
    - Test construction campaign requirements
    - Test insurance campaign multi-photo support
    - Test delivery campaign signature capture
    - Test healthcare campaign encryption
    - Test property management organization
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_

- [ ] 56. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 57. Implement emulator testing support
  - [ ] 57.1 Create mock sensor data providers
    - Detect emulator environment
    - Provide mock GPS coordinates from Android Studio location tools
    - Provide predefined mock WiFi network data
    - Provide predefined mock cell tower data
    - Provide mock environmental sensor readings
    - Use software-backed keys instead of hardware Keystore
    - Display "EMULATOR MODE" indicator in UI
    - Flag audit records as captured in emulator mode
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7_

  - [ ]* 57.2 Write unit tests for emulator mode
    - Test emulator detection
    - Test mock sensor data providers
    - Test software key fallback
    - Test audit record flagging
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7_

- [ ] 58. Implement GDPR compliance features
  - [ ] 58.1 Create privacy policy display
    - Display privacy policy on first launch
    - Obtain explicit consent before collecting location data
    - Allow users to export their data in JSON format
    - Implement data deletion request handling
    - Anonymize vendor IDs when privacy mode enabled
    - _Requirements: 24.1, 24.2, 24.3, 24.4, 24.5, 24.6, 24.7_

  - [ ]* 58.2 Write unit tests for privacy features
    - Test consent flow
    - Test data export
    - Test data deletion
    - Test anonymization
    - _Requirements: 24.1, 24.2, 24.3, 24.4, 24.5, 24.6_

- [ ] 59. Implement sensor data serialization
  - [ ] 59.1 Create JSON serialization
    - Serialize SensorDataPackage to JSON format
    - Include all GPS, WiFi, cell tower, environmental data
    - Format timestamps in ISO 8601 format
    - Format GPS coordinates as floating-point with 7 decimals
    - Include schema version field for backward compatibility
    - _Requirements: 26.1, 26.2, 26.3, 26.4, 26.5, 26.6_

  - [ ]* 59.2 Write property test for round-trip sensor data serialization
    - **Property 2: Round-Trip Sensor Data Serialization**
    - **Validates: Requirements 26.6**

  - [ ]* 59.3 Write unit tests for serialization
    - Test JSON structure
    - Test timestamp formatting
    - Test GPS precision preservation
    - Test schema versioning
    - _Requirements: 26.1, 26.2, 26.3, 26.4, 26.5_

- [ ] 60. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Phase 4: Integration and Testing

- [ ] 61. Implement end-to-end integration
  - [ ] 61.1 Wire backend services together
    - Connect authentication to all protected endpoints
    - Connect photo upload to verification workflow
    - Connect location matching to verification status
    - Connect audit logging to all photo captures
    - Connect subscription checking to upload endpoints
    - _Requirements: 1.1, 1.2, 7.5, 7.6, 9.1, 10.1_

  - [ ] 61.2 Wire web application to backend
    - Connect all API calls to backend endpoints
    - Implement JWT token refresh logic
    - Handle API errors gracefully
    - Implement loading states for all async operations
    - _Requirements: 1.1, 1.2_

  - [ ] 61.3 Wire Android app to backend
    - Connect vendor authentication to backend
    - Connect campaign validation to backend
    - Connect photo upload to backend
    - Implement certificate pinning for API calls
    - Handle network errors and retries
    - _Requirements: 1.1, 1.4, 9.1, 9.2_

  - [ ]* 61.4 Write end-to-end integration tests
    - Test complete web registration → vendor creation → Android login flow
    - Test campaign creation → vendor assignment → photo capture → upload
    - Test offline capture → queue → upload when online
    - Test location profile matching → verification status
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 7.5, 7.6, 9.1, 13.4_

- [ ] 62. Implement performance optimizations
  - [ ] 62.1 Optimize backend performance
    - Add database query indexes
    - Implement database connection pooling
    - Add Redis caching for frequently accessed data
    - Optimize photo upload with streaming
    - Implement API response compression
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6_

  - [ ] 62.2 Optimize web application performance
    - Implement code splitting and lazy loading
    - Optimize image loading with lazy loading
    - Add service worker for offline support
    - Implement virtual scrolling for large lists
    - Optimize bundle size
    - _Requirements: 16.1, 16.2_

  - [ ] 62.3 Optimize Android app performance
    - Optimize camera preview rendering
    - Implement background sensor data collection
    - Optimize image compression
    - Implement efficient database queries
    - Reduce memory footprint
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6_

  - [ ]* 62.4 Write performance tests
    - Test API response times (p95 < 500ms for validation)
    - Test photo upload time (< 10 seconds on 4G/5G)
    - Test camera preview load time (< 2 seconds)
    - Test signature generation time (< 500ms)
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_

- [ ] 63. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 64. Implement comprehensive testing
  - [ ] 64.1 Create property-based test suite
    - Implement all 20 correctness properties from requirements
    - Use Hypothesis for Python backend tests
    - Use Kotest for Kotlin Android tests
    - Generate test reports with coverage
    - _Requirements: All property requirements (1-20)_

  - [ ] 64.2 Create integration test suite
    - Test all API endpoints with valid/invalid inputs
    - Test authentication and authorization flows
    - Test photo upload and verification workflows
    - Test subscription and payment flows
    - Test report generation
    - _Requirements: 1.1, 1.2, 7.5, 7.6, 9.1, 9.2_

  - [ ] 64.3 Create UI test suite
    - Test web application user flows
    - Test Android application user flows
    - Test responsive design on multiple screen sizes
    - Test accessibility with screen readers
    - _Requirements: 20_

  - [ ] 64.4 Create security test suite
    - Test signature verification with tampered photos
    - Test authentication with invalid tokens
    - Test authorization with unauthorized access attempts
    - Test SQL injection prevention
    - Test XSS prevention
    - _Requirements: 8.1, 8.7, 27.3, 27.6_

  - [ ]* 64.5 Run full test suite and generate coverage report
    - Run all unit tests
    - Run all integration tests
    - Run all property-based tests
    - Generate coverage report (target 80%+)
    - Fix any failing tests
    - _Requirements: All requirements_

- [ ] 65. Implement monitoring and logging
  - [ ] 65.1 Set up backend monitoring
    - Configure CloudWatch metrics and alarms
    - Set up error tracking with Sentry
    - Implement structured logging
    - Create dashboards for key metrics
    - Set up alerts for high error rates
    - _Requirements: 22.1, 22.2, 22.3, 22.4_

  - [ ] 65.2 Set up web application monitoring
    - Integrate Sentry for error tracking
    - Implement analytics tracking
    - Monitor page load times
    - Track user interactions
    - _Requirements: 22.1, 22.2_

  - [ ] 65.3 Set up Android app monitoring
    - Integrate Firebase Crashlytics
    - Implement analytics tracking
    - Monitor app performance
    - Track upload success rates
    - _Requirements: 22.1, 22.2, 22.3, 22.4, 22.5, 22.6, 22.7_

- [ ] 66. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Phase 5: Deployment and Release

- [ ] 67. Set up deployment infrastructure
  - [ ] 67.1 Configure AWS infrastructure
    - Set up VPC with public and private subnets
    - Configure RDS PostgreSQL Multi-AZ instance
    - Set up ElastiCache Redis cluster
    - Configure S3 buckets with versioning and lifecycle policies
    - Set up DynamoDB table for audit logs
    - Configure CloudFront CDN for photo delivery
    - Set up Application Load Balancer
    - Configure ECS cluster with Fargate
    - _Requirements: 20_

  - [ ] 67.2 Create Docker containers
    - Create Dockerfile for FastAPI backend
    - Optimize Docker image size
    - Configure health checks
    - Set up docker-compose for local development
    - Push images to Amazon ECR
    - _Requirements: 20_

  - [ ] 67.3 Configure environment variables
    - Set up AWS Secrets Manager for sensitive data
    - Configure environment-specific variables (dev, staging, prod)
    - Set up database connection strings
    - Configure API keys (Stripe, Twilio, SendGrid)
    - _Requirements: 20_

- [ ] 68. Set up CI/CD pipelines
  - [ ] 68.1 Create backend CI/CD pipeline
    - Configure GitHub Actions workflow
    - Run tests on every push
    - Run security scans (Snyk)
    - Build Docker image
    - Deploy to ECS on merge to main
    - Implement blue-green deployment
    - _Requirements: 20_

  - [ ] 68.2 Create web application CI/CD pipeline
    - Configure GitHub Actions workflow
    - Run tests and linting
    - Build production bundle
    - Deploy to Vercel/Netlify on merge to main
    - Configure custom domain and SSL
    - _Requirements: 20_

  - [ ] 68.3 Create Android CI/CD pipeline
    - Configure GitHub Actions workflow
    - Run unit tests and lint checks
    - Build signed APK/AAB
    - Upload to Google Play Console (internal testing)
    - Automate version bumping
    - _Requirements: 20_

- [ ] 69. Checkpoint - Ensure all deployments successful
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 70. Prepare for production release
  - [ ] 70.1 Create production database
    - Run database migrations on production RDS
    - Set up automated backups (daily, 30-day retention)
    - Configure point-in-time recovery
    - Set up read replicas for reporting queries
    - _Requirements: 20_

  - [ ] 70.2 Configure production security
    - Enable AWS WAF for DDoS protection
    - Configure security groups and NACLs
    - Set up CloudTrail for audit logging
    - Enable GuardDuty for threat detection
    - Configure SSL/TLS certificates
    - _Requirements: 20_

  - [ ] 70.3 Set up production monitoring
    - Configure CloudWatch dashboards
    - Set up alarms for critical metrics
    - Configure SNS notifications for on-call team
    - Set up log aggregation
    - Configure uptime monitoring
    - _Requirements: 22.1, 22.2, 22.3, 22.4_

- [ ] 71. Conduct security audit
  - [ ] 71.1 Perform penetration testing
    - Test API endpoints for vulnerabilities
    - Test authentication and authorization
    - Test for SQL injection and XSS
    - Test cryptographic implementations
    - Test for sensitive data exposure
    - _Requirements: 8.1, 8.7, 27.1, 27.3_

  - [ ] 71.2 Review security configurations
    - Review AWS security groups
    - Review IAM policies and roles
    - Review database access controls
    - Review API rate limiting
    - Review encryption configurations
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 9.2, 12.1, 12.2_

  - [ ] 71.3 Document security findings
    - Create security audit report
    - Document vulnerabilities found
    - Implement fixes for critical issues
    - Create remediation plan for non-critical issues
    - _Requirements: 8.1, 8.7_

- [ ] 72. Prepare release documentation
  - [ ] 72.1 Create API documentation
    - Document all API endpoints
    - Provide request/response examples
    - Document authentication requirements
    - Create Postman collection
    - _Requirements: 20_

  - [ ] 72.2 Create user documentation
    - Write web application user guide
    - Write Android app user guide
    - Create video tutorials
    - Document common troubleshooting steps
    - _Requirements: 20_

  - [ ] 72.3 Create developer documentation
    - Document architecture and design decisions
    - Create setup guides for local development
    - Document deployment procedures
    - Create contribution guidelines
    - _Requirements: 20_

- [ ] 73. Checkpoint - Ensure all documentation complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 74. Conduct beta testing
  - [ ] 74.1 Release to internal testing
    - Deploy to staging environment
    - Invite 10-20 team members to test
    - Collect feedback via surveys
    - Monitor crash reports and errors
    - Fix critical bugs
    - _Requirements: 20_

  - [ ] 74.2 Release to closed beta
    - Upload Android app to Google Play Internal Testing
    - Invite 100-500 beta testers
    - Monitor usage metrics and crash rates
    - Collect user feedback
    - Iterate on UI/UX based on feedback
    - _Requirements: 20_

  - [ ] 74.3 Release to open beta
    - Promote to Google Play Beta track
    - Invite 1000+ users
    - Monitor performance and stability
    - Track upload success rates
    - Address reported issues
    - _Requirements: 22.1, 22.2, 22.3, 22.4_

- [ ] 75. Prepare for production launch
  - [ ] 75.1 Finalize production configurations
    - Review all environment variables
    - Verify API keys and credentials
    - Test payment integration with live Stripe keys
    - Verify SMS delivery with Twilio
    - Test email delivery with SendGrid
    - _Requirements: 20_

  - [ ] 75.2 Create launch checklist
    - Verify all tests passing
    - Verify security audit complete
    - Verify documentation complete
    - Verify monitoring and alerting configured
    - Verify backup and disaster recovery procedures
    - _Requirements: 20_

  - [ ] 75.3 Plan staged rollout
    - Start with 10% of users
    - Monitor metrics for 24 hours
    - Increase to 50% if stable
    - Monitor for another 24 hours
    - Roll out to 100% if no issues
    - _Requirements: 20_

- [ ] 76. Launch production release
  - [ ] 76.1 Deploy backend to production
    - Deploy FastAPI backend to ECS
    - Verify health checks passing
    - Monitor error rates and latency
    - Verify database connections
    - _Requirements: 20_

  - [ ] 76.2 Deploy web application to production
    - Deploy React app to Vercel/Netlify
    - Verify custom domain and SSL
    - Test all user flows
    - Monitor page load times
    - _Requirements: 20_

  - [ ] 76.3 Release Android app to production
    - Upload signed AAB to Google Play Console
    - Submit for review
    - Implement staged rollout (10% → 50% → 100%)
    - Monitor crash rates and user reviews
    - _Requirements: 20_

  - [ ] 76.4 Monitor production launch
    - Monitor all metrics for first 48 hours
    - Be on-call for critical issues
    - Respond to user feedback
    - Prepare hotfix releases if needed
    - _Requirements: 22.1, 22.2, 22.3, 22.4_

- [ ] 77. Final checkpoint - Production launch complete
  - Ensure all systems operational, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional testing tasks and can be skipped for faster MVP delivery
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation and quality
- Property tests validate universal correctness properties from the requirements document
- Unit and integration tests validate specific examples and edge cases
- The implementation follows a bottom-up approach: backend foundation → web UI → Android app → integration
- All cryptographic operations use industry-standard algorithms and hardware-backed security when available
- The system is designed for offline-first operation with automatic sync when network is available
- Multi-sensor triangulation makes GPS spoofing impractical by requiring WiFi, cell tower, and environmental sensor data
- The architecture supports multiple industries through configurable campaign types
- Performance targets: < 2s camera load, < 5s photo capture, < 10s upload on 4G/5G, < 500ms signature generation
