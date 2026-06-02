import time
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import requests
from sqlalchemy import and_, or_

from crud.base_manager import BaseManager
from database.models.proxy import Proxy
from utils.logger import LOGGER


class SQLAlchemyProxyManager(BaseManager[Proxy]):
    """Manager para proxies usando SQLAlchemy"""

    def __init__(self):
        super().__init__(Proxy)

    def add_proxy(
        self,
        name: str,
        host: str,
        port: int,
        proxy_type: str,
        username: str = None,
        password: str = None,
    ) -> Tuple[bool, str]:
        """Adiciona novo proxy"""
        session = self.get_session()
        try:
            # Verificar se já existe
            existing = (
                session.query(Proxy)
                .filter(and_(Proxy.host == host, Proxy.port == port))
                .first()
            )

            if existing:
                return False, f"Proxy {host}:{port} já existe"

            # Criar novo proxy
            proxy = Proxy(
                name=name,
                host=host,
                port=port,
                proxy_type=proxy_type,
                username=username,
                password=password,  # TODO: criptografar
            )

            session.add(proxy)
            session.commit()
            session.refresh(proxy)

            return True, proxy.id

        except Exception as e:
            session.rollback()
            self.logger.error(f"Erro ao adicionar proxy: {e}")
            return False, str(e)
        finally:
            session.close()

    def test_proxy(self, proxy_id: str) -> Tuple[bool, str, int]:
        """
        Testa conectividade do proxy respeitando o tipo (HTTP/SOCKS4/SOCKS5).
        Usa teste TCP + requisicao pelo protocolo correto.
        """
        session = self.get_session()
        try:
            proxy = session.query(Proxy).filter(Proxy.id == proxy_id).first()
            if not proxy:
                return False, "Proxy nao encontrado", 0

            host      = proxy.host
            port      = proxy.port
            username  = proxy.username or ""
            password  = proxy.password or ""
            ptype     = (proxy.proxy_type or "http").lower()

            start_time = time.time()

            # --- Passo 1: teste TCP rapido (2s) ---
            import socket
            try:
                sock = socket.create_connection((host, port), timeout=5)
                sock.close()
            except Exception as e:
                proxy.status      = "offline"
                proxy.last_tested = datetime.now(timezone.utc)
                session.commit()
                return False, f"Porta inacessivel: {e}", 0

            # --- Passo 2: requisicao HTTP atraves do proxy ---
            try:
                if ptype in ("socks5",):
                    if username and password:
                        proxy_url = f"socks5://{username}:{password}@{host}:{port}"
                    else:
                        proxy_url = f"socks5://{host}:{port}"
                elif ptype in ("socks4",):
                    proxy_url = f"socks4://{host}:{port}"
                else:
                    # HTTP / HTTPS
                    if username and password:
                        proxy_url = f"http://{username}:{password}@{host}:{port}"
                    else:
                        proxy_url = f"http://{host}:{port}"

                proxies_cfg = {"http": proxy_url, "https": proxy_url}

                req_session = requests.Session()
                req_session.trust_env = False  # ignora variaveis de ambiente de proxy

                response = req_session.get(
                    "http://httpbin.org/ip",
                    proxies=proxies_cfg,
                    timeout=12,
                )

                response_time = int((time.time() - start_time) * 1000)

                if response.status_code == 200:
                    proxy.status        = "available"
                    proxy.response_time = response_time
                    proxy.last_tested   = datetime.now(timezone.utc)
                    session.commit()
                    LOGGER.info(f"Proxy {proxy.name} OK — {response_time}ms")
                    return True, f"Conectividade OK via {ptype.upper()}", response_time
                else:
                    proxy.status      = "offline"
                    proxy.last_tested = datetime.now(timezone.utc)
                    session.commit()
                    return False, f"Resposta HTTP {response.status_code}", 0

            except Exception as e:
                response_time = int((time.time() - start_time) * 1000)
                proxy.status      = "offline"
                proxy.last_tested = datetime.now(timezone.utc)
                session.commit()
                LOGGER.warning(f"Proxy {proxy.name} falhou: {e}")
                return False, f"Erro de conexao: {e}", 0

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro interno ao testar proxy: {e}")
            return False, f"Erro interno: {e}", 0
        finally:
            session.close()
    
    
    def get_available_proxies(self) -> List[Proxy]:
        """Retorna proxies disponíveis"""
        session = self.get_session()
        try:
            return (
                session.query(Proxy)
                .filter(Proxy.is_active == True)
                .filter(Proxy.status != "offline")
                .all()
            )
        except Exception as e:
            self.logger.error(f"Erro ao buscar proxies disponíveis: {e}")
            return []
        finally:
            session.close()

    def mark_proxy_in_use(self, proxy_id: str, ai_name: str) -> bool:
        """Marca proxy como em uso por uma IA"""
        session = self.get_session()
        try:
            proxy = session.query(Proxy).filter(Proxy.id == proxy_id).first()
            if proxy:
                proxy.status = "in_use"
                proxy.current_ai = ai_name
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            return False
        finally:
            session.close()

    def release_proxy(self, proxy_id: str) -> bool:
        """Libera um proxy de uma IA"""
        session = self.get_session()
        try:
            proxy = session.query(Proxy).filter(Proxy.id == proxy_id).first()

            if not proxy:
                return False

            proxy.current_ai = None
            proxy.status = "available"
            session.commit()
            return True

        except Exception as e:
            session.rollback()
            self.logger.error(f"Erro ao liberar proxy {proxy_id}: {e}")
            return False
        finally:
            session.close()

    def update_proxy(self, proxy_id: str, update_data: dict) -> bool:
        """Atualiza um proxy existente"""
        session = self.get_session()
        try:
            proxy = session.query(Proxy).filter(Proxy.id == proxy_id).first()

            if not proxy:
                self.logger.warning(f"Proxy com ID {proxy_id} não encontrado")
                return False

            # Atualizar campos permitidos
            allowed_fields = [
                "name",
                "host",
                "port",
                "proxy_type",
                "username",
                "password",
                "is_active",
                "status",
            ]

            for key, value in update_data.items():
                if key in allowed_fields and hasattr(proxy, key):
                    setattr(proxy, key, value)

            session.commit()
            self.logger.info(f"Proxy {proxy_id} atualizado com sucesso")
            return True

        except Exception as e:
            session.rollback()
            self.logger.error(f"Erro ao atualizar proxy {proxy_id}: {e}")
            return False
        finally:
            session.close()

    def delete_proxy(self, proxy_id: str) -> bool:
        """Remove um proxy"""
        session = self.get_session()
        try:
            proxy = session.query(Proxy).filter(Proxy.id == proxy_id).first()

            if not proxy:
                self.logger.warning(f"Proxy com ID {proxy_id} não encontrado")
                return False

            session.delete(proxy)
            session.commit()
            self.logger.info(f"Proxy {proxy_id} removido com sucesso")
            return True

        except Exception as e:
            session.rollback()
            self.logger.error(f"Erro ao remover proxy {proxy_id}: {e}")
            return False
        finally:
            session.close()

    def assign_proxy_to_ai(self, proxy_id: str, ai_name: str) -> bool:
        """Atribui um proxy a uma IA"""
        session = self.get_session()
        try:
            proxy = session.query(Proxy).filter(Proxy.id == proxy_id).first()

            if not proxy:
                return False

            proxy.current_ai = ai_name
            proxy.status = "in_use"
            session.commit()
            return True

        except Exception as e:
            session.rollback()
            self.logger.error(f"Erro ao atribuir proxy {proxy_id} à IA {ai_name}: {e}")
            return False
        finally:
            session.close()
