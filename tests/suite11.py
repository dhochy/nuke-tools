"""Part eleven: nodes bring themselves up to date when a script is opened.

There is no menu command for this any more. Housekeeping that depends on
someone knowing which build their nodes are is housekeeping that does not
happen, so it runs on script load in the GUI instead, and the render farm keeps
running the internals the script was saved with, which is the whole reason these
are Groups.

The thing that has to be right for that to keep working is recognition. A node
was identified as a solve by having a gridsize knob, and it kept working until
the build that removed gridsize: after it, a current node could not be
recognized, so a future build could never have updated one. That is the failure
this part is mostly about.
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
    print("  %-4s %-62s %s" % ("PASS" if ok else "FAIL", name, detail))


W, H = 1920, 1080
nuke.addFormat("%d %d 0 0 %d %d 1 testHD" % (W, H, W, H))
nuke.root()["format"].setValue("testHD")
plate = nuke.nodes.Constant(format="testHD")

# ------------------------------------------------------- 40. recognition
print("\n=== 40. a current node can still be recognized, or it can never be updated ===")
g1 = nuke.createNode("dhPerspGuide", inpanel=False)
g1.setInput(0, plate)
g1["p1a"].setValue([1500.0, 900.0]); g1["p1b"].setValue([300.0, 780.0])
g1["p2a"].setValue([1500.0, 200.0]); g1["p2b"].setValue([300.0, 360.0])
g2 = nuke.createNode("dhPerspGuide", inpanel=False)
g2.setInput(0, g1)
g2["p1a"].setValue([200.0, 100.0]); g2["p1b"].setValue([1700.0, 300.0])
g2["p2a"].setValue([200.0, 800.0]); g2["p2b"].setValue([1700.0, 700.0])
s = nuke.createNode("dhPerspSolve", inpanel=False)
s.setInput(0, g2)
for n in nuke.allNodes():
    n.setSelected(False)
dhPersp.on_knob_changed(s, type("IC", (), {"name": staticmethod(lambda: "inputChange")})())

check("a node at the current build is recognized as a solve", dhPersp.is_solve(s),
      "build %d" % dhPersp.node_build(s))
check("and _class_of names it, which is what update_nodes rebuilds from",
      dhPersp._class_of(s) == "dhPerspSolve", str(dhPersp._class_of(s)))
check("a guide is recognized as a guide", dhPersp.is_persplines(g1), "")
check("and is not mistaken for a solve", not dhPersp.is_solve(g1), "")
check("a solve is not mistaken for a guide", not dhPersp.is_persplines(s), "")
check("an unrelated node is neither",
      not dhPersp.is_solve(plate) and not dhPersp.is_persplines(plate)
      and dhPersp._class_of(plate) is None, "")
check("nothing in a current script reads as stale", not dhPersp.stale_nodes(),
      "%d stale" % len(dhPersp.stale_nodes()))

# the knob it used to be recognized by is the one that was removed
check("recognition does not depend on a knob that has been deleted",
      "gridsize" not in s.knobs() and dhPersp.is_solve(s), "")

# --------------------------------------------- 41. self update on script load
print("\n=== 41. opening a script with old nodes updates it, quietly ===")
FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "fixtures", "dhPerspSolve_build5.gizmo")
old_body = io.open(FIX, encoding="utf-8").read().split("\n", 1)[1]
old_body = old_body.replace(" name dhPerspSolve\n", " name dhOldSolve\n", 1)
paste = os.path.join(TMP, "s11_paste.nk").replace("\\", "/")
io.open(paste, "w", encoding="utf-8", newline="").write(
    "set cut_paste_input [stack 0]\n" + old_body)
for n in nuke.allNodes():
    n.setSelected(False)
g2.setSelected(True)
nuke.nodePaste(paste)
old = nuke.toNode("dhOldSolve")
old.setInput(0, g2)
old["vp1"].setExpression(g1.name() + ".vp.x", 0)
old["vp1"].setExpression(g1.name() + ".vp.y", 1)
old["vp2"].setExpression(g2.name() + ".vp.x", 0)
old["vp2"].setExpression(g2.name() + ".vp.y", 1)
old["camera_height"].setValue(6.75)

path = os.path.join(TMP, "s11_old.nk").replace("\\", "/")
nuke.scriptSaveAs(path, overwrite=1)
nuke.scriptClear()

# register the callback the way menu.py does, since menu.py is GUI only and
# this is running in a terminal
nuke.addOnScriptLoad(lambda: dhPersp.update_on_load())
nuke.scriptOpen(path)

again = nuke.toNode("dhOldSolve")
check("the old node is still there under its own name", again is not None, "")
check("opening the script brought it to the current build",
      again is not None and dhPersp.node_build(again) == dhPersp.BUILD,
      "build %d" % (dhPersp.node_build(again) if again else -1))
check("the card is gone from it", again is not None
      and again.node("floorgrid") is None, "")
check("its camera height survived",
      again is not None and abs(again["camera_height"].value() - 6.75) < 1e-6,
      "%.4f" % (again["camera_height"].value() if again else -1))
check("its guide links survived",
      again is not None and again["vp1"].hasExpression(0), "")
check("it is still wired into the chain",
      again is not None and again.input(0) is not None, "")
check("nothing is left stale after the load", not dhPersp.stale_nodes(),
      "%d stale" % len(dhPersp.stale_nodes()))
check("and the script is not left dirty, so nobody is asked to save a change "
      "they did not make", not nuke.root().modified(), "")

# opening a script that is already current must change nothing at all
nuke.scriptSaveAs(path, overwrite=1)
nuke.scriptClear()
nuke.scriptOpen(path)
check("opening an up to date script rebuilds nothing",
      not dhPersp.update_on_load(), "")
check("and leaves it clean", not nuke.root().modified(), "")

# ------------------------------------------------------- 42. no menu command
print("\n=== 42. it is not a menu item ===")
menu = io.open(r"C:\Users\dhoch\.nuke\menu.py", encoding="utf-8").read()
check("the update menu entry is gone",
      "Update dhPersp nodes" not in menu, "")
check("it is registered on script load instead",
      "addOnScriptLoad" in menu and "update_on_load" in menu, "")
check("and only from menu.py, so a render runs what the script was saved with",
      "update_on_load" not in
      io.open(r"C:\Users\dhoch\.nuke\init.py", encoding="utf-8").read(), "")

print("\n" + "=" * 88)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 11: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
