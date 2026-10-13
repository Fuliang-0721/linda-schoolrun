import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.infrastructure.db.models.client_telemetry import ClientTelemetryModel as Client


class ClientTelemetryService:
    def __init__(self, db):
        self.db = db

    def _authenticate(self, row, token):
        digest = hashlib.sha256(token.encode()).hexdigest()
        if row and not hmac.compare_digest(row.token_hash, digest):
            raise HTTPException(status_code=403, detail="安装凭据不匹配")
        return digest

    def upload(self, payload):
        now = int(time.time() * 1000)
        if payload.location and not now - 120000 <= payload.location.capturedAt <= now + 30000:
            raise HTTPException(status_code=422, detail="位置已过期或设备时钟不正确")
        row = self.db.query(Client).filter_by(install_id=payload.installId).with_for_update().first()
        digest = self._authenticate(row, payload.token)
        if row is None:
            row = Client(install_id=payload.installId, token_hash=digest, first_seen=now,
                         last_seen=now, sequence=0, launches=0, simulation_count=0,
                         simulation_seconds=0, version_name="", version_code=0,
                         device_model="", android_sdk=28, location_status="disabled")
            self.db.add(row)
            try:
                self.db.flush()
            except IntegrityError:
                self.db.rollback()
                row = self.db.query(Client).filter_by(install_id=payload.installId).with_for_update().one()
                self._authenticate(row, payload.token)
        if payload.sequence <= row.sequence:
            self.db.rollback()
            return {"data": {"accepted": False}}
        row.sequence = payload.sequence
        row.version_name, row.version_code = payload.versionName, payload.versionCode
        row.device_model, row.android_sdk = payload.deviceModel, payload.androidSdk
        row.launches = max(row.launches, payload.launches)
        row.simulation_count = max(row.simulation_count, payload.simulationCount)
        row.simulation_seconds = max(row.simulation_seconds, payload.simulationSeconds)
        row.last_seen = now
        row.location_status = payload.locationStatus
        # A failed fix never presents an old coordinate as the current actual location.
        row.latitude = row.longitude = row.accuracy = row.location_at = None
        if payload.location:
            row.latitude, row.longitude = payload.location.latitude, payload.location.longitude
            row.accuracy, row.location_at = payload.location.accuracy, payload.location.capturedAt
        self.db.commit()
        return {"data": {"accepted": True}}

    def erase(self, identity):
        row = self.db.query(Client).filter_by(install_id=identity.installId).with_for_update().first()
        self._authenticate(row, identity.token)
        if row:
            self.db.delete(row)
        self.db.commit()
        return {"data": {"erased": True}}

    def delete(self, install_id: str):
        """管理端删除单条统计（按安装 ID）。"""
        row = self.db.query(Client).filter_by(install_id=install_id).first()
        if row is None:
            return {"data": {"deleted": False, "installId": install_id}}
        self.db.delete(row)
        self.db.commit()
        return {"data": {"deleted": True, "installId": install_id}}

    def delete_all(self):
        """管理端清空全部统计记录。"""
        count = self.db.query(Client).delete()
        self.db.commit()
        return {"data": {"deleted": True, "count": count}}

    def dashboard(self, page=1, page_size=30):
        tz = timezone(timedelta(hours=8))
        today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        day_start = int(today.timestamp() * 1000)
        month_start = int((today - timedelta(days=29)).timestamp() * 1000)
        query = self.db.query(Client)
        stats = {"installations": query.count(),
                 "dailyActive": query.filter(Client.last_seen >= day_start).count(),
                 "monthlyActive": query.filter(Client.last_seen >= month_start).count(),
                 "launches": self.db.query(func.coalesce(func.sum(Client.launches), 0)).scalar(),
                 "simulationCount": self.db.query(func.coalesce(func.sum(Client.simulation_count), 0)).scalar(),
                 "simulationSeconds": self.db.query(func.coalesce(func.sum(Client.simulation_seconds), 0)).scalar()}
        versions = [{"version": name, "count": count} for name, count in
                    self.db.query(Client.version_name, func.count()).group_by(Client.version_name).all()]
        rows = query.order_by(Client.last_seen.desc(), Client.install_id).offset((page - 1) * page_size).limit(page_size).all()
        def date(value):
            return datetime.fromtimestamp(value / 1000, tz).strftime("%Y-%m-%d %H:%M:%S") if value else "—"
        items = [{"installId": row.install_id, "version": row.version_name,
                  "device": row.device_model, "androidSdk": row.android_sdk,
                  "launches": row.launches, "simulationCount": row.simulation_count,
                  "simulationSeconds": row.simulation_seconds, "firstSeen": date(row.first_seen),
                  "lastSeen": date(row.last_seen), "latitude": row.latitude,
                  "longitude": row.longitude, "accuracy": row.accuracy,
                  "locationAt": date(row.location_at), "locationStatus": row.location_status} for row in rows]
        return {"stats": stats, "versions": versions, "items": items, "page": page,
                "totalPages": (stats["installations"] + page_size - 1) // page_size}
