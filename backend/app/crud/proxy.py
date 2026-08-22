"""CRUD de proxy por usuário (novo na versão web — ver nota em app/models/proxy.py).

No app desktop, proxies eram cadastrados/geridos só pelo admin e associados
por ferramenta de IA. Na versão web, cada usuário cadastra e escolhe seus
próprios proxies para a extensão usar — este módulo cobre só esse caso
(`user_id` preenchido); a listagem nunca inclui proxies de outro usuário
nem os proxies "globais" (`user_id is None`) usados por `AITool.proxy`.
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.proxy import Proxy


def list_for_user(db: Session, user_id: str) -> List[Proxy]:
    return (
        db.query(Proxy)
        .filter(Proxy.user_id == user_id)
        .order_by(Proxy.created_at.desc())
        .all()
    )


def get_owned(db: Session, user_id: str, proxy_id: str) -> Optional[Proxy]:
    return (
        db.query(Proxy)
        .filter(Proxy.id == proxy_id, Proxy.user_id == user_id)
        .first()
    )


def get_active(db: Session, user_id: str) -> Optional[Proxy]:
    return (
        db.query(Proxy)
        .filter(Proxy.user_id == user_id, Proxy.is_selected.is_(True))
        .first()
    )


def create(
    db: Session,
    *,
    user_id: str,
    name: str,
    host: str,
    port: int,
    proxy_type: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Proxy:
    proxy = Proxy(
        user_id=user_id,
        name=name,
        host=host,
        port=port,
        proxy_type=proxy_type,
        username=username,
        password=password,
    )
    db.add(proxy)
    db.commit()
    db.refresh(proxy)
    return proxy


def update(db: Session, proxy: Proxy, **fields) -> Proxy:
    for key, value in fields.items():
        if value is not None and hasattr(proxy, key):
            setattr(proxy, key, value)
    db.commit()
    db.refresh(proxy)
    return proxy


def delete(db: Session, proxy: Proxy) -> None:
    db.delete(proxy)
    db.commit()


def select_active(db: Session, user_id: str, proxy_id: str) -> Optional[Proxy]:
    """Marca `proxy_id` como o proxy ativo do usuário, desmarcando os demais.

    Só um proxy por usuário pode estar `is_selected=True` por vez — é o que
    a extensão consulta em GET /proxies/active para saber qual PAC aplicar.
    """
    target = get_owned(db, user_id, proxy_id)
    if target is None:
        return None

    db.query(Proxy).filter(Proxy.user_id == user_id, Proxy.id != proxy_id).update(
        {Proxy.is_selected: False}
    )
    target.is_selected = True
    db.commit()
    db.refresh(target)
    return target
