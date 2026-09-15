"""Part six: updating stale nodes in place, and refusing to solve from a blank guide.

This reproduces David's actual failure. A node saved with the OLD internals, where
the floor card's position was tied to its size, is loaded, and must come back with
the size term gone and every placed point still where he put it.
"""
import io
import os
import nuke

GIZDIR = r"C:\Users\dhoch\.nuke\Gizmos\DH_Tools\3D"
TMP = r"C:\temp\dgtest"
if not os.path.isdir(TMP):
    os.makedirs(TMP)
nuke.pluginAddPath(GIZDIR)
import dhPersp

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("  %-4s %-56s %s" % ("PASS" if ok else "FAIL", name, detail))


W, H = 1920, 1080
nuke.addFormat("%d %d 0 0 %d %d 1 testHD" % (W, H, W, H))
nuke.root()["format"].setValue("testHD")
plate = nuke.nodes.Constant(format="testHD")

# ------------------------------------------------- 29. the blank guide trap
print("\n=== 29. an untouched guide must not be solved from ===")
g = nuke.createNode("dhPerspGuide", inpanel=False)
g.setInput(0, plate)
dhPersp.on_knob_changed(g, type("IC", (), {"name": staticmethod(lambda: "inputChange")})())
for n in nuke.allNodes():
    n.setSelected(False)
vp = g["vp"].value()
check("a fresh guide's vanishing point is the center of frame",
      abs(vp[0] - W / 2.0) < 1.0 and abs(vp[1] - H / 2.0) < 1.0,
      "vp (%.1f, %.1f) vs center (%.1f, %.1f)" % (vp[0], vp[1], W / 2.0, H / 2.0))
check("and the tool knows it is untouched", dhPersp.is_pristine(g), "")

g2 = nuke.createNode("dhPerspGuide", inpanel=False)
g2.setInput(0, g)
dhPersp.on_knob_changed(g2, type("IC", (), {"name": staticmethod(lambda: "inputChange")})())
g2["p1a"].setValue([200.0, 100.0]); g2["p1b"].setValue([1700.0, 300.0])
g2["p2a"].setValue([200.0, 800.0]); g2["p2b"].setValue([1700.0, 700.0])
s = nuke.createNode("dhPerspSolve", inpanel=False)
s.setInput(0, g2)
for n in nuke.allNodes():
    n.setSelected(False)
dhPersp.on_knob_changed(s, type("IC", (), {"name": staticmethod(lambda: "inputChange")})())

blank = dhPersp.pristine_guides(s)
check("the solve reports which guide was never placed", g.name() in blank, str(blank))
check("a placed guide is not flagged", g2.name() not in blank, str(blank))
# What David originally saw was the focal collapsing to a fraction of a
# millimeter, and that is what this used to assert. The collapse was only ever
# the symptom: a blank guide puts its vanishing point at the center of frame, the
# pair describes no camera, and the number that came out was the clamp inside
# _fsolved. Build 31 shows the assumption in the box instead of the clamp, so the
# focal no longer collapses and asserting that it does would now be asserting the
# absence of a fix. The finding this check exists to protect is the one below it:
# a guide nobody placed must not produce a solve.
check("a blank guide leaves the solve refused, which is what the collapsed "
      "focal was telling him",
      s["_solveok"].value() < 0.5,
      "_fsq %.4g" % s["_fsq"].value())
check("so the number on the panel is the assumption, not a solve",
      abs(s["cam_focal"].value() - s["known_focal"].value()) < 0.01,
      "%.3f mm, and the box says %.3f"
      % (s["cam_focal"].value(), s["known_focal"].value()))
label = s["linked_to"].value()
check("the panel says so in the link label",
      "Warning" in label and g.name() in label, label[-80:])

# These have to converge to the LEFT, opposite the other guide. Two guides whose
# vanishing points sit on the same side of the lens axis describe no camera at
# all, and the solve now says so rather than returning a small number, so a made
# up pair is no longer good enough for a fixture.
g["p1a"].setValue([1500.0, 900.0]); g["p1b"].setValue([300.0, 780.0])
g["p2a"].setValue([1500.0, 200.0]); g["p2b"].setValue([300.0, 360.0])
dhPersp.set_link_label(s)
check("the warning clears once the guide is placed",
      not dhPersp.pristine_guides(s) and "Warning" not in s["linked_to"].value(), "")
check("and the focal becomes believable", 4.0 < s["cam_focal"].value() < 400.0,
      "%.2f mm" % s["cam_focal"].value())

# ------------------------------------------------- 30. updating a stale node
print("\n=== 30. a node saved with the old internals updates in place ===")

# A Group gizmo is copied into the script when the node is made, so a node saved
# at build 5 is the build 5 gizmo file. Pasting the kept copy gives a real old
# node instead of an imitation of one.
FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "fixtures", "dhPerspSolve_build5.gizmo")
old_body = io.open(FIX, encoding="utf-8").read()
old_body = old_body.split("\n", 1)[1]                  # drop the version line
old_body = old_body.replace(" name dhPerspSolve\n", " name dhStaleSolve\n", 1)
paste = os.path.join(TMP, "stale_paste.nk").replace("\\", "/")
io.open(paste, "w", encoding="utf-8", newline="").write(
    "set cut_paste_input [stack 0]\n" + old_body)

for n in nuke.allNodes():
    n.setSelected(False)
g2.setSelected(True)
nuke.nodePaste(paste)
old_solve = nuke.toNode("dhStaleSolve")
check("a build 5 node was pasted into the script", old_solve is not None, "")
old_solve.setInput(0, g2)
old_solve["vp1"].setExpression(g.name() + ".vp.x", 0)
old_solve["vp1"].setExpression(g.name() + ".vp.y", 1)
old_solve["vp2"].setExpression(g2.name() + ".vp.x", 0)
old_solve["vp2"].setExpression(g2.name() + ".vp.y", 1)

check("it is the old build", dhPersp.node_build(old_solve) < dhPersp.BUILD,
      "build %d against %d" % (dhPersp.node_build(old_solve), dhPersp.BUILD))
check("it still has the card floor inside it",
      old_solve.node("floorgrid") is not None, "")
check("and the knobs that used to move it",
      "gridsize" in old_solve.knobs() and "griddistance" in old_solve.knobs(), "")

# reproduce the report on the old node: growing it walks its near edge forward
card = old_solve.node("floorgrid")
old_solve["griddistance"].setValue(20.0)
near = []
for sz in (20.0, 80.0, 160.0):
    old_solve["gridsize"].setValue(sz)
    t = card["translate"].value()
    near.append(round(t[2] - sz / 2.0, 3))
check("the old node's near edge really does move when it is scaled, "
      "which is what David saw", len(set(near)) == 3, "near edge z %s" % near)

stale = dhPersp.stale_nodes()
check("stale_nodes finds it", old_solve.name() in [n.name() for n in stale],
      "%d stale" % len(stale))

keep_name = old_solve.name()
old_solve["camera_height"].setValue(7.25)
old_solve["cellsize"].setValue(3.5)
old_solve["gridcolor"].setValue([0.2, 0.4, 0.9, 1.0])
keep = {"camera_height": 7.25, "cellsize": 3.5}
guide_pts = {}
for n in nuke.allNodes():
    if dhPersp.is_persplines(n):
        guide_pts[n.name()] = [list(n[k].value()) for k in ("p1a", "p1b", "p2a", "p2b")]
linked = old_solve["vp1"].hasExpression(0)

dhPersp.update_nodes(quiet=True)

new_solve = nuke.toNode(keep_name)
check("the node keeps its name", new_solve is not None, keep_name)
check("it is now at the current build",
      new_solve is not None and dhPersp.node_build(new_solve) == dhPersp.BUILD,
      "build %d" % (dhPersp.node_build(new_solve) if new_solve else -1))
check("the knobs that still exist kept their values",
      new_solve is not None
      and all(abs(new_solve[k].value() - v) < 1e-6 for k, v in keep.items()),
      ", ".join("%s %.4g" % (k, new_solve[k].value()) for k in keep))
check("and so did the color",
      abs(new_solve["gridcolor"].value()[2] - 0.9) < 1e-6,
      str([round(v, 3) for v in new_solve["gridcolor"].value()]))
ok_pts = True
for nm, pts in guide_pts.items():
    n = nuke.toNode(nm)
    if n is None:
        ok_pts = False
        continue
    for k, want in zip(("p1a", "p1b", "p2a", "p2b"), pts):
        got = list(n[k].value())
        if abs(got[0] - want[0]) > 1e-4 or abs(got[1] - want[1]) > 1e-4:
            ok_pts = False
check("every placed guide point survived", ok_pts, "%d guides" % len(guide_pts))
check("expression links survived",
      (not linked) or new_solve["vp1"].hasExpression(0), "linked was %s" % linked)
check("it is still connected to the guide chain",
      new_solve.input(0) is not None,
      new_solve.input(0).name() if new_solve.input(0) else "nothing")

check("THE FIX: the card is gone, so there is nothing left to move",
      new_solve.node("floorgrid") is None, "")
check("and the ground is drawn from the solve instead",
      new_solve.node("groundxz") is not None
      and new_solve.node("gridmask") is not None, "")
for gone in ("gridsize", "griddistance", "autofit", "gridfade", "gridstyle"):
    check("the %s knob did not come back with it" % gone,
          gone not in new_solve.knobs(), "")
check("nothing is left stale", not dhPersp.stale_nodes(),
      "%d stale" % len(dhPersp.stale_nodes()))

print("\n" + "=" * 82)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 6: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
