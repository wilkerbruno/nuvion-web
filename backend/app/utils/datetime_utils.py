"""Utilitários de data/hora (equivalente reduzido de utils/datetime_utils.py).

Só porta o que os modelos atuais precisam (`safe_datetime_diff`, usado por
DeviceData.calculate_online_time). Se mais funções do utilitário original
forem necessárias em fases seguintes, portar sob demanda.
"""
from datetime import datetime, timezone


def safe_datetime_diff(start: datetime, end: datetime) -> int:
    """Diferença em segundos entre duas datas, tolerando datetimes "naive"
    (sem timezone) vindos do MySQL — assume UTC nesse caso."""
    if start is None or end is None:
        return 0

    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    return max(0, int((end - start).total_seconds()))
