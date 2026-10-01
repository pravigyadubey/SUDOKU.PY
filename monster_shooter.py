import math
import random
import time
import tkinter as tk
from dataclasses import dataclass, field


WIDTH = 1040
HEIGHT = 680
ARENA_RIGHT = 780
ARENA_TOP = 58
ARENA_BOTTOM = HEIGHT - 16


@dataclass(frozen=True)
class Weapon:
    name: str
    color: str
    damage: float
    cooldown: float
    speed: float
    pellets: int
    spread: float
    ammo_per_pickup: int | None
    pierce: int = 0
    blast_radius: float = 0


WEAPONS = {
    "Pistol": Weapon("Pistol", "#f3cb70", 25, 0.30, 690, 1, 0.025, 0),
    "Shotgun": Weapon("Shotgun", "#ff975e", 17, 0.72, 570, 6, 0.42, 18),
    "SMG": Weapon("SMG", "#76e7c1", 11, 0.105, 760, 1, 0.12, 50),
    "Railgun": Weapon("Railgun", "#78b9ff", 92, 0.95, 1050, 1, 0.015, 5, 2),
    "RPG": Weapon("RPG", "#f28b55", 76, 0.82, 440, 1, 0.012, None, blast_radius=76),
}

WEAPON_ORDER = ("Pistol", "Shotgun", "SMG", "Railgun", "RPG")
ENEMY_TYPES = {
    "Crawler": {"hp": 42, "speed": 78, "damage": 9, "radius": 13, "color": "#cb665d", "score": 10},
    "Runner": {"hp": 28, "speed": 132, "damage": 7, "radius": 11, "color": "#e7a154", "score": 15},
    "Brute": {"hp": 145, "speed": 47, "damage": 18, "radius": 20, "color": "#9c668d", "score": 35},
}


@dataclass
class Enemy:
    x: float
    y: float
    kind: str
    hp: float
    speed: float
    damage: float
    radius: float
    color: str
    score: int
    hit_cooldown: float = 0


@dataclass
class Bullet:
    x: float
    y: float
    vx: float
    vy: float
    damage: float
    color: str
    pierce: int
    blast_radius: float = 0
    hit_enemies: set[int] = field(default_factory=set)


@dataclass
class Explosion:
    x: float
    y: float
    radius: float
    age: float = 0
    duration: float = 0.24


@dataclass
class Pickup:
    x: float
    y: float
    kind: str
    value: str | int
    age: float = 0


class MonsterShooter:
    COLORS = {
        "bg": "#111b1a",
        "floor": "#172422",
        "grid": "#20312e",
        "panel": "#202d2a",
        "text": "#e4eee5",
        "muted": "#92a59a",
        "mint": "#80e3bb",
        "red": "#ee756a",
    }

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("LAST LIGHT | Monster Shooter")
        self.root.resizable(False, False)
        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg=self.COLORS["bg"], highlightthickness=0)
        self.canvas.pack()
        self.canvas.focus_set()
        self.keys: set[str] = set()
        self.mouse_x = ARENA_RIGHT / 2
        self.mouse_y = HEIGHT / 2
        self.firing = False
        self.last_shot = 0.0
        self.last_time = time.perf_counter()
        self.elapsed = 0.0
        self._draw_static_scene()
        self._bind_controls()
        self.restart()
        self.root.after(16, self._tick)

    def _bind_controls(self) -> None:
        self.root.bind("<KeyPress>", self._key_down)
        self.root.bind("<KeyRelease>", self._key_up)
        self.canvas.bind("<Motion>", self._aim)
        self.canvas.bind("<ButtonPress-1>", self._mouse_down)
        self.canvas.bind("<ButtonRelease-1>", self._mouse_up)
        self.canvas.bind("<Leave>", self._mouse_up)

    def _draw_static_scene(self) -> None:
        self.canvas.create_rectangle(0, 0, ARENA_RIGHT, HEIGHT, fill=self.COLORS["floor"], outline="", tags="static")
        for x in range(0, ARENA_RIGHT, 42):
            self.canvas.create_line(x, ARENA_TOP, x, HEIGHT, fill=self.COLORS["grid"], tags="static")
        for y in range(ARENA_TOP, HEIGHT, 42):
            self.canvas.create_line(0, y, ARENA_RIGHT, y, fill=self.COLORS["grid"], tags="static")
        decoration_random = random.Random(16)
        for _ in range(80):
            x = decoration_random.randint(12, ARENA_RIGHT - 12)
            y = decoration_random.randint(ARENA_TOP + 8, HEIGHT - 10)
            size = decoration_random.randint(2, 5)
            self.canvas.create_oval(x, y, x + size, y + size, fill="#2a3b36", outline="", tags="static")
        self.canvas.create_rectangle(0, 0, ARENA_RIGHT, ARENA_TOP, fill="#202d2a", outline="", tags="static")
        self.canvas.create_text(22, 18, anchor="w", text="LAST LIGHT", fill=self.COLORS["mint"], font=("Segoe UI", 15, "bold"), tags="static")
        self.canvas.create_text(22, 41, anchor="w", text="NIGHT SHIFT  /  HOLD THE LINE", fill=self.COLORS["muted"], font=("Segoe UI", 8, "bold"), tags="static")
        self.canvas.create_rectangle(ARENA_RIGHT, 0, WIDTH, HEIGHT, fill=self.COLORS["panel"], outline="", tags="static")
        self.canvas.create_line(ARENA_RIGHT, 0, ARENA_RIGHT, HEIGHT, fill="#40534b", width=2, tags="static")

    def restart(self) -> None:
        self.player_x = ARENA_RIGHT / 2
        self.player_y = HEIGHT / 2 + 25
        self.health = 100.0
        self.invulnerable = 0.0
        self.weapons: dict[str, int | None] = {"Pistol": None}
        self.active_weapon = "Pistol"
        self.enemies: list[Enemy] = []
        self.bullets: list[Bullet] = []
        self.explosions: list[Explosion] = []
        self.pickups: list[Pickup] = []
        self.wave = 1
        self.score = 0
        self.kills = 0
        self.spawn_left = 0
        self.spawn_timer = 0.0
        self.intermission = 0.0
        self.game_over = False
        self.auto_fire = False
        self.message = "WASD to move   /   Mouse to aim + fire"
        self.message_timer = 4.0
        self._start_wave()
        self._render()

    def _start_wave(self) -> None:
        self.spawn_left = 4 + self.wave * 2
        self.spawn_timer = 0.5
        self.intermission = 0.0
        self.message = f"WAVE {self.wave}   INCOMING"
        self.message_timer = 2.0

    def _key_down(self, event: tk.Event) -> None:
        key = event.keysym.lower()
        already_down = key in self.keys
        self.keys.add(key)
        if key == "q" and not already_down and not self.game_over:
            self.auto_fire = not self.auto_fire
            self.message = f"AUTO FIRE {'ON' if self.auto_fire else 'OFF'}"
            self.message_timer = 1.5
        elif key == "r" and self.game_over:
            self.restart()
        elif key in ("1", "2", "3", "4", "5"):
            weapon = WEAPON_ORDER[int(key) - 1]
            if weapon in self.weapons:
                self.active_weapon = weapon

    def _key_up(self, event: tk.Event) -> None:
        self.keys.discard(event.keysym.lower())

    def _aim(self, event: tk.Event) -> None:
        self.mouse_x = event.x
        self.mouse_y = event.y

    def _mouse_down(self, event: tk.Event) -> None:
        self._aim(event)
        self.firing = True

    def _mouse_up(self, _event: tk.Event) -> None:
        self.firing = False

    def _spawn_enemy(self) -> None:
        side = random.randrange(4)
        if side == 0:
            x, y = random.randint(20, ARENA_RIGHT - 20), ARENA_TOP + 82
        elif side == 1:
            x, y = random.randint(20, ARENA_RIGHT - 20), ARENA_BOTTOM - 15
        elif side == 2:
            x, y = 16, random.randint(ARENA_TOP + 80, ARENA_BOTTOM - 18)
        else:
            x, y = ARENA_RIGHT - 16, random.randint(ARENA_TOP + 80, ARENA_BOTTOM - 18)

        available = ["Crawler", "Runner"]
        if self.wave >= 2:
            available.append("Brute")
        kind = random.choice(available)
        stats = ENEMY_TYPES[kind]
        scale = 1 + (self.wave - 1) * 0.09
        self.enemies.append(Enemy(
            x=x, y=y, kind=kind, hp=stats["hp"] * scale,
            speed=stats["speed"] * min(1.5, scale), damage=stats["damage"],
            radius=stats["radius"], color=stats["color"], score=stats["score"],
        ))

    def _fire(self) -> None:
        weapon = WEAPONS[self.active_weapon]
        ammo = self.weapons[self.active_weapon]
        if ammo is not None and ammo <= 0:
            self.message = "OUT OF AMMO  /  FIND AN AMMO CRATE"
            self.message_timer = 1.2
            return

        angle = math.atan2(self.mouse_y - self.player_y, self.mouse_x - self.player_x)
        muzzle_x = self.player_x + math.cos(angle) * 23
        muzzle_y = self.player_y + math.sin(angle) * 23
        for _ in range(weapon.pellets):
            shot_angle = angle + random.uniform(-weapon.spread, weapon.spread)
            self.bullets.append(Bullet(
                muzzle_x, muzzle_y,
                math.cos(shot_angle) * weapon.speed,
                math.sin(shot_angle) * weapon.speed,
                weapon.damage, weapon.color, weapon.pierce, weapon.blast_radius,
            ))
        if ammo is not None:
            self.weapons[self.active_weapon] -= 1
        self.last_shot = self.elapsed

    def _move_player(self, dt: float) -> None:
        dx = float("d" in self.keys or "right" in self.keys) - float("a" in self.keys or "left" in self.keys)
        dy = float("s" in self.keys or "down" in self.keys) - float("w" in self.keys or "up" in self.keys)
        magnitude = math.hypot(dx, dy)
        if magnitude:
            speed = 245 * dt / magnitude
            self.player_x += dx * speed
            self.player_y += dy * speed
        self.player_x = min(ARENA_RIGHT - 20, max(20, self.player_x))
        self.player_y = min(ARENA_BOTTOM - 20, max(ARENA_TOP + 25, self.player_y))

    def _update_bullets(self, dt: float) -> None:
        remaining: list[Bullet] = []
        for bullet in self.bullets:
            bullet.x += bullet.vx * dt
            bullet.y += bullet.vy * dt
            if not (0 <= bullet.x <= ARENA_RIGHT and ARENA_TOP <= bullet.y <= HEIGHT):
                continue
            consumed = False
            for enemy in self.enemies:
                identity = id(enemy)
                if identity in bullet.hit_enemies:
                    continue
                if math.hypot(enemy.x - bullet.x, enemy.y - bullet.y) <= enemy.radius + 4:
                    bullet.hit_enemies.add(identity)
                    if bullet.blast_radius:
                        for blast_enemy in self.enemies:
                            distance = math.hypot(blast_enemy.x - bullet.x, blast_enemy.y - bullet.y)
                            if distance <= bullet.blast_radius + blast_enemy.radius:
                                was_alive = blast_enemy.hp > 0
                                blast_enemy.hp -= bullet.damage
                                if was_alive and blast_enemy.hp <= 0:
                                    self.score += blast_enemy.score
                                    self.kills += 1
                        self.explosions.append(Explosion(bullet.x, bullet.y, bullet.blast_radius))
                        consumed = True
                    else:
                        was_alive = enemy.hp > 0
                        enemy.hp -= bullet.damage
                        if bullet.pierce:
                            bullet.pierce -= 1
                        else:
                            consumed = True
                        if was_alive and enemy.hp <= 0:
                            self.score += enemy.score
                            self.kills += 1
                    break
            if not consumed:
                remaining.append(bullet)
        self.bullets = remaining
        self.enemies = [enemy for enemy in self.enemies if enemy.hp > 0]

    def _update_explosions(self, dt: float) -> None:
        for explosion in self.explosions:
            explosion.age += dt
        self.explosions = [explosion for explosion in self.explosions if explosion.age < explosion.duration]

    def _update_enemies(self, dt: float) -> None:
        for enemy in self.enemies:
            dx = self.player_x - enemy.x
            dy = self.player_y - enemy.y
            distance = max(1, math.hypot(dx, dy))
            if distance > enemy.radius + 17:
                enemy.x += dx / distance * enemy.speed * dt
                enemy.y += dy / distance * enemy.speed * dt
            enemy.hit_cooldown = max(0, enemy.hit_cooldown - dt)
            if distance <= enemy.radius + 17 and enemy.hit_cooldown == 0 and self.invulnerable == 0:
                self.health -= enemy.damage
                self.invulnerable = 0.65
                enemy.hit_cooldown = 0.7
                self.message = "HIT! KEEP MOVING"
                self.message_timer = 0.8
                if self.health <= 0:
                    self.health = 0
                    self.game_over = True
                    self.firing = False

    def _drop_pickup(self, x: float, y: float, guaranteed: bool = False) -> None:
        if guaranteed or random.random() < 0.18:
            available = [name for name in WEAPON_ORDER[1:] if name not in self.weapons]
            if available:
                self.pickups.append(Pickup(x, y, "weapon", random.choice(available)))
                return
        if guaranteed or random.random() < 0.25:
            ammo_weapons = [name for name in WEAPON_ORDER[1:] if WEAPONS[name].ammo_per_pickup is not None]
            self.pickups.append(Pickup(x, y, "ammo", random.choice(ammo_weapons)))
        elif random.random() < 0.16:
            self.pickups.append(Pickup(x, y, "health", 28))

    def _update_pickups(self, dt: float) -> None:
        kept: list[Pickup] = []
        for pickup in self.pickups:
            pickup.age += dt
            if math.hypot(pickup.x - self.player_x, pickup.y - self.player_y) < 30:
                if pickup.kind == "weapon":
                    weapon_name = str(pickup.value)
                    pickup_ammo = WEAPONS[weapon_name].ammo_per_pickup
                    if weapon_name in self.weapons:
                        ammo = self.weapons[weapon_name]
                        self.weapons[weapon_name] = None if ammo is None or pickup_ammo is None else ammo + pickup_ammo
                    else:
                        self.weapons[weapon_name] = pickup_ammo
                    self.active_weapon = weapon_name
                    self.message = f"{weapon_name.upper()} COLLECTED  /  PRESS {WEAPON_ORDER.index(weapon_name) + 1} TO SWITCH"
                elif pickup.kind == "ammo":
                    weapon_name = str(pickup.value)
                    pickup_ammo = WEAPONS[weapon_name].ammo_per_pickup
                    if pickup_ammo is None:
                        self.weapons[weapon_name] = None
                        self.active_weapon = weapon_name
                        self.message = f"{weapon_name.upper()} HAS INFINITE AMMO"
                        self.message_timer = 2.0
                        continue
                    if weapon_name not in self.weapons:
                        self.weapons[weapon_name] = 0
                    self.weapons[weapon_name] = (self.weapons[weapon_name] or 0) + pickup_ammo
                    self.message = f"{weapon_name.upper()} AMMO COLLECTED"
                else:
                    self.health = min(100, self.health + int(pickup.value))
                    self.message = "MED KIT COLLECTED"
                self.message_timer = 2.0
                continue
            kept.append(pickup)
        self.pickups = kept

    def _update_waves(self, dt: float) -> None:
        if self.spawn_left:
            self.spawn_timer -= dt
            if self.spawn_timer <= 0:
                self._spawn_enemy()
                self.spawn_left -= 1
                self.spawn_timer = max(0.38, 1.0 - self.wave * 0.035)
        elif not self.enemies and self.intermission == 0:
            self.score += self.wave * 25
            self.message = f"WAVE {self.wave} CLEARED  /  SUPPLIES DROPPED"
            self.message_timer = 3.2
            self._drop_pickup(random.randint(100, ARENA_RIGHT - 100), random.randint(ARENA_TOP + 100, ARENA_BOTTOM - 60), True)
            self._drop_pickup(random.randint(100, ARENA_RIGHT - 100), random.randint(ARENA_TOP + 100, ARENA_BOTTOM - 60), True)
            self.intermission = 5.0
        elif self.intermission > 0:
            self.intermission = max(0, self.intermission - dt)
            if self.intermission == 0:
                self.wave += 1
                self._start_wave()

    def _tick(self) -> None:
        now = time.perf_counter()
        dt = min(0.04, now - self.last_time)
        self.last_time = now
        self.elapsed += dt
        self.invulnerable = max(0, self.invulnerable - dt)
        self.message_timer = max(0, self.message_timer - dt)

        if not self.game_over:
            self._move_player(dt)
            if (self.firing or self.auto_fire) and self.mouse_x < ARENA_RIGHT and self.elapsed - self.last_shot >= WEAPONS[self.active_weapon].cooldown:
                self._fire()
            self._update_bullets(dt)
            self._update_explosions(dt)
            self._update_enemies(dt)
            self._update_pickups(dt)
            self._update_waves(dt)

        self._render()
        self.root.after(16, self._tick)

    def _draw_enemy(self, enemy: Enemy) -> None:
        x, y, radius = enemy.x, enemy.y, enemy.radius
        self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=enemy.color, outline="#f0b3a1", width=1, tags="dynamic")
        self.canvas.create_oval(x - radius * 0.52, y - radius * 0.15, x - radius * 0.19, y + radius * 0.1, fill="#f9dc9d", outline="", tags="dynamic")
        self.canvas.create_oval(x + radius * 0.19, y - radius * 0.15, x + radius * 0.52, y + radius * 0.1, fill="#f9dc9d", outline="", tags="dynamic")
        if enemy.hp < (ENEMY_TYPES[enemy.kind]["hp"] * (1 + (self.wave - 1) * 0.09)):
            width = radius * 2
            self.canvas.create_rectangle(x - radius, y - radius - 8, x + radius, y - radius - 5, fill="#442c2c", outline="", tags="dynamic")
            self.canvas.create_rectangle(x - radius, y - radius - 8, x - radius + width * max(0, enemy.hp) / (ENEMY_TYPES[enemy.kind]["hp"] * (1 + (self.wave - 1) * 0.09)), y - radius - 5, fill="#83dfaa", outline="", tags="dynamic")

    def _draw_player(self) -> None:
        angle = math.atan2(self.mouse_y - self.player_y, self.mouse_x - self.player_x)
        x, y = self.player_x, self.player_y
        if self.invulnerable <= 0 or int(self.elapsed * 15) % 2 == 0:
            self.canvas.create_oval(x - 15, y - 15, x + 15, y + 15, fill="#47bfa4", outline="#b4f6d8", width=2, tags="dynamic")
            self.canvas.create_oval(x - 6, y - 7, x + 7, y + 6, fill="#d5f7e5", outline="", tags="dynamic")
            self.canvas.create_line(x, y, x + math.cos(angle) * 26, y + math.sin(angle) * 26, fill=WEAPONS[self.active_weapon].color, width=6, capstyle="round", tags="dynamic")

    def _draw_pickup(self, pickup: Pickup) -> None:
        bob = math.sin(pickup.age * 4) * 3
        x, y = pickup.x, pickup.y + bob
        if pickup.kind == "weapon":
            color = WEAPONS[str(pickup.value)].color
            self.canvas.create_rectangle(x - 12, y - 12, x + 12, y + 12, fill="#263b38", outline=color, width=2, tags="dynamic")
            self.canvas.create_text(x, y, text="+", fill=color, font=("Segoe UI", 15, "bold"), tags="dynamic")
            self.canvas.create_text(x, y + 20, text=str(pickup.value).upper(), fill=color, font=("Segoe UI", 7, "bold"), tags="dynamic")
        else:
            color, symbol = ("#91d57e", "+") if pickup.kind == "health" else ("#f0ce76", "A")
            self.canvas.create_oval(x - 11, y - 11, x + 11, y + 11, fill="#263b38", outline=color, width=2, tags="dynamic")
            self.canvas.create_text(x, y, text=symbol, fill=color, font=("Segoe UI", 10, "bold"), tags="dynamic")

    def _draw_explosion(self, explosion: Explosion) -> None:
        progress = explosion.age / explosion.duration
        radius = explosion.radius * progress
        self.canvas.create_oval(
            explosion.x - radius, explosion.y - radius,
            explosion.x + radius, explosion.y + radius,
            outline="#f28b55", width=max(1, int(7 * (1 - progress))), tags="dynamic",
        )
        inner_radius = radius * 0.55
        self.canvas.create_oval(
            explosion.x - inner_radius, explosion.y - inner_radius,
            explosion.x + inner_radius, explosion.y + inner_radius,
            outline="#ffd17e", width=max(1, int(5 * (1 - progress))), tags="dynamic",
        )

    def _draw_sidebar(self) -> None:
        x0 = ARENA_RIGHT + 22
        self.canvas.create_text(x0, 26, anchor="w", text="FIELD REPORT", fill=self.COLORS["muted"], font=("Segoe UI", 9, "bold"), tags="dynamic")
        self.canvas.create_text(x0, 64, anchor="w", text=f"WAVE  {self.wave:02d}", fill=self.COLORS["text"], font=("Segoe UI", 22, "bold"), tags="dynamic")
        self.canvas.create_text(x0, 99, anchor="w", text=f"SCORE  {self.score:06d}", fill=self.COLORS["mint"], font=("Segoe UI", 11, "bold"), tags="dynamic")
        self.canvas.create_text(x0, 143, anchor="w", text="VITALS", fill=self.COLORS["muted"], font=("Segoe UI", 8, "bold"), tags="dynamic")
        self.canvas.create_rectangle(x0, 157, WIDTH - 22, 168, fill="#3c4a44", outline="", tags="dynamic")
        health_width = (WIDTH - 22 - x0) * self.health / 100
        health_color = "#76d49c" if self.health > 45 else "#e6a35f" if self.health > 20 else self.COLORS["red"]
        self.canvas.create_rectangle(x0, 157, x0 + health_width, 168, fill=health_color, outline="", tags="dynamic")
        self.canvas.create_text(x0, 182, anchor="w", text=f"{int(self.health)} / 100", fill=self.COLORS["text"], font=("Segoe UI", 9), tags="dynamic")
        self.canvas.create_line(x0, 204, WIDTH - 20, 204, fill="#40534b", tags="dynamic")
        self.canvas.create_text(x0, 226, anchor="w", text="ARMORY", fill=self.COLORS["muted"], font=("Segoe UI", 8, "bold"), tags="dynamic")

        y = 255
        for index, weapon_name in enumerate(WEAPON_ORDER, start=1):
            owned = weapon_name in self.weapons
            active = weapon_name == self.active_weapon
            color = WEAPONS[weapon_name].color if owned else "#66756d"
            label = f"{index}   {weapon_name}" if owned else f"{index}   LOCKED"
            if active:
                self.canvas.create_rectangle(x0 - 8, y - 16, WIDTH - 12, y + 18, fill="#30443c", outline="", tags="dynamic")
            self.canvas.create_text(x0, y, anchor="w", text=label, fill=color, font=("Segoe UI", 10, "bold" if active else "normal"), tags="dynamic")
            if owned:
                ammo = self.weapons[weapon_name]
                ammo_text = "INF" if ammo is None else str(ammo)
                self.canvas.create_text(WIDTH - 24, y, anchor="e", text=ammo_text, fill=color, font=("Consolas", 10, "bold"), tags="dynamic")
            y += 38

        self.canvas.create_line(x0, 443, WIDTH - 20, 443, fill="#40534b", tags="dynamic")
        self.canvas.create_text(x0, 463, anchor="w", text="THREATS REMOVED", fill=self.COLORS["muted"], font=("Segoe UI", 8, "bold"), tags="dynamic")
        self.canvas.create_text(x0, 492, anchor="w", text=f"{self.kills:03d}", fill=self.COLORS["text"], font=("Segoe UI", 25, "bold"), tags="dynamic")
        self.canvas.create_line(x0, 521, WIDTH - 20, 521, fill="#40534b", tags="dynamic")
        controls = (
            "WASD / ARROWS   MOVE",
            "MOUSE   AIM + FIRE",
            f"Q   AUTO FIRE: {'ON' if self.auto_fire else 'OFF'}",
            "1 - 5 GUNS  /  R RESTART",
        )
        for index, line in enumerate(controls):
            color = self.COLORS["mint"] if index == 2 and self.auto_fire else self.COLORS["muted"]
            self.canvas.create_text(x0, 544 + index * 23, anchor="w", text=line, fill=color, font=("Segoe UI", 8, "bold"), tags="dynamic")

    def _render(self) -> None:
        self.canvas.delete("dynamic")
        for explosion in self.explosions:
            self._draw_explosion(explosion)
        for pickup in self.pickups:
            self._draw_pickup(pickup)
        for bullet in self.bullets:
            if bullet.blast_radius:
                direction = math.atan2(bullet.vy, bullet.vx)
                tail_x = bullet.x - math.cos(direction) * 12
                tail_y = bullet.y - math.sin(direction) * 12
                self.canvas.create_line(tail_x, tail_y, bullet.x, bullet.y, fill=bullet.color, width=5, capstyle="round", tags="dynamic")
            else:
                self.canvas.create_oval(bullet.x - 4, bullet.y - 4, bullet.x + 4, bullet.y + 4, fill=bullet.color, outline="", tags="dynamic")
        for enemy in self.enemies:
            self._draw_enemy(enemy)
        self._draw_player()
        self._draw_sidebar()

        if self.message_timer > 0 and not self.game_over:
            self.canvas.create_text(ARENA_RIGHT / 2, ARENA_TOP + 30, text=self.message, fill=self.COLORS["mint"], font=("Segoe UI", 11, "bold"), tags="dynamic")
        if self.game_over:
            self.canvas.create_rectangle(0, 0, ARENA_RIGHT, HEIGHT, fill="#0b1211", stipple="gray50", outline="", tags="dynamic")
            self.canvas.create_text(ARENA_RIGHT / 2, HEIGHT / 2 - 32, text="YOU WERE OVERRUN", fill="#f08472", font=("Segoe UI", 25, "bold"), tags="dynamic")
            self.canvas.create_text(ARENA_RIGHT / 2, HEIGHT / 2 + 10, text=f"WAVE {self.wave}     SCORE {self.score:06d}", fill=self.COLORS["text"], font=("Segoe UI", 12, "bold"), tags="dynamic")
            self.canvas.create_text(ARENA_RIGHT / 2, HEIGHT / 2 + 48, text="PRESS R TO TRY AGAIN", fill=self.COLORS["mint"], font=("Segoe UI", 10, "bold"), tags="dynamic")


def main() -> None:
    root = tk.Tk()
    MonsterShooter(root)
    root.mainloop()


if __name__ == "__main__":
    main()