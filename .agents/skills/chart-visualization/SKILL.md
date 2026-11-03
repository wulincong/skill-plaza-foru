---
name: chart-visualization
description: Create accessible, evidence-bound SVG and HTML charts, maps, and city heatmaps for reports when the data source, geographic scope, and measurement unit are known.
---

# Chart Visualization

Use this shared skill for all report charts. Keep chart rules in this repository so report skills only decide which chart is needed and provide verified data.

## Workflow

1. Read [common-rules.md](references/common-rules.md).
2. Choose exactly one focused reference: bar, line, histogram, stacked bar, radar, sankey, map, or heatmap.
3. Preserve the source, query date, snapshot date, denominator, geographic scope, unit, and uncertainty in the figure.
4. For a map or heatmap, resolve the target province through the checked-in region registry, then load its standard-code mapping and offline boundary resource from [resources/](resources/README.md). Run `node scripts/validate-resources.mjs` when a mapping, manifest, registry entry, or boundary resource changes.
5. Generate a self-contained HTML/SVG figure. Do not use remote tiles, external scripts, screenshots, or invented boundaries.
6. Run a structural check for closed HTML/SVG, accessible `title`/`desc`, and the required `data-chart-skill` marker.

## References

- [common-rules.md](references/common-rules.md): shared evidence, accessibility, and data-shape rules.
- [bar-chart.md](references/bar-chart.md)
- [line-chart.md](references/line-chart.md)
- [histogram-chart.md](references/histogram-chart.md)
- [stacked-bar-chart.md](references/stacked-bar-chart.md)
- [radar-chart.md](references/radar-chart.md): multi-dimension score comparison with a shared 1–5 scale.
- [sankey-chart.md](references/sankey-chart.md): two-stage flow such as traditional-to-emerging skill evolution.
- [map-chart.md](references/map-chart.md)
- [heatmap-chart.md](references/heatmap-chart.md): city or region intensity maps without bubbles.
- [resources/README.md](resources/README.md): checked-in region registry, manifests, administrative code mappings, and offline boundary resources.

## Boundaries

A heatmap is valid only when every colored region has a standard geographic code and a matching boundary dataset. A missing query row must stay missing and use a neutral fill; it must not be changed into a zero count. If the user location is outside China, omit the China city-distribution heatmap. If the location is unknown, do not infer it; report the missing scope. A report may use a ranked bar chart when no valid boundary data exists.
