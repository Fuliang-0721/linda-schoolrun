from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from itsdangerous import URLSafeTimedSerializer
from app.core.config import settings


def signer():
    return URLSafeTimedSerializer(settings.mobile_auth_secret, salt="apk-download")


def authorize_url(url):
    configured = urlsplit(settings.release_public_base_url)
    parsed = urlsplit(url)
    if configured.netloc and parsed.netloc == configured.netloc and parsed.path.startswith('/dl/'):
        name = parsed.path.rsplit('/', 1)[-1]
        query = [(k, v) for k, v in parse_qsl(parsed.query) if k != 'token']
        query.append(('token', signer().dumps(name)))
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ''))
    return url
