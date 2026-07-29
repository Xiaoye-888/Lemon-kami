from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from profile_service import avatar_file_path, avatar_media_type


router = APIRouter(prefix="/api/v1/profile", tags=["Profile Assets"])


@router.get("/avatars/{filename}", summary="Serve profile avatar")
async def get_profile_avatar(filename: str):
    try:
        path = avatar_file_path(filename)
    except ValueError:
        raise HTTPException(status_code=404, detail="avatar not found")
    if not path.exists():
        raise HTTPException(status_code=404, detail="avatar not found")
    return FileResponse(path, media_type=avatar_media_type(filename))
