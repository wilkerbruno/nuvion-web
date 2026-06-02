import logging
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from database.models.base import BaseModel
from database.sqlalchemy_config import db_config
from utils.logger import LOGGER

# Type variable para modelos
ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseManager(Generic[ModelType]):
    """Manager base com operações CRUD comuns"""

    def __init__(self, model: Type[ModelType]):
        self.model = model
        self.logger = logging.getLogger(f"{__name__}.{model.__name__}")

    def get_session(self) -> Session:
        """Obtém uma sessão do banco"""
        return db_config.get_session()

    def create(self, **kwargs) -> Optional[ModelType]:
        """Cria um novo registro"""
        session = self.get_session()
        try:
            instance = self.model(**kwargs)
            session.add(instance)
            session.commit()
            session.refresh(instance)
            return instance
        except SQLAlchemyError as e:
            session.rollback()
            self.logger.error(f"Erro ao criar {self.model.__name__}: {e}")
            return None
        finally:
            session.close()

    def get_by_id(self, id: str) -> Optional[ModelType]:
        """Busca por ID"""
        session = self.get_session()
        try:
            return session.query(self.model).filter(self.model.id == id).first()
        except SQLAlchemyError as e:
            self.logger.error(f"Erro ao buscar {self.model.__name__}: {e}")
            return None
        finally:
            session.close()

    def get_all(self, limit: int = 100, offset: int = 0) -> List[ModelType]:
        """Lista todos os registros com paginação"""
        session = self.get_session()
        try:
            return session.query(self.model).limit(limit).offset(offset).all()
        except SQLAlchemyError as e:
            self.logger.error(f"Erro ao listar {self.model.__name__}: {e}")
            return []
        finally:
            session.close()

    def update(self, entity_id: str, data=None, **kwargs) -> bool:
        """
        Atualiza um registro.
        Aceita tanto dict quanto kwargs para compatibilidade:
            update(id, {"status": "Inativo"})
            update(id, status="Inativo")  <- legado, ainda suportado
        """
        session = self.get_session()
        try:
            # Normalizar: aceitar dict ou kwargs
            if data is None:
                data = kwargs
            elif isinstance(data, dict) and kwargs:
                data.update(kwargs)

            entity = session.query(self.model).filter_by(id=entity_id).first()
            if not entity:
                self.logger.warning(
                    f"{self.model.__name__} nao encontrado: {entity_id}"
                )
                return False

            for key, value in data.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
                else:
                    self.logger.warning(
                        f"Campo '{key}' nao existe em {self.model.__name__} — ignorado"
                    )

            session.commit()
            return True

        except Exception as e:
            session.rollback()
            self.logger.error(
                f"Erro ao atualizar {self.model.__name__} {entity_id}: {e}"
            )
            return False
        finally:
            session.close()
    
    
    def delete(self, id: str) -> bool:
        """Remove um registro"""
        session = self.get_session()
        try:
            instance = session.query(self.model).filter(self.model.id == id).first()
            if not instance:
                return False

            session.delete(instance)
            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            self.logger.error(f"Erro ao deletar {self.model.__name__}: {e}")
            return False
        finally:
            session.close()



    def get_by_id_with_relationships(
        self, id: str, *relationships
    ) -> Optional[ModelType]:
        """Busca por ID carregando relacionamentos especificados"""
        session = self.get_session()
        try:
            query = session.query(self.model)

            # Adicionar eager loading para relacionamentos especificados
            for relationship in relationships:
                query = query.options(joinedload(getattr(self.model, relationship)))

            return query.filter(self.model.id == id).first()
        except SQLAlchemyError as e:
            self.logger.error(
                f"Erro ao buscar {self.model.__name__} com relacionamentos: {e}"
            )
            return None
        finally:
            session.close()

    def update_and_return(self, id: str, **kwargs) -> Optional[ModelType]:
        """Atualiza um registro e retorna a instância atualizada com relacionamentos"""
        session = self.get_session()
        try:
            instance = session.query(self.model).filter(self.model.id == id).first()
            if not instance:
                return None

            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)

            session.commit()
            session.refresh(instance)

            # Retornar a instância ainda conectada à sessão
            return instance

        except SQLAlchemyError as e:
            session.rollback()
            self.logger.error(f"Erro ao atualizar {self.model.__name__}: {e}")
            return None
        finally:
            session.close()

    def get_all_with_relationships(self, *relationships) -> List[ModelType]:
        """Lista todos os registros carregando relacionamentos especificados"""
        session = self.get_session()
        try:
            query = session.query(self.model)

            # Adicionar eager loading para relacionamentos especificados
            for relationship in relationships:
                query = query.options(joinedload(getattr(self.model, relationship)))

            return query.all()
        except SQLAlchemyError as e:
            self.logger.error(
                f"Erro ao listar {self.model.__name__} com relacionamentos: {e}"
            )
            return []
        finally:
            session.close()
