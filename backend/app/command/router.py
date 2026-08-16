from fastapi import APIRouter, Depends

from app.db import command_settings
from app.dependencies import CurrentUser, require_full_plan, require_lojista
from app.models import CommandSettingsIn, CommandSettingsOut

router = APIRouter(prefix="/api/command-settings", tags=["command"], dependencies=[Depends(require_full_plan)])

DEFAULTS = {"autonomyOn": False, "suggestionsPerDay": 5, "removalWindow": 7, "strictFlag": True}


@router.get("", response_model=CommandSettingsOut)
async def get_command_settings(user: CurrentUser = Depends(require_lojista)):
    doc = await command_settings.find_one({"tenant_id": user.tenant_id})
    return CommandSettingsOut(**{**DEFAULTS, **(doc or {})})


@router.put("", response_model=CommandSettingsOut)
async def update_command_settings(data: CommandSettingsIn, user: CurrentUser = Depends(require_lojista)):
    await command_settings.update_one(
        {"tenant_id": user.tenant_id}, {"$set": data.model_dump()}, upsert=True
    )
    return CommandSettingsOut(**data.model_dump())
