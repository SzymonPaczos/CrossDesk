from fastapi import APIRouter, Depends

from .auth import current_user

router = APIRouter(prefix="/orders", dependencies=[Depends(current_user)])


@router.get("/")
def list_orders():
    return []


@router.post("/")
def create_order(payload: dict):
    return payload
