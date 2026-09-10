from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from datetime import datetime, timezone
from pathlib import Path
import uuid, math, re, shutil, os, json

ROOT = Path(__file__).resolve().parents[2]
UPLOADS = ROOT / "uploads"
UPLOADS.mkdir(exist_ok=True)
DB_DIR = ROOT / "database"
DB_DIR.mkdir(exist_ok=True)
DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_DIR / 'solvra.db'}")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class Problem(Base):
    __tablename__ = "problems"
    id = Column(String, primary_key=True)
    title = Column(String(180), nullable=False)
    description = Column(Text, nullable=False)
    domain = Column(String(40), default="OTHER", nullable=False)
    severity = Column(String(20), default="MEDIUM", nullable=False)
    urgency = Column(String(20), default="MEDIUM", nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String(255))
    district = Column(String(100))
    status = Column(String(30), default="REPORTED", nullable=False)
    people_affected = Column(Integer, default=0)
    ai_confidence = Column(Float, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    image_url = Column(String(500))

class Cluster(Base):
    __tablename__ = "clusters"
    id = Column(String, primary_key=True)
    title = Column(String(180), nullable=False)
    domain = Column(String(40), nullable=False)
    problem_ids = Column(Text, default="")
    confidence = Column(Float, default=0)
    root_cause = Column(Text)
    recommended_action = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(100))
    detail = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(engine)
app = FastAPI(title="SOLVRA — Problem Intelligence Platform", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory=UPLOADS), name="uploads")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

KEYWORDS = {
    "WATER": ["water", "borewell", "pond", "groundwater", "pipeline", "tap", "irrigation", "drinking"],
    "AGRICULTURE": ["crop", "farm", "farmer", "soil", "fertilizer", "harvest", "paddy", "wheat", "agriculture"],
    "HEALTHCARE": ["hospital", "clinic", "doctor", "medicine", "disease", "dengue", "malaria", "health", "patient"],
    "EDUCATION": ["school", "teacher", "student", "education", "dropout", "classroom", "college"],
    "SANITATION": ["toilet", "sanitation", "sewage", "drainage", "waste", "garbage", "cleanliness", "dump"],
    "TRANSPORT": ["road", "bus", "bridge", "railway", "highway", "traffic", "pothole", "transport"],
    "ENERGY": ["electricity", "power", "solar", "outage", "transformer", "streetlight", "energy"],
    "ENVIRONMENT": ["pollution", "forest", "plastic", "climate", "erosion", "landslide", "air quality", "environment"],
}
HIGH = ["death", "died", "fatal", "critical", "emergency", "collapsed", "contaminated", "no water", "severe", "dangerous"]
URGENT = ["urgent", "immediately", "growing", "increasing", "every day", "worsening", "rapidly", "before monsoon", "now"]
RELATED = [{"WATER", "AGRICULTURE"}, {"HEALTHCARE", "SANITATION"}, {"EDUCATION", "TRANSPORT"}, {"ENERGY", "TRANSPORT"}, {"ENVIRONMENT", "WATER"}]

def analyze(text: str):
    t = text.lower()
    scores = {d: sum(t.count(k) for k in ks) for d, ks in KEYWORDS.items()}
    domain = max(scores, key=scores.get) if max(scores.values()) else "OTHER"
    severity = "HIGH" if any(x in t for x in HIGH) else ("LOW" if "minor" in t else "MEDIUM")
    urgency = "HIGH" if any(x in t for x in URGENT) else "MEDIUM"
    confidence = min(0.98, 0.55 + 0.07 * max(scores.values())) if domain != "OTHER" else 0.45
    return domain, severity, urgency, round(confidence, 2)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def keyword_overlap(a: str, b: str):
    wa = set(re.findall(r"[a-z]{4,}", a.lower()))
    wb = set(re.findall(r"[a-z]{4,}", b.lower()))
    if not wa or not wb: return 0.0
    return len(wa & wb) / len(wa | wb)

class ProblemIn(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=5, max_length=5000)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address: str | None = None
    district: str | None = None
    people_affected: int = Field(default=0, ge=0)

class ProblemOut(ProblemIn):
    id: str
    domain: str
    severity: str
    urgency: str
    status: str
    ai_confidence: float
    created_at: datetime
    image_url: str | None = None
    class Config: from_attributes = True

def audit(db, action, entity_type, entity_id, detail=""):
    db.add(AuditLog(id=str(uuid.uuid4()), action=action, entity_type=entity_type, entity_id=entity_id, detail=detail))

@app.get("/api/health")
def health():
    return {"ok": True, "service": "SOLVRA", "database": "connected", "version": "2.0.0"}

@app.get("/api/ai/analyze")
def ai_analyze(title: str = "", description: str = ""):
    d, s, u, c = analyze(f"{title} {description}")
    return {"domain": d, "severity": s, "urgency": u, "confidence": c}

@app.post("/api/ai/analyze")
def ai_analyze_post(payload: dict):
    return ai_analyze(payload.get("title", ""), payload.get("description", ""))

@app.post("/api/problems", response_model=ProblemOut)
def create_problem(p: ProblemIn, db: Session = Depends(get_db)):
    domain, severity, urgency, conf = analyze(f"{p.title} {p.description}")
    row = Problem(id=str(uuid.uuid4()), **p.model_dump(), domain=domain, severity=severity, urgency=urgency, ai_confidence=conf)
    db.add(row); audit(db, "PROBLEM_CREATED", "problem", row.id, f"domain={domain};severity={severity}"); db.commit(); db.refresh(row)
    return row

@app.get("/api/problems", response_model=list[ProblemOut])
def list_problems(db: Session = Depends(get_db), domain: str | None = None, status: str | None = None, severity: str | None = None, q: str | None = None):
    query = db.query(Problem).order_by(Problem.created_at.desc())
    if domain: query = query.filter(Problem.domain == domain.upper())
    if status: query = query.filter(Problem.status == status.upper())
    if severity: query = query.filter(Problem.severity == severity.upper())
    rows = query.all()
    if q:
        needle = q.lower(); rows = [p for p in rows if needle in p.title.lower() or needle in p.description.lower() or needle in (p.district or "").lower()]
    return rows

@app.get("/api/problems/map")
def problem_map(db: Session = Depends(get_db)):
    return [{"id":p.id,"title":p.title,"domain":p.domain,"severity":p.severity,"urgency":p.urgency,"status":p.status,"latitude":p.latitude,"longitude":p.longitude,"district":p.district,"people_affected":p.people_affected} for p in db.query(Problem).all()]

@app.get("/api/problems/{pid}", response_model=ProblemOut)
def get_problem(pid: str, db: Session = Depends(get_db)):
    p = db.get(Problem, pid)
    if not p: raise HTTPException(404, "Problem not found")
    return p

@app.patch("/api/problems/{pid}/status")
def update_status(pid: str, status: str, db: Session = Depends(get_db)):
    p = db.get(Problem, pid)
    if not p: raise HTTPException(404, "Problem not found")
    allowed = {"REPORTED", "VERIFIED", "FUSED", "IN_PROGRESS", "RESOLVED"}
    status = status.upper()
    if status not in allowed: raise HTTPException(400, f"Status must be one of {sorted(allowed)}")
    p.status = status; audit(db, "STATUS_UPDATED", "problem", pid, status); db.commit()
    return {"id": pid, "status": status}

@app.post("/api/problems/{pid}/media")
def upload_media(pid: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    p = db.get(Problem, pid)
    if not p: raise HTTPException(404, "Problem not found")
    ext = Path(file.filename or "").suffix.lower()[:10]
    name = f"{pid}-{uuid.uuid4().hex}{ext}"; target = UPLOADS / name
    with target.open("wb") as out: shutil.copyfileobj(file.file, out)
    p.image_url = f"/uploads/{name}"; audit(db, "MEDIA_UPLOADED", "problem", pid, name); db.commit()
    return {"image_url": p.image_url}

@app.post("/api/fusion/run/{pid}")
def run_fusion(pid: str, db: Session = Depends(get_db)):
    p = db.get(Problem, pid)
    if not p: raise HTTPException(404, "Problem not found")
    matches = []
    for o in db.query(Problem).filter(Problem.id != pid).all():
        dist = haversine(p.latitude, p.longitude, o.latitude, o.longitude)
        geo = 1.0 if dist <= 5 else 0.7 if dist <= 15 else 0.3 if dist <= 50 else 0.0
        sem = 1.0 if p.domain == o.domain else 0.6 if {p.domain, o.domain} in RELATED else 0.1
        kw = keyword_overlap(p.title + " " + p.description, o.title + " " + o.description)
        score = 0.35*sem + 0.20*geo + 0.20*kw + 0.25*(1.0 if p.urgency == o.urgency else 0.5)
        if score >= 0.45: matches.append((o, score, dist))
    matches.sort(key=lambda x: x[1], reverse=True)
    if not matches: return {"fused": False, "message": "No related problems above the fusion threshold", "threshold": 0.45}
    ids = [p.id] + [x[0].id for x in matches[:12]]
    title = f"{p.domain.title()} Systemic Cluster"
    root = f"Multiple {p.domain.lower()} reports in the same area indicate a shared systemic cause requiring coordinated intervention."
    action = "Verify the cluster on the ground, assign a responsible agency, and track a measurable intervention outcome."
    cluster = Cluster(id=str(uuid.uuid4()), title=title, domain=p.domain, problem_ids=json.dumps(ids), confidence=round(min(0.98, 0.50 + 0.06*len(matches)), 2), root_cause=root, recommended_action=action)
    db.add(cluster)
    for x in [p] + [m[0] for m in matches[:12]]: x.status = "FUSED"
    audit(db, "FUSION_RUN", "cluster", cluster.id, f"members={len(ids)}")
    db.commit()
    return {"fused": True, "cluster_id": cluster.id, "title": title, "members": len(ids), "confidence": cluster.confidence, "matches":[{"id":o.id,"title":o.title,"score":round(sc,3),"distance_km":round(dist,2)} for o,sc,dist in matches[:12]]}

@app.get("/api/clusters")
def list_clusters(db: Session = Depends(get_db)):
    out=[]
    for c in db.query(Cluster).order_by(Cluster.created_at.desc()).all():
        try: ids=json.loads(c.problem_ids or "[]")
        except Exception: ids=[]
        out.append({"id":c.id,"title":c.title,"domain":c.domain,"confidence":c.confidence,"member_count":len(ids),"root_cause":c.root_cause,"recommended_action":c.recommended_action})
    return out

@app.get("/api/clusters/{cid}")
def cluster_detail(cid: str, db: Session = Depends(get_db)):
    c=db.get(Cluster,cid)
    if not c: raise HTTPException(404,"Cluster not found")
    try: ids=json.loads(c.problem_ids or "[]")
    except Exception: ids=[]
    members=db.query(Problem).filter(Problem.id.in_(ids)).all() if ids else []
    return {"id":c.id,"title":c.title,"domain":c.domain,"confidence":c.confidence,"root_cause":c.root_cause,"recommended_action":c.recommended_action,"members":[ProblemOut.model_validate(x).model_dump(mode="json") for x in members]}

@app.get("/api/stats")
def stats(db: Session = Depends(get_db)):
    rows=db.query(Problem).all()
    return {"total_problems":len(rows),"high_priority":sum(p.severity=="HIGH" for p in rows),"fused":sum(p.status=="FUSED" for p in rows),"resolved":sum(p.status=="RESOLVED" for p in rows),"clusters":db.query(Cluster).count(),"people_affected":sum(p.people_affected or 0 for p in rows),"domains":{d:sum(p.domain==d for p in rows) for d in list(KEYWORDS)+["OTHER"]}}

@app.get("/api/audit")
def audit_logs(db: Session = Depends(get_db), limit: int = Query(50, ge=1, le=200)):
    return [{"id":x.id,"action":x.action,"entity_type":x.entity_type,"entity_id":x.entity_id,"detail":x.detail,"created_at":x.created_at} for x in db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()]

@app.post("/api/seed")
def seed(db: Session = Depends(get_db)):
    if db.query(Problem).count(): return {"seeded":False,"message":"Database already contains data"}
    demo=[
        ("Village drinking water shortage","No drinking water in summer and borewells are dry. Families depend on distant sources.","WATER",13.0827,80.2707,"Chennai",450),
        ("Groundwater stress affecting agriculture","Farmers report groundwater depletion affecting irrigation and paddy crops.","AGRICULTURE",13.0750,80.2600,"Chennai",180),
        ("Road damage near school","Road is severely damaged causing daily transport issues for school students.","TRANSPORT",13.0067,80.2206,"Chennai",320),
        ("Waste accumulation","Garbage is not collected regularly and drainage is blocked near residential streets.","SANITATION",13.0418,80.2341,"Chennai",700),
        ("Primary health centre medicine shortage","Patients report medicine shortages and long waiting times at the local clinic.","HEALTHCARE",13.0500,80.2500,"Chennai",250),
        ("Streetlight outage","Multiple streetlights are not working, creating safety concerns every night.","ENERGY",13.0900,80.2800,"Chennai",500),
        ("School classroom overcrowding","Students are sharing limited classroom space and learning resources.","EDUCATION",13.0600,80.2400,"Chennai",150),
        ("Air pollution near traffic junction","Vehicle congestion is causing worsening air quality around the junction.","ENVIRONMENT",13.0300,80.2100,"Chennai",900),
    ]
    for title,desc,dom,lat,lon,district,people in demo:
        d,s,u,c=analyze(title+" "+desc)
        db.add(Problem(id=str(uuid.uuid4()),title=title,description=desc,domain=d if d!="OTHER" else dom,severity=s,urgency=u,latitude=lat,longitude=lon,district=district,people_affected=people,ai_confidence=c))
    audit(db,"DATABASE_SEEDED","system",None,"8 demo problems")
    db.commit(); return {"seeded":True,"count":len(demo)}
