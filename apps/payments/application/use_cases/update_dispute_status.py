"""Use case: update the status of an existing dispute (admin action)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from apps.payments.domain.entities import DisputeEntity
from apps.payments.domain.repositories import IDisputeRepository


class UpdateDisputeStatusUseCase:
    """Transition a dispute through its status lifecycle."""

    def __init__(self, dispute_repo: IDisputeRepository) -> None:
        self._disputes = dispute_repo

    def execute(
        self,
        *,
        dispute_id: uuid.UUID,
        new_status: str,
        resolution_notes: str,
    ) -> DisputeEntity:
        """Update dispute status and set resolved_at when closing."""
        dispute = self._disputes.get_by_id(dispute_id)
        now = datetime.now(timezone.utc)
        dispute.status = new_status
        dispute.updated_at = now
        if new_status in {"resolved", "closed"}:
            dispute.resolved_at = now
        if resolution_notes:
            dispute.evidence = {**dispute.evidence, "resolution_notes": resolution_notes}
        return self._disputes.update(dispute)
