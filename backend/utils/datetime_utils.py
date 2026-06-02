from datetime import datetime, timezone, timedelta
import logging

LOGGER = logging.getLogger(__name__)

# Configurar timezone BR (UTC-3)
BR_TIMEZONE = timezone(timedelta(hours=-3))


def normalize_datetime(dt):
    """Normaliza datetime para UTC timezone-aware"""
    if dt is None:
        return None
    
    try:
        # Se já tem timezone
        if dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None:
            # Converter para UTC
            return dt.astimezone(timezone.utc)
        
        # Se é naive (sem timezone), assumir que está em UTC e adicionar timezone
        return dt.replace(tzinfo=timezone.utc)
        
    except Exception as e:
        LOGGER.error(f"Erro ao normalizar datetime {dt}: {e}")
        # Em caso de erro, retornar datetime atual em UTC
        return datetime.now(timezone.utc)


def to_local_datetime(dt, local_tz=BR_TIMEZONE):
    """Converte datetime UTC para timezone local (padrão: Brasil UTC-3)."""
    if dt is None:
        return None
    
    try:
        # Normalizar para UTC primeiro
        dt_utc = normalize_datetime(dt)
        
        # Converter para timezone local
        dt_local = dt_utc.astimezone(local_tz)
        
        return dt_local
        
    except Exception as e:
        LOGGER.error(f"Erro ao converter para timezone local: {e}")
        return dt


def format_datetime_local(dt, format_str="%d/%m/%Y %H:%M:%S"):
    """Formata datetime convertendo para timezone local"""
    if dt is None:
        return "N/A"
    
    try:
        dt_local = to_local_datetime(dt)
        return dt_local.strftime(format_str)
    except Exception as e:
        LOGGER.error(f"Erro ao formatar datetime local: {e}")
        return "N/A"


def safe_datetime_diff(start_dt, end_dt=None):
    """Calcula diferença entre datetimes de forma segura"""
    try:
        # Normalizar start_dt
        start_normalized = normalize_datetime(start_dt)
        if start_normalized is None:
            return 0

        # Normalizar end_dt (usar agora se None)
        if end_dt is None:
            end_normalized = datetime.now(timezone.utc)
        else:
            end_normalized = normalize_datetime(end_dt)
            if end_normalized is None:
                end_normalized = datetime.now(timezone.utc)

        # Calcular diferença
        time_diff = end_normalized - start_normalized
        return int(time_diff.total_seconds())

    except Exception as e:
        LOGGER.error(f"Erro ao calcular diferença de tempo: {e}")
        return 0


def get_current_utc():
    """Retorna datetime atual em UTC timezone-aware"""
    return datetime.now(timezone.utc)


def get_current_local():
    """Retorna datetime atual no timezone local do Brasil (UTC-3)"""
    try:
        utc_now = datetime.now(timezone.utc)
        return to_local_datetime(utc_now)
    except Exception as e:
        LOGGER.error(f"Erro ao obter datetime local: {e}")
        return datetime.now()


def format_time_difference(seconds):
    """Formata diferença de tempo em formato legível"""
    if seconds <= 0:
        return "0m"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def safe_datetime_comparison(dt1, dt2, operation="<"):
    """Compara dois datetimes de forma segura, normalizando ambos para UTC."""
    try:
        # Normalizar ambos os datetimes
        dt1_normalized = normalize_datetime(dt1)
        dt2_normalized = normalize_datetime(dt2)
        
        if dt1_normalized is None or dt2_normalized is None:
            return False
        
        # Realizar comparação
        if operation == "<":
            return dt1_normalized < dt2_normalized
        elif operation == ">":
            return dt1_normalized > dt2_normalized
        elif operation == "<=":
            return dt1_normalized <= dt2_normalized
        elif operation == ">=":
            return dt1_normalized >= dt2_normalized
        elif operation == "==":
            return dt1_normalized == dt2_normalized
        elif operation == "!=":
            return dt1_normalized != dt2_normalized
        else:
            LOGGER.error(f"Operação de comparação inválida: {operation}")
            return False
            
    except Exception as e:
        LOGGER.error(f"Erro ao comparar datetimes: {e}")
        return False