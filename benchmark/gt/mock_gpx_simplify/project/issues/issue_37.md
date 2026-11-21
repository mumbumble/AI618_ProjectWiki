# Issue #37: read_gpx drops the last trackpoint when the file has more than one `<trkseg>`

**Status:** Closed (fixed in 0.3.1)
**Type:** Bug
**Reported by:** 이서연 (2026-09-02)
**Affected versions:** 0.3.0 (multi-segment files only)
**Fixed in:** 0.3.1 (2026-09-14), fix by 박민준

## Summary

When a GPX track contains more than one `<trkseg>` element, `read_gpx` returns one point fewer than the file contains for every segment after the first. The final point of each later segment is silently lost. Single-segment files are not affected.

## Environment

- trackslim 0.3.0
- Input: GPX 1.1 file with two `<trkseg>` elements, three `<trkpt>` elements each

## Steps to reproduce

1. Create a GPX 1.1 file with one `<trk>` containing two `<trkseg>` elements.
2. Segment A contains these points:
   - `lat=37.5000 lon=127.0000 ele=50`
   - `lat=37.5010 lon=127.0010 ele=55`
   - `lat=37.5020 lon=127.0020 ele=60`
3. Segment B contains these points:
   - `lat=37.5030 lon=127.0030 ele=62`
   - `lat=37.5040 lon=127.0040 ele=65`
   - `lat=37.5050 lon=127.0050 ele=70`
4. Call `read_gpx(path)` on the file.
5. Check `len(track.points)`.

## Expected result

The returned track has 6 points, in file order, with the last point of segment B (`37.5050, 127.0050, 70`) included.

## Actual result

The returned track has 5 points. The point `37.5050, 127.0050, 70` is missing. The other five points are present.

## Cause

In `_read_trkpts`, the loop over `<trkseg>` elements takes all points of the first segment, but for every later segment it slices the list with `points[:-1]`. That slice drops the last point of each segment after the first. With two segments of three points each, the result is 3 + 2 = 5 points.

The bug only appears when there is more than one segment, which is why single-segment files and round-trips written by `write_gpx` (which emits one segment) went unnoticed.

## Impact

- Any multi-segment track lost one point per extra segment.
- Simplification and statistics run on the truncated track, so the last point of each later segment could also be missing from the output of `simplify_track`.
- For tracks with paused recording, the lost points were usually the ends of each recorded stretch, which affects distance and ascent totals slightly.

## Fix

Removed the slice. `_read_trkpts` now appends every point from every `<trkseg>`, and segments are merged into a single `Track` in file order. The fix was agreed at the dev meeting on 2026-09-05, with a target of 2026-09-14.

## Regression test

`test_multi_segment_keeps_last_point` in the reader/writer unit tests builds a two-segment file with three points per segment and asserts that `read_gpx` returns 6 points. The test fails on 0.3.0 with 5 points and passes on 0.3.1.

## Notes

- Changelog entry for 0.3.1: "fix #37: keep last point of multi-segment files."
- If you see fewer points than expected after reading a multi-segment file, check the version first. Upgrading to 0.3.1 or later resolves it.
