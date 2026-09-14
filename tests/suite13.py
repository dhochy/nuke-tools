"""Part thirteen: renaming an option must not move a node that already has one.

The role options have been renamed twice. "ground" became "horizontal" for one
build and then the set became ground, across and vertical, which moved vertical
from index 1 to index 2. That is the one kind of edit that can quietly corrupt
existing work: rebuilding a node copies knob values across by name, an
Enumeration knob's value() is its label, and setting a label the new build does
not have fails silently and leaves the knob at its default.

So this tests the two cases that matter. A guide saved as vertical, whose label
survived every rename but whose index did not. And a value whose label is simply
gone, which has to fall back to the index or be lost.
"""
import io
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


W, H = 1920, 1080
nuke.addFormat("%d %d 0 0 %d %d 1 testHD" % (W, H, W, H))
nuke.root()["format"].setValue("testHD")
plate = nuke.nodes.Constant(format="testHD")

# ------------------------------------------------------- 48. the new labels
print("\n=== 48. the option says what it is ===")
g = nuke.createNode("dhPerspGuide", inpanel=False)
g.setInput(0, plate)
opts = list(g["role"].values())
check("the choices are ground, across and vertical",
      opts == ["ground", "across", "vertical"], str(opts))
check("ground is the default", g["role"].value() == "ground", g["role"].value())
tip = g["role"].tooltip()
check("the tooltip says the lines need not be on the ground",
      "not have to be on the ground" in tip, tip[:70])
check("and that a third guide is recognized on its own",
      "recognized" in tip, "")

# -------------------------------------------- 49. an older guide survives it
print("\n=== 49. a guide saved before the rename keeps what it was set to ===")
FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "fixtures", "dhPerspGuide_build8.gizmo")
body = io.open(FIX, encoding="utf-8").read().split("\n", 1)[1]
check("the kept fixture really is the old wording",
      "M {ground vertical}" in body, "")


def paste_old(name, role):
    b = body.replace(" name dhPerspGuide\n", " name %s\n" % name, 1)
    path = os.path.join(TMP, "s13_%s.nk" % name).replace("\\", "/")
    io.open(path, "w", encoding="utf-8", newline="").write(
        "set cut_paste_input [stack 0]\n" + b)
    for n in nuke.allNodes():
        n.setSelected(False)
    plate.setSelected(True)
    nuke.nodePaste(path)
    node = nuke.toNode(name)
    node.setInput(0, plate)
    node["role"].setValue(role)
    return node


old_ground = paste_old("oldGround", "ground")
old_vert = paste_old("oldVertical", "vertical")
old_ground["p1a"].setValue([1500.0, 900.0]); old_ground["p1b"].setValue([300.0, 780.0])
old_ground["p2a"].setValue([1500.0, 200.0]); old_ground["p2b"].setValue([300.0, 360.0])
old_vert["p1a"].setValue([500.0, 60.0]); old_vert["p1b"].setValue([512.0, 1020.0])
old_vert["p2a"].setValue([1400.0, 60.0]); old_vert["p2b"].setValue([1381.0, 1020.0])

check("the old node really says ground", old_ground["role"].value() == "ground",
      old_ground["role"].value())
check("and the other really says vertical", old_vert["role"].value() == "vertical",
      old_vert["role"].value())
check("both read as stale", len(dhPersp.stale_nodes()) >= 2,
      "%d stale" % len(dhPersp.stale_nodes()))

pts = {n.name(): [list(n[k].value()) for k in ("p1a", "p1b", "p2a", "p2b")]
       for n in (old_ground, old_vert)}
dhPersp.update_nodes(quiet=True)

now_ground = nuke.toNode("oldGround")
now_vert = nuke.toNode("oldVertical")
check("the ground guide came back", now_ground is not None, "")
check("it is at the current build",
      now_ground is not None and dhPersp.node_build(now_ground) == dhPersp.BUILD,
      "build %d" % (dhPersp.node_build(now_ground) if now_ground else -1))
check("ground is still ground",
      now_ground is not None and now_ground["role"].value() == "ground",
      now_ground["role"].value() if now_ground else "gone")
check("THE ONE THAT MATTERS: the vertical guide is still vertical, though "
      "its index moved from 1 to 2",
      now_vert is not None and now_vert["role"].value() == "vertical",
      now_vert["role"].value() if now_vert else "gone")
check("guide_role agrees for both",
      dhPersp.guide_role(now_ground) == dhPersp.GROUND
      and dhPersp.guide_role(now_vert) == dhPersp.VERTICAL,
      "%d and %d" % (dhPersp.guide_role(now_ground), dhPersp.guide_role(now_vert)))
ok = True
for nm, want in pts.items():
    n = nuke.toNode(nm)
    for k, v in zip(("p1a", "p1b", "p2a", "p2b"), want):
        got = list(n[k].value())
        if abs(got[0] - v[0]) > 1e-4 or abs(got[1] - v[1]) > 1e-4:
            ok = False
check("every placed point survived the rename", ok, "%d guides" % len(pts))

# ---------------------------------- 50. a label that is simply gone
print("\n=== 50. a value whose label no longer exists falls back to its index ===")
check("the working unit is spelled the American way now",
      list(nuke.createNode("dhPerspSolve", inpanel=False)["unit"].values())
      == ["feet", "meters", "centimeters"], "")
for n in nuke.allNodes():
    n.setSelected(False)

SFIX = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "fixtures", "dhPerspSolve_build5.gizmo")
sbody = io.open(SFIX, encoding="utf-8").read().split("\n", 1)[1]
check("the kept build 5 solve spells them the British way",
      "M {feet metres centimetres}" in sbody, "")
sbody = sbody.replace(" name dhPerspSolve\n", " name oldUnits\n", 1)
spaste = os.path.join(TMP, "s13_units.nk").replace("\\", "/")
io.open(spaste, "w", encoding="utf-8", newline="").write(
    "set cut_paste_input [stack 0]\n" + sbody)
for n in nuke.allNodes():
    n.setSelected(False)
plate.setSelected(True)
nuke.nodePaste(spaste)
old = nuke.toNode("oldUnits")
old.setInput(0, plate)
old["unit"].setValue("centimetres")
old["camera_height"].setValue(168.0)
check("the old node really is set to centimetres", old["unit"].value() == "centimetres",
      old["unit"].value())
check("and that option no longer exists in the current build",
      "centimetres" not in list(nuke.toNode("dhPerspSolve")["unit"].values()), "")

dhPersp.update_nodes([old], quiet=True)
back = nuke.toNode("oldUnits")
check("it rebuilt", back is not None, "")
check("THE ONE THAT MATTERS: centimetres came back as centimeters, by index, "
      "because the label it had was gone",
      back is not None and back["unit"].value() == "centimeters",
      back["unit"].value() if back else "gone")
check("dhPersp reads it as index 2", dhPersp.unit_index(back) == 2,
      str(dhPersp.unit_index(back)))
check("and the height it was measured in came with it",
      abs(back["camera_height"].value() - 168.0) < 1e-6,
      "%.2f" % back["camera_height"].value())
check("so the scale note says centimeters", "centimeters" in
      (back["scale_note"].value() or dhPersp.set_scale_note(back) or
       back["scale_note"].value()), back["scale_note"].value()[:60])

print("\n" + "=" * 88)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 13: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
