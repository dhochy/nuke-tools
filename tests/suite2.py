"""Part two: guide behaviour, linking, export, formats, persistence."""
import os
import nuke
from math import hypot


nuke.pluginAddPath(r"C:\Users\dhoch\.nuke\Gizmos\DH_Tools\3D")
import dhPersp

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("  %-4s %-48s %s" % ("PASS" if ok else "FAIL", name, detail))


class _IC(object):
    def name(self):
        return "inputChange"


IC = _IC()

for w, h, nm in ((1920, 1080, "hd"), (864, 1216, "tall"), (4096, 1716, "wide"), (512, 512, "sq")):
    nuke.addFormat("%d %d 0 0 %d %d 1 fmt_%s" % (w, h, w, h, nm))
nuke.root()["format"].setValue("fmt_hd")

# ------------------------------------------------------------ formats
print("\n=== 6. fitting to format ===")
bad = []
for nm, w, h in (("hd", 1920, 1080), ("tall", 864, 1216), ("wide", 4096, 1716), ("sq", 512, 512)):
    p = nuke.nodes.Constant(format="fmt_" + nm)
    p.setSelected(True)
    g = nuke.createNode("dhPerspGuide", inpanel=False)
    for n in nuke.allNodes():
        n.setSelected(False)
    pts = {k: g[k].value() for k in ("p1a", "p1b", "p2a", "p2b")}
    want = {"p1a": (0, 0), "p1b": (w / 3.0, h / 3.0), "p2a": (w, 0), "p2b": (2 * w / 3.0, h / 3.0)}
    for k, (cx, cy) in want.items():
        if abs(pts[k][0] - cx) > 1 or abs(pts[k][1] - cy) > 1:
            bad.append("%s %s got %s want %s" % (nm, k, [round(v) for v in pts[k]], (round(cx), round(cy))))
check("guide fits every format on creation", not bad, str(bad[:2]))

print("\n=== 7. re-fit on plate change, only when untouched ===")
small = nuke.nodes.Constant(format="fmt_tall")
big = nuke.nodes.Constant(format="fmt_wide")
small.setSelected(True)
ga = nuke.createNode("dhPerspGuide", inpanel=False)
for n in nuke.allNodes():
    n.setSelected(False)
ga.setInput(0, big)
dhPersp.on_knob_changed(ga, IC)
check("untouched guide re-fits to a new plate",
      abs(ga["p1b"].value()[0] - 4096 / 3.0) < 1, "p1b.x %.0f" % ga["p1b"].value()[0])

small.setSelected(True)
gb = nuke.createNode("dhPerspGuide", inpanel=False)
for n in nuke.allNodes():
    n.setSelected(False)
gb["p1b"].setValue([123.0, 456.0])
gb.setInput(0, big)
dhPersp.on_knob_changed(gb, IC)
check("placed points survive a plate change",
      [round(v) for v in gb["p1b"].value()] == [123, 456], str([round(v) for v in gb["p1b"].value()]))

# ------------------------------------------------------------ added lines
print("\n=== 8. additional lines ===")
plate = nuke.nodes.Constant(format="fmt_hd")
plate.setSelected(True)
g = nuke.createNode("dhPerspGuide", inpanel=False)
for n in nuke.allNodes():
    n.setSelected(False)
check("fresh guide shows no extra line handles",
      not [i for i in range(1, 13) if g["add%d" % i].visible()], "")
first = dhPersp.add_line(g)
check("first added line lands in the middle",
      abs(g["add%d" % first].value()[0] - 1920 * 0.5) < 2, "x %.0f" % g["add%d" % first].value()[0])
for _ in range(11):
    dhPersp.add_line(g)
check("twelve lines fill every slot", len(dhPersp.active_lines(g)) == 12,
      "%d active" % len(dhPersp.active_lines(g)))
check("thirteenth is refused", dhPersp.add_line(g) is None, "")
dhPersp.del_line(3, g)
check("delete removes one and hides it",
      3 not in dhPersp.active_lines(g) and not g["add3"].visible(), "")
dhPersp.clear_lines(g)
check("clear all empties every slot", not dhPersp.active_lines(g), "")

# ------------------------------------------------------------ vanishing point drag
print("\n=== 9. dragging the vanishing point ===")
dhPersp.fit_to_format(g)
worst = 0.0
anchors_held = True
for target in ([1500., 900.], [300., 700.], [-400., 1200.], [2500., 200.]):
    a1 = list(g["p1a"].value())
    a2 = list(g["p2a"].value())
    L1 = hypot(g["p1b"].value()[0] - a1[0], g["p1b"].value()[1] - a1[1])
    g["vp_drag"].setValue(target)
    dhPersp.on_knob_changed(g, g["vp_drag"])
    v = g["vp"].value()
    worst = max(worst, hypot(v[0] - target[0], v[1] - target[1]))
    if [round(x, 2) for x in g["p1a"].value()] != [round(x, 2) for x in a1]:
        anchors_held = False
    if [round(x, 2) for x in g["p2a"].value()] != [round(x, 2) for x in a2]:
        anchors_held = False
    L1b = hypot(g["p1b"].value()[0] - a1[0], g["p1b"].value()[1] - a1[1])
    if abs(L1 - L1b) > 0.5:
        anchors_held = False
check("dragged vanishing point lands exactly", worst < 0.01, "worst %.4f px" % worst)
check("anchors hold and arm lengths are preserved", anchors_held, "")

# ------------------------------------------------------------ parallel families
print("\n=== 10. parallel guide lines ===")
g["p1a"].setValue([500., 0.]); g["p1b"].setValue([500., 1080.])
g["p2a"].setValue([1400., 0.]); g["p2b"].setValue([1400., 1080.])
v = g["vp"].value()
check("parallel verticals give a finite-safe vanishing point",
      abs(v[0] - 500.) < 1 and abs(v[1]) > 1e6 and v[1] == v[1], "vp (%.0f, %.3g)" % (v[0], v[1]))

# ------------------------------------------------------------ independence
print("\n=== 11. two guides are independent ===")
h1 = nuke.createNode("dhPerspGuide", inpanel=False); h1.setInput(0, plate)
h2 = nuke.createNode("dhPerspGuide", inpanel=False); h2.setInput(0, plate)
h1["p1b"].setValue([111., 222.])
check("moving one guide leaves the other alone",
      [round(v) for v in h2["p1b"].value()] != [111, 222],
      "h2 p1b %s" % [round(v) for v in h2["p1b"].value()])

# ------------------------------------------------------------ auto link + export
print("\n=== 12. auto link and camera export ===")
a = nuke.createNode("dhPerspGuide", inpanel=False); a.setInput(0, plate)
b = nuke.createNode("dhPerspGuide", inpanel=False); b.setInput(0, a)
b["p1a"].setValue([1920., 1000.]); b["p1b"].setValue([1200., 880.])
b["p2a"].setValue([1200., 300.]); b["p2b"].setValue([1900., 200.])
s = nuke.createNode("dhPerspSolve", inpanel=False); s.setInput(0, b)
for n in nuke.allNodes():
    n.setSelected(False)
dhPersp.on_knob_changed(s, IC)
check("solve auto-links to guides in its input chain",
      s["vp1"].hasExpression(0) and s["vp2"].hasExpression(0), s["linked_to"].value()[:46])
cam = dhPersp.export_camera(s)
check("exported camera lands in the main node graph", "." not in cam.fullName(), cam.fullName())
check("exported camera is not inside the gizmo",
      cam.name() not in [n.name() for n in s.nodes()], "")
before = round(cam["focal"].value(), 3)
a["p1b"].setValue([600., 700.])
check("exported camera follows the guides",
      round(cam["focal"].value(), 3) != before,
      "%.3f -> %.3f" % (before, cam["focal"].value()))
dhPersp.bake_camera(cam)
frozen = round(cam["focal"].value(), 3)
a["p1b"].setValue([500., 500.])
check("baked camera stops following", round(cam["focal"].value(), 3) == frozen,
      "%.3f" % cam["focal"].value())

# ------------------------------------------------------------ persistence
print("\n=== 13. save and reload ===")
dhPersp.add_line(g); dhPersp.add_line(g)
g["add1"].setValue([777., 333.])
name = g.name()
path = r"C:\temp\dgtest\suite_state.nk"
nuke.scriptSaveAs(path, overwrite=1)
nuke.scriptClear()
nuke.scriptOpen(path)
g2 = nuke.toNode(name)
check("added lines survive reload", len(dhPersp.active_lines(g2)) == 2,
      "%d active" % len(dhPersp.active_lines(g2)))
check("their handles are visible again after reload",
      all(g2["add%d" % i].visible() for i in dhPersp.active_lines(g2)), "")
check("moved point value survives reload",
      [round(v) for v in g2["add1"].value()] == [777, 333],
      str([round(v) for v in g2["add1"].value()]))

print("\n" + "=" * 76)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 2: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
