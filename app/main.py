from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session, joinedload
from .database import SessionLocal, engine
from app import models, data_service
from pydantic import BaseModel
from typing import List

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

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
    device_type: str  # internal / external
    memory_gb: float
    location: str

class ConnectionCreate(BaseModel):
    device_id: str
    connected_device_id: str
    status: bool


class PeerRatingCreate(BaseModel):
    rater_device_id: str
    rated_device_id: str
    score: float
    comment: str = None

# === Routes ===
@app.post("/device/")
def create_device(device: DeviceCreate, db: Session = Depends(get_db)):
    try:
        return data_service.add_device(db, device.dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/connect/")
def connect_device(conn: ConnectionCreate, db: Session = Depends(get_db)):
    try:
        print(f"📡 CONNECT: {conn.device_id} → {conn.connected_device_id}, status={conn.status}") #debugging
        data_service.record_connection(db, conn.device_id, conn.connected_device_id, conn.status)
        return {"message": "Connection recorded and trust updated"}
    except Exception as e:
        print(f"❌ ERROR: {e}") # debugging
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

@app.get("/device/{device_id}/history")
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
    history = db.query(models.TrustHistory).filter_by(coordinator_id).order_by(models.TrustHistory.timestamp.asc()).all()
    return history

@app.post("/rate_peer/")
def rate_peer(rating: PeerRatingCreate, db: Session = Depends(get_db)):
    try:
        data_service.rate_peer(db, rating.rated_device_id, rating.rated_device_id, rating.score)
        return {"message": "Peer rating recorded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))