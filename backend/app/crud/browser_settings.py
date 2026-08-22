"""CRUD de configurações de navegação por usuário (portado de
database/models/browser_settings.py — só ganha uma função de
"buscar ou criar com defaults" que o desktop não precisava, porque lá a
tela de configurações criava a linha na primeira vez que o usuário abria
aquela aba; aqui a extensão pode pedir antes de qualquer visita ao painel).

`anti_detection_settings` define o formato que
`extension/src/content/anti_fingerprint.js` (Fase 2, task #24) espera —
mantido simples e documentado aqui para as duas pontas ficarem em sincronia.
"""
from sqlalchemy.orm import Session

from app.models.browser_settings import BrowserSettings

DEFAULT_ANTI_DETECTION_SETTINGS = {
    "spoof_webdriver": True,
    "spoof_canvas_noise": True,
    "spoof_webgl_vendor": False,
    "spoof_timezone": None,
    "spoof_languages": None,
    "spoof_user_agent": None,
}


def get_or_create(db: Session, user_id: str) -> BrowserSettings:
    settings = db.query(BrowserSettings).filter(BrowserSettings.user_id == user_id).first()
    if settings is not None:
        return settings

    settings = BrowserSettings(
        user_id=user_id,
        anti_detection_settings=dict(DEFAULT_ANTI_DETECTION_SETTINGS),
        cache_settings={},
        privacy_settings={},
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def update(db: Session, settings: BrowserSettings, **fields) -> BrowserSettings:
    for key, value in fields.items():
        if value is not None and hasattr(settings, key):
            setattr(settings, key, value)
    db.commit()
    db.refresh(settings)
    return settings
