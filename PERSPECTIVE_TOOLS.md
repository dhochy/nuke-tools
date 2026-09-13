# Perspective tools

`dhPerspGuide` and `dhPerspSolve`. Place perspective guide lines on a plate, get the
vanishing points, and solve a camera and ground plane from them.

Both are Groups, so their definitions travel inside the `.nk` and render on a farm
blade that does not have them installed.

## What they do

**dhPerspGuide** — two pairs of points define two lines; where those lines meet is the
vanishing point, reported on a read-only `vp` knob. Up to 12 extra guide lines can be
added, each running from the vanishing point through a point you place. Add and delete
buttons create and remove them; unused ones stay hidden so the viewer is not cluttered.

**dhPerspSolve** — takes two `dhPerspGuide` vanishing points and gives you three things:
the horizon line through them, a 3D wireframe floor rendered through a solved camera,
and the camera itself. If the floor grid lies flat on the floor in the plate, the solve
is right. **export camera** drops a copy into the node graph, expression-linked so it
keeps following the guides, with a **bake values** button to freeze it.

If you know the real focal length, tick **I know the focal length** on the Camera Solve
tab and enter it with the film back. The vanishing points then only set orientation,
which is both more accurate and the way out when the geometry cannot produce a focal.

## Install on a workstation

Clone or copy this repo, then add to `~/.nuke/init.py`:

```python
nuke.pluginAddPath('/path/to/nuke-tools/gizmos/3D')
nuke.pluginAddPath('/path/to/nuke-tools/icons')
nuke.pluginAddPath('/path/to/nuke-tools/python')
```

`init.py`, not `menu.py`. Nuke runs `init.py` in both GUI and `nuke -t` sessions but only
runs `menu.py` in the GUI, so paths added there are missing from terminal and farm renders.

Then in `~/.nuke/menu.py`:

```python
m = nuke.menu("Nodes").addMenu("DH_Tools")
t = m.addMenu("3D")
t.addCommand("dhPerspGuide", "nuke.createNode('dhPerspGuide')", icon="dhPerspGuide.png")
t.addCommand("dhPerspSolve", "nuke.createNode('dhPerspSolve')", icon="dhPerspSolve.png")

nuke.menu('Nuke').addCommand('Tools/Perspective/Horizon from 2 dhPerspGuide',
                             'import dhPersp; dhPersp.horizon()')
nuke.menu('Nuke').addCommand('Tools/Perspective/3D Floor from 2 dhPerspGuide',
                             'import dhPersp; dhPersp.floor_3d()')
nuke.menu('Nuke').addCommand('Tools/Perspective/Align Camera from 2 dhPerspGuide',
                             'import dhPersp; dhPersp.align_camera()', 'Shift+V')
```

`python/dhPersp.py` must be importable, which the `pluginAddPath` above handles. Without
it the gizmos still load and draw, but the add/delete buttons and the camera tools do not
work.

## Notes

Filenames are case sensitive on Linux and Nuke registers a gizmo by its filename, so
`dhPerspGuide.gizmo` must keep exactly that spelling to match `createNode('dhPerspGuide')`.

The lines are drawn analytically by an Expression node rather than as RotoPaint strokes.
Expressions stored inside RotoPaint control points no longer drive the raster in Nuke 15.2,
16.0 or 17.0, which is what broke the tool this replaces.

## The maths, and how it is verified

The camera solve is the standard two vanishing point calibration from Caprile and Torre
(1990), also Hartley and Zisserman chapter 8. For two vanishing points from perpendicular
world directions, square pixels, and the principal point assumed at the image centre:

    (v1 - p) . (v2 - p) + f^2 = 0

The gizmo computes it in an equivalent geometric form: drop a perpendicular from the image
centre O onto the horizon line to get the foot Vi, then

    f = sqrt( ViV1 * ViV2 - OVi^2 )

These are the same equation. Splitting each vector at the foot gives
(v1-O).(v2-O) = (v1-Vi).(v2-Vi) + |OVi|^2, and the two horizon segments point opposite
ways, so the first term is -ViV1*ViV2.

Pitch comes from the height of that foot above the centre, and yaw from the signed offset
of the other vanishing point along the horizon, measured against sqrt(f^2 + OVi^2) rather
than f, because under pitch the relevant distance is to the horizon, not to the centre.

### Test suites

`tests/` holds four suites, run with `nuke -t tests/suite.py` and so on. They cover 73
checks: solve accuracy against ground truth cameras, the published formula reimplemented
independently, degenerate inputs, format fitting, added lines, vanishing point dragging,
linking, export and bake, save and reload, and the drawn output measured by rendering to
disk and counting pixels rather than by reading knobs back.

`tests/make_testplates.py` and `tests/corridor.py` render ground truth plates with known
focal length and orientation, for placing guides on by hand.

### When to enter a known focal length instead of solving one

Accuracy depends entirely on how far off frame the vanishing points sit. Measured cost of
a two pixel slip in guide placement, on a 1920x1080 plate at 35mm:

| camera yaw | vanishing point offset | focal error per 2px slip |
|---|---|---|
| 2 deg | 78,700 px | 68.6% |
| 5 deg | 31,400 px | 13.7% |
| 15 deg | 10,300 px | 1.6% |
| 30 deg | 4,800 px | 0.3% |
| 45 deg | 2,700 px | 0.1% |

A near one point shot, such as looking straight down a corridor or an alley, cannot be
solved reliably from guides alone. Use "I know the focal length" there and let the
vanishing points set orientation only.
