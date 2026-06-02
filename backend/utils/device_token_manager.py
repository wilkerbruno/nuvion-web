"""
Gerenciador de Device Token
Responsável por gerar, armazenar e recuperar identificador único do dispositivo
"""

import json
import platform
import socket
import uuid
from pathlib import Path
from typing import Optional, Dict

from utils.logger import LOGGER


class DeviceTokenManager:
    """Gerencia identificador único e persistente do dispositivo"""

    def __init__(self):
        """Inicializa o gerenciador de device token"""
        self.system = platform.system()
        self.device_id_cache = None
        LOGGER.info(f"DeviceTokenManager inicializado - Sistema: {self.system}")

    def generate_device_id(self) -> str:
        """
        Gera um novo device_id único (UUID v4)
        
        Returns:
            str: UUID v4 como string
        """
        device_id = str(uuid.uuid4())
        LOGGER.info(f"Novo device_id gerado: {device_id}")
        return device_id

    def get_storage_path(self) -> Path:
        """
        Retorna caminho para armazenar device_id de forma segura
        
        Returns:
            Path: Caminho do arquivo de armazenamento
        """
        base_dir = Path.home() / ".nuvion_browser"
        base_dir.mkdir(parents=True, exist_ok=True)
        
        storage_file = base_dir / ".device_id"
        return storage_file

    def save_device_id_windows(self, device_id: str) -> bool:
        """
        Salva device_id no Windows Registry
        
        Args:
            device_id: UUID do dispositivo
            
        Returns:
            bool: True se salvou com sucesso
        """
        try:
            import winreg
            
            # Abrir chave no registry (HKEY_CURRENT_USER)
            key_path = r"Software\NuvionBrowser"
            
            # Criar chave se não existir
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
            
            # Salvar device_id
            winreg.SetValueEx(key, "DeviceID", 0, winreg.REG_SZ, device_id)
            
            # Fechar chave
            winreg.CloseKey(key)
            
            LOGGER.info(f"Device ID salvo no Registry: {key_path}")
            return True
            
        except Exception as e:
            LOGGER.error(f"Erro ao salvar device_id no Registry: {e}")
            return False

    def load_device_id_windows(self) -> Optional[str]:
        """
        Carrega device_id do Windows Registry
        
        Returns:
            Optional[str]: Device ID ou None se não encontrado
        """
        try:
            import winreg
            
            key_path = r"Software\NuvionBrowser"
            
            # Abrir chave
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            
            # Ler valor
            device_id, _ = winreg.QueryValueEx(key, "DeviceID")
            
            # Fechar chave
            winreg.CloseKey(key)
            
            LOGGER.info("Device ID recuperado do Registry")
            return device_id
            
        except FileNotFoundError:
            LOGGER.info("Device ID não encontrado no Registry")
            return None
        except Exception as e:
            LOGGER.error(f"Erro ao carregar device_id do Registry: {e}")
            return None

    def save_device_id_unix(self, device_id: str) -> bool:
        """
        Salva device_id em arquivo para Linux/Mac
        
        Args:
            device_id: UUID do dispositivo
            
        Returns:
            bool: True se salvou com sucesso
        """
        try:
            storage_path = self.get_storage_path()
            
            # Dados a serem salvos
            data = {
                "device_id": device_id,
                "created_at": platform.node(),
                "system": platform.system()
            }
            
            # Salvar em arquivo JSON
            with open(storage_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Definir permissões restritas (apenas usuário pode ler/escrever)
            storage_path.chmod(0o600)
            
            LOGGER.info(f"Device ID salvo em: {storage_path}")
            return True
            
        except Exception as e:
            LOGGER.error(f"Erro ao salvar device_id em arquivo: {e}")
            return False

    def load_device_id_unix(self) -> Optional[str]:
        """
        Carrega device_id de arquivo para Linux/Mac
        
        Returns:
            Optional[str]: Device ID ou None se não encontrado
        """
        try:
            storage_path = self.get_storage_path()
            
            if not storage_path.exists():
                LOGGER.info("Arquivo de device_id não encontrado")
                return None
            
            # Ler arquivo JSON
            with open(storage_path, 'r') as f:
                data = json.load(f)
            
            device_id = data.get("device_id")
            
            if device_id:
                LOGGER.info("Device ID recuperado do arquivo")
                return device_id
            else:
                LOGGER.warning("Device ID não encontrado no arquivo")
                return None
                
        except Exception as e:
            LOGGER.error(f"Erro ao carregar device_id de arquivo: {e}")
            return None

    def save_device_id(self, device_id: str) -> bool:
        """
        Salva device_id de forma segura (multiplataforma)
        
        Args:
            device_id: UUID do dispositivo
            
        Returns:
            bool: True se salvou com sucesso
        """
        if self.system == "Windows":
            success = self.save_device_id_windows(device_id)
            # Fallback para arquivo se Registry falhar
            if not success:
                LOGGER.warning("Registry falhou, usando arquivo como fallback")
                success = self.save_device_id_unix(device_id)
            return success
        else:
            return self.save_device_id_unix(device_id)

    def load_device_id(self) -> Optional[str]:
        """
        Carrega device_id salvo (multiplataforma)
        
        Returns:
            Optional[str]: Device ID ou None se não encontrado
        """
        if self.system == "Windows":
            device_id = self.load_device_id_windows()
            # Fallback para arquivo se Registry falhar
            if not device_id:
                device_id = self.load_device_id_unix()
            return device_id
        else:
            return self.load_device_id_unix()

    def get_or_create_device_id(self) -> str:
        """
        Obtém device_id existente ou cria um novo
        Método principal para obter device_id
        
        Returns:
            str: Device ID do dispositivo
        """
        # Usar cache se disponível
        if self.device_id_cache:
            LOGGER.debug("Usando device_id do cache")
            return self.device_id_cache
        
        # Tentar carregar device_id existente
        device_id = self.load_device_id()
        
        if device_id:
            LOGGER.info(f"Device ID existente encontrado: {device_id}")
            self.device_id_cache = device_id
            return device_id
        
        # Se não existe, gerar novo
        LOGGER.info("Nenhum device_id encontrado - gerando novo")
        device_id = self.generate_device_id()
        
        # Salvar novo device_id
        if self.save_device_id(device_id):
            LOGGER.info("Novo device_id gerado e salvo com sucesso")
            self.device_id_cache = device_id
            return device_id
        else:
            LOGGER.error("Falha ao salvar device_id - usando temporário")
            # Mesmo que falhe ao salvar, retornar o gerado (temporário)
            return device_id

    def get_hostname(self) -> str:
        """
        Obtém nome do computador
        
        Returns:
            str: Nome do host
        """
        try:
            return platform.node()
        except Exception as e:
            LOGGER.error(f"Erro ao obter hostname: {e}")
            return "Unknown"

    def get_os_info(self) -> str:
        """
        Obtém informações do sistema operacional
        
        Returns:
            str: Nome e versão do SO
        """
        try:
            return f"{platform.system()} {platform.release()}"
        except Exception as e:
            LOGGER.error(f"Erro ao obter info do SO: {e}")
            return "Unknown"

    def get_local_ip(self) -> str:
        """
        Obtém IP local da máquina
        
        Returns:
            str: Endereço IP local
        """
        try:
            # Conectar a um servidor externo para obter IP da interface usada
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception as e:
            LOGGER.error(f"Erro ao obter IP local: {e}")
            return "127.0.0.1"

    def get_processor_info(self) -> str:
        """
        Obtém informações do processador
        
        Returns:
            str: Nome do processador
        """
        try:
            return platform.processor()
        except Exception as e:
            LOGGER.error(f"Erro ao obter info do processador: {e}")
            return "Unknown"

    def get_device_info(self) -> Dict[str, str]:
        """
        Coleta informações completas do dispositivo
        Usado para enviar ao servidor junto com device_id
        
        Returns:
            Dict: Dicionário com informações do dispositivo
        """
        try:
            device_info = {
                "device_id": self.get_or_create_device_id(),
                "hostname": self.get_hostname(),
                "os": self.get_os_info(),
                "ip_address": self.get_local_ip(),
                "processor": self.get_processor_info(),
                "system": platform.system(),
                "platform": platform.platform(),
            }
            
            LOGGER.info("Informações do dispositivo coletadas")
            LOGGER.debug(f"Device Info: {device_info}")
            
            return device_info
            
        except Exception as e:
            LOGGER.error(f"Erro ao coletar informações do dispositivo: {e}")
            # Retornar informações mínimas
            return {
                "device_id": self.get_or_create_device_id(),
                "hostname": "Unknown",
                "os": "Unknown",
                "ip_address": "127.0.0.1",
                "processor": "Unknown",
                "system": "Unknown",
                "platform": "Unknown",
            }

    def clear_device_id(self) -> bool:
        """
        Remove device_id armazenado (útil para testes)
        
        Returns:
            bool: True se removeu com sucesso
        """
        try:
            # Limpar cache
            self.device_id_cache = None
            
            # Remover do Registry (Windows)
            if self.system == "Windows":
                try:
                    import winreg
                    key_path = r"Software\NuvionBrowser"
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE)
                    winreg.DeleteValue(key, "DeviceID")
                    winreg.CloseKey(key)
                    LOGGER.info("Device ID removido do Registry")
                except:
                    pass
            
            # Remover arquivo (todos os sistemas)
            storage_path = self.get_storage_path()
            if storage_path.exists():
                storage_path.unlink()
                LOGGER.info(f"Arquivo de device_id removido: {storage_path}")
            
            return True
            
        except Exception as e:
            LOGGER.error(f"Erro ao limpar device_id: {e}")
            return False

    def validate_device_id(self, device_id: str) -> bool:
        """
        Valida formato do device_id
        
        Args:
            device_id: Device ID a ser validado
            
        Returns:
            bool: True se válido
        """
        try:
            # Tentar converter para UUID
            uuid_obj = uuid.UUID(device_id)
            # Verificar se é UUID versão 4
            is_valid = uuid_obj.version == 4
            
            if not is_valid:
                LOGGER.warning(f"Device ID não é UUID v4: {device_id}")
            
            return is_valid
            
        except ValueError:
            LOGGER.error(f"Device ID inválido: {device_id}")
            return False


# Instância global do gerenciador
device_token_manager = DeviceTokenManager()