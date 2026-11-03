# 离线行政区资源

## 省内行政单元

34 个省级行政区都有独立的离线 GeoJSON、名称映射和资源清单。共 498 个可按编码连接的单元。内地按 2025 年末区划，香港、澳门、台湾地区的来源版本见下表。

| 覆盖范围 | 单元数 | 绘图层级及编码 |
|---|---:|---|
| 内地 22 省、5 自治区 | 333 + 32 | 293 个地级市、30 个自治州、7 个地区、3 个盟。另保留河南、湖北、海南、新疆的 32 个省直管县级单位，单独标为 `direct-county` |
| 北京、天津、上海、重庆 | 16 + 16 + 16 + 37 | 按区县连接。重庆含两江新区。内地各包使用六位行政区划码 |
| 香港 | 18 | 地方行政区，使用民政事务总署的地区字母标识，如沙田区 `R` |
| 澳门 | 8 | 7 个堂区与路氹填海区，使用 OSM relation ID 字符串。堂区与填海区分别标为 `parish`、`area` |
| 台湾地区 | 22 | 数据源的县、市统计单元，保留五位 `COUNTYCODE`，例如连江县 `09007`。新竹县与新竹市分别匹配 |

在[注册表](regions/registry.json)的 `provinceNameToCode` 查省名，按 `regions[].manifest` 打开该省包。[四川](regions/cn/510000/manifest.json)含地级市和自治州，[湖北](regions/cn/420000/manifest.json)还含省直管县级单位，[重庆](regions/cn/500000/manifest.json)按区县。输入须与所选图的实际层级相符。

## 全国省级底图

全国分省图使用独立的[资源清单](regions/cn/100000/manifest.json)，覆盖 34 个省级行政区。源图由 Maitian MaiLin 于 2024-09-21 发布，采用 CC0 1.0 许可。保留源图的投影、完整幅面、南海岛屿及辅助线形，移除英文地名与驻地标注，通过原图标注位置核对省级几何与六位编码。未单独编码的近海几何作为底图要素显示。该资源用于统计示意，无官方审图号。[原图及作者许可](https://commons.wikimedia.org/wiki/File:China_administrative_offical.svg) · [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)

## 数据连接与署名

- manifest 中的 `cityCodeMapping`、`boundaryResource` 均相对该 manifest。用映射的 `cityNameToCode` 把名称解析为字符串编码，再与 `String(feature.properties.adcode)` 相连。这些兼容字段同样适用于区县等层级。行政单元类型读 `properties.level`、`unitType`，省级归属读 `parent.adcode`。优先使用全名，不猜测缺失或有歧义的短名。
- 单独分发或生成地图时要随图标明 manifest 的 `source.attribution`、`snapshot` 和 `license`，保留来源与许可链接。每份 GeoJSON 也携带原始署名。边界经过制图简化，适用于统计展示。
- 内地 31 包来自 Cheng Rui、Hu Yunfeng、Xiao Chiwei、Wang Yanjun 的 CTAmap v2.0。2026 层代表 2025-12-31 状态，采用 CC BY 4.0。省、自治区读取地级层，直辖市读取县级层。广东、浙江沿用原文件入口与编码，早期静态图上注明的历史底图仍以当时的图注为准。[数据及引用](https://doi.org/10.5281/zenodo.22179207) · [许可](https://creativecommons.org/licenses/by/4.0/)
- 香港底图 © 香港特别行政区政府民政事务总署，来源为 DATA.GOV.HK，于 2026-11-03 取得。[数据](https://data.gov.hk/tc-data/dataset/hk-had-json1-hong-kong-administrative-boundaries) · [使用条款](https://data.gov.hk/en/terms-and-conditions)
- 台湾地区来自内政部国土测绘中心 2025-03-18 县市界，使用 plotdb/pdmaptw 的格式转换成果，适用政府资料开放授权条款第 1 版。[源数据](https://data.gov.tw/dataset/7442) · [转换版本](https://github.com/plotdb/pdmaptw/releases/tag/v2.4.0) · [许可](https://data.gov.tw/license)
- 澳门底图 © OpenStreetMap contributors，按 ODbL 1.0 提供澳门派生数据库。使用 Geofabrik 2026-11-02 提取包，并从同一版嘉模堂区 relation 5758865（v15） 补全裁剪线段。[数据](https://download.geofabrik.de/asia/china/macau.html) · [来源与许可](https://www.openstreetmap.org/copyright)

## 维护与验证

`node scripts/validate-resources.mjs` 核对 34 个省级编码、每个单元的几何环与名称、别名唯一性、行政层级、父级与 SHA-256。`--province=四川` 只筛选输出，仍验证全库。

重建时使用 `python3 scripts/import-regional-boundaries.py <原始文件目录> --out <新资源目录>`。仅维护时需要 Shapely 2.1 以上、pyosmium 和 ICU 的 uconv。输入文件名和校验值在脚本 PINNED 中，内地两份 GeoPackage 使用 Zenodo 公布的 MD5，其他输入使用 SHA-256。香港 JSON、台湾转换版 GeoJSON、澳门 PBF 与完整嘉模堂区 OSM XML 的取得方式均登记在对应 manifest。脚本按共同边界做拓扑简化，修复源数据的微小自交，逐单元核对几何非空、有效与面积偏差。运行与浏览图鉴均可离线。

资源变更后，用 `python3 scripts/update-region-gallery.py <图鉴HTML路径>` 在替换并校验资源后刷新图鉴已嵌入的 34 组图形和署名，可在断网状态按省、按单元检查。
