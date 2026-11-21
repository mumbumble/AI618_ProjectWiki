# Coral Reef Monitoring Reading List

Reading group, autumn term. Each session covers one or two papers and ends with a short discussion. Please bring one question per paper.

## Goals

- Understand how coral reef health is measured from images, sonar, and satellite data.
- Compare classical image processing with learned segmentation for underwater scenes.
- Learn the common indices used to flag bleaching and stress events.

## Session schedule

| Week | Theme | Focus |
|------|-------|-------|
| 1 | Why monitor reefs | Ecological background, bleaching causes, survey design |
| 2 | Bleaching indices | Degree heating weeks, sea surface temperature anomalies, alert levels |
| 3 | Underwater imaging | Color correction, light attenuation, turbidity |
| 4 | Benthic segmentation | Classifying coral, algae, sand, and rubble in quadrat photos |
| 5 | Sonar and acoustic mapping | Multibeam bathymetry, side-scan imagery, habitat maps |
| 6 | Field validation | Ground truth, annotation agreement, sampling bias |
| 7 | Open discussion | Choosing a monitoring setup for a small reef site |

## Reading themes

### Week 1: Why monitor reefs
- Background on how thermal stress leads to symbiont loss and bleaching.
- Survey designs: transects, quadrats, and photo-quadrat sampling.
- Discussion: what changes in cover are large enough to matter over a single season?

### Week 2: Bleaching indices
- Degree heating weeks accumulate sea surface temperature above a climatological threshold.
- Read how alert thresholds were chosen and where they fail, especially in shallow lagoons.
- Discussion: which index would you trust for a site with strong tidal heating?

### Week 3: Underwater imaging
- Water absorbs red light first, so raw photos look blue-green at depth.
- Compare colour-card calibration with physics-based correction models.
- Note how turbidity and backscatter change the apparent texture of the seabed.

### Week 4: Benthic segmentation
- Pixel-level labels for coral, macroalgae, sand, and dead substrate.
- Compare hand-tuned colour and texture features with convolutional segmentation networks.
- Check how each paper reports class imbalance and per-class scores.

### Week 5: Sonar and acoustic mapping
- Multibeam sonar gives depth; side-scan gives backscatter texture.
- Read how habitat maps are built by fusing acoustic and optical data.
- Discussion: how far can acoustic classes be trusted without diver checks?

### Week 6: Field validation
- Ground-truth labels are often produced by a single annotator.
- Look for inter-annotator agreement numbers and how disagreements were resolved.
- Discussion: how should sampling bias toward accessible sites be reported?

## Suggested reading list

1. A review of coral bleaching drivers and their ecological effects (Week 1).
2. Documentation of satellite-based bleaching alert products and their thresholds (Week 2).
3. A survey of underwater image enhancement and colour restoration methods (Week 3).
4. A benchmark paper on benthic cover classification from photo-quadrats (Week 4).
5. A study combining multibeam bathymetry with side-scan backscatter for habitat mapping (Week 5).
6. A field paper on annotator agreement for reef imagery (Week 6).

Organisers will circulate PDFs one week ahead. If a paper is behind a paywall, please tell the organiser and we will find an open copy.

## Discussion prompts

- Which measurement is easiest to automate, and which still needs divers?
- When two indices disagree about a bleaching event, which one should a manager act on?
- How would you test a segmentation model on a reef it has never seen?
- What is the smallest field budget that still produces a useful time series?

## Logistics

- Meeting room: seminar room 2, Thursdays at 16:00.
- Each member presents one paper during the term; sign up in the first session.
- Short summaries (half a page) are due the day before each session.
