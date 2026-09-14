"""Part eighteen: added lines have two points and feed the vanishing point.

An added line used to be one handle, drawn out from the vanishing point through
it. It could only pivot and it contributed nothing. Now it is a real line with a
point A and a point B, and the vanishing point is fitted from every line on the
node that has length.

Three things have to hold.

Two lines must give exactly what they gave before, to the last decimal, because a
least squares fit through two lines passes through both of them. Anything else
would mean every existing guide moved.

More lines must actually help. Measured the way part seventeen measures: real
edges projected through a real camera with their ends landed on whole pixels,
which is the error a person tracing by eye actually makes.

And a line with no length must weigh nothing, because that is what an unplaced
slot looks like and what a node from an older build loads as.
"""
import math
import nuke

nuke.pluginAddPath(r"C:\Users\dhoch\.nuke\Gizmos\DH_Tools\3D")
import dhPersp

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("  %-4s %-62s %s" % ("PASS" if ok else "FAIL", name, detail))


IC = type("IC", (), {"name": staticmethod(lambda: "inputChange")})()
W, H = 667, 1000
nuke.addFormat("%d %d 0 0 %d %d 1 rome" % (W, H, W, H))
nuke.root()["format"].setValue("rome")
plate = nuke.nodes.Constant(format="rome")
DIAG = math.hypot(W, H)
FILMBACK = 24.576
VA = FILMBACK * H / float(W)
F_PX = 35.0 * DIAG / math.hypot(FILMBACK, VA)
PX, PY = W / 2.0, H / 2.0
HEIGHT = 5.5


def new_guide():
    for n in nuke.allNodes():
        n.setSelected(False)
    g = nuke.createNode("dhPerspGuide", inpanel=False)
    g.setInput(0, plate)
    dhPersp.on_knob_changed(g, IC)
    return g


def intersect(a, b, c, d):
    x1, y1 = a
    x2, y2 = b
    x3, y3 = c
    x4, y4 = d
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    p = x1 * y2 - y1 * x2
    q = x3 * y4 - y3 * x4
    return ((p * (x3 - x4) - (x1 - x2) * q) / den,
            (p * (y3 - y4) - (y1 - y2) * q) / den)


# ------------------------------------------------ 76. two lines are unchanged
print("\n=== 76. two lines still give exactly their intersection ===")
g = new_guide()
A = [(1500.0, 900.0), (300.0, 780.0), (1500.0, 200.0), (300.0, 360.0)]
for k, v in zip(("p1a", "p1b", "p2a", "p2b"), A):
    g[k].setValue(list(v))
want = intersect(A[0], A[1], A[2], A[3])
got = g["vp"].value()
check("the fitted point is the intersection, to nine decimals",
      abs(got[0] - want[0]) < 1e-9 * max(1, abs(want[0]))
      and abs(got[1] - want[1]) < 1e-9 * max(1, abs(want[1])),
      "(%.9f, %.9f) against (%.9f, %.9f)" % (got[0], got[1], want[0], want[1]))

check("every slot has a point B now",
      all("add%db" % i in g.knobs() for i in range(1, 13)), "")
check("an unused slot's two points sit on top of each other, so it is not a line",
      g["add1"].value() == g["add1b"].value(), str(g["add1"].value()))
check("and it weighs nothing", abs(g["_Lw3"].value()) < 1e-12,
      "weight %.3g" % g["_Lw3"].value())

before = tuple(g["vp"].value())
g["use_add1"].setValue(True)
check("switching on a slot with no length changes nothing",
      tuple(g["vp"].value()) == before, str(g["vp"].value()))
g["use_add1"].setValue(False)

# ------------------------------------------------ 77. adding a line
print("\n=== 77. add line gives you both ends, aimed where the others are ===")
g2 = new_guide()
for k, v in zip(("p1a", "p1b", "p2a", "p2b"), A):
    g2[k].setValue(list(v))
vp0 = tuple(g2["vp"].value())
i = dhPersp.add_line(g2)
check("a slot was taken", i == 1, str(i))
a, b = g2["add1"].value(), g2["add1b"].value()
check("both ends were placed apart", math.hypot(b[0] - a[0], b[1] - a[1]) > 10.0,
      "A %s  B %s" % ([round(v) for v in a], [round(v) for v in b]))
check("both ends are visible in the panel",
      g2["add1"].visible() and g2["add1b"].visible(), "")
# the new line starts out aimed at the vanishing point, so it should not move it
moved = math.hypot(g2["vp"].value()[0] - vp0[0], g2["vp"].value()[1] - vp0[1])
check("a new line starts out aimed where the others are, so it does not move "
      "the answer", moved < 0.5, "moved %.4f px" % moved)
check("and it is drawn: its two points make a real line",
      g2["_Lw3"].value() > 0, "weight %.3g" % g2["_Lw3"].value())

# ------------------------------------------- 78. more lines, traced by eye
print("\n=== 78. more lines beat two, on lines traced to the pixel ===")


def camera_rows(pitch, yaw):
    cam = nuke.nodes.Camera2() if "Camera2" in dir(nuke.nodes) else nuke.nodes.Camera()
    cam["rotate"].setValue([pitch, yaw, 0.0])
    cam["translate"].setValue([0.0, HEIGHT, 0.0])
    wm = cam["world_matrix"].getValue()
    nuke.delete(cam)
    return [tuple(wm[0:3]), tuple(wm[4:7]), tuple(wm[8:11])]


def project(rows, w, snap=True):
    d = (w[0], w[1] - HEIGHT, w[2])
    c = [sum(rows[i][j] * d[i] for i in range(3)) for j in range(3)]
    if c[2] >= -1e-9:
        return None
    p = (PX + F_PX * c[0] / (-c[2]), PY + F_PX * c[1] / (-c[2]))
    return (round(p[0]), round(p[1])) if snap else p


ROWS = camera_rows(-4.0, 0.4)                 # the facade case
# six horizontal edges along world X at different heights on the wall
EDGES = [((-6.0, y, -25.0), (6.0, y, -25.0))
         for y in (11.0, 9.5, 8.0, 6.5, 5.0, 3.5)]
traced = [(project(ROWS, e[0]), project(ROWS, e[1])) for e in EDGES]
exact = [(project(ROWS, e[0], False), project(ROWS, e[1], False)) for e in EDGES]
truth = intersect(exact[0][0], exact[0][1], exact[1][0], exact[1][1])
print("     the true vanishing point is %.0f px from center" %
      math.hypot(truth[0] - PX, truth[1] - PY))


def fit_with(n):
    gg = new_guide()
    gg["p1a"].setValue(list(traced[0][0])); gg["p1b"].setValue(list(traced[0][1]))
    gg["p2a"].setValue(list(traced[1][0])); gg["p2b"].setValue(list(traced[1][1]))
    for k in range(2, n):
        slot = k - 1
        gg["add%d" % slot].setValue(list(traced[k][0]))
        gg["add%db" % slot].setValue(list(traced[k][1]))
        gg["use_add%d" % slot].setValue(True)
    v = gg["vp"].value()
    nuke.delete(gg)
    # what matters is the DIRECTION of the vanishing point from the lens axis,
    # because that is what the solve reads; the distance out there is meaningless
    # A point a hundred thousand pixels away has a direction but no side: which
    # end of that line it is reported at is not a real quantity and the solve
    # does not read it, so the error is measured modulo a half turn.
    ang = math.degrees(math.atan2(v[1] - PY, v[0] - PX))
    tru = math.degrees(math.atan2(truth[1] - PY, truth[0] - PX))
    d = abs(((ang - tru) + 90.0) % 180.0 - 90.0)
    return v, d


errs = []
print("     lines   angle error from the true direction")
for n in (2, 3, 4, 6):
    v, d = fit_with(n)
    errs.append(d)
    print("       %d      %8.4f deg" % (n, d))
check("six traced lines beat two", errs[-1] < errs[0],
      "%.4f deg against %.4f" % (errs[-1], errs[0]))
check("and no line count is wildly worse than two, which is what an "
      "unstable fit looks like",
      max(errs) < 5.0, "%s" % [round(e, 4) for e in errs])

# ------------------------------------- 78b. lines that barely converge
print("\n=== 78b. where the lines barely converge, fit the direction ===")
gf = new_guide()
# two almost parallel lines: they meet a very long way off, and where exactly is
# not a real quantity
gf["p1a"].setValue([40.0, 300.0]); gf["p1b"].setValue([620.0, 300.2])
gf["p2a"].setValue([40.0, 500.0]); gf["p2b"].setValue([620.0, 500.1])
check("the tool knows the answer is off at infinity", gf["_Sfar"].value() > 0.5,
      "reach %.0f px, frame diagonal %.0f"
      % (gf["_Sreach"].value(), gf["_Sdiag"].value()))
v = gf["vp"].value()
check("so it reports a point a very long way along their direction",
      math.hypot(v[0] - PX, v[1] - PY) > 100 * DIAG,
      "(%.0f, %.0f)" % (v[0], v[1]))
ang = math.degrees(math.atan2(v[1] - PY, v[0] - PX)) % 180.0
check("pointing the way the lines point", abs(ang - 0.0) < 2.0 or abs(ang - 180.0) < 2.0,
      "%.3f deg from horizontal" % ang)

# nudging one line end by a pixel must not swing that direction
gf["p1b"].setValue([620.0, 303.0])
v2 = gf["vp"].value()
ang2 = math.degrees(math.atan2(v2[1] - PY, v2[0] - PX)) % 180.0
swing = abs(((ang2 - ang) + 90.0) % 180.0 - 90.0)
check("and a one pixel nudge moves it by a fraction of a degree, not by tens",
      swing < 1.0, "%.4f deg" % swing)

# a well converging pair must not be diverted into the far form
gc = new_guide()
for k, v0 in zip(("p1a", "p1b", "p2a", "p2b"), A):
    gc[k].setValue(list(v0))
check("a pair that really converges is left as the plain intersection",
      gc["_Sfar"].value() < 0.5,
      "angular error of the fit %.2g" % gc["_Sang"].value())

# the case that made three lines worse than two: caught by the angular residual,
# which is the residual divided by how far away the fit landed. Neither the
# determinant nor the raw residual separates it.
gb = new_guide()
BAD = [((14.0, 668.0), (654.0, 662.0)), ((14.0, 611.0), (654.0, 606.0)),
       ((14.0, 554.0), (654.0, 549.0))]
gb["p1a"].setValue(list(BAD[0][0])); gb["p1b"].setValue(list(BAD[0][1]))
gb["p2a"].setValue(list(BAD[1][0])); gb["p2b"].setValue(list(BAD[1][1]))
gb["add1"].setValue(list(BAD[2][0])); gb["add1b"].setValue(list(BAD[2][1]))
gb["use_add1"].setValue(True)
vb = gb["vp"].value()
angb = math.degrees(math.atan2(vb[1] - PY, vb[0] - PX)) % 180.0
check("three nearly parallel lines give a direction along them, not across them",
      abs(angb) < 3.0 or abs(angb - 180.0) < 3.0,
      "%.3f deg from horizontal, vp (%.0f, %.0f)" % (angb, vb[0], vb[1]))

# ------------------------------------------------- 79. an older node loads safe
print("\n=== 79. a guide from before this keeps its added lines ===")
g3 = new_guide()
for k, v in zip(("p1a", "p1b", "p2a", "p2b"), A):
    g3[k].setValue(list(v))
vp_base = tuple(g3["vp"].value())
# exactly what a rebuilt older node looks like: A placed, B still on its default
g3["add1"].setValue([420.0, 260.0])
g3["add1b"].setValue([1024.0, 400.0])   # the default, as a rebuild leaves it
g3["use_add1"].setValue(True)
check("its point B is sitting on the default",
      abs(g3["add1b"].value()[0] - 1024.0) < 1e-6, str(g3["add1b"].value()))
# The default is nowhere near A, so this IS a line, and left alone it would feed
# the fit and drag the answer. That is what makes converting it necessary rather
# than merely tidy, and it is what the first version of this got wrong.
check("left alone it is a line pointing at nothing, and it moves the answer",
      tuple(g3["vp"].value()) != vp_base,
      "vp %s against %s" % ([round(v) for v in g3["vp"].value()],
                            [round(v) for v in vp_base]))

done = dhPersp.migrate_extra_lines(g3)
check("loading converts it", done == [1], str(done))
a, b = g3["add1"].value(), g3["add1b"].value()
check("A is where it was", abs(a[0] - 420.0) < 1e-6 and abs(a[1] - 260.0) < 1e-6,
      str(a))
# the converted line must be the line that used to be drawn: vp through A
cross = abs((a[0] - vp_base[0]) * (b[1] - vp_base[1])
            - (a[1] - vp_base[1]) * (b[0] - vp_base[0]))
scale = math.hypot(a[0] - vp_base[0], a[1] - vp_base[1]) * \
    math.hypot(b[0] - vp_base[0], b[1] - vp_base[1])
check("and B lands on the line that used to be drawn, from the vanishing point "
      "through A", cross / max(scale, 1e-9) < 1e-6,
      "off the ray by %.3g" % (cross / max(scale, 1e-9)))
after = tuple(g3["vp"].value())
check("converting it does not move the answer either, because it was already "
      "aimed there",
      math.hypot(after[0] - vp_base[0], after[1] - vp_base[1]) < 0.5,
      "moved %.4f px" % math.hypot(after[0] - vp_base[0], after[1] - vp_base[1]))
check("running it twice does nothing the second time",
      dhPersp.migrate_extra_lines(g3) == [], "")

# the sentinel is a number written down in two places, so check they agree
fresh = new_guide()
check("dhPersp's idea of an unplaced point matches what the gizmo declares",
      math.hypot(fresh["add1b"].value()[0] - dhPersp.SLOT_DEFAULT[0],
                 fresh["add1b"].value()[1] - dhPersp.SLOT_DEFAULT[1]) < 1e-6,
      "gizmo %s, dhPersp %s" % (fresh["add1b"].value(), dhPersp.SLOT_DEFAULT))
check("and point A is declared at the same place, so an unused slot is not a line",
      math.hypot(fresh["add1"].value()[0] - dhPersp.SLOT_DEFAULT[0],
                 fresh["add1"].value()[1] - dhPersp.SLOT_DEFAULT[1]) < 1e-6,
      str(fresh["add1"].value()))

print("\n" + "=" * 88)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 18: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
