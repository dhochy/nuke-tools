"""Part sixteen: the guide colors itself from its role.

Red ground, green across, blue vertical. The point is the viewer: three guides on
a plate look identical until they are colored, and a color set by hand means
whatever you last remembered it to mean.

The part that needs testing is not that setValue works. It is the two ways this
could quietly take something away: overwriting a color someone chose on purpose,
and doing it again every time the script is opened.
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


class Knob(object):
    def __init__(self, nm):
        self._n = nm

    def name(self):
        return self._n


IC = Knob("inputChange")
W, H = 1920, 1080
nuke.addFormat("%d %d 0 0 %d %d 1 testHD" % (W, H, W, H))
nuke.root()["format"].setValue("testHD")
nuke.root()["first_frame"].setValue(1)
nuke.root()["last_frame"].setValue(1)
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


def rgb(node):
    return tuple(round(v, 3) for v in node["linecolor"].value()[:3])


# --------------------------------------------------------- 62. the mapping
print("\n=== 62. the color says what the guide is ===")
g1 = guide(plate, [(1500, 900), (300, 780), (1500, 200), (300, 360)])
check("a fresh guide is red, and a fresh guide is ground",
      rgb(g1) == (1.0, 0.0, 0.0) and g1["role"].value() == "ground", str(rgb(g1)))

g1["role"].setValue("across")
dhPersp.on_knob_changed(g1, Knob("role"))
check("across turns it green", rgb(g1) == (0.0, 1.0, 0.0), str(rgb(g1)))

g1["role"].setValue("vertical")
dhPersp.on_knob_changed(g1, Knob("role"))
check("vertical turns it blue", rgb(g1)[2] == 1.0 and rgb(g1)[0] == 0.0,
      str(rgb(g1)))

g1["role"].setValue("ground")
dhPersp.on_knob_changed(g1, Knob("role"))
check("and back to ground turns it red again", rgb(g1) == (1.0, 0.0, 0.0),
      str(rgb(g1)))
check("the three colors are all different",
      len(set(dhPersp.ROLE_COLORS)) == 3, str(dhPersp.ROLE_COLORS))

# ------------------------------------------ 63. the guide it works out itself
print("\n=== 63. a guide recognized as vertical colors itself too ===")
g2 = guide(g1, [(200, 100), (1700, 300), (200, 800), (1700, 700)])
g3 = guide(g2, [(500, 60), (512, 1020), (1400, 60), (1381, 1020)])
check("the third guide is still red and still says ground",
      rgb(g3) == (1.0, 0.0, 0.0) and g3["role"].value() == "ground", str(rgb(g3)))
for n in nuke.allNodes():
    n.setSelected(False)
s = nuke.createNode("dhPerspSolve", inpanel=False)
s.setInput(0, g3)
for n in nuke.allNodes():
    n.setSelected(False)
dhPersp.on_knob_changed(s, IC)
check("connecting the solve recognized it as the upright one",
      g3["role"].value() == "vertical", g3["role"].value())
check("and it went blue without anyone pressing anything",
      rgb(g3)[2] == 1.0 and rgb(g3)[0] == 0.0, str(rgb(g3)))
check("the two level guides were not recoloured",
      rgb(g1) == (1.0, 0.0, 0.0) and rgb(g2) == (1.0, 0.0, 0.0),
      "%s and %s" % (str(rgb(g1)), str(rgb(g2))))

# ------------------------------------------------- 64. a color set by hand
print("\n=== 64. a color chosen on purpose is not taken away ===")
g2["linecolor"].setValue([1.0, 1.0, 0.0, 1.0])          # the R/G/B buttons' job
check("it is yellow now", rgb(g2) == (1.0, 1.0, 0.0), str(rgb(g2)))
dhPersp.link_guides(s)
check("linking the solve leaves it alone", rgb(g2) == (1.0, 1.0, 0.0), str(rgb(g2)))
dhPersp.on_knob_changed(g2, Knob("p1a"))
check("moving its points leaves it alone", rgb(g2) == (1.0, 1.0, 0.0), str(rgb(g2)))
dhPersp.fit_to_format(g2, quiet=True)
check("fitting to format leaves it alone", rgb(g2) == (1.0, 1.0, 0.0), str(rgb(g2)))

# Names have to be read before the clear: a Python node handle does not survive
# it, and asking one for its name afterwards raises rather than returning stale
# information, which is the better of the two behaviors.
n2, n3 = g2.name(), g3.name()
path = os.path.join(TMP, "s16.nk").replace("\\", "/")
nuke.scriptSaveAs(path, overwrite=1)
nuke.scriptClear()
nuke.scriptOpen(path)
back = nuke.toNode(n2)
check("THE ONE THAT MATTERS: reopening the script does not reset it",
      back is not None and rgb(back) == (1.0, 1.0, 0.0),
      str(rgb(back)) if back else "gone")
vert = nuke.toNode(n3)
check("and the guide worked out as vertical is still blue",
      vert is not None and rgb(vert)[2] == 1.0,
      str(rgb(vert)) if vert else "gone")

# changing the role is the one thing that does overwrite it, which is the point
back["role"].setValue("across")
dhPersp.on_knob_changed(back, Knob("role"))
check("changing the role does overwrite it, which is the whole idea",
      rgb(back) == (0.0, 1.0, 0.0), str(rgb(back)))

print("\n" + "=" * 88)
npass = sum(1 for _, ok, _ in RESULTS if ok)
print("part 16: %d of %d passed" % (npass, len(RESULTS)))
for n, ok, d in RESULTS:
    if not ok:
        print("   FAILED: %s   %s" % (n, d))
