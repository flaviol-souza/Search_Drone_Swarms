import random
import pygame as pg
from typing import List, Tuple, Iterable, Dict
from antenna import Antenna, SHAPE_COLORS
from constants import RADIUS_TARGET

vec2 = pg.math.Vector2

class Obstacles(object):
    def __init__(self, num_of_obstacles: int, map_size: Tuple[int, int]):
        super().__init__()
        self.num_of_obstacles = num_of_obstacles
        self.map_size = map_size
        self.antennas: List[Antenna] = []
        self.obst: List[vec2] = []  # legado: posições para avoidance
        self.seed = random.seed(0)

    def _random_shape(self):
        shapes = ["circle", "ellipse", "cone"]
        s = random.choice(shapes)
        if s == "circle":
            r = random.randint(120, 280)
            return s, (r, r), 0.0
        if s == "ellipse":
            rx = random.randint(120, 280)
            ry = random.randint(80, 220)
            return s, (rx, ry), 0.0
        # cone
        length = random.randint(180, 360)
        width  = random.randint(60, 160)
        heading = random.uniform(0, 360)
        return "cone", (length, width), heading

    def generate_obstacles(self):
        self.antennas.clear()
        self.obst.clear()
        margin = int(RADIUS_TARGET) if isinstance(RADIUS_TARGET, (int, float)) else 130
        for _ in range(self.num_of_obstacles):
            x = random.uniform(margin, self.map_size[0] - margin)
            y = random.uniform(margin, self.map_size[1] - margin)
            shape, size, heading = self._random_shape()
            color = SHAPE_COLORS.get(shape)
            ant = Antenna(pos=vec2(x, y), body_radius=12, shape=shape, size=size,
                          orientation_deg=heading, color=color, alpha=50)
            ant.set_params()  # assegura cache
            ant.ant_id = len(self.antennas) + 1
            self.antennas.append(ant)
            self.obst.append(ant.as_obstacle_point())

    def set_antennas(self, configs: Iterable[Dict]):
        """Define antenas manualmente.
        Cada item de configs pode conter: x, y, shape, size, orientation_deg, body_radius, color, alpha.
        shape ∈ {"circle","ellipse","cone"}. Se color não for informado, usa a cor padrão por formato.
        """
        self.antennas.clear()
        self.obst.clear()
        for cfg in configs:
            if 'x' not in cfg or 'y' not in cfg:
                continue
            shape = cfg.get('shape', 'circle')
            color = cfg.get('color', SHAPE_COLORS.get(shape))
            ant = Antenna(
                pos=vec2(float(cfg['x']), float(cfg['y'])),
                body_radius=int(cfg.get('body_radius', 12)),
                shape=shape,
                size=tuple(cfg.get('size', (200, 200))),
                orientation_deg=float(cfg.get('orientation_deg', 0.0)),
                color=color,
                alpha=int(cfg.get('alpha', 50)),
            )
            ant.set_params()  # pré-render cache
            self.antennas.append(ant)
            self.obst.append(ant.as_obstacle_point())

    def get_coordenates(self):
        return self.obst

    def reset_seed(self):
        self.seed = random.seed(0)

    def render_at(self, surface: pg.Surface, pos: vec2):
        for ant in self.antennas:
            if abs(ant.pos.x - pos.x) < 1e-3 and abs(ant.pos.y - pos.y) < 1e-3:
                ant.draw(surface)
                return
        pg.draw.circle(surface, (200, 0, 0), (int(pos.x), int(pos.y)), 5)

    def coverage_contains(self, p: vec2):
        """Retorna (hit: bool, antenna or None)."""
        for ant in self.antennas:
            if ant.contains_point(p):
                return True, ant
        return False, None
