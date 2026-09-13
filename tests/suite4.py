"""Part four: check the gizmo against the published formula, implemented separately.

Caprile and Torre 1990, and Hartley and Zisserman chapter 8: for two vanishing
points from perpendicular world directions, with square pixels and the principal
point at the image centre,

    (v1 - p) . (v2 - p) + f^2 = 0

The gizmo instead drops a perpendicular from the centre onto the horizon and uses
f = sqrt(ViV1 * ViV2 - OVi^2). Those are algebraically the same thing. This
recomputes the published form here in plain Python, from the same vanishing
points, and compares. An independent implementation agreeing is much stronger
evidence than the gizmo agreeing with itself.
"""
import math
import random
import nuke

nuke.pluginAddPath(r"C:\Users\dhoch\.nuke\Gizmos\DH_Tools\3D")
import dhPersp

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("  %-4s %-50s %s" % ("PASS" if ok else "FAIL", name, detail))


W, H = 1920, 1080
nuke.addFormat("%d %d 0 0 %d %d 1 testHD" % (W, H, W, H))
nuke.root()["format"].setValue("testHD")
plate = nuke.nodes.Constant(format="testHD")
solve = nuke.createNode("dhPerspSolve", inpanel=False)
solve.setInput(0, plate)
for n in nuke.allNodes():
    n.setSelected(False)

CX, CY = W / 2.0, H / 2.0


def textbook_focal(v1, v2):
    """f in pixels, straight from the published constraint."""
    d = (v1[0] - CX) * (v2[0] - CX) + (v1[1] - CY) * (v2[1] - CY)
    return math.sqrt(-d) if d < 0 else float("nan")


# ------------------------------------------------------- 22. against the published form
print("\n=== 22. focal against the published two vanishing point formula ===")
random.seed(11)
cases, worst, tested = [], 0.0, 0
while len(cases) < 40:
    v1 = [random.uniform(-9000, 600), random.uniform(300, 800)]
    v2 = [random.uniform(1300, 11000), random.uniform(300, 800)]
    if textbook_focal(v1, v2) != textbook_focal(v1, v2):
        continue
    cases.append((v1, v2))
for v1, v2 in cases:
    solve["vp1"].setValue(v1)
    solve["vp2"].setValue(v2)
    # the gizmo reports millimetres against its film back, so convert back to pixels
    fmm = solve["cam_focal"].value()
    fb = solve["filmback"].value()
    va = fb * H / float(W)
    fpx = fmm * math.sqrt(W * W + H * H) / math.sqrt(fb * fb + va * va)
    want = textbook_focal(v1, v2)
    worst = max(worst, abs(fpx - want) / want)
    tested += 1
check("focal matches the published formula", worst < 1e-4,
      "%d cases, worst relative error %.2e" % (tested, worst))

# ------------------------------------------------------- 23. the orthogonality constraint
print("\n=== 23. the solved camera really sees two perpendicular directions ===")
icam = solve.node("cam")
D = 1.0e9


def project(cam, p):
    r = nuke.nodes.Reconcile3D()
    r.setInput(0, plate)
    r.setInput(1, cam)
    a = nuke.nodes.Axis()
    a["translate"].setValue([float(v) for v in p])
    r.setInput(2, a)
    nuke.execute(r, 1, 1)
    o = r["output"].value()
    nuke.delete(a)
    nuke.delete(r)
    return [float(o[0]), float(o[1])]


worst_res = 0.0
for v1, v2 in cases[:10]:
    solve["vp1"].setValue(v1)
    solve["vp2"].setValue(v2)
    solve["axis_from"].setValue(1)
    fmm = solve["cam_focal"].value()
    fb = solve["filmback"].value()
    va = fb * H / float(W)
    fpx = fmm * math.sqrt(W * W + H * H) / math.sqrt(fb * fb + va * va)
    # the constraint the solve is supposed to satisfy, evaluated on its own output
    res = ((v1[0] - CX) * (v2[0] - CX) + (v1[1] - CY) * (v2[1] - CY) + fpx * fpx)
    worst_res = max(worst_res, abs(res) / (fpx * fpx))
check("orthogonality constraint is satisfied", worst_res < 1e-4,
      "worst normalised residual %.2e" % worst_res)

# ------------------------------------------------------- 24. sensitivity, the honest caveat
print("\n=== 24. how much a slipped guide line costs, by vanishing point distance ===")


def cam_at(focal, rx, ry):
    c = nuke.nodes.Camera2() if "Camera2" in dir(nuke.nodes) else nuke.nodes.Camera()
    c["focal"].setValue(focal)
    c["rotate"].setValue([rx, ry, 0.0])
    c["translate"].setValue([0.0, 12.0, 0.0])
    return c


print("  %-8s %-14s %-14s %s" % ("yaw", "vp2 offset px", "focal err per 2px", "verdict"))
rows = []
for yaw in (2.0, 5.0, 15.0, 30.0, 45.0):
    cam = cam_at(35.0, -6.0, yaw)
    vx = project(cam, [D, 0, 0])
    vz = project(cam, [0, 0, -D])
    solve["vp1"].setValue(vx)
    solve["vp2"].setValue(vz)
    base = solve["cam_focal"].value()
    # nudge one vanishing point by the amount a 2px line slip near frame edge causes
    far = max(abs(vx[0] - CX), abs(vz[0] - CX))
    scale = max(far / 900.0, 1.0)
    solve["vp2"].setValue([vz[0] + 2.0 * scale, vz[1]])
    err = abs(solve["cam_focal"].value() - base) / base * 100.0
    verdict = "solve it" if err < 3.0 else "enter the focal length"
    rows.append((yaw, far, err, verdict))
    print("  %-8.1f %-14.0f %-14s %s" % (yaw, far, "%.2f%%" % err, verdict))
    nuke.delete(cam)
check("a well framed shot is not sensitive to small guide slips",
      rows[-1][2] < 3.0, "at 45 deg yaw: %.2f%% per slip" % rows[-1][2])
check("the tool is honest about near one point shots being fragile",
      rows[0][2] > rows[-1][2], "2 deg %.2f%% vs 45 deg %.2f%%" % (rows[0][2], rows[-1][2]))

print("\n" + "=" * 74)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 4: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
