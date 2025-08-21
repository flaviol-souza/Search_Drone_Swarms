# vci_tracker.py
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple
from collections import defaultdict, deque
from math import exp, sqrt

# Tipos
RID = int
AntennaID = int

# Pesos e parâmetros (ajuste depois, se quiser)
W_DIST = 0.6         # peso do termo geométrico (quão dentro da cobertura)
W_DYN = 0.4          # peso de coerência dinâmica (sem “teleporte”)
VMAX = 20.0          # m/s (limite físico simples p/ detectar saltos)
TAU = 15.0           # s (decay temporal na fusão)
WINDOW_SEC = 60.0    # janela deslizante p/ manter observações

SHAPE_WEIGHT = {"circle": 1.0, "ellipse": 1.1, "cone": 1.2}  # exemplo

@dataclass
class LocalObs:
    t: float
    vci: float
    ant_id: AntennaID
    shape: str

class VCITracker:
    """
    Mantém VCI_local por antena e VCI_fused por RID, com janela temporal e decaimento.
    """
    def __init__(self):
        self.local: Dict[RID, Deque[LocalObs]] = defaultdict(deque)
        self.fused: Dict[RID, float] = defaultdict(float)
        self.rvl: Dict[RID, int] = defaultdict(int)
        # para coerência dinâmica simples
        self._last_pub: Dict[RID, Tuple[float, float, float]] = {}  # rid -> (t, x, y)

    # ---------- APIs de alto nível ----------
    def observe(self, *, rid: RID, t: float, ant, pos_pub, pos_gt=None) -> float:
        """
        Registra uma observação (heartbeat dentro de cobertura) e já atualiza VCI_fused/RVL.
        Retorna o VCI_local calculado.
        """
        ant_id = getattr(ant, "ant_id", id(ant))
        shape = getattr(ant, "shape", "circle")
        vci_local = self.compute_local(rid=rid, t=t, pos_pub=pos_pub, ant=ant)
        self.push_local(rid=rid, t=t, vci=vci_local, ant_id=ant_id, shape=shape)
        self.fused[rid], self.rvl[rid] = self.fuse(rid=rid, t=t)
        return vci_local

    # ---------- Cálculo de VCI_local ----------
    def compute_local(self, *, rid: RID, t: float, pos_pub, ant) -> float:
        """VCI_local ∈ [0,1]: combina quão 'dentro' da cobertura + coerência dinâmica."""
        # 1) termo geométrico (0..1) — 1 no centro, cai até 0 na borda
        geom = self._geom_score(pos_pub, ant)

        # 2) termo dinâmico simples (0..1) — penaliza saltos > VMAX
        dyn = self._dyn_score(rid, t, pos_pub)

        # Combinação (clamp 0..1)
        vci = max(0.0, min(1.0, W_DIST * geom + W_DYN * dyn))
        return vci

    def _geom_score(self, pos, ant) -> float:
        """Score geométrico baseado na posição normalizada ao formato da cobertura."""
        dx = pos.x - ant.pos.x
        dy = pos.y - ant.pos.y
        if ant.shape == "circle":
            r = float(ant.size[0])
            d = sqrt((dx*dx + dy*dy)) / max(r, 1e-6)
            return max(0.0, 1.0 - d)  # 1 no centro, 0 na borda
        elif ant.shape == "ellipse":
            rx, ry = float(ant.size[0]), float(ant.size[1])
            n2 = (dx*dx)/(max(rx,1e-6)**2) + (dy*dy)/(max(ry,1e-6)**2)  # <=1 dentro
            d = sqrt(max(0.0, n2))
            return max(0.0, 1.0 - d)
        else:  # cone: usa distância ao tip ao longo do comprimento
            # aproximação: distância normalizada ao comprimento
            length = float(ant.size[0])
            d = sqrt(dx*dx + dy*dy) / max(length, 1e-6)
            return max(0.0, 1.0 - d)

    def _dyn_score(self, rid: RID, t: float, pos_pub) -> float:
        """Score 1.0 se velocidade plausível; cai se 'teleporte'."""
        last = self._last_pub.get(rid)
        self._last_pub[rid] = (t, pos_pub.x, pos_pub.y)
        if not last:
            return 0.7  # primeira amostra: neutro-positivo
        t0, x0, y0 = last
        dt = max(1e-6, t - t0)
        dist = sqrt((pos_pub.x - x0)**2 + (pos_pub.y - y0)**2)
        v = dist / dt
        if v <= VMAX:
            return 1.0
        # penaliza acima de VMAX
        overflow = min(3.0, (v - VMAX) / max(VMAX, 1e-6))
        return max(0.0, 1.0 - 0.5*overflow)

    # ---------- Buffer + Fusão ----------
    def push_local(self, *, rid: RID, t: float, vci: float, ant_id: AntennaID, shape: str):
        dq = self.local[rid]
        dq.append(LocalObs(t=t, vci=vci, ant_id=ant_id, shape=shape))
        # limpa janela
        while dq and (t - dq[0].t) > WINDOW_SEC:
            dq.popleft()

    def fuse(self, *, rid: RID, t: float) -> Tuple[float, int]:
        dq = self.local.get(rid, None)
        if not dq:
            return 0.0, 0

        num = 0.0
        den = 0.0
        ants = set()

        for obs in dq:
            decay = exp(-(t - obs.t) / max(TAU, 1e-6))
            w_shape = SHAPE_WEIGHT.get(obs.shape, 1.0)
            w = decay * w_shape
            num += obs.vci * w
            den += w
            ants.add(obs.ant_id)

        vci_fused = (num / den) if den > 0 else 0.0
        rvl = self._rvl_from_fused(vci_fused, len(ants))
        return vci_fused, rvl

    def _rvl_from_fused(self, vci_fused: float, n_ants: int) -> int:
        """Mapeia VCI_fused para RVL 0–5 com exigência mínima de diversidade."""
        if vci_fused < 0.2: return 0
        if vci_fused < 0.4: return 1
        if vci_fused < 0.6: return 2
        if vci_fused < 0.75: return 3
        if vci_fused < 0.9: return 4
        # nível 5 pede evidência + diversidade
        return 5 if n_ants >= 2 else 4

    # ---------- Suporte ao HUD ----------
    def panel_rows(self, max_rows: int = 12) -> List[Tuple[int, float, int, int]]:
        """
        Linhas ordenadas p/ HUD: (rid, vci_fused, rvl, n_antenas_ativas).
        """
        rows = []
        for rid, dq in self.local.items():
            if not dq:
                continue
            # reusa último t do rid
            t = dq[-1].t
            vf, rvl = self.fuse(rid=rid, t=t)
            n_ants = len({obs.ant_id for obs in dq})
            rows.append((rid, vf, rvl, n_ants))
        rows.sort(key=lambda r: (-r[1], r[0]))
        return rows[:max_rows]
