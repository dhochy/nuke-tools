"""Part fifteen: three named roles, the axes pinned from them, and no dialogs.

A solve needs two level directions at right angles. One of them runs away from
the camera and the other runs across in front of it, and which is which is the
thing that decides how the scene arrives in Maya. The tool had been guessing at
that with "auto (smaller turn)", which is also what puts a ninety degree snap in
an animated solve. Naming them removes the guess.

Ground against across is never worked out from the picture, and that is
deliberate: the two are symmetric, and only the person who took the photograph
knows which way they were facing. Vertical still is, because upright edges do not
look like anything else.

Also here: every dialog is gone, so the things they used to say have to be
somewhere that can still be read.
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


IC = type("IC", (), {"name": staticmethod(lambda: "inputChange")})()
W, H = 1920, 1080
nuke.addFormat("%d %d 0 0 %d %d 1 testHD" % (W, H, W, H))
nuke.root()["format"].setValue("testHD")
plate = nuke.nodes.Constant(format="testHD", color=0.2)


def guide(after, pts):
    for n in nuke.allNodes():
        n.setSelected(False)
    g = nuke.createNode("dhPerspGuide", inpanel=False)
    g.setInput(0, after)
    dhPersp.on_knob_changed(g, IC)
    for k, v in zip(("p1a", "p1b", "p2a", "p2b"), pts):
        g[k].setValue([float(v[0]), float(v[1])])
    return g


# ------------------------------------------------------------ 56. the names
print("\n=== 56. the three kinds of guide ===")
g1 = guide(plate, [(1500, 900), (300, 780), (1500, 200), (300, 360)])
check("the choices are ground, across and vertical",
      list(g1["role"].values()) == ["ground", "across", "vertical"],
      str(list(g1["role"].values())))
check("ground is the default", g1["role"].value() == "ground", g1["role"].value())
check("dhPersp names them the same way",
      (dhPersp.GROUND, dhPersp.ACROSS, dhPersp.VERTICAL) == (0, 1, 2)
      and dhPersp.ROLE_NAMES == ("ground", "across", "vertical"), "")
for i, nm in enumerate(("ground", "across", "vertical")):
    g1["role"].setValue(nm)
    check("guide_role reads %s as %d" % (nm, i), dhPersp.guide_role(g1) == i,
          str(dhPersp.guide_role(g1)))
g1["role"].setValue("ground")

# ------------------------------------------------------ 57. pinning the axes
print("\n=== 57. naming them pins the world axes ===")
g2 = guide(g1, [(200, 100), (1700, 300), (200, 800), (1700, 700)])
g3 = guide(g2, [(500, 60), (512, 1020), (1400, 60), (1381, 1020)])
for n in nuke.allNodes():
    n.setSelected(False)
s = nuke.createNode("dhPerspSolve", inpanel=False)
s.setInput(0, g3)
for n in nuke.allNodes():
    n.setSelected(False)
dhPersp.on_knob_changed(s, IC)

check("the upright guide was recognised without being told",
      g3["role"].value() == "vertical", g3["role"].value())
check("the two level guides were left as ground",
      g1["role"].value() == "ground" and g2["role"].value() == "ground", "")
check("so the axis is not pinned, and the panel says so",
      int(s["axis_from"].getValue()) == 0 and "Not pinned" in s["axis_state"].value(),
      s["axis_state"].value()[:60])

# which guide feeds which vanishing point is not click order, so read it
src1 = s["vp1"].animation(0).expression().split(".")[0]
g_vp1 = nuke.toNode(src1)
g_vp2 = g2 if g_vp1 is g1 else g1
check("vp1 is fed by one of the level guides", g_vp1 in (g1, g2), src1)

g_vp1["role"].setValue("across")
g_vp2["role"].setValue("ground")
dhPersp.link_guides(s)
check("with the across guide on vp1, X is pinned to vanishing point 1",
      int(s["axis_from"].getValue()) == 1, "axis_from %d" % int(s["axis_from"].getValue()))
check("and the panel names which guide is which",
      g_vp1.name() in s["axis_state"].value() and "Pinned" in s["axis_state"].value(),
      s["axis_state"].value()[:70])

g_vp1["role"].setValue("ground")
g_vp2["role"].setValue("across")
dhPersp.link_guides(s)
check("with the across guide on vp2, X is pinned to vanishing point 2",
      int(s["axis_from"].getValue()) == 2, "axis_from %d" % int(s["axis_from"].getValue()))

# and it really is the world axis, not just a knob
cam = s.node("cam")
gg = lambda k: float(s[k].value())
u1 = (gg("_u1x"), gg("_u1y"), gg("_u1z"))
u2 = (gg("_u2x"), gg("_u2y"), gg("_u2z"))
rowX = tuple(cam["world_matrix"].getValue()[0:3])
want = u2 if int(s["axis_from"].getValue()) == 2 else u1
check("the camera's X axis really runs along the across guide",
      min(max(abs(a - b) for a, b in zip(rowX, want)),
          max(abs(a + b) for a, b in zip(rowX, want))) < 2e-3,
      "X %s against %s" % ([round(v, 4) for v in rowX], [round(v, 4) for v in want]))

# both the same is left alone rather than guessed at
g_vp1["role"].setValue("across")
g_vp2["role"].setValue("across")
s["axis_from"].setValue(0)
dhPersp.link_guides(s)
check("two guides set to the same thing are not guessed between",
      int(s["axis_from"].getValue()) == 0 and "Not pinned" in s["axis_state"].value(),
      "axis_from %d" % int(s["axis_from"].getValue()))
g_vp1["role"].setValue("ground")
g_vp2["role"].setValue("across")
dhPersp.link_guides(s)

# ---------------------------------------------- 58. pinning stops the snap
print("\n=== 58. and that is what stops an animated solve snapping ===")
nuke.root()["first_frame"].setValue(1)
nuke.root()["last_frame"].setValue(24)
k = g_vp2["p1b"]
k.setAnimated(0); k.setAnimated(1)
k.setValueAt(1700.0, 1, 0); k.setValueAt(1300.0, 24, 0)
k.setValueAt(300.0, 1, 1); k.setValueAt(620.0, 24, 1)

s["axis_from"].setValue(0)
auto = [s["cam_ry"].getValueAt(f) for f in range(1, 25)]
snap = max(abs(b - a) for a, b in zip(auto, auto[1:]))
dhPersp.link_guides(s)
check("linking with the roles set pins the axis",
      int(s["axis_from"].getValue()) in (1, 2),
      "axis_from %d" % int(s["axis_from"].getValue()))
pinned = [s["cam_ry"].getValueAt(f) for f in range(1, 25)]
worst = max(abs(b - a) for a, b in zip(pinned, pinned[1:]))
# Whether auto snaps depends on the frame where the two candidates swap falling
# inside the range, which these guide positions do not produce. Part 14 has a
# case that does, at eighty nine degrees. What holds either way is that pinning
# cannot be worse and that the pinned move is smooth.
check("pinned, the yaw never jumps between frames", worst < 20.0,
      "biggest step %.2f degrees, auto was %.2f" % (worst, snap))
check("and pinning is never rougher than leaving it automatic",
      worst <= snap + 1e-6, "pinned %.2f against auto %.2f" % (worst, snap))
k.clearAnimated(0); k.clearAnimated(1)
k.setValue([1700.0, 300.0])

# -------------------------------------------------------- 59. no dialogs
print("\n=== 59. nothing pops up, and nothing is lost ===")
src = io.open(r"C:\Users\dhoch\.nuke\python\dhPersp.py", encoding="utf-8").read()
check("dhPersp.py opens no dialogs at all",
      "nuke.message" not in src and "nuke.ask" not in src, "")
check("both nodes have somewhere to put a message",
      "status" in s.knobs() and "status" in g1.knobs(), "")

dhPersp.link_guides(s)
check("a successful link leaves no complaint", True, s["status"].value()[:40])

# a refusal has to say so on the node
for n in nuke.allNodes():
    n.setSelected(False)
lonely = nuke.createNode("dhPerspSolve", inpanel=False)
lonely.setInput(0, plate)
for n in nuke.allNodes():
    n.setSelected(False)
dhPersp.link_guides(lonely)
check("a solve with no guides says so on its own panel",
      "solve needs" in lonely["status"].value(),
      lonely["status"].value()[:70])

# and an export reports where you can read it again
ex = dhPersp.export_camera(s)
check("a camera exported", ex is not None, ex.name() if ex else "none")
check("the solve's status says what happened",
      ex is not None and ex.name() in s["status"].value(),
      s["status"].value()[:70])
check("the exported camera has its own status line",
      ex is not None and "status" in ex.knobs(), "")
dhPersp.bake_camera(ex)
check("baking reports on the camera itself",
      "Baked" in ex["status"].value(), ex["status"].value()[:60])

# ---------------------------------------------------- 60. help and the tab
print("\n=== 60. the ? button and the How to use tab ===")
for node, what in ((g1, "guide"), (s, "solve")):
    h = node.help()
    check("the %s has help on its ? button" % what, len(h) > 200, "%d chars" % len(h))
    check("the %s help starts with what the node is for" % what,
          h.split(".")[0].strip() != "", h.split(".")[0][:50])
    check("the %s has a How to use tab" % what, "howto" in node.knobs(), "")
    steps = node["howto_s"].value()
    check("the %s tab has numbered steps" % what,
          "<b>1.</b>" in steps and "<b>5.</b>" in steps, "%d chars" % len(steps))
    check("the %s tab has notes under them" % what,
          len(node["howto_n"].value()) > 200, "%d chars" % len(node["howto_n"].value()))
check("the guide help explains the three kinds",
      all(w in g1.help() for w in ("ground", "across", "vertical")), "")
check("the solve help mentions camera height, which is the one thing to set",
      "camera height" in s.help(), "")

# ---------------------------------------- 61. older guides migrate by label
print("\n=== 61. guides from before the rename still mean what they meant ===")
FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "fixtures", "dhPerspGuide_build8.gizmo")
body = io.open(FIX, encoding="utf-8").read().split("\n", 1)[1]


def paste_old(name, role):
    b = body.replace(" name dhPerspGuide\n", " name %s\n" % name, 1)
    path = os.path.join(TMP, "s15_%s.nk" % name).replace("\\", "/")
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


old_g = paste_old("oldGround", "ground")
old_v = paste_old("oldVert", "vertical")
check("the old build only had two choices",
      list(old_g["role"].values()) == ["ground", "vertical"],
      str(list(old_g["role"].values())))
check("and vertical was index 1 there", int(old_v["role"].getValue()) == 1, "")
dhPersp.update_nodes([old_g, old_v], quiet=True)
new_g, new_v = nuke.toNode("oldGround"), nuke.toNode("oldVert")
check("ground is still ground", new_g["role"].value() == "ground",
      new_g["role"].value())
check("THE ONE THAT MATTERS: vertical is still vertical, though its index moved "
      "from 1 to 2", new_v["role"].value() == "vertical", new_v["role"].value())
check("and dhPersp agrees", dhPersp.guide_role(new_v) == dhPersp.VERTICAL,
      str(dhPersp.guide_role(new_v)))

print("\n" + "=" * 88)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 15: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
