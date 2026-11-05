"""Stage 4 method from the 11/05 meeting: preference-aware clustering, no training.

- guide (multiple choice, 3안): group_by = folder | content | mixed sets how much the folder tree counts.
- pairs (1-5 relatedness ratings on example pairs): fix the distance of each rated pair (5 -> 0, 1 -> 1).
- anchors (important files, 1안): each anchor seeds a group; other files join their nearest anchor when
  close enough, and the rest are clustered as in the baseline.
"""
from __future__ import annotations

import numpy as np

from ..config import Config
from ..stage3_record import Record
from ..schema import Group, Preferences
from .baseline import agglomerate, mixed_distance, upper

GUIDE_ALPHA = {"folder": 0.2, "content": 0.9}
ANCHOR_PCT = 25.0  # a file joins its nearest anchor if closer than this percentile of distances


class PreferenceClusterer:
    name = "pref"

    def __init__(self, cfg: Config):
        self.alpha, self.pct = cfg.cluster_alpha, cfg.cluster_pct

    def cluster(self, record: Record, prefs: Preferences) -> list[Group]:
        files = record.files
        if len(files) < 3:
            return [Group(id="g1", name="", members=[f.id for f in files])]
        dist = mixed_distance(record, GUIDE_ALPHA.get(prefs.guide.get("group_by", ""), self.alpha))
        for p in prefs.pairs:
            a, b = record.resolve(p.get("a")), record.resolve(p.get("b"))
            if a and b and a != b:
                i, j = record.file_index[a], record.file_index[b]
                dist[i, j] = dist[j, i] = (5.0 - float(np.clip(p.get("score", 3), 1, 5))) / 4.0
        threshold = float(np.percentile(upper(dist), self.pct))

        anchors = list(dict.fromkeys(record.file_index[a] for a in map(record.resolve, prefs.anchors) if a))
        clusters = [[a] for a in anchors]
        rest = []
        if anchors:
            join = float(np.percentile(upper(dist), ANCHOR_PCT))
            for i in range(len(files)):
                if i in anchors:
                    continue
                k = int(np.argmin(dist[i, anchors]))
                if dist[i, anchors[k]] <= join:
                    clusters[k].append(i)
                else:
                    rest.append(i)
        else:
            rest = list(range(len(files)))
        if rest:
            sub = dist[np.ix_(rest, rest)]
            clusters += [[rest[j] for j in c] for c in agglomerate(sub, threshold)]
        return [Group(id=f"g{n + 1}", name="", members=[files[i].id for i in c]) for n, c in enumerate(clusters)]
