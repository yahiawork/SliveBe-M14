import json
import math
import os
import random
import re
import threading
import time
from pathlib import Path
from typing import List, Tuple

import pygame
import requests


# ---------------------------
# Configuration
# ---------------------------
SCREEN_TITLE = "SliveBe M14"
GRID_SIZE = 15
TILE_SIZE = 32
WINDOW_WIDTH = GRID_SIZE * TILE_SIZE
WINDOW_HEIGHT = GRID_SIZE * TILE_SIZE
PLAYER_SPEED = 220.0
BULLET_SPEED = 520.0
BULLET_LIFETIME = 1.8


# ---------------------------
# Fallback map matrix
# ---------------------------
FALLBACK_MAP = [
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1],
    [1, 0, 1, 0, 0, 0, 1, 0, 1, 0, 0, 0, 1, 0, 1],
    [1, 0, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1],
    [1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1],
    [1, 0, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 0, 1],
    [1, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 1],
    [1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
]


# ---------------------------
# Asset loading
# ---------------------------
def _safe_load(path: str) -> pygame.Surface:
    if os.path.exists(path):
        return pygame.image.load(path).convert_alpha()
    raise FileNotFoundError(path)


def load_assets() -> dict:
    """
    Load the main spritesheet if present, otherwise fall back to the existing project assets.
    The implementation uses pygame.subsurface() for tile extraction so the prototype stays faithful
    to the requested slicing workflow.
    """
    assets = {
        "floor": None,
        "wall": None,
        "player": None,
        "bullet": None,
        "sheet": None,
        "sheet_name": "",
    }

    candidate_sheets = [
        "img/image_dc1882.png",
        "img/Tilesheet/tilesheet_complete.png",
        "img/Spritesheet/spritesheet_tiles.png",
        "img/Tilesheet/tilesheet_complete_2X.png",
    ]

    loaded_sheet = None
    for candidate in candidate_sheets:
        if os.path.exists(candidate):
            loaded_sheet = pygame.image.load(candidate).convert_alpha()
            assets["sheet_name"] = candidate
            break

    if loaded_sheet is None:
        raise FileNotFoundError("No compatible spritesheet was found in img/.")

    assets["sheet"] = loaded_sheet
    sw, sh = loaded_sheet.get_size()

    # Robust subsurface extraction using a dynamic fallback grid.
    tile_w = min(32, sw // 8)
    tile_h = min(32, sh // 8)

    # Floor sample from the lower/middle area.
    floor_x = max(0, sw // 4)
    floor_y = max(0, sh - tile_h * 2)
    assets["floor"] = loaded_sheet.subsurface((floor_x, floor_y, tile_w, tile_h)).copy()
    if assets["floor"].get_width() < 8 or assets["floor"].get_height() < 8:
        assets["floor"] = pygame.Surface((tile_w, tile_h), pygame.SRCALPHA)
        pygame.draw.rect(assets["floor"], (120, 130, 150, 255), (0, 0, tile_w, tile_h))

    # Wall sample from the upper-left area.
    wall_x = max(0, min(sw - tile_w, tile_w))
    wall_y = max(0, min(sh - tile_h, tile_h))
    assets["wall"] = loaded_sheet.subsurface((wall_x, wall_y, tile_w, tile_h)).copy()
    if assets["wall"].get_width() < 8 or assets["wall"].get_height() < 8:
        assets["wall"] = pygame.Surface((tile_w, tile_h), pygame.SRCALPHA)
        pygame.draw.rect(assets["wall"], (60, 50, 55, 255), (0, 0, tile_w, tile_h), border_radius=0)
        pygame.draw.rect(assets["wall"], (180, 120, 40, 255), (1, 1, tile_w - 2, tile_h - 2), 2)

    # Character sprite from the spritesheet folder if available, otherwise use the main sheet.
    player_sheet = None
    for candidate in ["img/Spritesheet/spritesheet_characters.png", "img/PNG/Man Brown/manBrown_stand.png"]:
        if os.path.exists(candidate):
            player_sheet = pygame.image.load(candidate).convert_alpha()
            break

    if player_sheet is not None and player_sheet.get_width() >= 32 and player_sheet.get_height() >= 32:
        assets["player"] = player_sheet.subsurface((0, 0, 32, 32)).copy()
    else:
        assets["player"] = loaded_sheet.subsurface((max(0, sw - tile_w), max(0, sh - tile_h), tile_w, tile_h)).copy()

    # Bullet sample from a small section of the current spritesheet using subsurface().
    bullet_w = max(6, min(16, tile_w // 2))
    bullet_h = max(6, min(16, tile_h // 2))
    bullet_x = max(0, min(sw - bullet_w, sw // 2))
    bullet_y = max(0, min(sh - bullet_h, sh // 3))
    assets["bullet"] = loaded_sheet.subsurface((bullet_x, bullet_y, bullet_w, bullet_h)).copy()
    if assets["bullet"].get_width() < 4 or assets["bullet"].get_height() < 4:
        assets["bullet"] = pygame.Surface((bullet_w, bullet_h), pygame.SRCALPHA)
        pygame.draw.circle(assets["bullet"], (255, 210, 60, 255), (bullet_w // 2, bullet_h // 2), max(2, bullet_w // 2))

    # Make sure the surfaces are not tiny or empty.
    for key in ("floor", "wall", "player", "bullet"):
        surf = assets[key]
        if surf is None:
            raise RuntimeError(f"Failed to create asset: {key}")
        if surf.get_width() <= 0 or surf.get_height() <= 0:
            raise RuntimeError(f"Invalid asset dimensions for {key}")

    return assets


# ---------------------------
# AI map fetch (threaded + fallback)
# ---------------------------

def load_env_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def generate_random_fallback_map() -> List[List[int]]:
    """Create a fresh fallback arena every time the game starts."""
    grid = [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            if x in (0, GRID_SIZE - 1) or y in (0, GRID_SIZE - 1):
                grid[y][x] = 1
            elif random.random() < 0.28:
                grid[y][x] = 1

    # keep the spawn area open
    for y in range(6, 9):
        for x in range(6, 9):
            grid[y][x] = 0
    grid[7][7] = 0
    return grid


def parse_map_json(content: str) -> List[List[int]] | None:
    text = content.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and isinstance(parsed.get("map_grid"), list):
            return parsed["map_grid"]
    except json.JSONDecodeError:
        pass

    match = re.search(r'\{\s*"map_grid"\s*:\s*(\[[\s\S]*?\])\s*\}', text)
    if match:
        try:
            parsed = json.loads('{"map_grid": ' + match.group(1) + '}')
            if isinstance(parsed.get("map_grid"), list):
                return parsed["map_grid"]
        except json.JSONDecodeError:
            pass
    return None


def fetch_map_layout(result_holder: dict, api_key: str | None = None) -> None:
    """Generate a fresh map on every run, using AI when possible and the built-in matrix only as a fallback."""
    load_env_file(".env")
    api_key = api_key or os.getenv("NVIDIA_API_KEY") or os.getenv("NIM_API_KEY")
    base_url = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
    model_name = os.getenv("NVIDIA_MODEL_NAME", "meta/llama-3.1-8b-instruct")

    if not api_key:
        result_holder["grid"] = generate_random_fallback_map()
        return

    seed = random.randint(1000, 9999)
    system_prompt = (
        "You are generating a fresh 15x15 arena map for a top-down shooter. "
        "Return ONLY valid JSON with one key 'map_grid'. "
        "Use integers 0 for floor and 1 for wall. "
        f"Use variation seed {seed} so the arrangement is different on every run. "
        "Keep the center tile (7,7) and its immediate neighbors as 0 for spawn safety. "
        "Create a balanced layout with 30-40% walls, some open lanes, and avoid all-wall or all-floor maps. "
        "Do not wrap the answer in markdown or commentary."
    )
    user_prompt = f"Generate one brand-new strict 15x15 map_grid for the arena using variation seed {seed}. Keep the center spawn area open and make the layout different from any previous run."

    for _ in range(3):
        try:
            url = f"{base_url}/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
            }
            response = requests.post(url, headers=headers, json=payload, timeout=8)
            response.raise_for_status()
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed_grid = parse_map_json(content)
            if isinstance(parsed_grid, list) and len(parsed_grid) == GRID_SIZE and all(isinstance(row, list) for row in parsed_grid):
                # Basic validation: center area must remain open.
                if parsed_grid[7][7] == 0 and parsed_grid[6][7] == 0 and parsed_grid[7][6] == 0 and parsed_grid[8][7] == 0 and parsed_grid[7][8] == 0:
                    result_holder["grid"] = parsed_grid
                    return
        except Exception:
            pass

    result_holder["grid"] = generate_random_fallback_map()


def start_map_fetch_thread(result_holder: dict) -> threading.Thread:
    load_env_file(".env")
    api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("NIM_API_KEY")
    thread = threading.Thread(target=fetch_map_layout, args=(result_holder, api_key), daemon=True)
    thread.start()
    return thread


# ---------------------------
# Game helpers
# ---------------------------
def normalize(vx: float, vy: float) -> Tuple[float, float]:
    length = math.hypot(vx, vy)
    if length == 0:
        return 0.0, 0.0
    return vx / length, vy / length


def rect_from_center(cx: float, cy: float, w: float, h: float) -> pygame.Rect:
    return pygame.Rect(cx - w / 2, cy - h / 2, w, h)


def rect_collides_with_wall(player_rect: pygame.Rect, walls: List[pygame.Rect]) -> bool:
    return any(player_rect.colliderect(wall_rect) for wall_rect in walls)


def build_wall_rects(grid: List[List[int]]) -> List[pygame.Rect]:
    walls = []
    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            if cell == 1:
                walls.append(pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE))
    return walls


def point_in_grid(x: float, y: float) -> Tuple[int, int]:
    return int(x // TILE_SIZE), int(y // TILE_SIZE)


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


# ---------------------------
# Main loop
# ---------------------------
def main() -> None:
    random.seed(time.time_ns())
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption(SCREEN_TITLE)

    assets = load_assets()
    map_result = {"grid": None}
    thread = start_map_fetch_thread(map_result)

    # Wait for the AI thread to finish, but allow enough time for the real API call.
    thread.join(timeout=8)

    grid = map_result.get("grid") or generate_random_fallback_map()
    wall_rects = build_wall_rects(grid)

    clock = pygame.time.Clock()

    player_x = TILE_SIZE * 7 + TILE_SIZE // 2
    player_y = TILE_SIZE * 7 + TILE_SIZE // 2
    player_rect = rect_from_center(player_x, player_y, 24, 24)

    keys = pygame.key.get_pressed()
    mouse_pos = pygame.Vector2(player_x, player_y)
    bullets = []

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        screen.fill((12, 18, 24))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                aim_x = player_x + 1
                aim_y = player_y
                bullet = {
                    "x": player_x,
                    "y": player_y,
                    "vx": BULLET_SPEED,
                    "vy": 0.0,
                    "life": BULLET_LIFETIME,
                    "angle": 0.0,
                }
                bullets.append(bullet)

        keys = pygame.key.get_pressed()
        move_x = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        move_y = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])

        if move_x != 0 or move_y != 0:
            vx, vy = normalize(move_x, move_y)
            player_x += vx * PLAYER_SPEED * dt
            player_y += vy * PLAYER_SPEED * dt

            # Strict AABB collision resolution with sliding.
            new_rect = rect_from_center(player_x, player_y, 24, 24)
            if rect_collides_with_wall(new_rect, wall_rects):
                player_x -= vx * PLAYER_SPEED * dt
                new_rect = rect_from_center(player_x, player_y, 24, 24)
            if rect_collides_with_wall(new_rect, wall_rects):
                player_y -= vy * PLAYER_SPEED * dt
                new_rect = rect_from_center(player_x, player_y, 24, 24)
            if rect_collides_with_wall(new_rect, wall_rects):
                player_x += vx * PLAYER_SPEED * dt
                player_y += vy * PLAYER_SPEED * dt

        # Clamp the player to the visible area.
        player_x = clamp(player_x, 24, WINDOW_WIDTH - 24)
        player_y = clamp(player_y, 24, WINDOW_HEIGHT - 24)
        player_rect = rect_from_center(player_x, player_y, 24, 24)

        aim_dx = 1.0
        aim_dy = 0.0
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            aim_dx, aim_dy = 0.0, -1.0
        elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
            aim_dx, aim_dy = 0.0, 1.0
        elif keys[pygame.K_LEFT] or keys[pygame.K_a]:
            aim_dx, aim_dy = -1.0, 0.0
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            aim_dx, aim_dy = 1.0, 0.0
        angle = math.degrees(math.atan2(aim_dy, aim_dx))

        # Draw the map.
        for y, row in enumerate(grid):
            for x, cell in enumerate(row):
                rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                if cell == 1:
                    screen.blit(pygame.transform.scale(assets["wall"], (TILE_SIZE, TILE_SIZE)), rect)
                else:
                    screen.blit(pygame.transform.scale(assets["floor"], (TILE_SIZE, TILE_SIZE)), rect)

        # Update and draw bullets.
        for bullet in bullets[:]:
            bullet["x"] += bullet["vx"] * dt
            bullet["y"] += bullet["vy"] * dt
            bullet["life"] -= dt
            if bullet["life"] <= 0:
                bullets.remove(bullet)
                continue
            bullet_surface = pygame.transform.rotate(assets["bullet"], bullet["angle"] - 90)
            bullet_rect = bullet_surface.get_rect(center=(bullet["x"], bullet["y"]))
            screen.blit(bullet_surface, bullet_rect)

        # Rotate the player sprite toward the cursor.
        player_surface = pygame.transform.rotate(assets["player"], angle)
        player_surface = pygame.transform.scale(player_surface, (34, 34))
        screen.blit(player_surface, player_surface.get_rect(center=(player_x, player_y)))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
