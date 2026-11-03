# Shared chart rules

- Every figure uses a meaningful `data-chart-skill` value, a `<title>`, a `<desc>`, and a visible caption.
- State the source, query date, snapshot date, filter scope, denominator, unit, and whether the values are counts or percentages.
- Keep one chart to one scope and unit. Do not mix national, provincial, and city data in one denominator.
- Report proportions for decision making; retain counts in the development-side evidence when useful. Small samples need a visible representativeness note.
- Do not make a chart from missing or failed query data. Mark the section “未评估” and include the failure reason in developer-side evidence.
- Use inline SVG for static report output. Do not load remote maps, map tiles, chart libraries, or JavaScript.
- Use standard geographic codes and a local boundary dataset for maps. Do not draw approximate geography from memory.
- For maps and heatmaps, missing or out-of-coverage regions use a neutral fill; a real zero may use the lowest data color only when the legend labels it as zero. Never imply zero when the region was not covered.
- Keep labels readable, use color with sufficient contrast, and provide a text fallback or ranked list for the same key findings.
- If a chart protocol limits data points, show the top-ranked points and aggregate the remainder as “其他”; state that choice in the caption.
