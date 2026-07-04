from fastapi import APIRouter
from pydantic import BaseModel

from app.core.responses import Envelope

router = APIRouter(tags=["health"])


class HealthData(BaseModel):
    status: str


@router.get("/health", response_model=Envelope[HealthData])
async def health() -> Envelope[HealthData]:
    return Envelope(data=HealthData(status="ok"))
