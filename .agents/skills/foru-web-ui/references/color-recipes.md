# FORU 配色配方与材质分工

用于细化颜色、交互状态和局部材质。值来自 [source-css.txt](source-css.txt) 与 [source-observations.md](source-observations.md)；Hero、图标近似项另行标注。选择器名是重建示例，尺寸沿用设计参考或目标项目。

## 源样式配方

共享变量按角色命名，防止将正文、弱信息、背景和描边混用。品牌蓝保持同一值；企业头部、入口 hover 各有自己的渐变。

```css
:root {
  --foru-blue: #165dff;
  --foru-ink: #1d2129;
  --foru-title: #1f2329;
  --foru-hero-ink: #061840;
  --foru-body: #4e5969;
  --foru-meta: #86909c;
  --foru-white: #fff;
  --foru-soft: #f9fbff;
  --foru-entry: #f2f8ff;
  --foru-entry-hover: #e3f0ff;
  --foru-tag: #ecf6ff;
  --foru-line: #daeaff;
  --foru-divider: #f2f3f5;
  --foru-card-shadow: 0 6px 10px rgba(119, 167, 255, .18);
  --foru-panel-shadow: 0 4px 20px rgba(119, 167, 255, .12);
  --foru-feature-shadow: 0 10px 40px rgba(119, 167, 255, .22);
}

.hero-action {
  color: var(--foru-ink);
  border: 1px solid #94bfff;
  background: linear-gradient(225.3deg, #f0f5ff, #e9f7ff);
}
.hero-action-icon { color: var(--foru-blue); }
.role-tab { color: var(--foru-ink); background: var(--foru-entry); }
.role-tab:hover { background: var(--foru-entry-hover); }
.role-tab[aria-selected="true"] {
  color: var(--foru-white);
  background: var(--foru-blue);
}
.product-panel { background: var(--foru-white); box-shadow: var(--foru-panel-shadow); }
.product-entry {
  color: var(--foru-ink);
  border: 1px solid var(--foru-line);
  background: linear-gradient(rgba(242, 248, 255, 0), #f2f8ff 100%);
}
.product-entry:hover {
  color: var(--foru-white);
  background: linear-gradient(155.11deg, #9ac2fd 14.264%, #165dff 93.013%);
}
.product-entry:hover .product-icon {
  background: var(--foru-white);
  border-radius: 22px;
}
```

原站入口默认的图标底是透明，hover才出现白色圆角底、图形由56px缩为36px。不要在默认状态提前给所有图标加白色徽章，或把hover渐变长期显示。将相同视觉用于 `:focus-visible` 是键盘操作改造。

```css
.solution-section {
  background: linear-gradient(#fafeff, rgba(245, 251, 253, 0) 100%);
}
.feature-line { border-left: 1px solid var(--foru-line); }
.feature-title { color: var(--foru-body); }
.feature-desc { color: var(--foru-meta); }
.feature[aria-selected="true"] {
  background: var(--foru-white);
  border: 1px solid rgba(194, 220, 255, .6);
  box-shadow: var(--foru-feature-shadow);
}
.feature[aria-selected="true"] .feature-title { color: var(--foru-blue); }
.feature-progress { background: var(--foru-blue); }
.tag-blue { color: var(--foru-blue); background: var(--foru-tag); }
.company-head {
  background: linear-gradient(270deg, #2c68ff, #2f91fa 100%);
  color: var(--foru-white);
}
.company-head-meta { color: #ebf4ff; }
.company-logo { background: var(--foru-white); border: .6px solid #e2ecff; }
.resource-card { background: var(--foru-white); box-shadow: var(--foru-card-shadow); }
.job-company-strip,
.reason-head {
  background: linear-gradient(90deg, #f8ffff 6.812%, #f9fdff 93.188%);
}
.news-card,
.reason-card { box-shadow: 0 4px 12px rgba(119, 167, 255, .18); }
.news-date { color: #c9cdd4; }
```

企业渐变的可见方向为左侧偏青蓝 `#2F91FA`、右侧偏纯蓝 `#2C68FF`。它承担实体身份头部；岗位主体保持白底，薪资用品牌蓝，公司条只染极浅青白。产业图片的文字遮罩另用 `linear-gradient(rgba(10,14,28,0) 25%, rgba(10,14,28,.6))`，这是图片可读性遮罩，不是蓝色UI表面。

伙伴玻璃是局部例外：源规则底部alpha `.79`，常规卡片 `.18` 阴影也不能替代伙伴 `.4` 阴影。其最终蓝色还受后方图片影响；在纯白祖先上复制CSS不会自动得到相同整体效果。

对照 [完整伙伴区](screenshots/desktop-partners.jpg)：标题位于玻璃板外的白色上半部，饱和蓝只从后方波形向下铺开。无原背景图时，另画背景层来保持这一范围；starter 使用 `#2457F9 → #178CF1` 与白色曲线近似它，两个色值不是源 CSS token。

```css
.partner-glass {
  border: 1px solid rgba(255, 255, 255, .6);
  background: linear-gradient(rgba(255, 255, 255, .79), rgba(141, 208, 255, .79) 100%);
  backdrop-filter: blur(60px);
  box-shadow: 0 12px 22px rgba(47, 111, 229, .4);
}
.partner-logo-tile {
  background: var(--foru-white);
  box-shadow: 0 8px 12px rgba(119, 167, 255, .32);
}
.site-footer { background: #141933; }
.site-footer-title { color: #fbfcfd; }
.site-footer-link { color: #c9cdd4; }

/* 导航下拉菜单的独立材质与密度；不用于普通业务卡片。 */
.product-menu { background: #fff; box-shadow: 0 12px 32px rgba(0, 0, 0, .12); }
.menu-group-label { position: relative; isolation: isolate; }
.menu-group-label::before {
  content: "";
  position: absolute;
  inset: auto 0 2px;
  height: 6px;
  border-radius: 2px;
  background: #d3edff;
  z-index: -1;
}
.menu-product:hover { background: #f7f9fc; }
.menu-product:hover .menu-product-name { color: var(--foru-blue); }
```

人才技能标签是四组固定文字/底色组合，不是全页第二套品牌色：

| 分类顺序 | 字色 | 底色 | 源选择器 |
| --- | --- | --- | --- |
| 1 | `#165DFF` | `#ECF6FF` | `.column9 .tag-item.index1` |
| 2 | `#1CAB84` | `#E8FFF5` | `.column9 .tag-item.index2` |
| 3 | `#FF991C` | `#FFF8E8` | `.column9 .tag-item.index3` |
| 4 | `#FF4B5D` | `#FFEAE8` | `.column9 .tag-item.index4` |

源样式中 `.html-wrap p` 还存在 `linear-gradient(-74.05deg,#94BFFF,#165DFF)` 的文字裁剪规则；它只作用于匹配的p。已存首屏截图的主标题为深色，不据此将整段H1改成渐变字。

## Hero 与图标重建近似

Hero是位图照明，已知源CSS不足以还原它的每个色值。保留可见关系：左上极浅青蓝、文字附近近白；向下淡出为白；右侧饱和蓝紫AI、半透明蓝青结构、白色平台与柔和蓝色投影。以下是无原图时的建议近似，不是源站token：

```css
.hero-rebuilt {
  background:
    radial-gradient(ellipse at 78% 38%, rgba(176, 220, 255, .34), transparent 56%),
    linear-gradient(180deg, #eafaff 0%, #f7fdff 46%, #fff 100%);
}
.hero-rebuilt-art {
  /* 将紫色限制在立体标识/侧面；高亮面用白与浅青。 */
  --art-violet: #6535da;
  --art-blue: #4689f5;
  --art-cyan: #95ecf4;
  --art-glint: #efffff;
}
```

这些色可随自有插画微调；更接近原图依赖形状、透视、透光层、高光和背景淡出，而不只是四个hex。全首屏铺均匀青色、只放一张平面紫色AI，会削弱原图的白色留白和立体感。入口小图标应以蓝青层叠为主、嫩绿或紫色为点缀；目标项目已有图标体系时优先用它的图标并添加适度材质，不引入不一致的混合emoji。

## 配色核对

同视口对照 [桌面首屏](screenshots/desktop-home.jpg)、[解决方案](screenshots/desktop-solutions.jpg)、[园区与企业](screenshots/desktop-companies.jpg)。先看大面积：Hero下沿是否回到白、方案区是否渐隐、产品面板是否白；再看局部：品牌蓝是否统一、企业渐变方向、Tab hover/selected顺序、蓝色阴影是否只在应有模块增强。不要用JPEG像素取样替代源CSS；截图抗锯齿、压缩和透明叠加都影响像素色。
