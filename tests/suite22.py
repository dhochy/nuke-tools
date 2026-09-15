"""Part twenty two: a refused solve draws nothing, because there is nothing to draw.

The verdict had been saying "these two guides do not describe a camera" for
several builds while the viewer drew a floor and a horizon underneath it anyway.
That is the contradiction David walked into on his first real plate. He read the
picture rather than the paragraph, saw a grid lying on the ground and a horizon
across the frame, and concluded the tool had solved it. It had returned a floor
value of a fraction of a millimeter and said so in a place he had no reason to be
looking.

A refused solve has no camera. No camera means no lens axis, so there is no
horizon, and no ground plane, so there is no floor. Drawing them asserts exactly
what the node has just refused to assert.

What this has to pin down is both halves. Nothing when it is refused, and
everything, unchanged, when it is not: the grid appearing is only a useful signal
if it is reliable in both directions. So a good solve is measured, then broken,
then put back, and the count has to come back to the same number it started at.
"""
import math
import nuke

nuke.pluginAddPath(r"C:\Users\dhoch\.nuke\Gizmos\DH_Tools\3D")
import dhPersp

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("  %-4s %-62s %s" % ("PASS" if ok else "FAIL", name, detail))


W, H = 1920, 1080
nuke.addFormat("%d %d 0 0 %d %d 1 testHD" % (W, H, W, H))
nuke.root()["format"].setValue("testHD")
plate = nuke.nodes.Constant(format="testHD", color=0.2)
s = nuke.createNode("dhPerspSolve", inpanel=False)
s.setInput(0, plate)
s["camera_height"].setValue(5.5)
s["cellsize"].setValue(2.0)
out = s.node("horizon_line")          # the last node before Output


def horizon_y(x):
    """Where the horizon really is at that column.

    It runs through both vanishing points, and those are rarely at the same
    height, so an average row misses it at the edges of frame. Sampling the
    wrong row and counting what turns up is how the first version of this test
    counted grid pixels and called them horizon.
    """
    (ax, ay), (bx, by) = s["vp1"].value(), s["vp2"].value()
    if abs(bx - ax) < 1e-9:
        return 0.5 * (ay + by)
    return ay + (by - ay) * (x - ax) / (bx - ax)


def drawn():
    """How much floor and how much horizon the node's OUTPUT is showing.

    Measured on the output, not on gridmask: gridmask sits above the switch that
    turns the floor off, so sampling it there can never see the switch do
    anything, which is a way to write a test that passes whatever the node does.

    The two are told apart by color rather than by "differs from the plate",
    because near the horizon they overlap and either one alone would be counted
    as both. The grid is orange, so it takes red up and blue down. The horizon
    is cyan, so it takes blue up. Blue going up is the horizon and nothing else.
    """
    grid = 0
    base = nuke.sample(plate, "red", 0.5, 0.5)
    hz = 0.5 * (s["vp1"].value()[1] + s["vp2"].value()[1])
    for y in (int(hz) - 200, int(hz) - 90, int(hz) - 30):
        if y < 2 or y > H - 2:
            continue
        x = 40
        while x < W - 40:
            if nuke.sample(out, "red", x + 0.5, y + 0.5) > base + 0.02:
                grid += 1
            x += 4
    horizon = 0
    for x in (200, 700, 1200, 1700):
        y = horizon_y(x + 0.5)
        if y < 2 or y > H - 2:
            continue
        for dy in (-0.5, 0.0, 0.5):
            if nuke.sample(out, "blue", x + 0.5, y + dy) > 0.6:
                horizon += 1
    return grid, horizon


GOOD = ([-1500.0, 600.0], [3700.0, 567.0])
SAME_WAY = ([820.0, 600.0], [880.0, 601.0])


def put(vps):
    s["vp1"].setValue(vps[0])
    s["vp2"].setValue(vps[1])


# ------------------------------------------- 96. a solve that stands up draws
print("\n=== 96. a solve that stands up draws its floor and its horizon ===")
put(GOOD)
good = drawn()
check("the solve stands up", s["_solveok"].value() > 0.5, "")
check("its floor is drawn", good[0] > 100, "%d pixels of grid" % good[0])
check("its horizon is drawn", good[1] > 0, "%d of 12 samples" % good[1])

# ------------------------------------------------- 97. a refused one does not
print("\n=== 97. two guides going the same way draw nothing at all ===")
put(SAME_WAY)
check("this really is refused, or the rest of this proves nothing",
      s["_solveok"].value() < 0.5,
      "the node would have called it %.4g mm" % s["cam_focal"].value())
bad = drawn()
check("no floor is drawn for a camera that does not exist", bad[0] == 0,
      "%d pixels of grid" % bad[0])
check("and no horizon, which is a lens axis there is not one of",
      bad[1] == 0, "%d of 12 samples" % bad[1])
check("the verdict says so in words as well",
      "do not describe a camera" in s["verdict"].value(), "")
check("and says why the viewer is empty",
      "not being drawn" in s["verdict"].value(), "")

# ---------------------------------------- 98. taking the focal as given draws
print("\n=== 98. unless the focal is taken as given, which needs no solve ===")
s["use_known_focal"].setValue(True)
s["known_focal"].setValue(35.0)
check("the same guides are accepted once the focal comes from outside",
      s["_solveok"].value() > 0.5, "%.2f mm" % s["cam_focal"].value())
known = drawn()
check("so the floor comes back", known[0] > 100, "%d pixels of grid" % known[0])
check("and the horizon with it", known[1] > 0, "%d of 12 samples" % known[1])
s["use_known_focal"].setValue(False)

# -------------------------------------------------- 99. and it comes straight back
print("\n=== 99. and a good solve draws exactly what it drew before ===")
put(GOOD)
back = drawn()
check("nothing about being refused leaves a mark on the next good solve",
      back == good, "%d and %d, against %d and %d before"
      % (back[0], back[1], good[0], good[1]))
s["show_floor"].setValue(False)
off = drawn()
check("show floor off leaves the horizon and takes the grid",
      off[0] < good[0] and off[1] == good[1],
      "%d pixels of grid, %d of 12 horizon samples" % off)
s["show_floor"].setValue(True)
s["show_horizon"].setValue(False)
nohz = drawn()
check("show horizon off leaves the grid and takes the horizon",
      nohz[1] == 0 and nohz[0] > 100,
      "%d pixels of grid, %d of 12 horizon samples" % nohz)
s["show_horizon"].setValue(True)
check("both back on and it is the same picture again", drawn() == good, "")

print("\n" + "=" * 88)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 22: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
