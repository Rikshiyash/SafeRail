from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid
from app.database import database, alerts

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

class AlertCreate(BaseModel):
    segment_id: str
    alert_type: str
    severity: str
    confidence: float
    description: str

class AlertAssign(BaseModel):
    crew_id: str

@router.get("/")
async def get_alerts(status: Optional[str] = None, severity: Optional[str] = None):
    query = alerts.select()
    if status:
        query = query.where(alerts.c.status == status)
    if severity:
        query = query.where(alerts.c.severity == severity)
    return await database.fetch_all(query)

@router.post("/")
async def create_alert(alert: AlertCreate):
    alert_id = f"ALT_{uuid.uuid4().hex[:8].upper()}"
    query = alerts.insert().values(
        alert_id=alert_id,
        segment_id=alert.segment_id,
        alert_type=alert.alert_type,
        severity=alert.severity,
        status="open",
        confidence=alert.confidence,
        description=alert.description,
        created_at=datetime.utcnow().isoformat()
    )
    await database.execute(query)
    
    if alert.severity == "critical":
        try:
            from app.main import connected_websockets
            import asyncio
            for ws in connected_websockets:
                asyncio.create_task(ws.send_json({"type": "new_alert", "alert": alert.dict()}))
        except:
            pass
            
    return {"alert_id": alert_id}

@router.put("/{alert_id}/assign")
async def assign_alert(alert_id: str, assign: AlertAssign):
    query = alerts.update().where(alerts.c.alert_id == alert_id).values(
        status="in_progress",
        assigned_crew_id=assign.crew_id
    )
    result = await database.execute(query)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "in_progress", "assigned_crew_id": assign.crew_id}

@router.put("/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    query = alerts.update().where(alerts.c.alert_id == alert_id).values(
        status="resolved",
        resolved_at=datetime.utcnow().isoformat()
    )
    result = await database.execute(query)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "resolved"}
