from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from itsdangerous import BadSignature
from app.core.config import settings
from app.core.download_tokens import signer

router = APIRouter()


@router.get('/dl/{filename}')
def download(filename: str, token: str = Query(default='', max_length=2048)):
    try:
        granted = signer().loads(token, max_age=1800)
    except BadSignature:
        raise HTTPException(403, '下载授权已失效，请重新检查更新')
    if granted != filename or Path(filename).name != filename or not filename.endswith('.apk'):
        raise HTTPException(403, '无效下载授权')
    root = Path(settings.releases_dir).resolve()
    target = (root / filename).resolve()
    if target.parent != root or not target.is_file():
        raise HTTPException(404, '安装包不存在')
    return FileResponse(target, media_type='application/vnd.android.package-archive',
                        headers={'Cache-Control': 'private, no-store'})
