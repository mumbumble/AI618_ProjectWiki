"""Read and write GPX 1.1 track files.

Reading parses the XML with the standard library, merges every
<trkseg> into a single Track and turns timestamps into datetime
objects. Writing emits one <trk> with one <trkseg>.
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime

GPX_NS = "http://www.topografix.com/GPX/1/1"
_NS = {"gpx": GPX_NS}

ET.register_namespace("", GPX_NS)
logger = logging.getLogger(__name__)


def _q(tag):
    """Qualify a tag name with the GPX 1.1 namespace."""
    return "{%s}%s" % (GPX_NS, tag)


def parse_time(text):
    """Parse an ISO-8601 timestamp; a trailing 'Z' means UTC."""
    if text is None or not text.strip():
        return None
    text = text.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def _format_time(dt):
    """Format a datetime the way GPX files usually store it."""
    iso = dt.isoformat()
    if iso.endswith("+00:00"):
        iso = iso[:-6] + "Z"
    return iso


def _read_trkpts(root):
    """Return the <trkpt> elements of all <trkseg> blocks, in file order.

    Every segment is read in full. Version 0.3.0 sliced off the last
    point of each segment after the first, which lost data (issue #37).
    """
    points = []
    for trk in root.findall("gpx:trk", _NS):
        for seg in trk.findall("gpx:trkseg", _NS):
            points.extend(seg.findall("gpx:trkpt", _NS))
    return points


def _point_from_element(el, index):
    from trackslim import TrackPoint  # local import avoids a circular import

    ele_el = el.find("gpx:ele", _NS)
    if ele_el is not None and ele_el.text:
        ele = float(ele_el.text)
    else:
        logger.warning("trkpt #%d has no <ele>, using 0.0", index)
        ele = 0.0
    time_el = el.find("gpx:time", _NS)
    time = parse_time(time_el.text) if time_el is not None else None
    return TrackPoint(
        lat=float(el.get("lat")),
        lon=float(el.get("lon")),
        ele=ele,
        time=time,
    )


def read_gpx(path):
    """Read a GPX file and return a Track holding all segment points."""
    from trackslim import Track

    root = ET.parse(path).getroot()
    name_el = root.find("gpx:trk/gpx:name", _NS)
    name = name_el.text if name_el is not None else None
    points = [_point_from_element(el, i)
              for i, el in enumerate(_read_trkpts(root))]
    return Track(points=tuple(points), name=name)


def write_gpx(track, path, precision=6, keep_time=True):
    """Write a Track as a single-segment GPX 1.1 file."""
    root = ET.Element(_q("gpx"), {"version": "1.1", "creator": "trackslim"})
    trk = ET.SubElement(root, _q("trk"))
    if track.name:
        ET.SubElement(trk, _q("name")).text = track.name
    seg = ET.SubElement(trk, _q("trkseg"))
    fmt = "{:.%df}" % precision
    for p in track.points:
        el = ET.SubElement(seg, _q("trkpt"),
                           {"lat": fmt.format(p.lat), "lon": fmt.format(p.lon)})
        ET.SubElement(el, _q("ele")).text = fmt.format(p.ele)
        if keep_time and p.time is not None:
            ET.SubElement(el, _q("time")).text = _format_time(p.time)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
