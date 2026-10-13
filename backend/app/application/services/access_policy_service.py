from datetime import datetime, timezone

from app.infrastructure.db.models.access_policy import AccessPolicyModel

VALID_SCOPES = {"all", "public_only"}


class AccessPolicyService:
    """全局服务开关：客户端启动确认 + 后台一键停止/恢复。"""

    def __init__(self, db):
        self.db = db

    def _row(self) -> AccessPolicyModel:
        row = self.db.get(AccessPolicyModel, 1)
        if row is None:
            row = AccessPolicyModel(id=1, service_enabled=True, message="", scope="all", updated_at=0)
            self.db.add(row)
            self.db.commit()
        return row

    def _payload(self, row, channel: str = "") -> dict:
        channel = (channel or "").strip().lower()
        effective = bool(row.service_enabled)
        if not effective and row.scope == "public_only" and channel == "internal":
            effective = True
        return {
            "allowed": effective,
            "serviceEnabled": bool(row.service_enabled),
            "scope": row.scope,
            "message": (row.message or "").strip(),
            "channel": channel,
            "updatedAt": row.updated_at,
        }

    def status(self, channel: str = "") -> dict:
        return {"data": self._payload(self._row(), channel)}

    def policy(self) -> dict:
        row = self._row()
        return {"data": {"serviceEnabled": bool(row.service_enabled), "message": row.message or "",
                         "scope": row.scope, "updatedAt": row.updated_at}}

    def update(self, service_enabled: bool, message: str, scope: str) -> dict:
        scope = (scope or "all").strip().lower()
        if scope not in VALID_SCOPES:
            scope = "all"
        row = self._row()
        row.service_enabled = bool(service_enabled)
        row.message = (message or "").strip()[:255]
        row.scope = scope
        row.updated_at = int(datetime.now(timezone.utc).timestamp() * 1000)
        self.db.commit()
        return self.policy()
