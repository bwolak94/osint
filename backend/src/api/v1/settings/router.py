"""User and system settings endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.settings_repository import SqlAlchemyUserSettingsRepository
from src.api.v1.auth.dependencies import get_current_user, require_role
from src.api.v1.settings.schemas import (
    ApiKeyInfoResponse,
    ApiKeyResponse,
    GdprDeleteResponse,
    GdprExportResponse,
    MessageResponse,
    SessionResponse,
    SystemSettingsResponse,
    SystemSettingsUpdate,
    UserSettingsResponse,
    UserSettingsUpdate,
)
from src.core.domain.entities.settings import SystemSettings, UserSettings
from src.core.domain.entities.types import UserRole
from src.core.domain.entities.user import User
from src.dependencies import get_db

router = APIRouter()


def _settings_response(s: UserSettings) -> UserSettingsResponse:
    return UserSettingsResponse(
        user_id=s.user_id,
        theme=s.theme,
        language=s.language,
        date_format=s.date_format,
        timezone=s.timezone,
        email_on_scan_complete=s.email_on_scan_complete,
        email_on_new_findings=s.email_on_new_findings,
        email_weekly_digest=s.email_weekly_digest,
        default_scan_depth=s.default_scan_depth,
        default_enabled_scanners=s.default_enabled_scanners,
        default_tags=s.default_tags,
        anonymize_exports=s.anonymize_exports,
        data_retention_days=s.data_retention_days,
        has_api_key=s.api_key_hash is not None,
        api_key_prefix=s.api_key_prefix,
        api_key_created_at=s.api_key_created_at,
        gdpr_consent_given_at=s.gdpr_consent_given_at,
        marketing_consent=s.marketing_consent,
        updated_at=s.updated_at,
    )


@router.get("/me", response_model=UserSettingsResponse)
async def get_my_settings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserSettingsResponse:
    repo = SqlAlchemyUserSettingsRepository(db)
    settings = await repo.get_by_user_id(current_user.id)
    if settings is None:
        settings = UserSettings(user_id=current_user.id)
        settings = await repo.save(settings)
    return _settings_response(settings)


@router.patch("/me", response_model=UserSettingsResponse)
async def update_my_settings(
    body: UserSettingsUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserSettingsResponse:
    repo = SqlAlchemyUserSettingsRepository(db)
    settings = await repo.get_by_user_id(current_user.id)
    if settings is None:
        settings = UserSettings(user_id=current_user.id)

    updates = body.model_dump(exclude_unset=True)
    if updates:
        settings = settings.update(**updates)
    settings = await repo.save(settings)
    return _settings_response(settings)


@router.post("/me/api-key", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def generate_api_key(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiKeyResponse:
    from src.adapters.db.repositories import SqlAlchemyUserRepository
    from src.core.use_cases.settings.generate_api_key import GenerateApiKeyUseCase

    user_repo = SqlAlchemyUserRepository(db)
    settings_repo = SqlAlchemyUserSettingsRepository(db)
    use_case = GenerateApiKeyUseCase(user_repo=user_repo, settings_repo=settings_repo)

    try:
        result = await use_case.execute(current_user.id)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    return ApiKeyResponse(key=result.key, prefix=result.prefix, created_at=result.created_at)


@router.delete("/me/api-key", response_model=MessageResponse)
async def revoke_api_key(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    repo = SqlAlchemyUserSettingsRepository(db)
    settings = await repo.get_by_user_id(current_user.id)
    if settings is None or settings.api_key_hash is None:
        raise HTTPException(status_code=404, detail="No API key found")
    settings = settings.revoke_api_key()
    await repo.save(settings)
    return MessageResponse(message="API key revoked")


@router.get("/system", response_model=SystemSettingsResponse)
async def get_system_settings(
    current_user: Annotated[User, Depends(require_role(UserRole.ADMIN))],
) -> SystemSettingsResponse:
    # Placeholder — in production load from DB
    s = SystemSettings()
    return SystemSettingsResponse(
        max_concurrent_browsers=s.max_concurrent_browsers,
        max_scan_depth_global=s.max_scan_depth_global,
        default_request_delay_ms=s.default_request_delay_ms,
        free_tier_investigations_per_month=s.free_tier_investigations_per_month,
        free_tier_scans_per_day=s.free_tier_scans_per_day,
        proxy_enabled=s.proxy_enabled,
        proxy_rotation_enabled=s.proxy_rotation_enabled,
        maintenance_mode=s.maintenance_mode,
        maintenance_message=s.maintenance_message,
        updated_at=s.updated_at,
    )


@router.patch("/system", response_model=SystemSettingsResponse)
async def update_system_settings(
    body: SystemSettingsUpdate,
    current_user: Annotated[User, Depends(require_role(UserRole.ADMIN))],
) -> SystemSettingsResponse:
    s = SystemSettings()
    updates = body.model_dump(exclude_unset=True)
    if updates:
        s = s.update(**updates)
    return SystemSettingsResponse(
        max_concurrent_browsers=s.max_concurrent_browsers,
        max_scan_depth_global=s.max_scan_depth_global,
        default_request_delay_ms=s.default_request_delay_ms,
        free_tier_investigations_per_month=s.free_tier_investigations_per_month,
        free_tier_scans_per_day=s.free_tier_scans_per_day,
        proxy_enabled=s.proxy_enabled,
        proxy_rotation_enabled=s.proxy_rotation_enabled,
        maintenance_mode=s.maintenance_mode,
        maintenance_message=s.maintenance_message,
        updated_at=s.updated_at,
    )


@router.get("/me/sessions", response_model=list[SessionResponse])
async def list_sessions(
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[SessionResponse]:
    # Placeholder
    return []


@router.delete("/me/sessions", response_model=MessageResponse)
async def revoke_all_sessions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    from src.adapters.db.refresh_token_repository import SqlAlchemyRefreshTokenRepository
    repo = SqlAlchemyRefreshTokenRepository(db)
    await repo.revoke_all_for_user(current_user.id)
    return MessageResponse(message="All sessions revoked")


@router.post("/me/gdpr/export", response_model=GdprExportResponse)
async def gdpr_export(
    current_user: Annotated[User, Depends(get_current_user)],
) -> GdprExportResponse:
    return GdprExportResponse(message="Your data export has been queued. You will receive an email when ready.")


@router.post("/me/gdpr/delete", response_model=GdprDeleteResponse)
async def gdpr_delete(
    current_user: Annotated[User, Depends(get_current_user)],
) -> GdprDeleteResponse:
    from datetime import datetime, timedelta, timezone
    scheduled = datetime.now(timezone.utc) + timedelta(days=30)
    return GdprDeleteResponse(
        message="Your account deletion has been scheduled. You have 30 days to cancel.",
        scheduled_for=scheduled,
    )
