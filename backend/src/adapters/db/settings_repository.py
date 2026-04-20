"""SQLAlchemy implementation of settings repositories."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.settings_models import SystemSettingsModel, UserSettingsModel
from src.core.domain.entities.settings import SystemSettings, UserSettings


class SqlAlchemyUserSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: UUID) -> UserSettings | None:
        stmt = select(UserSettingsModel).where(UserSettingsModel.user_id == user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)

    async def save(self, settings: UserSettings) -> UserSettings:
        stmt = select(UserSettingsModel).where(UserSettingsModel.user_id == settings.user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is not None:
            model.theme = settings.theme
            model.language = settings.language
            model.date_format = settings.date_format
            model.timezone = settings.timezone
            model.email_on_scan_complete = settings.email_on_scan_complete
            model.email_on_new_findings = settings.email_on_new_findings
            model.email_weekly_digest = settings.email_weekly_digest
            model.default_scan_depth = settings.default_scan_depth
            model.default_enabled_scanners = settings.default_enabled_scanners
            model.default_tags = settings.default_tags
            model.anonymize_exports = settings.anonymize_exports
            model.data_retention_days = settings.data_retention_days
            model.api_key_hash = settings.api_key_hash
            model.api_key_prefix = settings.api_key_prefix
            model.api_key_created_at = settings.api_key_created_at
            model.gdpr_consent_given_at = settings.gdpr_consent_given_at
            model.marketing_consent = settings.marketing_consent
            model.updated_at = datetime.now(timezone.utc)
        else:
            model = UserSettingsModel(
                id=uuid4(),
                user_id=settings.user_id,
                theme=settings.theme,
                language=settings.language,
                date_format=settings.date_format,
                timezone=settings.timezone,
                email_on_scan_complete=settings.email_on_scan_complete,
                email_on_new_findings=settings.email_on_new_findings,
                email_weekly_digest=settings.email_weekly_digest,
                default_scan_depth=settings.default_scan_depth,
                default_enabled_scanners=settings.default_enabled_scanners,
                default_tags=settings.default_tags,
                anonymize_exports=settings.anonymize_exports,
                data_retention_days=settings.data_retention_days,
                api_key_hash=settings.api_key_hash,
                api_key_prefix=settings.api_key_prefix,
                api_key_created_at=settings.api_key_created_at,
                gdpr_consent_given_at=settings.gdpr_consent_given_at,
                marketing_consent=settings.marketing_consent,
            )
            self._session.add(model)

        await self._session.flush()
        return self._to_entity(model)

    async def delete(self, user_id: UUID) -> None:
        stmt = select(UserSettingsModel).where(UserSettingsModel.user_id == user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()

    @staticmethod
    def _to_entity(model: UserSettingsModel) -> UserSettings:
        return UserSettings(
            user_id=model.user_id,
            theme=model.theme,
            language=model.language,
            date_format=model.date_format,
            timezone=model.timezone,
            email_on_scan_complete=model.email_on_scan_complete,
            email_on_new_findings=model.email_on_new_findings,
            email_weekly_digest=model.email_weekly_digest,
            default_scan_depth=model.default_scan_depth,
            default_enabled_scanners=list(model.default_enabled_scanners or []),
            default_tags=list(model.default_tags or []),
            anonymize_exports=model.anonymize_exports,
            data_retention_days=model.data_retention_days,
            api_key_hash=model.api_key_hash,
            api_key_prefix=model.api_key_prefix,
            api_key_created_at=model.api_key_created_at,
            gdpr_consent_given_at=model.gdpr_consent_given_at,
            marketing_consent=model.marketing_consent,
            updated_at=model.updated_at,
        )
