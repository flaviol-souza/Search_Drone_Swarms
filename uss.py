# uss.py
from typing import Dict, Deque, Tuple, List, Optional
from collections import defaultdict, deque
from dataclasses import dataclass
from math import exp

# Tipos simples
RID = int

# Janela de retenção (segundos) para manter os eventos recentes no buffer
WINDOW_SEC = 120.0

@dataclass
class GSReport:
    t: float
    x: float
    y: float
    gs_name: str

@dataclass
class AntReport:
    t: float
    ant_id: int
    shape: str
    x_pub: float
    y_pub: float

class USS:
    """
    UAS Service Supplier (modelo simples):
    - Recebe do Ground Station: estimativas ruidosas no heartbeat (GSReport)
    - Recebe das Antenas: observações quando RID está sob cobertura (AntReport)
    - Expõe consultas básicas para HUD/logs
    (Cálculo do índice/gestão de procedência virá depois.)
    """
    def __init__(self, name: str = "USS-1", window_sec: float = WINDOW_SEC):
        self.name = name
        self.window_sec = float(window_sec)
        # Buffers por RID
        self.gs_reports: Dict[RID, Deque[GSReport]] = defaultdict(lambda: deque(maxlen=1000))
        self.ant_reports: Dict[RID, Deque[AntReport]] = defaultdict(lambda: deque(maxlen=2000))
        # Último t visto, por rid (ajuda na limpeza incremental)
        self._last_t: Dict[RID, float] = {}

    # ---------- Entrada de dados ----------
    def report_gs_estimate(self, *, rid: RID, t: float, x: float, y: float, gs_name: str):
        self.gs_reports[rid].append(GSReport(t=t, x=x, y=y, gs_name=gs_name))
        self._last_t[rid] = t
        self._prune(rid, t)

    def report_antenna_observation(self, *, rid: RID, t: float, ant_id: int, shape: str, x_pub: float, y_pub: float):
        self.ant_reports[rid].append(AntReport(t=t, ant_id=ant_id, shape=shape, x_pub=x_pub, y_pub=y_pub))
        self._last_t[rid] = t
        self._prune(rid, t)

    # ---------- Limpeza de janela ----------
    def _prune(self, rid: RID, t: float):
        """Remove eventos fora da janela para um RID específico."""
        w = self.window_sec
        dq_gs = self.gs_reports.get(rid)
        if dq_gs:
            while dq_gs and (t - dq_gs[0].t) > w:
                dq_gs.popleft()
        dq_ant = self.ant_reports.get(rid)
        if dq_ant:
            while dq_ant and (t - dq_ant[0].t) > w:
                dq_ant.popleft()

    # ---------- Consultas p/ HUD / depuração ----------
    def counts(self, rid: RID) -> Tuple[int, int]:
        """(n_gs, n_ant) observações recentes na janela."""
        return len(self.gs_reports.get(rid, ())), len(self.ant_reports.get(rid, ()))

    def last_gs(self, rid: RID) -> Optional[GSReport]:
        dq = self.gs_reports.get(rid)
        return dq[-1] if dq else None

    def last_ant(self, rid: RID) -> Optional[AntReport]:
        dq = self.ant_reports.get(rid)
        return dq[-1] if dq else None

    def rows_for_panel(self, max_rows: int = 12) -> List[Tuple[int, int, int]]:
        """
        Retorna linhas ordenadas por maior atividade: (rid, n_gs, n_ant)
        Útil p/ um painel simples enquanto o índice não é calculado.
        """
        rows: List[Tuple[int, int, int]] = []
        for rid in set(list(self.gs_reports.keys()) + list(self.ant_reports.keys())):
            n_gs, n_ant = self.counts(rid)
            rows.append((rid, n_gs, n_ant))
        rows.sort(key=lambda r: (-(r[1] + r[2]), r[0]))
        return rows[:max_rows]
