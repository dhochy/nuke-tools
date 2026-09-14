"""The Pantheon plate, three guides, the setup that refused to link.

667 x 1000, a 35mm lens. Two guides along the ground directions and a third
along the columns, none of them told what they are. This is the case that came
back with "Need exactly two dhPerspGuide nodes, found 3", and it is also a fair
test of the solve, because the answer is known.
"""
import os
import nuke

nuke.pluginAddPath(r"C:\Users\dhoch\.nuke\Gizmos\DH_Tools\3D")
import dhPersp

TMP = r"C:\temp\dgtest"
PLATE = r"C:\Users\dhoch\Downloads\rome_35mm.jpg"

read = nuke.nodes.Read(file=PLATE.replace("\\", "/"))
W, H = read.width(), read.height()
print("plate %d x %d" % (W, H))


def guide(after, pts, colour):
    for n in nuke.allNodes():
        n.setSelected(False)
    g = nuke.createNode("dhPerspGuide", inpanel=False)
    g.setInput(0, after)
    dhPersp.on_knob_changed(
        g, type("IC", (), {"name": staticmethod(lambda: "inputChange")})())
    for k, v in zip(("p1a", "p1b", "p2a", "p2b"), pts):
        g[k].setValue([float(v[0]), float(v[1])])
    g["linecolor"].setValue(list(colour))
    return g


# Nuke's y runs up from the bottom of frame.
# Ground direction one: the step edge and the cornice, running left to right and
# receding slightly. Ground direction two: the portico floor edges going in.
g1 = guide(read, [(60, 690), (640, 700), (120, 450), (610, 448)], (0, 1, 0, 1))
g2 = guide(g1, [(90, 250), (600, 120), (30, 640), (655, 560)], (1, 0, 0, 1))
# The columns. Steep, and converging a long way above frame.
g3 = guide(g2, [(196, 60), (198, 480), (430, 60), (424, 480)], (0, 0, 1, 1))

for n in nuke.allNodes():
    n.setSelected(False)
s = nuke.createNode("dhPerspSolve", inpanel=False)
s.setInput(0, g3)
for n in nuke.allNodes():
    n.setSelected(False)
dhPersp.on_knob_changed(
    s, type("IC", (), {"name": staticmethod(lambda: "inputChange")})())

print("\nthe third guide, before anything is told to the tool:")
print("  looks vertical           : %s" % dhPersp.looks_vertical(g3))
print("  its vanishing point      : %.0f, %.0f" % tuple(g3["vp"].value()))
print("  the two ground guides do : %s, %s"
      % (dhPersp.looks_vertical(g1), dhPersp.looks_vertical(g2)))

ground, vertical = dhPersp.split_guides([g1, g2, g3])
print("\nsplit_guides -> %d ground, %d vertical" % (len(ground), len(vertical)))
print("  roles now: %s"
      % [(g.name(), int(g["role"].getValue())) for g in (g1, g2, g3)])

for n in nuke.allNodes():
    n.setSelected(False)
dhPersp.link_guides(s)
print("\nafter pressing 'solve from guides':")
print("  vp1 linked               : %s" % s["vp1"].hasExpression(0))
print("  vp2 linked               : %s" % s["vp2"].hasExpression(0))
print("  vp3 linked               : %s" % s["vp3"].hasExpression(0))
print("  using the vertical       : %s" % bool(s["use_vertical"].value()))
print("  third vp actually usable : %s" % (s["_v3ok"].value() > 0.5))
print("  lens axis                : %.1f, %.1f   (centre is %.1f, %.1f)"
      % (s["_px"].value(), s["_py"].value(), W / 2.0, H / 2.0))
print("  focal                    : %.2f mm   (the plate says 35)"
      % s["cam_focal"].value())
print("  roll                     : %.2f deg" % s["cam_rz"].value())
print("  solve stands up          : %s" % (s["_solveok"].value() > 0.5))
dhPersp.set_verdict(s)
print("  verdict                  : %s" % s["verdict"].value()[:100])

s["use_vertical"].setValue(False)
print("\nwith the vertical guide switched off:")
print("  focal                    : %.2f mm" % s["cam_focal"].value())
s["use_vertical"].setValue(True)

s["camera_height"].setValue(5.5)
s["cellsize"].setValue(2.0)
s["show_horizon"].setValue(True)
for tag, fade in (("rome_nofade", False), ("rome_fade", True)):
    s["fade_far"].setValue(fade)
    w = nuke.nodes.Write(file=os.path.join(TMP, tag + ".png").replace("\\", "/"),
                         file_type="png", datatype="8 bit")
    w.setInput(0, s)
    nuke.execute(w, 1, 1)
    nuke.delete(w)
    print("  wrote %s.png  (thinning %s)" % (tag, "on" if fade else "off"))
