"""Part twenty: square cells, a far half that does not alias, and a floor you can move.

Three things David found by looking at his own plates.

The cells came out as diamonds. The two ground directions are perpendicular only
when the focal length is the one that makes them so, and that used to be
guaranteed because the focal was solved FROM that pair. It is not any more: on a
facade the focal comes from a vertical pair instead, so nothing forced the ground
square. One Gram-Schmidt step does: keep the better conditioned direction, derive
the other perpendicular to it in the same plane.

The far half was a band of moire and then a slab of solid. The mask asks how far
this pixel is from the nearest line, which is the right question only while the
lines are more than a pixel apart. Closer than that, several land in one pixel and
counting the nearest throws the rest away, which is exactly what moire is. Down
there the answer is the fraction of ground the lines cover, which cannot alias
because it does not depend on where the sample fell.

And the grid offset's Y did nothing. It raises and lowers the ground now.
"""
import math
import nuke

nuke.pluginAddPath(r"C:\Users\dhoch\.nuke\Gizmos\DH_Tools\3D")
import dhPersp

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("  %-4s %-62s %s" % ("PASS" if ok else "FAIL", name, detail))


W, H = 667, 1000
nuke.addFormat("%d %d 0 0 %d %d 1 rome" % (W, H, W, H))
nuke.root()["format"].setValue("rome")
plate = nuke.nodes.Constant(format="rome", color=0.2)
s = nuke.createNode("dhPerspSolve", inpanel=False)
s.setInput(0, plate)
s["camera_height"].setValue(5.5)
s["cellsize"].setValue(2.0)
ground, mask = s.node("groundxz"), s.node("gridmask")


def g(k):
    return float(s[k].value())


def angle(ax, ay, az, bx, by, bz):
    d = max(-1.0, min(1.0, ax * bx + ay * by + az * bz))
    return math.degrees(math.acos(d))


def raw_angle():
    return angle(g("_a1x"), g("_a1y"), g("_a1z"), g("_a2x"), g("_a2y"), g("_a2z"))


def drawn_angle():
    return angle(g("_u1x"), g("_u1y"), g("_u1z"), g("_u2x"), g("_u2y"), g("_u2z"))


# --------------------------------------------------- 88. the cells are square
print("\n=== 88. the floor's two directions are square, whatever the solve did ===")
CASES = [("a proper two point shot", (-1500.0, 600.0), (3700.0, 567.0),
          (400.0, 60000.0)),
         ("a facade, across far off", (300.0, 420.0), (72000.0, 430.0),
          (330.0, 14000.0)),
         ("a facade, across further", (280.0, 415.0), (-136000.0, 425.0),
          (330.0, 13500.0))]
skewed = 0
for nm, a, b, v in CASES:
    s["vp1"].setValue(list(a))
    s["vp2"].setValue(list(b))
    s["vp3"].setValue(list(v))
    for use in (False, True):
        s["use_vertical"].setValue(use)
        raw, drawn = raw_angle(), drawn_angle()
        if abs(raw - 90.0) > 0.5:
            skewed += 1
        check("%s%s: the floor is square" % (nm, " + vertical" if use else ""),
              abs(drawn - 90.0) < 1e-4,
              "vanishing points give %.3f deg, floor drawn at %.4f deg"
              % (raw, drawn))
check("and at least one of those really was skewed, or this proves nothing",
      skewed >= 1, "%d of %d cases" % (skewed, 2 * len(CASES)))

# where the pair is already perpendicular, nothing may change
s["vp1"].setValue([-1500.0, 600.0])
s["vp2"].setValue([3700.0, 567.0])
s["use_vertical"].setValue(False)
check("a pair that is already perpendicular is left exactly alone",
      abs(g("_u1x") - g("_a1x")) < 1e-9 and abs(g("_u2x") - g("_a2x")) < 1e-9,
      "raw %.3f deg" % raw_angle())
check("it keeps whichever direction is better conditioned",
      (g("_keep1") > 0.5) == (g("_rr1") <= g("_rr2")),
      "kept %s, distances %.0f and %.0f"
      % ("vp1" if g("_keep1") > 0.5 else "vp2", g("_rr1"), g("_rr2")))

# ------------------------------------------- 89. the far half does not alias
print("\n=== 89. where the lines close up, coverage replaces nearest-line ===")
s["vp1"].setValue([760.0, 330.0])       # a street, camera nearly level
s["vp2"].setValue([-9000.0, 300.0])
s["use_vertical"].setValue(False)
s["cellsize"].setValue(1.0)
s["fade_far"].setValue(False)
hz = 0.5 * (s["vp1"].value()[1] + s["vp2"].value()[1])


def spacing_at(x, y):
    """The two families' line spacing in pixels, from the node's own numbers."""
    b = nuke.sample(ground, "blue", x + 0.5, y + 0.5)
    out = []
    for val, ux, uy in ((nuke.sample(ground, "red", x + 0.5, y + 0.5),
                         g("_u1x"), g("_u1y")),
                        (nuke.sample(ground, "green", x + 0.5, y + 0.5),
                         g("_u2x"), g("_u2y"))):
        hgt = g("camera_height") - s["gridoffset"].value()[1]
        grad = math.hypot(ux + val * g("_nx") / hgt, uy + val * g("_ny") / hgt)
        out.append(g("cellsize") * g("_f") * abs(b) / max(hgt * grad, 1e-12))
    return min(out)


def biggest_jump(y):
    v = [nuke.sample(mask, "red", x + 0.5, y + 0.5) for x in range(40, W - 40)]
    return max(abs(v[i + 1] - v[i]) for i in range(len(v) - 1))


print("     row        line spacing   biggest jump between neighbors")
worst = 0.0
tested = 0
for d in (20, 40, 60, 80):
    y = int(hz) - d
    sp = spacing_at(W // 2, y)
    jump = biggest_jump(y)
    print("   %3d under hz    %7.2f px      %6.3f" % (d, sp, jump))
    if sp < 1.0:
        tested += 1
        worst = max(worst, jump)
check("there are rows where the lines are closer than a pixel", tested >= 3,
      "%d rows" % tested)
check("and there the picture is smooth, which is what stops it aliasing",
      worst < 0.02, "biggest neighbor jump %.4f" % worst)

# further down, where the lines are separate, it must still draw crisp lines
far = int(hz) - 260
check("further down, where the lines are separate, they are still crisp",
      biggest_jump(far) > 0.5,
      "spacing %.1f px, jump %.3f" % (spacing_at(W // 2, far), biggest_jump(far)))

# ---------------------------------------------- 90. the offset moves the floor
print("\n=== 90. grid offset Y raises and lowers the ground ===")
s["cellsize"].setValue(2.0)
s["gridoffset"].setValue([0.0, 0.0, 0.0])


def dist_at(x=333, y=120):
    return nuke.sample(ground, "red", x + 0.5, y + 0.5)


base = dist_at()
hz_row = int(hz)
s["gridoffset"].setValue([0.0, 2.0, 0.0])
nearer = dist_at()
s["gridoffset"].setValue([0.0, -2.0, 0.0])
further = dist_at()
s["gridoffset"].setValue([0.0, 0.0, 0.0])
check("raising the ground brings it nearer", nearer < base,
      "%.2f against %.2f" % (nearer, base))
check("lowering it pushes it away", further > base,
      "%.2f against %.2f" % (further, base))
check("and it is exactly the height above the plane that changed",
      abs(nearer / base - (5.5 - 2.0) / 5.5) < 1e-3,
      "ratio %.4f, want %.4f" % (nearer / base, (5.5 - 2.0) / 5.5))

# the horizon is where the ground goes at infinity, so moving the plane up or
# down cannot move it
s["gridoffset"].setValue([0.0, 3.0, 0.0])
above = nuke.sample(ground, "blue", 333.5, hz_row + 20.5)
below = nuke.sample(ground, "blue", 333.5, hz_row - 20.5)
check("the horizon does not move when the ground does",
      above >= 0.0 and below < 0.0, "D above %.4f, below %.4f" % (above, below))
s["gridoffset"].setValue([0.0, 0.0, 0.0])

# X and Z still slide the lines along the ground rather than moving the ground
was = dist_at()
s["gridoffset"].setValue([4.0, 0.0, -3.0])
check("X and Z leave the ground where it is, they slide the lines on it",
      abs(dist_at() - was) < 1e-6, "%.4f against %.4f" % (dist_at(), was))
s["gridoffset"].setValue([0.0, 0.0, 0.0])

print("\n" + "=" * 88)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 20: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
