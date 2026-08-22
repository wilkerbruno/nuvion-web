"""Declarative base compartilhada por todos os modelos.

Equivalente a `Base = declarative_base()` de database/sqlalchemy_config.py
no projeto desktop.
"""
from sqlalchemy.orm import declarative_base

Base = declarative_base()
