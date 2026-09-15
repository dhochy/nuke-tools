"""Part twenty two: a refused solve gives you a floor you can push into place.

Two complaints had to be answered at once here, and for a while they looked
opposed.

The first was David's, on his first real plate. The node drew a grid lying on
the ground and a horizon across the frame, he read the picture rather than the
paragraph, and concluded it had solved. It had not: the guides described no
camera, and the number underneath was 0.56 mm.

Build 30 answered that by drawing nothing at all when the solve is refused,
which answered it and created the second complaint. An empty viewer is a dead
end. What he wants from a plate the geometry cannot solve is a floor he can push
into place by hand, which is a perfectly reasonable thing to want.

Both are satisfied once you notice that the problem was never that a floor
existed. It was what the floor was built from. _fsolved on a refused solve is
not a solve: it is the clamp inside sqrt(max(_fsq, ...)), a floor value, and a
grid built on it is not so much wrong as meaningless. So the fallback is the
assumption instead of the clamp. _f takes the number already sitting in
"focal (mm)" at the top of the Camera Solve tab, the guides set the orientation
around it, and the verdict says in words that this is an assumption and which
knob moves it.

That only became usable in build 29. A focal that does not come from the
geometry leaves the two level rays neither perpendicular nor in the ground
plane, so a floor drawn from them shears; drawn from the orthonormal frame the
cells stay square whatever the assumption is. Part 21 covers that directly, and
it is checked here too, because if it were not true the fallback would be
handing him a grid of rhombi to fight with.
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
ground = s.node("groundxz")


def horizon_y(x):
    """Where the horizon really is at that column.

    It runs through both vanishing points and those are rarely at the same
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


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def shear():
    """How far the drawn floor is from being an honest map of its own plane.

    Honest coordinates on a plane are an isometry, so the real distance between
    two ground points and the distance the floor's own two channels imply are
    the same number. None of the node's own working is trusted to answer this:
    the hit points come from the lens.
    """
    f = s["_f"].value()
    px, py = s["_px"].value(), s["_py"].value()
    hh = s["camera_height"].value() - s["gridoffset"].value()[1]
    nrm = [s[k].value() for k in ("_nx", "_ny", "_nz")]
    pts = []
    for x in (200, 620, 1040, 1460, 1820):
        for y in (30, 130, 260, 400):
            if nuke.sample(ground, "blue", x + 0.5, y + 0.5) >= 0:
                continue
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


GOOD = ([-1500.0, 600.0], [3700.0, 567.0])
SAME_WAY = ([820.0, 600.0], [880.0, 601.0])


def put(vps):
    s["vp1"].setValue(vps[0])
    s["vp2"].setValue(vps[1])


# ------------------------------------------- 96. a solve that stands up draws
print("\n=== 96. a solve that stands up draws its own answer ===")
put(GOOD)
good = drawn()
good_focal = s["cam_focal"].value()
check("the solve stands up", s["_solveok"].value() > 0.5,
      "%.2f mm" % good_focal)
check("its floor is drawn", good[0] > 100, "%d pixels of grid" % good[0])
check("its horizon is drawn", good[1] > 0, "%d of 12 samples" % good[1])
check("and the focal is the solved one, not the box",
      abs(good_focal - s["known_focal"].value()) > 1.0,
      "solved %.2f mm, the box says %.2f"
      % (good_focal, s["known_focal"].value()))

# ---------------------------- 97. a refused one falls back to the assumption
print("\n=== 97. a refused solve draws from the assumption, not the clamp ===")
put(SAME_WAY)
check("this really is refused, or the rest of this proves nothing",
      s["_solveok"].value() < 0.5, "_fsq %.4g" % s["_fsq"].value())
cam = s.node("cam")
clamp_mm = (math.sqrt(s["_fmin"].value())
            * math.hypot(cam["haperture"].value(), cam["vaperture"].value())
            / math.hypot(float(W), float(H)))
check("the focal shown is the number in the box, not the clamp",
      abs(s["cam_focal"].value() - s["known_focal"].value()) < 0.01,
      "shows %.2f mm, box %.2f, the clamp would have been %.2f"
      % (s["cam_focal"].value(), s["known_focal"].value(), clamp_mm))
check("and the clamp really is the useless number it is being spared",
      clamp_mm < 2.0, "%.2f mm" % clamp_mm)
bad = drawn()
check("the floor is drawn, so there is something to work with",
      bad[0] > 100, "%d pixels of grid" % bad[0])
check("and the horizon with it", bad[1] > 0, "%d of 12 samples" % bad[1])

# ------------------------------------------------ 98. and it is adjustable
print("\n=== 98. and the box moves it, which is the whole point ===")
worst, npts = shear()
check("the floor it draws is square, or he would be fighting rhombi",
      worst < 1e-4 and npts >= 12,
      "worst %.4f%% over %d pixels" % (100.0 * worst, npts))
at35 = drawn()
s["known_focal"].setValue(85.0)
check("the focal follows the box", abs(s["cam_focal"].value() - 85.0) < 0.01,
      "%.2f mm" % s["cam_focal"].value())
at85 = drawn()
check("and the floor moves with it", at85 != at35,
      "%d pixels of grid at 35, %d at 85" % (at35[0], at85[0]))
worst, npts = shear()
check("still square at the other end of the range", worst < 1e-4,
      "worst %.4f%% over %d pixels" % (100.0 * worst, npts))
s["known_focal"].setValue(35.0)
check("and putting the box back puts the picture back", drawn() == at35, "")

# ------------------------------------------- 99. the panel says which it is
print("\n=== 99. the panel says which of the two it is showing ===")
dhPersp.set_verdict(s)
said = s["verdict"].value()
check("the verdict still says the guides describe no camera",
      "do not describe a camera" in said, said[:58])
check("and that the number is an assumption rather than a solve",
      "not a solve" in said and "assumption" in said, "")
check("and names the knob that moves it", "focal (mm)" in said, "")
put(GOOD)
dhPersp.set_verdict(s)
check("a solve that stands up says none of that",
      "assumption" not in s["verdict"].value(), "")

# ------------------------------------------ 100. and nothing was left behind
print("\n=== 100. and a good solve draws exactly what it drew before ===")
back = drawn()
check("nothing about being refused leaves a mark on the next good solve",
      back == good and abs(s["cam_focal"].value() - good_focal) < 1e-9,
      "%d and %d at %.2f mm, against %d and %d at %.2f"
      % (back[0], back[1], s["cam_focal"].value(),
         good[0], good[1], good_focal))
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
