from typing import Dict, List, Optional, Tuple
from sqlalchemy import and_, or_
from crud.base_manager import BaseManager
from database.models.ai_tool import AITool
from utils.logger import LOGGER


class SQLAlchemyAIToolsManager(BaseManager[AITool]):
    """Manager para ferramentas de IA usando SQLAlchemy - VERSÃO LIMPA"""

    def __init__(self):
        super().__init__(AITool)

    def add_tool(
        self,
        name: str,
        url: str,
        description: str,
        category: str,
        tags: List[str],
        observations: str = None,
        proxy_id: str = None,
        login_method: str = "manual",
        is_featured: bool = False,
        block_extensions: bool = False,  # *** NOVO PARÂMETRO ***
    ) -> Tuple[bool, str]:
        """
        Adiciona nova ferramenta de IA
        
        Args:
            name: Nome da IA
            url: URL da IA
            description: Descrição da IA
            category: Categoria da IA
            tags: Lista de tags
            observations: Observações
            proxy_id: ID do proxy (opcional)
            login_method: Método de login (manual, direct, cookies, google)
            is_featured: Se é IA em destaque
            block_extensions: Se deve bloquear extensões do Chrome
            
        Returns:
            Tuple[bool, str]: (sucesso, id_da_ia_ou_mensagem_erro)
        """
        session = self.get_session()
        try:
            self.logger.info(f"=== CRIANDO IA: {name} ===")
            self.logger.info(f"URL: {url}, Método de login: {login_method}")
            self.logger.info(f"Bloquear extensões: {block_extensions}")
            
            # Verificar se já existe
            existing = session.query(AITool).filter(
                AITool.name == name
            ).first()

            if existing:
                self.logger.warning(f"IA já existe com o nome: {name}")
                return False, "Ferramenta com este nome já existe"
            
            # Criar nova ferramenta
            tool = AITool(
                name=name,
                url=url,
                description=description,
                category=category,
                tags=tags,
                observations=observations,
                proxy_id=proxy_id,
                login_method=login_method,
                is_featured=is_featured,
                block_extensions=block_extensions,  # *** ADICIONAR ***
            )

            session.add(tool)
            session.commit()

            self.logger.info(f"✅ IA '{name}' criada com sucesso - ID: {tool.id}")
            return True, tool.id

        except Exception as e:
            session.rollback()
            self.logger.error(f"❌ Erro ao criar IA '{name}': {e}")
            return False, f"Erro ao criar IA: {str(e)}"
        finally:
            session.close()

    def update_tool(
        self,
        tool_id: str,
        name: str = None,
        url: str = None,
        description: str = None,
        category: str = None,
        tags: List[str] = None,
        observations: str = None,
        proxy_id: str = None,
        login_method: str = None,
        is_featured: bool = None,
        block_extensions: bool = None,  # *** NOVO PARÂMETRO ***
    ) -> bool:
        """Atualiza dados de uma IA existente"""
        session = self.get_session()
        try:
            tool = session.query(AITool).filter(AITool.id == tool_id).first()
            
            if not tool:
                self.logger.warning(f"IA não encontrada: {tool_id}")
                return False

            # Atualizar apenas campos fornecidos
            if name is not None:
                tool.name = name
            if url is not None:
                tool.url = url
            if description is not None:
                tool.description = description
            if category is not None:
                tool.category = category
            if tags is not None:
                tool.tags = tags
            if observations is not None:
                tool.observations = observations
            if proxy_id is not None:
                tool.proxy_id = proxy_id
            if login_method is not None:
                tool.login_method = login_method
            if is_featured is not None:
                tool.is_featured = is_featured
            if block_extensions is not None:  # *** ADICIONAR ***
                tool.block_extensions = block_extensions
                self.logger.info(f"Block extensions atualizado para: {block_extensions}")

            session.commit()
            self.logger.info(f"✅ IA atualizada: {tool.name}")
            return True

        except Exception as e:
            session.rollback()
            self.logger.error(f"❌ Erro ao atualizar IA {tool_id}: {e}")
            return False
        finally:
            session.close()

    def get_tool_with_credentials_info(self, tool_id: str) -> Optional[Dict]:
        """
        Retorna IA com informações sobre credenciais
        """
        session = self.get_session()
        try:
            tool = session.query(AITool).filter(AITool.id == tool_id).first()
            
            if not tool:
                return None

            # Criar resumo básico da IA
            tool_data = {
                'id': tool.id,
                'name': tool.name,
                'url': tool.url,
                'description': tool.description,
                'category': tool.category,
                'tags': tool.tags,
                'observations': tool.observations,
                'proxy_id': tool.proxy_id,
                'login_method': tool.login_method,
                'is_featured': tool.is_featured,
                'created_at': tool.created_at,
                'updated_at': tool.updated_at,
            }

            # Adicionar informações de credenciais
            try:
                from crud.database_adapter import crud_system
                
                # Verificar se tem credenciais diretas configuradas
                direct_summary = crud_system.direct_credentials.get_credentials_summary(tool_id)
                tool_data['direct_configured'] = direct_summary.get('configured', False)
                
                # Verificar cookies (se tiver método para isso)
                tool_data['cookies_configured'] = tool.has_cookies_configured() if hasattr(tool, 'has_cookies_configured') else False
                
            except Exception as cred_error:
                self.logger.debug(f"Erro ao verificar credenciais para {tool_id}: {cred_error}")
                # Valores padrão em caso de erro
                tool_data['direct_configured'] = False
                tool_data['cookies_configured'] = False

            return tool_data

        except Exception as e:
            self.logger.error(f"Erro ao buscar ferramenta com credenciais {tool_id}: {e}")
            return None
        finally:
            session.close()

    def get_tools_by_category(self, category: str) -> List[AITool]:
        """Busca IAs por categoria"""
        session = self.get_session()
        try:
            tools = session.query(AITool).filter(
                AITool.category == category
            ).all()
            return tools
        except Exception as e:
            self.logger.error(f"Erro ao buscar IAs por categoria {category}: {e}")
            return []
        finally:
            session.close()

    def get_featured_tools(self) -> List[AITool]:
        """Busca IAs em destaque"""
        session = self.get_session()
        try:
            tools = session.query(AITool).filter(
                AITool.is_featured == True
            ).all()
            return tools
        except Exception as e:
            self.logger.error(f"Erro ao buscar IAs em destaque: {e}")
            return []
        finally:
            session.close()

    def search_tools(self, query: str) -> List[AITool]:
        """Busca IAs por nome ou descrição"""
        session = self.get_session()
        try:
            tools = session.query(AITool).filter(
                or_(
                    AITool.name.ilike(f"%{query}%"),
                    AITool.description.ilike(f"%{query}%")
                )
            ).all()
            return tools
        except Exception as e:
            self.logger.error(f"Erro ao buscar IAs com query '{query}': {e}")
            return []
        finally:
            session.close()

    def get_tools_with_login_method(self, login_method: str) -> List[AITool]:
        """Busca IAs por método de login"""
        session = self.get_session()
        try:
            tools = session.query(AITool).filter(
                AITool.login_method == login_method
            ).all()
            return tools
        except Exception as e:
            self.logger.error(f"Erro ao buscar IAs com login {login_method}: {e}")
            return []
        finally:
            session.close()

    def get_statistics(self) -> Dict:
        """Retorna estatísticas das IAs"""
        session = self.get_session()
        try:
            total = session.query(AITool).count()
            featured = session.query(AITool).filter(AITool.is_featured == True).count()
            
            # Contar por método de login
            direct_count = session.query(AITool).filter(AITool.login_method == "direct").count()
            cookies_count = session.query(AITool).filter(AITool.login_method == "cookies").count()
            manual_count = session.query(AITool).filter(AITool.login_method == "manual").count()
            
            # Contar por categoria
            from sqlalchemy import func
            categories = session.query(
                AITool.category, 
                func.count(AITool.id).label('count')
            ).group_by(AITool.category).all()
            
            return {
                'total_tools': total,
                'featured_tools': featured,
                'login_methods': {
                    'direct': direct_count,
                    'cookies': cookies_count,
                    'manual': manual_count
                },
                'categories': {cat: count for cat, count in categories}
            }
            
        except Exception as e:
            self.logger.error(f"Erro ao gerar estatísticas: {e}")
            return {}
        finally:
            session.close()

    def delete_tool(self, ai_tool_id: str) -> bool:
        """
        Remove ferramenta de IA e todas suas dependências
        
        Remove em ordem:
        1. Credenciais Diretas  
        2. Cookies de sessão
        3. A própria IA
        """
        session = self.get_session()
        try:
            self.logger.info(f"🗑️ Iniciando remoção da IA: {ai_tool_id}")
            
            # 1. Buscar a IA
            ai_tool = session.query(AITool).filter(AITool.id == ai_tool_id).first()
            if not ai_tool:
                self.logger.warning(f"IA {ai_tool_id} não encontrada")
                return False
            
            ai_name = ai_tool.name
            self.logger.info(f"Removendo IA: {ai_name}")

            # Remover credenciais diretas (se existir)
            direct_deleted = 0
            if hasattr(ai_tool, 'direct_credentials') and ai_tool.direct_credentials:
                session.delete(ai_tool.direct_credentials)
                direct_deleted = 1
                self.logger.info(f"✅ Credenciais diretas removidas")
            
            # Remover cookies de sessão (se existir)
            cookies_deleted = 0
            if hasattr(ai_tool, 'cookie_sessions') and ai_tool.cookie_sessions:
                for cookie_session in ai_tool.cookie_sessions:
                    session.delete(cookie_session)
                    cookies_deleted += 1
                self.logger.info(f"✅ {cookies_deleted} sessões de cookies removidas")
            
            # Remover a IA
            session.delete(ai_tool)
            
            # Commit todas as operações
            session.commit()
            
            self.logger.info(
                f"🎉 IA '{ai_name}' removida com sucesso! "
                f"Direct: {direct_deleted}, Cookies: {cookies_deleted})"
            )
            
            return True
            
        except Exception as e:
            session.rollback()
            self.logger.error(f"❌ Erro ao remover IA: {e}")
            return False
        finally:
            session.close()

    def get_by_name(self, name: str) -> Optional[AITool]:
        """
        Busca IA pelo nome exato
        
        Args:
            name: Nome exato da IA
            
        Returns:
            AITool ou None se não encontrar
        """
        session = self.get_session()
        try:
            self.logger.info(f"🔍 Buscando IA pelo nome: '{name}'")
            
            tool = session.query(AITool).filter(
                AITool.name == name
            ).first()
            
            if tool:
                self.logger.info(f"✅ IA encontrada: {tool.name} (ID: {tool.id})")
            else:
                self.logger.warning(f"❌ IA não encontrada com nome: '{name}'")
            
            return tool
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao buscar IA por nome '{name}': {e}")
            return None
        finally:
            session.close()

    def get_by_name_or_id(self, identifier: str) -> Optional[AITool]:
        """
        Busca IA por nome ou ID (método conveniente)
        
        Args:
            identifier: Nome ou ID da IA
            
        Returns:
            AITool ou None se não encontrar
        """
        session = self.get_session()
        try:
            self.logger.info(f"🔍 Buscando IA por nome ou ID: '{identifier}'")
            
            # Tentar primeiro por ID (se parece com UUID)
            if len(identifier) == 36 and '-' in identifier:
                tool = self.get_by_id(identifier)
                if tool:
                    return tool
            
            # Tentar por nome
            tool = self.get_by_name(identifier)
            if tool:
                return tool
            
            # Tentar busca aproximada
            tools = self.search_tools(identifier)
            if tools:
                self.logger.info(f"📋 Encontradas {len(tools)} IAs com busca aproximada")
                # Retornar primeira com nome exato (se existir)
                for tool in tools:
                    if tool.name.lower() == identifier.lower():
                        return tool
                # Senão, retornar primeira
                return tools[0]
            
            self.logger.warning(f"❌ IA não encontrada: '{identifier}'")
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao buscar IA '{identifier}': {e}")
            return None


    def update_favicon(self, tool_id: str, icon_url: str) -> bool:
        """
        Atualiza a URL do favicon de uma ferramenta
        
        Args:
            tool_id: ID da ferramenta
            icon_url: URL do ícone
            
        Returns:
            True se atualizado com sucesso
        """
        try:
            session = self.get_session()
            tool = session.query(self.model).filter(self.model.id == tool_id).first()
            
            if tool:
                tool.icon_url = icon_url
                session.commit()
                LOGGER.info(f"Ícone atualizado para {tool.name}: {icon_url}")
                return True
            else:
                LOGGER.warning(f"Ferramenta {tool_id} não encontrada")
                return False
                
        except Exception as e:
            LOGGER.error(f"Erro ao atualizar favicon: {e}")
            session.rollback()
            return False
        finally:
            session.close()


    def fetch_and_update_all_favicons(self) -> int:
        """
        Busca e atualiza favicons de todas as ferramentas
        
        Returns:
            Número de favicons atualizados
        """
        from utils.favicon_fetcher import favicon_fetcher
        
        try:
            tools = self.get_all(limit=1000)
            updated_count = 0
            
            for tool in tools:
                if not tool.icon_url:  # Só buscar se não tiver ícone
                    LOGGER.info(f"Buscando favicon para: {tool.name}")
                    icon_url = favicon_fetcher.fetch_favicon_url(tool.url)
                    
                    if icon_url:
                        if self.update_favicon(tool.id, icon_url):
                            updated_count += 1
                            LOGGER.info(f"Favicon atualizado: {tool.name}")
                    
                    # Pequeno delay para não sobrecarregar
                    import time
                    time.sleep(0.5)
            
            LOGGER.info(f"Total de favicons atualizados: {updated_count}")
            return updated_count
            
        except Exception as e:
            LOGGER.error(f"Erro ao buscar favicons: {e}")
            return 0