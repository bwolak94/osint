"""Tests for investigation lifecycle use cases."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from src.core.domain.entities.investigation import Investigation
from src.core.domain.entities.types import InvestigationStatus, SeedInput, ScanInputType


def make_investigation(**overrides) -> Investigation:
    defaults = {
        "id": uuid4(),
        "owner_id": uuid4(),
        "title": "Test Investigation",
        "description": "Testing",
        "status": InvestigationStatus.DRAFT,
        "seed_inputs": [SeedInput(value="test@example.com", input_type=ScanInputType.EMAIL)],
        "tags": frozenset({"test"}),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return Investigation(**defaults)


class TestInvestigationLifecycle:
    def test_start_from_draft(self):
        inv = make_investigation(status=InvestigationStatus.DRAFT)
        running = inv.mark_running()
        assert running.status == InvestigationStatus.RUNNING

    def test_start_from_paused(self):
        inv = make_investigation(status=InvestigationStatus.PAUSED)
        running = inv.mark_running()
        assert running.status == InvestigationStatus.RUNNING

    def test_cannot_start_completed(self):
        inv = make_investigation(status=InvestigationStatus.COMPLETED)
        with pytest.raises(ValueError):
            inv.mark_running()

    def test_cannot_start_archived(self):
        inv = make_investigation(status=InvestigationStatus.ARCHIVED)
        with pytest.raises(ValueError):
            inv.mark_running()

    def test_pause_running(self):
        inv = make_investigation(status=InvestigationStatus.RUNNING)
        paused = inv.pause()
        assert paused.status == InvestigationStatus.PAUSED

    def test_cannot_pause_draft(self):
        inv = make_investigation(status=InvestigationStatus.DRAFT)
        with pytest.raises(ValueError):
            inv.pause()

    def test_complete_running(self):
        inv = make_investigation(status=InvestigationStatus.RUNNING)
        completed = inv.complete()
        assert completed.status == InvestigationStatus.COMPLETED
        assert completed.completed_at is not None

    def test_archive_completed(self):
        inv = make_investigation(status=InvestigationStatus.COMPLETED)
        archived = inv.archive()
        assert archived.status == InvestigationStatus.ARCHIVED

    def test_full_lifecycle(self):
        """DRAFT -> RUNNING -> PAUSED -> RUNNING -> COMPLETED -> ARCHIVED"""
        inv = make_investigation()
        inv = inv.mark_running()
        assert inv.status == InvestigationStatus.RUNNING
        inv = inv.pause()
        assert inv.status == InvestigationStatus.PAUSED
        inv = inv.mark_running()
        assert inv.status == InvestigationStatus.RUNNING
        inv = inv.complete()
        assert inv.status == InvestigationStatus.COMPLETED
        inv = inv.archive()
        assert inv.status == InvestigationStatus.ARCHIVED

    def test_add_seed_in_draft(self):
        inv = make_investigation(status=InvestigationStatus.DRAFT)
        seed = SeedInput(value="newuser", input_type=ScanInputType.USERNAME)
        updated = inv.add_seed(seed)
        assert len(updated.seed_inputs) == 2

    def test_cannot_add_seed_while_running(self):
        inv = make_investigation(status=InvestigationStatus.RUNNING)
        seed = SeedInput(value="x", input_type=ScanInputType.EMAIL)
        with pytest.raises(ValueError):
            inv.add_seed(seed)

    def test_seed_inputs_preserved_on_state_change(self):
        seeds = [SeedInput(value="a@b.com", input_type=ScanInputType.EMAIL)]
        inv = make_investigation(seed_inputs=seeds)
        running = inv.mark_running()
        assert running.seed_inputs == seeds
