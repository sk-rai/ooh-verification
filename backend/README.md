# TrustCapture Backend

> Tamper-proof photo verification system with multi-sensor geolocation triangulation

## 📋 Overview

TrustCapture backend is a FastAPI-based REST API that provides:
- Client and vendor management
- Campaign creation and configuration
- Photo upload with cryptographic verification
- Multi-sensor location triangulation
- Subscription and payment processing
- Comprehensive audit trails

## 🏗️ Architecture

```
backend/
├── app/
│   ├── api/              # API endpoints (TODO)
│   ├── core/             # Core configuration
│   │   └── database.py   # Database setup ✅
│   ├── models/           # SQLAlchemy models ✅
│   │   ├── client.py
│   │   ├── vendor.py
│   │   ├── campaign.py
│   │   ├── location_profile.py
│   │   ├── campaign_vendor_assignment.py
│   │   ├── photo.py
│   │   ├── sensor_data.py
│   │   ├── photo_signature.py
│   │   └── subscription.py
│   ├── schemas/          # Pydantic schemas (TODO)
│   └── services/         # Business logic (TODO)
├── alembic/              # Database migrations ✅
│   └── versions/
│       └── 20260304_initial_schema.py
├── scripts/              # Utility scripts ✅
│   └── db_setup.py
├── tests/                # Test suite (TODO)
├── requirements.txt      # Python dependencies ✅
├── .env.example          # Environment template ✅
└── alembic.ini           # Alembic config ✅
```

## 🚀 Quick Start

See [QUICKSTART.md](QUICKSTART.md) for detailed setup instructions.

**TL;DR:**
```bash
# 1. Create database
sudo -u postgres psql
CREATE DATABASE trustcapture_db;
CREATE USER trustcapture WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE trustcapture_db TO trustcapture;
\q

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your database credentials

# 4. Run migrations
alembic upgrade head

# 5. Seed sample data (optional)
python scripts/db_setup.py seed
```

## 📊 Database Schema

### Core Tables (9 total)

| Table | Purpose | Status |
|-------|---------|--------|
| **clients** | Client accounts with subscription management | ✅ |
| **vendors** | Field workers who capture photos | ✅ |
| **campaigns** | Verification campaigns | ✅ |
| **location_profiles** | Expected sensor patterns | ✅ |
| **campaign_vendor_assignments** | Campaign-vendor links | ✅ |
| **photos** | Photo metadata and verification | ✅ |
| **sensor_data** | Multi-sensor readings | ✅ |
| **photo_signatures** | Cryptographic signatures | ✅ |
| **subscriptions** | Subscription tracking | ✅ |

See [DATABASE.md](DATABASE.md) for complete schema documentation.

## 🔧 Technology Stack

- **Framework**: FastAPI 0.109.0
- **Database**: PostgreSQL 15+ with asyncpg
- **ORM**: SQLAlchemy 2.0 (async)
- **Migrations**: Alembic 1.13.1
- **Authentication**: JWT with python-jose
- **Password Hashing**: bcrypt
- **Cloud Storage**: AWS S3 (boto3)
- **Cache**: Redis
- **Payments**: Stripe
- **SMS**: Twilio
- **Email**: SendGrid
- **Testing**: pytest with async support

## 📝 API Endpoints (Planned)

### Authentication
- `POST /api/auth/register` - Client registration
- `POST /api/auth/login` - Client login
- `POST /api/auth/vendor-login` - Vendor login with OTP

### Client Management
- `GET /api/clients/me` - Get current client
- `PATCH /api/clients/me` - Update client profile

### Vendor Management
- `POST /api/vendors` - Create vendor
- `GET /api/vendors` - List vendors
- `PATCH /api/vendors/{vendor_id}` - Update vendor
- `DELETE /api/vendors/{vendor_id}` - Deactivate vendor

### Campaign Management
- `POST /api/campaigns` - Create campaign
- `GET /api/campaigns` - List campaigns
- `GET /api/campaigns/{campaign_id}` - Get campaign details
- `PATCH /api/campaigns/{campaign_id}` - Update campaign
- `POST /api/campaigns/{campaign_id}/vendors` - Assign vendors

### Photo Management
- `POST /api/photos/upload` - Upload photo with verification
- `GET /api/photos` - List photos
- `GET /api/photos/{photo_id}` - Get photo details

### Reports
- `GET /api/campaigns/{campaign_id}/export/csv` - Export CSV
- `GET /api/campaigns/{campaign_id}/export/geojson` - Export GeoJSON
- `GET /api/campaigns/{campaign_id}/export/pdf` - Generate PDF report

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_models.py

# Run with verbose output
pytest -v
```

## 📦 Development

### Create New Migration

```bash
# After modifying models
alembic revision --autogenerate -m "description"

# Review generated migration
# Edit if necessary

# Apply migration
alembic upgrade head
```

### Database Management

```bash
# Check connection
python scripts/db_setup.py check

# Reset database (WARNING: deletes all data)
python scripts/db_setup.py reset

# Seed sample data
python scripts/db_setup.py seed
```

### Code Quality

```bash
# Format code
black app/

# Lint code
flake8 app/

# Type checking
mypy app/
```

## 🔐 Security Features

- **Password Hashing**: bcrypt with salt
- **JWT Tokens**: Secure token-based authentication
- **SQL Injection Prevention**: Parameterized queries via SQLAlchemy
- **CORS Protection**: Configurable CORS origins
- **Rate Limiting**: Redis-based rate limiting (planned)
- **Input Validation**: Pydantic schemas
- **Cryptographic Signatures**: RSA/ECDSA photo signing
- **Hardware-Backed Keys**: Android Keystore integration

## 📈 Performance

- **Async Operations**: Full async/await support
- **Connection Pooling**: Configurable pool size
- **Database Indexes**: 20+ strategic indexes
- **Caching**: Redis for session and data caching
- **CDN**: CloudFront for photo delivery

## 🌍 Environment Variables

See `.env.example` for all configuration options:

```bash
# Application
APP_NAME=TrustCapture
DEBUG=True
SECRET_KEY=your-secret-key

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db

# AWS
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
S3_BUCKET_NAME=trustcapture-photos

# External Services
TWILIO_ACCOUNT_SID=your-sid
STRIPE_SECRET_KEY=your-key
SENDGRID_API_KEY=your-key

# JWT
JWT_SECRET_KEY=your-jwt-secret
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=10080
```

## 📚 Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Get started in 5 minutes
- **[DATABASE.md](DATABASE.md)** - Complete database documentation
- **[DB_IMPLEMENTATION_SUMMARY.md](DB_IMPLEMENTATION_SUMMARY.md)** - Implementation details
- **[../.kiro/specs/trust-capture/requirements.md](../.kiro/specs/trust-capture/requirements.md)** - Full requirements
- **[../.kiro/specs/trust-capture/design.md](../.kiro/specs/trust-capture/design.md)** - System design
- **[../.kiro/specs/trust-capture/tasks.md](../.kiro/specs/trust-capture/tasks.md)** - Implementation tasks

## ✅ Completed Tasks

- [x] Task 1: Backend project structure
- [x] Task 2.1: PostgreSQL database schema
- [x] Task 2.2: SQLAlchemy ORM models
- [x] Task 2.4: Initial Alembic migration
- [ ] Task 2.3: Property-based tests (next)
- [ ] Task 3: Authentication implementation
- [ ] Task 4: Client management API
- [ ] Task 6: Vendor management API
- [ ] Task 7: Campaign management API

## 🎯 Next Steps

1. **Task 2.3**: Write property-based tests for models
2. **Task 3**: Implement JWT authentication and vendor OTP
3. **Task 4**: Create client management API endpoints
4. **Task 6**: Create vendor management API endpoints
5. **Task 7**: Create campaign management API endpoints

## 🤝 Contributing

1. Follow PEP 8 style guide
2. Write tests for new features
3. Update documentation
4. Use type hints
5. Run linters before committing

## 📄 License

Proprietary - All rights reserved

## 🆘 Support

For issues or questions:
1. Check [DATABASE.md](DATABASE.md) for database issues
2. Check [QUICKSTART.md](QUICKSTART.md) for setup issues
3. Review error logs in `logs/` directory
4. Check PostgreSQL logs: `/var/log/postgresql/`

## 🎉 Status

**Current Phase**: Phase 1 - Backend Foundation  
**Progress**: Task 2 Complete (Database Implementation)  
**Next**: Task 3 (Authentication)

---

Built with ❤️ for tamper-proof photo verification
