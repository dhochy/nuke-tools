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

## Real world scale, and getting the camera into Maya or Blender

A photograph carries no scale of its own. Vanishing points fix the camera's
orientation and focal length and nothing else, because a doll's house and a real
house photograph identically. Scale has to come from one measured length, and the
one a compositor actually knows is how high the camera was off the ground.

The Scale tab takes that height. Everything else on the node is then in the same
unit: cell size, grid size, distance and offset.

| knob | meaning |
|---|---|
| working unit | feet, metres or centimetres |
| camera height | height above the ground plane, in that unit |

Feet is the default because US survey and location data is given that way.
Changing the dropdown converts the values you have already set rather than
reinterpreting them, so switching feet to metres leaves the setup physically
where it was. A full round trip returns the original numbers exactly.

Changing the height never disturbs the solved focal length or angles. That is
correct rather than a limitation: scale is unobservable in a single image, so
only the numbers change, not the picture.

`export camera` writes the height into the exported camera's translate, live
linked, and puts a `units` knob on it saying which unit the numbers are in. Set
the same linear unit at the other end before importing:

- Maya: Preferences, Settings, Linear
- Blender: Scene Properties, Units, Length

### The axis choice matters more for export than for the overlay

The two settings of `ground X axis runs toward` give complementary yaws that add
up to ninety degrees. In the viewer they look identical, because a square grid
turned ninety degrees about its own centre is the same square grid. The choice
only becomes visible once the camera leaves Nuke and real geometry arrives on
it, where it decides which world direction is X and which is Z. Check it before
exporting, not after.

### The grid never moves when you scale it

Position and size are independent knobs. `translate` is built from the grid
offset and the distance only, with no size term, and `uniform_scale` is the size,
which a Card applies about its own centre. Cell count tracks size divided by cell
size, so tiles stay the same size on the ground as the plane grows.

Worth knowing if you ever test this yourself: the centre of mass of the drawn
grid pixels is NOT invariant under a pure scale. A larger ground plane reaches
further away, and distance compresses toward the horizon, so the centroid rises
even though nothing moved. The invariants that do hold, and that the suite
checks, are the card centre's projected pixel and containment of the smaller
grid inside the larger one.

## The third guide: solving the lens axis instead of assuming it

Two vanishing points give two equations. That is enough for focal length and
orientation only if you already know where the lens axis sits on the frame, and
the tool assumed the centre. That assumption is written into the expressions as
`width/2, height/2`, and it is false for any cropped, re-framed or shifted plate.
A cropped photograph then solves to the wrong focal length with nothing to
indicate trouble.

Set a third `dhPerspGuide` to **vertical** and place its two lines on upright
building edges. With three mutually perpendicular vanishing points the principal
point is the orthocenter of their triangle, so it is solved rather than assumed
(Caprile and Torre 1990; Hartley and Zisserman ch. 8). The focal length then
follows from the same formula already in use, with the solved point substituted
for the frame centre.

Measured on a 35mm camera with the lens axis deliberately shifted, which is what
a crop is:

| lens axis shift | two guides | three guides | axis found |
|---|---|---|---|
| none | 35.00 mm | 35.00 mm | exactly centre |
| 0.30 right | 34.13 mm | 35.00 mm | 672, 540 |
| 0.25 down | 34.20 mm | 35.00 mm | 960, 780 |
| 0.35, 0.20 | 34.39 mm | 35.00 mm | 624, 348 |
| half frame crop | 32.79 mm | 35.00 mm | 240, 108 |

The axis positions are exact, not approximate.

### It refuses a vertical guide it cannot trust

On a near level camera the verticals are almost parallel, so their vanishing
point runs off toward infinity and the orthocenter becomes noise. Measured at
0.4 degrees of pitch, it sat 391,668 px from the centre of a 1920x1080 frame.
The solve detects that, ignores the vertical guide, falls back to the centred
assumption and says so in the panel rather than reporting a confident wrong
answer. A camera tilted up or down, which is most architectural photography,
gives verticals that genuinely converge and is the case where the third guide
earns its keep.

Two-guide setups behave exactly as before.

## The floor reads as ground, not as a card

A finite card always has four edges. A ground plane has none: it runs past both
sides of frame and meets the horizon at infinity. Two things make the card read
as ground.

**It is fitted from the solve.** The card is centred under the camera rather than
pushed out in front, because it is axis aligned to world X and Z while the camera
can be at any yaw, so pushing it forward leaves its near corner in shot as a
pointed edge. Centred, every direction is covered whatever the yaw. Side coverage
went from 7 and 10 rows touching the frame edges to 152 and 155.

**It fades out approaching the horizon.** This is the part that matters, and it
is not cosmetic. Covering from the bottom of frame to the horizon with evenly
spaced cells needs roughly `3 x (horizon height in px) / gap` cells, about 545 at
a 4 px gap, and Nuke's Card caps at 400 rows. Push for the horizon and the cells
grow larger than the whole near half of frame, so nothing is drawn where you
actually judge alignment. Fading the far edge out removes the need to reach it,
which frees the cell size to serve the near field. Cell size is therefore driven
by `cells across the near edge`, and the plane reaches as far as the row ceiling
then allows.

`floor style` also offers a textured grid, which has no 400 row ceiling but
softens where the near ground magnifies the texture. Wireframe is the default.

## Updating nodes made by an older build

These are Groups so the render farm can run them without the gizmo installed.
The price is that a Group is copied into the script when it is created, so a node
already in a comp keeps the internals it was born with: editing the `.gizmo` on
disk fixes new nodes and does nothing for old ones.

That is not theoretical. The floor card's position used to be tied to its size
(`* parent.gridsize/2`), so growing the grid moved it. The expression was fixed,
and nodes created before the fix carried on moving.

**Tools > Perspective > Update dhPersp nodes in this script** rebuilds every
stale node in place, keeping placed points, knob values and expression links.
Each node carries a hidden build number so it knows whether it is behind.

## An unplaced guide is refused, not solved

A fresh `dhPerspGuide` has its two lines crossing at the exact centre of frame.
That is the principal point, so an untouched guide's vanishing point lands on it
and every term in the focal formula collapses. Feeding one to the solve used to
produce a confident looking small number, measured at 0.000 mm where the real
answer was 28.27 mm.

The panel now names any guide still sitting at its default cross, and the camera
export refuses rather than handing over a meaningless camera. Exporting a solve
outside 4 to 400 mm asks for confirmation first.
