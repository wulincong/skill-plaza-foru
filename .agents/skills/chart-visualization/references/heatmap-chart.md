# City heatmap chart

Use for city or region intensity distributions when standard geographic codes and offline boundary data are available. The color encodes the queried database's job-record distribution; it does not estimate hiring or employment outcomes.

## Required structure

```html
<figure data-chart-skill="heatmap-chart" data-chart-id="CH_CITY">
  <svg viewBox="0 0 960 640" role="img" aria-labelledby="CH_CITY-title CH_CITY-desc">
    <title id="CH_CITY-title">广东省 Java 后端在招岗位城市分布</title>
    <desc id="CH_CITY-desc">按城市展示经过同一岗位筛选口径的岗位记录数量，颜色越深表示记录数越多，未返回数据的城市使用中性色。</desc>
    <!-- one boundary path per standard city code -->
  </svg>
  <figcaption>来源、查询日期、快照日期、城市字段、岗位筛选、分母、单位和“岗位库记录分布”说明。</figcaption>
</figure>
```

## Offline boundary resources

- Resolve the target province in `resources/regions/registry.json`, then load that entry's manifest under `resources/regions/cn/<provinceCode>/`. The manifest is the resource-package contract: it names the city-code mapping, offline boundary file, standard code system, scope, source, SHA-256, and license status. The currently checked-in city-level packages cover Guangdong (`provinceCode=440000`) and Zhejiang (`provinceCode=330000`); an unregistered province has no valid map resource.
- Use only the bundled resources in `resources/administrative-codes/` and `resources/boundaries/`. Never download a boundary at report time or let the model synthesize one. A registry match is necessary but not sufficient: the query scope and the manifest scope must have the same province code.
- The city-code mapping is the join contract: `cityNameToCode[queryRow.city]` produces a six-digit string such as `440100`, then that value must match `feature.properties.adcode` in the offline GeoJSON. Do not join by fuzzy text, coordinates, or model-generated geometry.
- Every colored path must have a matching standard code and boundary feature. If a returned city name is missing or ambiguous in the mapping, the map is unassessed and the report must show the failure reason.
- Run `node scripts/validate-resources.mjs` after changing a mapping, manifest, registry entry, or boundary resource. Use `--province=浙江省` (or a six-digit province code) to validate one package while iterating.

## Data contract

The cross-city query and chart renderer exchange a bounded, code-first payload. Field names below are part of the chart Skill contract:

```json
{
  "queryId": "city-distribution",
  "scope": { "country": "中国", "province": "广东省", "provinceCode": "440000", "level": "city" },
  "queryDate": "2026-09-28",
  "snapshotDate": "2026-09-28",
  "source": "岗位库只读查询",
  "filters": { "keywords": ["Java"], "roleTerms": ["后端", "服务端", "开发"], "internship": true },
  "unit": "job_records",
  "rows": [{ "city": "广州", "code": "440100", "count": 329 }],
  "coveredCodes": ["440100", "440300"],
  "totalCount": 669,
  "otherCount": 11
}
```

Rules for the payload:

- `rows[].code` is required, is a six-digit string, and must equal the code obtained from the bundled name mapping. `rows[].count` is a non-negative integer when the query returned a value.
- `coveredCodes` states the boundary scope that the query actually covered. A boundary in scope with no returned row has a **missing** value and receives the neutral fill. Do not convert that missing value to `0`, and do not add a zero-valued row merely to color the map.
- `totalCount` is the total for the same fixed filters and scope. `otherCount` is the remainder outside the displayed top 20 (`totalCount - sum(rows[].count)` after validating the top 20 rows). If the query only returns top 20 rows and does not provide a same-filter total, do not invent “其他”; mark the chart unassessed or obtain a separately recorded total.
- Keep at most 20 city rows in the report payload, sorted by `count` descending, and add “其他” only when `otherCount` is known. The boundary SVG may still render every `coveredCodes` region in neutral color when its value is missing.
- `queryDate`, `snapshotDate`, `source`, `filters`, `scope`, and `unit` must be visible in the caption or accessible text. State that the measure is a distribution of job-library records, not actual employment headcount.

## Rules

- Use a single continuous color scale for one query scope and unit. Known zero is a real `0` and may use the lowest data color; missing or out-of-coverage is neutral and must be labeled as missing in the accessible title/description or text fallback.
- Do not use bubbles or circle overlays. Use region fill and a legend; label only the most relevant cities to avoid clutter.
- China-only condition: include this section when the user's target location is in China and city-level data is available. Omit it for an overseas target. For an unknown target location, ask or mark it unassessed.
- Use standard Chinese administrative codes and an offline boundary file. State whether the map covers all China, a province, or only cities returned by the query.
- If the report protocol limits data rows, keep the map's metric payload to the top 20 cities plus “其他”; the SVG may still show covered boundary regions in neutral color.
- A map is not evidence of hiring or employment outcomes. Describe it as the distribution of job records in the queried database.

## Query failure behavior

Do not silently omit a failed cross-city query. Render a compact `data-chart-skill="heatmap-chart"` status block such as:

```html
<figure data-chart-skill="heatmap-chart" data-chart-id="CH_CITY" data-chart-status="unassessed">
  <figcaption>热点图未评估：city-distribution 查询失败（说明可重试或待人工处理的原因）。</figcaption>
</figure>
```
