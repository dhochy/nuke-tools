"""Part nineteen: 'follows the vanishing point', per line.

Attached, a line runs out from the vanishing point through one point. It is a
prediction: here is where perspective says an edge should lie. It cannot vote on
the vanishing point because it was drawn from it, so it can neither help nor
hurt.

Free, it has two points and is a measurement: does this edge agree with the
others. It votes, so it helps when traced well and hurts when not. One line
traced thirty degrees off costs about four degrees of camera roll among six good
ones, which is the risk this switch exists to put back under control.

The default is attached, and that is what makes a node from any earlier build
safe: rebuilding copies knob values by name, an older node has no switch to copy,
so the new one keeps the default and its added lines do exactly what they always
did. No conversion, no cleverness, nothing to get wrong.
"""
import io
import math
import os
import nuke

nuke.pluginAddPath(r"C:\Users\dhoch\.nuke\Gizmos\DH_Tools\3D")
import dhPersp

TMP = r"C:\temp\dgtest"
if not os.path.isdir(TMP):
    os.makedirs(TMP)

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("  %-4s %-62s %s" % ("PASS" if ok else "FAIL", name, detail))


def knob(nm):
    return type("K", (), {"name": staticmethod(lambda: nm)})()


IC = knob("inputChange")
W, H = 1920, 1080
nuke.addFormat("%d %d 0 0 %d %d 1 t" % (W, H, W, H))
nuke.root()["format"].setValue("t")
plate = nuke.nodes.Constant(format="t")
BASE = [(1500.0, 900.0), (300.0, 780.0), (1500.0, 200.0), (300.0, 360.0)]


def new_guide():
    for n in nuke.allNodes():
        n.setSelected(False)
    g = nuke.createNode("dhPerspGuide", inpanel=False)
    g.setInput(0, plate)
    dhPersp.on_knob_changed(g, IC)
    for k, v in zip(("p1a", "p1b", "p2a", "p2b"), BASE):
        g[k].setValue(list(v))
    return g


# --------------------------------------------------------- 81. the switch
print("\n=== 81. every added line has a switch, and it starts attached ===")
g = new_guide()
check("there is a switch on every slot",
      all("pin%d" % i in g.knobs() for i in range(1, 13)), "")
check("it is on by default, which is the half that cannot hurt",
      all(g["pin%d" % i].value() for i in range(1, 13)), "")
check("its label says what it does",
      g["pin1"].label() == "follows the vanishing point", g["pin1"].label())

base = tuple(g["vp"].value())
i = dhPersp.add_line(g)
check("pressing add line creates a free one, because that is a deliberate act",
      not g["pin%d" % i].value(), "pin%d %s" % (i, g["pin%d" % i].value()))
check("and it starts out aimed where the others are, so nothing jumps",
      math.hypot(g["vp"].value()[0] - base[0],
                 g["vp"].value()[1] - base[1]) < 0.5,
      "vp %s" % [round(v) for v in g["vp"].value()])

# ------------------------------------------------------ 82. attached is inert
print("\n=== 82. an attached line cannot move the answer, however bad it is ===")
g["pin1"].setValue(True)
dhPersp.on_knob_changed(g, knob("pin1"))
check("it carries no weight in the fit", g["_Lw3"].value() == 0.0,
      "weight %.3g" % g["_Lw3"].value())
check("point B is hidden, because it means nothing for this line",
      not g["add1b"].visible(), "")
check("the answer is exactly what it was with no added line at all",
      tuple(g["vp"].value()) == base, str([round(v) for v in g["vp"].value()]))

# put its points somewhere absurd: still nothing
# well inside the frame, so unticking cannot decide to re-place them, but at a
# wild angle to the two base lines
g["add1"].setValue([200.0, 950.0])
g["add1b"].setValue([1700.0, 120.0])
check("and dragging it anywhere at all still changes nothing",
      tuple(g["vp"].value()) == base, str([round(v) for v in g["vp"].value()]))

# ------------------------------------------------------- 83. free is a vote
print("\n=== 83. a free line votes, which is the point of it ===")
g["pin1"].setValue(False)
dhPersp.on_knob_changed(g, knob("pin1"))
check("now it carries weight", g["_Lw3"].value() > 0,
      "weight %.3g" % g["_Lw3"].value())
check("point B is shown, because now it means something", g["add1b"].visible(), "")
moved = math.hypot(g["vp"].value()[0] - base[0], g["vp"].value()[1] - base[1])
check("and the answer has moved a long way, because the line disagrees",
      moved > 100.0, "vp %s, moved %.0f px"
      % ([round(v) for v in g["vp"].value()], moved))
check("unticking did not quietly re-place a point that was already on screen",
      abs(g["add1b"].value()[0] - 1700.0) < 1e-6, str(g["add1b"].value()))

# ------------------------------------ 84. releasing places B where you can see it
print("\n=== 84. unticking puts B on the line that was already drawn ===")
g2 = new_guide()
j = dhPersp.add_line(g2)
clean = tuple(g2["vp"].value())
g2["pin%d" % j].setValue(True)
dhPersp.on_knob_changed(g2, knob("pin%d" % j))
g2["add%db" % j].setValue(list(dhPersp.SLOT_DEFAULT))    # never placed
g2["pin%d" % j].setValue(False)
dhPersp.on_knob_changed(g2, knob("pin%d" % j))
b = g2["add%db" % j].value()
check("B lands inside the frame", 0 <= b[0] <= W and 0 <= b[1] <= H,
      str([round(v) for v in b]))
a = g2["add%d" % j].value()
cross = abs((a[0] - clean[0]) * (b[1] - clean[1])
            - (a[1] - clean[1]) * (b[0] - clean[0]))
span = math.hypot(a[0] - clean[0], a[1] - clean[1]) * \
    max(math.hypot(b[0] - clean[0], b[1] - clean[1]), 1e-9)
check("on the line that was being drawn a moment ago, from the vanishing point "
      "through A", cross / span < 1e-6, "off the ray by %.3g" % (cross / span))
check("so the answer does not jump when you untick it",
      math.hypot(g2["vp"].value()[0] - clean[0],
                 g2["vp"].value()[1] - clean[1]) < 0.5,
      "moved %.4f px" % math.hypot(g2["vp"].value()[0] - clean[0],
                                   g2["vp"].value()[1] - clean[1]))

# ---------------------------------------- 85. the outlier, with and without
print("\n=== 85. what the switch is actually protecting you from ===")


def horizon(gg):
    v = gg["vp"].value()
    return math.degrees(math.atan2(v[1] - H / 2.0, v[0] - W / 2.0)) % 180.0


g3 = new_guide()
truth = horizon(g3)
k = dhPersp.add_line(g3)
# drag it thirty degrees off the direction the others agree on
a = g3["add%d" % k].value()
ang = math.radians(30.0)
vx, vy = g3["vp"].value()
dx, dy = a[0] - vx, a[1] - vy
n = math.hypot(dx, dy)
ux = (dx * math.cos(ang) - dy * math.sin(ang)) / n
uy = (dx * math.sin(ang) + dy * math.cos(ang)) / n
g3["add%db" % k].setValue([a[0] + ux * 400.0, a[1] + uy * 400.0])
free_err = abs(((horizon(g3) - truth) + 90.0) % 180.0 - 90.0)
g3["pin%d" % k].setValue(True)
dhPersp.on_knob_changed(g3, knob("pin%d" % k))
pinned_err = abs(((horizon(g3) - truth) + 90.0) % 180.0 - 90.0)
check("free, a line thirty degrees off drags the horizon", free_err > 1.0,
      "%.3f deg of roll" % free_err)
check("attached, the same line costs exactly nothing", pinned_err < 1e-9,
      "%.6f deg of roll" % pinned_err)

# ------------------------------------------ 86. an older node is safe by default
print("\n=== 86. a guide from an earlier build comes back doing what it did ===")
# Build 15: two point added lines, no switch. Kept in the repo rather than
# in a session temp folder, or this test quietly stops testing anything.
FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "fixtures", "dhPerspGuide_build15.gizmo")
check("the build 15 fixture is where the test can find it",
      os.path.isfile(FIX), FIX)
if os.path.isfile(FIX):
    body = io.open(FIX, encoding="utf-8").read().split("\n", 1)[1]
    body = body.replace(" name dhPerspGuide\n", " name oldOne\n", 1)
    paste = os.path.join(TMP, "s19_old.nk").replace("\\", "/")
    io.open(paste, "w", encoding="utf-8", newline="").write(
        "set cut_paste_input [stack 0]\n" + body)
    for n in nuke.allNodes():
        n.setSelected(False)
    plate.setSelected(True)
    nuke.nodePaste(paste)
    old = nuke.toNode("oldOne")
    old.setInput(0, plate)
    for kk, v in zip(("p1a", "p1b", "p2a", "p2b"), BASE):
        old[kk].setValue(list(v))
    check("it has no switch at all", "pin1" not in old.knobs(), "")
    old["add1"].setValue([420.0, 260.0])
    old["use_add1"].setValue(True)
    want = tuple(old["vp"].value())
    dhPersp.update_nodes([old], quiet=True)
    now = nuke.toNode("oldOne")
    check("it rebuilt", now is not None, "")
    check("its added line came back attached, with no conversion needed",
          now is not None and now["pin1"].value(), "")
    check("so it carries no weight", now["_Lw3"].value() == 0.0,
          "weight %.3g" % now["_Lw3"].value())
    check("and the answer is bit for bit what it was before the rebuild",
          tuple(now["vp"].value()) == want,
          "%s against %s" % ([round(v) for v in now["vp"].value()],
                             [round(v) for v in want]))
    check("point A is where it was", abs(now["add1"].value()[0] - 420.0) < 1e-6,
          str(now["add1"].value()))
else:
    check("without it this section proves nothing", False, FIX)

# ------------------------------- 87. the panel puts itself right
print("\n=== 87. a panel update hides what should not be there ===")
gu = new_guide()
check("a fresh node shows no switches",
      not any(gu["pin%d" % i].visible() for i in range(1, 13)), "")
check("and a redundant sync touches nothing, so updateUI cannot loop",
      dhPersp.sync_lines(gu) == 0, "%d knobs set" % dhPersp.sync_lines(gu))

# Exactly David's symptom: the switches visible with no lines added, which is
# what a node gets when it is made in a session whose Python is older than its
# gizmo. Such a node is not stale, so nothing ever rebuilds it, and before this
# there was no later moment that could put it right.
for i in range(1, 13):
    gu["pin%d" % i].setVisible(True)
check("forcing them all visible reproduces it",
      sum(1 for i in range(1, 13) if gu["pin%d" % i].visible()) == 12, "")
fixed = dhPersp.on_update_ui(gu)
check("a panel update puts it right", fixed == 12 and
      not any(gu["pin%d" % i].visible() for i in range(1, 13)),
      "%d knobs corrected" % fixed)
check("and the update after that does nothing at all",
      dhPersp.on_update_ui(gu) == 0, "")

k = dhPersp.add_line(gu)
check("with a line added, exactly one switch shows",
      [n for n in range(1, 13) if gu["pin%d" % n].visible()] == [k],
      str([n for n in range(1, 13) if gu["pin%d" % n].visible()]))
check("and a panel update leaves that alone", dhPersp.on_update_ui(gu) == 0, "")
check("the delete button and both points came with it",
      gu["add%d" % k].visible() and gu["add%db" % k].visible()
      and gu["del%d" % k].visible(), "")

check("the gizmo actually calls it on every panel update",
      "on_update_ui" in io.open(
          r"C:\Users\dhoch\.nuke\Gizmos\DH_Tools\3D\dhPerspGuide.gizmo",
          encoding="utf-8").read(), "")

print("\n" + "=" * 88)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 19: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
