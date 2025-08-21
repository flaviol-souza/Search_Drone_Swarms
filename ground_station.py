# ground_station.py
import pygame as pg
import numpy as np
from typing import Dict, Deque, Tuple, List
from collections import defaultdict, deque

vec2 = pg.math.Vector2

class GroundStation:
    """
    Estação fixa de comando/controle.
    - Mantém um conjunto de RIDs (drones) 'pertencentes'.
    - A cada heartbeat de um drone pertencente, registra uma estimativa ruidosa da posição.
    """
    def __init__(self, position: vec2, sigma_px: float = 8.0, name: str = "GS-1"):
        self.position = vec2(position.x, position.y)
        self.sigma_px = float(sigma_px)
        self.name = name
        self.managed_rids = set()  # RIDs sob este GS
        # armazenamento: rid -> deque[(t, est_x, est_y)]
        self.obs: Dict[int, Deque[Tuple[float, float, float]]] = defaultdict(lambda: deque(maxlen=300))

    def set_uss(self, uss):
        """Registra a instância do USS para notificar a cada heartbeat observado."""
        self.uss = uss

    def attach_drone(self, rid: int):
        self.managed_rids.add(int(rid))

    def attach_drones(self, rids: List[int]):
        for rid in rids:
            self.attach_drone(rid)

    def set_sigma(self, sigma_px: float):
        self.sigma_px = float(sigma_px)

    def relocate(self, position: vec2):
        """Reposiciona o GS (se necessário)."""
        self.position = vec2(position.x, position.y)

    def observe_heartbeat(self, *, rid: int, t: float, pos_gt: vec2):
        """
        Registra uma estimativa ruidosa da posição do RID no timestamp t.
        Apenas se o RID estiver sob este GS.
        """
        if rid not in self.managed_rids:
            return None  # ignora drones que não pertencem
        # ruído gaussiano (px)
        est_x = float(pos_gt.x + np.random.normal(0.0, self.sigma_px))
        est_y = float(pos_gt.y + np.random.normal(0.0, self.sigma_px))
        self.obs[rid].append((t, est_x, est_y))
        # notifica o USS (se houver)
        if hasattr(self, "uss") and self.uss is not None:
            self.uss.report_gs_estimate(
                rid=rid, t=t, x=est_x, y=est_y, gs_name=self.name
            )

        return vec2(est_x, est_y)

    # --------- (Opcional) desenho do GS no mapa ----------
    def draw(self, surface: pg.Surface):
        x, y = int(self.position.x), int(self.position.y)
        pg.draw.circle(surface, (30, 120, 200), (x, y), 10)       # nó central
        pg.draw.circle(surface, (30, 120, 200), (x, y), 18, 2)    # anel
        font = pg.font.SysFont(None, 18)
        surface.blit(font.render(self.name, True, (220, 220, 240)), (x + 10, y - 10))

    # --------- (Opcional) acesso rápido p/ HUD / logs ----------
    def last_estimate(self, rid: int):
        dq = self.obs.get(rid)
        return dq[-1] if dq else None
