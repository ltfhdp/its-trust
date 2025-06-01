from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from fastapi import HTTPException
from .models import Device, Connection, TrustHistory, PeerRating
import requests
from typing import List

TRUST_SERVICE_URL = "http://localhost:8001"
TRUST_THRESHOLD = 0.3
FLOODING_LIMIT = 15

def get_initial_trust(ownership_type, memory_gb, device_type):
    res = requests.post(f"{TRUST_SERVICE_URL}/trust/initial", json={
        "ownership_type": ownership_type,
        "memory_gb": memory_gb,
        "device_type": device_type
    })
    return res.json()["trust_score"]

def get_computing_weight(device_type):
    res = requests.get(f"{TRUST_SERVICE_URL}/trust/weight/{device_type}")
    return res.json()["computing_power"]

def evaluate_security(device_id: str, conn_count_last_minute: int):
    res = requests.post(f"{TRUST_SERVICE_URL}/security/evaluate", json={
        "device_id": device_id,
        "conn_count_last_minute": conn_count_last_minute
    })
    return res.json()

def update_trust_score(session: Session, device: Device, peer: Device, success: bool):
    from .models import PeerRating, Connection, TrustHistory, Device
    import requests
    from datetime import datetime

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

# Tambah device baru ke sistem
def add_device(session: Session, device_data: dict) -> Device:
    # Cek history dulu
    history_check = check_device_history(session, device_data["id"])
    
    if not history_check["can_join"]:
        raise HTTPException(status_code=403, detail=history_check["reason"])
    
    #kalau ada history, pakai initial trust dr history
    if "initial_trust" in history_check:
        trust_score = history_check["initial_trust"]
    else:
        trust_score = get_initial_trust(
            ownership_type=device_data["ownership_type"],
            memory_gb=device_data["memory_gb"],
            device_type=device_data["device_type"]
        )

    if trust_score < TRUST_THRESHOLD:
        raise HTTPException(status_code=403, detail="Device rejected due to low trust score")

    computing_power = get_computing_weight(device_data["device_type"])

    device = Device(
        id=device_data["id"],
        name=device_data["name"],
        ownership_type=device_data["ownership_type"],
        device_type=device_data["device_type"],
        memory_gb=device_data["memory_gb"],
        computing_power=computing_power,
        location=device_data["location"],
        trust_score=trust_score
    )
    session.add(device)
    session.commit()

    history = TrustHistory(
        device_id=device.id,
        trust_score=trust_score,
        connection_count=0,
        notes="Device joined"
    )
    session.add(history)
    session.commit()

    select_coordinator(session)
    return device

# --- Rating Manual atau Otomatis ---
def add_peer_rating_simple(session: Session, rater_id: str, rated_id: str, score: float):
    session.add(PeerRating(
        rater_device_id=rater_id,
        rated_device_id=rated_id,
        score=score
    ))

def rate_peer(session: Session, rater_id: str, rated_id: str, score: float):
    session.add(PeerRating(
        rater_device_id=rater_id,
        rated_device_id=rated_id,
        score=score
    ))
    session.commit()

    # Optional: update trust secara langsung, atau bisa dijadwalkan
    rater = session.get(Device, rater_id)
    rated = session.get(Device, rated_id)
    if rater and rated:
        update_trust_score(session, rater, rated, True)
        update_trust_score(session, rated, rater, True)
        session.commit()

def record_connection_batch(session: Session, connections: List[dict], update_trust: bool = True):
    affected_devices = set()
    for conn_data in connections:
        source_id = conn_data["source_id"]
        target_id = conn_data["target_id"]
        status = conn_data["status"]
        connection_type = conn_data.get("connection_type", "data")

        recent_conn = session.query(Connection).filter(
            Connection.source_device_id == source_id,
            Connection.timestamp >= datetime.utcnow() - timedelta(seconds=60)
        ).count()

        if recent_conn >= FLOODING_LIMIT:
            print(f"🚨 ALERT: {source_id} suspected of spamming")
            sec_eval = evaluate_security(source_id, recent_conn)
            device = session.get(Device, source_id)
            if device:
                device.trust_score = max(0.0, device.trust_score - sec_eval["penalty"])
                device.is_blacklisted = sec_eval["blacklisted"]

        conn = Connection(
            source_device_id=source_id,
            target_device_id=target_id,
            status=status,
            connection_type=connection_type
        )
        session.add(conn)

        source = session.get(Device, source_id)
        target = session.get(Device, target_id)
        if not source or not target or source.is_blacklisted or target.is_blacklisted:
            continue

        source.active = True
        target.active = True
        if status:
            source.successful_connections += 1
            target.successful_connections += 1
        else:
            source.failed_connections += 1
            target.failed_connections += 1

        source.connection_count = source.successful_connections + source.failed_connections
        target.connection_count = target.successful_connections + target.failed_connections

        add_peer_rating_simple(session, source_id, target_id, 1.0 if status else 0.0)
        add_peer_rating_simple(session, target_id, source_id, 1.0 if status else 0.0)

        affected_devices.add((source, target, status))

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
    select_coordinator(session)

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

    recent_conn = session.query(Connection).filter(
        Connection.source_device_id == source_id,
        Connection.timestamp >= datetime.utcnow() - timedelta(seconds=60)
    ).count()

    if recent_conn >= FLOODING_LIMIT:
        sec_eval = evaluate_security(source_id, recent_conn)
        source.trust_score = max(0.0, source.trust_score - sec_eval["penalty"])
        source.is_blacklisted = sec_eval["blacklisted"]

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

    source.active = True
    target.active = True
    if status:
        source.successful_connections += 1
        target.successful_connections += 1
    else:
        source.failed_connections += 1
        target.failed_connections += 1

    source.connection_count = source.successful_connections + source.failed_connections
    target.connection_count = target.successful_connections + target.failed_connections

    add_peer_rating_simple(session, source_id, target_id, 1.0 if status else 0.0)
    add_peer_rating_simple(session, target_id, source_id, 1.0 if status else 0.0)

    if update_trust:
        update_trust_score(session, source, target, status)
        update_trust_score(session, target, source, status)

    session.commit()
    if update_trust:
        select_coordinator(session)

# Pemilihan koordinator otomatis
def select_coordinator(session: Session):
    # Ambil koordinator aktif
    current = session.query(Device).filter_by(is_coordinator=True).first()

    if current and not current.is_blacklisted and current.trust_score >= TRUST_THRESHOLD:
        print(f"✅ Coordinator remains: {current.id}")
        return current  # Masih layak

    # Reset jika tidak layak
    session.query(Device).update({Device.is_coordinator: False})
    session.commit()

    print("🔁 Selecting new coordinator...")

    # Prioritas 1: RSU dengan trust tertinggi
    rsu = session.query(Device).filter_by(
        device_type="RSU", 
        is_blacklisted=False
    ).filter(
        Device.trust_score >= TRUST_THRESHOLD
    ).order_by(Device.trust_score.desc()).first()
    
    if rsu:
        rsu.is_coordinator = True
        session.commit()
        print(f"✅ New RSU coordinator: {rsu.id}")
        return rsu

    # Prioritas 2: Internal device (Computer/RSU) dengan trust tertinggi
    best = session.query(Device).filter(
        Device.is_blacklisted == False,
        Device.ownership_type == "internal",
        Device.device_type.in_(["RSU", "Computer"]),
        Device.trust_score >= TRUST_THRESHOLD
    ).order_by(Device.trust_score.desc()).first()

    if best:
        best.is_coordinator = True
        session.commit()
        print(f"✅ Fallback coordinator: {best.id}")
        return best

    print("❌ No eligible devices found for coordinator")
    return None

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