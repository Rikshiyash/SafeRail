from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.database import database, users, alerts
from app.auth import require_admin, require_field, get_current_user

router = APIRouter(prefix="/api/crew", tags=["crew"])

class LocationUpdate(BaseModel):
    lat: float
    lng: float

@router.get("/")
async def get_crew(user: dict = Depends(require_admin)):
    query = users.select().where(users.c.role == "field_attendant")
    crew = await database.fetch_all(query)
    return [{"user_id": c["user_id"], "name": c["name"], "zone": c["zone"], "crew_lat": c["crew_lat"], "crew_lng": c["crew_lng"]} for c in crew]

@router.get("/my-tasks")
async def get_my_tasks(user: dict = Depends(require_field)):
    query = alerts.select().where(alerts.c.assigned_crew_id == user["user_id"])
    return await database.fetch_all(query)

@router.post("/{crew_id}/location")
async def update_location(crew_id: str, location: LocationUpdate, user: dict = Depends(get_current_user)):
    # Field attendants can only update their own location, admin can update anyone
    if user["role"] != "admin" and user["user_id"] != crew_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this location")
        
    query = users.update().where(users.c.user_id == crew_id).values(
        crew_lat=location.lat,
        crew_lng=location.lng
    )
    await database.execute(query)
    return {"status": "location updated"}
