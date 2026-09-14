"""Part thirteen: renaming an option must not move a node that already has one.

The first role was called "ground" and is called "horizontal" now, because both
of the guides a solve needs mark horizontal directions and because the lines
never had to be on the ground. That is a label change, and a label change is the
one kind of edit that can quietly corrupt existing work: rebuilding a node copies
knob values across by name, an Enumeration knob's value() is its label, and
setting a label the new build does not have fails silently and leaves the knob at
its default.

Here that default happens to be the right answer, which is worse than it being
wrong, because nothing would have shown up. So this tests the case that matters:
a guide saved as vertical, whose label did not change but whose index would be
hit by any reordering, and a guide saved as ground, whose label did.
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
check("the choices are horizontal and vertical", opts == ["horizontal", "vertical"],
      str(opts))
check("horizontal is the default and is index 0",
      g["role"].value() == "horizontal" and int(g["role"].getValue()) == 0, "")
tip = g["role"].tooltip()
check("the tooltip says the lines need not be on the ground",
      "do not have to be on the ground" in tip, tip[:70])
check("and that a third guide is recognised on its own",
      "recognised" in tip, "")

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
check("and 'ground' became 'horizontal', which is the same thing",
      now_ground is not None and now_ground["role"].value() == "horizontal",
      now_ground["role"].value() if now_ground else "gone")
check("THE ONE THAT MATTERS: the vertical guide is still vertical",
      now_vert is not None and now_vert["role"].value() == "vertical",
      now_vert["role"].value() if now_vert else "gone")
check("guide_role agrees for both",
      dhPersp.guide_role(now_ground) == 0 and dhPersp.guide_role(now_vert) == 1,
      "%d and %d" % (dhPersp.guide_role(now_ground), dhPersp.guide_role(now_vert)))
ok = True
for nm, want in pts.items():
    n = nuke.toNode(nm)
    for k, v in zip(("p1a", "p1b", "p2a", "p2b"), want):
        got = list(n[k].value())
        if abs(got[0] - v[0]) > 1e-4 or abs(got[1] - v[1]) > 1e-4:
            ok = False
check("every placed point survived the rename", ok, "%d guides" % len(pts))

# ---------------------------------- 50. and a label that is simply gone
print("\n=== 50. a value whose label no longer exists falls back to its index ===")
s = nuke.createNode("dhPerspSolve", inpanel=False)
s.setInput(0, now_vert)
check("the working unit knob is a pulldown with three options",
      list(s["unit"].values()) == ["feet", "metres", "centimetres"],
      str(list(s["unit"].values())))
s["unit"].setValue(2)
check("set to centimetres", s["unit"].value() == "centimetres", s["unit"].value())
name = s.name()
s["_build"].setValue(1)
done = dhPersp.update_nodes([s], quiet=True)
back = nuke.toNode(name)
check("the solve rebuilt", back is not None and done == [name], str(done))
check("and the unit is still centimetres",
      back is not None and back["unit"].value() == "centimetres",
      back["unit"].value() if back else "gone")
check("which dhPersp reads as index 2",
      back is not None and dhPersp.unit_index(back) == 2,
      str(dhPersp.unit_index(back)) if back else "gone")

print("\n" + "=" * 88)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 13: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
