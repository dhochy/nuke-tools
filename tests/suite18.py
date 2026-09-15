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
slot looks like. What an older node loads as is part 19's problem now: it comes
back attached to the vanishing point, which is what it always was.
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
g["pin1"].setValue(False)
check("and even freed it weighs nothing, because it has no length",
      abs(g["_Lw3"].value()) < 1e-12, "weight %.3g" % g["_Lw3"].value())
g["pin1"].setValue(True)

g["pin1"].setValue(False)          # free it first: unticking places B
g["add1b"].setValue(list(g["add1"].value()))     # now make it genuinely zero length
before = tuple(g["vp"].value())
g["use_add1"].setValue(True)
after = tuple(g["vp"].value())
check("switching on a slot with no length changes nothing",
      abs(after[0] - before[0]) < 1e-6 and abs(after[1] - before[1]) < 1e-6,
      "%s against %s" % (str(after), str(before)))
g["use_add1"].setValue(False)
g["pin1"].setValue(True)

# ------------------------------------------------ 77. adding a line
print("\n=== 77. add line gives you both ends, aimed where the others are ===")
g2 = new_guide()
for k, v in zip(("p1a", "p1b", "p2a", "p2b"), A):
    g2[k].setValue(list(v))
vp0 = tuple(g2["vp"].value())
i = dhPersp.add_line(g2)
# it arrives attached, which is the safe half; this section is about the line
g2["pin%d" % i].setValue(False)
dhPersp.on_knob_changed(g2, type("K", (), {
    "name": staticmethod(lambda: "pin%d" % i)})())
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
        # a slot built by hand comes up attached, which is inert on purpose; this
        # section is about lines that vote
        gg["pin%d" % slot].setValue(False)
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

# Section 79 was about converting an older node's added lines, which had a
# point A and no point B. The per line switch removed the need: an older
# line comes back attached, which is what it was, and its point B is never
# consulted until the switch is unticked. Part 19 covers that.

# --------------------------------- 80. the handle has to be reachable
print("\n=== 80. point B is placed where you can actually get at it ===")
off = 0
short = 0
for vpos in ((-1500.0, 600.0), (3700.0, 567.0), (-120000.0, 500.0),
             (PX, 100000.0), (300.0, 400.0)):
    gp = new_guide()
    gp["p1a"].setValue([W * 0.2, H * 0.2]); gp["p1b"].setValue(list(vpos))
    gp["p2a"].setValue([W * 0.8, H * 0.3]); gp["p2b"].setValue(list(vpos))
    for k in range(1, 7):
        dhPersp.add_line(gp)
        pa = gp["add%d" % k].value()
        pb = gp["add%db" % k].value()
        if not (0 <= pb[0] <= W and 0 <= pb[1] <= H):
            off += 1
        if math.hypot(pb[0] - pa[0], pb[1] - pa[1]) < 20.0:
            short += 1
    nuke.delete(gp)
check("every added line puts B inside the frame, wherever the vanishing point is",
      off == 0, "%d off canvas out of 30" % off)
check("and long enough to be a line rather than a dot", short == 0,
      "%d too short" % short)

# A B that is already off the picture is pulled back along its own line. Sliding
# a point along the line it defines does not change the line, so this must leave
# the answer untouched, which is the thing to check about a function that edits
# guide points on load.
gt = new_guide()
for k, v0 in zip(("p1a", "p1b", "p2a", "p2b"), A):
    gt[k].setValue(list(v0))
# Free it first. Unticking runs release_line, which places B, so a B set before
# the untick is the one thing that cannot survive to be tested.
gt["pin1"].setValue(False)
gt["use_add1"].setValue(True)
gt["add1"].setValue([300.0, 400.0])
gt["add1b"].setValue([9000.0, 2600.0])            # miles off the picture
was = tuple(gt["vp"].value())
moved = dhPersp.tidy_extra_lines(gt)
pb = gt["add1b"].value()
check("an unreachable B is brought back into frame",
      moved == [1] and 0 <= pb[0] <= W and 0 <= pb[1] <= H,
      "B now %s" % [round(v) for v in pb])
cross = abs((9000.0 - 300.0) * (pb[1] - 400.0) - (2600.0 - 400.0) * (pb[0] - 300.0))
span = math.hypot(9000.0 - 300.0, 2600.0 - 400.0) * \
    max(math.hypot(pb[0] - 300.0, pb[1] - 400.0), 1e-9)
check("it stayed on the same line", cross / span < 1e-9,
      "off the line by %.3g" % (cross / span))
now = tuple(gt["vp"].value())
# The line got 99.8% shorter, and every normalized sum behind the fit moved by
# about three parts in 1e16, which is the last bit of a double. Comparing two
# numbers near a million with == asks for more than that. Direction is also the
# honest measure here: this fit is in its far form, where the point stands in for
# a direction and its distance is arbitrary.
was_dir = math.degrees(math.atan2(was[1] - PY, was[0] - PX))
now_dir = math.degrees(math.atan2(now[1] - PY, now[0] - PX))
check("so the answer did not move", abs(now_dir - was_dir) < 1e-9,
      "direction %.9f against %.9f deg" % (now_dir, was_dir))
check("and the line it came from really did change length, so that was not a "
      "no-op", abs(gt["_Ln3"].value() - 80530000.0) > 1e6,
      "%.0f against 80530000" % gt["_Ln3"].value())
check("a B that is already in frame is left alone",
      dhPersp.tidy_extra_lines(gt) == [], "")

print("\n" + "=" * 88)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 18: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
