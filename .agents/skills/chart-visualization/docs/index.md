# 绘制可复核的统计图

这项共享技能供制图与报告开发使用。准备一份有出处的数据表，写清每行代表的对象、计量单位和缺失值含义，再根据读者的问题选择图型。

## 从配对观测示例开始

在技能目录执行下面的命令。输出路径指向尚未创建的目录，工具自动创建父目录，无需预建目标目录。修订使用新路径并保留旧图稿。

```sh
python3 scripts/figure.py render examples/paired-recovery.json --out /tmp/recovery-figure
python3 scripts/figure.py verify examples/paired-recovery.json --out /tmp/recovery-figure
```

打开输出中的 `figure.html`，将配对对象的起点和终点与数值表核对，再看 SVG 或 PDF 在实际版面宽度下是否仍易读。复用这个例子时，保留对象 ID，按成对观测替换示例值。

## 按数据关系选图

比较同一对象前后变化时保留配对关系。呈现全国各省指标时使用省级编码或可匹配的省名，并区分缺失和零。时间趋势需要真实时间间隔；只有两批不同时点的独立样本时，应分别描述两批样本。

[规格字段与依赖](../references/figure-spec.md) · [完整图鉴](../examples/chart-gallery.html)

## 图型扩展与报告调用

新增图型在技能入口登记用途、数据前提、规格和示例，并说明绘图实现状态。报告渲染技能在选图时读取最新入口，沿用完整图稿协议的新增类型可通过共享生成与复验流程交给报告。若输出协议或运行依赖发生变化，需要同时说明兼容要求。
