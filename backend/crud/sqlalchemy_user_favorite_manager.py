# crud/sqlalchemy_user_favorite_manager.py
from typing import List, Optional, Tuple

from sqlalchemy import and_
from sqlalchemy.orm import joinedload

from crud.base_manager import BaseManager
from database.models.ai_tool import AITool
from database.models.user import User
from database.models.user_favorite import UserFavorite
from utils.logger import LOGGER


class SQLAlchemyUserFavoriteManager(BaseManager[UserFavorite]):
    """Manager para gerenciar favoritos dos usuários"""

    def __init__(self):
        super().__init__(UserFavorite)

    def add_favorite(self, user_id: str, ai_tool_id: str) -> Tuple[bool, str]:
        """Adiciona uma IA aos favoritos do usuário"""
        session = self.get_session()
        try:
            # Verificar se já existe
            existing = (
                session.query(UserFavorite)
                .filter(
                    and_(
                        UserFavorite.user_id == user_id,
                        UserFavorite.ai_tool_id == ai_tool_id,
                    )
                )
                .first()
            )

            if existing:
                return True, "Já está nos favoritos"

            # Verificar se user e ai_tool existem
            user = session.query(User).filter(User.id == user_id).first()
            ai_tool = session.query(AITool).filter(AITool.id == ai_tool_id).first()

            if not user:
                return False, "Usuário não encontrado"
            if not ai_tool:
                return False, "IA não encontrada"

            # Criar favorito
            favorite = UserFavorite(user_id=user_id, ai_tool_id=ai_tool_id)

            session.add(favorite)
            session.commit()

            LOGGER.info(f"Favorito adicionado: user={user_id}, ai_tool={ai_tool_id}")
            return True, "Adicionado aos favoritos"

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao adicionar favorito: {e}")
            return False, str(e)
        finally:
            session.close()

    def remove_favorite(self, user_id: str, ai_tool_id: str) -> Tuple[bool, str]:
        """Remove uma IA dos favoritos do usuário"""
        session = self.get_session()
        try:
            favorite = (
                session.query(UserFavorite)
                .filter(
                    and_(
                        UserFavorite.user_id == user_id,
                        UserFavorite.ai_tool_id == ai_tool_id,
                    )
                )
                .first()
            )

            if not favorite:
                return False, "Favorito não encontrado"

            session.delete(favorite)
            session.commit()

            LOGGER.info(f"Favorito removido: user={user_id}, ai_tool={ai_tool_id}")
            return True, "Removido dos favoritos"

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao remover favorito: {e}")
            return False, str(e)
        finally:
            session.close()

    def toggle_favorite(self, user_id: str, ai_tool_id: str) -> Tuple[bool, str, bool]:
        """Alterna status de favorito. Retorna (sucesso, mensagem, is_favorite)"""
        session = self.get_session()
        try:
            existing = (
                session.query(UserFavorite)
                .filter(
                    and_(
                        UserFavorite.user_id == user_id,
                        UserFavorite.ai_tool_id == ai_tool_id,
                    )
                )
                .first()
            )

            if existing:
                # Remover
                session.delete(existing)
                session.commit()
                LOGGER.info(
                    f"Favorito removido via toggle: user={user_id}, ai_tool={ai_tool_id}"
                )
                return True, "Removido dos favoritos", False
            else:
                # Adicionar
                # Verificar se user e ai_tool existem
                user = session.query(User).filter(User.id == user_id).first()
                ai_tool = session.query(AITool).filter(AITool.id == ai_tool_id).first()

                if not user:
                    return False, "Usuário não encontrado", False
                if not ai_tool:
                    return False, "IA não encontrada", False

                favorite = UserFavorite(user_id=user_id, ai_tool_id=ai_tool_id)

                session.add(favorite)
                session.commit()
                LOGGER.info(
                    f"Favorito adicionado via toggle: user={user_id}, ai_tool={ai_tool_id}"
                )
                return True, "Adicionado aos favoritos", True

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao alternar favorito: {e}")
            return False, str(e), False
        finally:
            session.close()

    def get_user_favorites(self, user_id: str) -> List[AITool]:
        """Busca todas as IAs favoritas de um usuário"""
        session = self.get_session()
        try:
            favorites = (
                session.query(UserFavorite)
                .filter(UserFavorite.user_id == user_id)
                .options(joinedload(UserFavorite.ai_tool))
                .all()
            )

            return [fav.ai_tool for fav in favorites if fav.ai_tool]

        except Exception as e:
            LOGGER.error(f"Erro ao buscar favoritos do usuário {user_id}: {e}")
            return []
        finally:
            session.close()

    def get_user_favorite_ids(self, user_id: str) -> List[str]:
        """Busca apenas os IDs das IAs favoritas de um usuário"""
        session = self.get_session()
        try:
            favorite_ids = (
                session.query(UserFavorite.ai_tool_id)
                .filter(UserFavorite.user_id == user_id)
                .all()
            )

            return [fav_id[0] for fav_id in favorite_ids]

        except Exception as e:
            LOGGER.error(f"Erro ao buscar IDs de favoritos do usuário {user_id}: {e}")
            return []
        finally:
            session.close()

    def is_favorite(self, user_id: str, ai_tool_id: str) -> bool:
        """Verifica se uma IA é favorita de um usuário"""
        session = self.get_session()
        try:
            exists = (
                session.query(UserFavorite)
                .filter(
                    and_(
                        UserFavorite.user_id == user_id,
                        UserFavorite.ai_tool_id == ai_tool_id,
                    )
                )
                .first()
                is not None
            )

            return exists

        except Exception as e:
            LOGGER.error(f"Erro ao verificar favorito: {e}")
            return False
        finally:
            session.close()

    def get_favorite_count_by_ai(self, ai_tool_id: str) -> int:
        """Conta quantos usuários favoritaram uma IA específica"""
        session = self.get_session()
        try:
            count = (
                session.query(UserFavorite)
                .filter(UserFavorite.ai_tool_id == ai_tool_id)
                .count()
            )

            return count

        except Exception as e:
            LOGGER.error(f"Erro ao contar favoritos da IA {ai_tool_id}: {e}")
            return 0
        finally:
            session.close()

    def get_user_favorites_with_details(self, user_id: str) -> List[dict]:
        """Busca favoritos do usuário com detalhes completos das IAs"""
        session = self.get_session()
        try:
            favorites = (
                session.query(UserFavorite)
                .filter(UserFavorite.user_id == user_id)
                .options(joinedload(UserFavorite.ai_tool))
                .all()
            )

            result = []
            for fav in favorites:
                if fav.ai_tool:
                    ai_tool = fav.ai_tool
                    result.append(
                        {
                            "id": str(ai_tool.id),
                            "name": ai_tool.name,
                            "url": ai_tool.url,
                            "category": ai_tool.category or "conversacao",
                            "tags": ai_tool.tags or ["IA"],
                            "description": getattr(ai_tool, "description", ""),
                            "is_favorite": True,
                            "favorited_at": (
                                fav.created_at.isoformat() if fav.created_at else None
                            ),
                        }
                    )

            return result

        except Exception as e:
            LOGGER.error(
                f"Erro ao buscar detalhes dos favoritos do usuário {user_id}: {e}"
            )
            return []
        finally:
            session.close()
