from fastapi import APIRouter

router = APIRouter(prefix="/api/dev/auth", tags=["dev_auth"])

# No additional endpoints needed because main login already handles dev mode.
