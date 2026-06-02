import platform
import socket
import uuid
import subprocess
import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import psutil
from sqlalchemy.orm import Session

from crud.base_manager import BaseManager
from database.models.device_data import DeviceData
from database.models.user import User
from database.models.constants import BlockReasons
from utils.datetime_utils import get_current_utc, normalize_datetime, safe_datetime_diff
from utils.logger import LOGGER


class DeviceDataManager(BaseManager[DeviceData]):
    """Manager para gerenciar dados de dispositivo dos usuários"""

    def __init__(self):
        super().__init__(DeviceData)

    def get_mac_address(self) -> str:
        """
        Obtém o endereço MAC da máquina usando métodos nativos do Windows
        
        Returns:
            str: Endereço MAC no formato AA:BB:CC:DD:EE:FF
        """
        try:
            if platform.system() == "Windows":
                # Método 1: Usar comando getmac do Windows (mais confiável)
                try:
                    result = subprocess.run(
                        ['getmac', '/fo', 'csv', '/nh'],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=True
                    )
                    
                    if result.returncode == 0 and result.stdout:
                        # Parsear output CSV: "MAC-Address","Transport Name"
                        lines = result.stdout.strip().split('\n')
                        for line in lines:
                            # Extrair MAC da primeira linha válida
                            mac_match = re.search(r'"([0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2})"', line)
                            if mac_match:
                                mac_raw = mac_match.group(1).upper()
                                # Normalizar formato com ':'
                                mac_address = mac_raw.replace('-', ':')
                                LOGGER.info(f"MAC Address capturado via getmac: {mac_address}")
                                return mac_address
                
                except subprocess.TimeoutExpired:
                    LOGGER.warning("Comando getmac excedeu timeout")
                except subprocess.CalledProcessError as e:
                    LOGGER.warning(f"Erro ao executar getmac: {e}")
                except Exception as e:
                    LOGGER.warning(f"Erro ao processar saída do getmac: {e}")
                
                # Método 2: Usar WMI (Windows Management Instrumentation)
                try:
                    import wmi  # type: ignore[import]
                    _WMI_AVAILABLE = True
                except ImportError:
                    wmi = None  # type: ignore[assignment]
                    _WMI_AVAILABLE = False
                
                # Método 3: Usar uuid.getnode() como último recurso
                try:
                    mac_num = uuid.getnode()
                    
                    # Verificar se retornou um valor válido (não 0 e não aleatório)
                    if mac_num != 0 and mac_num != 0xffffffffffff:
                        mac_hex = hex(mac_num)[2:].upper().zfill(12)
                        mac_address = ":".join(mac_hex[i:i+2] for i in range(0, 12, 2))
                        LOGGER.info(f"MAC Address capturado via uuid.getnode: {mac_address}")
                        return mac_address
                    else:
                        LOGGER.warning("uuid.getnode() retornou valor inválido")
                
                except Exception as e:
                    LOGGER.warning(f"Erro ao obter MAC via uuid.getnode: {e}")
                
                # Se todos os métodos falharam, lançar exceção
                error_msg = "ERRO CRÍTICO: Não foi possível capturar o endereço MAC no Windows. Verifique as permissões do sistema."
                LOGGER.error(error_msg)
                raise RuntimeError(error_msg)
            
            else:
                # Para outros sistemas operacionais (não será usado por enquanto)
                LOGGER.error("Sistema operacional não suportado. Apenas Windows é suportado.")
                raise RuntimeError("Sistema operacional não suportado")
        
        except Exception as e:
            error_msg = f"FALHA ao obter MAC address: {e}"
            LOGGER.error(error_msg)
            # Não usar fallback - notificar erro
            raise RuntimeError(error_msg)

    def get_computer_name(self) -> str:
        """
        Obtém o nome do computador usando métodos nativos do Windows
        
        Returns:
            str: Nome do computador
        """
        try:
            if platform.system() == "Windows":
                # Método 1: Variável de ambiente COMPUTERNAME (mais confiável no Windows)
                import os
                computer_name = os.environ.get('COMPUTERNAME')
                
                if computer_name:
                    LOGGER.info(f"Nome do computador capturado via COMPUTERNAME: {computer_name}")
                    return computer_name
                
                # Método 2: Usar comando hostname
                try:
                    result = subprocess.run(
                        ['hostname'],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=True
                    )
                    
                    if result.returncode == 0 and result.stdout:
                        computer_name = result.stdout.strip()
                        LOGGER.info(f"Nome do computador capturado via hostname: {computer_name}")
                        return computer_name
                
                except Exception as e:
                    LOGGER.warning(f"Erro ao executar hostname: {e}")
                
                # Método 3: platform.node() como último recurso
                computer_name = platform.node()
                if computer_name and computer_name != "":
                    LOGGER.info(f"Nome do computador capturado via platform.node: {computer_name}")
                    return computer_name
                
                # Se todos os métodos falharam
                error_msg = "ERRO CRÍTICO: Não foi possível capturar o nome do computador no Windows."
                LOGGER.error(error_msg)
                raise RuntimeError(error_msg)
            
            else:
                # Para outros sistemas operacionais (não será usado por enquanto)
                LOGGER.error("Sistema operacional não suportado. Apenas Windows é suportado.")
                raise RuntimeError("Sistema operacional não suportado")
        
        except Exception as e:
            error_msg = f"FALHA ao obter nome do computador: {e}"
            LOGGER.error(error_msg)
            raise RuntimeError(error_msg)

    def get_ip_address(self) -> str:
        """Obtém o IP local da máquina"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                LOGGER.info(f"IP Address capturado: {ip}")
                return ip
        except Exception as e:
            error_msg = f"FALHA ao obter IP: {e}"
            LOGGER.error(error_msg)
            raise RuntimeError(error_msg)

    def get_system_info(self) -> dict:
        """
        Coleta informações completas do sistema com tratamento rigoroso de erros
        
        Returns:
            dict: Dicionário com informações do sistema
            
        Raises:
            RuntimeError: Se não conseguir capturar informações críticas
        """
        try:
            LOGGER.info("Iniciando coleta de informações do sistema...")
            
            # Verificar se está no Windows
            if platform.system() != "Windows":
                error_msg = "Sistema operacional não suportado. Apenas Windows é suportado."
                LOGGER.error(error_msg)
                raise RuntimeError(error_msg)
            
            # Coletar informações críticas (se falhar, deve notificar)
            device_name = self.get_computer_name()
            ip_address = self.get_ip_address()
            mac_address = self.get_mac_address()
            
            system_info = {
                "device_name": device_name,
                "os_name": platform.system(),
                "os_version": f"{platform.release()} {platform.version()}",
                "ip_address": ip_address,
                "mac_address": mac_address,
            }
            
            LOGGER.info(f"Informações críticas capturadas com sucesso:")
            LOGGER.info(f"  - Device Name: {device_name}")
            LOGGER.info(f"  - IP: {ip_address}")
            LOGGER.info(f"  - MAC: {mac_address}")

            # Coletar informações adicionais (se falhar, apenas logar warning)
            try:
                system_info["cpu_info"] = platform.processor()
                memory = psutil.virtual_memory()
                system_info["memory_total"] = f"{memory.total // (1024**3)}GB"

                if psutil.sensors_battery():
                    system_info["device_type"] = "Laptop"
                else:
                    system_info["device_type"] = "Desktop"
                
                LOGGER.info(f"  - CPU: {system_info['cpu_info']}")
                LOGGER.info(f"  - RAM: {system_info['memory_total']}")
                LOGGER.info(f"  - Tipo: {system_info['device_type']}")

            except ImportError:
                LOGGER.warning("psutil não disponível - informações de hardware limitadas")
                system_info["cpu_info"] = "Informação não disponível"
                system_info["memory_total"] = "N/A"
                system_info["device_type"] = "Computador"
            except Exception as e:
                LOGGER.warning(f"Erro ao coletar informações adicionais de hardware: {e}")
                system_info["cpu_info"] = "Informação não disponível"
                system_info["memory_total"] = "N/A"
                system_info["device_type"] = "Computador"

            # Capturar resolução da tela
            try:
                if platform.system() == "Windows":
                    import tkinter as tk
                    root = tk.Tk()
                    width = root.winfo_screenwidth()
                    height = root.winfo_screenheight()
                    system_info["resolution"] = f"{width}x{height}"
                    root.destroy()
                    LOGGER.info(f"  - Resolução: {system_info['resolution']}")
                else:
                    system_info["resolution"] = "N/A"
            except Exception as e:
                LOGGER.warning(f"Erro ao capturar resolução: {e}")
                system_info["resolution"] = "N/A"

            LOGGER.info("Coleta de informações do sistema concluída com sucesso")
            return system_info

        except RuntimeError as e:
            # Re-lançar erros críticos
            raise
        except Exception as e:
            error_msg = f"ERRO CRÍTICO ao coletar informações do sistema: {e}"
            LOGGER.error(error_msg)
            raise RuntimeError(error_msg)

    # ========== NOVOS MÉTODOS: Sistema de Autorização de Dispositivos ==========

    def validate_device_for_login(
        self, user_id: str, device_id: str
    ) -> Tuple[bool, str, Optional[DeviceData]]:
        """
        Valida se um dispositivo pode fazer login
        
        Fluxo:
        1. Busca dispositivo por user_id + device_id
        2. Se não existe:
           - Verifica se usuário tem dispositivo autorizado
           - Se SIM: bloqueia usuário e retorna False (novo dispositivo detectado)
           - Se NÃO: cria como primeiro dispositivo autorizado
        3. Se existe:
           - Verifica se está autorizado
           - Se SIM: permite login
           - Se NÃO: bloqueia usuário e retorna False
        
        Args:
            user_id: ID do usuário
            device_id: UUID do dispositivo
            
        Returns:
            Tuple[bool, str, Optional[DeviceData]]:
                - bool: True se pode logar
                - str: Mensagem explicativa
                - DeviceData: Objeto do dispositivo (ou None)
        """
        session = self.get_session()
        try:
            LOGGER.info(f"Validando dispositivo para login - User: {user_id}, Device: {device_id}")
            
            # Buscar dispositivo específico
            device = (
                session.query(DeviceData)
                .filter(
                    DeviceData.user_id == user_id,
                    DeviceData.device_id == device_id
                )
                .first()
            )
            
            if device:
                # Dispositivo existe - verificar autorização
                LOGGER.info(f"Dispositivo encontrado - Status: {device.authorization_status}")
                
                if device.is_authorized_device():
                    # Dispositivo autorizado - permitir login
                    device.update_last_seen()
                    session.commit()
                    LOGGER.info("Dispositivo autorizado - login permitido")
                    return True, "Dispositivo autorizado", device
                
                else:
                    # Dispositivo não autorizado - bloquear
                    LOGGER.warning("Dispositivo não autorizado - bloqueando usuário")
                    return False, "Dispositivo não autorizado", device
            
            else:
                # Dispositivo não existe - verificar se é o primeiro
                LOGGER.info("Dispositivo não encontrado - verificando se é o primeiro do usuário")
                
                # Buscar dispositivos autorizados do usuário
                authorized_devices = (
                    session.query(DeviceData)
                    .filter(
                        DeviceData.user_id == user_id,
                        DeviceData.is_authorized == True
                    )
                    .count()
                )
                
                if authorized_devices > 0:
                    # Usuário já tem dispositivo - novo dispositivo não autorizado
                    LOGGER.warning(f"Novo dispositivo detectado - usuário já tem {authorized_devices} dispositivo(s) autorizado(s)")
                    return False, "Novo dispositivo detectado - autorização necessária", None
                else:
                    # Primeiro dispositivo - será autorizado automaticamente no create_or_update
                    LOGGER.info("Primeiro dispositivo do usuário - será criado e autorizado")
                    return True, "Primeiro dispositivo - será autorizado automaticamente", None
        
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao validar dispositivo: {e}")
            return False, f"Erro ao validar dispositivo: {e}", None
        finally:
            session.close()

    def create_or_update_device_data(
        self, user_id: str, device_id: str, device_info: dict
    ) -> Optional[DeviceData]:
        """
        Cria ou atualiza dados do dispositivo do usuário COM DEVICE_ID
        
        Args:
            user_id: ID do usuário
            device_id: UUID único do dispositivo
            device_info: Dicionário com informações coletadas
            
        Returns:
            Optional[DeviceData]: Objeto do dispositivo criado/atualizado ou None
        """
        session = self.get_session()
        try:
            current_time = get_current_utc()
            
            # Buscar por device_id (identificador único do dispositivo)
            existing_device = (
                session.query(DeviceData)
                .filter(
                    DeviceData.user_id == user_id,
                    DeviceData.device_id == device_id
                )
                .first()
            )
            
            # Extrair informações do device_info usando get_system_info
            system_info = self.get_system_info()
            
            if existing_device:
                # Calcular tempo da sessão anterior se houver last_logout
                additional_time = 0
                if existing_device.last_logout:
                    additional_time = safe_datetime_diff(existing_device.last_login, existing_device.last_logout)
                    existing_device.online_time = (existing_device.online_time or 0) + additional_time
                
                # Atualizar dados
                existing_device.last_login = current_time
                existing_device.last_logout = None
                existing_device.is_active = "Online"
                existing_device.ip_address = system_info.get("ip_address", existing_device.ip_address)
                existing_device.os_version = system_info.get("os_version", existing_device.os_version)
                existing_device.device_name = system_info.get("device_name", existing_device.device_name)
                existing_device.mac_address = system_info.get("mac_address", existing_device.mac_address)
                existing_device.update_last_seen()
                
                session.commit()
                session.refresh(existing_device)
                
                LOGGER.info(f"Dispositivo atualizado para usuário {user_id}")
                LOGGER.info(f"  - Device Name: {existing_device.device_name}")
                LOGGER.info(f"  - MAC: {existing_device.mac_address}")
                LOGGER.info(f"  - IP: {existing_device.ip_address}")
                return existing_device
            
            else:
                # Verificar se é o primeiro dispositivo do usuário
                authorized_count = (
                    session.query(DeviceData)
                    .filter(
                        DeviceData.user_id == user_id,
                        DeviceData.is_authorized == True
                    )
                    .count()
                )
                
                # Se for o primeiro, autorizar automaticamente
                is_first_device = authorized_count == 0
                
                # Criar novo dispositivo
                device_data = DeviceData(
                    user_id=user_id,
                    device_id=device_id,
                    device_name=system_info.get("device_name"),
                    device_type=system_info.get("device_type", "Computador"),
                    ip_address=system_info.get("ip_address"),
                    mac_address=system_info.get("mac_address"),
                    os_name=system_info.get("os_name"),
                    os_version=system_info.get("os_version"),
                    last_login=current_time,
                    last_logout=None,
                    online_time=0,
                    cpu_info=system_info.get("cpu_info", "N/A"),
                    memory_total=system_info.get("memory_total", "N/A"),
                    resolution=system_info.get("resolution", "N/A"),
                    is_active="Online",
                    # Sistema de autorização
                    is_authorized=is_first_device,
                    authorization_status="authorized" if is_first_device else "pending",
                    authorization_date=current_time if is_first_device else None,
                    first_seen_at=current_time,
                    last_seen_at=current_time,
                )
                
                session.add(device_data)
                session.commit()
                session.refresh(device_data)
                
                if is_first_device:
                    LOGGER.info(f"Primeiro dispositivo criado e autorizado para usuário {user_id}")
                else:
                    LOGGER.warning(f"Novo dispositivo criado como PENDENTE para usuário {user_id}")
                
                LOGGER.info(f"  - Device Name: {device_data.device_name}")
                LOGGER.info(f"  - MAC: {device_data.mac_address}")
                LOGGER.info(f"  - IP: {device_data.ip_address}")
                return device_data
        
        except RuntimeError as e:
            # Erros críticos de captura de dados
            session.rollback()
            LOGGER.error(f"ERRO CRÍTICO ao criar/atualizar dispositivo: {e}")
            raise
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao criar/atualizar dispositivo: {e}")
            return None
        finally:
            session.close()

    def create_pending_device(
        self, user_id: str, device_id: str, device_info: dict
    ) -> Optional[DeviceData]:
        """
        Cria um dispositivo com status pendente (não autorizado)
        
        Args:
            user_id: ID do usuário
            device_id: UUID do dispositivo
            device_info: Informações do dispositivo
            
        Returns:
            Optional[DeviceData]: Dispositivo criado ou None
        """
        session = self.get_session()
        try:
            current_time = get_current_utc()
            
            device_data = DeviceData(
                user_id=user_id,
                device_id=device_id,
                device_name=device_info.get("hostname", "Unknown"),
                device_type=device_info.get("device_type", "Computador"),
                ip_address=device_info.get("ip_address", "127.0.0.1"),
                mac_address=device_info.get("mac_address", "00:00:00:00:00:00"),
                os_name=device_info.get("system", "Unknown"),
                os_version=device_info.get("os", "Unknown"),
                last_login=current_time,
                last_logout=None,
                online_time=0,
                cpu_info=device_info.get("processor", "N/A"),
                memory_total="N/A",
                resolution="N/A",
                is_active="Offline",
                # Sistema de autorização
                is_authorized=False,
                authorization_status="pending",
                first_seen_at=current_time,
                last_seen_at=current_time,
            )
            
            session.add(device_data)
            session.commit()
            session.refresh(device_data)
            
            LOGGER.info(f"Dispositivo pendente criado para usuário {user_id}")
            return device_data
        
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao criar dispositivo pendente: {e}")
            return None
        finally:
            session.close()

    def set_device_offline(self, user_id: str, mac_address: str) -> bool:
        """
        Marca dispositivo como offline e calcula tempo de sessão
        
        Args:
            user_id: ID do usuário
            mac_address: MAC address do dispositivo
            
        Returns:
            bool: True se sucesso
        """
        session = self.get_session()
        try:
            current_time = get_current_utc()
            
            LOGGER.info(f"Marcando dispositivo como offline - User: {user_id}, MAC: {mac_address}")
            
            # Buscar dispositivo ativo
            device = (
                session.query(DeviceData)
                .filter(
                    DeviceData.user_id == user_id,
                    DeviceData.mac_address == mac_address,
                    DeviceData.is_active == "Online"
                )
                .first()
            )

            if device and device.last_login:
                # Atualizar logout e status
                device.last_logout = current_time
                device.is_active = "Offline"
                
                # Calcular tempo da sessão
                if device.last_login:
                    session_time = safe_datetime_diff(device.last_login, current_time)
                    device.online_time = (device.online_time or 0) + session_time
                    LOGGER.info(f"Tempo de sessão calculado: {session_time}s")
                    LOGGER.info(f"Tempo total online: {device.online_time}s")
                else:
                    LOGGER.warning(f"device.last_login é None para usuário {user_id}")

                session.commit()
                LOGGER.info(f"Dispositivo marcado como offline com sucesso")
                return True

            elif device:
                LOGGER.info(f"Dispositivo já estava offline para usuário {user_id}")
                return True
            else:
                LOGGER.warning(f"Dispositivo não encontrado para usuário {user_id} e MAC {mac_address}")
                return False

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao marcar dispositivo como offline: {e}")
            import traceback
            LOGGER.error(f"Traceback: {traceback.format_exc()}")
            return False
        finally:
            session.close()

    def get_all_devices_with_users(self) -> List[Tuple[DeviceData, User]]:
        """Retorna todos os dispositivos com informações dos usuários"""
        session = self.get_session()
        try:
            devices_with_users = (
                session.query(DeviceData, User)
                .join(User, DeviceData.user_id == User.id)
                .order_by(DeviceData.last_login.desc())
                .all()
            )
            return devices_with_users
        except Exception as e:
            LOGGER.error(f"Erro ao buscar dispositivos com usuários: {e}")
            return []
        finally:
            session.close()

    def get_devices_by_user_id(self, user_id: str) -> List[DeviceData]:
        """Retorna todos os dispositivos de um usuário específico"""
        session = self.get_session()
        try:
            return (
                session.query(DeviceData)
                .filter(DeviceData.user_id == user_id)
                .order_by(DeviceData.last_login.desc())
                .all()
            )
        except Exception as e:
            LOGGER.error(f"Erro ao buscar dispositivos do usuário {user_id}: {e}")
            return []
        finally:
            session.close()

    def authorize_device(
        self, device_id: str, admin_user_id: str
    ) -> Tuple[bool, str]:
        """
        Autoriza um dispositivo pendente pelo device_id (UUID).

        Args:
            device_id: UUID do dispositivo (campo device_id, nao o id inteiro)
            admin_user_id: ID do admin autorizando

        Returns:
            Tuple[bool, str]: (sucesso, mensagem)
        """
        session = self.get_session()
        try:
            # Buscar pelo campo device_id (UUID unico) — nao pelo id inteiro
            device = (
                session.query(DeviceData)
                .filter(DeviceData.device_id == device_id)
                .first()
            )

            if not device:
                LOGGER.error(
                    f"authorize_device: dispositivo nao encontrado "
                    f"para device_id={device_id}"
                )
                return False, "Dispositivo nao encontrado"

            if device.is_authorized:
                LOGGER.info(
                    f"authorize_device: dispositivo {device_id} "
                    f"ja estava autorizado"
                )
                return False, "Dispositivo ja esta autorizado"

            device.authorize(admin_user_id)
            session.commit()

            LOGGER.info(
                f"Dispositivo {device_id} autorizado por admin {admin_user_id}"
            )
            return True, "Dispositivo autorizado com sucesso"

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao autorizar dispositivo: {e}")
            return False, f"Erro ao autorizar: {e}"
        finally:
            session.close()
    
    
    def reject_device(self, device_id: int) -> Tuple[bool, str]:
        """
        Rejeita um dispositivo pendente
        
        Args:
            device_id: ID do dispositivo no banco
            
        Returns:
            Tuple[bool, str]: (sucesso, mensagem)
        """
        session = self.get_session()
        try:
            device = session.query(DeviceData).filter(DeviceData.id == device_id).first()
            
            if not device:
                return False, "Dispositivo não encontrado"
            
            device.reject()
            session.commit()
            
            LOGGER.info(f"Dispositivo {device_id} rejeitado")
            return True, "Dispositivo rejeitado"
        
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao rejeitar dispositivo: {e}")
            return False, f"Erro ao rejeitar: {e}"
        finally:
            session.close()

    def revoke_device_authorization(self, device_id: int) -> Tuple[bool, str]:
        """
        Revoga autorização de um dispositivo
        
        Args:
            device_id: ID do dispositivo no banco
            
        Returns:
            Tuple[bool, str]: (sucesso, mensagem)
        """
        session = self.get_session()
        try:
            device = session.query(DeviceData).filter(DeviceData.id == device_id).first()
            
            if not device:
                return False, "Dispositivo não encontrado"
            
            if not device.is_authorized:
                return False, "Dispositivo não está autorizado"
            
            device.revoke_authorization()
            session.commit()
            
            LOGGER.info(f"Autorização revogada para dispositivo {device_id}")
            return True, "Autorização revogada"
        
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao revogar autorização: {e}")
            return False, f"Erro ao revogar: {e}"
        finally:
            session.close()

    def get_pending_devices(self) -> List[Tuple[DeviceData, User]]:
        """
        Retorna dispositivos pendentes de autorização
        
        Returns:
            List[Tuple[DeviceData, User]]: Lista de tuplas (dispositivo, usuário)
        """
        session = self.get_session()
        try:
            pending = (
                session.query(DeviceData, User)
                .join(User, DeviceData.user_id == User.id)
                .filter(DeviceData.authorization_status == "pending")
                .order_by(DeviceData.first_seen_at.desc())
                .all()
            )
            return pending
        except Exception as e:
            LOGGER.error(f"Erro ao buscar dispositivos pendentes: {e}")
            return []
        finally:
            session.close()
