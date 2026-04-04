from fastapi import APIRouter

from providers import MODELS

router = APIRouter(prefix="/api")


@router.get("/models")
async def list_models():
    return MODELS
