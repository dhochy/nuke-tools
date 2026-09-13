"""A corridor plate: floor running AWAY in Z and ACROSS in X, plus walls.

This is the shape David's alley shot actually is, unlike the 38 degree yaw of the
first test plates. It also lets us find out how the solve behaves as the yaw
approaches zero, where one family of lines stops converging at all.
"""
import os
import nuke

OUT = r"C:\temp\perspective_tests"
if not os.path.isdir(OUT):
    os.makedirs(OUT)

W, H = 1920, 1080
nuke.addFormat("%d %d 0 0 %d %d 1 testHD" % (W, H, W, H))
nuke.root()["format"].setValue("testHD")


def tex(box, c0, c1, name):
    cb = nuke.nodes.CheckerBoard2(format="testHD")
    cb.setName(name)
    if "boxsize" in cb.knobs():
        cb["boxsize"].setValue(box)
    if "color0" in cb.knobs():
        cb["color0"].setValue(c0)
    if "color1" in cb.knobs():
        cb["color1"].setValue(c1)
    if "linewidth" in cb.knobs():
        cb["linewidth"].setValue(3)
    return cb


def card(orient, scale, translate, texture, name):
    c = nuke.nodes.Card2() if "Card2" in dir(nuke.nodes) else nuke.nodes.Card()
    c.setInput(0, texture)
    c.setName(name)
    if "orientation" in c.knobs():
        c["orientation"].setValue(orient)
    if "uniform_scale" in c.knobs():
        c["uniform_scale"].setValue(scale)
    c["translate"].setValue(translate)
    return c


CASES = [("corridor_35mm_yaw2", 35.0, -7.0, 2.0),
         ("corridor_35mm_yaw15", 35.0, -7.0, 15.0)]

for name, focal, rx, ry in CASES:
    floor = card("ZX", 240.0, [0.0, 0.0, -80.0],
                 tex(40, [0.15, 0.15, 0.17, 1], [0.5, 0.5, 0.55, 1], "ft_" + name),
                 "floor_" + name)
    left = card("YZ", 120.0, [-26.0, 26.0, -80.0],
                tex(40, [0.1, 0.12, 0.16, 1], [0.38, 0.42, 0.5, 1], "lt_" + name),
                "left_" + name)
    right = card("YZ", 120.0, [26.0, 26.0, -80.0],
                 tex(40, [0.1, 0.12, 0.16, 1], [0.38, 0.42, 0.5, 1], "rt_" + name),
                 "right_" + name)

    scene = nuke.nodes.Scene()
    for i, g in enumerate((floor, left, right)):
        scene.setInput(i, g)

    cam = nuke.nodes.Camera2() if "Camera2" in dir(nuke.nodes) else nuke.nodes.Camera()
    cam["focal"].setValue(focal)
    cam["rotate"].setValue([rx, ry, 0.0])
    cam["translate"].setValue([0.0, 9.0, 0.0])

    bg = nuke.nodes.Constant(format="testHD", color=0.03)
    sr = nuke.nodes.ScanlineRender()
    sr.setInput(0, bg); sr.setInput(1, scene); sr.setInput(2, cam)
    if "antialiasing" in sr.knobs():
        sr["antialiasing"].setValue("high")

    path = os.path.join(OUT, "plate_%s.png" % name).replace("\\", "/")
    w = nuke.nodes.Write(file=path, file_type="png")
    w.setInput(0, sr)
    nuke.execute(w, 1, 1)
    print("%-22s focal %.1f  pitch %.1f  yaw %.1f" % (name, focal, rx, ry))
print("written to " + OUT)
