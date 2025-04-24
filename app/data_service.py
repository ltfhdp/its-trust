from sqlalchemy.orm import Session
from datetime import datetime
from .models import Device, Connection, TrustHistory, PeerRating
from .trust import (
    get_computing_weight,
    calculate_initial_trust,
    calculate_updated_trust,
    get_connection_status_score,
    should_blacklist
)

# Tambah device baru ke sistem
def add_device(session: Session, device_data: dict) -> Device:
    trust_score = calculate_initial_trust(
        device_data["device_type"],
        device_data["memory_gb"]
    )

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

    # Simpan trust init ke history
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

# Rekam koneksi antar device dan update trust keduanya
def record_connection(session: Session, source_id: str, target_id: str, status: bool):
    connection = Connection(
        source_device_id=source_id,
        target_device_id=target_id,
        status=status
    )
    session.add(connection)

    source = session.get(Device, source_id)
    target = session.get(Device, target_id)

    if status:
        source.successful_connections += 1
        target.successful_connections += 1
    else:
        source.failed_connections += 1
        target.failed_connections += 1

    source.connection_count = source.successful_connections + source.failed_connections
    target.connection_count = target.successful_connections + target.failed_connections

    # Simulasi rating default
    rate_peer(session, source_id, target_id, 1.0 if status else 0.0)
    rate_peer(session, target_id, source_id, 1.0 if status else 0.0)

    update_trust_score(session, source, target, status)
    update_trust_score(session, target, source, status)

    session.commit()
    select_coordinator(session)

# Simpan rating antar device
def rate_peer(session: Session, rater_id: str, rated_id: str, score: float):
    rating = PeerRating(
        rater_device_id=rater_id,
        rated_device_id=rated_id,
        score=score
    )
    session.add(rating)
    session.commit()

# Hitung centrality berdasarkan jumlah device unik yang connect ke dia
def calculate_centrality(session: Session, device_id: str) -> float:
    unique_sources = session.query(Connection.source_device_id)\
        .filter(Connection.target_device_id == device_id).distinct().count()

    if unique_sources <= 1:
        return 0.2
    elif unique_sources <= 20:
        return 0.2 + 0.3 * ((unique_sources - 1) / 19)
    elif unique_sources <= 50:
        return 0.5 + 0.2 * ((unique_sources - 20) / 30)
    elif unique_sources <= 100:
        return 0.7 + 0.3 * ((unique_sources - 50) / 50)
    else:
        return 1.0

# Update trust berdasarkan interaksi
def update_trust_score(session: Session, device: Device, peer: Device, success: bool):
    conn_score = get_connection_status_score(success)

    avg_rating = session.query(PeerRating).filter_by(rated_device_id=device.id).with_entities(PeerRating.score).all()
    avg_peer_rating = sum([r[0] for r in avg_rating]) / len(avg_rating) if avg_rating else 0.5

    centrality = calculate_centrality(session, device.id)
    new_trust = calculate_updated_trust(
        last_trust=device.trust_score,
        centrality_score=centrality,
        avg_peer_rating=avg_peer_rating,
        connection_status_score=conn_score
    )
    device.trust_score = new_trust
    device.is_blacklisted = should_blacklist(new_trust)

    history = TrustHistory(
        device_id=device.id,
        trust_score=new_trust,
        connection_count=device.connection_count,
        last_connected_device_id=peer.id,
        notes="Connection {} with {}".format("success" if success else "failed", peer.id)
    )
    session.add(history)
    session.commit()

# Pemilihan koordinator otomatis
def select_coordinator(session: Session):
    # Reset semua
    session.query(Device).update({Device.is_coordinator: False})
    session.commit()

    rsu = session.query(Device).filter_by(device_type="RSU", is_blacklisted=False).first()
    if rsu:
        rsu.is_coordinator = True
        session.commit()
        return rsu

    # Kalau tidak ada RSU, pilih device dengan trust tertinggi
    best = session.query(Device).filter(Device.is_blacklisted == False).order_by(Device.trust_score.desc()).first()
    if best:
        best.is_coordinator = True
        session.commit()
        return best
    return None
