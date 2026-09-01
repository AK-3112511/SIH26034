from fastapi import APIRouter

router = APIRouter(prefix="/challans", tags=["challans"])

@router.post("/generate")
async def generate_challan():
    return {"message": "Challans generator endpoint stub", "status": "PENDING"}
