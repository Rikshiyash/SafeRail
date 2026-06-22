import databases
import sqlalchemy
import json
import random
import datetime
from passlib.hash import bcrypt

DATABASE_URL = "sqlite:///./railguard.db"

database = databases.Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()

# TABLE: track_segments
track_segments = sqlalchemy.Table(
    "track_segments",
    metadata,
    sqlalchemy.Column("segment_id", sqlalchemy.String, primary_key=True),
    sqlalchemy.Column("km_post", sqlalchemy.Integer),
    sqlalchemy.Column("zone", sqlalchemy.String),
    sqlalchemy.Column("latitude", sqlalchemy.Float),
    sqlalchemy.Column("longitude", sqlalchemy.Float),
    sqlalchemy.Column("risk_score", sqlalchemy.Float, default=0.0),
    sqlalchemy.Column("risk_tier", sqlalchemy.String, default="safe"),
    sqlalchemy.Column("vibration_hz", sqlalchemy.Float),
    sqlalchemy.Column("strain_microstrain", sqlalchemy.Float),
    sqlalchemy.Column("temperature_celsius", sqlalchemy.Float),
    sqlalchemy.Column("humidity_percent", sqlalchemy.Float),
    sqlalchemy.Column("last_inspected", sqlalchemy.String),
)

# TABLE: alerts
alerts = sqlalchemy.Table(
    "alerts",
    metadata,
    sqlalchemy.Column("alert_id", sqlalchemy.String, primary_key=True),
    sqlalchemy.Column("segment_id", sqlalchemy.String),
    sqlalchemy.Column("alert_type", sqlalchemy.String),
    sqlalchemy.Column("severity", sqlalchemy.String),
    sqlalchemy.Column("status", sqlalchemy.String),
    sqlalchemy.Column("confidence", sqlalchemy.Float),
    sqlalchemy.Column("description", sqlalchemy.String),
    sqlalchemy.Column("created_at", sqlalchemy.String),
    sqlalchemy.Column("assigned_crew_id", sqlalchemy.String),
    sqlalchemy.Column("resolved_at", sqlalchemy.String),
)

# TABLE: reports
reports = sqlalchemy.Table(
    "reports",
    metadata,
    sqlalchemy.Column("report_id", sqlalchemy.String, primary_key=True),
    sqlalchemy.Column("hazard_type", sqlalchemy.String),
    sqlalchemy.Column("latitude", sqlalchemy.Float),
    sqlalchemy.Column("longitude", sqlalchemy.Float),
    sqlalchemy.Column("predicted_class", sqlalchemy.String),
    sqlalchemy.Column("ai_confidence", sqlalchemy.Float),
    sqlalchemy.Column("is_verified", sqlalchemy.Integer, default=0),
    sqlalchemy.Column("status", sqlalchemy.String, default="pending"),
    sqlalchemy.Column("created_at", sqlalchemy.String),
)

# TABLE: users
users = sqlalchemy.Table(
    "users",
    metadata,
    sqlalchemy.Column("user_id", sqlalchemy.String, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String),
    sqlalchemy.Column("email", sqlalchemy.String, unique=True),
    sqlalchemy.Column("password_hash", sqlalchemy.String),
    sqlalchemy.Column("role", sqlalchemy.String),
    sqlalchemy.Column("zone", sqlalchemy.String),
    sqlalchemy.Column("crew_lat", sqlalchemy.Float),
    sqlalchemy.Column("crew_lng", sqlalchemy.Float),
    sqlalchemy.Column("is_available", sqlalchemy.Integer, default=1),
)

engine = sqlalchemy.create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

async def init_db():
    metadata.create_all(engine)
    
    is_connected = database.is_connected
    if not is_connected:
        await database.connect()
        
    try:
        query = track_segments.select()
        segments = await database.fetch_all(query)
        if not segments:
            await seed_db()
    finally:
        if not is_connected:
            await database.disconnect()

async def seed_db():
    zones = ["North Delhi", "South Delhi", "East Corridor", "West Line"]
    
    segments_to_insert = []
    
    # Track segments creation
    for i in range(50):
        zone = zones[i % 4]
        vibration = random.uniform(2.0, 14.0)
        strain = random.uniform(80.0, 850.0)
        temp = random.uniform(22.0, 60.0)
        humidity = random.uniform(25.0, 90.0)
        
        risk_score = 0.35 * (vibration / 14.0) + 0.40 * (strain / 850.0) + 0.25 * (temp / 60.0)
        
        if risk_score < 0.45:
            risk_tier = "safe"
        elif risk_score <= 0.75:
            risk_tier = "warning"
        else:
            risk_tier = "critical"
            
        last_inspected_date = datetime.datetime.now() - datetime.timedelta(days=random.randint(0, 30))
            
        segments_to_insert.append({
            "segment_id": f"SEG_{i+1:03d}",
            "km_post": i * 5,
            "zone": zone,
            "latitude": random.uniform(28.40, 28.85),
            "longitude": random.uniform(76.90, 77.35),
            "risk_score": risk_score,
            "risk_tier": risk_tier,
            "vibration_hz": vibration,
            "strain_microstrain": strain,
            "temperature_celsius": temp,
            "humidity_percent": humidity,
            "last_inspected": last_inspected_date.isoformat()
        })
        
    await database.execute_many(query=track_segments.insert(), values=segments_to_insert)

    # Users creation
    users_to_insert = [
        {
            "user_id": "USR_ADMIN",
            "name": "Divisional Manager",
            "email": "admin@railguard.in",
            "password_hash": bcrypt.hash("admin123"),
            "role": "admin",
            "zone": None,
            "crew_lat": None,
            "crew_lng": None,
            "is_available": 1
        }
    ]
    
    for i in range(1, 6):
        zone = zones[(i-1) % 4]
        users_to_insert.append({
            "user_id": f"USR_CREW{i}",
            "name": f"Technician {i}",
            "email": f"crew{i}@railguard.in",
            "password_hash": bcrypt.hash("crew123"),
            "role": "field_attendant",
            "zone": zone,
            "crew_lat": random.uniform(28.40, 28.85),
            "crew_lng": random.uniform(76.90, 77.35),
            "is_available": 1
        })
        
    await database.execute_many(query=users.insert(), values=users_to_insert)

    # Alerts creation
    severities = ["low", "medium", "high", "critical"]
    statuses = ["open"] * 10 + ["in_progress"] * 5 + ["resolved"] * 5
    random.shuffle(statuses)
    
    alerts_to_insert = []
    
    for i in range(20):
        segment = random.choice(segments_to_insert)
        status = statuses[i]
        created_at = datetime.datetime.now() - datetime.timedelta(days=random.randint(1, 10))
        resolved_at = (created_at + datetime.timedelta(days=random.randint(1, 2))).isoformat() if status == "resolved" else None
        assigned_crew_id = f"USR_CREW{random.randint(1, 5)}" if status in ["in_progress", "resolved"] else None
        
        alerts_to_insert.append({
            "alert_id": f"ALT_{i+1:03d}",
            "segment_id": segment["segment_id"],
            "alert_type": random.choice(["fracture_risk", "visual_anomaly", "commuter_report"]),
            "severity": random.choice(severities),
            "status": status,
            "confidence": random.uniform(0.65, 0.97),
            "description": f"Auto-generated alert for segment {segment['segment_id']}",
            "created_at": created_at.isoformat(),
            "assigned_crew_id": assigned_crew_id,
            "resolved_at": resolved_at
        })
        
    await database.execute_many(query=alerts.insert(), values=alerts_to_insert)
