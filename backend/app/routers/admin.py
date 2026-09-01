from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/ruleset")
async def get_ruleset():
    return {"message": "Admin ruleset endpoint stub", "active_ruleset": "PCR_2011_V1"}
