# 原站观察与证据

采集：2026-09-14。来源：[https://foru-ai.com/](https://foru-ai.com/)。页面标题为“优才知路-领先AI产教融合平台 | 院校企业人才对接 | 实习就业解决方案”。范围是公开首页、导航菜单及首页交互，不包含登录后的工作台，也不宣称覆盖所有产品子站。

## 证据可信度

- **直接实测**：浏览器渲染页面、DOM、computed style、已加载CSS、可见交互状态。
- **有来源的推断**：Nuxt/Vue与Element UI来自#__nuxt、#__layout、/_nuxt/、data-v属性、el-carousel类等公开痕迹；不能据此确定准确版本或完整服务架构。
- **重建建议**：组件拆分、流式Grid、移动端断点、可访问性、生命周期管理，以及随包starter；均非原站源代码。

HTTP抓取与web打开当时返回500；Tavily已安装，但extract因配额限制失败。主要证据由正常渲染的浏览器获得，并成功导出已观察的公开样式资源。不能把抓取失败推断为网站对用户不可用。

## 实测交互

| 测试 | 结果 |
| --- | --- |
| 初始个人角色 | 知路课堂、优才智评、找工作、找项目 |
| 选择企业角色 | 蓝色选中项转到企业；展示优才甄选、项目众包、科技成果 |
| 展开产品生态菜单 | 四列，面向个人、企业、院校、共建者；每项有说明/子入口 |
| AI展示等待期间 | active项和图示会自动变化 |
| 手动选择简历疑点亮点 | 当前标签变为知识图谱、简历标签提取等；右图为column3-2.dd05936.png |
| 产业链状态 | 普通项106px、当前项245px、高234px；参考截图中当前行业会变化 |
| 窄屏390 × 844 | innerWidth390、clientWidth386、scrollWidth1200；header与内容区均1200px |

桌面测量视口1440 × 1000，实际页面client宽1436px（滚动条占4px）；1200px内容区起始x118px。原站按content-box计算部分尺寸：Tab CSS内容宽160 + 左右48 padding = 外宽208；产品面板内容宽1120 + 左右80 padding = 外宽1200。重建按border-box换算可见尺寸。

完整首页当时高度约9955px；一次返回首页时新闻请求未成功、页面变为约9298px。总高度与每个区块y坐标是异步内容的结果，不是设计token。

## 样式定位

已加载资源含：

- [首页相关CSS c3985be.css](https://foru-ai.com/_nuxt/css/c3985be.css)
- [共享CSS eb25074.css](https://foru-ai.com/_nuxt/css/eb25074.css)
- [共享组件CSS 8dcf1e7.css](https://foru-ai.com/_nuxt/css/8dcf1e7.css)
- [布局CSS fa4333c.css](https://foru-ai.com/_nuxt/css/fa4333c.css)
- [自定义业务UI](https://foru-ai.com/cjrh_cdn/yc-business-ui/yc-business-ui.css)

与复现有关的选择器记录于 [source-css.txt](source-css.txt)：cjrh_page_main、column-header、cont-wrap、swiper-button、nav-item__wrap、cont-item、solution-card、left-section__item、column4-item、column5至column12及fixed header。哈希资源名仅用于本次来源定位，不作为长期开发依赖。

公开设计素材URL见 [asset-inventory.json](asset-inventory.json)，只保留图片、字体与样式引用，未保留接口请求、脚本、会话数据或data URI。Hero背景资源为2026/02/05路径下的蓝紫AI平台PNG；它是插画背景，标题和CTA是HTML叠层。源字体名HP-Regular/Medium是CSS别名，未据此推断真实字体来源。

## 配色细化复核

同日第二轮由三个 subagents 分别复核配色、组件细节和示例，主 agent 在原站补测。原始 computed style 与相关已加载 CSSOM 规则存于 [visual-recheck.json](visual-recheck.json)，不是原站设计文件或源码仓库。

| 复核对象 | 直接证据 | 重建时的含义 |
| --- | --- | --- |
| 区块标题 | `34px / 50px; HP-Medium; font-weight:400`，色 `#1F2329` | Medium 是字体别名；系统字体建议先用500再目测，不将900传播到全部标题 |
| 方案区 `.bg3` | `linear-gradient(#FAFEFF, rgba(245,251,253,0) 100%)` | 区块渐隐，与资源区 `#F9FBFF` 分开 |
| 伙伴 `.column10-wrap` | 白 `.79` → `#8DD0FF` `.79`；白 `.6` 描边，24px圆角、blur60px；`0 12px 22px rgba(47,111,229,.4)` | 原 `.79` 是透明度；单纯复制到白底不能复现后方蓝色图片的影响 |
| 页脚主底 / 标题 / 链接 | `#141933` / `#FBFCFD` / `#C9CDD4`；链接12px/17px | 与 Hero 标题 `#061840` 分开，不共用深色token |
| 产品菜单表面 | 白底，`0 12px 32px rgba(0,0,0,.12)`；四列共用1200px中线 | 下拉菜单投影是源站的中性投影例外，不将它复制到业务卡片 |
| 菜单分组标题 | 14px/21px、weight500，下padding8px | 分组、产品、子入口分层，不简化成四个大按钮 |

Hero和图标的立体光色来自位图，新增 [color-recipes.md](color-recipes.md) 中的蓝紫青近似值属于重建建议。颜色应先从源CSS核对；JPEG像素同时受压缩、抗锯齿、透明叠加影响，不能直接当官方token。

## 截图

按需查看，图片作为证据而非输出页面素材：

- [桌面首屏与角色入口](screenshots/desktop-home.jpg)
- [解决方案卡片](screenshots/desktop-solutions.jpg)
- [四列产品菜单](screenshots/desktop-megamenu.jpg)
- [AI功能展示](screenshots/desktop-ai-features.jpg)
- [产业链展开状态](screenshots/desktop-industry.jpg)
- [园区与企业卡片](screenshots/desktop-companies.jpg)
- [岗位卡片与标签层级](screenshots/desktop-jobs.jpg)
- [完整伙伴区与背景波形](screenshots/desktop-partners.jpg)
- [已完成入场的选择理由](screenshots/desktop-reasons.jpg)
- [页脚](screenshots/desktop-footer.jpg)
- [原站390px溢出](screenshots/mobile-original.jpg)

截图中的业务内容、数据和图片加载状态可能随着时间变化。高保真核对以截图、相关CSS和实测尺寸相互参照；不要仅依赖一张还在入场动画中的截图。

本轮更正：先前的 `desktop-megamenu.jpg` 实际拍到已关闭菜单的方案区，现替换为实际展开的四列产品菜单局部截图；菜单下部未全部收入，少量图标尚在加载。`desktop-footer.jpg` 也已替换为理由卡片完成入场后的页尾，另补一张理由区截图。首页截图更新为四个入口完成入场后的状态，可见卡片在面板内均分；第二轮顶部占位与第一轮相差64px，未确定原因，不据此改写64px导航或460px Hero规格。未加载图像、入场偏移和动态占位均不作为设计规范。
