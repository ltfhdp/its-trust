from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from .models import Device, Connection, TrustHistory, PeerRating
import requests
from sqlalchemy import case, select, func
import logging
import os

TRUST_SERVICE_URL = os.getenv("TRUST_SERVICE_URL", "http://localhost:8001")
TRUST_THRESHOLD = 0.3

def setup_logger():
    logger = logging.getLogger(__name__)
    
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.DEBUG)
    
    console_handler = logging.StreamHandler()
    console_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    console_handler.setLevel(getattr(logging, console_level))
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    # File handler 
    file_handler = logging.FileHandler('trust_system.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

logger = setup_logger()

def evaluate_security(device_id: str, conn_count_last_minute: int, session: Session):
    device = session.get(Device, device_id)
    if not device:
        return {"penalty": 0.0, "blacklisted": False}
    
    try:
        res = requests.post(f"{TRUST_SERVICE_URL}/security/evaluate", json={
            "device_id": device_id,
            "conn_count_last_minute": conn_count_last_minute,
            "is_coordinator": device.is_coordinator
        })
        res.raise_for_status()  
        return res.json() 
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to call trust service for security evaluation: {e}")
        return {"penalty": 0.0, "threshold_used": 0}

def ensure_valid_coordinator(session: Session):
    current = session.query(Device).filter_by(is_coordinator=True).first()
    if current and not current.is_blacklisted and current.trust_score >= TRUST_THRESHOLD:
        return current
    old_coordinator_id = current.id if current else None
    return select_coordinator(session, old_coordinator_id=old_coordinator_id)

def update_trust_score(session: Session, device: Device, peer: Device, success: bool):
    if device.is_blacklisted:
        logger.debug(f"SKIP_UPDATE: Device {device.id} is blacklisted, skipping trust update")
        return
    
    if peer.is_blacklisted:
        logger.debug(f"SKIP_UPDATE: Peer {peer.id} is blacklisted, skipping trust update for {device.id}")
        return
    
    # mengambil 15 rating terbaru selain dari peer saat ini
    subquery = (
        select(Connection.status)
        .correlate(PeerRating)
        .where(
            ((Connection.source_device_id == PeerRating.rater_device_id) & (Connection.target_device_id == PeerRating.rated_device_id)) |
            ((Connection.source_device_id == PeerRating.rated_device_id) & (Connection.target_device_id == PeerRating.rater_device_id))
        )
        .where (Connection.timestamp < PeerRating.timestamp)
        .order_by(Connection.timestamp.desc())
        .limit(1)
        .as_scalar()
    )
    
    results = session.query(
        PeerRating.score,
        subquery.label("connection_status")
        )\
        .filter(PeerRating.rated_device_id == device.id)\
        .filter(PeerRating.rater_device_id != peer.id)\
        .filter(subquery != None)\
        .order_by(PeerRating.timestamp.desc())\
        .limit(15)\
        .all()
    
    peer_evaluations = []
    for score, status in results:
        peer_evaluations.append({
            "rating_score": score,
            "interaction_was_successful": status
        })

    # centrality dari jumlah source unik
    successful_peers_q = session.query(Connection.source_device_id)\
        .filter(Connection.target_device_id == device.id)\
        .filter(Connection.status == True)\
        .distinct()

    db_successful_peers = {row[0] for row in successful_peers_q.all()}

    # menambahkan peer saat ini jika koneksi sukses
    if success:
        db_successful_peers.add(peer.id)
    
    centrality_raw = len(db_successful_peers)

    # mengirim ke trust service
    try:
        start_eval = datetime.utcnow()

        res = requests.post(f"{TRUST_SERVICE_URL}/trust/calculate", json={
            "last_trust": device.trust_score,
            "success": success,
            "peer_evaluations": peer_evaluations,
            "centrality_raw": centrality_raw
        })
        result = res.json()

        end_eval = datetime.utcnow()
        eval_duration = (end_eval - start_eval).total_seconds()

        device.trust_score = result["updated_trust"]
        device.is_blacklisted = result["blacklisted"]

        # blacklist event
        if result["blacklisted"]:
            device.blacklisted_at = datetime.utcnow() 
            detection_time = (device.blacklisted_at - device.created_at).total_seconds()
            logger.warning(f"BLACKLIST: Device {device.id} blacklisted after evaluation {eval_duration:.3f}s with detection time: {detection_time:.3f} after joined")
        else:
            logger.info(f"SAFE: Device {device.id} passed evaluation (duration {eval_duration:.3f}s)")

        # menyimpan history
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
        logger.error(f"Error contacting trust service: {e}")

    # blacklist jika skor di bawah ambang batas dan belum di-blacklist
    if device.trust_score < TRUST_THRESHOLD and not device.is_blacklisted:
        blacklist_reason = f"Trust score ({device.trust_score:.3f}) fell below threshold ({TRUST_THRESHOLD})."
        blacklist_device(session, device, blacklist_reason)

    # jika koordinator sekarang sudah di-blacklist, trigger pemilihan ulang
    if device.is_coordinator and (device.is_blacklisted or device.trust_score < TRUST_THRESHOLD):
        logger.warning(f"Coordinator {device.id} unfit, will be replaced")
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
    is_blacklisted_before = session.query(TrustHistory)\
        .filter(TrustHistory.device_id == device_id)\
        .filter(TrustHistory.notes.like('%blacklist%'))\
        .first()
    
    if is_blacklisted_before:
        return {
            "status": "previously_blacklisted", 
            "can_join": False,
            "reason": f"Device {device_id} has a history of being blacklisted."
        }
    
    last_history = session.query(TrustHistory)\
        .filter(TrustHistory.device_id == device_id)\
        .order_by(TrustHistory.timestamp.desc())\
        .first()
    
    if last_history:
        last_known_score = last_history.trust_score
        new_initial_trust = last_known_score
        return {
            "status": "returning",
            "can_join": True,
            "initial_trust": new_initial_trust
        }
    
    # jika tidak ditemukan histori sama sekali
    return {"status": "unknown", "can_join": True}

def add_device(session: Session, device_data):
    from .models import Device
    device = session.query(Device).filter(Device.id == device_data.id).first()

    # jika device sudah pernah regis
    if device:
        if device.is_blacklisted:
            reason = f"Device {device.id} has been permanently blacklisted."
            logger.warning(f"REJOIN_BLOCKED: {reason}")
            raise ValueError(reason) # BLOKIR SECARA TEGAS

        history_check = check_device_history(session, device_data.id)
        
        if not history_check["can_join"]:
            raise ValueError(history_check["reason"])
            
        if device.is_active:
            raise ValueError("Device already exists and is active.")

        # rejoin device dengan trust dari history check jika ada
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

    # device baru
    res = requests.post(f"{TRUST_SERVICE_URL}/trust/initial", json=device_data.model_dump())
    trust_result = res.json()
    
    initial_trust = trust_result["trust_score"]
    computing_power = trust_result.get("computing_power", 0.5)  # default jika tidak ada

    if initial_trust < TRUST_THRESHOLD:
        raise ValueError("Device rejected due to low trust score")

    new_device = Device(
        id=device_data.id,
        name=device_data.name,
        device_type=device_data.device_type,
        ownership_type=device_data.ownership_type,
        memory_gb=device_data.memory_gb,
        computing_power=computing_power,  
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

def add_peer_rating(session: Session, rater_id: str, rated_id: str, score: float, reason: str = None, update_trust: bool = False):
    # validasi devices
    rater = session.get(Device, rater_id)
    rated = session.get(Device, rated_id)
    if not rater or not rated:
        raise ValueError("Device not found")
    
    if rater.is_blacklisted:
        logger.warning(f"BLACKLIST_VIOLATION: Blacklisted device {rater.id} attempted to rate {rated.id}. Action blocked.")
        raise ValueError(f"Device {rater.id} is blacklisted and cannot perform this action.")
    
    if rated.is_blacklisted:
        logger.warning(f"BLACKLIST_VIOLATION: Attempt to rate blacklisted device {rated.id}. Action blocked.")
        raise ValueError(f"Device {rated.id} is blacklisted and cannot be rated.")
    
    # cari koneksi terakhir antara kedua device ini
    last_interaction = session.query(Connection).filter(
        ((Connection.source_device_id == rater_id) & (Connection.target_device_id == rated_id)) |
        ((Connection.source_device_id == rated_id) & (Connection.target_device_id == rater_id))
    ).order_by(Connection.timestamp.desc()).first()

    is_dishonest = False
    dishonest_type = None
    log_reason = "" 

    if last_interaction:
        last_status_success = last_interaction.status

        # badmouthing
        if last_status_success and score < 0.4 and not rated.is_flagged and not rated.is_blacklisted:
            is_dishonest = True
            dishonest_type = "badmouthing"
            log_reason = f"Bad-mouthing: Gave low score ({score}) to a reputable device after a successful connection."
            
        # collusion
        elif not last_status_success and score > 0.6:
            is_dishonest = True
            dishonest_type= "collusion"
            log_reason = f"Collusion: Gave high score ({score}) after a failed connection."

    # PENALTI karena DISHONEST
    if is_dishonest:
        penalty = 0.15
        
        old_trust_score = rater.trust_score
        
        rater.suspicious_count += 1
        rater.last_suspicious_activity = datetime.utcnow()

        import json
        reasons_list = json.loads(rater.suspicious_reasons or "[]") 
        reasons_list.append({ 
            "type": dishonest_type,
            "timestamp": datetime.utcnow().isoformat(),
            "details": log_reason
        })
        rater.suspicious_reasons = json.dumps(reasons_list[-10:]) 

        if rater.suspicious_count >= 3:
            rater.is_flagged = True
            logger.warning(f"FLAGGED: Device {rater.id} flagged after {rater.suspicious_count} suspicious activities")
        
        rater.trust_score = max(0.0, rater.trust_score - penalty)
        
        logger.warning(f"DISHONEST RATING: Device {rater.id} trust_score directly reduced from {old_trust_score:.3f} to {rater.trust_score:.3f} (suspicious: {rater.suspicious_count}).")

        penalty_log = TrustHistory(
            device_id=rater.id,
            trust_score=rater.trust_score,
            connection_count=rater.connection_count,
            notes=f"Dishonest rating penalty (suspicious count: {rater.suspicious_count}). Reason: {log_reason}"
        )
        session.add(penalty_log)

    rating = PeerRating(
        rater_device_id=rater_id, rated_device_id=rated_id, score=score, comment=reason
    )
    session.add(rating)
    session.commit()
    return rating

def get_device_reputation_info(session: Session, device_id: str) -> dict:
    device = session.get(Device, device_id)
    if not device:
        return {"exists": False}
    
    # parse suspicious reasons untuk analisis
    import json
    reasons = json.loads(device.suspicious_reasons or "[]")
    recent_reasons = [r for r in reasons if r.get("type")]
    
    return {
        "exists": True,
        "trust_score": device.trust_score,
        "is_blacklisted": device.is_blacklisted,
        "is_flagged": device.is_flagged,
        "suspicious_count": device.suspicious_count,
        "reputation_level": get_reputation_level(device),
        "last_suspicious_activity": device.last_suspicious_activity,
        "recent_suspicious_types": [r["type"] for r in recent_reasons[-3:]]  
    }

def get_reputation_level(device: Device) -> str:
    if device.is_blacklisted:
        return "BLACKLISTED"
    elif device.is_flagged:
        if device.suspicious_count >= 5:
            return "VERY_SUSPICIOUS"
        else:
            return "SUSPICIOUS"
    elif device.trust_score >= 0.8:
        return "EXCELLENT"
    elif device.trust_score >= 0.6:
        return "GOOD"
    elif device.trust_score >= 0.4:
        return "AVERAGE"
    else:
        return "POOR"
    
def handle_flooding_check(session: Session, source_id: str, source: Device):
    if source.is_blacklisted:
        logger.debug(f"SKIP_FLOOD_CHECK: Device {source.id} is blacklisted")
        return

    recent_conn = session.query(Connection).filter(
        Connection.source_device_id == source_id,
        Connection.timestamp >= datetime.utcnow() - timedelta(seconds=60)
    ).count()

    sec_eval = evaluate_security(source_id, recent_conn, session)

    if sec_eval["penalty"] > 0:
        source.suspicious_count += 1
        source.last_suspicious_activity = datetime.utcnow()

        import json
        reason = json.loads(source.suspicious_reasons or "[]")
        reason.append({
            "type": "flooding",
            "timestamp": datetime.utcnow().isoformat(),
            "details": f"Recent connections: {recent_conn}"
        })
        source.suspicious_reasons = json.dumps(reason[-10:])

        if source.suspicious_count >= 2:
            source.is_flagged = True
            logger.warning(f"FLAGGED: Device {source.id} flagged after {source.suspicious_count} suspicious activities")
    
        source.trust_score = max(0.0, source.trust_score - sec_eval["penalty"])

        flood_log = TrustHistory(
            device_id=source.id,
            trust_score=source.trust_score,
            connection_count=source.connection_count,
            notes=f"Flooding detected (suspicious count: {source.suspicious_count}). Recent: {recent_conn}"
        )
        session.add(flood_log)
        logger.warning(f"FLOODING: Device {source.id} - {recent_conn} connections in 1min (penalty: {sec_eval['penalty']}, total suspicious: {source.suspicious_count})")

def record_connection(session: Session, connections, update_trust: bool = True):
    if isinstance(connections, dict):
        connections = [connections]
    
    affected_devices = set()
    
    for conn_data in connections:
        source_id = conn_data["source_id"]
        target_id = conn_data["target_id"] 
        status = conn_data["status"]
        connection_type = conn_data.get("connection_type", "data")

        source = session.get(Device, source_id)
        target = session.get(Device, target_id)
        
        if not source:
            logger.error(f"UNREGISTERED ACCESS: {source_id} attempted to connect")
            continue
        if not target:
            logger.error(f"UNREGISTERED ACCESS: {target_id} not found")
            continue

        if source.is_blacklisted or target.is_blacklisted:
            logger.warning(
                f"BLACKLIST_VIOLATION: Connection between {source_id} (blacklisted: {source.is_blacklisted}) "
                f"and {target_id} (blacklisted: {target.is_blacklisted}) was blocked."
            )
            continue 

        handle_flooding_check(session, source_id, source)

        conn = Connection(
            source_device_id=source_id,
            target_device_id=target_id,
            status=status,
            connection_type=connection_type
        )
        session.add(conn)

        # update stats untuk non blacklisted
        source.is_active = True
        target.is_active = True
        
        if status:
            source.successful_connections += 1
            target.successful_connections += 1
        else:
            source.failed_connections += 1
            target.failed_connections += 1
            
        source.connection_count = source.successful_connections + source.failed_connections
        target.connection_count = target.successful_connections + target.failed_connections

        affected_devices.add((source, target, status))

    # update trust untuk semua affected devices
    if update_trust:
        processed = set()
        for source, target, status in affected_devices:
            if source.is_blacklisted or target.is_blacklisted:
                continue

            if source.id not in processed:
                update_trust_score(session, source, target, status)
                processed.add(source.id)
            if target.id not in processed:
                update_trust_score(session, target, source, status)
                processed.add(target.id)

    session.commit()
    
    if len(connections) == 1:
        return {"message": "Connection recorded and trust updated"}
    else:
        return {"message": f"{len(connections)} connections processed"}
   
def select_coordinator(session: Session, old_coordinator_id: str = None):
    # simpan koordinator sebelum reset
    current_coordinator_obj = session.query(Device).filter_by(is_coordinator=True).first()
    old_coord_id = current_coordinator_obj.id if current_coordinator_obj else old_coordinator_id
    
    # reset 
    session.query(Device).update({Device.is_coordinator: False})
    session.commit()

    logger.info("Selecting new coordinator...")

    # hanya internal devices - RSU internal > Computer internal berdasarkan trust
    internal_coordinator = session.query(Device).filter(
        Device.is_blacklisted == False,
        Device.ownership_type == "internal",
        Device.device_type.in_(["RSU", "Computer"]),  
        Device.trust_score >= TRUST_THRESHOLD,
        Device.is_active == True
    ).order_by(
    
        case((Device.device_type == "RSU", 0), else_=1),
        Device.trust_score.desc()
    ).first()

    if internal_coordinator:
        # jika ditemukan koordinator baru yang berbeda dari yang lama
        if internal_coordinator.id != old_coord_id:
            internal_coordinator.is_coordinator = True
            session.commit()
            logger.info(f"Internal coordinator selected: {internal_coordinator.id} ({internal_coordinator.device_type})")
         
            log_note = f"Elected as new community coordinator."
            if old_coord_id:
                log_note += f" Replacing former coordinator {old_coord_id}."
            
            log_entry = TrustHistory(
                device_id=internal_coordinator.id,
                trust_score=internal_coordinator.trust_score,
                connection_count=internal_coordinator.connection_count,
                notes=log_note,
                coordinator_id=old_coord_id 
            )
            session.add(log_entry)
            session.commit()
        return internal_coordinator
    
    logger.warning("No eligible internal devices found for coordinator")
    if old_coord_id:
        log_entry = TrustHistory(
            notes=f"Failed to elect new coordinator. System is now without a coordinator (was {old_coord_id}).",
            coordinator_id=old_coord_id
        )
        session.add(log_entry)
        session.commit()
    return None

def blacklist_device(session: Session, device: Device, reason: str):
    if device.is_blacklisted:
        return 

    logger.warning(f"BLACKLISTING: Device {device.id} is being blacklisted. Reason: {reason}")
    
    device.is_blacklisted = True
    device.is_flagged = True 
    device.is_active = False 
    device.blacklisted_at = datetime.utcnow()

    log_entry = TrustHistory(
        device_id=device.id,
        trust_score=device.trust_score,
        connection_count=device.connection_count,
        notes=f"Device blacklisted. Reason: {reason}",
        coordinator_id=None 
    )
    session.add(log_entry)
    logger.info(f"Device {device.id} has been kicked from the system.")