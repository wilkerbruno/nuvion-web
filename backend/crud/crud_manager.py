# crud/crud_manager.py
"""
Sistema CRUD usando SQLAlchemy
Mantém compatibilidade com código existente
"""

# REMOVER imports antigos e usar apenas o novo
from crud.database_adapter import crud_system

# Exportar para compatibilidade
__all__ = ["crud_system"]

# NÃO FAZER ISSO:
# from crud.database_manager import DatabaseManager  ❌

# O código existente que importa crud_system continuará funcionando
