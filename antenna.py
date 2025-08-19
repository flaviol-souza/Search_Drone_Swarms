import pygame as pg
from dataclasses import dataclass
from typing import Tuple, Literal, Optional
from math import cos, sin, radians

vec2 = pg.math.Vector2
CoverageShape = Literal["circle", "ellipse", "cone"]

SHAPE_COLORS = {
    "circle": (0, 200, 0),     # verde
    "ellipse": (255, 165, 0),  # laranja
    "cone": (200, 0, 200)      # magenta
}

@dataclass
class Antenna:
    pos: vec2
    body_radius: int = 10  # raio físico do “mastro” (para colisão/obstáculo)
    shape: CoverageShape = "circle"
    size: Tuple[int, int] = (200, 200)  # circle: (r,r); ellipse: (rx,ry); cone: (length,width)
    orientation_deg: float = 0.0        # orientação (graus) para cone
    color: Optional[Tuple[int, int, int]] = None
    alpha: int = 50                     # transparência do campo

    # cache do desenho da cobertura
    _cov_surf: Optional[pg.Surface] = None
    _cov_rect: Optional[pg.Rect] = None

    def _ensure_color(self):
        if self.color is None:
            self.color = SHAPE_COLORS.get(self.shape, (0, 200, 255))

    def _build_cached_coverage(self):
        """Pré-renderiza a cobertura em uma surface pequena (bounding box) para acelerar o draw."""
        self._ensure_color()
        if self.shape == "circle":
            r = int(self.size[0])
            w = h = 2*r
            surf = pg.Surface((w, h), pg.SRCALPHA)
            pg.draw.circle(surf, (*self.color, self.alpha), (r, r), r, 0)
            rect = surf.get_rect(center=(int(self.pos.x), int(self.pos.y)))
        elif self.shape == "ellipse":
            rx, ry = self.size
            w, h = int(2*rx), int(2*ry)
            surf = pg.Surface((w, h), pg.SRCALPHA)
            pg.draw.ellipse(surf, (*self.color, self.alpha), pg.Rect(0, 0, w, h), 0)
            rect = surf.get_rect(center=(int(self.pos.x), int(self.pos.y)))
        else:  # cone
            length, width = self.size
            # bounding box aproximado para o triângulo
            w = int(max(length, width) * 1.2)
            h = int(max(length, width) * 1.2)
            surf = pg.Surface((w, h), pg.SRCALPHA)
            cx, cy = w // 2, h // 2
            ang = radians(self.orientation_deg)
            tip   = (cx, cy)
            left  = (cx + length*cos(ang) - width*sin(ang),
                     cy + length*sin(ang) + width*cos(ang))
            right = (cx + length*cos(ang) + width*sin(ang),
                     cy + length*sin(ang) - width*cos(ang))
            pg.draw.polygon(surf, (*self.color, self.alpha), [tip, left, right], 0)
            rect = surf.get_rect(center=(int(self.pos.x), int(self.pos.y)))
        self._cov_surf, self._cov_rect = surf, rect

    def set_params(self, *, pos: Tuple[float, float] = None, shape: CoverageShape = None,
                   size: Tuple[int, int] = None, orientation_deg: float = None,
                   body_radius: int = None, color: Tuple[int, int, int] = None, alpha: int = None):
        """Atualiza parâmetros e reconstrói o cache de cobertura."""
        changed = False
        if pos is not None:
            self.pos = vec2(pos[0], pos[1]); changed = True
        if shape is not None and shape != self.shape:
            self.shape = shape; changed = True
        if size is not None:
            self.size = size; changed = True
        if orientation_deg is not None:
            self.orientation_deg = orientation_deg; changed = True
        if body_radius is not None:
            self.body_radius = body_radius
        if color is not None:
            self.color = color; changed = True
        if alpha is not None:
            self.alpha = alpha; changed = True
        if changed or self._cov_surf is None:
            self._build_cached_coverage()

    def as_obstacle_point(self) -> vec2:
        return self.pos

    def draw(self, surface: pg.Surface) -> None:
        if self._cov_surf is None:
            self._build_cached_coverage()
        # blit cobertura
        surface.blit(self._cov_surf, self._cov_rect.topleft)
        # corpo da antena
        pg.draw.circle(surface, (60, 60, 60), (int(self.pos.x), int(self.pos.y)), self.body_radius)
        base_rect = pg.Rect(0, 0, int(self.body_radius*1.6), int(self.body_radius*0.6))
        base_rect.center = (int(self.pos.x), int(self.pos.y + self.body_radius + 6))
        pg.draw.rect(surface, (90, 90, 90), base_rect, border_radius=3)
        pg.draw.line(surface, (120, 120, 120),
                     (int(self.pos.x), int(self.pos.y)),
                     (int(self.pos.x), int(self.pos.y - self.body_radius*2)), 3)
        # ondas
        pg.draw.arc(surface, (0, 200, 255),
                    pg.Rect(int(self.pos.x - 24), int(self.pos.y - 24), 48, 48), 0.2, 1.2, 2)
        pg.draw.arc(surface, (0, 200, 255),
                    pg.Rect(int(self.pos.x - 36), int(self.pos.y - 36), 72, 72), 0.2, 1.2, 2)

    def contains_point(self, p: vec2) -> bool:
        dx = p.x - self.pos.x
        dy = p.y - self.pos.y
        if self.shape == "circle":
            r = float(self.size[0])
            return (dx*dx + dy*dy) <= (r*r)
        elif self.shape == "ellipse":
            rx, ry = float(self.size[0]), float(self.size[1])
            if rx <= 0 or ry <= 0:
                return False
            return (dx*dx)/(rx*rx) + (dy*dy)/(ry*ry) <= 1.0
        else:  # cone modelado como triângulo (tip, left, right)
            from math import cos, sin, radians
            length, width = self.size
            ang = radians(self.orientation_deg)
            tip   = vec2(self.pos.x, self.pos.y)
            left  = vec2(self.pos.x + length*cos(ang) - width*sin(ang),
                        self.pos.y + length*sin(ang) + width*cos(ang))
            right = vec2(self.pos.x + length*cos(ang) + width*sin(ang),
                        self.pos.y + length*sin(ang) - width*cos(ang))
            def sign(p1, p2, p3):
                return (p1.x - p3.x)*(p2.y - p3.y) - (p2.x - p3.x)*(p1.y - p3.y)
            b1 = sign(p, tip, left) < 0.0
            b2 = sign(p, left, right) < 0.0
            b3 = sign(p, right, tip) < 0.0
            return (b1 == b2) and (b2 == b3)
