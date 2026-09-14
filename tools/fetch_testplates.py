"""Pull ground truth test frames via shutterdial, which searches Flickr by focal length.

The hard part is not finding photos, it is finding photos whose stated focal
length still describes the framing. A cropped upload keeps the camera's original
EXIF, so the number is right about the lens and wrong about the picture: that is
what made a Wikimedia frame labeled 24mm actually measure 37mm.

Two filters deal with it.

Native sensor size. A file whose pixel dimensions match a camera's full readout
cannot have been cropped. Anything else is rejected, however good it looks.

35mm equivalent. shutterdial searches on the EXIF focal length, which is the
physical one. On a crop body 35mm physical is not 35mm equivalent, and the solve
reports against a chosen film back, so the equivalent is the number to compare
with. It comes from the photo's own meta page.
"""
import io
import json
import os
import re
import subprocess
import sys

UA = "dhPerspTest/1.0 (dhochy@gmail.com)"
API = "https://www.shutterdial.com/api/search"
OUT = os.environ.get("PLATE_DIR", r"C:\temp\perspective_tests\flickr")

# Full sensor readouts. A file at one of these cannot be a crop.
NATIVE = set([
    (6000, 4000), (6016, 4016), (6048, 4024), (8256, 5504), (5568, 3712),
    (4928, 3264), (4288, 2848), (3872, 2592), (3008, 2000), (4272, 2848),
    (5472, 3648), (5184, 3456), (4752, 3168), (3888, 2592), (5616, 3744),
    (5760, 3840), (6720, 4480), (7360, 4912), (6240, 4160), (6480, 4320),
    (4608, 3456), (4000, 3000), (4032, 3024), (8064, 6048), (5496, 3670),
    (2848, 4288), (4000, 6000), (3456, 5184), (3648, 5472), (4912, 7360),
])


def curl(url, binary=None):
    cmd = ["curl", "-s", "-L", "-A", UA, "-H", "Referer: https://www.shutterdial.com/"]
    if binary:
        cmd += ["-o", binary]
    cmd.append(url)
    out = subprocess.run(cmd, capture_output=True)
    return out.stdout


def search(subject, focal, perpage=40):
    url = "%s?tx=%s&fl=%d&av=0&tv=0&perpage=%d" % (
        API, subject.replace(" ", "%20"), focal, perpage)
    try:
        d = json.loads(curl(url).decode("utf-8", "replace"))
    except Exception as e:
        print("  search failed (%s)" % e)
        return []
    return (d.get("photos", {}) or {}).get("photo", []) or []


NUMS = re.compile(r"([\d.]+)")


def meta(photo):
    """Focal length, 35mm equivalent, model and original size, from the photo page."""
    url = "https://www.flickr.com/photos/%s/%s/sizes/o/" % (photo["owner"], photo["id"])
    html = curl(url).decode("utf-8", "replace")
    m = re.search(r'(\d{3,5})\s*x\s*(\d{3,5})', html)
    size = (int(m.group(1)), int(m.group(2))) if m else None
    src = None
    m = re.search(r'(https://live\.staticflickr\.com/[^"\']+_o\.(?:jpg|png))', html)
    if m:
        src = m.group(1)

    exif = curl("https://www.flickr.com/photos/%s/%s/meta/"
                % (photo["owner"], photo["id"])).decode("utf-8", "replace")

    def field(label):
        m = re.search(re.escape(label) + r"</h4>\s*<p[^>]*>([^<]+)", exif)
        return m.group(1).strip() if m else None

    f35 = field("Focal Length (35mm format)") or field("Focal length in 35mm format")
    focal = field("Focal Length")
    model = field("Model")
    def num(v):
        if not v:
            return None
        m = NUMS.search(v)
        return float(m.group(1)) if m else None
    return {"size": size, "src": src, "f35": num(f35), "focal": num(focal),
            "model": model}


def main():
    subjects = sys.argv[1].split(",") if len(sys.argv) > 1 else [
        "architecture", "building corner", "street corner", "plaza", "warehouse"]
    focals = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [
        24, 35, 50, 85]
    want = int(sys.argv[3]) if len(sys.argv) > 3 else 2

    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    kept = []
    for focal in focals:
        got = 0
        for subject in subjects:
            if got >= want:
                break
            print("\nsearching %-18s at %d mm" % (subject, focal))
            for photo in search(subject, focal):
                if got >= want:
                    break
                info = meta(photo)
                if not info["size"] or not info["src"]:
                    continue
                if info["size"] not in NATIVE:
                    continue
                if info["f35"] is None:
                    continue
                tag = "fl%03d_%s" % (int(round(info["f35"])), photo["id"])
                dest = os.path.join(OUT, tag + ".jpg")
                curl(info["src"], binary=dest)
                if not os.path.isfile(dest) or os.path.getsize(dest) < 40000:
                    continue
                kept.append({"file": dest, "id": photo["id"],
                             "title": photo.get("title", ""),
                             "owner": photo.get("ownername", ""),
                             "size": list(info["size"]), "model": info["model"],
                             "focal": info["focal"], "f35": info["f35"],
                             "searched_fl": focal})
                got += 1
                print("  kept %-26s %4dx%-4d  %s  %smm actual, %smm eq"
                      % (photo.get("title", "")[:24], info["size"][0],
                         info["size"][1], info["model"], info["focal"], info["f35"]))

    io.open(os.path.join(OUT, "plates.json"), "w", encoding="utf-8").write(
        json.dumps(kept, indent=1))
    print("\n%d uncropped plate(s) with a known 35mm equivalent, in %s"
          % (len(kept), OUT))


if __name__ == "__main__":
    main()
