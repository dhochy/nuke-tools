"""Part eight: the third guide, and what it is actually for.

Two vanishing points can only give a focal length if you assume where the lens
axis is. This tool assumed the center of frame. The test that matters is
therefore not "does it still work on a normal plate" but "does it now work on a
plate where that assumption is false", because that is the case it was added for
and the case that silently produced wrong answers before.

So the ground truth here is a camera with a deliberately shifted lens axis, which
is what a cropped photograph is.
"""
import nuke
from math import hypot

nuke.pluginAddPath(r"C:\Users\dhoch\.nuke\Gizmos\DH_Tools\3D")
import dhPersp

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("  %-4s %-56s %s" % ("PASS" if ok else "FAIL", name, detail))


W, H = 1920, 1080
nuke.addFormat("%d %d 0 0 %d %d 1 testHD" % (W, H, W, H))
nuke.root()["format"].setValue("testHD")
plate = nuke.nodes.Constant(format="testHD")
D = 1.0e9
IC = type("IC", (), {"name": staticmethod(lambda: "inputChange")})()


def make_cam(focal, rx, ry, rz=0.0, shift=(0.0, 0.0), height=9.0):
    c = nuke.nodes.Camera2() if "Camera2" in dir(nuke.nodes) else nuke.nodes.Camera()
    c["focal"].setValue(focal)
    c["rotate"].setValue([rx, ry, rz])
    c["translate"].setValue([0.0, height, 0.0])
    if "win_translate" in c.knobs():
        c["win_translate"].setValue(list(shift))
    return c


def project(cam, p):
    r = nuke.nodes.Reconcile3D()
    r.setInput(0, plate)
    r.setInput(1, cam)
    a = nuke.nodes.Axis()
    a["translate"].setValue([float(v) for v in p])
    r.setInput(2, a)
    nuke.execute(r, 1, 1)
    o = r["output"].value()
    nuke.delete(a); nuke.delete(r)
    return [float(o[0]), float(o[1])]


def rig(with_vertical):
    a = nuke.createNode("dhPerspGuide", inpanel=False); a.setInput(0, plate)
    b = nuke.createNode("dhPerspGuide", inpanel=False); b.setInput(0, a)
    nodes = [a, b]
    v = None
    if with_vertical:
        v = nuke.createNode("dhPerspGuide", inpanel=False); v.setInput(0, b)
        v["role"].setValue("vertical")   # by label: the index has moved once
        nodes.append(v)
    s = nuke.createNode("dhPerspSolve", inpanel=False)
    s.setInput(0, nodes[-1])
    for n in nuke.allNodes():
        n.setSelected(False)
    for n in nodes:
        dhPersp.on_knob_changed(n, IC)
        n.setSelected(True)
    dhPersp.link_guides(s)
    for n in nuke.allNodes():
        n.setSelected(False)
    return a, b, v, s


def feed(a, b, v, cam):
    """Place every guide on lines that really are parallel in the world."""
    a["p1a"].setValue(project(cam, [-30.0, 0.0, -40.0]))
    a["p1b"].setValue(project(cam, [40.0, 0.0, -40.0]))
    a["p2a"].setValue(project(cam, [-30.0, 0.0, -90.0]))
    a["p2b"].setValue(project(cam, [40.0, 0.0, -90.0]))
    b["p1a"].setValue(project(cam, [-20.0, 0.0, -30.0]))
    b["p1b"].setValue(project(cam, [-20.0, 0.0, -110.0]))
    b["p2a"].setValue(project(cam, [30.0, 0.0, -30.0]))
    b["p2b"].setValue(project(cam, [30.0, 0.0, -110.0]))
    if v is not None:
        v["p1a"].setValue(project(cam, [-20.0, 0.0, -60.0]))
        v["p1b"].setValue(project(cam, [-20.0, 40.0, -60.0]))
        v["p2a"].setValue(project(cam, [25.0, 0.0, -60.0]))
        v["p2b"].setValue(project(cam, [25.0, 40.0, -60.0]))


# ------------------------------------------------ 33. linking three guides
print("\n=== 33. a third guide links instead of breaking the solve ===")
cam = make_cam(35.0, -14.0, 38.0)
a, b, v, s = rig(True)
feed(a, b, v, cam)
check("three guides link without complaint",
      s["vp1"].hasExpression(0) and s["vp2"].hasExpression(0)
      and s["vp3"].hasExpression(0), s["linked_to"].value()[:46])
check("the vertical guide turns the option on", s["use_vertical"].value(), "")
check("the vertical vanishing point is usable here", s["_v3ok"].value() > 0.5,
      "vp3 %s" % [round(x) for x in s["vp3"].value()])
px, py = s["_px"].value(), s["_py"].value()
check("the lens axis is solved back to the center on a centered plate",
      hypot(px - W / 2.0, py - H / 2.0) < 8.0,
      "solved (%.1f, %.1f) vs center (%.1f, %.1f)" % (px, py, W / 2.0, H / 2.0))
s["axis_from"].setValue(1)
check("and the focal is still right", abs(s["cam_focal"].value() - 35.0) < 0.1,
      "%.3f mm" % s["cam_focal"].value())
nuke.delete(cam)

# ------------------------------------------------ 34. the case it was added for
print("\n=== 34. a shifted lens axis: what two points cannot do ===")
rows = []
worst2 = worst3 = 0.0
# 0.30 is a gentle shift; 0.75 is what an off-center crop of roughly half the
# frame actually looks like, which is the case that bit us on the Chicago photo.
for shift, label in (((0.30, 0.0), "shift right"),
                     ((0.0, -0.25), "shift down"),
                     ((0.35, 0.20), "shift both"),
                     ((0.75, 0.45), "half frame crop")):
    cam = make_cam(35.0, -12.0, 40.0, shift=shift)
    truth = project(cam, [0.0, 0.0, -D])  # not used, keeps the camera evaluated

    a2, b2, _, s2 = rig(False)
    feed(a2, b2, None, cam)
    s2["axis_from"].setValue(1)
    f2 = s2["cam_focal"].value()

    a3, b3, v3, s3 = rig(True)
    feed(a3, b3, v3, cam)
    s3["axis_from"].setValue(1)
    f3 = s3["cam_focal"].value()

    worst2 = max(worst2, abs(f2 - 35.0))
    worst3 = max(worst3, abs(f3 - 35.0))
    rows.append((label, f2, f3, s3["_px"].value(), s3["_py"].value()))
    print("  %-12s two points %7.2f mm   three points %7.2f mm   axis (%.0f, %.0f)"
          % (label, f2, f3, s3["_px"].value(), s3["_py"].value()))
    nuke.delete(cam)

check("two points get it wrong when the axis is not centered, as expected",
      worst2 > 1.0, "worst error %.2f mm" % worst2)
check("three points recover the focal anyway", worst3 < 0.2,
      "worst error %.4f mm" % worst3)
check("three points beat two on every one of these", worst3 < worst2 / 5.0,
      "%.3f mm vs %.3f mm" % (worst3, worst2))

# ------------------------------------------------ 35. refusing a bad vertical
print("\n=== 35. a near level camera must not trust its verticals ===")
cam = make_cam(35.0, -0.4, 38.0)
a4, b4, v4, s4 = rig(True)
feed(a4, b4, v4, cam)
far = hypot(s4["vp3"].value()[0] - W / 2.0, s4["vp3"].value()[1] - H / 2.0)
check("the vertical vanishing point runs away on a level camera", far > 25000,
      "%.0f px from center" % far)
check("the solve refuses to use it", s4["_v3ok"].value() < 0.5, "")
check("and falls back to the center of frame",
      abs(s4["_px"].value() - W / 2.0) < 1e-6, "%.1f" % s4["_px"].value())
dhPersp.set_axis_note(s4)
check("the panel explains why", "too close to parallel" in s4["axis_note"].value(),
      s4["axis_note"].value()[:60])
s4["axis_from"].setValue(1)
check("the focal is still right via the two point fallback",
      abs(s4["cam_focal"].value() - 35.0) < 0.1, "%.3f mm" % s4["cam_focal"].value())
nuke.delete(cam)

# ------------------------------------------------ 36. two guides still work
print("\n=== 36. nothing changes for two guides ===")
cam = make_cam(50.0, -8.0, 33.0)
a5, b5, _, s5 = rig(False)
feed(a5, b5, None, cam)
check("two guides still link on their own",
      s5["vp1"].hasExpression(0) and s5["vp2"].hasExpression(0), "")
check("the vertical option stays off", not s5["use_vertical"].value(), "")
s5["axis_from"].setValue(1)
check("focal unchanged", abs(s5["cam_focal"].value() - 50.0) < 0.05,
      "%.4f mm" % s5["cam_focal"].value())
check("pitch unchanged", abs(s5["cam_rx"].value() + 8.0) < 0.05,
      "%.4f deg" % s5["cam_rx"].value())
dhPersp.set_axis_note(s5)
check("the panel says the axis was assumed",
      "center of frame" in s5["axis_note"].value(), s5["axis_note"].value()[:52])
nuke.delete(cam)

print("\n" + "=" * 82)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 8: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
