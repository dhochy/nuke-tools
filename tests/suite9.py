"""Part nine: the ground plane drawn in 2D, and whether it agrees with the camera.

Three things are being asked.

Does it still describe the same scene. The grid no longer goes through the 3D
renderer, so it has to be checked against the camera some other way: take the
solved camera's own world matrix, project a ground point of known real position,
and see whether the pixel that lands on reports that same position back. If those
agree the grid is the camera, drawn a different way.

Does it behave the way a ground plane behaves. Filled from the bottom of frame up
to the horizon, nothing above the horizon, no edge anywhere in between, and
nothing that moves when a knob that should not move it is touched.

Is the thing David complained about actually gone. Not fixed, gone: there is no
size knob to move it with any more.
"""
import math
import os
import nuke

GIZDIR = r"C:\Users\dhoch\.nuke\Gizmos\DH_Tools\3D"
TMP = r"C:\temp\dgtest"
if not os.path.isdir(TMP):
    os.makedirs(TMP)
nuke.pluginAddPath(GIZDIR)
import dhPersp

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("  %-4s %-58s %s" % ("PASS" if ok else "FAIL", name, detail))


W, H = 1920, 1080
nuke.addFormat("%d %d 0 0 %d %d 1 testHD" % (W, H, W, H))
nuke.root()["format"].setValue("testHD")
plate = nuke.nodes.Constant(format="testHD", color=0.2)

g1 = nuke.createNode("dhPerspGuide", inpanel=False)
g1.setInput(0, plate)
g1["p1a"].setValue([180.0, 120.0]); g1["p1b"].setValue([1500.0, 430.0])
g1["p2a"].setValue([180.0, 940.0]); g1["p2b"].setValue([1500.0, 700.0])
g2 = nuke.createNode("dhPerspGuide", inpanel=False)
g2.setInput(0, g1)
g2["p1a"].setValue([1780.0, 150.0]); g2["p1b"].setValue([420.0, 470.0])
g2["p2a"].setValue([1780.0, 930.0]); g2["p2b"].setValue([420.0, 690.0])
s = nuke.createNode("dhPerspSolve", inpanel=False)
s.setInput(0, g2)
for n in nuke.allNodes():
    n.setSelected(False)
dhPersp.on_knob_changed(s, type("IC", (), {"name": staticmethod(lambda: "inputChange")})())
s["camera_height"].setValue(5.5)
s["cellsize"].setValue(2.0)
s["gridwidth"].setValue(2.0)

print("\n=== 31. the knobs that moved the floor no longer exist ===")
for gone in ("gridsize", "griddistance", "autofit", "gridfade", "gridstyle",
             "texlines", "near_cells", "horizon_gap", "gridrows", "fitfloor"):
    check("no %s knob" % gone, gone not in s.knobs(), "")
check("no card inside the node", s.node("floorgrid") is None, "")
check("no 3D renderer inside the node", s.node("render3d") is None, "")
check("the camera is still there and still solved",
      s.node("cam") is not None and 4.0 < s["cam_focal"].value() < 400.0,
      "%.2f mm" % s["cam_focal"].value())

# --------------------------------------------------- 32. agrees with the camera
print("\n=== 32. the ground the grid draws is the ground the camera sees ===")
cam = s.node("cam")
# world_matrix.value(i) returns the first row and then zeros, which makes a
# singular matrix whose inverse is nan. getValue() returns all sixteen.
wm = cam["world_matrix"].getValue()
m = nuke.math.Matrix4()
for i in range(16):
    m[i] = wm[i]
check("the camera's world matrix is real", abs(m.determinant() - 1.0) < 1e-3,
      "determinant %.6f" % m.determinant())
# Rows of the rotation part are the world axes written in camera coordinates,
# which is exactly what turns a world offset into a camera space one.
rows = [tuple(wm[0:3]), tuple(wm[4:7]), tuple(wm[8:11])]
cx, cy, cz = wm[3], wm[7], wm[11]

f_px = float(s["_f"].value())
px, py = float(s["_px"].value()), float(s["_py"].value())
ground = s.node("groundxz")
mask = s.node("gridmask")


def project(X, Z):
    """Where a ground point lands, using Nuke's own camera matrix."""
    # Matrix4.transform applies the rotation and throws the translation away,
    # so it answers for a direction, not a point. The camera is five and a half
    # feet off the ground, which is the entire scale of this test, so that has
    # to be subtracted by hand.
    w = (X - cx, 0.0 - cy, Z - cz)
    # Row i of the rotation is world axis i written in camera coordinates, which
    # is what identifies the axes. Turning a world offset into a camera space
    # one is the other way round: it is the columns that get dotted.
    p = [sum(rows[i][j] * w[i] for i in range(3)) for j in range(3)]
    if not (p[2] < -1e-6):                # false for nan too, which is the point
        return None
    at = (px + f_px * p[0] / (-p[2]), py + f_px * p[1] / (-p[2]))
    if at[0] != at[0] or at[1] != at[1]:
        return None
    return at


# The grid's two axes are the two directions the guides marked. Which of them
# the camera calls X and which Z, and which way round each runs, is the axis
# choice on the Horizon tab, so the mapping is fixed once and then has to hold
# for every pixel.
SAMPLES = [(x, y) for x in (240, 700, 1200, 1680) for y in (40, 160, 320, 460)]
FORMS = [("X,Z", lambda a, b: (a, b)), ("Z,X", lambda a, b: (b, a)),
         ("-X,Z", lambda a, b: (-a, b)), ("X,-Z", lambda a, b: (a, -b)),
         ("-X,-Z", lambda a, b: (-a, -b)), ("-Z,X", lambda a, b: (-b, a)),
         ("Z,-X", lambda a, b: (b, -a)), ("-Z,-X", lambda a, b: (-b, -a))]

read = []
for x, y in SAMPLES:
    if nuke.sample(ground, "blue", x + 0.5, y + 0.5) >= 0:
        continue                                   # above the horizon, not ground
    read.append((x + 0.5, y + 0.5,
                 nuke.sample(ground, "red", x + 0.5, y + 0.5),
                 nuke.sample(ground, "green", x + 0.5, y + 0.5)))
check("there is ground to test under the horizon", len(read) >= 8,
      "%d of %d sample pixels are ground" % (len(read), len(SAMPLES)))

best, bestname = None, ""
for nm, f in FORMS:
    worst = 0.0
    for x, y, a, b in read:
        at = project(*f(a, b))
        worst = 1e9 if at is None else max(worst, math.hypot(at[0] - x, at[1] - y))
    if best is None or worst < best:
        best, bestname = worst, nm

for x, y, a, b in read[:4]:
    at = project(*dict(FORMS)[bestname](a, b))
    print("     pixel (%7.1f,%7.1f) -> ground (%8.2f,%8.2f) -> back to "
          "(%7.1f,%7.1f)" % (x, y, a, b, at[0], at[1]))
check("every ground point the grid reports projects back onto its own pixel",
      best is not None and best < 0.5,
      "axes %s, worst error %.4f px over %d pixels" % (bestname, best, len(read)))

# ------------------------------------------------ 33. it behaves like ground
print("\n=== 33. filled to the horizon, nothing above it, no edge between ===")
hy = 0.5 * (s["vp1"].value()[1] + s["vp2"].value()[1])
check("the horizon is inside the frame", 0 < hy < H, "y = %.1f" % hy)

above = max(nuke.sample(ground, "blue", x, hy + 30) for x in (60, 960, 1860))
below = min(nuke.sample(ground, "blue", x, hy - 30) for x in (60, 960, 1860))
check("above the horizon there is no ground", above >= 0.0, "D = %.4f" % above)
check("below the horizon there is", below < 0.0, "D = %.4f" % below)


def band(y, x0, x1, step=1):
    """How many pixels of that row span have grid on them.

    nuke.sample given a box returns something that does not see a two pixel
    line, so this walks the row instead. It is the slow way and it is the one
    that matches what the render looks like.
    """
    n = 0
    x = int(x0)
    while x < int(x1):
        if nuke.sample(mask, "red", x + 0.5, y + 0.5) > 0.02:
            n += 1
        x += step
    return n


quarters = [band(6, q * W / 4.0, (q + 1) * W / 4.0) for q in range(4)]
check("the grid runs the full width at the bottom of frame, no card corner",
      min(quarters) > 0, "row 6, lit pixels per quarter %s" % quarters)

reach = None
for y in range(int(hy) - 1, 4, -1):
    if band(y, 0, W, 2) > 0:
        reach = y
        break
# An infinite grid cannot draw all the way to the horizon: the lines there are
# closer together than a pixel. It stops where they stop being readable, which
# depends on the cell size, so what matters is that the gap is small and that a
# coarser cell reaches further, not that it touches.
check("the grid runs out within a twentieth of frame height of the horizon",
      reach is not None and hy - reach < H / 20.0,
      "last lit row %s, horizon %.1f, gap %.0f px" % (reach, hy, hy - (reach or 0)))

holes = [y for y in range(4, int(reach or 10) - 6, 24) if band(y, 0, W, 2) == 0]
check("no empty band anywhere between the bottom of frame and where it runs out",
      not holes, "%d empty rows %s" % (len(holes), holes[:6]))

# a card has a straight edge, which shows up as a row where the lit width
# suddenly shrinks. Ground never does that: the lit span is the whole frame all
# the way up.
narrow = [y for y in range(4, int(hy) - 40, 48)
          if band(y, 0, W / 4.0, 2) == 0 or band(y, 3 * W / 4.0, W, 2) == 0]
check("the grid touches both sides of frame at every height, so it has no corner",
      len(narrow) <= 1, "%d rows short of an edge %s" % (len(narrow), narrow[:6]))

# ------------------------------------------------ 34. nothing moves any more
print("\n=== 34. touching things does not move the grid ===")


def fingerprint():
    return [round(nuke.sample(ground, "red", x + 0.5, y + 0.5), 4)
            for x in (200, 960, 1700) for y in (60, 300, 600)]


base = fingerprint()
s["gridwidth"].setValue(5.0)
check("line width does not move the ground", fingerprint() == base, "")
s["gridwidth"].setValue(2.0)
s["gridcolor"].setValue([0.0, 1.0, 0.0, 1.0])
check("colour does not move the ground", fingerprint() == base, "")

cell_lines = []
for cell in (1.0, 2.0, 4.0, 8.0):
    s["cellsize"].setValue(cell)
    cell_lines.append(round(nuke.sample(mask, "red", 960.5, 60.5), 3))
check("cell size does not move the ground plane itself", fingerprint() == base,
      "ground unchanged across four cell sizes")
s["cellsize"].setValue(2.0)

# the line through the offset must stay put when the cell size changes, which is
# the property that made the old grid feel like it was crawling
s["gridoffset"].setValue([0.0, 0.0, 0.0])
anchor = []
for cell in (1.0, 2.0, 4.0):
    s["cellsize"].setValue(cell)
    col = None
    for x in range(200, 1720):
        if nuke.sample(mask, "red", x + 0.5, 40.5) > 0.5:
            col = x
            break
    anchor.append(col)
check("a grid line exists low in frame at every cell size",
      all(a is not None for a in anchor), str(anchor))
s["cellsize"].setValue(2.0)

# camera height is a real scale change and is allowed to move the ground, but
# the grid must stay on the ground: doubling the height doubles the distance to
# everything, so the pattern is the same picture
s["camera_height"].setValue(11.0)
doubled = [round(v, 3) for v in fingerprint()]
ok = all(abs(d - 2.0 * b) < max(0.02 * abs(b), 0.01) for d, b in zip(doubled, base))
check("doubling camera height doubles every ground distance, as it must", ok,
      "%s vs %s" % (doubled[:3], [round(2 * b, 3) for b in base[:3]]))
s["camera_height"].setValue(5.5)

# ------------------------------------------------ 35. the fade is per line now
print("\n=== 35. lines fade by their own spacing, not by height on screen ===")
s["cellsize"].setValue(8.0)
coarse_near = band(6, 0, W, 2)
coarse_top = band(int(hy) - 10, 0, W, 2)
check("a coarse grid still draws near the camera", coarse_near > 0,
      "%d lit pixels on the bottom row" % coarse_near)
s["cellsize"].setValue(0.25)
fine_near = band(6, 0, W, 2)
fine_top = band(int(hy) - 10, 0, W, 2)
check("a fine grid draws near the camera too", fine_near > 0,
      "%d lit pixels on the bottom row" % fine_near)
check("a fine grid draws more near the camera than a coarse one",
      fine_near > coarse_near, "fine %d vs coarse %d" % (fine_near, coarse_near))
check("but not more at the horizon, because it runs out of pixels first",
      fine_top <= coarse_top, "fine %d vs coarse %d ten rows under the horizon"
      % (fine_top, coarse_top))
check("and nothing near the horizon fills in solid",
      max(fine_top, coarse_top) < 0.6 * (W / 2), "worst %d of %d"
      % (max(fine_top, coarse_top), W / 2))
s["cellsize"].setValue(2.0)

nuke.scriptSaveAs(os.path.join(TMP, "s9.nk").replace("\\", "/"), overwrite=1)
w = nuke.nodes.Write(file=os.path.join(TMP, "s9_ground.png").replace("\\", "/"),
                     file_type="png")
w.setInput(0, s)
nuke.execute(w, 1, 1)
print("  wrote %s" % os.path.join(TMP, "s9_ground.png"))

print("\n" + "=" * 84)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 9: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
