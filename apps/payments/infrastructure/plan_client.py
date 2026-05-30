"""HTTP adapter for fetching org plan from management-service."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid


class HttpPlanClient:
    """Calls management-service to look up an org's subscription plan."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def get_org_plan(self, org_id: uuid.UUID) -> str:
        """
        Fetch the org's plan from management-service.

        Falls back to 'free' if the service is unreachable or the org doesn't exist.
        """
        url = f"{self._base_url}/api/v1/organizations/internal/orgs/{org_id}/plan/"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read())
                return data.get("plan", "free")
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError):
            return "free"
