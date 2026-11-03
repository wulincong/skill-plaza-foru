# 离线行政区资源

本目录保存城市热点图需要的固定行政区资源。渲染时从仓库读取这些文件；不得在运行时下载远程地图、调用地图瓦片，或让模型按城市名称临时拼接边界。

## 资源注册表

`regions/registry.json` 是省级资源的唯一索引。每个条目的 `provinceCode`、`province` 和 `manifest` 必须一一对应；渲染器先按目标地区标准化省份名称，再读取对应 manifest。没有 registry 条目或 manifest 的省份不能绘制中国城市热点图，应输出未评估原因。

每个 manifest 位于 `regions/cn/<provinceCode>/manifest.json`，固定声明：

- `scope`：国家、省份、省级行政区编码和城市级别；
- `cityCodeMapping`：城市名称到六位 `adcode` 的映射；
- `boundaryResource`：离线 GeoJSON；
- `source.sha256`、来源、获取日期和许可状态。

渲染器只能使用 manifest 指向的文件，不能依据文件名或模型记忆猜地图。

## 当前资源

| 文件 | 用途 | 规模 | 关键字段 |
|---|---|---:|---|
| `administrative-codes/guangdong-city-codes.json` | 广东省地级市编码和名称映射 | 21 个城市、42 个名称（含“市”后缀与查询常见简称） | `cities[].code`、`cities[].name`、`cities[].aliases[]`、`cityNameToCode` |
| `boundaries/guangdong-440000-city.geojson` | 广东省地级市离线边界 | 21 个 `MultiPolygon` feature，约 188 KiB | `properties.adcode`、`properties.name`、`geometry` |
| `administrative-codes/zhejiang-city-codes.json` | 浙江省地级市编码和名称映射 | 11 个城市、22 个名称（含“市”后缀与查询常见简称） | `cities[].code`、`cities[].name`、`cities[].aliases[]`、`cityNameToCode` |
| `boundaries/zhejiang-330000-city.geojson` | 浙江省地级市离线边界 | 11 个 `MultiPolygon` feature，约 118 KiB | `properties.adcode`、`properties.name`、`geometry` |

城市编码使用六位 `adcode` 字符串，例如 `440100`（广州）和 `440300`（深圳）。查询返回的 `city` 必须先通过 `cityNameToCode` 转成编码，再与 GeoJSON 的 `properties.adcode` 连接；名称无法匹配或一个名称对应多个编码时，图表必须标记为未评估，不能猜测。

## 来源和发布限制

边界文件是项目已有 `reports/guangdong_440000_full.geojson` 的离线副本。该文件的 21 个 feature 均为 `level=city`、`parent.adcode=440000`，原文件 SHA-256 为 `209ad617a296b154c4fd0828180b2a9ab2b270044990ab34e72a344ce913c8c7`。历史报告曾将这份边界归因于“阿里云 DataV 行政区 GeoJSON”；当前资源保留该来源线索，但**许可状态仍待核实**，在对外发布共享 Skill 前必须完成归属和许可复核。

浙江边界是阿里云 DataV `https://geo.datav.aliyun.com/areas_v3/bound/330000_full.json` 的离线副本，包含 11 个地级市 feature，SHA-256 为 `f87241d47687264861aa619b8dc37ffeb61a2be5d6018a8c01ec0ce0acb5cb38`。该来源的公开接口归属和许可状态同样**待核实**；在对外发布前必须完成复核。

当前资源只覆盖广东、浙江两省省内城市，不能被当作全国边界。新增省份或全国边界时，应先增加 registry 条目和独立 manifest，为每个资源提供标准编码范围、来源、获取日期、文件校验和及许可状态，并通过同样的资源校验脚本。

## 校验

在本 Skill 目录执行：

```bash
node scripts/validate-resources.mjs
```

脚本会遍历 registry 中的资源包，检查：manifest 与 registry scope 是否一致、编码是否为六位数字、城市名称映射是否无歧义、映射城市与 GeoJSON feature 是否一一对应、边界 feature 的 parent 编码是否匹配、SHA-256 是否一致，以及资源文件是否可被 JSON 解析。可用 `node scripts/validate-resources.mjs --province=浙江省` 只检查一个资源包。
