from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import database, track_segments

router = APIRouter(prefix="/api/segments", tags=["segments"])

class WeatherEvent(BaseModel):
    event_type: str
    intensity: int

@router.get("/")
async def get_all_segments():
    query = track_segments.select()
    return await database.fetch_all(query)

@router.get("/{segment_id}")
async def get_segment(segment_id: str):
    query = track_segments.select().where(track_segments.c.segment_id == segment_id)
    segment = await database.fetch_one(query)
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    return segment

@router.post("/{segment_id}/inject-weather")
async def inject_weather(segment_id: str, event: WeatherEvent):
    query = track_segments.select().where(track_segments.c.segment_id == segment_id)
    segment = await database.fetch_one(query)
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
        
    s = dict(segment)
    if event.event_type == "heatwave":
        s["temperature_celsius"] += event.intensity * 4
        s["strain_microstrain"] += event.intensity * 30
    elif event.event_type == "flash_flood":
        s["humidity_percent"] += event.intensity * 8
        s["vibration_hz"] += event.intensity * 0.8
    elif event.event_type == "cold_snap":
        s["temperature_celsius"] -= event.intensity * 3
        s["strain_microstrain"] += event.intensity * 20
        
    # Recalculate risk
    risk_score = 0.35 * (s["vibration_hz"] / 14.0) + 0.40 * (s["strain_microstrain"] / 850.0) + 0.25 * (s["temperature_celsius"] / 60.0)
    s["risk_score"] = risk_score
    if risk_score < 0.45:
        s["risk_tier"] = "safe"
    elif risk_score <= 0.75:
        s["risk_tier"] = "warning"
    else:
        s["risk_tier"] = "critical"
        
    update_query = track_segments.update().where(track_segments.c.segment_id == segment_id).values(
        temperature_celsius=s["temperature_celsius"],
        strain_microstrain=s["strain_microstrain"],
        humidity_percent=s["humidity_percent"],
        vibration_hz=s["vibration_hz"],
        risk_score=s["risk_score"],
        risk_tier=s["risk_tier"]
    )
    await database.execute(update_query)
    return s
