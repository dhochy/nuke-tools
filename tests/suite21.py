"""Part twenty one: the floor that gets drawn is a true picture of its own plane.

Part twenty checked that _u1 and _u2, the two directions the floor is supposed to
be drawn with, are square and lie in the ground plane. They were, and they always
had been, and for three builds nothing read them: the floor kept being drawn from
_a1 and _a2, the raw ray directions to the two level vanishing points. A test on
the knobs cannot see that. This one reads the pixels.

On an automatic solve the difference is exactly nothing, because the focal length
is chosen as the one that makes those two rays perpendicular, so _u1 and _a1 are
the same vector. It is the known focal path that was wrong. There the focal comes
from the person rather than from the geometry, the two rays sit at whatever angle
they happen to sit at, and the floor came out sheared: at 24 mm on a plate that
wants 35 the red and green channels disagreed with the plane they describe by
10.5 percent, and at 85 mm by 66 percent, which is a grid of slivers no camera
height could ever make lie down on the plate.

The question a test can ask about this without trusting any of the node's own
working: take the floor's two channels at a spread of pixels, work out from the
lens where each of those pixels really lands on the plane, and compare the real
distance between two of them against the distance the floor's own numbers imply.
Honest coordinates on a plane are an isometry, so those two numbers are the same
number. Sheared ones are not.
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

# A camera looking slightly down and turned off square, which is the ordinary
# case. Everything the floor does happens in camera space, so the only thing
# needed out of this is where the three vanishing points land.
PITCH, YAW, ROLL = math.radians(-9.0), math.radians(34.0), math.radians(1.5)
FOCAL_PX = 1500.0
CX, CY = W / 2.0, H / 2.0


def world_to_camera(p, y, r):
    """Nuke composes rotate XYZ, and world to camera is that inverted."""
    cp, sp, cy, sy, cr, sr = (math.cos(p), math.sin(p), math.cos(y),
                              math.sin(y), math.cos(r), math.sin(r))
    rx = ((1, 0, 0), (0, cp, -sp), (0, sp, cp))
    ry = ((cy, 0, sy), (0, 1, 0), (-sy, 0, cy))
    rz = ((cr, -sr, 0), (sr, cr, 0), (0, 0, 1))
    m = [[sum(ry[i][k] * rx[k][j] for k in range(3)) for j in range(3)]
         for i in range(3)]
    m = [[sum(rz[i][k] * m[k][j] for k in range(3)) for j in range(3)]
         for i in range(3)]
    return [[m[j][i] for j in range(3)] for i in range(3)]


R = world_to_camera(PITCH, YAW, ROLL)


def vanishing(d):
    """Where a world direction's parallel lines meet on screen."""
    c = [sum(R[i][j] * d[j] for j in range(3)) for i in range(3)]
    if c[2] > 0:                      # a vanishing point is the same both ways
        c = [-v for v in c]
    return (CX + FOCAL_PX * c[0] / (-c[2]), CY + FOCAL_PX * c[1] / (-c[2]))


plate = nuke.nodes.Constant(format="testHD", color=0.2)


def guide(under, vp, anchors, role):
    """A guide whose two lines both run at that vanishing point."""
    gd = nuke.createNode("dhPerspGuide", inpanel=False)
    gd.setInput(0, under)
    gd["role"].setValue(role)
    for i, (ax, ay) in enumerate(anchors):
        ux, uy = vp[0] - ax, vp[1] - ay
        n = math.hypot(ux, uy)
        gd["p%da" % (i + 1)].setValue([ax, ay])
        gd["p%db" % (i + 1)].setValue([ax + ux / n * 900.0,
                                       ay + uy / n * 900.0])
    return gd


g1 = guide(plate, vanishing((1.0, 0.0, 0.0)),
           [(300.0, 200.0), (300.0, 800.0)], "ground")
g2 = guide(g1, vanishing((0.0, 0.0, -1.0)),
           [(1600.0, 230.0), (1600.0, 840.0)], "across")
g3 = guide(g2, vanishing((0.0, 1.0, 0.0)),
           [(500.0, 300.0), (1400.0, 320.0)], "vertical")

s = nuke.createNode("dhPerspSolve", inpanel=False)
s.setInput(0, g3)
for n in nuke.allNodes():
    n.setSelected(False)
dhPersp.on_knob_changed(
    s, type("IC", (), {"name": staticmethod(lambda: "inputChange")})())
s["camera_height"].setValue(5.5)
s["cellsize"].setValue(2.0)
ground = s.node("groundxz")


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def shear():
    """How far the drawn floor is from being an honest map of its own plane.

    Returns the worst disagreement, as a fraction, between the real distance
    between two ground points and the distance the floor's own two channels
    say is between them, along with how many pixels went into the answer.
    """
    f = s["_f"].value()
    px, py = s["_px"].value(), s["_py"].value()
    hh = s["camera_height"].value() - s["gridoffset"].value()[1]
    nrm = [s[k].value() for k in ("_nx", "_ny", "_nz")]
    pts = []
    for x in (200, 620, 1040, 1460, 1820):
        for y in (30, 130, 260, 400):
            if nuke.sample(ground, "blue", x + 0.5, y + 0.5) >= 0:
                continue                             # above the horizon
            r = nuke.sample(ground, "red", x + 0.5, y + 0.5)
            gg = nuke.sample(ground, "green", x + 0.5, y + 0.5)
            d = ((x + 0.5 - px) / f, (y + 0.5 - py) / f, -1.0)
            dd = dot(d, nrm)
            if abs(dd) < 1e-9:
                continue
            pts.append(((r, gg), [(-hh / dd) * v for v in d]))
    worst = 0.0
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            (ra, rb), pa = pts[i]
            (sa, sb), pb = pts[j]
            real = math.sqrt(sum((pa[k] - pb[k]) ** 2 for k in range(3)))
            if real < 1e-6:
                continue
            worst = max(worst, abs(math.hypot(ra - sa, rb - sb) - real) / real)
    return worst, len(pts)


# ------------------------------- 93. the floor agrees with the plane it draws
print("\n=== 93. the floor's own coordinates are honest on its own plane ===")
worst, npts = shear()
check("there is ground in frame to measure", npts >= 12,
      "%d ground pixels" % npts)
check("an automatic solve draws an honest floor", worst < 1e-4,
      "worst %.4f%% over %d pixels" % (100.0 * worst, npts))

# The focal length an automatic solve picks is the one that makes the two level
# rays perpendicular, so on that path the raw rays and the plane frame are the
# same vectors and this can never catch anything. Every case below sets the
# focal from outside, which is where the shear used to come from.
s["use_known_focal"].setValue(True)
for mm, was in ((24.0, 10.5), (35.0, None), (50.0, None), (85.0, 66.3)):
    s["known_focal"].setValue(mm)
    worst, npts = shear()
    detail = "worst %.4f%% over %d pixels" % (100.0 * worst, npts)
    if was is not None:
        detail += ", used to be %.1f%%" % was
    check("I know the focal length: %d mm draws an honest floor" % mm,
          worst < 1e-4 and npts >= 12, detail)

# ---------------------------------------- 94. and it is the frame, not luck
print("\n=== 94. because the floor is drawn with the in plane frame ===")
s["known_focal"].setValue(85.0)


def ang(a, b):
    c = dot(a, b) / (math.sqrt(dot(a, a)) * math.sqrt(dot(b, b)))
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


nrm = [s[k].value() for k in ("_nx", "_ny", "_nz")]
a1 = [s[k].value() for k in ("_a1x", "_a1y", "_a1z")]
a2 = [s[k].value() for k in ("_a2x", "_a2y", "_a2z")]
u1 = [s[k].value() for k in ("_u1x", "_u1y", "_u1z")]
u2 = [s[k].value() for k in ("_u2x", "_u2y", "_u2z")]
check("this case really is one where the raw rays are not square, or the "
      "checks above prove nothing", abs(ang(a1, a2) - 90.0) > 5.0,
      "the two rays are %.2f deg apart and %.2f deg out of the plane"
      % (ang(a1, a2), 90.0 - ang(a1, nrm)))
check("the frame the floor draws with is square and lies in the plane",
      abs(ang(u1, u2) - 90.0) < 1e-3 and abs(ang(u1, nrm) - 90.0) < 1e-3
      and abs(ang(u2, nrm) - 90.0) < 1e-3,
      "%.4f deg apart, %.4f and %.4f deg off the normal"
      % (ang(u1, u2), ang(u1, nrm), ang(u2, nrm)))

expr = s.node("groundxz")["expr0"].value() + s.node("groundxz")["expr1"].value()
mask = (s.node("gridmask")["temp_expr0"].value()
        + s.node("gridmask")["temp_expr1"].value())
check("the floor's two coordinates read the frame, not the raw rays",
      "_u1" in expr and "_u2" in expr and "_a1" not in expr
      and "_a2" not in expr, "")
check("and so does the spacing the fade is judged on, or the two disagree",
      "_u1" in mask and "_u2" in mask and "_a1" not in mask
      and "_a2" not in mask, "")

# ------------------------------------- 95. and none of this moved the solve
print("\n=== 95. none of which is allowed to move the camera ===")
s["use_known_focal"].setValue(False)
before = (s["cam_focal"].value(), s["cam_rx"].value(), s["cam_ry"].value(),
          s["cam_rz"].value())
# In pixels, which is what the plate was actually built with. Millimeters
# depend on the camera's aperture settings and would be testing those.
check("the solve still finds the lens the plate was built with",
      abs(s["_f"].value() - FOCAL_PX) < 1.0,
      "%.2f px against %.0f, which is %.2f mm"
      % (s["_f"].value(), FOCAL_PX, before[0]))
s["cellsize"].setValue(7.0)
s["gridoffset"].setValue([3.0, 0.0, -4.0])
after = (s["cam_focal"].value(), s["cam_rx"].value(), s["cam_ry"].value(),
         s["cam_rz"].value())
check("moving the grid does not move the camera",
      all(abs(a - b) < 1e-9 for a, b in zip(before, after)),
      "%.4f mm, %.4f / %.4f / %.4f deg" % after)

print("\n" + "=" * 88)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 21: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
