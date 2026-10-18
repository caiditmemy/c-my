from fastapi import APIRouter, Depends
from dependencies import verify_token

router = APIRouter(prefix="/api", tags=["Protected APIs"])

@router.get("/hello")
def hello_world(current_user: dict = Depends(verify_token)):
    return {
        "message": "Hello World",
        "authenticatedAs": current_user.get("UserName")
    }