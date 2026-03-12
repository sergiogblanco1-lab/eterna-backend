from fastapi import APIRouter

router = APIRouter(prefix="/reaction", tags=["reaction"])


@router.get("/{order_uuid}")
def reaction_placeholder(order_uuid: str):
    return {"order_uuid": order_uuid, "status": "pending"}
