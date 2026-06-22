from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Request
import uuid
from datetime import datetime
from app.database import database, reports, alerts
from app.auth import require_admin

router = APIRouter(prefix="/api/reports", tags=["reports"])

@router.post("/")
async def create_report(
    request: Request,
    hazard_type: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    photo: UploadFile = File(None)
):
    report_id = f"REP_{uuid.uuid4().hex[:8].upper()}"
    predicted_class = None
    ai_confidence = None
    is_defect = False
    
    if photo:
        photo_bytes = await photo.read()
        cnn_service = getattr(request.app.state, "cnn", None)
        if cnn_service and cnn_service.ready:
            result = cnn_service.predict(photo_bytes)
            if result:
                predicted_class = result.get("predicted_class")
                ai_confidence = result.get("confidence")
                is_defect = result.get("is_defect")
            
    query = reports.insert().values(
        report_id=report_id,
        hazard_type=hazard_type,
        latitude=latitude,
        longitude=longitude,
        predicted_class=predicted_class,
        ai_confidence=ai_confidence,
        is_verified=0,
        status="pending",
        created_at=datetime.utcnow().isoformat()
    )
    await database.execute(query)
    
    if is_defect:
        alert_id = f"ALT_{uuid.uuid4().hex[:8].upper()}"
        alert_query = alerts.insert().values(
            alert_id=alert_id,
            segment_id=None, # Or infer nearest segment based on lat/lng
            alert_type="visual_anomaly",
            severity="high",
            status="open",
            confidence=ai_confidence,
            description=f"Auto-created from report {report_id}: {predicted_class}",
            created_at=datetime.utcnow().isoformat()
        )
        await database.execute(alert_query)
        
    return {
        "report_id": report_id, 
        "prediction": {
            "class": predicted_class,
            "confidence": ai_confidence,
            "is_defect": is_defect
        }
    }

@router.get("/")
async def get_reports(user: dict = Depends(require_admin)):
    query = reports.select()
    return await database.fetch_all(query)

@router.put("/{report_id}/verify")
async def verify_report(report_id: str, user: dict = Depends(require_admin)):
    query = reports.update().where(reports.c.report_id == report_id).values(is_verified=1)
    await database.execute(query)
    return {"status": "verified"}
