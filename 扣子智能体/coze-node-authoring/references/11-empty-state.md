# 11 · 空配置态（Empty State）—— 数据不足时的默认做法

> **一句话**：参数不全时，产出**平台原生的空配置态**，不要编内容、也不要填假 ID。
> 空态**能粘**，粘上去由用户在画布上补；假 ID **会被拦**；编的内容会让用户以为能用。

---

## 1. 三种「参数缺失」的处理方式对比

| 做法 | 例子 | 粘贴结果 | 评价 |
|---|---|---|---|
| ✅ **空配置态** | `databaseInfoList: []` | **能粘**（不触发资源校验） | **默认做法** |
| ❌ 填占位 ID | `[{"databaseInfoID": "FILL_ME_profile"}]` | **弹红条阻断导入** | 明确禁止 |
| ❌ 填空 ID 对象 | `[{"databaseInfoID": ""}]` | 平台拿空 ID 查资源 → **失败** | 畸形值，最隐蔽 |
| ❌ 自己编内容 | 编一段提示词 / 意图名 / SQL | 能粘，但**看起来能用其实不能用** | 误导用户 |

**关键判据**：能不能粘，取决于**是否引用了需要校验的资源**。

```
空数组 []            → 没有引用任何资源 → 不校验 → ✅ 能粘
["真实ID"]           → 引用存在         → 校验通过 → ✅ 能粘
["FILL_ME_x"]        → 声称要引用       → 查不到   → ❌ 阻断
[{"id": ""}]         → 声称要引用       → 查不到   → ❌ 阻断
```

---

## 2. 各类型的实测空配置态

以下全部来自**平台自己产出的空节点样本**（2026-09-20），逐值比对通过。

### 2.1 数据库族

```jsonc
// 查询数据 type:"43"   height 138
"inputs": {
  "databaseInfoList": [],
  "selectParam": {"condition": {"logic": "AND"}}      // 没有 conditionList / fieldList / orderByList / limit
}

// 更新数据 type:"42"   height 138
"inputs": {
  "databaseInfoList": [],
  "updateParam": {"condition": {"logic": "AND"}}      // 没有 fieldInfo
}

// 新增数据 type:"46"   height 138
"inputs": {
  "databaseInfoList": []                              // 完全没有 insertParam 键
}

// 删除数据 type:"44"   height 138
"inputs": {
  "databaseInfoList": [],
  "deleteParam": {"condition": {"logic": "AND"}}
}

// SQL自定义 type:"12"  height 138（主色 #FF811A，与其它数据库节点不同）
"inputs": {
  "inputParameters": [],
  "databaseInfoList": []                              // 也没有 sql 文本字段（未证实）
}
```

⚠️ **对比「已配置态」**（同一批节点选了库之后）：

| | 未配置 | 已配置 |
|---|---|---|
| `databaseInfoList` | `[]` | `[{"databaseInfoID": "768…"}]` |
| `condition` | `{"logic": "AND"}` | `{"conditionList": [...], "logic": "AND"}` |
| `selectParam` 额外键 | 无 | `fieldList` / `limit` / `orderByList` |
| `settingOnError` | **不写** | `{processType:1, timeoutMs:60000, retryTimes:0}` |

→ 所以生成器里「空态」和「配置态」是**两条分支**，不是同一套结构填空。

### 2.2 知识库检索 `type:"6"`

```jsonc
"inputs": {
  "datasetParam": [ /* 未配置：7 项；选了知识库：9 项 */ ],
  "inputParameters": [
    {"name": "enableChatHistory", "input": {"type": "boolean",
      "value": {"type": "literal", "content": false, "rawMeta": {"type": 3}}}},
    {"name": "chatHistoryRound",  "input": {"type": "float",
      "value": {"type": "literal", "content": 3, "rawMeta": {"type": 4}}}}
  ]
},
"outputs": [{"type": "list", "name": "outputList",
  "schema": {"type": "object", "schema": [
    {"type": "string", "name": "output"}, {"type": "string", "name": "documentId"}]}}]
```

要点：
- **7 项 vs 9 项**：`minScore`、`strategy` 只在选了知识库后才出现
- `inputParameters` 顺序实测是 **[上游引用…, enableChatHistory, chatHistoryRound]**（开关在**后**）
- `chatHistoryRound` 的 `input.type` 是 `"float"` 而 `content` 是**数字**（不是字符串）—— 照抄
- 默认输出名是 `outputList`（schema 含 `output` + `documentId`），不是自定义名

> 📌 **补充观察（2026-09-20，用户提供的真实样本）**：未配置知识库的节点，在平台上**实际是 8 项** ——
> `datasetList / topK / useRerank / useRewrite / isPersonalOnly / datasetType / VolcanoInfoList / **strategy**`，
> 即**有 `strategy`（值 `"0"`）、没有 `minScore`**。
> 所以真实规则更可能是：
> **未配置 = 8 项（到 `strategy` 为止）｜已配置 = 9 项（多 `minScore`）**，
> 而生成器目前给 7 项（到 `VolcanoInfoList` 为止）。
> **两者都能粘**（已验证），平台在粘贴/交互时会自行补齐 —— 属已知无害差异。
> 要趋近原生就补齐 `strategy`，但不值得为它重跑已验证过的文件。

### 2.3 LLM 族

```jsonc
// 意图识别 type:"22"  height 176（=150+26×1）
"inputs": {
  "chatHistorySetting": {"enableChatHistory": false, "chatHistoryRound": 3},
  "inputParameters": [],
  "intents": [{"name": ""}],                 // 1 条空意图
  "llmParam": { /* 17 键，见 04 */ "prompt": {"…content": "{{query}}"}, "systemPrompt": {"…content": ""} },
  "mode": "top_speed", "version": "2",
  "settingOnError": {"processType":1,"timeoutMs":60000,"retryTimes":0}
}

// 大模型 type:"3"
"llmParam": [ … "prompt": "", "systemPrompt": "" … ]   // 两个提示词都是空串

// 问答 type:"18"
"options": [{"name": ""}, {"name": ""}], "question": "", "answer_type": "text"
```

⚠️ **空态下 `prompt` 与 `inputParameters` 天然「断链」**（平台自己就是 `prompt={{query}}` + 无参数）。
所以校验器的提示词变量检查在**空配置态必须豁免**，否则会对平台自己的样本误报。

---

## 3. 工程实现要点

### 3.1 「省略键」优先于「填空值」

平台的空态**经常是「键不存在」而不是「键为空」**：

| 情况 | 平台写法 |
|---|---|
| 新增数据未配置 | **没有 `insertParam` 键** |
| 结束节点 `2` / 选择器 `8` / 输出节点 `13` | **没有 `outputs` 键** |
| 未配置的数据库节点 | **没有 `settingOnError` 键** |
| 节点无边 | **没有 `edges` 键**（不是 `edges: []`）|

**当不确定时，少写一个键比多写一个键安全**（多写的键可能触发额外的校验或结构不一致）。

### 3.2 校验器的「未配置项」不是错误

`validate_workflow.py` 把这类情况归为 **level `U`（unconfigured）**，单独输出、**不计入 error/warning**：

```
节点 5 个 / 连线 0 条 → error 2，warning 0，未配置项 5
  ℹ️  以下 5 处是「未配置态」（不是问题，粘上后在画布上补配置即可）：
      · type=43(查询数据) id=198104
        查询数据节点未选数据库（databaseInfoList 为空数组）—— 属合法未配置态，粘上后在画布上选库表即可
```

这样用户一眼能区分「**必须改**（error）」「**建议改**（warning）」「**你自己补**（unconfigured）」。

### 3.3 交付话术

不要写「已完成」，要写清**哪些是空态、需要用户做什么**：

> 这份是**骨架版**：29 个节点、36 条连线都在，`XX`/`YY` 等 N 个节点是**空配置态**（未选库表/知识库/无提示词）。
> 粘上后在画布上逐个补即可；需要我填内容的话，把该节点的真实配置复制给我。

---

## 4. 什么时候**可以**填内容（不算编）

| 来源 | 可以照抄吗 |
|---|---|
| 用户明确给的提示词原文 | ✅ |
| 用户文档里写明的意图名 / 参数名 / 模型名 | ✅ |
| 从用户**自己已发布的工作流**里挖出的资源 ID | ✅（见 `09`）|
| 从**同类型真实样本**推出的结构默认值 | ✅（本文件 §2 就是） |
| 自己根据需求"合理想象"的提示词 / SQL / 意图名 | ❌ **不要** |

判据很简单：**能不能指出这段话/这个值是从哪抄来的。** 指不出来，就用空态。
