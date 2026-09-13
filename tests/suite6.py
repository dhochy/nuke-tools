"""Part six: updating stale nodes in place, and refusing to solve from a blank guide.

This reproduces David's actual failure. A node saved with the OLD internals, where
the floor card's position was tied to its size, is loaded, and must come back with
the size term gone and every placed point still where he put it.
"""
import os
import re
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
check("a fresh guide's vanishing point is the centre of frame",
      abs(vp[0] - W / 2.0) < 1.0 and abs(vp[1] - H / 2.0) < 1.0,
      "vp (%.1f, %.1f) vs centre (%.1f, %.1f)" % (vp[0], vp[1], W / 2.0, H / 2.0))
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
check("the focal collapses when fed the blank guide, which is the bug David saw",
      s["cam_focal"].value() < 4.0, "%.3f mm" % s["cam_focal"].value())
label = s["linked_to"].value()
check("the panel says so in the link label",
      "Warning" in label and g.name() in label, label[-80:])

g["p1a"].setValue([300.0, 900.0]); g["p1b"].setValue([1500.0, 700.0])
g["p2a"].setValue([300.0, 200.0]); g["p2b"].setValue([1500.0, 340.0])
dhPersp.set_link_label(s)
check("the warning clears once the guide is placed",
      not dhPersp.pristine_guides(s) and "Warning" not in s["linked_to"].value(), "")
check("and the focal becomes believable", 4.0 < s["cam_focal"].value() < 400.0,
      "%.2f mm" % s["cam_focal"].value())

# ------------------------------------------------- 30. updating a stale node
print("\n=== 30. a node saved with the old internals updates in place ===")
path = os.path.join(TMP, "stale.nk").replace("\\", "/")
nuke.scriptSaveAs(path, overwrite=1)

# forge the old behaviour: size drives position, exactly as it did before 012eef9
src = open(path).read()
OLD = ('translate {{"parent.gridoffset.x - sin((parent.cam_ry*3.14159265358979/180))'
       '*parent.griddistance"} {parent.gridoffset.y} '
       '{"parent.gridoffset.z - cos((parent.cam_ry*3.14159265358979/180))'
       '*parent.griddistance"}}')
NEW = ('translate {{"parent.gridoffset.x - sin((parent.cam_ry*3.14159265358979/180))'
       '*parent.gridsize/2"} {parent.gridoffset.y} '
       '{"parent.gridoffset.z - cos((parent.cam_ry*3.14159265358979/180))'
       '*parent.gridsize/2"}}')
check("the saved script contains the fixed expression", OLD in src, "")
# forge an OLD build number whatever the current one is, or this test
# quietly stops testing anything the moment BUILD is bumped
src = re.sub(r"\n _build \d+\n", "\n _build 1\n", src.replace(OLD, NEW))
open(path, "w").write(src)
nuke.scriptClear()
nuke.scriptOpen(path)

old_solve = [n for n in nuke.allNodes() if "gridsize" in n.knobs()][0]
card = old_solve.node("floorgrid")
old_solve["griddistance"].setValue(20.0)
moved = []
for sz in (20.0, 80.0, 160.0):
    old_solve["gridsize"].setValue(sz)
    moved.append(round(card["translate"].value()[2], 3))
check("the stale node really does move when scaled, reproducing the report",
      len(set(moved)) == 3, "card z %s" % moved)
check("and it reports an old build", dhPersp.node_build(old_solve) < dhPersp.BUILD,
      "build %d vs %d" % (dhPersp.node_build(old_solve), dhPersp.BUILD))
stale = dhPersp.stale_nodes()
check("stale_nodes finds it", old_solve.name() in [n.name() for n in stale],
      "%d stale" % len(stale))

keep_name = old_solve.name()
keep_size = old_solve["gridsize"].value()
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
check("knob values survived the rebuild",
      new_solve is not None and abs(new_solve["gridsize"].value() - keep_size) < 1e-6,
      "gridsize %.2f" % (new_solve["gridsize"].value() if new_solve else -1))
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

newcard = new_solve.node("floorgrid")
new_solve["griddistance"].setValue(20.0)
fixed = []
for sz in (20.0, 80.0, 160.0):
    new_solve["gridsize"].setValue(sz)
    fixed.append(round(newcard["translate"].value()[2], 3))
check("THE FIX: the updated node no longer moves when scaled",
      len(set(fixed)) == 1, "card z %s" % fixed)
check("nothing is left stale", not dhPersp.stale_nodes(),
      "%d stale" % len(dhPersp.stale_nodes()))

print("\n" + "=" * 82)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 6: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
