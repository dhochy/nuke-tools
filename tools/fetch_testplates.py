"""Pull real photographs with known focal lengths, to test the solve against.

Everything the test suites measure is synthetic: the plate is a Constant and the
vanishing points are projected through a camera the test chose. That proves the
arithmetic is self consistent. It cannot prove the tool gets 35mm out of a 35mm
photograph, which is the only question that matters.

shutterdial searches Flickr by EXIF focal length, which is the database that can
answer it. Its API is /api/search with tx (subject), fl (focal length), page and
perpage; empty parameters are left out rather than sent as zero, which is what an
earlier attempt at this got wrong and why it returned nothing.

Two things have to come off the photo's own page rather than the search result.

The 35mm equivalent. shutterdial searches on the PHYSICAL focal length, and on a
crop body 35mm physical is not 35mm equivalent. The solve reports against a
chosen film back, so the equivalent is the number to compare with.

And the pixel size, so a crop can be spotted. A cropped upload keeps the camera's
original EXIF, so its stated focal length is right about the lens and wrong about
the picture. There is no way to be certain from outside, but a file whose aspect
ratio matches its camera's native one is far less likely to have been reframed.

    python tools/fetch_testplates.py                     the default subjects
    python tools/fetch_testplates.py "street corner" 35 6

What comes back is candidates, not results. The lines still have to be traced by
a person, so this writes the plates and a manifest of what each one claims to be,
and the comparing is done by hand afterwards.
"""
import io
import json
import os
import re
import struct
import subprocess
import sys

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
API = "https://www.shutterdial.com/api/search"
OUT = os.environ.get("PLATE_DIR", r"C:\temp\perspective_tests\plates")

# Biggest first. Flickr serves whichever of these the upload was large enough for.
SIZES = ("k", "h", "b", "c", "z")

# Subjects that tend to be two point: a corner presents two wall directions at an
# angle. A facade square to the camera is the case the solve cannot do from two
# guides, so it is no use as a test of accuracy.
SUBJECTS = ("building corner", "street corner", "warehouse", "brick building",
            "office building")


def get(url, binary=None, referer="https://www.shutterdial.com/search"):
    cmd = ["curl", "-s", "-m", "40", "-A", UA, "-H", "Referer: " + referer]
    if binary:
        cmd += ["-o", binary]
    cmd.append(url)
    try:
        return subprocess.run(cmd, capture_output=True).stdout
    except Exception:
        return b""


def search(subject, focal, page=1, perpage=24):
    url = "%s?tx=%s&fl=%d&page=%d&perpage=%d" % (
        API, subject.replace(" ", "%20"), focal, page, perpage)
    try:
        d = json.loads(get(url).decode("utf-8", "replace"))
    except Exception as e:
        print("  search failed (%s)" % e)
        return []
    return ((d.get("photos") or {}).get("photo") or [])


FIELD = re.compile(r"<th>\s*%s\s*</th>\s*<td>(?:<[^>]+>)?\s*([^<]+)")


def meta(photo):
    """Focal length, 35mm equivalent, camera and pixel size, from the photo page.

    The page is server rendered as a table of <th>label</th><td>value</td>, not
    the heading-and-paragraph markup an earlier attempt assumed.
    """
    base = "https://www.flickr.com/photos/%s/%s/" % (photo["owner"], photo["id"])
    html = get(base + "meta/", referer=base).decode("utf-8", "replace")

    def field(label):
        m = FIELD.search(html.replace(label, label))
        m = re.search(r"<th>\s*" + re.escape(label) + r"\s*</th>\s*<td>"
                      r"(?:<[^>]*>)?\s*([^<]+)", html)
        return m.group(1).strip() if m else None

    def num(v):
        if not v:
            return None
        m = re.search(r"([\d.]+)", v)
        return float(m.group(1)) if m else None

    return {"focal": num(field("Focal Length")),
            "f35": num(field("Focal Length (35mm format)")),
            "model": field("Model") or field("Camera"),
            "make": field("Make")}


def jpeg_size(path):
    """Pixel size straight out of the file, not out of anyone's metadata."""
    try:
        d = io.open(path, "rb").read()
    except Exception:
        return None
    i = 2
    while i < len(d) - 9:
        if d[i] != 0xFF:
            i += 1
            continue
        m = d[i + 1]
        if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB):
            h, w = struct.unpack(">HH", d[i + 5:i + 9])
            return int(w), int(h)
        if m in (0xD8, 0xD9) or 0xD0 <= m <= 0xD7:
            i += 2
            continue
        try:
            i += 2 + struct.unpack(">H", d[i + 2:i + 4])[0]
        except Exception:
            return None
    return None


def download(photo, dest):
    """The largest size Flickr will serve for this upload."""
    for sz in SIZES:
        url = "https://live.staticflickr.com/%s/%s_%s_%s.jpg" % (
            photo["server"], photo["id"], photo["secret"], sz)
        get(url, binary=dest, referer="https://www.flickr.com/")
        if os.path.isfile(dest) and os.path.getsize(dest) > 60000:
            wh = jpeg_size(dest)
            if wh and min(wh) >= 600:
                return sz, wh
    return None, None


def main():
    subjects = sys.argv[1].split(",") if len(sys.argv) > 1 else list(SUBJECTS)
    focals = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 \
        else [24, 35, 50, 85]
    want = int(sys.argv[3]) if len(sys.argv) > 3 else 3

    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    kept, seen = [], set()
    for focal in focals:
        got = 0
        for subject in subjects:
            if got >= want:
                break
            print("\n%d mm, %s" % (focal, subject))
            for photo in search(subject, focal):
                if got >= want or photo["id"] in seen:
                    continue
                seen.add(photo["id"])
                info = meta(photo)
                if info["f35"] is None:
                    continue
                dest = os.path.join(
                    OUT, "f%03d_%s.jpg" % (int(round(info["f35"])), photo["id"]))
                sz, wh = download(photo, dest)
                if not wh:
                    if os.path.isfile(dest):
                        os.remove(dest)
                    continue
                kept.append({
                    "file": dest, "id": photo["id"],
                    "title": (photo.get("title") or "")[:70],
                    "owner": photo.get("ownername", ""),
                    "page": "https://www.flickr.com/photos/%s/%s"
                            % (photo["owner"], photo["id"]),
                    "width": wh[0], "height": wh[1], "size_served": sz,
                    "make": info["make"], "model": info["model"],
                    "focal_mm": info["focal"], "focal_35mm_equiv": info["f35"],
                    "searched_at": focal})
                got += 1
                print("  %-44s %4dx%-4d  %-22s %smm -> %smm eq"
                      % ((photo.get("title") or "")[:42], wh[0], wh[1],
                         (info["model"] or "?")[:22], info["focal"], info["f35"]))

    man = os.path.join(OUT, "plates.json")
    io.open(man, "w", encoding="utf-8").write(
        json.dumps(kept, indent=1, ensure_ascii=False))
    print("\n%d plate(s) in %s" % (len(kept), OUT))
    print("manifest: %s" % man)
    if kept:
        print("\nEach one claims a 35mm equivalent focal length. Trace two guides")
        print("on it, one along each of the two wall directions, and compare.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
