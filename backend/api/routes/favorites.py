# backend/api/routes/favorites.py
from fastapi import APIRouter, Depends, HTTPException
from core.security import get_current_user_id

router = APIRouter()


@router.get("")
def list_favorites(user_id: str = Depends(get_current_user_id)):
    from crud.crud_manager import crud_system
    return crud_system.user_favorites.get_user_favorite_ids(user_id)


@router.post("/{tool_id}")
def add_favorite(tool_id: str, user_id: str = Depends(get_current_user_id)):
    from crud.crud_manager import crud_system
    success, msg, status = crud_system.user_favorites.toggle_favorite(user_id, tool_id)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"is_favorite": status, "message": msg}


@router.delete("/{tool_id}")
def remove_favorite(tool_id: str, user_id: str = Depends(get_current_user_id)):
    from crud.crud_manager import crud_system
    success, msg, status = crud_system.user_favorites.toggle_favorite(user_id, tool_id)
    return {"is_favorite": status}
