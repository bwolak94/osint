"""SQLAlchemy implementation of the scan result repository."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.models import ScanResultModel
from src.core.domain.entities.scan_result import ScanResult
from src.core.domain.entities.types import ScanStatus


class SqlAlchemyScanResultRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, result: ScanResult) -> ScanResult:
        model = ScanResultModel(
            id=result.id,
            investigation_id=result.investigation_id,
            scanner_name=result.scanner_name,
            input_value=result.input_value,
            status=result.status,
            raw_data=result.raw_data,
            extracted_identifiers=result.extracted_identifiers,
            duration_ms=result.duration_ms,
            error_message=result.error_message,
        )
        self._session.add(model)
        await self._session.flush()
        return result

    async def get_by_id(self, scan_id: UUID) -> ScanResult | None:
        model = await self._session.get(ScanResultModel, scan_id)
        if model is None:
            return None
        return self._to_entity(model)

    async def get_by_investigation(
        self,
        investigation_id: UUID,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ScanResult]:
        stmt = (
            select(ScanResultModel)
            .where(ScanResultModel.investigation_id == investigation_id)
            .order_by(ScanResultModel.created_at.desc())
            .offset(offset)
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_pending(self, investigation_id: UUID) -> list[ScanResult]:
        stmt = (
            select(ScanResultModel)
            .where(
                ScanResultModel.investigation_id == investigation_id,
                ScanResultModel.status == ScanStatus.PENDING,
            )
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    @staticmethod
    def _to_entity(model: ScanResultModel) -> ScanResult:
        return ScanResult(
            id=model.id,
            investigation_id=model.investigation_id,
            scanner_name=model.scanner_name,
            input_value=model.input_value,
            status=ScanStatus(model.status),
            raw_data=model.raw_data or {},
            extracted_identifiers=list(model.extracted_identifiers or []),
            duration_ms=model.duration_ms,
            created_at=model.created_at,
            error_message=model.error_message,
        )
