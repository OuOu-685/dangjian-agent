# 05 · 连线、分支端口与校验清单

## 边（edges）的三种形态 `[实测]`

```json
{ "sourceNodeID": "100001", "targetNodeID": "151383" }                            // 普通直线
{ "sourceNodeID": "175977", "targetNodeID": "101712", "sourcePortID": "true" }     // 选择器的"如果"分支
{ "sourceNodeID": "175977", "targetNodeID": "164691", "sourcePortID": "false" }    // 选择器的"否则"分支
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `sourceNodeID` | 是 | 起点节点 id |
| `targetNodeID` | 是 | 终点节点 id |
| `sourcePortID` | 否 | 从**源节点的哪个出口**出来。缺省 = 默认出口 |
| `targetPortID` | 否 | 指向**目标节点的哪个入口**。仅在循环体的回连中出现 |

⚠️ **JSON 里键的顺序不重要**，但实测平台自己写出来的顺序是 `sourceNodeID, targetNodeID, sourcePortID`。生成时保持这个顺序更"原生"。

## 端口的已知取值 `[实测]`

| 端口名 | 出现在 | 含义 |
|---|---|---|
| （缺省） | 普通边 | 唯一出口 / 默认出口；**选择器的"否则"分支也是缺省** |
| `"true"` | 选择器的边 | 第 1 个 `如果能…` 分支 |
| `"false"` | 选择器的边 | 第 2 个分支 |
| `"loop-output"` | 循环 → 下游 | 循环节点的对外出口。**循环节点连向后续节点时必须带上** |
| `"loop-function-inline-output"` | 循环 → 循环体节点 | 从循环节点**进入**循环体 |
| `"loop-function-inline-input"` | 循环体节点 → 循环节点 | 从循环体**回到**循环节点（写在 `targetPortID`）|
| `"batch-output"` | 批处理 → 下游 | 批处理节点的对外出口。**与循环对应但名字不同**，不要混用 |
| `"branch_0"` `"branch_1"` … `"branch_{N-1}"` | **意图识别 → 各意图分支** | 按 `inputs.intents` 数组**下标**对应：`branch_0` = 第 1 个意图 |
| `"default"` | **意图识别 → 未匹配** | 没有命中任何意图时的出口 |

### ⚠️ 意图识别：有几个 `intents`，就必须连出几条边

**实测样本（用户 2026-09-20 提供，4 类意图）**：

```jsonc
"intents": [ {"name":"正常求职指导"}, {"name":"代写简历或代做测评"},
             {"name":"编造经历学历或伪造材料"}, {"name":"按性别地域等敏感属性筛选候选人"} ]
// 出边：
{"sourceNodeID":"100002","targetNodeID":"131427","sourcePortID":"branch_0"}
{"sourceNodeID":"100002","targetNodeID":"105869","sourcePortID":"branch_1"}
{"sourceNodeID":"100002","targetNodeID":"173620","sourcePortID":"branch_2"}
{"sourceNodeID":"100002","targetNodeID":"134476","sourcePortID":"branch_3"}
{"sourceNodeID":"100002","targetNodeID":"900001","sourcePortID":"default"}
```

**这是一条硬要求，不是建议**：N 个 `intents` → 必须写 **N 条 `branch_N` 边 + 1 条 `default` 边**。
少写一条的后果：**画布上那个分支端口是悬空的**，用户一眼就能看出来（"你有几个匹配项就得创造几个分支"）。

- 允许多条分支指向**同一个下游节点**（例如 `branch_0` 和 `default` 都进「正常处理」链），扇入是合法的。
- 也可以让某条分支直接连到 `结束`，或连到一个「输出」节点（`type 13`）。
- `default` **不能省** —— 它是「意图识别没匹配上」的唯一出口。
- 校验器 **`E18`** 专守这条（见 `10`/脚本头部）。

> 不要用「顺序推断」去造多分支端口名（例如给选择器猜 `branch_0`）。
> 意图识别的端口**确实**叫 `branch_N`，但选择器是另一套实现，**两者不能互推**。

### ⚠️ 选择器：`branches` **恒为 1 项**，`false` 是隐式「否则」

**实测 13/13：所有真实选择器节点的 `inputs.branches` 数组长度都是 1。**

```
inputs.branches[0].condition = { logic: 2, conditions: [ {operator, left, right} ] }
  → true  端口：上面这个条件成立时走
  → false 端口：隐式「否则」，**不需要、也不应该**再写一个条件
```

所以「如果 v_ok == Y，否则……」**只写 1 个条件**即可。多写的项会被平台当成「否则如果」分支，
而**它对应的端口名本技能没有实测样本**（全样本 24 条选择器出边只有 `true` / `false`），所以无法连线。

**那需要 3~4 路分流怎么办？**（例如「按专业类别分 4 条」）

→ **串成多个二分支选择器**：

```
选择器A: v == "cs"    true→分支1    false→选择器B
选择器B: v == "arts"  true→分支2    false→选择器C
选择器C: v == "sci"   true→分支3    false→分支4（兜底）
```

`wf_onboarding.md` 里就有 **3 个选择器串联**的真实样本（`169542 → 185594 → 183021`），此写法有实测依据。
代价是节点数增加（4 路分流需要 3 个选择器，而不是 1 个）。

> 反过来也成立：**能在意图识别节点一次分流的，就别用选择器串联**。
> 意图识别天然支持 N 路（每个意图一个端口），而选择器只能 2 路。
> 判据：分流的依据如果**本来就是「用户想干什么」**，交给意图识别；
> 如果依据是**上游节点算出来的状态量**（如 `v_hit == 'Y'`、`data_len == 0`），才用选择器。

### 选择器的端口到底怎么写（容易搞错）

实测样本（`新建 文本文档.txt` / `新建 文本文档 (3).txt`）：

```
① 单分支的写法：
   {"sourceNodeID":"175977","targetNodeID":"101712","sourcePortID":"true"}    ← 条件成立
   {"sourceNodeID":"175977","targetNodeID":"164691","sourcePortID":"false"}   ← 条件不成立（否则）

② 但同一份里还有一条普通边：
   {"sourceNodeID":"101712","targetNodeID":"164691"}                          ← 分支内部继续往下
```

结论：**用 `"true"` / `"false"` 两个端口表达选择器的两条出路，不要用缺省。** 因为缺省端口在别的语境下表示"唯一出口"，混用会让校验脚本和平台都难以判断。

多分支时的端口名（如第 3、第 4 个 `如果能`）**样本里没有出现**，取值为 `"3"`、`"4"` 之类的猜测**未证实**——需要多分支时，先在画布上配好再复制出来看端口名。

### 循环节点的内外三根线（必须三根都给齐）

```json
"edges": [
  {"sourceNodeID":"161640","targetNodeID":"197010","sourcePortID":"loop-function-inline-output"},
  {"sourceNodeID":"197010","targetNodeID":"161640","targetPortID":"loop-function-inline-input"}
],
"blocks": [ {"id":"197010", "type":"3", …} ]
```

- 这两条边写在**循环节点的顶层 `edges`** 里（不是工作流根层的 `edges`）。
- 循环节点自身与外部节点的连线写在**工作流根层的 `edges`** 里，用 `sourcePortID: "loop-output"`。
- 循环体内部节点之间的连线，也写在循环节点顶层 `edges` 里，用普通形态（无端口）。

## 根层 `edges` 与循环内 `edges` 的关系

```
{
  "json": {
    "nodes": [
      { "id":"171354", … },
      { "id":"161640", "type":"21", "blocks":[…], "edges":[…循环内的边…] },
      { "id":"131835", … }
    ],
    "edges": [
      {"sourceNodeID":"100001","targetNodeID":"171354"},
      {"sourceNodeID":"171354","targetNodeID":"161640"},                      ← 进循环
      {"sourceNodeID":"161640","targetNodeID":"900001","sourcePortID":"loop-output"}   ← 循环出
    ]
  }
}
```

**根层 `edges` 不允许出现指向循环体内部节点的边**（实测样本中，循环体内部节点 `197010` 从未出现在根层 edges 里）。

## ⚠️ 循环节点的"变量来源"不止 outputs（**曾因此误报，务必记住**）

循环体内引用 `blockID = 循环节点id` 时，`name` **可以从循环节点的 `inputParameters` 里取**——这是"循环变量"，即当前遍历到的那个元素：

```json
// 循环 113490 的定义
"inputs": {
  "inputParameters": [
    {"name": "header",    "input": {"type": "list", "schema": {"type": "string"}, …}},
    {"name": "task_book", "input": {"type": "list", "schema": {"type": "object", …}, …}},
    {"name": "module",    "input": {"type": "list", …}}
  ],
  "loopType": "array"
}

// 循环体内的文本处理节点这样引用 —— 合法！
{"type": "ref", "content": {"source": "block-output", "blockID": "113490", "name": "header"}}
{"type": "ref", "content": {"source": "block-output", "blockID": "113490", "name": "task_book"}}
```

另一例：循环 `177204` 的 `inputParameters` 只有一个 `plan_items`（list），循环体内的新增数据节点引用 `177204.plan_items.stage` / `177204.plan_items.task_name` —— **这也是合法的**（对当前元素取字段）。

**结论：校验循环引用时，可引用名 = `outputs[].name` ∪ `inputParameters[].name`。批处理（`type:"28"`）**完全同理**（实测子画布内的代码节点引用 `134383.input`，而 `input` 正是批处理的 `inputParameters[0].name`）。

⚠️ **还有一层语义**：子画布内拿到的**不是整个数组，而是「当前元素」**。所以给内层节点推导类型时要降一层：

```
list<object{content_type, content}>  →  object{content_type, content}   （元素类型）
list<string>                        →  string
```

实测证据：批处理节点的 `inputParameters[0].input.type = "list"`，
而子画布内代码节点的 `inputParameters[0].input.type = "object"` + `schema:[{content_type},{content}]`。
**漏了这层降级，生成的结构会和平台不一致**（早期版本就踩过）。

> **踩坑记录**：本技能第一版校验器只查了 `outputs`，把上面两处**合法引用误报成 E5「引用了不存在的变量」**，还写进了交付说明——差点让用户去改一份本来正确的工作流。
> **教训**：校验器对**平台自己生成的文件**报 error，第一反应应该是"我的规则漏了"，而不是"用户的文件错了"。**零误报**是校验器的底线：12 份平台文件里任何一条 error 都说明规则有问题。

同样地，**工作流（子工作流）节点的 `inputDefs[].name` 也登记为可引用名**（保守起见，样本中未直接观察到引用，但结构上成立）。

## 校验清单（`validate_workflow.py` 实现的 15 条）

按"能不能用"分三档。**E = error（必须修）**，**W = warning（建议修）**。

| # | 级别 | 规则 | 为什么 |
|---|---|---|---|
| 1 | E | `nodes` 里 `id` 全局唯一（含循环体 `blocks` 内的 id） | 重复 id 会让引用指向错误节点 |
| 2 | E | 每条工作流**恰好 1 个 `type:"1"`、恰好 1 个 `type:"2"`** | 官方硬约束，多个结束节点会导致输出定义冲突 |
| 3 | E | 根层 `edges` 的 `sourceNodeID` / `targetNodeID` 都存在于 `nodes` | 悬空边 = 断链 |
| 4 | E | 每个 `ref.content.blockID` 都存在于 `nodes`（或在**同层** `blocks` 里） | 引用了不存在的节点 |
| 5 | E | 每个 `ref.content.name` 能在目标节点的 `outputs` 里找到（支持 `a.b` / `a[0]` 点路径） | 引用不存在的变量是运行时才报错的静默坑 |
| 6 | E | 代码节点：**每个 `return {...}` 字面量的键集合都完整覆盖 `outputs[].name`** | 少一个键 → 走到那条路径才报"变量不存在"，极难排查 |
| 7 | E | 代码节点：`inputParameters[].name` 与函数形参名一致（用 AST 解析） | 形参名对不上 → 取不到值 |
| 8 | W | 大模型节点 `llmParam` 应包含 19 个固定键 | 缺项不必然报错，但配置面板可能显示异常 |
| 9 | W | 插件节点 `apiParam` 应包含 7 个固定键 | 同上 |
| 10 | W | 选择器节点：`branches` 应为 **1 项**（`W18`）；出边应有 `true`/`false` 两条 | 实测平台恒为 1 项，多写会变成端口名未知的「否则如果」分支 |
| 11 | W | 循环节点必须有非空 `blocks`，且内层 `edges` 含 `loop-function-inline-output` 与 `loop-function-inline-input` 各一条 | 缺了循环体跑不起来 |
| 12 | W | 未在本技能 `02` 表中证实的 `type` 编号 | 提示"未知类型，请实测确认" |

### 第 6 条为什么必须做

```python
def main(task_book: dict) -> dict:
    if not task_book:
        return {"is_valid": False}                    # ← 只有 1 个键
    return {"is_valid": True, "missing_modules": [], "check_report": "通过"}
    #        ↑ 3 个键
```

平台**不会**在保存时报错。只有当输入走空分支时，下游引用 `{{格式校验.missing_modules}}` 才炸，且报错信息不会告诉你"是代码节点少写了键"。这条只有静态分析能提前发现。

### 第 7 条的两种合法形态

```
形态 ① async def main(args: Args) -> Output:   → 形参名固定为 args，不校验
形态 ② def main(task_book: dict) -> dict:      → 形参名必须 == inputParameters 的 name 集合
```

脚本按此区分：形参列表长度 == 1 且名字是 `args` → 走形态 ①，跳过第 7 条；否则按形态 ② 严格比对。

### 点路径引用的解析规则

`ref.content.name` 允许以下形式，校验时逐层下钻：

| 形式 | 例 | 解析方式 |
|---|---|---|
| 直接变量 | `paragraphs` | 在 `outputs[].name` 里精确匹配 |
| 对象字段 | `data.content` | 找到 `data`（`type:"object"`），在它的 `schema[].name` 里找 `content` |
| 数组元素字段 | `outputList.id` | 找到 `outputList`（`type:"list"`），在其 `schema.schema[].name` 里找 `id` |
| 特殊：循环体内部节点 | `197010.output` | `blockID` 指向 `blocks` 里的节点 |
| 特殊：`*` 通配 | — | 样本中未出现，遇到就跳过校验并告警 |

**无法解析时输出 W 而不是 E**（因为 schema 可能是空数组 `[]`，例如数据库写入节点的 `outputList`）。

## 交付前的人味检查（脚本查不出来）

1. **变量命名遵循前缀约定**：`in_`(入参) `q_`(查询结果) `k_`(知识库) `llm_`(大模型) `v_`(中间变量) `out_`(输出)。跨工作流同名变量必须同名。
2. **结束节点引用的每个变量，在所有路径上都有值**。典型翻车：结束节点引用分支内部才产出的变量 → 另一条路径上它不存在。
3. **别在一条工作流里画多个结束节点**来分流"不同话术"。正确做法是：用代码节点/大模型节点在**分支之前**算好 `out_status`，结束节点无条件引用它。
4. **能在分支之前算的，不要放到分支之后**——分支前的节点在所有路径上都执行，其输出可被下游无条件引用，省掉整个变量聚合。
5. **粘贴后立刻用画布的「试运行」单测**，不要通过对话调试（慢 10 倍）。
6. **改完必须重新发布**，否则智能体仍用旧版。
