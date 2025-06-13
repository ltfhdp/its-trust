from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Device(Base):
    __tablename__ = "devices"

    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    ownership_type = Column(String) 
    device_type = Column(String)  
    memory_gb = Column(Float)
    computing_power = Column(Float)
    location = Column(String)
    trust_score = Column(Float, default=0.5)
    successful_connections = Column(Integer, default=0)
    failed_connections = Column(Integer, default=0)
    connection_count = Column(Integer, default=0)
    is_coordinator = Column(Boolean, default=False)
    is_blacklisted = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    left_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    blacklisted_at = Column(DateTime, nullable=True)

    trust_history = relationship("TrustHistory", back_populates="device", cascade="all, delete-orphan", foreign_keys="[TrustHistory.device_id]")
    connections_initiated = relationship("Connection", back_populates="source_device", foreign_keys='Connection.source_device_id')
    connections_received = relationship("Connection", back_populates="target_device", foreign_keys='Connection.target_device_id')
    ratings_given = relationship("PeerRating", back_populates="rater", foreign_keys='PeerRating.rater_device_id')
    ratings_received = relationship("PeerRating", back_populates="rated", foreign_keys='PeerRating.rated_device_id')

class TrustHistory(Base):
    __tablename__ = "trust_history"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, ForeignKey("devices.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    trust_score = Column(Float)
    connection_count = Column(Integer)
    last_connected_device_id = Column(String, ForeignKey("devices.id"))
    notes = Column(Text)
    coordinator_id = Column(String, ForeignKey("devices.id"))
    direct_trust = Column(Float)
    indirect_trust = Column(Float)
    centrality_score = Column(Float)

    device = relationship("Device", back_populates="trust_history", foreign_keys=[device_id])
    coordinator = relationship("Device", viewonly=True, foreign_keys=[coordinator_id])


class Connection(Base):
    __tablename__ = "connections"

    id = Column(Integer, primary_key=True, index=True)
    source_device_id = Column(String, ForeignKey("devices.id"))
    target_device_id = Column(String, ForeignKey("devices.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(Boolean)
    connection_type = Column(String, default="data")  # opsional

    source_device = relationship("Device", back_populates="connections_initiated", foreign_keys=[source_device_id])
    target_device = relationship("Device", back_populates="connections_received", foreign_keys=[target_device_id])

class PeerRating(Base):
    __tablename__ = "peer_ratings"

    id = Column(Integer, primary_key=True, index=True)
    rater_device_id = Column(String, ForeignKey("devices.id"))
    rated_device_id = Column(String, ForeignKey("devices.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    score = Column(Float)  # 0.0 - 1.0
    comment = Column(Text)

    rater = relationship("Device", back_populates="ratings_given", foreign_keys=[rater_device_id])
    rated = relationship("Device", back_populates="ratings_received", foreign_keys=[rated_device_id])
