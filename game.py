import curses, math, random, time, locale

locale.setlocale(locale.LC_ALL, '')

W, H = 600, 240

KNIGHT = [
    ("  ~~,   ", "  rrg   "),
    ("  /==\\  ", "  gwwg  "),
    ("  |=-|  ", "  gwdg  "),
    (" _\\__/_ ", " gggggg "),
    ("(O|##|\\ ", "gygwwgg "),
    ("(O|##| +", "gygwwg y"),
    ("  |__| |", "  gggg w"),
]
LEGS = [("  /  \\  ", "  g  g  "), ("  |  |  ", "  g  g  ")]

# tiny chick: yellow body, white eye, orange beak
CHICK = [
    ("(o>", "cwo"),
    ("(_)", "ccc"),
]

MIRROR = str.maketrans("/\\()[]<>", "\\/)(][><")

def flip(rows):
    return [(s[::-1].translate(MIRROR), c[::-1]) for s, c in rows]

SPRITES = {
    1:  [KNIGHT + [legs] for legs in LEGS],
    -1: [flip(KNIGHT + [legs]) for legs in LEGS],
}
CHICK_SPRITES = {1: CHICK, -1: flip(CHICK)}

# braille
DOTS = [[0x01, 0x02, 0x04, 0x40], [0x08, 0x10, 0x20, 0x80]]

def blade(col, base, height, lean):
    # bitmask of braille dots
    mask = 0
    for i in range(height):
        row = base - i
        c = col + lean if i >= 1 else col
        if 0 <= row <= 3 and 0 <= c <= 1:
            mask |= DOTS[c][row]
    return mask

rng = random.Random(7)
BRAILLE, ASCII = [], []
for _ in range(64):
    blades = [(rng.randint(0, 1), rng.randint(1, 3), rng.randint(2, 3))
              for _ in range(rng.choice([1, 1, 2]))]
    chars = []
    for lean in (-1, 0, 1):
        mask = 0
        for col, base, height in blades:
            mask |= blade(col, base, height, lean)
        chars.append(chr(0x2800 + mask))
    BRAILLE.append(chars)
    ASCII.append(("`", rng.choice("'.'"), ","))

def cell_hash(x, y):
    return (x * 73856093 ^ y * 19349663) & 0xFFFF

MOVES = {
    curses.KEY_LEFT: (-1, 0), curses.KEY_RIGHT: (1, 0),
    curses.KEY_UP: (0, -1),   curses.KEY_DOWN: (0, 1),
}
C_MOVES = {
    ord('a'): (-1, 0), ord('d'): (1, 0),
    ord('w'): (0, -1), ord('s'): (0, 1),
}
C_MOVES.update({ord(chr(k).upper()): v for k, v in list(C_MOVES.items())})

def main(scr):
    curses.curs_set(0)
    scr.nodelay(True)
    curses.start_color()
    curses.use_default_colors()
    rich = curses.COLORS >= 256

    pinks = [212, 218, 219, 225] if rich else [curses.COLOR_MAGENTA] * 4
    for i, c in enumerate(pinks):
        curses.init_pair(1 + i, c, -1)

    if rich:
        palette = {'g': 248, 'w': 255, 'd': 240, 'r': 160, 'y': 178,
                   'c': 226, 'o': 208}
    else:
        palette = {'g': curses.COLOR_WHITE, 'w': curses.COLOR_WHITE,
                   'd': curses.COLOR_WHITE, 'r': curses.COLOR_RED,
                   'y': curses.COLOR_YELLOW, 'c': curses.COLOR_YELLOW,
                   'o': curses.COLOR_RED}
    KC = {}
    for i, (k, c) in enumerate(palette.items()):
        curses.init_pair(10 + i, c, -1)
        KC[k] = curses.color_pair(10 + i) | (curses.A_BOLD if k in 'wyc' else 0)

    px, py = W // 2, H // 2
    facing, step = 1, 0
    # baby chick spawns right next to the knight
    cx, cy = px + 7, py
    cfacing, cstep, hop_until = -1, 0, 0.0
    cam_x = cam_y = None
    variants = BRAILLE

    while True:
        key = scr.getch()
        while key != -1:
            if key == ord('q'):
                return
            if key == ord('g'):
                variants = ASCII if variants is BRAILLE else BRAILLE
            if key in MOVES:
                dx, dy = MOVES[key]
                if dx:
                    facing = dx
                # need to step twice
                px = max(5, min(W - 6, px + dx * 2))
                py = max(9, min(H - 2, py + dy))
                step += 1
            if key in C_MOVES:
                dx, dy = C_MOVES[key]
                if dx:
                    cfacing = dx
                cx = max(3, min(W - 4, cx + dx * 2))
                cy = max(3, min(H - 2, cy + dy))
                cstep += 1
                hop_until = time.time() + 0.12
            key = scr.getch()

        t = time.time()
        sh, sw = scr.getmaxyx()
        view_h = sh - 1
        if cam_x is None:
            cam_x, cam_y = px - sw // 2, py - view_h // 2
        mx, my = sw // 4, view_h // 5
        cam_x = min(max(cam_x, px + mx - sw), px - mx)
        cam_y = min(max(cam_y, py + my - view_h), py - 8 - my)
        cam_x = max(0, min(cam_x, W - sw))
        cam_y = max(0, min(cam_y, H - view_h))

        # grass
        scr.erase()
        for sy in range(view_h):
            wy = cam_y + sy
            if not 0 <= wy < H:
                continue
            near_feet = py - 1 <= wy <= py
            near_chick = cy - 1 <= wy <= cy
            for sx in range(sw - 1):
                wx = cam_x + sx
                if not 0 <= wx < W:
                    continue
                h = cell_hash(wx, wy)
                dk = wx - px
                dc = wx - cx
                if near_feet and 0 < abs(dk) <= 4:
                    lean = -1 if dk < 0 else 1
                elif near_chick and 0 < abs(dc) <= 2:
                    lean = -1 if dc < 0 else 1
                else:
                    wind = math.sin(wx * 0.08 + wy * 0.15 - t * 1.2) + 0.4 * math.sin(wx * 0.03 - t * 0.5)
                    lean = 1 if wind > 0.5 else -1 if wind < -0.5 else 0
                ch = variants[h % 64][lean + 1]
                glow = math.sin(wx * 0.03 + wy * 0.06 - t * 0.3) + ((h >> 6) % 3 - 1) * 0.6
                shade = min(3, max(0, int((glow + 1.6) * 1.25)))
                attr = curses.color_pair(1 + shade)
                if shade == 3:
                    attr |= curses.A_BOLD
                scr.addstr(sy, sx, ch, attr)

        def draw(sprite, x0, y0, left):
            # y0 = world row of the sprite's feet, left = world col of its left edge
            for i, (row, colors) in enumerate(sprite):
                y = y0 - len(sprite) + i - cam_y
                for j, (c, k) in enumerate(zip(row, colors)):
                    x = left + j - cam_x
                    if c != ' ' and 0 <= y < view_h and 0 <= x < sw - 1:
                        scr.addstr(y, x, c, KC[k])

        knight_sprite = SPRITES[facing][(step // 2) % 2]
        hop = 1 if t < hop_until and cstep % 2 else 0   # little hop while walking
        chick_sprite = CHICK_SPRITES[cfacing]

        # draw whoever is further back first so the nearer one overlaps
        if cy < py:
            draw(chick_sprite, cx, cy - hop, cx - 1)
            draw(knight_sprite, px, py, px - 4)
        else:
            draw(knight_sprite, px, py, px - 4)
            draw(chick_sprite, cx, cy - hop, cx - 1)

        help_text = "arrows: knight, wasd: chick, g grass style, q quit"
        scr.addstr(sh - 1, 0, help_text[:sw - 1], curses.A_DIM)

        scr.refresh()
        time.sleep(1 / 30)

curses.wrapper(main)