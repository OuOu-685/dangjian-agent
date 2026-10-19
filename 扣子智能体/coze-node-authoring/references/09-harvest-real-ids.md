# 09 · 挖出「平台侧生成的资源 ID」（不要手填、不要瞎猜）

## ⚠️ 资源 ID 有「空间隔离」—— 这是最容易翻车的地方

**`databaseInfoID` / `fieldID` / `datasetList`（知识库）/ `apiID` / `workflowId` 都是按 `spaceId` 隔离的。**
在空间 A 挖到的资源 ID，粘到空间 B 的工作流里**不认**，会直接弹红条阻断导入。

### 实测证据

同一批用户样本里出现过 **5 个不同的 `spaceId`**：

| spaceId | 样本数 |
|---|---|
| `7493357645614039092` | 10（主力空间，库表 ID 都是从这里挖的） |
| `7682603562333552680` | 1 |
| `7469774079734972416` | 1 |
| `7493359288082661391` | 1 |
| `7495957404262121481` | 1（后来又新给的） |

> 注意：`source.spaceId` 这个字段**本身不构成校验**（跨空间也能粘），
> 真正被校验的是**节点里引用的那些资源 ID 在不在目标空间**。

### 生成前的必查动作

1. 问清用户**目标工作流在哪个空间**（或让他从目标工作流复制一个节点出来，读 `source.spaceId`）。
2. 确认 `harvest_ids.py` 挖 ID 用的样本**与目标空间同源**。
3. 若不同源 → **必须重新在目标空间里挖**，否则一定失败。

**不要用"反正都是同一个账号"来自我安慰 —— 空间不同就是不同的资源命名空间。**

---

## 为什么必须挖

这几类 ID **平台侧生成，代码里生不出来**：

| 项 | 在哪 | 粘贴时的行为 |
|---|---|---|
| `databaseInfoID` | 数据库查询/新增/更新节点的 `inputs.databaseInfoList[0]` | **强校验** —— 填错会弹「数据库不存在」 |
| `fieldID` | 数据库节点的 `fieldList[].fieldID` / `conditionList[].left` / `fieldInfo[][0]` | 同上 |
| `datasetList`（知识库 ID） | 知识库检索节点的 `datasetParam` | **强校验** —— 实测报「知识库 FILL_ME_xxx 不存在」，直接阻断导入 |
| `apiID` / `pluginID` | 插件节点的 `apiParam` | 强校验 |
| `workflowId` | 工作流节点的 `inputs` | 强校验（且子工作流必须先发布） |
| `modelType` | 大模型节点的 `llmParam` | 换模型时要实测 |

### ⚠️ 一个实锤教训（2026-09-19 真实翻车）

生成的工作流里知识库 ID 用了 `FILL_ME_flow_kb_id` 占位，粘贴时平台直接弹红条：

```
❌ 知识库 FILL_ME_flow_kb_id,FILL_ME_academic_kb_id不存在
```

**所以：资源类 ID 不能用 `FILL_ME_*` 占位**（那是给"平台不校验的字段"用的）。资源类要么填真值，要么**留空/省略该节点**。

好消息：**同一个空间里的资源 ID 是全局复用的**。你之前已经发布的工作流里，这些 ID 全都在。

## 核心技巧：一行代码把「字段 ID → 字段名」对照表挖出来

> **查询数据节点的 `selectParam.fieldList[]`（字段 ID 数组）与该节点 `outputs[0].schema.schema[]`（字段名数组）是同一顺序。**

两者 `zip` 一下，就得到对照表。这是本技能里最省力的一个发现 —— 不用去画布上一个个点字段看 ID。

```python
flist = [f["fieldID"] for f in node["data"]["inputs"]["selectParam"]["fieldList"]]
names = [x["name"] for x in node["data"]["outputs"][0]["schema"]["schema"]]
field_map = dict(zip(flist, names))     # {1831982593025: 'user_id', ...}
```

> 🔴 **前置断言（2026-09-25 踩坑）**：`selectParam` 里**可能根本没有 `fieldList` 这个键** ——
> 查询节点一个字段都没勾时，平台用「缺键」表示"返回全字段"，不写空数组。
> 此时 `node["data"]["inputs"]["selectParam"]["fieldList"]` 会 `KeyError`。
>
> **收料第一件事**：
> ```python
> sp = node["data"]["inputs"].get("selectParam", {})
> if "fieldList" not in sp or not sp["fieldList"]:
>     raise SystemExit("这份回传没解出字段 ID —— 请让用户重勾任意一个查询字段再复制")
> ```
> 手写生成的 JSON 里也不要补 `"fieldList": []`：**空数组 = 只要 0 个字段**，
> 与"缺键（全字段）"语义相反，粘贴后可能返回空列表。

**前提**：长度必须相等。若不等（说明那次导出丢了字段或 schema 被改过），跳过该节点，用别的节点配。

### ⚠️ 2026-09-21 补正：这个前提**经常不成立**，别默认可用

对 4 份真实画布样本里的 9 个查询数据节点做了统计：

| 节点 | fieldList 项数 | schema 项数 | 同序可用？ |
|---|---|---|---|
| wf_flow_guide 查询档案 | 12 | 12 | ✅ |
| wf_flow_guide 本校精确 / 类型兜底 | 8 / 8 | 8 / 8 | ✅ |
| wf_stage_advance 查询档案 | **6** | **12** | ❌ |
| wf_onboarding 查询档案 | **8** | **9** | ❌ |
| wf_onboarding 学校校验 / 查询选题 / 本校精确 / 类型兜底 | 3/4/8/8 | 3/4/8/8 | ✅ |

**7 个可用、2 个不可用**。长度不等时，`schema` 里塞的可能是**整张表的全部字段**（wf_stage_advance 只选了 6 个，
schema 却写了 12 个），也可能是历史遗留 —— **两种情况下 `zip` 出来的对照表都是错的，且不会报错。**

**正确做法（两层校验）**：

1. **同序 `zip` 只作为初稿**，且必须先断言 `len(fieldList) == len(schema)`；不等就直接跳过。
2. **再拿一份「选了全部字段」的样本交叉验证**。本次就是靠 `wf_flow_guide` 的
   `12/12`（12 个字段全选）独立确认了 `student_profile` 的完整对照表：
   `3025=user_id、3026=nickname、3027=school、1832257632257=school_type、3028=college、3029=major、`
   `3030=degree、3031=topic、3032=advisor、3033=current_stage、3034=created_at、3035=updated_at`
   —— 与 WF-8 自己那张 8 项的 `zip` 结果**逐项吻合**，这才敢批量回填。

> 教训一句话：**「能推算」不等于「推算对了」。** 靠顺序推断出来的映射，必须有一个独立来源对账。

## 现成工具：`scripts/harvest_ids.py`

```bash
# 人类可读报告
python harvest_ids.py 已有工作流1.json 已有工作流2.md ...

# 直接产出可用的 field_map（喂给 build_workflow.py 的规格）
python harvest_ids.py *.json --emit-field-map field_map.json

# 机器可读
python harvest_ids.py *.json --json
```

它会挖出：数据库 ID（附「条件里用过的字段名」帮你认表）、字段 ID→名对照表、写入字段（附引用变量名，帮你反推字段含义）、知识库 ID、插件 apiID/pluginID、子工作流 ID + 其 inputDefs/outputs、模型 modelType。

### 认表方法

光有 `databaseInfoID` 不知道是哪张表。两个线索合起来就能认：

1. **条件里用过的字段名**（`conditionList[].left` 是字段**名**，不是 ID）—— 例如条件用 `user_id` + 输出有 `current_stage` → 是 `student_profile`
2. **写入时的引用变量名**（`fieldInfo[][1]` 的 ref 名）—— 例如 `1831982107652 ← LIT '阶段引导'/'建档'/'阶段变更'` → 那是 `action` 字段

## ⚠️ 字段 ID 是「每张表独立」的

**同一个字段名在不同表里是不同的 ID。**

| 字段名 | student_profile | school_rules | user_progress_log |
|---|---|---|---|
| `school` | `1831982593027` | `1831981827073` | `1831982107649` |
| `school_type` | `1832257632257` | `1832024098817` | — |

### ⚠️⚠️ 更麻烦的是：同一个「字段」在三处的写法还不一样

**别把它们统一** —— 这是平台自己的实现。真实画布样本（`wf_onboarding` 等 4 份）实测：

| 位置 | 写法 | 例子 |
|---|---|---|
| `selectParam.fieldList[].fieldID` | **数字** | `{"fieldID":1832255057921,"isDistinct":false}` |
| `selectParam.conditionList[][].left` | **字段名** | `"content":"school"` |
| `insertParam.fieldInfo[][0]` 的 `fieldID` | **字符串** | `"content":"1831982593026"` |

写错的表现（**不报错、能粘贴**，只在画布上看得见）：
`fieldList` 用字符串 → 「查询字段」整列 `undefined`；`left` 用数字 → 「查询条件」左侧显示裸数字。

校验器 **`E19`** 专守这三条。生成器对应 `_as_field_id_num()`（数字）/ `_as_field_id()`（字符串）/
条件 `left` **原样输出字段名不转换**。

**所以 `field_map` 必须按 `databaseInfoID` 分表**，不能用一张全局表。规格文件里这样写：

```json
{
  "field_map": {
    "7683881920299581483": {"user_id": "1831982593025", "school": "1831982593027"},
    "7683882874499498020": {"school": "1831981827073",  "stage": "1831981827075"}
  }
}
```

`coze_node_lib` 会在处理每个数据库节点前，按它的 `database_id` 自动切到对应那张表的映射。之后规格里就能直接写字段名：

```json
"select": {
  "where": [{"field": "user_id", "op": "EQUAL", "value": "__REF__100001.in_user_id"}],
  "fields": ["user_id", "school", "school_type", "current_stage"],
  "limit": 1
}
```

比满屏数字可读得多，也不容易把两张表的 ID 串了。

## 三种取值的写法（数据库条件里）

字段值既可能是引用、也可能是普通文本，所以需要一个**显式引用哨兵**：

| 写法 | 含义 |
|---|---|
| `"__REF__100001.in_user_id"` | 引用节点 100001 的 `in_user_id` |
| `"通用"` | 纯文本固定值 |
| `"1831982593025"` | 纯数字固定值（当字段本身存数字时） |

**为什么需要 `__REF__`**：如果直接用 `"100001.in_user_id"` 这种简写，会和"字段值本身恰好长得像节点引用"的情况混淆。数据库条件/写入值一律用 `__REF__` 前缀声明引用，最稳。

## 检查清单（生成数据库/知识库节点后逐条过）

- [ ] `databaseInfoID` 是 ≥10 位真实数字，不是 `FILL_ME_*`
- [ ] 每个 `fieldID` 都来自**对应那张表**
- [ ] `datasetList` 里全是真实知识库 ID
- [ ] 子工作流 `workflowId` + `workflowVersion` 都填了，且**该子工作流已发布**
- [ ] 规格里没有 `FILL_ME` 残留 —— 跑 `validate_workflow.py`，`E15` 会逐一列出

`validate_workflow.py` 的 **E15** 规则专门查这个：**资源位出现 `FILL_ME` 一律判 error**（因为粘贴一定失败），而**非资源位**的 `FILL_ME` 只判 warning（因为不影响导入）。

---

## ★★ 还有一类坑：**值的类型** 也必须照抄真实样本

字段 ID 挖对了，**类型写错一样跑不通**。2026-09-21 实测（4 份真实画布样本 vs 生成的文件）：

| 位置 | 真实样本 | 生成的文件（错） |
|---|---|---|
| `开始.outputs` 里 `in_user_id` | `"type":"integer"` | `"type":"string"` |
| 查询条件 `right` | `"type":"integer"` + `ref.rawMeta:{type:2}` | `"type":"string"` + `rawMeta:{type:1}` |
| 写入 `fieldValue` | `"type":"integer"` + `rawMeta:{type:2}` | `"type":"string"` + `rawMeta:{type:1}` |
| `outputs[0].schema` 里 `user_id` | `"type":"integer"` | `"type":"string"` |

**不是「哪个对」的问题，是「同一个值在四个地方必须同类型」** —— 字符串 `"1001"` 去和整数列 `1001` 比，
很可能一条也匹配不上，而且**不报错**。

**怎么查**：找一个**同类真实样本**，看它那个字段在四处分别怎么写。
本项目里 `user_id` 命中整数，是靠 `wf_flow_guide` / `wf_stage_advance` / `wf_onboarding` 三份样本
在四处**全都**写 integer 才敢定的。

**通用口诀**：
> **主键/外键（`*_id`）和时间戳（`*_ts`）先假设是整数，然后去真实样本里核实；**
> **核实不到就保持整条链路写法一致，并在交付说明里点名让用户确认列类型。**


