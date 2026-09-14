"""Part seventeen: the facade shot, where the horizontal pair cannot answer.

A wall square to the camera has horizontals that barely converge. Their vanishing
point is out near infinity, and out there a pixel of line placement moves it
thousands of pixels, so the focal length computed against it is whatever the
noise says. That is the Pantheon plate: 0.89 mm from a 35 mm lens, while ticking
"I know the focal length" and typing 35 gives a grid that lies down correctly.

The verticals are a third perpendicular direction, and vertical against the
receding ground direction is a good pair on exactly the shots where the
horizontal pair is useless.

The important thing about this part is where the numbers come from. Vanishing
points computed exactly from a known camera solve perfectly however badly
conditioned they are, because there is nothing wrong with the arithmetic: an
earlier version of this file did that and proved nothing. So the lines are drawn
the way a person draws them. Real edges are projected through a real camera and
their endpoints are landed on whole pixels, which is the best anyone can do by
eye, and the vanishing points are then intersected from those. On a wall square
to the camera that half pixel is the whole story.
"""
import math
import nuke

nuke.pluginAddPath(r"C:\Users\dhoch\.nuke\Gizmos\DH_Tools\3D")
import dhPersp

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("  %-4s %-62s %s" % ("PASS" if ok else "FAIL", name, detail))


W, H = 667, 1000                      # the Pantheon plate
nuke.addFormat("%d %d 0 0 %d %d 1 rome" % (W, H, W, H))
nuke.root()["format"].setValue("rome")
plate = nuke.nodes.Constant(format="rome")
DIAG = math.hypot(W, H)
FILMBACK = 24.576
VA = FILMBACK * H / float(W)
DIAG_MM = math.hypot(FILMBACK, VA)
FOCAL = 35.0
HEIGHT = 5.5                          # feet, eye level


def camera_rows(pitch, yaw, roll=0.0):
    """World axes in camera coordinates, from Nuke's own camera.

    Taken from the camera rather than written out here, so a mistake about
    rotation order fails a test instead of agreeing with itself.
    """
    cam = nuke.nodes.Camera2() if "Camera2" in dir(nuke.nodes) else nuke.nodes.Camera()
    cam["rotate"].setValue([pitch, yaw, roll])
    cam["translate"].setValue([0.0, HEIGHT, 0.0])
    wm = cam["world_matrix"].getValue()
    nuke.delete(cam)
    return [tuple(wm[0:3]), tuple(wm[4:7]), tuple(wm[8:11])]


F_PX = FOCAL * DIAG / DIAG_MM
PX, PY = W / 2.0, H / 2.0


def project(rows, w, snap=True):
    """Where a world point lands, optionally on a whole pixel.

    Snapping is the point of this whole file. Tracing a line by eye puts its ends
    on pixels, and on a nearly parallel pair that rounding is the difference
    between a usable vanishing point and one out past a hundred thousand pixels.
    """
    d = (w[0], w[1] - HEIGHT, w[2])
    c = [sum(rows[i][j] * d[i] for i in range(3)) for j in range(3)]
    if c[2] >= -1e-9:
        return None
    p = (PX + F_PX * c[0] / (-c[2]), PY + F_PX * c[1] / (-c[2]))
    return (round(p[0]), round(p[1])) if snap else p


def cross(a, b, c, d):
    """Where line ab meets line cd."""
    x1, y1 = a
    x2, y2 = b
    x3, y3 = c
    x4, y4 = d
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-12:
        return (1e9, 1e9)
    p = (x1 * y2 - y1 * x2)
    q = (x3 * y4 - y3 * x4)
    return ((p * (x3 - x4) - (x1 - x2) * q) / den,
            (p * (y3 - y4) - (y1 - y2) * q) / den)


# Two real edges per direction, chosen the way you would choose them in a plate.
EDGES = {
    # the wall's own horizontals: an architrave and a step line, both running
    # along world X
    "across": [((-6.0, 11.0, -25.0), (6.0, 11.0, -25.0)),
               ((-6.0, 7.0, -25.0), (6.0, 7.0, -25.0))],
    # two kerbs on the ground running away from the camera, along world Z
    "ground": [((-4.0, 0.0, -7.0), (-4.0, 0.0, -30.0)),
               ((4.0, 0.0, -7.0), (4.0, 0.0, -30.0))],
    # two upright edges of the facade
    "vertical": [((-3.0, 0.5, -25.0), (-3.0, 13.0, -25.0)),
                 ((3.0, 0.5, -25.0), (3.0, 13.0, -25.0))],
}


def traced(rows, snap=True):
    """The three vanishing points, from lines drawn on whole pixels."""
    out = {}
    for name, (e1, e2) in EDGES.items():
        a, b = project(rows, e1[0], snap), project(rows, e1[1], snap)
        c, d = project(rows, e2[0], snap), project(rows, e2[1], snap)
        if None in (a, b, c, d):
            return None
        out[name] = cross(a, b, c, d)
    return out


s_node = nuke.createNode("dhPerspSolve", inpanel=False)
s = s_node
s.setInput(0, plate)


def solve(vps, vertical):
    s["vp1"].setValue([float(vps["ground"][0]), float(vps["ground"][1])])
    s["vp2"].setValue([float(vps["across"][0]), float(vps["across"][1])])
    s["vp3"].setValue([float(vps["vertical"][0]), float(vps["vertical"][1])])
    s["use_vertical"].setValue(bool(vertical))
    return s["cam_focal"].value()


# --------------------------------------------- 70. a well conditioned shot
print("\n=== 70. a two point shot: the horizontal pair is the right pair ===")
rows = camera_rows(-4.0, 38.0)
vps = traced(rows)
off = math.hypot(vps["across"][0] - PX, vps["across"][1] - PY)
print("     across vanishing point %.0f px from centre, %.0f frame diagonals"
      % (off, off / DIAG))
got = solve(vps, False)
check("two guides recover 35mm when both directions converge properly",
      abs(got - FOCAL) < 0.5, "%.4f mm" % got)
got = solve(vps, True)
check("a vertical guide does not disturb it", abs(got - FOCAL) < 0.5,
      "%.4f mm" % got)
check("and the horizontal pair is the one it used",
      int(s["_pair"].value()) == 12, "pair %d" % int(s["_pair"].value()))

# ------------------------------------------------- 71. the facade shot
print("\n=== 71. a facade shot: the horizontal pair cannot answer ===")
rows = camera_rows(-4.0, 0.4)          # most of half a degree off square
exact = traced(rows, snap=False)
vps = traced(rows)
offe = math.hypot(exact["across"][0] - PX, exact["across"][1] - PY)
off = math.hypot(vps["across"][0] - PX, vps["across"][1] - PY)
print("     across vanishing point: %.0f px exact, %.0f px once the line ends "
      "land on pixels" % (offe, off))
check("rounding the line ends to pixels moves that vanishing point a very long "
      "way", abs(off - offe) > 0.2 * offe,
      "%.0f px against %.0f px" % (off, offe))

two = solve(vps, False)
check("with two guides the answer is not a lens", abs(two - FOCAL) > 5.0,
      "%.4f mm against %.1f" % (two, FOCAL))

three = solve(vps, True)
# Line ends land on whole pixels, which on a 667 wide frame is worth a few per
# cent on its own; the two guide column of section 72 shows the same residual
# where it is well conditioned. Anything inside three millimetres of thirty five
# is the rounding, not the method.
check("THE FIX: the vertical guide rescues it", abs(three - FOCAL) < 3.0,
      "%.4f mm" % three)
check("and it used a pair involving the vertical",
      int(s["_pair"].value()) in (13, 23), "pair %d" % int(s["_pair"].value()))
check("the solve stands up", s["_solveok"].value() > 0.5, "")
dhPersp.set_verdict(s)
check("the panel says which pair answered",
      "vertical one" in s["verdict"].value(), s["verdict"].value()[-80:])

# the across guide is the unreliable one, so the answer must not depend on it
spread = []
for nudge in (-3.0, -1.0, 1.0, 3.0):
    moved = dict(vps)
    moved["across"] = (vps["across"][0] + nudge * 40000.0, vps["across"][1])
    spread.append(solve(moved, True))
check("and moving that vanishing point by tens of thousands of pixels barely "
      "changes it", max(spread) - min(spread) < 1.0,
      "%.3f mm spread over %s" % (max(spread) - min(spread),
                                  [round(v, 2) for v in spread]))

# ----------------------------------------- 72. across the range of angles
print("\n=== 72. across every angle from square on to a proper two point ===")
rowsets = [(yaw, camera_rows(-4.0, yaw)) for yaw in (0.2, 0.5, 1.0, 2.0, 5.0,
                                                     10.0, 20.0, 38.0)]
print("     yaw    two guides    three guides   pair")
worst2 = worst3 = 0.0
for yaw, r in rowsets:
    v = traced(r)
    a = solve(v, False)
    b = solve(v, True)
    print("     %5.1f   %9.3f     %9.3f    %2d"
          % (yaw, a, b, int(s["_pair"].value())))
    worst2 = max(worst2, abs(a - FOCAL))
    worst3 = max(worst3, abs(b - FOCAL))
check("two guides are wrong by a lot somewhere in that range", worst2 > 5.0,
      "worst %.2f mm off" % worst2)
check("three guides are right everywhere in it", worst3 < 3.0,
      "worst %.2f mm off" % worst3)

# --------------------------------------------- 73. it degrades honestly
print("\n=== 73. where nothing can answer, nothing is claimed ===")
rows = camera_rows(-4.0, 0.4)
vps = traced(rows)
blank = dict(vps)
blank["vertical"] = (PX, PY)           # a vertical guide nobody placed
solve(blank, True)
check("an unplaced vertical guide is not pressed into service",
      s_node["_v3use"].value() < 0.5, "")
# It does not refuse here, and that is the point: two guides on a facade produce
# a number that looks like a lens. What it must not do is call it believable.
got = s_node["cam_focal"].value()
check("two guides alone report something that looks like a lens", got > 5.0,
      "%.4f mm against a real %.1f" % (got, FOCAL))
check("but it is wrong by a lot", abs(got - FOCAL) > 5.0,
      "%.1f mm out" % abs(got - FOCAL))
check("the solve knows the answer rests on a far vanishing point",
      s_node["_ill"].value() > 0.5, "worst distance %.0f px, %.0f diagonals"
      % (s_node["_qb"].value(), s_node["_qb"].value() / DIAG))
dhPersp.set_verdict(s_node)
check("so the panel says to treat it with suspicion, and why",
      "suspicion" in s_node["verdict"].value(), s_node["verdict"].value()[-90:])
check("and it points at the upright guide, which is the way out",
      "upright edges" in s_node["verdict"].value(), "")

# ------------------------------------- 74. the orthocenter case is unchanged
print("\n=== 74. where the lens axis is solved, all three pairs agree anyway ===")
rows = camera_rows(-9.0, 38.0)
vps = traced(rows, snap=False)
solve(vps, True)
check("the vertical guide is usable", s["_v3use"].value() > 0.5, "")
check("and its orthocenter is a believable lens axis", s["_v3ok"].value() > 0.5,
      "(%.1f, %.1f) against centre (%.1f, %.1f)"
      % (s["_px"].value(), s["_py"].value(), PX, PY))
d = [s["_d12"].value(), s["_d13"].value(), s["_d23"].value()]
check("all three pairs give the same focal length, which is what an orthocenter "
      "is", max(d) - min(d) < max(abs(max(d)) * 1e-4, 1.0),
      "%s" % [round(v, 1) for v in d])
check("so it does not matter which pair was picked",
      abs(s["cam_focal"].value() - FOCAL) < 0.05,
      "%.4f mm" % s["cam_focal"].value())

# --------------------------------- 75. the old formula is still the same thing
print("\n=== 75. the horizontal pair is computed the same way it always was ===")
rows = camera_rows(-6.0, 33.0)
vps = traced(rows, snap=False)
s["use_vertical"].setValue(False)
solve(vps, False)
old = -s["_s1"].value() * s["_s2"].value() - s["_oivi"].value() ** 2
check("the dot product form matches the signed horizon form exactly",
      abs(s["_d12"].value() - old) < max(abs(old) * 1e-6, 1e-3),
      "%.4f against %.4f" % (s["_d12"].value(), old))
check("and the focal comes back", abs(s["cam_focal"].value() - FOCAL) < 0.05,
      "%.4f mm" % s["cam_focal"].value())

print("\n" + "=" * 88)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 17: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
