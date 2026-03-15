# Design Document: TrustCapture Android App

## Overview

TrustCapture is a dual-platform system consisting of:

1. **Web Application**: Client management portal for registration, vendor management, campaign creation, and reporting
2. **Android Application**: Field worker app for tamper-proof photo capture with multi-sensor verification

The system provides forensic-grade photo verification through multi-sensor geolocation triangulation, environmental context validation, and cryptographic integrity. It creates tamper-proof evidence by capturing GPS coordinates, Wi-Fi fingerprints, cell tower data, and environmental sensor readings (barometer, ambient light, magnetometer, accelerometer/gyroscope), then cryptographically signing photos with hardware-backed device keys before secure upload.

### System Architecture Philosophy

**Web App (Client-Facing)**:
- Client registration and subscription management
- Vendor/sub-vendor registration and ID generation
- Campaign creation and configuration
- Photo gallery and verification dashboard
- Report generation and export (CSV, GeoJSON, PDF)
- Analytics and insights
- Team management and permissions

**Android App (Field Worker-Facing)**:
- Photo capture ONLY (no registration, no management)
- Requires vendor ID generated from web app
- Multi-sensor data collection
- Offline-first with upload queue
- Minimal UI focused on capture workflow

### Core Value Proposition

TrustCapture prevents photo fraud by making it computationally and physically impractical to spoof all verification layers simultaneously. Unlike single-sensor solutions, our multi-layered approach creates a "location fingerprint" that includes:

- **Geolocation triangulation**: GPS + Wi-Fi + Cell tower data
- **Environmental context**: Barometric pressure, ambient light levels, magnetic field signatures
- **Human verification**: Physiological hand tremor detection (8-12Hz) proving handheld capture
- **Cryptographic integrity**: Hardware-backed signing with Android Keystore
- **Visual tamper evidence**: Burned-in watermarks that degrade under editing
- **Role-based access**: Clients manage vendors, vendors capture photos

### Target Industries

- Out-of-Home advertising verification
- Construction progress documentation
- Insurance claims processing
- Delivery logistics proof-of-delivery
- Healthcare compliance documentation
- Property management inspections

### Competitive Differentiation

**vs CompanyCam**: Stronger cryptographic verification, environmental sensors, hardware-backed security, web-based client portal
**vs VeraSnap**: More comprehensive sensor suite, offline-first architecture, team collaboration features, vendor management
**vs Timemark**: Multi-sensor triangulation, location profile matching, enterprise-grade audit trails, separate client/vendor interfaces


## Architecture

### High-Level System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    TrustCapture Web Application                   │
│                    (React + TypeScript)                           │
├──────────────────────────────────────────────────────────────────┤
│  Client Portal                                                    │
│  ├─ Registration & Login                                          │
│  ├─ Subscription Management (Stripe)                              │
│  ├─ Vendor Management (Create/Edit/Deactivate)                    │
│  ├─ Campaign Creation & Configuration                             │
│  ├─ Photo Gallery & Verification Dashboard                        │
│  ├─ Reports & Analytics (CSV, GeoJSON, PDF export)                │
│  ├─ Map Visualization (Mapbox/OpenStreetMap)                      │
│  └─ Team & Permission Management                                  │
└──────────────────────────────────────────────────────────────────┘
                              ↓ HTTPS
┌──────────────────────────────────────────────────────────────────┐
│                     TrustCapture Android App                      │
│                     (Kotlin + Jetpack Compose)                    │
├──────────────────────────────────────────────────────────────────┤
│  Presentation Layer                                               │
│  ├─ Vendor Login (Phone + Vendor ID)                              │
│  ├─ Campaign Selection                                            │
│  ├─ Camera Screen (Photo Capture ONLY)                            │
│  ├─ Photo Review Screen                                           │
│  └─ Upload Progress & Queue Management                            │
├──────────────────────────────────────────────────────────────────┤
│  Sensor Integration Layer                                         │
│  ├─ GPS_Sensor, WiFi_Scanner, Cell_Tower_Scanner                  │
│  ├─ Barometer, Light_Sensor, Magnetometer                         │
│  └─ Accelerometer, Gyroscope (Hand Tremor)                        │
├──────────────────────────────────────────────────────────────────┤
│  Security & Crypto Layer                                          │
│  ├─ Android Keystore (Hardware-backed signing)                    │
│  ├─ AES-256-GCM Encryption                                        │
│  └─ Root Detection, SafetyNet Attestation                         │
├──────────────────────────────────────────────────────────────────┤
│  Local Storage (Offline-First)                                    │
│  ├─ Room Database (Encrypted)                                     │
│  └─ Upload Queue (Encrypted pending photos)                       │
└──────────────────────────────────────────────────────────────────┘
                              ↓ TLS 1.3
┌──────────────────────────────────────────────────────────────────┐
│                  Backend Services (Python/FastAPI)                │
├──────────────────────────────────────────────────────────────────┤
│  API Layer (FastAPI + Pydantic)                                   │
│  ├─ /api/auth/* - Authentication & Authorization                  │
│  ├─ /api/clients/* - Client registration & management             │
│  ├─ /api/vendors/* - Vendor CRUD & ID generation                  │
│  ├─ /api/campaigns/* - Campaign management                        │
│  ├─ /api/photos/* - Photo upload & verification                   │
│  ├─ /api/reports/* - Report generation & export                   │
│  └─ /api/subscriptions/* - Stripe webhook handling                │
├──────────────────────────────────────────────────────────────────┤
│  Business Logic Layer                                             │
│  ├─ Photo Verification Service (Signature validation)             │
│  ├─ Location Profile Matcher                                      │
│  ├─ Sensor Data Analyzer                                          │
│  ├─ Report Generator (CSV, GeoJSON, PDF)                          │
│  └─ Notification Service (Email, SMS, Push)                       │
├──────────────────────────────────────────────────────────────────┤
│  Data Layer                                                       │
│  ├─ PostgreSQL 15+ (Primary database)                             │
│  │   ├─ clients, vendors, campaigns, photos                       │
│  │   ├─ subscriptions, teams, permissions                         │
│  │   └─ sensor_data, location_profiles                            │
│  ├─ DynamoDB (Immutable audit logs)                               │
│  ├─ Redis (Session cache, rate limiting)                          │
│  └─ AWS S3 (Photo storage with versioning)                        │
├──────────────────────────────────────────────────────────────────┤
│  External Services                                                │
│  ├─ Stripe API (Payment processing)                               │
│  ├─ Twilio (SMS for vendor ID delivery)                           │
│  ├─ SendGrid (Email notifications)                                │
│  ├─ Firebase Cloud Messaging (Push to Android)                    │
│  └─ OpenWeatherMap (Barometer validation)                         │
└──────────────────────────────────────────────────────────────────┘
```

### User Flow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT FLOW                              │
└─────────────────────────────────────────────────────────────────┘

1. Client Registration (Web App)
   ├─ Email + Password + Phone Number
   ├─ Company Details
   ├─ Select Subscription Tier (Free/Pro/Enterprise)
   └─ Payment (Stripe) → Client ID generated

2. Vendor Management (Web App)
   ├─ Add Vendor: Name + Phone Number
   ├─ System generates unique Vendor ID
   ├─ SMS sent to vendor with Vendor ID + Download link
   └─ Client can view/edit/deactivate vendors

3. Campaign Creation (Web App)
   ├─ Campaign Name + Type (OOH, Construction, etc.)
   ├─ Location Profile (Expected GPS, WiFi, Cell towers)
   ├─ Assign Vendors to Campaign
   └─ Generate Campaign Code

4. Monitoring & Reports (Web App)
   ├─ View uploaded photos in gallery
   ├─ Verification status dashboard
   ├─ Map visualization with photo markers
   ├─ Export reports (CSV, GeoJSON, PDF)
   └─ Analytics (distance metrics, compliance rate)

┌─────────────────────────────────────────────────────────────────┐
│                         VENDOR FLOW                              │
└─────────────────────────────────────────────────────────────────┘

1. Vendor Onboarding (Android App)
   ├─ Download app from SMS link
   ├─ Enter Phone Number + Vendor ID (received via SMS)
   ├─ OTP verification
   └─ Device registered with hardware key generation

2. Campaign Selection (Android App)
   ├─ View assigned campaigns
   ├─ Select active campaign
   └─ Enter Campaign Code (or scan QR)

3. Photo Capture (Android App)
   ├─ Camera screen with sensor status
   ├─ Capture photo with multi-sensor data
   ├─ Review photo with watermark
   └─ Upload (or queue if offline)

4. Offline Mode (Android App)
   ├─ Capture photos without network
   ├─ Encrypted local storage (max 50 photos)
   ├─ Auto-upload when network available
   └─ Notification on upload completion
```

### Architecture Patterns

**Web Application**:
- **Framework**: React 18+ with TypeScript
- **State Management**: Redux Toolkit or Zustand
- **Routing**: React Router v6
- **UI Library**: Material-UI (MUI) or Ant Design
- **Forms**: React Hook Form + Zod validation
- **Data Fetching**: TanStack Query (React Query)
- **Maps**: Mapbox GL JS or Leaflet (OpenStreetMap)
- **Charts**: Recharts or Chart.js
- **Authentication**: JWT tokens in httpOnly cookies

**Android Application**:
- **Pattern**: MVVM (Model-View-ViewModel)
- **Architecture**: Clean Architecture (Domain/Data/Presentation layers)
- **Repository Pattern**: Abstraction for data sources
- **Use Case Pattern**: Single-responsibility business logic
- **Dependency Injection**: Hilt
- **Offline-First**: Local-first data with background sync
- **Reactive**: StateFlow/LiveData for UI updates

**Backend (Python/FastAPI)**:
- **Pattern**: Layered Architecture
  - API Layer (FastAPI routers)
  - Service Layer (Business logic)
  - Repository Layer (Database access)
  - Model Layer (Pydantic schemas + SQLAlchemy models)
- **Async**: async/await for I/O operations
- **Dependency Injection**: FastAPI's built-in DI
- **Validation**: Pydantic models
- **ORM**: SQLAlchemy 2.0 (async)


## Components and Interfaces

## Web Application Components

### 1. Client Management Module

#### Client Registration & Authentication
```python
# FastAPI Backend
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
import bcrypt
import jwt

router = APIRouter(prefix="/api/clients", tags=["clients"])

class ClientRegistration(BaseModel):
    email: EmailStr
    password: str
    company_name: str
    phone_number: str
    subscription_tier: str  # "free", "pro", "enterprise"

class ClientResponse(BaseModel):
    client_id: str
    email: str
    company_name: str
    subscription_tier: str
    created_at: datetime

@router.post("/register", response_model=ClientResponse)
async def register_client(data: ClientRegistration, db: Session = Depends(get_db)):
    # Check if email exists
    existing = db.query(Client).filter(Client.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash password
    hashed_password = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt())
    
    # Create client
    client = Client(
        client_id=str(uuid.uuid4()),
        email=data.email,
        password_hash=hashed_password,
        company_name=data.company_name,
        phone_number=data.phone_number,
        subscription_tier=data.subscription_tier,
        created_at=datetime.utcnow()
    )
    db.add(client)
    db.commit()
    
    # Send welcome email
    await send_welcome_email(client.email, client.company_name)
    
    return ClientResponse.from_orm(client)

@router.post("/login")
async def login_client(email: EmailStr, password: str, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.email == email).first()
    if not client or not bcrypt.checkpw(password.encode(), client.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Generate JWT token
    token = jwt.encode({
        "client_id": client.client_id,
        "email": client.email,
        "exp": datetime.utcnow() + timedelta(days=7)
    }, SECRET_KEY, algorithm="HS256")
    
    return {"access_token": token, "token_type": "bearer"}
```

```typescript
// React Frontend
interface ClientRegistrationForm {
  email: string;
  password: string;
  companyName: string;
  phoneNumber: string;
  subscriptionTier: 'free' | 'pro' | 'enterprise';
}

const ClientRegistration: React.FC = () => {
  const { register, handleSubmit, formState: { errors } } = useForm<ClientRegistrationForm>();
  const navigate = useNavigate();
  
  const onSubmit = async (data: ClientRegistrationForm) => {
    try {
      const response = await fetch('/api/clients/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      
      if (response.ok) {
        navigate('/dashboard');
      }
    } catch (error) {
      console.error('Registration failed:', error);
    }
  };
  
  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <TextField {...register('email', { required: true })} label="Email" />
      <TextField {...register('password', { required: true, minLength: 8 })} type="password" label="Password" />
      <TextField {...register('companyName', { required: true })} label="Company Name" />
      <TextField {...register('phoneNumber', { required: true })} label="Phone Number" />
      <Select {...register('subscriptionTier')} label="Subscription Tier">
        <MenuItem value="free">Free</MenuItem>
        <MenuItem value="pro">Pro</MenuItem>
        <MenuItem value="enterprise">Enterprise</MenuItem>
      </Select>
      <Button type="submit">Register</Button>
    </form>
  );
};
```

### 2. Vendor Management Module

#### Vendor CRUD Operations
```python
# FastAPI Backend
class VendorCreate(BaseModel):
    name: str
    phone_number: str
    email: Optional[EmailStr] = None

class VendorResponse(BaseModel):
    vendor_id: str
    name: str
    phone_number: str
    email: Optional[str]
    status: str  # "active", "inactive"
    created_at: datetime
    created_by_client_id: str

@router.post("/vendors", response_model=VendorResponse)
async def create_vendor(
    data: VendorCreate,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    # Generate unique vendor ID (6-digit alphanumeric)
    vendor_id = generate_vendor_id()
    
    vendor = Vendor(
        vendor_id=vendor_id,
        name=data.name,
        phone_number=data.phone_number,
        email=data.email,
        status="active",
        created_by_client_id=current_client.client_id,
        created_at=datetime.utcnow()
    )
    db.add(vendor)
    db.commit()
    
    # Send SMS with vendor ID and app download link
    await send_vendor_sms(
        phone_number=data.phone_number,
        vendor_id=vendor_id,
        client_name=current_client.company_name
    )
    
    return VendorResponse.from_orm(vendor)

@router.get("/vendors", response_model=List[VendorResponse])
async def list_vendors(
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    vendors = db.query(Vendor).filter(
        Vendor.created_by_client_id == current_client.client_id
    ).all()
    return [VendorResponse.from_orm(v) for v in vendors]

@router.patch("/vendors/{vendor_id}/deactivate")
async def deactivate_vendor(
    vendor_id: str,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    vendor = db.query(Vendor).filter(
        Vendor.vendor_id == vendor_id,
        Vendor.created_by_client_id == current_client.client_id
    ).first()
    
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    vendor.status = "inactive"
    db.commit()
    
    return {"message": "Vendor deactivated successfully"}

def generate_vendor_id() -> str:
    """Generate 6-character alphanumeric vendor ID"""
    import random
    import string
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=6))
```

```typescript
// React Frontend - Vendor Management Component
interface Vendor {
  vendorId: string;
  name: string;
  phoneNumber: string;
  email?: string;
  status: 'active' | 'inactive';
  createdAt: string;
}

const VendorManagement: React.FC = () => {
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [showAddDialog, setShowAddDialog] = useState(false);
  
  const { data, isLoading } = useQuery('vendors', async () => {
    const response = await fetch('/api/vendors', {
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });
    return response.json();
  });
  
  const addVendorMutation = useMutation(async (vendor: VendorCreate) => {
    const response = await fetch('/api/vendors', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken()}`
      },
      body: JSON.stringify(vendor)
    });
    return response.json();
  });
  
  return (
    <Box>
      <Button onClick={() => setShowAddDialog(true)}>Add Vendor</Button>
      <DataGrid
        rows={vendors}
        columns={[
          { field: 'vendorId', headerName: 'Vendor ID', width: 120 },
          { field: 'name', headerName: 'Name', width: 200 },
          { field: 'phoneNumber', headerName: 'Phone', width: 150 },
          { field: 'status', headerName: 'Status', width: 100 },
          {
            field: 'actions',
            headerName: 'Actions',
            renderCell: (params) => (
              <>
                <IconButton onClick={() => handleEdit(params.row)}>
                  <EditIcon />
                </IconButton>
                <IconButton onClick={() => handleDeactivate(params.row.vendorId)}>
                  <DeleteIcon />
                </IconButton>
              </>
            )
          }
        ]}
      />
    </Box>
  );
};
```

### 3. Campaign Management Module

```python
# FastAPI Backend
class CampaignCreate(BaseModel):
    name: str
    campaign_type: str  # "ooh", "construction", "insurance", etc.
    location_profile: Optional[LocationProfileCreate]
    assigned_vendor_ids: List[str]
    start_date: datetime
    end_date: datetime

class LocationProfileCreate(BaseModel):
    expected_latitude: float
    expected_longitude: float
    tolerance_meters: float = 50.0
    expected_wifi_bssids: Optional[List[str]] = None
    expected_cell_tower_ids: Optional[List[int]] = None

@router.post("/campaigns", response_model=CampaignResponse)
async def create_campaign(
    data: CampaignCreate,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    # Generate campaign code
    campaign_code = generate_campaign_code(data.name)
    
    campaign = Campaign(
        campaign_id=str(uuid.uuid4()),
        campaign_code=campaign_code,
        name=data.name,
        campaign_type=data.campaign_type,
        client_id=current_client.client_id,
        start_date=data.start_date,
        end_date=data.end_date,
        created_at=datetime.utcnow()
    )
    db.add(campaign)
    
    # Create location profile if provided
    if data.location_profile:
        profile = LocationProfile(
            campaign_id=campaign.campaign_id,
            **data.location_profile.dict()
        )
        db.add(profile)
    
    # Assign vendors
    for vendor_id in data.assigned_vendor_ids:
        assignment = CampaignVendorAssignment(
            campaign_id=campaign.campaign_id,
            vendor_id=vendor_id
        )
        db.add(assignment)
    
    db.commit()
    
    # Notify vendors via SMS
    for vendor_id in data.assigned_vendor_ids:
        vendor = db.query(Vendor).filter(Vendor.vendor_id == vendor_id).first()
        if vendor:
            await send_campaign_assignment_sms(
                phone_number=vendor.phone_number,
                campaign_name=data.name,
                campaign_code=campaign_code
            )
    
    return CampaignResponse.from_orm(campaign)
```

### 4. Photo Gallery & Dashboard Module

```typescript
// React Frontend - Photo Gallery
interface Photo {
  photoId: string;
  campaignCode: string;
  vendorId: string;
  captureTimestamp: string;
  thumbnailUrl: string;
  verificationStatus: 'verified' | 'flagged' | 'rejected';
  gpsCoordinates: { lat: number; lng: number };
  distanceFromExpected?: number;
}

const PhotoGallery: React.FC<{ campaignId: string }> = ({ campaignId }) => {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [selectedPhoto, setSelectedPhoto] = useState<Photo | null>(null);
  const [viewMode, setViewMode] = useState<'grid' | 'map'>('grid');
  
  const { data } = useQuery(['photos', campaignId], async () => {
    const response = await fetch(`/api/campaigns/${campaignId}/photos`, {
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });
    return response.json();
  });
  
  return (
    <Box>
      <ToggleButtonGroup value={viewMode} exclusive onChange={(e, val) => setViewMode(val)}>
        <ToggleButton value="grid">
          <GridViewIcon />
        </ToggleButton>
        <ToggleButton value="map">
          <MapIcon />
        </ToggleButton>
      </ToggleButtonGroup>
      
      {viewMode === 'grid' ? (
        <ImageList cols={4} gap={8}>
          {photos.map((photo) => (
            <ImageListItem key={photo.photoId} onClick={() => setSelectedPhoto(photo)}>
              <img src={photo.thumbnailUrl} alt={photo.photoId} />
              <ImageListItemBar
                title={new Date(photo.captureTimestamp).toLocaleString()}
                subtitle={`Status: ${photo.verificationStatus}`}
                actionIcon={
                  <Chip
                    label={photo.verificationStatus}
                    color={photo.verificationStatus === 'verified' ? 'success' : 'warning'}
                    size="small"
                  />
                }
              />
            </ImageListItem>
          ))}
        </ImageList>
      ) : (
        <MapView photos={photos} onPhotoClick={setSelectedPhoto} />
      )}
      
      {selectedPhoto && (
        <PhotoDetailDialog photo={selectedPhoto} onClose={() => setSelectedPhoto(null)} />
      )}
    </Box>
  );
};
```

### 5. Report Generation Module

```python
# FastAPI Backend - Report Generation
@router.get("/campaigns/{campaign_id}/export/csv")
async def export_campaign_csv(
    campaign_id: str,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    # Verify campaign belongs to client
    campaign = db.query(Campaign).filter(
        Campaign.campaign_id == campaign_id,
        Campaign.client_id == current_client.client_id
    ).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get all photos for campaign
    photos = db.query(Photo).filter(Photo.campaign_id == campaign_id).all()
    
    # Generate CSV
    csv_content = generate_csv_report(photos)
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=campaign_{campaign_id}_{datetime.now().strftime('%Y%m%d')}.csv"
        }
    )

@router.get("/campaigns/{campaign_id}/export/geojson")
async def export_campaign_geojson(
    campaign_id: str,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    photos = db.query(Photo).filter(Photo.campaign_id == campaign_id).all()
    geojson = generate_geojson_report(photos)
    
    return Response(
        content=geojson,
        media_type="application/geo+json",
        headers={
            "Content-Disposition": f"attachment; filename=campaign_{campaign_id}_{datetime.now().strftime('%Y%m%d')}.geojson"
        }
    )
```

## Android Application Components (Vendor-Facing)

### 1. Sensor Integration Layer

#### GPS_Sensor
```kotlin
interface LocationProvider {
    suspend fun getCurrentLocation(timeout: Duration): Result<LocationData>
    fun startLocationUpdates(callback: (LocationData) -> Unit)
    fun stopLocationUpdates()
}

data class LocationData(
    val latitude: Double,      // 7 decimal precision
    val longitude: Double,     // 7 decimal precision
    val altitude: Double?,
    val accuracy: Float,       // meters
    val verticalAccuracy: Float?,
    val provider: LocationProvider, // GPS, NETWORK, FUSED
    val satelliteCount: Int?,
    val timestamp: Instant
)
```

#### WiFi_Scanner
```kotlin
interface WiFiScanner {
    suspend fun scanNetworks(timeout: Duration): Result<List<WiFiNetwork>>
    fun isWiFiEnabled(): Boolean
}

data class WiFiNetwork(
    val ssid: String?,         // null for hidden networks
    val bssid: String,         // MAC address
    val signalStrength: Int,   // dBm
    val frequency: Int,        // MHz
    val timestamp: Instant
)
```

#### Cell_Tower_Scanner
```kotlin
interface CellTowerScanner {
    suspend fun getCellInfo(): Result<List<CellTowerInfo>>
}

data class CellTowerInfo(
    val cellId: Long,
    val locationAreaCode: Int,
    val mobileCountryCode: Int,
    val mobileNetworkCode: Int,
    val signalStrength: Int,   // dBm
    val networkType: NetworkType, // LTE, 5G, GSM, CDMA
    val timestamp: Instant
)
```

#### Environmental Sensors (New)
```kotlin
interface BarometerSensor {
    suspend fun getPressure(): Result<BarometerData>
}

data class BarometerData(
    val pressure: Float,       // hPa (hectopascals)
    val altitude: Float?,      // meters (derived)
    val timestamp: Instant
)

interface AmbientLightSensor {
    suspend fun getLightLevel(): Result<LightData>
}

data class LightData(
    val illuminance: Float,    // lux
    val timestamp: Instant
)

interface MagnetometerSensor {
    suspend fun getMagneticField(): Result<MagneticData>
}

data class MagneticData(
    val x: Float,              // μT (microtesla)
    val y: Float,
    val z: Float,
    val magnitude: Float,
    val timestamp: Instant
)

interface MotionSensor {
    suspend fun analyzeHandTremor(duration: Duration): Result<TremorData>
}

data class TremorData(
    val dominantFrequency: Float,  // Hz
    val isHumanTremor: Boolean,    // 8-12Hz range
    val confidence: Float,         // 0.0-1.0
    val timestamp: Instant
)
```


### 2. Location Triangulation and Validation

#### Location_Triangulator
```kotlin
interface LocationTriangulator {
    suspend fun collectSensorData(): Result<SensorDataPackage>
    fun calculateLocationConfidence(data: SensorDataPackage): Float
    fun generateLocationHash(data: SensorDataPackage): String
}

data class SensorDataPackage(
    val gps: LocationData?,
    val wifiNetworks: List<WiFiNetwork>,
    val cellTowers: List<CellTowerInfo>,
    val barometer: BarometerData?,
    val ambientLight: LightData?,
    val magneticField: MagneticData?,
    val handTremor: TremorData?,
    val locationHash: String,
    val confidence: Float,
    val schemaVersion: String = "2.0"
)
```

#### Location_Profile_Matcher
```kotlin
interface LocationProfileMatcher {
    suspend fun matchProfile(
        captured: SensorDataPackage,
        expected: LocationProfile
    ): MatchResult
}

data class LocationProfile(
    val campaignId: String,
    val expectedGPS: GPSBounds,
    val expectedWiFiNetworks: List<String>, // BSSIDs
    val expectedCellTowers: List<Long>,     // Cell IDs
    val expectedPressureRange: ClosedFloatingPointRange<Float>?,
    val expectedLightRange: ClosedFloatingPointRange<Float>?,
    val toleranceMeters: Float = 50f
)

data class MatchResult(
    val isMatch: Boolean,
    val confidence: Float,     // 0-100
    val gpsMatch: Boolean,
    val wifiMatch: Int,        // count of matched networks
    val cellMatch: Boolean,
    val pressureMatch: Boolean?,
    val lightMatch: Boolean?,
    val discrepancies: List<String>
)
```

### 3. Cryptographic Security

#### Crypto_Signer
```kotlin
interface CryptoSigner {
    suspend fun initializeKeyPair(): Result<Unit>
    suspend fun signPhoto(
        photoBytes: ByteArray,
        metadata: PhotoMetadata
    ): Result<PhotoSignature>
    suspend fun getPublicKey(): Result<String>
    fun isHardwareBackedAvailable(): Boolean
}

data class PhotoSignature(
    val signature: ByteArray,
    val algorithm: String,     // "SHA256withRSA" or "SHA256withECDSA"
    val timestamp: Instant,
    val locationHash: String,
    val deviceId: String
)

data class PhotoMetadata(
    val timestamp: Instant,
    val locationHash: String,
    val campaignCode: String,
    val sensorData: SensorDataPackage
)
```

#### Encryption_Manager
```kotlin
interface EncryptionManager {
    suspend fun encryptPhoto(
        photoBytes: ByteArray,
        metadata: PhotoMetadata
    ): Result<EncryptedPhoto>
    
    suspend fun decryptPhoto(encrypted: EncryptedPhoto): Result<ByteArray>
}

data class EncryptedPhoto(
    val ciphertext: ByteArray,
    val iv: ByteArray,
    val authTag: ByteArray,
    val metadata: PhotoMetadata
)
```


### 4. Photo Capture and Processing

#### Photo_Capture_Module
```kotlin
interface PhotoCaptureModule {
    suspend fun initializeCamera(): Result<Unit>
    suspend fun capturePhoto(): Result<RawPhoto>
    fun releaseCamera()
    fun isCameraAvailable(): Boolean
}

data class RawPhoto(
    val imageBytes: ByteArray,
    val width: Int,
    val height: Int,
    val format: ImageFormat,
    val exifData: ExifData,
    val captureTimestamp: Instant
)
```

#### Watermark_Generator
```kotlin
interface WatermarkGenerator {
    suspend fun applyWatermark(
        photo: RawPhoto,
        metadata: WatermarkMetadata
    ): Result<ByteArray>
}

data class WatermarkMetadata(
    val gpsCoordinates: String,  // "12.3456789, 98.7654321"
    val timestamp: String,        // ISO 8601 format
    val campaignCode: String,
    val customBranding: String?   // Enterprise tier only
)
```

### 5. Upload and Synchronization

#### Upload_Manager
```kotlin
interface UploadManager {
    suspend fun uploadPhoto(
        photo: ByteArray,
        signature: PhotoSignature,
        sensorData: SensorDataPackage
    ): Result<UploadReceipt>
    
    suspend fun queueForLater(photo: EncryptedPhoto): Result<Unit>
    fun getPendingUploadsCount(): Int
    suspend fun processPendingUploads(): Result<List<UploadReceipt>>
}

data class UploadReceipt(
    val receiptId: String,
    val photoId: String,
    val uploadTimestamp: Instant,
    val serverSignature: String
)
```

### 6. Campaign Management

#### Campaign_Validator
```kotlin
interface CampaignValidator {
    suspend fun validateCode(code: String): Result<CampaignConfig>
    suspend fun parseConfig(json: String): Result<CampaignConfig>
    fun formatConfig(config: CampaignConfig): String
}

data class CampaignConfig(
    val campaignId: String,
    val campaignCode: String,
    val campaignType: CampaignType,
    val locationProfile: LocationProfile?,
    val expirationDate: Instant,
    val maxPhotos: Int?,
    val requiresSignature: Boolean = false,
    val requiresSafetyTags: Boolean = false,
    val allowsMultiplePhotos: Boolean = false
)

enum class CampaignType {
    CONSTRUCTION,
    INSURANCE,
    DELIVERY,
    HEALTHCARE,
    PROPERTY_MANAGEMENT,
    OOH_ADVERTISING
}
```


### 7. Subscription and Payment Integration

#### Subscription_Manager
```kotlin
interface SubscriptionManager {
    suspend fun getCurrentTier(): Result<SubscriptionTier>
    suspend fun upgradeToTier(tier: SubscriptionTier): Result<Unit>
    suspend fun processStripePayment(paymentMethodId: String): Result<PaymentResult>
    suspend fun processGooglePlayPurchase(purchaseToken: String): Result<PaymentResult>
    fun canCapturePhoto(): Boolean  // Check quota
    suspend fun getUsageStats(): Result<UsageStats>
}

enum class SubscriptionTier {
    FREE,
    PRO,
    ENTERPRISE
}

data class SubscriptionDetails(
    val tier: SubscriptionTier,
    val photosPerMonth: Int,
    val photosUsedThisMonth: Int,
    val teamMemberLimit: Int,
    val currentTeamMembers: Int,
    val retentionDays: Int,
    val features: Set<Feature>,
    val renewalDate: Instant?,
    val isActive: Boolean
)

enum class Feature {
    BASIC_WATERMARK,
    MULTI_SENSOR_VERIFICATION,
    LOCATION_PROFILE_MATCHING,
    TEAM_COLLABORATION,
    PRIORITY_UPLOAD,
    CUSTOM_BRANDING,
    API_ACCESS,
    WHITE_LABEL,
    SSO_INTEGRATION,
    ANALYTICS_DASHBOARD,
    PHONE_SUPPORT
}

data class UsageStats(
    val photosThisMonth: Int,
    val photosLastMonth: Int,
    val uploadSuccessRate: Float,
    val averageUploadTime: Duration,
    val storageUsed: Long  // bytes
)
```

#### Payment_Integration
```kotlin
interface PaymentProcessor {
    suspend fun initializeStripe(publishableKey: String): Result<Unit>
    suspend fun createPaymentIntent(amount: Int, currency: String): Result<String>
    suspend fun confirmPayment(clientSecret: String): Result<PaymentResult>
}

interface GooglePlayBillingClient {
    suspend fun querySubscriptions(): Result<List<SubscriptionOffer>>
    suspend fun launchBillingFlow(sku: String): Result<PurchaseResult>
    suspend fun acknowledgePurchase(purchaseToken: String): Result<Unit>
}

data class PaymentResult(
    val success: Boolean,
    val transactionId: String?,
    val errorMessage: String?
)
```


### 8. Audit and Compliance

#### Audit_Logger
```kotlin
interface AuditLogger {
    suspend fun logPhotoCapture(record: AuditRecord): Result<Unit>
    suspend fun getAuditTrail(userId: String): Result<List<AuditRecord>>
    suspend fun exportAuditData(format: ExportFormat): Result<ByteArray>
}

data class AuditRecord(
    val auditId: String,
    val photoId: String,
    val userId: String,
    val campaignCode: String,
    val timestamp: Instant,
    val sensorData: SensorDataPackage,
    val signature: PhotoSignature,
    val deviceInfo: DeviceInfo,
    val previousRecordHash: String?,  // Hash chaining
    val flags: Set<AuditFlag>
)

enum class AuditFlag {
    ROOTED_DEVICE,
    EMULATOR_MODE,
    LOW_GPS_ACCURACY,
    SENSOR_CONFLICT,
    LOCATION_PROFILE_MISMATCH,
    OFFLINE_CAPTURE,
    MANUAL_RETRY
}

data class DeviceInfo(
    val manufacturer: String,
    val model: String,
    val androidVersion: String,
    val appVersion: String,
    val isRooted: Boolean,
    val isEmulator: Boolean,
    val hasHardwareKeystore: Boolean
)
```

### 9. Team Management (Pro/Enterprise)

#### Team_Manager
```kotlin
interface TeamManager {
    suspend fun createTeam(name: String): Result<Team>
    suspend fun inviteMember(email: String, role: TeamRole): Result<Unit>
    suspend fun removeMember(userId: String): Result<Unit>
    suspend fun getTeamMembers(): Result<List<TeamMember>>
    suspend fun assignCampaign(campaignId: String, memberIds: List<String>): Result<Unit>
}

data class Team(
    val teamId: String,
    val name: String,
    val ownerId: String,
    val members: List<TeamMember>,
    val createdAt: Instant
)

data class TeamMember(
    val userId: String,
    val email: String,
    val role: TeamRole,
    val joinedAt: Instant,
    val photosContributed: Int
)

enum class TeamRole {
    OWNER,
    ADMIN,
    MEMBER,
    VIEWER
}
```


## Data Models

### Database Schema (PostgreSQL)

#### Client Table
```sql
CREATE TABLE clients (
    client_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    subscription_tier VARCHAR(20) NOT NULL CHECK (subscription_tier IN ('free', 'pro', 'enterprise')),
    subscription_status VARCHAR(20) DEFAULT 'active',
    stripe_customer_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_clients_email ON clients(email);
CREATE INDEX idx_clients_subscription ON clients(subscription_tier, subscription_status);
```

#### Vendor Table
```sql
CREATE TABLE vendors (
    vendor_id VARCHAR(6) PRIMARY KEY,  -- 6-char alphanumeric
    name VARCHAR(255) NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    email VARCHAR(255),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_by_client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    device_id VARCHAR(255),  -- Android device ID after first login
    public_key TEXT,  -- RSA public key from Android Keystore
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP
);

CREATE INDEX idx_vendors_client ON vendors(created_by_client_id);
CREATE INDEX idx_vendors_phone ON vendors(phone_number);
CREATE INDEX idx_vendors_status ON vendors(status);
```

#### Campaign Table
```sql
CREATE TABLE campaigns (
    campaign_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    campaign_type VARCHAR(50) NOT NULL,
    client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_campaigns_client ON campaigns(client_id);
CREATE INDEX idx_campaigns_code ON campaigns(campaign_code);
CREATE INDEX idx_campaigns_dates ON campaigns(start_date, end_date);
```

#### Location Profile Table
```sql
CREATE TABLE location_profiles (
    profile_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(campaign_id) ON DELETE CASCADE,
    expected_latitude DECIMAL(10, 7) NOT NULL,
    expected_longitude DECIMAL(10, 7) NOT NULL,
    tolerance_meters FLOAT DEFAULT 50.0,
    expected_wifi_bssids TEXT[],  -- Array of BSSIDs
    expected_cell_tower_ids INTEGER[],  -- Array of cell IDs
    expected_pressure_min FLOAT,
    expected_pressure_max FLOAT,
    expected_light_min FLOAT,
    expected_light_max FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_location_profiles_campaign ON location_profiles(campaign_id);
```

#### Campaign Vendor Assignment Table
```sql
CREATE TABLE campaign_vendor_assignments (
    assignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(campaign_id) ON DELETE CASCADE,
    vendor_id VARCHAR(6) NOT NULL REFERENCES vendors(vendor_id) ON DELETE CASCADE,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(campaign_id, vendor_id)
);

CREATE INDEX idx_assignments_campaign ON campaign_vendor_assignments(campaign_id);
CREATE INDEX idx_assignments_vendor ON campaign_vendor_assignments(vendor_id);
```

#### Photo Table
```sql
CREATE TABLE photos (
    photo_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(campaign_id) ON DELETE CASCADE,
    vendor_id VARCHAR(6) NOT NULL REFERENCES vendors(vendor_id) ON DELETE CASCADE,
    capture_timestamp TIMESTAMP NOT NULL,
    upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    s3_key VARCHAR(500) NOT NULL,  -- S3 object key
    thumbnail_s3_key VARCHAR(500),
    verification_status VARCHAR(20) DEFAULT 'pending' CHECK (verification_status IN ('verified', 'flagged', 'rejected', 'pending')),
    signature_valid BOOLEAN,
    location_match_score FLOAT,  -- 0-100
    distance_from_expected FLOAT,  -- meters
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_photos_campaign ON photos(campaign_id);
CREATE INDEX idx_photos_vendor ON photos(vendor_id);
CREATE INDEX idx_photos_timestamp ON photos(capture_timestamp);
CREATE INDEX idx_photos_status ON photos(verification_status);
```

#### Sensor Data Table
```sql
CREATE TABLE sensor_data (
    sensor_data_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    photo_id UUID NOT NULL REFERENCES photos(photo_id) ON DELETE CASCADE,
    gps_latitude DECIMAL(10, 7),
    gps_longitude DECIMAL(10, 7),
    gps_altitude FLOAT,
    gps_accuracy FLOAT,
    gps_provider VARCHAR(20),
    gps_satellite_count INTEGER,
    wifi_networks JSONB,  -- Array of {ssid, bssid, signal_strength, frequency}
    cell_towers JSONB,  -- Array of {cell_id, lac, mcc, mnc, signal_strength, network_type}
    barometer_pressure FLOAT,
    barometer_altitude FLOAT,
    ambient_light_lux FLOAT,
    magnetic_field_x FLOAT,
    magnetic_field_y FLOAT,
    magnetic_field_z FLOAT,
    magnetic_field_magnitude FLOAT,
    hand_tremor_frequency FLOAT,
    hand_tremor_is_human BOOLEAN,
    hand_tremor_confidence FLOAT,
    location_hash VARCHAR(64),  -- SHA-256 hash
    confidence_score FLOAT,  -- 0-1
    schema_version VARCHAR(10) DEFAULT '2.0',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sensor_data_photo ON sensor_data(photo_id);
CREATE INDEX idx_sensor_data_gps ON sensor_data(gps_latitude, gps_longitude);
```

#### Photo Signature Table
```sql
CREATE TABLE photo_signatures (
    signature_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    photo_id UUID NOT NULL REFERENCES photos(photo_id) ON DELETE CASCADE,
    signature_data TEXT NOT NULL,  -- Base64 encoded signature
    algorithm VARCHAR(50) NOT NULL,  -- "SHA256withRSA" or "SHA256withECDSA"
    device_id VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    location_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_signatures_photo ON photo_signatures(photo_id);
```

#### Subscription Table
```sql
CREATE TABLE subscriptions (
    subscription_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    tier VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    stripe_subscription_id VARCHAR(255),
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    photos_quota INTEGER,
    photos_used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_subscriptions_client ON subscriptions(client_id);
```

### Database Schema (Room - Android Local Storage)

#### Photo Entity
```kotlin
@Entity(tableName = "photos")
data class PhotoEntity(
    @PrimaryKey val photoId: String,
    val campaignCode: String,
    val userId: String,
    val captureTimestamp: Long,  // Unix epoch millis
    val uploadStatus: UploadStatus,
    val localPath: String?,      // Encrypted file path
    val receiptId: String?,
    val sensorDataJson: String,  // Serialized SensorDataPackage
    val signatureJson: String,   // Serialized PhotoSignature
    val retryCount: Int = 0,
    val lastRetryTimestamp: Long?
)

enum class UploadStatus {
    PENDING,
    UPLOADING,
    COMPLETED,
    FAILED
}
```

#### Campaign Entity
```kotlin
@Entity(tableName = "campaigns")
data class CampaignEntity(
    @PrimaryKey val campaignId: String,
    val campaignCode: String,
    val campaignType: String,
    val configJson: String,      // Serialized CampaignConfig
    val isActive: Boolean,
    val expirationDate: Long,
    val photosCount: Int = 0,
    val lastSyncTimestamp: Long
)
```

#### User Entity
```kotlin
@Entity(tableName = "users")
data class UserEntity(
    @PrimaryKey val userId: String,
    val email: String,
    val displayName: String?,
    val subscriptionTier: String,
    val photosQuota: Int,
    val photosUsed: Int,
    val teamId: String?,
    val publicKey: String,
    val lastLoginTimestamp: Long
)
```

#### Audit Entity
```kotlin
@Entity(tableName = "audit_logs")
data class AuditEntity(
    @PrimaryKey val auditId: String,
    val photoId: String,
    val userId: String,
    val timestamp: Long,
    val auditRecordJson: String,  // Serialized AuditRecord
    val previousRecordHash: String?,
    val isSynced: Boolean = false
)
```

### API Payloads

#### Photo Upload Request
```json
{
  "photoId": "uuid-v4",
  "campaignCode": "CAMP-2024-001",
  "userId": "user-uuid",
  "captureTimestamp": "2024-01-15T14:30:00Z",
  "photoData": "base64-encoded-jpeg",
  "signature": {
    "signature": "base64-encoded-signature",
    "algorithm": "SHA256withECDSA",
    "timestamp": "2024-01-15T14:30:00Z",
    "locationHash": "sha256-hash",
    "deviceId": "device-uuid"
  },
  "sensorData": {
    "gps": {
      "latitude": 12.9715987,
      "longitude": 77.5945627,
      "altitude": 920.5,
      "accuracy": 8.2,
      "provider": "FUSED",
      "satelliteCount": 12,
      "timestamp": "2024-01-15T14:30:00Z"
    },
    "wifiNetworks": [
      {
        "ssid": "CoffeeShop-WiFi",
        "bssid": "00:11:22:33:44:55",
        "signalStrength": -45,
        "frequency": 2437,
        "timestamp": "2024-01-15T14:30:00Z"
      }
    ],
    "cellTowers": [
      {
        "cellId": 12345,
        "locationAreaCode": 100,
        "mobileCountryCode": 404,
        "mobileNetworkCode": 45,
        "signalStrength": -75,
        "networkType": "LTE",
        "timestamp": "2024-01-15T14:30:00Z"
      }
    ],
    "barometer": {
      "pressure": 1013.25,
      "altitude": 920.0,
      "timestamp": "2024-01-15T14:30:00Z"
    },
    "ambientLight": {
      "illuminance": 15000.0,
      "timestamp": "2024-01-15T14:30:00Z"
    },
    "magneticField": {
      "x": 25.3,
      "y": -12.7,
      "z": 48.2,
      "magnitude": 55.8,
      "timestamp": "2024-01-15T14:30:00Z"
    },
    "handTremor": {
      "dominantFrequency": 10.2,
      "isHumanTremor": true,
      "confidence": 0.92,
      "timestamp": "2024-01-15T14:30:00Z"
    },
    "locationHash": "sha256-hash-of-combined-data",
    "confidence": 0.95,
    "schemaVersion": "2.0"
  }
}
```


#### Photo Upload Response
```json
{
  "success": true,
  "receiptId": "receipt-uuid",
  "photoId": "photo-uuid",
  "uploadTimestamp": "2024-01-15T14:30:05Z",
  "serverSignature": "base64-encoded-server-signature",
  "verificationStatus": "VERIFIED",
  "matchResult": {
    "isMatch": true,
    "confidence": 95.5,
    "gpsMatch": true,
    "wifiMatch": 4,
    "cellMatch": true,
    "pressureMatch": true,
    "lightMatch": true
  }
}
```

### 10. Reporting and Analytics

#### Report_Generator
```kotlin
interface ReportGenerator {
    suspend fun generateCSVReport(
        campaignId: String,
        dateRange: ClosedRange<Instant>
    ): Result<ByteArray>
    
    suspend fun generateMapVisualization(
        campaignId: String
    ): Result<MapVisualizationData>
    
    suspend fun calculateDistanceMetrics(
        photos: List<PhotoEntity>
    ): Result<DistanceMetrics>
}

data class MapVisualizationData(
    val geoJsonFeatures: String,  // GeoJSON format for mapping
    val centerPoint: LatLng,
    val boundingBox: BoundingBox,
    val photoMarkers: List<PhotoMarker>
)

data class PhotoMarker(
    val photoId: String,
    val latitude: Double,
    val longitude: Double,
    val timestamp: Instant,
    val thumbnailUrl: String?,
    val verificationStatus: String,
    val distanceFromExpected: Float?  // meters
)

data class DistanceMetrics(
    val averageDistanceFromExpected: Float,  // meters
    val maxDistanceFromExpected: Float,
    val minDistanceFromExpected: Float,
    val photosWithinTolerance: Int,
    val photosOutsideTolerance: Int,
    val totalPhotos: Int
)
```

#### CSV Export Format
```csv
PhotoID,CampaignCode,CaptureTimestamp,Latitude,Longitude,Altitude,GPSAccuracy,WiFiNetworks,CellTowers,Pressure,AmbientLight,MagneticField,HandTremor,VerificationStatus,DistanceFromExpected,UploadTimestamp
photo-001,CAMP-2024-001,2024-01-15T14:30:00Z,12.9715987,77.5945627,920.5,8.2,5,2,1013.25,15000.0,55.8,true,VERIFIED,12.3,2024-01-15T14:30:05Z
photo-002,CAMP-2024-001,2024-01-15T15:45:00Z,12.9716234,77.5946012,921.0,6.5,6,2,1013.20,14800.0,55.9,true,VERIFIED,8.7,2024-01-15T15:45:03Z
```

#### GeoJSON Export Format
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [77.5945627, 12.9715987]
      },
      "properties": {
        "photoId": "photo-001",
        "campaignCode": "CAMP-2024-001",
        "timestamp": "2024-01-15T14:30:00Z",
        "verificationStatus": "VERIFIED",
        "distanceFromExpected": 12.3,
        "thumbnailUrl": "https://cdn.trustcapture.com/thumb/photo-001.jpg"
      }
    }
  ]
}
```


## User Interface Design

### Web Application Screens

#### 1. Client Registration/Login
- Email + password authentication
- Company details form
- Subscription tier selection
- Stripe payment integration
- Email verification

#### 2. Client Dashboard
- Overview cards: Total vendors, active campaigns, photos captured, verification rate
- Recent activity feed
- Quick actions: Add vendor, create campaign, view reports
- Subscription status and usage metrics

#### 3. Vendor Management
- DataGrid with vendor list (ID, name, phone, status, last active)
- Add vendor dialog (name, phone, email)
- Edit/deactivate actions
- Bulk operations (export, deactivate multiple)
- Vendor activity history

#### 4. Campaign Management
- Campaign list with filters (active, completed, cancelled)
- Create campaign wizard:
  - Step 1: Basic info (name, type, dates)
  - Step 2: Location profile (GPS, WiFi, cell towers)
  - Step 3: Assign vendors
  - Step 4: Review and create
- Campaign detail view with photo gallery
- Campaign analytics dashboard

#### 5. Photo Gallery & Verification
- Grid view with thumbnails
- Map view with photo markers
- Filters: Date range, vendor, verification status
- Photo detail modal:
  - Full-size image with watermark
  - Sensor data display
  - Verification status
  - Distance from expected location
  - Actions: Approve, flag, reject
- Bulk actions: Export selected, approve all

#### 6. Map Visualization
- Interactive map (Mapbox or Leaflet)
- Photo markers color-coded by status
- Expected location marker (if location profile defined)
- Distance circles
- Cluster markers for dense areas
- Photo preview popup on marker click
- Layer toggles (satellite, terrain, street)

#### 7. Reports & Analytics
- Campaign summary report
- Distance metrics (avg, min, max from expected)
- Verification rate chart
- Photos per vendor chart
- Timeline chart (photos over time)
- Export options: CSV, GeoJSON, PDF

#### 8. Settings
- Account settings (email, password, company details)
- Subscription management (upgrade, downgrade, cancel)
- Billing history
- API keys (Pro/Enterprise)
- Webhook configuration (Enterprise)
- Team management (Enterprise)

### Android Application Screens

### Screen Flow

**Web Application (Client)**:
```
[Landing Page]
      ↓
[Client Registration] → [Subscription Selection] → [Payment (Stripe)]
      ↓
[Client Dashboard]
      ├─→ [Vendor Management] → [Add/Edit Vendor]
      ├─→ [Campaign Management] → [Create Campaign Wizard]
      ├─→ [Photo Gallery] ←→ [Map View]
      ├─→ [Reports & Analytics] → [Export (CSV/GeoJSON/PDF)]
      └─→ [Settings] → [Subscription/Billing/API Keys]
```

**Android Application (Vendor)**:
```
[Splash Screen]
      ↓
[Vendor Login]
   ├─ Phone Number Input
   ├─ Vendor ID Input (from SMS)
   └─ OTP Verification
      ↓
[Campaign Selection] (List of assigned campaigns)
      ↓
[Campaign Code Entry] (or QR scan)
      ↓
[Camera Screen] (Photo capture ONLY)
      ├─ Sensor status indicators
      ├─ Live camera preview
      └─ Capture button
      ↓
[Photo Review]
      ├─ Photo with watermark
      ├─ Sensor data summary
      └─ Submit/Retake buttons
      ↓
[Upload Progress]
      ├─ Encryption
      ├─ Upload
      └─ Verification
      ↓
[Success] → Back to Campaign Selection
```

### 1. Login/Register Screen

**Components:**
- Email input field
- Password input field
- "Sign In" button
- "Sign Up" link
- "Forgot Password" link
- Google Sign-In button
- Terms & Privacy policy links

**Validation:**
- Email format validation
- Password strength indicator (min 8 chars, 1 uppercase, 1 number)
- Network connectivity check

**Navigation:**
- Success → Campaign Entry Screen (Free tier) or Subscription Selection (new users)
- Forgot Password → Password Reset Flow


### 2. Subscription Selection Screen

**Components:**
- Tier comparison cards (Free, Pro, Enterprise)
- Feature checklist per tier
- Pricing display (monthly/annual toggle)
- "Start Free Trial" button (Pro tier)
- "Subscribe" buttons
- "Skip for now" link (defaults to Free tier)

**Features Display:**
| Feature | Free | Pro | Enterprise |
|---------|------|-----|------------|
| Photos/month | 50 | Unlimited | Unlimited |
| GPS + Timestamp | ✓ | ✓ | ✓ |
| Multi-sensor verification | ✗ | ✓ | ✓ |
| Environmental sensors | ✗ | ✓ | ✓ |
| Location profile matching | ✗ | ✓ | ✓ |
| Team collaboration | ✗ | ✗ | ✓ |
| Custom branding | ✗ | ✗ | ✓ |
| API access | ✗ | ✓ | ✓ |
| Retention | 7 days | 1 year | Custom |
| Support | Email | Priority | Phone |

**Payment Integration:**
- Stripe payment sheet for credit card
- Google Play Billing for in-app subscriptions
- Annual discount display (save 20%)

### 3. Campaign Entry Screen

**Components:**
- Campaign code input field (alphanumeric with hyphens)
- "Start Verification" button
- Info card explaining tamper-proof capture
- Recent campaigns list (cached)
- QR code scanner button (scan campaign QR codes)
- Settings icon (top-right)

**Validation:**
- Campaign code format check (local)
- Server-side campaign validation
- Expiration date check
- User quota check (photos remaining)

**Error States:**
- Invalid campaign code
- Expired campaign
- Network error (show cached campaigns)
- Quota exceeded (prompt upgrade)


### 4. Camera Screen

**Layout:**
```
┌─────────────────────────────────┐
│  [Back] Campaign: CAMP-001 [⚙] │ ← Header
├─────────────────────────────────┤
│                                 │
│                                 │
│      Camera Preview             │
│      (Full screen)              │
│                                 │
│                                 │
├─────────────────────────────────┤
│  GPS: ●  WiFi: 5  Cell: ●       │ ← Sensor status
│  Light: 15000 lux  Alt: 920m    │
├─────────────────────────────────┤
│         [Capture Button]        │ ← Capture control
│      Point camera at target     │
└─────────────────────────────────┘
```

**Components:**
- Full-screen camera preview (rear camera only)
- Sensor status indicators (real-time)
  - GPS: Green dot (locked), Yellow (searching), Red (unavailable)
  - WiFi: Network count
  - Cell: Green dot (connected)
  - Light: Lux value
  - Altitude: Meters from barometer
- Capture button (large, centered)
- Instruction text overlay
- Back button
- Settings button

**Sensor Status Updates:**
- Update every 1 second
- Show warnings if GPS accuracy > 50m
- Disable capture if critical sensors unavailable (configurable per campaign)

### 5. Photo Review Screen

**Layout:**
```
┌─────────────────────────────────┐
│  [← Retake]  Verification  [Submit →] │
├─────────────────────────────────┤
│                                 │
│     Captured Photo              │
│     with Watermark              │
│                                 │
│  ┌─────────────────────────┐   │
│  │ 12.9715987°N, 77.5945627°E │
│  │ ±8.2m                    │   │
│  │ 2024-01-15 14:30:00 IST  │   │
│  │ CAMPAIGN: CAMP-2024-001  │   │
│  └─────────────────────────┘   │
├─────────────────────────────────┤
│  ✓ Tamper-proof verification   │
│    applied                      │
│                                 │
│  Sensor Data:                   │
│  • GPS: 12 satellites           │
│  • WiFi: 5 networks detected    │
│  • Cell: LTE tower 12345        │
│  • Pressure: 1013.25 hPa        │
│  • Light: 15000 lux (daylight)  │
│  • Magnetic: 55.8 μT            │
│  • Hand tremor: Verified ✓      │
└─────────────────────────────────┘
```

**Components:**
- Photo preview with visible watermark
- Sensor data summary (expandable)
- Verification status indicator
- "Retake" button (left)
- "Submit" button (right, primary action)
- Success message box

**Actions:**
- Retake: Return to camera screen, discard current photo
- Submit: Begin upload process, navigate to upload progress


### 6. Upload Progress Screen

**Components:**
- Progress bar (0-100%)
- Status text ("Encrypting...", "Uploading...", "Verifying...")
- Photo thumbnail
- Cancel button (queues for later)
- Network speed indicator

**States:**
1. Encrypting photo (10%)
2. Generating signature (20%)
3. Uploading to server (20-80%)
4. Server verification (80-95%)
5. Generating receipt (95-100%)

**Error Handling:**
- Network timeout: Offer retry or queue for later
- Server error: Show error message, auto-queue
- Quota exceeded: Prompt upgrade

### 7. Dashboard/Success Screen

**Components:**
- Success message with checkmark animation
- Photo count for current campaign
- "Capture Another" button
- "View Campaign Report" button (Pro/Enterprise)
- "Export Data" button (Pro/Enterprise)
- Pending uploads indicator (if any)
- Recent photos grid (thumbnails)

**Navigation:**
- Capture Another → Camera Screen (same campaign)
- View Report → Campaign Report Screen
- Export Data → Export options dialog
- Photo thumbnail → Photo detail view


### 8. Campaign Report Screen (Pro/Enterprise)

**Components:**
- Campaign header (name, code, date range)
- Statistics cards:
  - Total photos captured
  - Verification success rate
  - Average GPS accuracy
  - Photos within location tolerance
- Interactive map view (OpenStreetMap or Mapbox)
  - Photo markers (color-coded by verification status)
  - Expected location marker (if location profile defined)
  - Distance circles
  - Cluster markers for dense areas
- Photo list view (sortable by date, distance, status)
- Export buttons (CSV, GeoJSON, PDF report)

**Map Interactions:**
- Tap marker → Show photo preview popup
- Zoom/pan controls
- Layer toggles (satellite, terrain, street)
- Distance measurement tool
- Heatmap overlay (photo density)


### 9. Settings Screen

**Sections:**

**Account:**
- Email address (read-only)
- Display name (editable)
- Subscription tier (with "Upgrade" button)
- Usage stats (photos this month, storage used)
- Sign out button

**Camera Settings:**
- Photo quality (High/Medium/Low)
- Auto-capture on GPS lock (toggle)
- Flash mode (Auto/On/Off)
- Grid overlay (toggle)

**Sensor Settings:**
- Required sensors (checkboxes)
- GPS accuracy threshold (slider: 10-100m)
- WiFi scan timeout (slider: 1-5s)
- Sensor data in watermark (toggle)

**Upload Settings:**
- Auto-upload on capture (toggle)
- Upload on WiFi only (toggle)
- Retry failed uploads (toggle)
- Max retry attempts (slider: 1-5)

**Privacy & Security:**
- Biometric authentication (toggle)
- Auto-delete after upload (toggle)
- Share diagnostic data (toggle)
- View privacy policy
- View terms of service

**Advanced:**
- Developer mode (toggle)
- View device info
- View public key
- Clear cache
- App version

## Technology Stack

### Web Application

**Frontend:**
- **Framework**: React 18+ with TypeScript
- **Build Tool**: Vite or Create React App
- **State Management**: Redux Toolkit or Zustand
- **Routing**: React Router v6
- **UI Library**: Material-UI (MUI) v5
- **Forms**: React Hook Form + Zod validation
- **Data Fetching**: TanStack Query (React Query)
- **Maps**: Mapbox GL JS (Pro/Enterprise) or Leaflet (Free tier)
- **Charts**: Recharts
- **Tables**: MUI DataGrid or TanStack Table
- **Date/Time**: date-fns
- **HTTP Client**: Axios
- **Authentication**: JWT in httpOnly cookies

**Deployment:**
- **Hosting**: Vercel, Netlify, or AWS S3 + CloudFront
- **CDN**: CloudFront for static assets
- **SSL**: Let's Encrypt or AWS Certificate Manager

### Android App

**Language & Framework:**
- Kotlin 1.9+
- Jetpack Compose for UI
- Coroutines for async operations
- Flow for reactive streams

**Architecture:**
- MVVM (Model-View-ViewModel)
- Clean Architecture (Domain/Data/Presentation layers)
- Repository pattern
- Use Case pattern

**Libraries:**
- **Dependency Injection**: Hilt
- **Networking**: Retrofit 2.9+, OkHttp 4.x
- **Database**: Room 2.6+ with SQLCipher for encryption
- **Image Processing**: Coil for loading, Android Bitmap API
- **Cryptography**: Android Keystore, Tink library
- **Location**: Google Play Services Location API
- **Sensors**: Android Sensor Framework
- **JSON**: Kotlinx Serialization
- **Testing**: JUnit 5, Mockk, Turbine, Kotest for property-based testing

**Minimum SDK:** API 26 (Android 8.0)
**Target SDK:** API 34 (Android 14)


### Backend Services

**Language & Framework:**
- **Python 3.11+**
- **FastAPI 0.104+** (async web framework)
- **Pydantic 2.0+** (data validation)
- **SQLAlchemy 2.0+** (async ORM)
- **Alembic** (database migrations)

**Key Libraries:**
- **Authentication**: python-jose (JWT), passlib (password hashing)
- **Cryptography**: cryptography library, PyNaCl
- **HTTP Client**: httpx (async)
- **Task Queue**: Celery with Redis
- **Email**: python-sendgrid
- **SMS**: twilio
- **PDF Generation**: ReportLab or WeasyPrint
- **Image Processing**: Pillow
- **Testing**: pytest, pytest-asyncio, hypothesis (property-based)

**Infrastructure:**
- **Hosting**: AWS ECS with Fargate (serverless containers)
- **Load Balancer**: AWS Application Load Balancer
- **Container Registry**: AWS ECR
- **Orchestration**: Docker + Docker Compose (local), ECS (production)

**Database:**
- **Primary**: PostgreSQL 15+ (Amazon RDS Multi-AZ)
  - Extensions: pgcrypto, postgis (for geospatial queries)
- **Audit Logs**: Amazon DynamoDB (append-only, immutable)
- **Cache**: Redis 7+ (Amazon ElastiCache)
- **Search**: (Optional) Elasticsearch for photo search

**Storage:**
- **Photos**: Amazon S3 with versioning
- **Lifecycle**: S3 Intelligent-Tiering, Glacier for archives
- **CDN**: CloudFront for photo delivery

**External Services:**
- **Payment**: Stripe API
- **SMS**: Twilio
- **Email**: SendGrid
- **Push Notifications**: Firebase Cloud Messaging
- **Weather Data**: OpenWeatherMap API (barometer validation)
- **Maps**: Mapbox API (Pro/Enterprise tier)

**Monitoring & Logging:**
- **Application Monitoring**: Sentry
- **Infrastructure Monitoring**: AWS CloudWatch
- **Log Aggregation**: CloudWatch Logs or ELK stack
- **Uptime Monitoring**: UptimeRobot or Pingdom
- **APM**: New Relic or Datadog (optional)

**Development Tools:**
- **API Documentation**: FastAPI auto-generated Swagger/ReDoc
- **Code Quality**: Black (formatter), Flake8 (linter), mypy (type checker)
- **Pre-commit Hooks**: pre-commit framework
- **CI/CD**: GitHub Actions or GitLab CI

## Security Architecture

### Defense in Depth Strategy

**Layer 1: Device Security**
- Root detection (Magisk, SuperSU checks)
- SafetyNet attestation
- Emulator detection
- Debug mode detection
- Screen recording prevention

**Layer 2: Cryptographic Security**
- Hardware-backed Android Keystore (StrongBox when available)
- RSA-2048 or ECDSA P-256 for signing
- AES-256-GCM for encryption
- SHA-256 for hashing
- TLS 1.3 for network communication

**Layer 3: Data Security**
- No unencrypted photos stored locally
- Encrypted Room database (SQLCipher)
- Secure SharedPreferences (EncryptedSharedPreferences)
- Memory scrubbing after sensitive operations
- Certificate pinning for API calls

**Layer 4: Network Security**
- TLS 1.3 with certificate pinning
- API request signing
- Rate limiting (per user, per IP)
- DDoS protection (CloudFlare or AWS Shield)
- Input validation and sanitization

**Layer 5: Backend Security**
- JWT token validation
- Role-based access control (RBAC)
- SQL injection prevention (parameterized queries)
- XSS prevention
- CSRF protection
- Regular security audits


### Threat Model

**Threat 1: GPS Spoofing**
- **Mitigation**: Multi-sensor triangulation (WiFi + Cell + Barometer)
- **Detection**: Sensor data conflict analysis

**Threat 2: Photo Tampering**
- **Mitigation**: Cryptographic signing, burned-in watermarks
- **Detection**: Signature verification, watermark integrity check

**Threat 3: Replay Attacks**
- **Mitigation**: Timestamp validation (±5 minutes), nonce in signature
- **Detection**: Server-side timestamp verification

**Threat 4: Man-in-the-Middle**
- **Mitigation**: TLS 1.3, certificate pinning
- **Detection**: Certificate validation failure

**Threat 5: Key Extraction**
- **Mitigation**: Hardware-backed Keystore, StrongBox
- **Detection**: Root detection, SafetyNet attestation

**Threat 6: Screen Recapture**
- **Mitigation**: Moiré pattern detection, luminance analysis, rolling shutter detection
- **Detection**: Multi-modal fusion algorithm (96%+ accuracy)

## Performance Requirements

### App Performance

**Startup Time:**
- Cold start: < 2 seconds
- Warm start: < 1 second

**Photo Capture:**
- Camera preview load: < 2 seconds
- Sensor data collection: < 3 seconds
- Photo capture to review: < 5 seconds
- Signature generation: < 500ms
- Watermark application: < 1 second

**Upload Performance:**
- 4G/5G: < 10 seconds for 3MB photo
- WiFi: < 5 seconds for 3MB photo
- Retry with exponential backoff: 1s, 2s, 4s

**Battery Usage:**
- Active capture session: < 5% per hour
- Background sync: < 1% per hour
- GPS usage: Low-power mode when not capturing

**Memory Usage:**
- App memory footprint: < 150MB
- Photo processing: < 50MB additional
- Database cache: < 20MB

**Storage:**
- App size: < 50MB
- Pending uploads: Max 50 photos (encrypted)
- Database: < 10MB for 1000 photos metadata


### Backend Performance

**API Response Times:**
- Campaign validation: < 500ms (p95)
- Photo upload: < 2 seconds (p95)
- Signature verification: < 200ms (p95)
- Report generation: < 5 seconds (p95)

**Throughput:**
- 1000 concurrent uploads
- 10,000 API requests per second
- 99.9% uptime SLA

**Scalability:**
- Horizontal scaling for API servers
- Auto-scaling based on load
- CDN for photo delivery
- Database read replicas

## Testing Strategy

### Unit Testing

**Coverage Target:** 80%+

**Test Frameworks:**
- JUnit 5 for standard tests
- Mockk for mocking
- Kotest for property-based testing
- Turbine for Flow testing

**Property-Based Tests:**
```kotlin
class SensorDataSerializationTest : StringSpec({
    "round-trip serialization preserves data" {
        checkAll(Arb.sensorDataPackage()) { sensorData ->
            val json = sensorData.toJson()
            val deserialized = SensorDataPackage.fromJson(json)
            deserialized shouldBe sensorData
        }
    }
    
    "location hash is deterministic" {
        checkAll(Arb.sensorDataPackage()) { sensorData ->
            val hash1 = sensorData.calculateLocationHash()
            val hash2 = sensorData.calculateLocationHash()
            hash1 shouldBe hash2
        }
    }
    
    "GPS coordinates preserve 7 decimal precision" {
        checkAll(Arb.double(-90.0, 90.0)) { lat ->
            val formatted = formatGPS(lat, precision = 7)
            val parsed = parseGPS(formatted)
            (parsed - lat).absoluteValue shouldBeLessThan 0.00000005
        }
    }
})
```

**Unit Test Coverage:**
- All ViewModels
- All Use Cases
- All Repositories
- Cryptographic operations
- Sensor data processing
- Location triangulation logic
- Watermark generation


### Integration Testing

**Test Scenarios:**
- Camera → Capture → Upload flow
- Offline capture → Queue → Upload when online
- Campaign validation → Location profile matching
- Payment flow → Subscription activation
- Multi-sensor data collection → Signature generation

**Mock Services:**
- Mock GPS provider
- Mock WiFi scanner
- Mock cell tower scanner
- Mock backend API
- Mock payment gateway


### UI Testing

**Framework:** Jetpack Compose Testing

**Test Scenarios:**
- Login flow
- Campaign entry
- Camera screen interactions
- Photo review and submission
- Settings changes
- Error state handling

**Accessibility Testing:**
- TalkBack compatibility
- Touch target sizes (min 48dp)
- Color contrast ratios
- Screen reader labels

### Emulator Testing

**Android Studio Emulator Setup:**

**Device Configuration:**
- Device: Pixel 6 Pro (API 34)
- System Image: Android 14 (Google APIs)
- RAM: 4GB
- Internal Storage: 8GB
- SD Card: 512MB

**Mock Sensor Data:**
```kotlin
// Mock GPS coordinates
val mockGPS = LocationData(
    latitude = 12.9715987,
    longitude = 77.5945627,
    altitude = 920.5,
    accuracy = 8.2f,
    provider = LocationProvider.FUSED,
    satelliteCount = 12,
    timestamp = Instant.now()
)

// Mock WiFi networks
val mockWiFi = listOf(
    WiFiNetwork("CoffeeShop-WiFi", "00:11:22:33:44:55", -45, 2437, Instant.now()),
    WiFiNetwork("Office-5G", "AA:BB:CC:DD:EE:FF", -52, 5180, Instant.now())
)

// Mock cell tower
val mockCell = CellTowerInfo(
    cellId = 12345,
    locationAreaCode = 100,
    mobileCountryCode = 404,
    mobileNetworkCode = 45,
    signalStrength = -75,
    networkType = NetworkType.LTE,
    timestamp = Instant.now()
)
```

**Emulator Extended Controls:**
- Location: Set custom GPS coordinates
- Cellular: Set network type and signal strength
- Battery: Test low battery scenarios
- Camera: Use virtual scene or webcam

**Testing Workflow:**
1. Launch emulator with Google APIs
2. Enable location services
3. Set mock GPS coordinates via Extended Controls
4. Run app and verify sensor data collection
5. Test offline mode by disabling network
6. Test upload queue and retry logic


### End-to-End Testing

**Test Scenarios:**
1. New user registration → Free tier → Capture photo → Upload
2. Existing user → Upgrade to Pro → Enable all sensors → Capture → Verify
3. Team admin → Invite member → Assign campaign → Member captures → Admin reviews
4. Offline capture → Queue 10 photos → Go online → Verify all upload
5. Location profile mismatch → Flag for review → Admin approves/rejects

**Tools:**
- Appium for cross-device testing
- Firebase Test Lab for cloud testing
- Manual testing on physical devices

## Deployment Strategy

### Development Environment

**Local Development:**
- Android Studio Iguana (2023.2.1) or later
- JDK 17
- Gradle 8.2+
- Android SDK 34
- Emulator with Google APIs

**Version Control:**
- Git with GitHub/GitLab
- Branch strategy: main, develop, feature/*, hotfix/*
- Pull request reviews required
- CI/CD pipeline on merge

**Environment Configuration:**
```kotlin
// build.gradle.kts
android {
    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            buildConfigField("String", "API_BASE_URL", "\"https://dev-api.trustcapture.com\"")
            buildConfigField("String", "STRIPE_KEY", "\"pk_test_...\"")
        }
        release {
            buildConfigField("String", "API_BASE_URL", "\"https://api.trustcapture.com\"")
            buildConfigField("String", "STRIPE_KEY", "\"pk_live_...\"")
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
}
```


### CI/CD Pipeline

**GitHub Actions Workflow:**
```yaml
name: Android CI/CD

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up JDK 17
        uses: actions/setup-java@v3
        with:
          java-version: '17'
      - name: Grant execute permission for gradlew
        run: chmod +x gradlew
      - name: Run unit tests
        run: ./gradlew test
      - name: Run lint
        run: ./gradlew lint
      - name: Build debug APK
        run: ./gradlew assembleDebug
      - name: Upload APK
        uses: actions/upload-artifact@v3
        with:
          name: app-debug
          path: app/build/outputs/apk/debug/app-debug.apk
```

**Automated Checks:**
- Unit tests (80%+ coverage)
- Lint checks
- Code style (ktlint)
- Security scan (Snyk)
- Dependency vulnerabilities
- APK size check (< 50MB)


### Release Process

**Beta Testing:**
- Internal testing: 10-20 team members
- Closed beta: 100-500 users via Google Play Internal Testing
- Open beta: 1000+ users via Google Play Beta track
- Feedback collection via Firebase Crashlytics and in-app surveys

**Production Release:**
1. Merge develop → main
2. Tag release (v1.0.0)
3. Build signed release APK/AAB
4. Upload to Google Play Console
5. Staged rollout: 10% → 50% → 100% over 7 days
6. Monitor crash rates and user feedback
7. Hotfix if critical issues detected

**App Signing:**
- Google Play App Signing (recommended)
- Upload key stored in CI/CD secrets
- Signing key managed by Google Play

### Backend Deployment

**Infrastructure:**
- AWS ECS or EKS for container orchestration
- Application Load Balancer
- Auto Scaling Groups (min 2, max 10 instances)
- Multi-AZ deployment for high availability
- CloudFront CDN for photo delivery

**Database:**
- Amazon RDS PostgreSQL (Multi-AZ)
- Read replicas for reporting queries
- Automated backups (daily, 30-day retention)
- Point-in-time recovery enabled

**Storage:**
- Amazon S3 for photos
- Versioning enabled
- Lifecycle policies (archive to Glacier after 1 year)
- Cross-region replication for disaster recovery

**Monitoring:**
- CloudWatch for metrics and logs
- Alarms for high error rates, latency, CPU usage
- SNS notifications to on-call team
- Datadog dashboards for real-time monitoring

**Deployment Pipeline:**
1. Code push to main branch
2. Run tests and security scans
3. Build Docker image
4. Push to Amazon ECR
5. Update ECS task definition
6. Rolling deployment (zero downtime)
7. Health check validation
8. Rollback on failure


## Pricing Model

### Free Tier
**Price:** $0/month

**Limits:**
- 50 photos per month
- GPS + timestamp watermark only
- Single campaign at a time
- 7-day photo retention
- Email support (48-hour response)

**Use Case:** Individual users, small projects, proof of concept


### Pro Tier
**Price:** $29/month or $290/year (save 17%)

**Features:**
- Unlimited photos
- Multi-sensor verification (GPS + WiFi + Cell)
- Environmental sensors (barometer, light, magnetometer)
- Hand tremor detection
- Location profile matching
- Offline mode with upload queue
- Unlimited campaigns
- 1-year photo retention
- CSV/GeoJSON export
- Map visualization
- API access (1000 requests/day)
- Priority email support (24-hour response)

**Use Case:** Freelancers, small teams, field workers


### Enterprise Tier
**Price:** Custom (starting at $199/month)

**Features:**
- Everything in Pro
- Custom photo retention
- Team collaboration (unlimited members)
- Role-based access control
- Custom branding (white-label)
- Screen recapture detection
- SSO integration (SAML, OAuth)
- Analytics dashboard
- Webhook integrations
- API access (unlimited)
- Dedicated account manager
- Phone support (4-hour response)
- SLA guarantee (99.9% uptime)
- Custom integrations

**Use Case:** Large enterprises, agencies, compliance-heavy industries


### Add-ons (All Tiers)

**Additional Storage:**
- $5/month per 100GB beyond included retention

**Additional API Calls:**
- $10/month per 10,000 requests (Pro tier)

**Priority Processing:**
- $20/month for sub-5-second upload verification

**Custom Integrations:**
- $500 one-time setup fee per integration

## Map Visualization Implementation

### Map Library Selection

**Option 1: Mapbox SDK (Recommended)**
- **Pros**: Beautiful maps, offline support, customizable styles, good performance
- **Cons**: Requires API key, pricing after free tier (50,000 loads/month)
- **Cost**: Free tier sufficient for most users, $5/1000 loads after

**Option 2: OpenStreetMap (osmdroid)**
- **Pros**: Free, open-source, no API key required, offline maps
- **Cons**: Less polished UI, requires more customization
- **Cost**: Free

**Decision**: Start with osmdroid for MVP, offer Mapbox as Pro/Enterprise feature


### Map Features

**Photo Markers:**
```kotlin
data class PhotoMarker(
    val photoId: String,
    val position: LatLng,
    val timestamp: Instant,
    val verificationStatus: VerificationStatus,
    val thumbnailUrl: String?,
    val distanceFromExpected: Float?
)

enum class VerificationStatus {
    VERIFIED,      // Green marker
    FLAGGED,       // Yellow marker
    REJECTED,      // Red marker
    PENDING        // Gray marker
}
```

**Marker Clustering:**
- Group nearby markers when zoomed out
- Show count badge on cluster
- Expand on tap/zoom

**Distance Calculation:**
```kotlin
fun calculateDistance(point1: LatLng, point2: LatLng): Float {
    // Haversine formula
    val R = 6371000f // Earth radius in meters
    val lat1 = Math.toRadians(point1.latitude)
    val lat2 = Math.toRadians(point2.latitude)
    val dLat = Math.toRadians(point2.latitude - point1.latitude)
    val dLon = Math.toRadians(point2.longitude - point1.longitude)
    
    val a = sin(dLat / 2) * sin(dLat / 2) +
            cos(lat1) * cos(lat2) *
            sin(dLon / 2) * sin(dLon / 2)
    val c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    return R * c
}
```

**Map Interactions:**
- Tap marker → Show photo preview popup
- Long press → Measure distance tool
- Pinch zoom
- Two-finger rotate
- Tilt gesture (3D buildings)


### CSV Export Implementation

**Export Service:**
```kotlin
interface CSVExporter {
    suspend fun exportCampaign(
        campaignId: String,
        dateRange: ClosedRange<Instant>?
    ): Result<File>
}

class CSVExporterImpl : CSVExporter {
    override suspend fun exportCampaign(
        campaignId: String,
        dateRange: ClosedRange<Instant>?
    ): Result<File> = withContext(Dispatchers.IO) {
        val photos = photoRepository.getPhotos(campaignId, dateRange)
        val csvFile = File(context.cacheDir, "campaign_${campaignId}_${System.currentTimeMillis()}.csv")
        
        csvFile.bufferedWriter().use { writer ->
            // Header
            writer.write("PhotoID,CampaignCode,CaptureTimestamp,Latitude,Longitude,Altitude,GPSAccuracy,WiFiNetworks,CellTowers,Pressure,AmbientLight,MagneticField,HandTremor,VerificationStatus,DistanceFromExpected,UploadTimestamp\n")
            
            // Data rows
            photos.forEach { photo ->
                writer.write(photo.toCSVRow())
                writer.write("\n")
            }
        }
        
        Result.success(csvFile)
    }
}

fun PhotoEntity.toCSVRow(): String {
    val sensorData = Json.decodeFromString<SensorDataPackage>(sensorDataJson)
    return listOf(
        photoId,
        campaignCode,
        Instant.ofEpochMilli(captureTimestamp).toString(),
        sensorData.gps?.latitude?.toString() ?: "",
        sensorData.gps?.longitude?.toString() ?: "",
        sensorData.gps?.altitude?.toString() ?: "",
        sensorData.gps?.accuracy?.toString() ?: "",
        sensorData.wifiNetworks.size.toString(),
        sensorData.cellTowers.size.toString(),
        sensorData.barometer?.pressure?.toString() ?: "",
        sensorData.ambientLight?.illuminance?.toString() ?: "",
        sensorData.magneticField?.magnitude?.toString() ?: "",
        sensorData.handTremor?.isHumanTremor?.toString() ?: "",
        uploadStatus.name,
        "", // Distance calculated on backend
        receiptId?.let { Instant.now().toString() } ?: ""
    ).joinToString(",") { escapeCSV(it) }
}

fun escapeCSV(value: String): String {
    return if (value.contains(",") || value.contains("\"") || value.contains("\n")) {
        "\"${value.replace("\"", "\"\"")}\""
    } else {
        value
    }
}
```

### GeoJSON Export Implementation

```kotlin
interface GeoJSONExporter {
    suspend fun exportCampaign(
        campaignId: String,
        dateRange: ClosedRange<Instant>?
    ): Result<File>
}

class GeoJSONExporterImpl : GeoJSONExporter {
    override suspend fun exportCampaign(
        campaignId: String,
        dateRange: ClosedRange<Instant>?
    ): Result<File> = withContext(Dispatchers.IO) {
        val photos = photoRepository.getPhotos(campaignId, dateRange)
        val geoJson = buildGeoJSON(photos)
        
        val file = File(context.cacheDir, "campaign_${campaignId}_${System.currentTimeMillis()}.geojson")
        file.writeText(geoJson)
        
        Result.success(file)
    }
    
    private fun buildGeoJSON(photos: List<PhotoEntity>): String {
        val features = photos.mapNotNull { photo ->
            val sensorData = Json.decodeFromString<SensorDataPackage>(photo.sensorDataJson)
            sensorData.gps?.let { gps ->
                """
                {
                  "type": "Feature",
                  "geometry": {
                    "type": "Point",
                    "coordinates": [${gps.longitude}, ${gps.latitude}]
                  },
                  "properties": {
                    "photoId": "${photo.photoId}",
                    "campaignCode": "${photo.campaignCode}",
                    "timestamp": "${Instant.ofEpochMilli(photo.captureTimestamp)}",
                    "verificationStatus": "${photo.uploadStatus}",
                    "gpsAccuracy": ${gps.accuracy},
                    "altitude": ${gps.altitude ?: "null"},
                    "wifiNetworks": ${sensorData.wifiNetworks.size},
                    "cellTowers": ${sensorData.cellTowers.size},
                    "pressure": ${sensorData.barometer?.pressure ?: "null"},
                    "ambientLight": ${sensorData.ambientLight?.illuminance ?: "null"}
                  }
                }
                """.trimIndent()
            }
        }
        
        return """
        {
          "type": "FeatureCollection",
          "features": [
            ${features.joinToString(",\n")}
          ]
        }
        """.trimIndent()
    }
}
```


### Distance Metrics Calculation

```kotlin
interface DistanceCalculator {
    suspend fun calculateMetrics(
        photos: List<PhotoEntity>,
        expectedLocation: LatLng?
    ): Result<DistanceMetrics>
}

class DistanceCalculatorImpl : DistanceCalculator {
    override suspend fun calculateMetrics(
        photos: List<PhotoEntity>,
        expectedLocation: LatLng?
    ): Result<DistanceMetrics> = withContext(Dispatchers.Default) {
        if (expectedLocation == null) {
            return@withContext Result.failure(IllegalArgumentException("Expected location required"))
        }
        
        val distances = photos.mapNotNull { photo ->
            val sensorData = Json.decodeFromString<SensorDataPackage>(photo.sensorDataJson)
            sensorData.gps?.let { gps ->
                calculateDistance(
                    LatLng(gps.latitude, gps.longitude),
                    expectedLocation
                )
            }
        }
        
        if (distances.isEmpty()) {
            return@withContext Result.failure(IllegalStateException("No GPS data available"))
        }
        
        val tolerance = 50f // meters
        val withinTolerance = distances.count { it <= tolerance }
        val outsideTolerance = distances.count { it > tolerance }
        
        Result.success(
            DistanceMetrics(
                averageDistanceFromExpected = distances.average().toFloat(),
                maxDistanceFromExpected = distances.maxOrNull() ?: 0f,
                minDistanceFromExpected = distances.minOrNull() ?: 0f,
                photosWithinTolerance = withinTolerance,
                photosOutsideTolerance = outsideTolerance,
                totalPhotos = photos.size
            )
        )
    }
}
```


## Future Enhancements

### Phase 2 Features (6-12 months)

**AI-Powered Verification:**
- Object detection (verify billboard content matches campaign)
- OCR for text extraction from photos
- Image similarity matching (detect duplicate submissions)
- Anomaly detection (flag suspicious patterns)

**Advanced Analytics:**
- Heatmaps of photo density
- Time-series analysis of capture patterns
- Predictive analytics for fraud detection
- Custom report builder

**Integrations:**
- Zapier integration for workflow automation
- Slack/Teams notifications
- Salesforce CRM integration
- QuickBooks for billing

**Mobile Features:**
- iOS app (Swift/SwiftUI)
- Tablet optimization
- Wear OS companion app
- Voice commands for hands-free capture


### Phase 3 Features (12-24 months)

**Blockchain Integration:**
- Immutable audit trail on blockchain
- NFT certificates for verified photos
- Smart contracts for automated verification

**AR Features:**
- AR overlay for expected location guidance
- AR measurement tools
- AR annotations on photos

**Machine Learning:**
- Auto-tagging of photo content
- Smart campaign suggestions
- Fraud pattern recognition
- Automated quality scoring

**Enterprise Features:**
- Multi-tenant architecture
- Custom domain support
- Advanced RBAC with custom roles
- Compliance certifications (SOC 2, ISO 27001)


## Conclusion

TrustCapture represents a comprehensive solution for tamper-proof photo verification across multiple industries. By combining multi-sensor geolocation triangulation, environmental context validation, cryptographic integrity, and user-friendly mobile interfaces, we create a system that makes photo fraud computationally and physically impractical.

The architecture is designed for scalability, security, and extensibility, with clear separation of concerns and modern Android development practices. The pricing model balances accessibility (free tier) with sustainable revenue (Pro/Enterprise tiers), while the roadmap ensures continuous innovation and market leadership.

**Key Differentiators:**
- Most comprehensive sensor suite in the market (GPS + WiFi + Cell + Barometer + Light + Magnetometer + Tremor)
- Hardware-backed cryptographic security
- Offline-first architecture with intelligent sync
- Cross-industry applicability
- Developer-friendly API and export formats
- Transparent, competitive pricing

**Success Metrics:**
- 10,000 active users in first year
- 95%+ user satisfaction score
- 99.9% upload success rate
- <2% fraud detection rate
- $500K ARR by end of year 1


## Summary of Design Updates

### Key Architecture Changes

**1. Dual-Platform System:**
- **Web Application**: Client-facing portal for management, built with React + TypeScript
- **Android Application**: Vendor-facing photo capture app, built with Kotlin + Jetpack Compose
- Clear separation of concerns: Management vs. Field Operations

**2. User Roles & Flow:**
- **Clients**: Register on web app → Create vendors → Create campaigns → View reports
- **Vendors**: Receive SMS with vendor ID → Login on Android app → Capture photos only
- No registration or management features in Android app

**3. Technology Stack:**
- **Frontend**: React 18 + TypeScript + Material-UI
- **Backend**: Python 3.11 + FastAPI (changed from Node.js/Kotlin for cost savings)
- **Database**: PostgreSQL 15 (primary) + DynamoDB (audit logs) + Redis (cache)
- **Android**: Kotlin + Jetpack Compose + Room (encrypted)
- **Infrastructure**: AWS ECS (Fargate) + S3 + CloudFront

**4. Cost Optimization:**
- Python backend reduces developer costs by ~$40K/year vs Kotlin
- Simpler maintenance with Python's readability
- Faster development cycles
- Better library support for cryptography and data processing

**5. Security Model:**
- Clients manage vendors (create, deactivate)
- Vendors can only capture photos for assigned campaigns
- Hardware-backed cryptographic signing on Android
- Multi-sensor verification prevents GPS spoofing
- Immutable audit trail in DynamoDB

**6. Subscription Model:**
- **Free**: 50 photos/month, basic GPS + timestamp, web access
- **Pro**: Unlimited photos, all sensors, API access, $29/month
- **Enterprise**: Custom features, white-label, SSO, custom pricing

This design provides a scalable, secure, and cost-effective solution for tamper-proof photo verification across multiple industries.
