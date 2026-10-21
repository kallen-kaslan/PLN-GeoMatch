# PLN GeoMatch

Sistem rekonsiliasi data pelanggan PLN dengan pencocokan koordinat geospasial.

## Prasyarat

- Python 3.12+
- Node.js 18+
- PostgreSQL 14+
- Redis (opsional, untuk background tasks)

## Instalasi

### 1. Clone Repository

```bash
git clone https://github.com/username/PLN-GeoMatch.git
cd PLN-GeoMatch
```

### 2. Setup Backend

```bash
cd backend

# Buat virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# atau
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env sesuai konfigurasi database Anda
```

### 3. Setup Database PostgreSQL

```sql
-- Buat database
CREATE DATABASE pln_geomatch;

-- Buat user (opsional)
CREATE USER postgres WITH PASSWORD 'postgres';
GRANT ALL PRIVILEGES ON DATABASE pln_geomatch TO postgres;
```

### 4. Jalankan Migrasi Database

```bash
cd backend
alembic upgrade head
```

### 5. Setup Frontend

```bash
cd frontend
npm install
```

## Menjalankan Aplikasi

### Development Mode

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate  # Linux/Mac
# atau venv\Scripts\activate  # Windows
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

Aplikasi akan berjalan di:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Production Mode

```bash
# Build frontend
cd frontend
npm run build

# Serve dengan nginx atau static server
```

## Konfigurasi Environment

Edit file `backend/.env`:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/pln_geomatch
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
REDIS_URL=redis://localhost:6379/0
```

## Fitur

- Upload data pelanggan dan koordinat
- Pencocokan otomatis berdasarkan radius
- Validasi IDPEL dan koordinat
- Visualisasi peta interaktif
- Multi-filter dan pagination
- Export hasil rekonsiliasi

## Kelayakan Data

Status validitas data:

| Status | Kondisi |
|--------|---------|
| VALID | Koordinat + IDPEL ada |
| IDPEL_KOSONG | IDPEL tidak ada (prioritas tinggi) |
| PERLU_KONFIRMASI_IDPEL | Koordinat ada, IDPEL tidak ada |
| DILUAR_RADIUS | Koordinat tidak ada, IDPEL ada |

## Teknologi

- **Backend:** FastAPI, SQLAlchemy, PostgreSQL, Alembic
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS
- **Database:** PostgreSQL dengan ekstensi PostGIS (opsional)
- **Maps:** Leaflet, OpenStreetMap

## Testing

```bash
cd backend
pytest tests/
```

## Lisensi

MIT License
