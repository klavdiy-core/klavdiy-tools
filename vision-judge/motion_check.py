"""motion check: scripted input -> telemetry per frame (camera, speed, contacts) -> rules.

The bugs that hurt most in a game are the ones every screenshot hides: each frame looks fine, the motion is wrong.
A tiny 2D platformer here carries five such bugs behind flags, so the check can be shown catching each one while a
per-frame look ("is the player on screen, inside the level?") passes them all. For your own game: record the same
telemetry from your engine (one dict per frame) and run check() on it.

python motion_check.py            # each planted bug: what a frame-by-frame look says vs what the rules say
"""
import json
import sys

DT = 1 / 60
LEVEL = (0.0, 40.0)               # x from wall to wall
FLOOR = 0.0
MAX_SPEED = 8.0                   # m/s, the game's own limit
CAM_HALF = 6.0                    # half the camera's width
KILL_Y = -2.0                     # under this the player respawns at the checkpoint
BUGS = ("camera_in_wall", "speed_unclamped", "teleport", "fall_through", "stuck")

# run right, jump, dash, run left into the wall: two seconds of play that touches every system
SCRIPT = [("right", 0, 90), ("jump", 20, 21), ("dash", 50, 51), ("left", 90, 170), ("jump", 120, 121)]


def keys_at(script, f):
    return {k for k, a, b in script if a <= f < b}


def play(script, frames=180, bugs=frozenset()):
    """Run the game; return the telemetry, one dict per frame."""
    x, y, vx, vy, cam = 5.0, 0.0, 0.0, 0.0, 5.0
    out = []
    for f in range(frames):
        k = keys_at(script, f)
        on_ground = y <= FLOOR + 1e-9
        want = (1 if "right" in k else 0) - (1 if "left" in k else 0)
        if "stuck" in bugs and f >= 100:
            want = 0                                         # input is read, never applied
        vx += (want * 60 - vx * 10) * DT
        if "dash" in k:
            vx += 14 * (1 if vx >= 0 else -1)
        if "speed_unclamped" not in bugs:
            vx = max(-MAX_SPEED, min(MAX_SPEED, vx))
        if "jump" in k and on_ground:
            vy = 9.0
        vy -= 25 * DT
        if "fall_through" in bugs and f == 60:
            vy = -40.0                                       # a hard landing
        x += vx * DT
        y += vy * DT
        if "teleport" in bugs and f == 70:
            x += 6.0                                         # a frame where the position jumps
        # collisions: the floor (the buggy version tests it only at low speed - tunnelling)
        if y < FLOOR and not ("fall_through" in bugs and vy < -30):
            y, vy = FLOOR, 0.0
        if y < KILL_Y:                                       # under the level: back to the checkpoint, as games do
            x, y, vx, vy = 5.0, 0.0, 0.0, 0.0
        x = max(LEVEL[0] + 0.5, min(LEVEL[1] - 0.5, x))
        cam += (x - cam) * 0.15
        if "camera_in_wall" not in bugs:
            cam = max(LEVEL[0] + CAM_HALF, min(LEVEL[1] - CAM_HALF, cam))
        out.append({"frame": f, "x": round(x, 4), "y": round(y, 4), "vx": round(vx, 4), "vy": round(vy, 4),
                    "cam": round(cam, 4), "keys": sorted(k)})
    return out


def check(t, max_speed=MAX_SPEED, level=LEVEL, floor=FLOOR, cam_half=CAM_HALF):
    """Rules over time. Each violation: rule, frame, detail. The first frame of each rule only (no flood)."""
    seen, out = set(), []

    def bad(rule, f, detail):
        if rule not in seen:
            seen.add(rule)
            out.append({"rule": rule, "frame": f, "detail": detail})
    for i, s in enumerate(t):
        if s["cam"] - cam_half < level[0] - 1e-6 or s["cam"] + cam_half > level[1] + 1e-6:
            bad("camera", s["frame"], f"the camera's view reaches {s['cam'] - cam_half:.2f}..{s['cam'] + cam_half:.2f}, "
                                      f"the level is {level[0]}..{level[1]}: it shows the inside of a wall")
        if abs(s["vx"]) > max_speed + 1e-6:
            bad("speed", s["frame"], f"horizontal speed {abs(s['vx']):.2f} m/s, the limit is {max_speed}")
        if s["y"] < floor - 1e-6:
            bad("floor", s["frame"], f"the player is {floor - s['y']:.2f} m under the floor")
        if i:
            p = t[i - 1]
            allowed = (abs(p["vx"]) + abs(s["vx"])) / 2 * DT + 1e-3
            if abs(s["x"] - p["x"]) > allowed * 3 + 0.05:
                bad("teleport", s["frame"], f"a jump of {abs(s['x'] - p['x']):.2f} m in one frame; the speed "
                                            f"allows {allowed:.3f}")
        if i >= 10:
            window = t[i - 10:i + 1]
            held = [w for w in window if ("right" in w["keys"]) != ("left" in w["keys"])]
            free = all(level[0] + 0.6 < w["x"] < level[1] - 0.6 for w in window)
            path = sum(abs(b["x"] - a["x"]) for a, b in zip(window, window[1:]))   # path, not net: a turn-around moves
            if len(held) == len(window) and free and path < 0.01:
                bad("stuck", s["frame"], "a direction held for 10 frames with room to move, and the player did "
                                         "not move")
    return out


def frame_looks_fine(t, cam_half=CAM_HALF):
    """What a screenshot of each frame can tell: is the player on screen and inside the level? Frames that fail."""
    return [s["frame"] for s in t
            if not (abs(s["x"] - s["cam"]) <= cam_half and LEVEL[0] <= s["x"] <= LEVEL[1] and s["y"] >= -5)]


def main():
    print(f"{'bug':<18} {'frames that look wrong':<24} rules broken (first frame)")
    for bug in ("none",) + BUGS:
        t = play(SCRIPT, bugs=set() if bug == "none" else {bug})
        found = check(t)
        print(f"{bug:<18} {len(frame_looks_fine(t)):<24} " +
              ("; ".join(f"{v['rule']} @{v['frame']}" for v in found) or "-"))
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        print(json.dumps({b: check(play(SCRIPT, bugs={b})) for b in BUGS}, indent=1))
    else:
        sys.exit(main())
