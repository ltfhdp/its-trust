from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from fastapi import HTTPException
from .models import Device, Connection, TrustHistory, PeerRating
import requests
from typing import List
from sqlalchemy import case

TRUST_SERVICE_URL = "http://localhost:8001"
TRUST_THRESHOLD = 0.3
FLOODING_LIMIT = 15

def evaluate_security(device_id: str, conn_count_last_minute: int, session: Session):
    """
    Updated security evaluation dengan adaptive threshold
    """
    # Get device info
    device = session.get(Device, device_id)
    if not device:
        return {"penalty": 0.0, "blacklisted": False, "risk_level": "unknown"}
    
    # Get network stats
    active_count = get_active_device_count(session)
    
    # Call trust service dengan info lengkap
    res = requests.post(f"{TRUST_SERVICE_URL}/security/evaluate", json={
        "device_id": device_id,
        "conn_count_last_minute": conn_count_last_minute,
        "is_coordinator": device.is_coordinator,
        "total_active_devices": active_count
    })
    
    result = res.json()
    
    # Enhanced logging
    if result.get("risk_level") in ["moderate", "severe"]:
        role = "COORDINATOR" if device.is_coordinator else "MEMBER"
        print(f"🚨 FLOODING ALERT: {device_id} ({role}) - {conn_count_last_minute}/{result.get('threshold_used')} connections")
        print(f"   Risk: {result.get('risk_level')}, Penalty: {result.get('penalty')}")
    
    return result

def ensure_valid_coordinator(session: Session):
    current = session.query(Device).filter_by(is_coordinator=True).first()
    if current and not current.is_blacklisted and current.trust_score >= TRUST_THRESHOLD:
        return current
    return select_coordinator(session)

def update_trust_score(session: Session, device: Device, peer: Device, success: bool):
    # --- 1. Ambil 5 rating terbaru selain dari peer saat ini
    ratings = session.query(PeerRating)\
        .filter(PeerRating.rated_device_id == device.id)\
        .filter(PeerRating.rater_device_id != peer.id)\
        .order_by(PeerRating.timestamp.desc())\
        .limit(5)\
        .all()
    rating_scores = [r.score for r in ratings]

    # --- 2. Hitung centrality dari jumlah source unik
    centrality_raw = session.query(Connection.source_device_id)\
        .filter(Connection.target_device_id == device.id)\
        .filter(Connection.status == True)\
        .distinct()\
        .count()

    # --- 3. Kirim ke trust service
    try:
        start_eval = datetime.utcnow()

        res = requests.post(f"{TRUST_SERVICE_URL}/trust/calculate", json={
            "last_trust": device.trust_score,
            "success": success,
            "peer_ratings": rating_scores,
            "centrality_raw": centrality_raw
        })
        result = res.json()

        end_eval = datetime.utcnow()
        eval_duration = (end_eval - start_eval).total_seconds()

        device.trust_score = result["updated_trust"]
        device.is_blacklisted = result["blacklisted"]

        # --- Logging blacklist event
        if result["blacklisted"]:
            print(f"🛑 [BLACKLIST] Device {device.id} diblacklist setelah evaluasi {eval_duration:.3f}s")
        else:
            print(f"✅ [SAFE] Device {device.id} lolos evaluasi (durasi {eval_duration:.3f}s)")

        # --- Simpan history
        coordinator = session.query(Device).filter_by(is_coordinator=True).first()
        coordinator_id = coordinator.id if coordinator else None

        session.add(TrustHistory(
            device_id=device.id,
            trust_score=result["updated_trust"],
            connection_count=device.connection_count,
            last_connected_device_id=peer.id,
            notes=f"Connection {'success' if success else 'failed'} with {peer.id}",
            coordinator_id=coordinator_id,
            direct_trust=result.get("direct_trust"),
            indirect_trust=result.get("indirect_trust"),
            centrality_score=result.get("centrality_score")
        ))

    except Exception as e:
        print(f"❌ Error contacting trust service: {e}")

    # Jika koordinator sekarang sudah di-blacklist, trigger pemilihan ulang
    if device.is_coordinator and (device.is_blacklisted or device.trust_score < TRUST_THRESHOLD):
        print(f"⚠️ Coordinator {device.id} tidak layak, akan diganti")
        ensure_valid_coordinator(session)


def leave_device(session: Session, device_id: str):
    device = session.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise ValueError("Device not found")
    if device.is_blacklisted:
        raise ValueError("Blacklisted device cannot leave. It must be reviewed manually.")
    if not device.is_active:
        raise ValueError("Device already inactive")

    device.is_active = False
    device.left_at = datetime.utcnow()

    session.add(TrustHistory(
        device_id=device.id,
        trust_score=device.trust_score,
        connection_count=device.connection_count,
        last_connected_device_id=None,
        notes="Device left the system",
        coordinator_id=None
    ))

    session.commit()

def check_device_history(session: Session, device_id: str) -> dict:
    """Cek apakah device pernah di-blacklist atau punya history buruk"""
    
    # Cek history trust terakhir
    last_history = session.query(TrustHistory)\
        .filter_by(device_id=device_id)\
        .order_by(TrustHistory.timestamp.desc())\
        .first()
    
    if not last_history:
        return {"status": "new", "can_join": True}
    
    # Cek apakah pernah blacklisted
    blacklist_history = session.query(TrustHistory)\
        .filter_by(device_id=device_id)\
        .filter(TrustHistory.notes.like('%blacklist%'))\
        .first()
    
    if blacklist_history:
        # Cek berapa lama sejak blacklist
        days_since = (datetime.utcnow() - blacklist_history.timestamp).days
        
        if days_since < 30:  # Cooling period 30 hari
            return {
                "status": "recently_blacklisted", 
                "can_join": False,
                "reason": f"Blacklisted {days_since} days ago"
            }
        else:
            return {
                "status": "previously_blacklisted", 
                "can_join": True,
                "initial_trust": 0.1  # Trust rendah untuk ex-blacklisted
            }
    
    # Cek rata-rata trust historis
    avg_trust = session.query(TrustHistory.trust_score)\
        .filter_by(device_id=device_id)\
        .all()
    
    if avg_trust:
        historical_avg = sum([t[0] for t in avg_trust]) / len(avg_trust)
        
        return {
            "status": "returning",
            "can_join": True,
            "historical_trust": historical_avg,
            "initial_trust": max(0.2, historical_avg * 0.8)  # 80% dari rata-rata historis
        }
    
    return {"status": "unknown", "can_join": True}

# Tambah device baru ke sistem
def add_device(session: Session, device_data):
    from .models import Device
    device = session.query(Device).filter(Device.id == device_data.id).first()

    # --- Jika device sudah pernah ada ---
    if device:
        # Gunakan check_device_history untuk validasi yang lebih komprehensif
        history_check = check_device_history(session, device_data.id)
        
        if not history_check["can_join"]:
            raise ValueError(history_check["reason"])
            
        if device.is_active:
            raise ValueError("Device already exists and is active.")

        # Rejoin device dengan trust dari history check jika ada
        device.is_active = True
        device.left_at = None
        
        if "initial_trust" in history_check:
            device.trust_score = history_check["initial_trust"]

        session.add(TrustHistory(
            device_id=device.id,
            trust_score=device.trust_score,
            connection_count=device.connection_count,
            last_connected_device_id=None,
            notes=f"Device rejoined - {history_check['status']}",
            coordinator_id=None
        ))

        session.commit()
        return device

    # --- Device benar-benar baru ---
    res = requests.post(f"{TRUST_SERVICE_URL}/trust/initial", json=device_data.model_dump())
    trust_result = res.json()
    
    initial_trust = trust_result["trust_score"]
    computing_power = trust_result.get("computing_power", 0.5)  # Default jika tidak ada

    if initial_trust < TRUST_THRESHOLD:
        raise ValueError("Device rejected due to low trust score")

    new_device = Device(
        id=device_data.id,
        name=device_data.name,
        device_type=device_data.device_type,
        ownership_type=device_data.ownership_type,
        memory_gb=device_data.memory_gb,
        computing_power=computing_power,  # Simpan computing power dari trust service
        location=device_data.location,
        trust_score=initial_trust,
        connection_count=0,
        is_blacklisted=False,
        is_coordinator=False,
        is_active=True
    )

    session.add(new_device)
    session.commit()

    session.add(TrustHistory(
        device_id=new_device.id,
        trust_score=new_device.trust_score,
        connection_count=0,
        last_connected_device_id=None,
        notes="Device registered",
        coordinator_id=None
    ))
    session.commit()

    ensure_valid_coordinator(session)

    return new_device

# --- Fungsi rating yang disederhanakan ---
def add_peer_rating(session: Session, rater_id: str, rated_id: str, score: float, reason: str = None, update_trust: bool = False):
    """Universal peer rating function"""
    # Validate devices
    rater = session.get(Device, rater_id)
    rated = session.get(Device, rated_id)
    if not rater or not rated:
        raise ValueError("Device not found")
    
    # Add rating
    rating = PeerRating(
        rater_device_id=rater_id,
        rated_device_id=rated_id,
        score=score,
        comment=reason
    )
    session.add(rating)
    session.commit()
    
    # Optional trust update
    if update_trust:
        update_trust_score(session, rated, rater, True)
        session.commit()
    
    return rating

def handle_flooding_check(session: Session, source_id: str, source: Device):
    if source.is_blacklisted:
        return

    """Updated helper function dengan adaptive threshold"""
    recent_conn = session.query(Connection).filter(
        Connection.source_device_id == source_id,
        Connection.timestamp >= datetime.utcnow() - timedelta(seconds=60)
    ).count()

    # Gunakan evaluate_security yang sudah updated
    sec_eval = evaluate_security(source_id, recent_conn, session)
    
    # Apply penalty dan blacklist
    source.trust_score = max(0.0, source.trust_score - sec_eval["penalty"])
    
    # Blacklist hanya untuk severe cases
    if sec_eval.get("blacklisted", False):
        source.is_blacklisted = True
        print(f"🛑 BLACKLISTED: {source_id} due to severe flooding")
    
    # Warning untuk moderate cases
    elif sec_eval.get("risk_level") == "moderate":
        print(f"⚠️  WARNING: {source_id} showing moderate flooding behavior")

def update_connection_stats(device: Device, status: bool):
    """Helper function untuk update statistik koneksi"""
    device.is_active = True  # Fix: gunakan is_active bukan active
    if status:
        device.successful_connections += 1
    else:
        device.failed_connections += 1
    device.connection_count = device.successful_connections + device.failed_connections

def record_connection_batch(session: Session, connections: List[dict], update_trust: bool = True):
    affected_devices = set()
    
    for conn_data in connections:
        source_id = conn_data["source_id"]
        target_id = conn_data["target_id"]
        status = conn_data["status"]
        connection_type = conn_data.get("connection_type", "data")

        source = session.get(Device, source_id)
        target = session.get(Device, target_id)
        
        if not source or not target:
            continue

        # Flooding check
        handle_flooding_check(session, source_id, source)

        # Record connection
        conn = Connection(
            source_device_id=source_id,
            target_device_id=target_id,
            status=status,
            connection_type=connection_type
        )
        session.add(conn)

        if source.is_blacklisted or target.is_blacklisted:
            continue

        # Update stats untuk kedua device
        update_connection_stats(source, status)
        update_connection_stats(target, status)

        affected_devices.add((source, target, status))

    # Update trust untuk semua affected devices
    if update_trust:
        processed = set()
        for source, target, status in affected_devices:
            if source.id not in processed:
                update_trust_score(session, source, target, status)
                processed.add(source.id)
            if target.id not in processed:
                update_trust_score(session, target, source, status)
                processed.add(target.id)

    session.commit()

# --- Connection Individual ---
def record_connection(session: Session, source_id: str, target_id: str, status: bool, connection_type: str = "data", update_trust: bool = True):
    source = session.get(Device, source_id)
    target = session.get(Device, target_id)

    if not source:
        print(f"🚨 UNREGISTERED ACCESS: {source_id} attempted to connect")
        return {"status": "failed", "reason": "source device not registered"}
    if not target:
        print(f"🚨 UNREGISTERED ACCESS: {target_id} not found")
        return {"status": "failed", "reason": "target device not registered"}

    # Flooding check
    handle_flooding_check(session, source_id, source)

    # Record connection
    conn = Connection(
        source_device_id=source_id,
        target_device_id=target_id,
        status=status,
        connection_type=connection_type
    )
    session.add(conn)

    if source.is_blacklisted or target.is_blacklisted:
        session.commit()
        return

    # Update stats
    update_connection_stats(source, status)
    update_connection_stats(target, status)

    # Update trust
    if update_trust:
        update_trust_score(session, source, target, status)
        update_trust_score(session, target, source, status)

    session.commit()
   

# Pemilihan koordinator otomatis
def select_coordinator(session: Session):
    # Reset jika tidak layak
    session.query(Device).update({Device.is_coordinator: False})
    session.commit()

    print("🔁 Selecting new coordinator...")

    # Hanya internal devices - RSU internal > Computer internal berdasarkan trust
    internal_coordinator = session.query(Device).filter(
        Device.is_blacklisted == False,
        Device.ownership_type == "internal",
        Device.device_type.in_(["RSU", "Computer"]),  # High intelligence factor
        Device.trust_score >= TRUST_THRESHOLD,
        Device.is_active == True
    ).order_by(
        # Prioritas: RSU internal > Computer internal, lalu trust tertinggi
        case((Device.device_type == "RSU", 0), else_=1),
        Device.trust_score.desc()
    ).first()

    if internal_coordinator:
        internal_coordinator.is_coordinator = True
        session.commit()
        print(f"✅ Internal coordinator: {internal_coordinator.id} ({internal_coordinator.device_type})")
        return internal_coordinator

    print("❌ No eligible internal devices found for coordinator")
    return None

def get_active_device_count(session: Session) -> int:
    """Helper function untuk menghitung jumlah device aktif"""
    return session.query(Device).filter(
        Device.is_active == True,
        Device.is_blacklisted == False
    ).count()