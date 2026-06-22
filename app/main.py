from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from app.database import database, init_db, track_segments, users, alerts
import json
from datetime import datetime

# Global WebSocket connections
connected_websockets = []

async def simulator_loop(app: FastAPI):
    from app.services.simulator import SensorSimulator
    while True:
        await asyncio.sleep(5)
        if not connected_websockets:
            continue
            
        try:
            query = track_segments.select()
            segs = await database.fetch_all(query)
            segs_dicts = [dict(s) for s in segs]
            
            updated_segs = SensorSimulator.simulate_tick(segs_dicts)
            
            # Update DB - doing this sequentially might be slow but it's okay for 50 segments
            for s in updated_segs:
                u_query = track_segments.update().where(track_segments.c.segment_id == s["segment_id"]).values(
                    vibration_hz=s["vibration_hz"],
                    strain_microstrain=s["strain_microstrain"],
                    temperature_celsius=s["temperature_celsius"],
                    humidity_percent=s["humidity_percent"],
                    risk_score=s["risk_score"],
                    risk_tier=s["risk_tier"]
                )
                await database.execute(u_query)
                
            # Batch predict
            if getattr(app.state, "xgb", None) and app.state.xgb.ready:
                xgb_results = app.state.xgb.batch_predict(updated_segs)
                for s, xr in zip(updated_segs, xgb_results):
                    s["xgb_risk"] = xr
                    
            # Broadcast update
            for ws in connected_websockets:
                try:
                    await ws.send_json({"type": "segment_update", "segments": updated_segs})
                except Exception:
                    pass
        except Exception as e:
            print(f"Simulator error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to the database and initialize tables/seed data
    await database.connect()
    await init_db()
    
    from app.services.xgboost_service import XGBoostService
    from app.services.cnn_service import CNNService
    app.state.xgb = XGBoostService()
    app.state.cnn = CNNService()
    
    # Start simulator task
    sim_task = asyncio.create_task(simulator_loop(app))
    
    yield
    # Disconnect when the application shuts down
    sim_task.cancel()
    await database.disconnect()

app = FastAPI(title="RailGuard API", lifespan=lifespan)

app.add_middleware(CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"])

from app.routers import segments, alerts as alerts_router, reports, crew, dev_auth
from app.auth import verify_password, create_token, is_dev_mode

# Add root redirect endpoint
@app.get("/")
async def root():
    return RedirectResponse(url="/docs")

app.include_router(segments.router)
app.include_router(alerts_router.router)
app.include_router(reports.router)
app.include_router(crew.router)
app.include_router(dev_auth.router)

class LoginRequest(BaseModel):
    email: str
    password: str

@app.post("/api/auth/login")
async def login(req: LoginRequest):
    if is_dev_mode():
        # Return deterministic mock token and user for development
        token = create_token({"sub": "admin@railguard.in", "role": "admin"})
        user = {
            "user_id": "admin@railguard.in",
            "name": "Admin",
            "role": "admin",
            "email": "admin@railguard.in",
        }
        return {"token": token, "user": user}
    query = users.select().where(users.c.email == req.email)
    user = await database.fetch_one(query)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token({"sub": user["user_id"], "role": user["role"]})
    return {"token": token, "user": {"user_id": user["user_id"], "name": user["name"], "role": user["role"], "zone": user["zone"]}}


@app.get("/health")
async def health():
    query = track_segments.select()
    segments_count = len(await database.fetch_all(query))
    return {
        "status": "ok", 
        "xgb_ready": getattr(app.state, "xgb", None) is not None and app.state.xgb.ready, 
        "cnn_ready": getattr(app.state, "cnn", None) is not None and app.state.cnn.ready, 
        "db_segments": segments_count
    }

@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.append(websocket)
    try:
        # Initial snapshot
        query = track_segments.select()
        segs = await database.fetch_all(query)
        segs_dicts = [dict(s) for s in segs]
        
        # Batch predict
        if getattr(app.state, "xgb", None) and app.state.xgb.ready:
            xgb_results = app.state.xgb.batch_predict(segs_dicts)
            for s, xr in zip(segs_dicts, xgb_results):
                s["xgb_risk"] = xr
                
        await websocket.send_json({"type": "snapshot", "segments": segs_dicts})
        
        while True:
            data = await websocket.receive_text() # keep connection open
    except WebSocketDisconnect:
        connected_websockets.remove(websocket)
