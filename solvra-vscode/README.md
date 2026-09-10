# SOLVRA — Problem Intelligence Platform

A **VS Code-ready local application** for the SIH SOLVRA concept. Docker is intentionally removed.

## 1. Project structure

```text
solvra-vscode/
├── backend/
│   ├── app/
│   │   └── main.py              # FastAPI API + AI/fusion logic
│   ├── requirements.txt
│   └── .venv/                   # created locally
├── frontend/
│   ├── src/
│   │   ├── main.jsx            # React application
│   │   └── index.css
│   ├── package.json
│   └── vite.config.js
├── database/
│   ├── schema.sql               # schema reference
│   └── solvra.db                # created automatically after first run
├── scripts/
│   ├── start-backend.bat
│   ├── start-frontend.bat
│   └── seed.bat
└── README.md
```

## 2. Technology

- **Frontend:** React + Vite + React-Leaflet
- **Backend:** Python + FastAPI + SQLAlchemy
- **Database:** SQLite for zero-configuration local development
- **Map:** OpenStreetMap + Leaflet
- **AI layer:** explainable keyword/domain/severity/urgency classification
- **Problem Fusion:** semantic/domain + geographic distance + keyword overlap + urgency
- **Storage:** local `uploads/` folder for evidence images

## 3. Run in VS Code — Windows

### Terminal 1: Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Backend: http://localhost:8000  
API documentation: http://localhost:8000/docs

### Terminal 2: Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173

You can also double-click the files inside `scripts/` after opening the project in VS Code.

## 4. First-time database setup

No database server is required. On the first backend start, SQLAlchemy creates:

`database/solvra.db`

To load demonstration data, either click **Load demo data** in the dashboard or run:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/api/seed
```

## 5. Main application workflow

1. User opens SOLVRA.
2. User reports a problem.
3. User captures GPS or selects coordinates on the map.
4. FastAPI validates and stores the geotagged problem.
5. AI classifies domain, severity, urgency and confidence.
6. The problem appears in the registry and live map.
7. SOLVRA compares it with other reports.
8. Related reports are fused into a systemic cluster.
9. Cluster intelligence shows likely root cause and recommended coordinated action.
10. Problem status can move from `REPORTED` → `VERIFIED` → `FUSED` → `IN_PROGRESS` → `RESOLVED`.
11. Audit events are stored in the database.

## 6. API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Backend/database health |
| `GET/POST /api/ai/analyze` | AI classification |
| `GET /api/problems` | Search/filter problems |
| `POST /api/problems` | Create geotagged report |
| `GET /api/problems/map` | Map-ready problem data |
| `GET /api/problems/{id}` | Problem details |
| `PATCH /api/problems/{id}/status` | Update workflow status |
| `POST /api/problems/{id}/media` | Upload evidence |
| `POST /api/fusion/run/{id}` | Run Problem Fusion Engine |
| `GET /api/clusters` | List systemic clusters |
| `GET /api/clusters/{id}` | Cluster details and members |
| `GET /api/stats` | Dashboard statistics |
| `GET /api/audit` | Audit trail |
| `POST /api/seed` | Add demo data |

## 7. Fusion logic

SOLVRA uses a transparent score rather than pretending every related report is a duplicate:

```text
fusion score =
  0.35 × semantic/domain similarity
+ 0.20 × geographic proximity
+ 0.20 × keyword overlap
+ 0.25 × urgency similarity
```

A score of **0.45 or higher** is considered a candidate for systemic fusion. A cluster is created and the original reports remain individually traceable.

## 8. Important

This version is designed to be **easy to open, run and demonstrate in VS Code without Docker**. SQLite is used so the database works immediately on a student laptop. For a production/SIH deployment, the same SQLAlchemy layer can be moved to PostgreSQL/PostGIS, with proper authentication/RBAC, background AI jobs, object storage, stronger embeddings, government workflows and deployment security.
