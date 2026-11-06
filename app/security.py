"""Sécurité HTTP : en-têtes, politique de contenu (CSP) et protection contre les requêtes inter-sites (CSRF).

Pourquoi le CSRF compte ici : avec l'authentification HTTP Basic, le navigateur renvoie automatiquement les identifiants à chaque
requête vers le serveur, y compris celles déclenchées par une AUTRE page (formulaire caché). Sans garde-fou, un site malveillant
pourrait envoyer des fichiers ou déclencher des suppressions pour le compte d'un utilisateur connecté. On refuse donc toute requête
modifiante dont l'origine n'est pas ce serveur.
"""
from __future__ import annotations

import base64
import secrets
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse

from . import config

# Scripts : uniquement ceux du serveur (aucun script inline ni externe). Styles inline autorisés (l'interface pose des attributs style).
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "media-src 'self' blob:",
    "connect-src 'self'",
    "worker-src 'self'",
    "manifest-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])
PERMISSIONS = "microphone=(self), display-capture=(self), camera=(), geolocation=(), payment=(), usb=()"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _same_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:                       # client non navigateur (curl, scripts) ou requête de même origine sans en-tête
        return True
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    return urlparse(origin).netloc == host.split(",")[0].strip()


def authorized(request: Request) -> bool:
    """Mot de passe (HTTP Basic, nom d'utilisateur libre). Couvre TOUTES les routes, fichiers de l'interface compris,
    sauf la sonde /healthz. (Une dépendance FastAPI ne protégerait pas les fichiers statiques montés.)"""
    if not config.PASSWORD or request.url.path == "/healthz":
        return True
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("basic "):
        return False
    try:
        _, _, pw = base64.b64decode(header[6:]).decode("utf-8").partition(":")
    except Exception:  # noqa: BLE001
        return False
    return secrets.compare_digest(pw.encode(), config.PASSWORD.encode())


async def middleware(request: Request, call_next):
    if not authorized(request):
        resp = JSONResponse({"detail": "Authentification requise"}, status_code=401, headers={"WWW-Authenticate": 'Basic realm="GMeeting"'})
    elif request.method not in SAFE_METHODS and (request.headers.get("sec-fetch-site") == "cross-site" or not _same_origin(request)):
        resp = JSONResponse({"detail": "Requête inter-sites refusée"}, status_code=403)
    else:
        resp = await call_next(request)
    h = resp.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h["X-Frame-Options"] = "DENY"
    h["Referrer-Policy"] = "no-referrer"
    h["Permissions-Policy"] = PERMISSIONS
    h["Content-Security-Policy"] = CSP
    h["Cross-Origin-Opener-Policy"] = "same-origin"
    if request.url.path.startswith("/api/") or request.url.path == "/healthz":
        h["Cache-Control"] = "no-store"             # données de réunion : jamais en cache navigateur ou proxy
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resp
