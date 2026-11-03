# 离线行政区资源

| 省份 | 省级编码 | 地级市边界 | 城市名及别名 | 资源清单 |
|---|---|---:|---:|---|
| 广东 | `440000` | 21 | 42 | [广东清单](regions/cn/440000/manifest.json) |
| 浙江 | `330000` | 11 | 22 | [浙江清单](regions/cn/330000/manifest.json) |

## 全国省级底图

全国分省图使用独立的[资源清单](regions/cn/100000/manifest.json)，覆盖 34 个省级行政区。源图由 Maitian MaiLin 于 2024-09-21 发布，采用 CC0 1.0 许可。保留源图的投影、完整幅面、南海岛屿及辅助线形，移除英文地名与驻地标注，通过原图标注位置核对省级几何与六位编码。未单独编码的近海几何作为底图要素显示。该资源用于统计示意，无官方审图号。[原图及作者许可](https://commons.wikimedia.org/wiki/File:China_administrative_offical.svg) · [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)

## 省内地市资源的使用边界

1. 在[省份注册表](regions/registry.json)中查目标省份，打开对应清单。核对 `scope` 中的省级编码和行政层级。未注册的省份缺少可用边界。
2. 按清单里的 `cityCodeMapping` 和 `boundaryResource` 读取城市名称映射、离线 GeoJSON。路径以清单所在目录为起点。
3. 用 `cityNameToCode` 将查询返回的城市名转成六位编码，再匹配边界的 `properties.adcode`。例如“广州”和“广州市”都对应 `440100`。遇到重名、未知城市或缺失边界，图块标“未评估”并写明原因。不要在出图时下载或猜画边界。

## 维护资源

新增省份时，在注册表增加条目并单独建清单。登记编码体系、范围、城市映射、边界文件，以及来源、获取日期、SHA-256 和许可状态。

广东边界取自项目已有的 `reports/guangdong_440000_full.geojson`，历史材料将其归于阿里云 DataV。浙江边界取自 DataV 的浙江地级市接口。两份资源的归属与许可均须在对外发布前复核。来源和校验值见各省清单。

修改资源后，在本技能目录运行：

```sh
node scripts/validate-resources.mjs
```

脚本检查注册信息、资源范围、城市编码与别名、边界数量、父级编码及文件校验值。加 `--province=浙江省` 或 `--province=330000` 可只显示浙江的结果，校验仍遍历全部资源包。
