from fastapi import APIRouter, Depends

from .auth import current_user

router = APIRouter(prefix="/orders")


@router.get("/")
def list_orders():
    return []


@router.post("/")
def create_order(payload: dict):
    return payload


@router.get("/{order_id}")
def read_order(order_id: str, user=Depends(current_user)):
    return order_id
