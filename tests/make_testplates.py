"""Render ground-truth test plates for the perspective solve.

A tiled floor and two perpendicular walls, seen through a camera whose focal
length and orientation we choose. Placing guides on the rendered tile edges and
comparing the solve to these numbers is a real end-to-end test, including the
part where a human places the lines by eye.
"""
import os
import nuke

OUT = r"C:\temp\perspective_tests"
if not os.path.isdir(OUT):
    os.makedirs(OUT)

W, H = 1920, 1080
nuke.addFormat("%d %d 0 0 %d %d 1 testHD" % (W, H, W, H))
nuke.root()["format"].setValue("testHD")

CASES = [
    # name, focal mm, pitch, yaw
    ("24mm_wide", 24.0, -9.0, 32.0),
    ("35mm_normal", 35.0, -6.0, 38.0),
    ("85mm_long", 85.0, -2.5, 41.0),
]


def checker(n, name):
    cb = nuke.nodes.CheckerBoard2(format="testHD")
    cb.setName(name)
    if "boxsize" in cb.knobs():
        cb["boxsize"].setValue(n)
    for k, v in (("color0", [0.18, 0.18, 0.2, 1]), ("color1", [0.55, 0.55, 0.6, 1])):
        if k in cb.knobs():
            cb[k].setValue(v)
    if "linewidth" in cb.knobs():
        cb["linewidth"].setValue(2)
    return cb


for name, focal, rx, ry in CASES:
    floor = nuke.nodes.Card2() if "Card2" in dir(nuke.nodes) else nuke.nodes.Card()
    floor.setInput(0, checker(8, "floorTex_" + name))
    floor.setName("floor_" + name)
    if "orientation" in floor.knobs():
        floor["orientation"].setValue("ZX")
    if "uniform_scale" in floor.knobs():
        floor["uniform_scale"].setValue(900.0)
    for k in ("rows", "columns"):
        if k in floor.knobs():
            floor[k].setValue(2)

    wallA = nuke.nodes.Card2() if "Card2" in dir(nuke.nodes) else nuke.nodes.Card()
    wallA.setInput(0, checker(60, "wallATex_" + name))
    wallA.setName("wallA_" + name)
    if "orientation" in wallA.knobs():
        wallA["orientation"].setValue("XY")
    if "uniform_scale" in wallA.knobs():
        wallA["uniform_scale"].setValue(120.0)
    wallA["translate"].setValue([0.0, 55.0, -110.0])

    wallB = nuke.nodes.Card2() if "Card2" in dir(nuke.nodes) else nuke.nodes.Card()
    wallB.setInput(0, checker(60, "wallBTex_" + name))
    wallB.setName("wallB_" + name)
    if "orientation" in wallB.knobs():
        wallB["orientation"].setValue("YZ")
    if "uniform_scale" in wallB.knobs():
        wallB["uniform_scale"].setValue(120.0)
    wallB["translate"].setValue([110.0, 55.0, 0.0])

    scene = nuke.nodes.Scene()
    for i, g in enumerate((floor, wallA, wallB)):
        scene.setInput(i, g)

    cam = nuke.nodes.Camera2() if "Camera2" in dir(nuke.nodes) else nuke.nodes.Camera()
    cam["focal"].setValue(focal)
    cam["rotate"].setValue([rx, ry, 0.0])
    cam["translate"].setValue([0.0, 14.0, 0.0])

    bg = nuke.nodes.Constant(format="testHD", color=0.02)
    sr = nuke.nodes.ScanlineRender()
    sr.setInput(0, bg)
    sr.setInput(1, scene)
    sr.setInput(2, cam)
    if "antialiasing" in sr.knobs():
        sr["antialiasing"].setValue("high")

    path = os.path.join(OUT, "plate_%s.png" % name).replace("\\", "/")
    w = nuke.nodes.Write(file=path, file_type="png")
    w.setInput(0, sr)
    nuke.execute(w, 1, 1)

    ha, va = cam["haperture"].value(), cam["vaperture"].value()
    print("%-12s focal %5.1fmm  pitch %6.1f  yaw %6.1f  haperture %.3f  -> %s"
          % (name, focal, rx, ry, ha, os.path.basename(path)))

print("\nwritten to " + OUT)
