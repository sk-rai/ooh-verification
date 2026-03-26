# TrustCapture

Tamper-proof photo verification platform for field operations. Prevents vendor fraud in OOH advertising, delivery/logistics, construction, and agriculture through GPS-stamped, sensor-validated, cryptographically signed photos.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Web App     │     │  Backend API │     │  Android App │
│  (React/TS)  │────▶│  (FastAPI)   │◀────│  (Kotlin)    │
│  Tailwind    │     │  PostgreSQL  │     │  StrongBox   │
└─────────────┘     └──────────────┘     └──────────────┘
```

- **Web App** — React + TypeScript + Tailwind CSS. Landing page, dashboard, campaign/vendor management, reports.
- **Backend API** — FastAPI + SQLAlchemy + PostgreSQL. Multi-tenant, async, with Alembic migrations.
- **Android App** — Kotlin, camera-only capture, hardware-backed signatures (StrongBox/TEE), offline-first with SQLCipher + WorkManager.

## Key Features

- 5-layer photo verification: GPS + pressure + magnetic field + tremor + cryptographic signature
- Tamper-proof watermarks burned into image pixels
- Hardware-backed photo signatures (Android StrongBox/TEE)
- Offline-first Android app with encrypted local storage
- Bidirectional geocoding (Google Maps + Nominatim fallback)
- Auto-populated pressure/magnetic baselines (Open-Meteo + NOAA)
- Hash-chained, append-only audit trail
- Multi-tenant white-label architecture
- Bulk CSV operations (campaigns, vendors, assignments)
- PDF, CSV, GeoJSON report exports
- SMS (Twilio) + Email (SendGrid) notifications


## Subscription Tiers

| | Free | Pro | Enterprise |
|---|---|---|---|
| Photos/month | 50 | 1,000 | Unlimited |
| Vendors | 5 | 10 | Unlimited |
| Campaigns | 3 | 5 | Unlimited |
| Storage | 100 MB | 10 GB | 100 GB |
| Price (INR) | ₹0 | ₹999/mo | ₹4,999/mo |
| Price (USD) | $0 | $15/mo | $75/mo |

## Deployment

- **Backend**: Docker on Render (Singapore) — `ooh-verification.onrender.com`
- **Web**: Static site on Render (Global) — `trustcapture-web.onrender.com`
- **Database**: PostgreSQL 18 on Render (Singapore)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Tailwind CSS, Vite |
| Backend | FastAPI, SQLAlchemy 2.0, asyncpg, Alembic |
| Database | PostgreSQL 18 |
| Android | Kotlin, Jetpack, Room (SQLCipher), WorkManager |
| Auth | JWT + OTP (Twilio) + StrongBox device attestation |
| Storage | Cloudinary |
| Email | SendGrid |
| SMS | Twilio |
| Payments | Razorpay |
| Geocoding | Google Maps + Nominatim |
| Verification | Open-Meteo (pressure) + NOAA WMM (magnetic) |

## Project Structure

```
├── android/          # Android vendor app (Kotlin)
├── backend/          # FastAPI backend
│   ├── alembic/      # Database migrations
│   ├── app/
│   │   ├── api/      # Route handlers
│   │   ├── core/     # Config, auth, deps
│   │   ├── models/   # SQLAlchemy models
│   │   ├── schemas/  # Pydantic schemas
│   │   └── services/ # Business logic
│   └── tests/        # Backend tests
├── web/              # React web app
│   └── src/
│       ├── pages/    # Page components
│       ├── components/
│       ├── contexts/ # Auth context
│       └── services/ # API client
└── tests/            # Integration tests
```

## License

Proprietary — LynkSavvy Technologies © 2026
