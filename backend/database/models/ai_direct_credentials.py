from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer
from database.models.base import BaseModel
from database.sqlalchemy_config import Base

class AIDirectCredentials(Base, BaseModel):
    """Credenciais Diretas - Versão Equilibrada (Crucial + Diferenciais)"""
    
    __tablename__ = "ai_direct_credentials"
    
    # CRUCIAL
    ai_tool_id = Column(String(36), ForeignKey("ai_tools.id"), nullable=False, unique=True)
    username = Column(Text, nullable=False)
    password = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # DIFERENCIAIS IMPORTANTES
    login_url = Column(Text, nullable=True)
    login_status = Column(String(20), default="pending")
    last_successful_login = Column(DateTime, nullable=True)
    
    # Controle de tentativas (evitar spam/bloqueio)
    failed_attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    
    # Seletores para automação (ESSENCIAIS)
    username_selector = Column(String(255), default="#email, #username, input[name='email'], input[name='username']")
    password_selector = Column(String(255), default="#password, input[name='password'], input[type='password']")
    submit_selector = Column(String(255), default="button[type='submit'], input[type='submit'], #login-button")
    
    def is_valid(self) -> bool:
        """Verifica se credenciais são válidas"""
        return (self.is_active and 
                bool(self.username and self.password) and 
                self.login_status != "blocked")
    
    def should_retry(self) -> bool:
        """Verifica se deve tentar login novamente"""
        return self.is_valid() and self.failed_attempts < self.max_attempts
    
    def mark_login_attempt(self, success: bool):
        """Marca tentativa de login"""
        now = datetime.now(timezone.utc)
        
        if success:
            self.last_successful_login = now
            self.failed_attempts = 0
            self.login_status = "active"
        else:
            self.failed_attempts += 1
            if self.failed_attempts >= self.max_attempts:
                self.login_status = "blocked"
            else:
                self.login_status = "failed"
    
    def reset_failed_attempts(self):
        """Reset contador de falhas"""
        self.failed_attempts = 0
        if self.login_status == "blocked":
            self.login_status = "pending"
