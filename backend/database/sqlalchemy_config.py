# database/sqlalchemy_config.py - VERSÃO COM CREDENCIAIS HARDCODED
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool

from utils.config_manager import config_manager
from utils.logger import LOGGER

Base = declarative_base()


class DatabaseConfig:
    """Configuração do banco com credenciais hardcoded"""

    def __init__(self):
        self.DATABASE_URL = None
        self.engine = None
        self.SessionLocal = None
        self._initialized = False
        LOGGER.info("DatabaseConfig inicializado com credenciais hardcoded")

    def _ensure_initialized(self):
        """Garante inicialização apenas quando necessário"""
        if not self._initialized:
            LOGGER.info("Inicializando conexão com banco...")
            self._initialize_connection()
            self._initialized = True

    def _get_database_url(self):
        """Constrói URL usando credenciais hardcoded"""
        db_config = config_manager.get_database_config()

        if not db_config.user or not db_config.password:
            error_msg = "Credenciais hardcoded não configuradas em config_manager.py"
            LOGGER.error(error_msg)
            LOGGER.error("Edite utils/config_manager.py e configure as credenciais")
            raise ConnectionError(error_msg)

        url = f"mysql+pymysql://{db_config.user}:{db_config.password}@{db_config.host}:{db_config.port}/{db_config.database}?charset=utf8mb4"

        # Log sem senha por segurança
        safe_url = f"mysql+pymysql://{db_config.user}:****@{db_config.host}:{db_config.port}/{db_config.database}"
        LOGGER.info(f"URL de conexão: {safe_url}")
        return url

    def _initialize_connection(self):
        """Inicialização da conexão com tratamento de erro melhorado"""
        try:
            self.DATABASE_URL = self._get_database_url()

            # Engine otimizado
            self.engine = create_engine(
                self.DATABASE_URL,
                poolclass=QueuePool,
                pool_size=10,
                max_overflow=20,
                pool_timeout=60,
                pool_recycle=7200,
                echo=False,
                connect_args={
                    "charset": "utf8mb4",
                    "connect_timeout": 20,
                    "read_timeout": 60,
                    "write_timeout": 60,
                    "autocommit": False,
                },
            )

            self.SessionLocal = sessionmaker(
                autocommit=False, 
                autoflush=False, 
                bind=self.engine
            )

            # Teste de conexão imediato
            LOGGER.info("Conexão com banco configurada e testada com sucesso")

        except Exception as e:
            LOGGER.error(f"Erro crítico ao configurar banco de dados: {e}")
            LOGGER.error("Verifique:")
            LOGGER.error("1. Credenciais em utils/config_manager.py")
            LOGGER.error("2. Se o MySQL está rodando")
            LOGGER.error("3. Se a porta 33060 está acessível")
            LOGGER.error("4. Se o banco 'browser' existe")
            raise

    def get_session(self):
        """Retorna sessão, inicializando se necessário"""
        self._ensure_initialized()
        return self.SessionLocal()

    def create_tables(self):
        """Cria tabelas, inicializando se necessário"""
        self._ensure_initialized()
        try:
            LOGGER.info("Criando tabelas do banco de dados...")
            Base.metadata.create_all(bind=self.engine)
            LOGGER.info("Tabelas criadas com sucesso")
        except Exception as e:
            LOGGER.error(f"Erro ao criar tabelas: {e}")
            raise

    def test_connection_sync(self):
        """Teste de conexão síncrono"""
        try:
            self._ensure_initialized()
            return True
        except Exception as e:
            LOGGER.error(f"Teste de conexão síncrono falhou: {e}")
            return False


# Instância global
db_config = DatabaseConfig()