# 03 · 值对象与类型编码

节点里每一个"参数值"都是同一种结构（`name` + `input` 成对出现）：

```json
{
  "name": "draft_text",
  "input": {
    "type": "string",
    "value": { "type": "ref", "content": { "source": "block-output", "blockID": "100001", "name": "draft_text" }, "rawMeta": { "type": 1 } }
  }
}
```

- `name`：参数名（对输入参数就是该节点上的变量名；对 `apiParam`/`llmParam` 就是平台固定键）
- `input.type`：声明的类型关键字（`string`/`integer`/`float`/`boolean`/`object`/`list`）
- `input.schema`：仅当类型是 `list`/`object` 时出现
- `input.value`：真实取值，只有两种形态

## 两种取值形态 `[实测]`

### 形态 1：固定值 `literal`

```json
{ "type": "literal", "content": <任意 JSON 值>, "rawMeta": { "type": 1 } }
```

`content` 的类型决定怎么写：

| 声明的类型 | `content` 写法 | 例子 |
|---|---|---|
| `string` | 字符串（可含 `\n`、`{{变量}}`） | `"审批通过"` |
| `integer` | **数字或数字字符串都可以** | `10` 或 `"10"` |
| `float` | 数字字符串（样本里常写成字符串） | `"0.5"` |
| `boolean` | 真布尔 | `true` |
| `list` / `object` | 真数组 / 真对象 | `["a","b"]` |

⚠️ **`rawMeta` 可以省略**：实测 486 个 `literal` 中有一批没有 `rawMeta`（数据库条件的 `left`/`operation`、`fieldID`、`datasetList`、`concatParams` 等），平台照样识别。**但为稳妥，生成时一律带上。**

### 形态 2：引用 `ref`

```json
{
  "type": "ref",
  "content": { "source": "block-output", "blockID": "151383", "name": "need_reference" },
  "rawMeta": { "type": 3 }
}
```

| 字段 | 说明 |
|---|---|
| `content.source` | 恒为 `"block-output"`（实测 143/143 全是这个值，**没有别的取值**） |
| `content.blockID` | 被引用的**节点 id**（字符串）。也可指向 loop 内部控制块 id |
| `content.name` | 被引用的**输出变量名** |

**`name` 支持点路径取子字段** `[实测]`：`"outputList.id"`（数据库查询结果取 `id` 列）、`"data.content"`（插件返回体里的字段）。写点路径时 `input.type` 要写成**最终字段的类型**，不是容器类型。

**数组/对象取值要用下标**：在**提示词文本里**引用数组元素写 `{{final_topics[0].title}}` `[实测]`；在 **`ref` 的 `name` 里不要写下标**（用点路径即可）。

## `rawMeta.type` 编码表 `[实测]`

实测统计（`input.type` → `rawMeta.type` 的出现频次）：

| `rawMeta.type` | 含义 | 频次 | 对应的 `input.type` |
|---|---|---|---|
| `1` | string | 278 | `string` |
| `2` | integer | 96 | `integer` |
| `3` | boolean | 93 | `boolean` |
| `4` | float / number | 25 | `float` |
| `6` | object | 3 | `object` |
| `99` | list\<string\> | 13 | `list` + `schema:{type:"string"}` |
| `103` | list\<object\> | 13 | `list` + `schema:{type:"object",…}` |
| （省略） | object | 21 | `object`（**多数 object 不带 rawMeta**）|
| （省略） | list | 4 | `list`（纯字面量数组，如 `datasetList`）|

### 三个必须知道的坑

1. **`99` 和 `103` 不是"数组"，而是"数组+元素类型"。** `99` = 数组里装 string，`103` = 数组里装 object。写错了平台可能按错类型解析。判据看 `input.schema`：`schema.type == "string"` → 99；`schema.type == "object"` → 103。
2. **`100`/`101`/`102` 未被证实。** 网上有说法称它们对应 `array<integer>` / `array<boolean>` / `array<number>`，但**本技能采集的样本里从未出现整数数组/布尔数组**，所以不要照这个规律推算。要用整数数组时，先造一个小节点实测一次。
3. **循环节点的 `outputs` 是特例**：实测 3 个循环节点，其 `outputs[0].input` 都是 `"type":"list"` 但 `rawMeta.type` 写成 **`1`**（string）。这不是笔误，是平台的既有写法（循环输出声明层不严格）。**照抄即可，不要去"修正"它。** 下游引用这个循环输出时，`rawMeta.type` 才写 `99`/`103`。

## `input.schema` 嵌套规则 `[实测]`

**数组**：`schema` 是单对象

```json
{"type":"list","schema":{"type":"string"}}
{"type":"list","schema":{"type":"object","schema":[{"type":"string","name":"documentId"},{"type":"string","name":"output"}]}}
```

**对象**：`schema` 是"字段数组"（注意与上面不同层）

```json
{"type":"object","schema":[
  {"type":"string","name":"title"},
  {"type":"string","name":"difficulty"},
  {"type":"list","name":"tech_stack","schema":{"type":"string"}}
]}
```

**字段项可以带 `required` 和 `description`**（`[实测]`）：

```json
{"type":"string","name":"url","required":false,"description":"link url"}
{"type":"string","name":"label","required":true}
```

`description` 只在两类地方出现：**插件节点输出的 `_temp.externalData.outputs`**、以及**手动补写过的 schema**。开始/结束节点的变量说明则写在 `outputs[]` / `trigger_parameters[]` 项上（见下）。

## 输出声明的两种写法

### 写法 1：数组（绝大多数节点）`[实测]`

```json
"outputs": [
  { "type": "string", "name": "topic_title" },
  { "type": "list",   "name": "core_keywords", "schema": { "type": "string" } },
  { "type": "boolean","name": "need_reference" }
]
```

可带 `required`（样本中插件节点与代码节点常带，大模型节点多数不带）。

### 写法 2：`name` + `input`（循环节点用）`[实测]`

循环节点的输出是"从循环体里某个节点的输出引出来"，所以结构不同：

```json
"outputs": [
  {
    "name": "output_list",
    "input": {
      "type": "list",
      "schema": { "type": "string" },
      "value": { "type": "ref", "content": { "source": "block-output", "blockID": "181101", "name": "output" }, "rawMeta": { "type": 1 } }
    }
  }
]
```

`blockID` 指向**循环体内部**的节点 id。

## 开始节点特有的两个修饰位 `[实测]`

```json
{"type":"string","name":"start_date","required":false,"assistType":10000}
```

| 字段 | 说明 |
|---|---|
| `required` | 是否必填 |
| `assistType` | 实测只见过 `10000`，出现在 `start_date` / `end_date` 上，是**日期选择辅助**（画布上给日期控件）。其他变量不要加 |
| `description` | 变量说明，会显示在画布输入框下方。**建议都写上**，尤其必填项 |

`trigger_parameters` 是 `outputs` 的镜像副本，字段相同（`type`/`name`/`required`/`description`）。实测 7 份样本里 6 份是 `[]`，只有新格式那份填了内容。**建议：填成与 `outputs` 一致，或直接给 `[]`（两种都能用）。**

## 大模型节点专属的值结构

`llmParam` 里的 `parameters` 项不是普通 literal，而是"对象引用占位"：

```json
{
  "name": "parameters",
  "input": {
    "value": { "type": "object_ref" },
    "type": "object",
    "schema": [ { "name": "max_completion_tokens", "input": { "type": "integer", "value": { "type": "literal", "content": "0", "rawMeta": { "type": 2 } } } } ]
  }
}
```

`value.type` 取值 `"object_ref"` —— **这是除 `literal`/`ref` 之外的第三种 `value.type`，实测只在 `llmParam.parameters` 出现过。** 直接照抄，不要改。

## 文本处理节点的 `{{…}}` 模板引用 `[实测]`

`concatParams.concatResult` 里用 `{{参数名.字段}}` 引用**本节点输入参数**：

```json
"content": "大学名称：{{String1.university}}\n学生姓名：{{String1.student_name}}\n研究类型：{{String1.research_type}}"
```

这里的 `String1` 是**本节点的输入参数名**（不是节点 id）。同理，结束节点 `useAnswerContent` 模式的 `content` 里用 `{{final_topics[0].title}}` 引用本节点输入参数。

**注意区分**：`ref` 引用跨节点用 `blockID + name`；`{{…}}` 模板只用于节点内部的文本拼接/话术，不产生 `ref` 结构。
