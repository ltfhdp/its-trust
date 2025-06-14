# uvicorn app.main:app --reload --port 8000

from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session, joinedload
from .database import SessionLocal, engine
from app import models, data_service
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import logging

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# === Schemas ===
class DeviceCreate(BaseModel):
    id: str
    name: str
    ownership_type: str
    device_type: str
    memory_gb: float
    location: str

class ConnectionCreate(BaseModel):
    device_id: str
    connected_device_id: str
    status: bool
    connection_type: str = "data"

class PeerRatingCreate(BaseModel):
    rater_device_id: str
    rated_device_id: str
    score: float
    comment: str = None
    update_trust: bool = False

class TrustRecord(BaseModel):
    timestamp: datetime
    trust_score: float
    connection_count: int
    last_connected_device_id: Optional[str] = None
    coordinator_id: Optional[str] = None
    notes: Optional[str] = None
    direct_trust: Optional[float] = None
    indirect_trust: Optional[float] = None
    centrality_score: Optional[float] = None

    class Config:
        orm_mode = True

class ReputationInfo(BaseModel):
    exists: bool
    trust_score: Optional[float] = None
    is_blacklisted: Optional[bool] = None
    is_flagged: Optional[bool] = None
    suspicious_count: Optional[int] = None
    reputation_level: Optional[str] = None
    last_suspicious_activity: Optional[datetime] = None
    recent_suspicious_types: Optional[List[str]] = None

# === Routes ===
@app.get("/")
def root():
    return {"message": "ITS Trust Backend"}

@app.post("/device")
def add_device(device: DeviceCreate, db: Session = Depends(get_db)):
    try:
        result = data_service.add_device(db, device)
        return result
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

@app.post("/device/{device_id}/leave")
def leave_device(device_id: str, db: Session = Depends(get_db)):
    try:
        data_service.leave_device(db, device_id)
        return {"message": f"Device {device_id} has left the system."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@app.post("/connect")
def connect_device(conn: ConnectionCreate, db: Session = Depends(get_db)):
    try:
        print(f"CONNECT: {conn.device_id} → {conn.connected_device_id}, type={conn.connection_type}, status={conn.status}")
        
        # Convert to format expected by merged function
        connection_data = {
            "source_id": conn.device_id,
            "target_id": conn.connected_device_id,
            "status": conn.status,
            "connection_type": conn.connection_type
        }
        
        result = data_service.record_connection(db, connection_data)
        return result
        
    except Exception as e:
        print(f"Connection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/devices/")
def list_devices(db: Session = Depends(get_db)):
    devices = db.query(models.Device).options(joinedload(models.Device.connections_received)).all()
    return devices

@app.get("/device/{device_id}")
def get_device(device_id: str, db: Session = Depends(get_db)):
    device = db.query(models.Device).filter_by(id=device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

@app.get("/device/{device_id}/history", response_model=List[TrustRecord])
def get_trust_history(device_id: str, db: Session = Depends(get_db)):
    history = db.query(models.TrustHistory).filter_by(device_id=device_id).order_by(models.TrustHistory.timestamp.asc()).all()
    return history

@app.get("/coordinator")
def get_current_coordinator(db: Session = Depends(get_db)):
    coord = db.query(models.Device).filter_by(is_coordinator=True).first()
    if not coord:
        raise HTTPException(status_code=404, detail="No coordinator found")
    return coord

@app.get("/coordinator/{coordinator_id}/history")
def get_trust_history_by_coordinator(coordinator_id: str, db: Session = Depends(get_db)):
    history = db.query(models.TrustHistory).filter_by(coordinator_id=coordinator_id).order_by(models.TrustHistory.timestamp.asc()).all()
    return history

@app.post("/rate_peer/")
def rate_peer(rating: PeerRatingCreate, db: Session = Depends(get_db)):
    try:
        data_service.add_peer_rating(
            db, 
            rating.rater_device_id, 
            rating.rated_device_id, 
            rating.score,
            reason=rating.comment,
            update_trust=rating.update_trust  # Set default
        )
        return {"message": "Peer rating recorded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/log_activity")
def get_log_activity(db: Session = Depends(get_db)):
    logs = []

     # TrustHistory
    history_entries = db.query(models.TrustHistory).all()
    for h in history_entries:
        activity_type = "malicious" if "blacklist" in (h.notes or "").lower() else "normal"
        status_detail = "trust_updated"
        if "joined" in (h.notes or "").lower():
            status_detail = "device_joined"
        elif "blacklist" in (h.notes or "").lower():
            status_detail = "blacklisted"
        elif "unregistered" in (h.notes or "").lower():
            status_detail = "denied_unregistered"
        elif "trust too low" in (h.notes or "").lower():
            status_detail = "trust_rejected"

        logs.append({
            "timestamp": h.timestamp,
            "device_id": h.device_id,
            "activity_type": activity_type,
            "description": h.notes,
            "connection_status": status_detail,
        })

    # Connection
    conn_entries = db.query(models.Connection).all()
    for c in conn_entries:
        status_detail = "success" if c.status else "failed"
        if c.connection_type != "data":
            status_detail += f"_{c.connection_type}"

        logs.append({
            "timestamp": c.timestamp,
            "device_id": c.source_device_id,
            "activity_type": "malicious" if not c.status else "normal",
            "description": f"Connection to {c.target_device_id} ({c.connection_type})",
            "connection_status": status_detail
        })

    # PeerRating (optional)
    rating_entries = db.query(models.PeerRating).all()
    for r in rating_entries:
        logs.append({
            "timestamp": r.timestamp,
            "device_id": r.rater_device_id,
            "activity_type": "normal",
            "description": f"Rated {r.rated_device_id} with score {r.score}",
            "connection_status": "peer_rating"
        })

    logs.sort(key=lambda x: x["timestamp"], reverse=True)
    return logs

@app.get("/reputation/{device_id}", response_model=ReputationInfo)
def get_reputation_endpoint(device_id: str, session: Session = Depends(get_db)):
    """
    Endpoint untuk mendapatkan informasi reputasi sebuah device.
    """
    reputation_info = data_service.get_device_reputation_info(session, device_id)
    
    if not reputation_info["exists"]:
        raise HTTPException(status_code=404, detail=f"Device with id {device_id} not found")
        
    return reputation_info
