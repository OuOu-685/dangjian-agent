# 01 · 剪贴板信封与三种格式辨析

## 1. 剪贴板格式的完整外层

```json
{
  "type": "coze-workflow-clipboard-data",
  "source": {
    "workflowId": "7687266526169120819",
    "flowMode": 0,
    "spaceId": "7493357645614039092",
    "isDouyin": false,
    "host": "www.coze.cn"
  },
  "json": {
    "nodes": [ /* 节点数组 */ ],
    "edges": [ /* 连线数组 */ ]
  },
  "bounds": { "x": -364, "y": -109.35, "width": 5150, "height": 195.35 }
}
```

| 字段 | 证据 | 说明 |
|---|---|---|
| `type` | `[实测]` | 固定 `"coze-workflow-clipboard-data"`，不能改 |
| `source.workflowId` | `[实测]` | 来源工作流 ID。**粘贴到别的空间/工作流时它不构成校验**——实测把 A 工作流的 JSON 粘到 B 工作流可以成功 |
| `source.flowMode` | `[实测]` | 全部样本都为 `0`。含义未证实，**照抄 0** |
| `source.spaceId` | `[实测]` | 空间 ID。**不是门槛**——实测样本里出现过 4 个不同 `spaceId`，都能粘 |
| `source.isDouyin` | `[实测]` | 全部 `false`。抖音端相关，**照抄 false** |
| `source.host` | `[实测]` | 全部 `"www.coze.cn"` |
| `json.nodes` / `json.edges` | `[实测]` | 根层节点与连线 |
| **顶层 `bounds`** | **`[实测]` 13/13** | **必需**，见下节。**不是** `json.bounds` |

> ⚠️ **已更正的一处错误结论（本技能最贵的坑）**：本文档早期版本把 `bounds` 写在 `json` 里面，并标注「可选，建议省略，平台会自行算」。
> **这是错的**，而且这个错误直接导致生成器漏写 `bounds`，出现「按 Ctrl+V 完全没反应」。
> 正确位置是**顶层**（`type` / `source` / `json` 的兄弟），且**必须写**。已用单变量对照实验实证闭环（见 §1.1）。
>
> **教训**：文档里写「可选 / 建议省略 / 平台会自行处理」这类**主观判断**时，必须标证据等级，
> 不能凭感觉写。一个没根据的「可选」害整批文件全部粘不上。

---

## 1.1 ⚠️ 顶层 `bounds` —— 缺了会「按 Ctrl+V 毫无反应」

这是本技能踩过**最贵**的一个坑，单独成节。

### 定义（13/13 精确吻合）

```
顶层 bounds = 所有【根节点】 _temp.bounds 的并集
  x      = min(每个节点的 bounds.x)
  y      = min(每个节点的 bounds.y)
  width  = max(bounds.x + bounds.width)  - x
  height = max(bounds.y + bounds.height) - y
```

注意是**根节点**（不含循环/批处理 `blocks` 里的子节点）—— 13 份文件按「只算根节点」全部精确吻合（浮点误差 < 1e-6）。

### 验证记录

| 文件 | 顶层 `bounds` | 根节点并集 | 一致 |
|---|---|---|---|
| 新建文本文档.txt | `{"x":-2367.7688507052735, …}` | 同 | ✅ |
| risk_detector.txt | `{"x":-180,"y":-112.0005,"width":3281.7755029471846,…}` | 同 | ✅ |
| wf_onboarding.md | `{"x":0,"y":0,"width":8840,"height":796}` | 同 | ✅ |
| 测试工作流.md | `{"x":-364,"y":-109.35,"width":5150,"height":195.35}` | 同 | ✅ |
| …（13 份全测） | — | — | **13/13 ✅** |

### 🎯 实证闭环（单变量对照实验，已由用户真机验证）

上面「13/13 吻合」只是**结构统计**。真正的因果证明是一次**单变量对照实验**：

| # | 文件 | 顶层 `bounds` | 其他内容 | 真机结果 |
|---|---|---|---|---|
| 1 | 平台原版（用户从 Coze 自己复制） | ✅ 有 | 基准 | ✅ **能粘** |
| 2 | **实验A = 平台原版 − 顶层 bounds** | ❌ 无 | **与 #1 逐字节相同，仅少这一个字段** | ❌ **毫无反应** |
| 3 | 修复后的生成器产物 | ✅ 有 | 我们自己生成 | ✅ **能粘** |

**三个文件之间唯一的变量就是 `bounds`。因果锁定，无需再猜。**

> 复现方法（以后遇到可疑字段都能用这招）：拿一份**已确认能粘**的文件，**只删/只改那一个字段**，
> 再让用户粘一次。这比「反复调整自己生成的文件」快得多，而且结论不可反驳。

### 症状与判别（照这个顺序排查，别跳步）

| 症状 | 最可能的原因 | 处理 |
|---|---|---|
| 按 Ctrl+V **完全没反应**（无报错、无节点、无提示） | ① **缺顶层 `bounds`** ② 画布已有同 id 节点 ③ 用了缩进版 | 跑 `validate_workflow.py`，看 `E16`；再看清单第 1 条 |
| 弹红条报错 | **不是** `bounds` 问题 —— 那是资源 ID 校验（见 `08` / `09`） | 按 `E15` 修资源 ID |

⚠️ **极易误判**：缺 `bounds` 时节点内容**完全正确**、结构校验**全对**，人很容易去怀疑「平台不允许外部 JSON 粘贴」。
实际是**信封层少了一个字段**。`E16` 就是专门守这条的。

⚠️ **极易误判**：因为节点内容完全正确、`validate` 结构也全对，人会去怀疑「平台不让外部 JSON 粘贴」。
实际是**信封层少了一个字段**。所以校验器加了 `E16` 专门守这条。

### 节点侧对应的字段

每个节点的 `_temp.bounds` 是平台自己算的：`x = meta.position.x - 180`、`y = meta.position.y`、`width = 360`、`height` 按类型查表（`BOUNDS_H`）。所以**只要节点位置定了，`bounds` 就是确定的**，不需要额外信息。

> 最省事的做法：从目标工作流里复制一个节点出来当模板，只替换 `json.nodes` / `json.edges`，`source` 整块保留原样。这也是 `build_workflow.py` 默认的行为（可传 `--base template.json` 继承一份真实信封）。

## 2. 节点对象的统一骨架

```json
{
  "id": "151383",
  "type": "3",
  "meta": {
    "position": { "x": 640, "y": 0 },
    "canvasPosition": { "x": 1128.65, "y": 297.18 }
  },
  "data": {
    "nodeMeta": {
      "title": "信息解析大模型",
      "subTitle": "大模型",
      "description": "调用大语言模型,使用变量和提示词生成回复",
      "icon": "https://lf3-static.bytednsdoc.com/.../icon-LLM-v2.jpg",
      "mainColor": "#5C62FF"
    },
    "inputs": { /* 每种节点不同 */ },
    "outputs": [ /* 输出声明 */ ],
    "version": "3"
  },
  "_temp": {
    "bounds": { "x": 460, "y": 0, "width": 360, "height": 163.6 },
    "externalData": { "icon": "…", "description": "…", "title": "大模型", "mainColor": "#5C62FF" }
  },
  "blocks": [ /* 仅循环节点 */ ],
  "edges":  [ /* 仅循环节点：内层连线 */ ]
}
```

| 字段 | 证据 | 说明 |
|---|---|---|
| `meta.position` | `[实测]` | 画布坐标。原点在初始画布中间虚拟区（1512×644）左上角，X 右为正、Y 下为正 |
| `meta.canvasPosition` | `[实测][官方]` | **只有循环 / 批处理节点**有，是子画布位置 |
| `data.nodeMeta.subTitle` | `[实测]` | 画布上的类型小标签（"大模型"/"代码"…）。**注意大小写：只有插件节点用全小写 `subtitle`** |
| `data.nodeMeta.mainColor` | `[实测]` | 颜色。开始/结束节点**没有**这个字段 |
| `data.version` | `[实测]` | 大模型与代码节点有（`"3"` / `"v2"`）。其他类型没有 |
| `_temp.bounds` | `[实测]` | 视觉包围盒，宽固定 360，高随内容变。**删掉也能粘贴成功**，但保留更像"原生的" |
| `_temp.externalData` | `[实测]` | 图标/描述/标题的冗余副本。插件节点这里还带完整 `inputs`/`outputs` 定义 |
| `blocks` / `edges` | `[实测]` | **仅循环节点**的顶层字段，见 `05-edges-and-ports.md` |

### 各节点主色 `[实测]`

| 颜色 | 用于 |
|---|---|
| `#5C62FF` | 开始、结束、大模型 |
| `#00B2B2` | 代码、选择器、循环、变量聚合 |
| `#3071F2` | 文本处理 |
| `#F2B600` | 数据库类（查询 / 新增 / 更新） |

### 图标 URL `[实测]`

全部是 `https://lf3-static.bytednsdoc.com/obj/eden-cn/dvsmryvd_avi_dvsm/ljhwZthlaukjlkulzlp/icon/<name>-v2.jpg`，已知 name：

`icon-Start`、`icon-End`、`icon-LLM`、`icon-Plugin`、`icon-Code`、`icon-Condition`、`icon-Loop`、`icon-StrConcat`、`VariableMerge-icon`、`icaon-database-select`（注意官方这里把 icon 拼成了 `icaon`）、`icon-database-insert`、`icon-database-update`。

找不到对应图标时，**直接复用同类型节点的图标**即可，不影响功能。

## 3. 三种格式的辨析（重要）

### A. 剪贴板格式 —— 本技能主角
见上文。**用途：在画布上 Ctrl+V 粘贴。**

### B. 官方 DSL 导出格式 —— 有官方文档，但不能直接粘贴

```yaml
schema_version: 1.0.0
name: summarize_article_1_783
id: 7482702358159*****
description: 示例：总结提炼文章中的要点
mode: workflow
icon: plugin_icon/workflow.png
nodes:
  - id: "100001"
    type: start
    title: 开始
    icon: https://...
    description: 工作流的起始节点，用于设定启动工作流需要的信息
    position: { x: 180, y: 39.7 }
    parameters:
      node_outputs:
        article_url: { type: string, required: true, description: 文章的链接地址 }
  - id: "197398"
    type: llm
    parameters:
      node_inputs:
        - name: input
          input:
            value: { ref_node: "140349", path: data.content }
      node_outputs:
        summary: { type: string }
edges:
  - { source_node: "100001", target_node: "140349" }
```

关键差异一览：

| 维度 | 剪贴板 | DSL |
|---|---|---|
| 节点类型 | 数字字符串 | 英文名（`start`/`llm`/`condition`/…） |
| 输入输出 | `data.inputs` / `data.outputs` | `parameters.node_inputs` / `parameters.node_outputs` |
| 输出定义形态 | **数组** `[{name,type,…}]` | **对象** `{ 变量名: {type, required} }` |
| 值引用 | `blockID` + `name` | `ref_node` + `path` |
| 数据类型关键字 | `string`/`integer`/`boolean`/`float`/`object`/`list` | `string`/`integer`/`number`/`boolean`/`object`/`array`/`file`/`image`/… |
| 数值类型名 | `float` | `number` |
| 数组类型名 | `list` | `array` |
| DSL 独有 | — | `schema_version`、`mode`、`icon`、`name`、`description` |
| 剪贴板独有 | — | `_temp`、`rawMeta`、`trigger_parameters`、`source` |

⚠️ 两个易错点：
- **LLM 节点的模型名字段拼写不同**：剪贴板里是 `modleName`（官方拼错了，实测 21/21 个节点全是这个拼法），DSL 里是 `modelName`。**别"顺手改对"**。
- **DSL 的 `type` 列表里 `knowledge` 是"知识库检索"，而剪贴板 `type:"6"` 的 subTitle 也是"知识库检索"**，可以对应；但 DSL 的 `dataset_write`/`dataset_delete` 是知识库**写入/删除**，剪贴板样本中未出现对应编号，**不要臆造**。

### C. 伪格式 —— 不要用
网上流传的"节点编号 1~10 对照表"（1 插件 / 2 大模型 / 3 代码 / 4 知识库 …）**不是 `type` 字段的取值**。那只是某篇文章对"工作流有哪些组件"的列举编号。照它写 JSON 一定粘贴失败。


## 2. 输出形态：**一律单行紧凑**（实测教训）

平台自己写进剪贴板的载荷是**单行紧凑 JSON**，不是带缩进的多行。

| | 字节 | 行数 |
|---|---|---|
| 平台自己导出的（示例） | 43,964 | **1** |
| 同一份内容用 `indent=2` 输出 | 93,358 | 2,865 |

**缩进版体积接近翻倍**，粘贴时出现过「按了 Ctrl+V **完全没反应**」（不是弹红条，是毫无动静）。

**规则：交付给用户粘贴的一律单行。**

```python
json.dumps(obj, ensure_ascii=False, separators=(",", ":"))   # 单行
# 写文件时还要加 newline="\n"，避免 Windows 上写出 


open(path, "w", encoding="utf-8", newline="\n")
```

`build_workflow.py` 默认就是单行（`--indent 2` 可切换成可读版，但**别拿去粘贴**）。

---

## 3. 粘贴失败排查清单（按可能性排序）

| # | 现象 | 原因 | 处理 |
|---|---|---|---|
| **1** | **Ctrl+V 完全没反应**，画布无变化 | **顶层缺 `bounds`**（见 §1.1）—— 平台拿不到落位包围盒就静默中止。**先查这条**，跑 `validate_workflow.py` 看有没有 `E16` | 用生成器重新产出（默认已带 `bounds`），或手工补上「根节点包围盒并集」 |
| 2 | 同上 | **画布上已经有这些 node id 了** —— 同一份内容粘第二次会被静默忽略（不报错、不提示） | ① 新建一个空工作流再粘；或 ② 先删掉画布上已有的节点；或 ③ 换一批 node id 重新生成 |
| 3 | 同上 | 用的是**缩进版**文件（体积翻倍） | 改用单行版 |
| 4 | 同上 | 画布**没获得焦点**（焦点还在左侧资源列表/右侧面板） | 先在画布空白处点一下，再 Ctrl+V |
| 5 | 同上 | 复制的是**预览面板里可见的那一段**，不是完整文件 | 用记事本打开 → `Ctrl+A` → `Ctrl+C`；粘到记事本先自查首尾是不是 `{` 和 `}` |
| 6 | 弹红条「知识库 xxx 不存在」 | 资源类 ID 是占位符 | 见 `08`，资源类 ID 必须填真值 |
| 7 | 弹红条「数据库不存在」 | `databaseInfoID` 填错或不属于当前空间 | 从自己的工作流里挖，见 `09` |
| 8 | 部分节点没进来 | 平台对单次粘贴的节点数有上限 | 分批粘（按阶段拆，每批 ≤ 10 个节点） |
| 9 | 节点进来了但没连线 | 合成粘贴不还原 edges | 手动拖一下；或把 edges 单独作为一个小文件粘 |

### 最快的定位方法：3 节点冒烟测试

准备一个**最小可粘工作流**（开始 → 代码 → 结束，约 3KB / 1 行）：

- 它能粘进去 → 粘贴通道没问题，问题在**大文件**（换单行版 / 分批 / 换空画布）
- 它也粘不进去 → 问题在**通道或环境**（焦点、剪贴板、权限）

**别一上来就怀疑 JSON 结构**——先确认通道能用，再查内容。

---

## 4. 附：key 顺序不用管

对 13 份平台文件做过对照：平台**自己各类型的 `data` 键顺序都不一致**（例如结束节点是 `nodeMeta, inputs`，循环节点是 `inputs, nodeMeta, outputs`，意图识别是 `nodeMeta, outputs, inputs`）。所以键顺序**不是**粘贴失败的原因，不必刻意对齐。

顶层和节点级的顺序倒是稳定的，可以照抄：

```
顶层:  type → source → json{nodes, edges}
节点:  id → type → meta{position} → data → _temp{bounds, externalData}
```

## 5. 导入方式（两种，都实测存在）

**方式 1：Ctrl + V 粘贴（官方免费用户首选）**
1. 用记事本打开 JSON 文件，`Ctrl+A` `Ctrl+C` 全选复制
2. 回到 Coze 工作流工作台，`Ctrl+V`
3. 平台提示"当前复制内容包含开始/结束节点，已自动覆盖开始/结束参数配置"

**方式 2：导入按钮（会员）**
创建工作流时点「导入」→ 选 JSON 文件。

**已知现象**：
- 粘贴会**覆盖**画布上原有的开始/结束节点参数，其他节点是**追加**。
- 部分场景下**连线不还原**，需要手动拖一下 —— 交付时提前告知用户。
- 改完工作流**必须重新发布**（或智能体里重新选版本）才生效。
