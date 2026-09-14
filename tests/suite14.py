"""Part fourteen: animating the guides, and what has to follow.

The whole chain is expressions and an expression is evaluated per frame, so
keying the guide points gives a camera that moves. That part needed no work. Two
things around it did.

Baking froze the current frame. On a move that silently throws the shot away and
leaves one pose, which looks like it worked.

And the ground axis defaults to picking whichever vanishing point needs the
smaller turn. Per frame that is sensible; across a shot it is not, because the
two candidates are ninety degrees apart and nothing stops it changing its mind
halfway through. That is a real ninety degree snap, and it is measured here
rather than assumed.

Reading an animated value is its own trap. knob.value() answers for whatever
context the knob is in, and in a terminal session nuke.frame() does not move it,
so everything reads as frame one and a moving camera measures as a still one.
getValueAt is the one that answers the question asked.
"""
import nuke

nuke.pluginAddPath(r"C:\Users\dhoch\.nuke\Gizmos\DH_Tools\3D")
import dhPersp

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("  %-4s %-62s %s" % ("PASS" if ok else "FAIL", name, detail))


IC = type("IC", (), {"name": staticmethod(lambda: "inputChange")})()
W, H = 1920, 1080
FIRST, LAST = 1, 24
nuke.addFormat("%d %d 0 0 %d %d 1 testHD" % (W, H, W, H))
nuke.root()["format"].setValue("testHD")
nuke.root()["first_frame"].setValue(FIRST)
nuke.root()["last_frame"].setValue(LAST)
plate = nuke.nodes.Constant(format="testHD")


def guide(after, pts):
    for n in nuke.allNodes():
        n.setSelected(False)
    g = nuke.createNode("dhPerspGuide", inpanel=False)
    g.setInput(0, after)
    dhPersp.on_knob_changed(g, IC)
    for k, v in zip(("p1a", "p1b", "p2a", "p2b"), pts):
        g[k].setValue([float(v[0]), float(v[1])])
    return g


g1 = guide(plate, [(1500, 900), (300, 780), (1500, 200), (300, 360)])
g2 = guide(g1, [(200, 100), (1700, 300), (200, 800), (1700, 700)])
for n in nuke.allNodes():
    n.setSelected(False)
s = nuke.createNode("dhPerspSolve", inpanel=False)
s.setInput(0, g2)
for n in nuke.allNodes():
    n.setSelected(False)
dhPersp.on_knob_changed(s, IC)
s["camera_height"].setValue(5.5)

# ------------------------------------------------------- 51. nothing keyed yet
print("\n=== 51. a still solve is still still ===")
check("no guide is animated", not dhPersp.animated_guides(s), "")
dhPersp.set_verdict(s)
check("and the verdict does not mention animation",
      "animated" not in s["verdict"].value(), s["verdict"].value()[:60])
cam = s.node("cam")
still = [round(cam["focal"].getValueAt(f), 6) for f in (FIRST, 12, LAST)]
check("the camera reads the same on every frame", len(set(still)) == 1,
      "%.4f mm" % still[0])

# ---------------------------------------------------- 52. key the guide points
print("\n=== 52. keying the guides moves the camera ===")
k = g2["p1b"]
k.setAnimated(0)
k.setAnimated(1)
k.setValueAt(1700.0, FIRST, 0)
k.setValueAt(1300.0, LAST, 0)
k.setValueAt(300.0, FIRST, 1)
k.setValueAt(620.0, LAST, 1)

check("the tool sees the guide as animated",
      [n.name() for n in dhPersp.animated_guides(s)] == [g2.name()],
      str([n.name() for n in dhPersp.animated_guides(s)]))
check("a guide with no keys is not counted",
      g1 not in dhPersp.animated_guides(s), "")

vps = [round(g2["vp"].getValueAt(f, 0), 3) for f in (FIRST, 8, 16, LAST)]
check("the guide's vanishing point moves", len(set(vps)) == 4, str(vps))

focals = [round(s["cam_focal"].getValueAt(f), 4) for f in (FIRST, 8, 16, LAST)]
check("the solved focal length moves with it", len(set(focals)) == 4, str(focals))
pitch = [round(s["cam_rx"].getValueAt(f), 4) for f in (FIRST, 8, 16, LAST)]
check("so does the pitch", len(set(pitch)) == 4, str(pitch))

inner = [round(cam["focal"].getValueAt(f), 4) for f in (FIRST, 8, 16, LAST)]
check("and the camera inside the node follows, without being told to",
      len(set(inner)) == 4, str(inner))
check("nobody had to key the camera: it is still an expression",
      cam["focal"].hasExpression(0), "")

# --------------------------------------------------- 53. the axis can snap
print("\n=== 53. automatic ground axis changes its mind mid shot ===")
s["axis_from"].setValue(0)
auto = [s["cam_ry"].getValueAt(f) for f in range(FIRST, LAST + 1)]
jumps = [f for f, a, b in zip(range(FIRST + 1, LAST + 1), auto, auto[1:])
         if abs(b - a) > 20.0]
check("on automatic, the yaw takes a jump of more than twenty degrees "
      "between two frames", bool(jumps),
      "at frame(s) %s, %.1f to %.1f" % (jumps[:3], auto[jumps[0] - FIRST - 1],
                                        auto[jumps[0] - FIRST]) if jumps else "none")
dhPersp.set_verdict(s)
check("the panel warns about it",
      "ninety degree snap" in s["verdict"].value(), s["verdict"].value()[-70:])

s["axis_from"].setValue(1)
pinned = [s["cam_ry"].getValueAt(f) for f in range(FIRST, LAST + 1)]
worst = max(abs(b - a) for a, b in zip(pinned, pinned[1:]))
check("pinned to one vanishing point, the yaw is smooth", worst < 20.0,
      "biggest step between frames %.2f degrees" % worst)
dhPersp.set_verdict(s)
check("and the warning goes away, but it still says it is animated",
      "ninety degree snap" not in s["verdict"].value()
      and "animated" in s["verdict"].value(), s["verdict"].value()[:70])

# -------------------------------------------------------- 54. baking a move
print("\n=== 54. baking keeps the move ===")
want_focal = [round(s["cam_focal"].getValueAt(f), 5) for f in range(FIRST, LAST + 1)]
want_ry = [round(s["cam_ry"].getValueAt(f), 5) for f in range(FIRST, LAST + 1)]
ex = dhPersp.export_camera(s)
check("a camera exports", ex is not None, ex.name() if ex else "none")
check("it starts out linked", ex["focal"].hasExpression(0), "")

dhPersp.bake_camera(ex)
check("baking drops the link", not ex["focal"].hasExpression(0), "")
check("but keeps a curve", ex["focal"].isAnimated(0),
      "%d keys" % len(ex["focal"].animation(0).keys()))
got_focal = [round(ex["focal"].getValueAt(f), 5) for f in range(FIRST, LAST + 1)]
got_ry = [round(ex["rotate"].getValueAt(f, 1), 5) for f in range(FIRST, LAST + 1)]
check("every frame of the focal length survived", got_focal == want_focal,
      "%s ... %s" % (got_focal[:2], got_focal[-2:]))
check("every frame of the yaw survived", got_ry == want_ry,
      "%s ... %s" % (got_ry[:2], got_ry[-2:]))
check("and it is genuinely a move, not the same number repeated",
      len(set(got_focal)) > 20, "%d distinct values over %d frames"
      % (len(set(got_focal)), LAST - FIRST + 1))

# the baked camera must not follow the guides any more
g2["p2a"].setValue([400.0, 900.0])
after = [round(ex["focal"].getValueAt(f), 5) for f in range(FIRST, LAST + 1)]
check("moving a guide afterwards does not touch it", after == got_focal, "")

# --------------------------------------------- 55. baking a still solve
print("\n=== 55. baking something that does not move gives plain numbers ===")
for n in nuke.allNodes():
    n.setSelected(False)
s2 = nuke.createNode("dhPerspSolve", inpanel=False)
s2.setInput(0, g1)
for n in nuke.allNodes():
    n.setSelected(False)
dhPersp.on_knob_changed(s2, IC)
s2["vp1"].clearAnimated(0); s2["vp1"].clearAnimated(1)
s2["vp2"].clearAnimated(0); s2["vp2"].clearAnimated(1)
s2["vp1"].setValue([-1500.0, 600.0])
s2["vp2"].setValue([3700.0, 567.0])
ex2 = dhPersp.export_camera(s2)
was = round(ex2["focal"].getValueAt(FIRST), 5)
dhPersp.bake_camera(ex2)
check("the link is gone", not ex2["focal"].hasExpression(0), "")
check("no curve was left behind", not ex2["focal"].isAnimated(0), "")
check("and the value is the one it had", abs(ex2["focal"].value() - was) < 1e-5,
      "%.4f mm" % ex2["focal"].value())

print("\n" + "=" * 88)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 14: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
