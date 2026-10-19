# 04 · 13 种节点的最小可运行骨架

每份骨架都是**实测可粘贴**的结构，只是把长文本换成了占位。省略号 `…` 表示"照此处规则填"。

通用外层（所有节点共有，下文骨架里为省篇幅只写 `data` 部分）：

```json
{ "id": "<6位数字字符串>", "type": "<见 02 表>", "meta": { "position": {"x": 0, "y": 0} },
  "data": { "nodeMeta": {...}, "inputs": {...}, "outputs": [...] }, "_temp": {...} }
```

---

## 1. 开始 `type:"1"`

```json
{
  "nodeMeta": {"description":"工作流的起始节点，用于设定启动工作流需要的信息",
    "icon":"…/icon-Start-v2.jpg","subTitle":"","title":"开始"},
  "outputs": [
    {"type":"string","name":"university","required":false,"description":"院校名称"},
    {"type":"string","name":"start_date","required":false,"assistType":10000}
  ],
  "trigger_parameters": []
}
```

要点：**没有 `inputs`、没有 `mainColor`**。`title` 固定 `"开始"`，`subTitle` 是空串。

## 2. 结束 `type:"2"`

### 模式 A：返回变量（默认，7/8 样本都用这个）

```json
{
  "nodeMeta": {"description":"工作流的最终节点，用于返回工作流运行后的结果信息",
    "icon":"…/icon-End-v2.jpg","subTitle":"","title":"结束"},
  "inputs": {
    "terminatePlan": "returnVariables",
    "inputParameters": [
      {"name":"task_book","input":{"type":"list","schema":{"type":"string"},
        "value":{"type":"ref","content":{"source":"block-output","blockID":"113490","name":"output_list"},"rawMeta":{"type":99}}}}
    ]
  }
}
```

### 模式 B：返回话术（`useAnswerContent`，可夹模板）

```json
{
  "inputs": {
    "terminatePlan": "useAnswerContent",
    "streamingOutput": false,
    "inputParameters": [ {"name":"final_topics","input":{"type":"list","schema":{"type":"object","schema":[{"type":"string","name":"title"}]},
        "value":{"type":"ref","content":{"source":"block-output","blockID":"153079","name":"final_topics"},"rawMeta":{"type":103}}}} ],
    "content": {"type":"string","value":{"type":"literal",
      "content":"已为您生成选题：\n1.【{{final_topics[0].title}}】\n2.【{{final_topics[1].title}}】"}}
  }
}
```

要点：`content` **不作为 `inputParameters` 的一项**，而是 `inputs` 的直接子字段。模板里用 `{{变量[下标].字段}}`。

## 3. 大模型 `type:"3"`

```json
{
  "nodeMeta": {"description":"调用大语言模型,使用变量和提示词生成回复",
    "icon":"…/icon-LLM-v2.jpg","mainColor":"#5C62FF","subTitle":"大模型","title":"信息解析大模型"},
  "inputs": {
    "inputParameters": [
      {"name":"university","input":{"type":"string",
        "value":{"type":"ref","content":{"source":"block-output","blockID":"100001","name":"university"},"rawMeta":{"type":1}}}}
    ],
    "llmParam": [
      {"name":"modelType",          "input":{"type":"integer","value":{"type":"literal","content":"1772700462","rawMeta":{"type":2}}}},
      {"name":"modleName",          "input":{"type":"string", "value":{"type":"literal","content":"豆包·2.0·pro","rawMeta":{"type":1}}}},
      {"name":"generationDiversity","input":{"type":"string", "value":{"type":"literal","content":"balance","rawMeta":{"type":1}}}},
      {"name":"frequencyPenalty",   "input":{"type":"float",  "value":{"type":"literal","content":"0","rawMeta":{"type":4}}}},
      {"name":"maxTokens",          "input":{"type":"integer","value":{"type":"literal","content":"4096","rawMeta":{"type":2}}}},
      {"name":"spCurrentTime",      "input":{"type":"boolean","value":{"type":"literal","content":false,"rawMeta":{"type":3}}}},
      {"name":"spAntiLeak",         "input":{"type":"boolean","value":{"type":"literal","content":false,"rawMeta":{"type":3}}}},
      {"name":"responseFormat",     "input":{"type":"integer","value":{"type":"literal","content":"2","rawMeta":{"type":2}}}},
      {"name":"parameters","input":{"value":{"type":"object_ref"},"type":"object","schema":[
        {"name":"max_completion_tokens","input":{"type":"integer","value":{"type":"literal","content":"0","rawMeta":{"type":2}}}}]}},
      {"name":"prompt",             "input":{"type":"string", "value":{"type":"literal","content":"院校：{{university}}\n专业：{{major}}","rawMeta":{"type":1}}}},
      {"name":"enableChatHistory",  "input":{"type":"boolean","value":{"type":"literal","content":false,"rawMeta":{"type":3}}}},
      {"name":"chatHistoryRound",   "input":{"type":"integer","value":{"type":"literal","content":"3","rawMeta":{"type":2}}}},
      {"name":"systemPrompt",       "input":{"type":"string", "value":{"type":"literal","content":"你是…\n严格以 JSON 格式输出。","rawMeta":{"type":1}}}},
      {"name":"stableSystemPrompt", "input":{"type":"string", "value":{"type":"literal","content":"","rawMeta":{"type":1}}}},
      {"name":"canContinue",        "input":{"type":"boolean","value":{"type":"literal","content":false,"rawMeta":{"type":3}}}},
      {"name":"loopPromptVersion",  "input":{"type":"string", "value":{"type":"literal","content":"","rawMeta":{"type":1}}}},
      {"name":"loopPromptName",     "input":{"type":"string", "value":{"type":"literal","content":"","rawMeta":{"type":1}}}},
      {"name":"loopPromptId",       "input":{"type":"string", "value":{"type":"literal","content":"","rawMeta":{"type":1}}}}
    ],
    "fcParamVar": {"knowledgeFCParam": {}},
    "settingOnError": {"processType":1,"timeoutMs":180000,"retryTimes":0}
  },
  "outputs": [
    {"type":"string","name":"topic_title"},
    {"type":"list","name":"core_keywords","schema":{"type":"string"}},
    {"type":"boolean","name":"need_reference"}
  ],
  "version": "3"
}
```

要点：
- **`llmParam` 必须凑齐这 18 项**（实测键名一致、顺序也一致；生成器 `_llm_param()` 输出的就是这 18 个）。
  缺项未必报错，但补齐最稳。
  > 📌 勘误（2026-09-20）：本节曾写「19 项」，但下面列出的键实际是 **18 个**，
  > 且 `coze_node_lib.py` 生成结果经复核也是 18 个。以 18 为准。
- **`modleName` 是平台的拼写错误**，不要改成 `modelName`。
- `prompt` 是用户提示词，`systemPrompt` 是系统提示词，两者都用 `{{变量名}}` 引用 `inputParameters` 里的名字。
- `outputs` 里若声明 `boolean`/`list` 等非字符串类型，需要提示词明确"严格 JSON 输出"配合。
- `reasoning_content` 是平台自动回填的思考链输出，**不要自己声明**。

**常见模型的 `modelType`（实测值）**：`豆包·2.0·pro` → `"1772700462"`。换模型时**必须实测**（在画布上选一次模型再复制出来看）。

## 4. 插件 `type:"4"`

```json
{
  "nodeMeta": {"description":"搜索用户询问的内容","icon":"…/icon-Plugin-v2.jpg",
    "subtitle":"头条搜索:search","title":"规范检索"},
  "inputs": {
    "apiParam": [
      {"name":"apiID",        "input":{"type":"string","value":{"content":"7372463719307296795","rawMeta":{"type":1},"type":"literal"}}},
      {"name":"apiName",      "input":{"type":"string","value":{"content":"search","rawMeta":{"type":1},"type":"literal"}}},
      {"name":"pluginID",     "input":{"type":"string","value":{"content":"7372463719307264027","rawMeta":{"type":1},"type":"literal"}}},
      {"name":"pluginName",   "input":{"type":"string","value":{"content":"头条搜索","rawMeta":{"type":1},"type":"literal"}}},
      {"name":"pluginVersion","input":{"type":"string","value":{"content":"","rawMeta":{"type":1},"type":"literal"}}},
      {"name":"tips",         "input":{"type":"string","value":{"content":"","rawMeta":{"type":1},"type":"literal"}}},
      {"name":"outDocLink",   "input":{"type":"string","value":{"content":"","rawMeta":{"type":1},"type":"literal"}}}
    ],
    "inputParameters": [
      {"name":"count",       "input":{"type":"integer","value":{"type":"literal","content":10,"rawMeta":{"type":2}}}},
      {"name":"cursor",      "input":{"type":"integer","value":{"type":"literal","content":0,"rawMeta":{"type":2}}}},
      {"name":"input_query", "input":{"type":"string","value":{"type":"ref","content":{"source":"block-output","blockID":"151383","name":"school"},"rawMeta":{"type":1}}}}
    ],
    "settingOnError": {"processType":1,"timeoutMs":180000,"retryTimes":0}
  },
  "outputs": [
    {"type":"boolean","name":"ok","required":false},
    {"type":"integer","name":"code","required":false},
    {"type":"object","name":"data","required":false,"schema":[
      {"type":"integer","name":"cursor","required":false},
      {"type":"list","name":"doc_results","required":false,"schema":{"type":"object","schema":[
        {"type":"string","name":"sitename","required":false,"description":"the site name which url belongs to"},
        {"type":"string","name":"summary","required":false,"description":"the summary of the url content"},
        {"type":"string","name":"title","required":false,"description":"title of the url content"},
        {"type":"string","name":"url","required":false,"description":"link url"}]}},
      {"type":"boolean","name":"has_more","required":false},
      {"type":"string","name":"search_id","required":false}]},
    {"type":"integer","name":"errcode","required":false},
    {"type":"string","name":"errmsg","required":false},
    {"type":"string","name":"log_id","required":false}
  ]
}
```

要点：
- **`nodeMeta` 用全小写 `subtitle`**，值是 `插件名:API名`。
- **`apiParam` 固定 7 项**（实测 3/3 一致）。`pluginVersion`/`tips`/`outDocLink` 常为空串，但要在。
- **`inputParameters` 的项必须和该插件 API 的入参名一致** —— 名字不对平台会报参数缺失。可靠做法：在画布上插入该插件节点，复制出来当模板，只改引用。
- `_temp.externalData` 里会冗余存一份完整 `inputs`/`outputs`/`pluginID` 等，粘贴时可省略，但保留更稳。

## 5. 代码 `type:"5"`

```json
{
  "nodeMeta": {"description":"编写代码，处理输入变量来生成返回值","icon":"…/icon-Code-v2.jpg",
    "mainColor":"#00B2B2","subTitle":"代码","title":"格式校验"},
  "inputs": {
    "inputParameters": [
      {"name":"task_book","input":{"type":"object","schema":[],
        "value":{"type":"ref","content":{"source":"block-output","blockID":"147662","name":"task_book"},"rawMeta":{"type":6}}}}
    ],
    "code": "def main(task_book: dict) -> dict:\n    required = [\"选题依据\", \"研究内容\"]\n    modules = task_book.get(\"modules\", [])\n    names = [m.get(\"module\", \"\") for m in modules]\n    missing = [r for r in required if r not in names]\n    return {\"is_valid\": not missing, \"missing_modules\": missing}",
    "language": 3,
    "settingOnError": {"processType":1,"timeoutMs":60000,"retryTimes":0}
  },
  "outputs": [
    {"type":"boolean","name":"is_valid"},
    {"type":"list","name":"missing_modules","schema":{"type":"string"}},
    {"type":"string","name":"check_report"}
  ],
  "version": "v2"
}
```

要点：
- **`language: 3` = Python**（实测 4/4）。JavaScript 的取值未证实，别猜。
- `code` 是**带 `\n` 转义的单一字符串**，不是数组。
- `data.version: "v2"`（字符串）。
- 详细写码规则见 `06-code-node-python.md`。

## 6. 知识库检索 `type:"6"`

```json
{
  "nodeMeta": {"description":"在选定的知识中,根据输入变量召回最匹配的信息,并以列表形式返回",
    "icon":"…","mainColor":"#5C62FF","subTitle":"知识库检索","title":"知识库检索"},
  "outputs": [
    {"type":"list","name":"outputList","schema":{"type":"object","schema":[
      {"type":"string","name":"output"},{"type":"string","name":"documentId"}]}}
  ],
  "inputs": {
    "datasetParam": [
      {"name":"datasetList","input":{"type":"list","schema":{"type":"string"},
        "value":{"type":"literal","content":["7685909060688723987","7685909060689018899"]}}},
      {"name":"topK",        "input":{"type":"integer","value":{"type":"literal","content":"5","rawMeta":{"type":2}}}},
      {"name":"useRerank",   "input":{"type":"boolean","value":{"type":"literal","content":true,"rawMeta":{"type":3}}}},
      {"name":"useRewrite",  "input":{"type":"boolean","value":{"type":"literal","content":true,"rawMeta":{"type":3}}}},
      {"name":"isPersonalOnly","input":{"type":"boolean","value":{"type":"literal","content":true,"rawMeta":{"type":3}}}},
      {"name":"datasetType", "input":{"type":"integer","value":{"type":"literal","content":"0","rawMeta":{"type":2}}}},
      {"name":"VolcanoInfoList","input":{"type":"list","schema":{"type":"object","schema":[
        {"type":"string","name":"datasetID"},{"type":"string","name":"volcanoServiceID"}]},
        "value":{"type":"literal","content":[]}}},
      {"name":"minScore",    "input":{"type":"float","value":{"type":"literal","content":"0.5","rawMeta":{"type":4}}}},
      {"name":"strategy",    "input":{"type":"integer","value":{"type":"literal","content":"1","rawMeta":{"type":2}}}}
    ],
    "inputParameters": [
      {"name":"Query","input":{"type":"string","value":{"type":"ref","content":{"source":"block-output","blockID":"100001","name":"event_info"},"rawMeta":{"type":1}}}},
      {"name":"enableChatHistory","input":{"type":"boolean","value":{"type":"literal","content":false,"rawMeta":{"type":3}}}},
      {"name":"chatHistoryRound","input":{"type":"float","value":{"type":"literal","content":3,"rawMeta":{"type":4}}}}
    ]
  }
}
```

要点：
- **`datasetParam` 固定 9 项**（实测 2/2 一致）。`datasetList` 里填知识库 ID 数组 —— 这些 ID 只能从画布上选一次知识库再复制出来拿，**无法凭空生成**。
- 查询变量名固定叫 **`Query`**（大写 Q）。
- **`outputList` 是数组**，取值要写 `{{节点.outputList}}`，在 LLM 提示词里若要取第一条要写 `[0]`。
- 实测没有 `settingOnError` 子字段（其他节点多数有）。

## 7. 选择器 `type:"8"`

```json
{
  "nodeMeta": {"description":"连接多个下游分支，若设定的条件成立则仅运行对应的分支，若均不成立则只运行“否则”分支",
    "icon":"…/icon-Condition-v2.jpg","mainColor":"#00B2B2","subTitle":"选择器","title":"选择器"},
  "inputs": {
    "branches": [
      {"condition": {"logic": 2, "conditions": [
        {"operator": 1,
         "left":  {"input":{"type":"boolean","value":{"type":"ref","content":{"source":"block-output","blockID":"151383","name":"need_reference"},"rawMeta":{"type":3}}}},
         "right": {"input":{"type":"boolean","value":{"type":"literal","content":true,"rawMeta":{"type":3}}}}}
      ]}}
    ]
  }
}
```

要点：
- **没有 `outputs`**（分支由 `edges` 的端口表达）。
- `logic`：实测全部为 `2`，语义未证实（疑似"且"）。若要"或"，**必须实测**。
- `operator`：实测 `1`（5 次，字符串与布尔比较都用它）→ **`1` = 等于**；`7`（1 次，字符串比较）→ 语义未证实。
- 每个 `conditions[i]` 固定三键：`operator` / `left` / `right`。
- **`else` 分支不写在 `branches` 里**，而是靠 `edges` 里"没有 `sourcePortID` 的那条边"表达（即 `sourcePortID` 缺省 = 否则分支）。见 `05-edges-and-ports.md`。
- 多个分支就在 `branches` 数组里追加对象，**顺序即优先级**。

## 8. 文本处理 `type:"15"`

```json
{
  "nodeMeta": {"description":"用于处理多个字符串类型变量的格式","icon":"…/icon-StrConcat-v2.jpg",
    "mainColor":"#3071F2","subTitle":"文本处理","title":"header文本处理"},
  "inputs": {
    "method": "concat",
    "inputParameters": [
      {"name":"String1","input":{"type":"object","schema":[
        {"type":"string","name":"university"},{"type":"string","name":"student_name"}],
        "value":{"type":"ref","content":{"source":"block-output","blockID":"113490","name":"header"},"rawMeta":{"type":6}}}}
    ],
    "concatParams": [
      {"name":"concatResult","input":{"type":"string","value":{"type":"literal",
        "content":"大学名称：{{String1.university}}\n学生姓名：{{String1.student_name}}","rawMeta":{"type":1}}}},
      {"name":"arrayItemConcatChar","input":{"type":"string","value":{"type":"literal","content":"，","rawMeta":{"type":1}}}},
      {"name":"allArrayItemConcatChars","input":{"type":"list","schema":{"type":"object","schema":[
        {"type":"string","name":"label","required":true},{"type":"string","name":"value","required":true},{"type":"boolean","name":"isDefault","required":true}]},
        "value":{"type":"literal","content":[
          {"isDefault":true,"label":"换行","value":"\n"},
          {"isDefault":true,"label":"制表符","value":"\t"},
          {"isDefault":true,"label":"句号","value":"。"},
          {"isDefault":true,"label":"逗号","value":"，"},
          {"isDefault":true,"label":"分号","value":"；"}]}}}
    ]
  }
}
```

要点：
- 输入参数名是**平台固定的 `String1` `String2`…**（不是自定义名）。
- `concatResult` 里用 `{{String1.字段}}` 引用。
- `method` 实测只见过 `"concat"`；**其他 method 取值未证实**（文本处理节点还有替换/截取等模式，但样本没有）。要用别的模式，从画布复制。
- **该节点未见 `outputs` 字段**（输出名由 `method` 决定，实测此例输出叫 `output`）。引用它时用 `{{节点.output}}`。

## 9. 工作流（子工作流）`type:"9"`

```json
{
  "nodeMeta": {
    "description": "输入「学校 + 学院 + 专业 + 学校类型」，用三级回退查出该专业的毕设进程节点，并算出「当前节点 / 下一个节点 / 距结束还有几天 / 是否逾期」。",
    "icon": "…/icon-Workflow-v2.jpg",
    "isImageflow": false,
    "title": "里程碑查询"
  },
  "inputs": {
    "inputDefs": [
      {"input": {}, "name": "in_school",      "required": true,  "type": "string"},
      {"input": {}, "name": "in_college",     "required": false, "type": "string"},
      {"input": {}, "name": "in_major",       "required": true,  "type": "string"},
      {"input": {}, "name": "in_school_type", "required": true,  "type": "string"},
      {"input": {}, "name": "in_now_ts",      "required": true,  "type": "integer"}
    ],
    "inputParameters": [
      {"name": "in_school",  "input": {"type": "string",
        "value": {"type": "ref", "content": {"source": "block-output", "blockID": "100003", "name": "v_school"}, "rawMeta": {"type": 1}}}},
      {"name": "in_now_ts",  "input": {"type": "integer",
        "value": {"type": "ref", "content": {"source": "block-output", "blockID": "100001", "name": "in_now_ts"}, "rawMeta": {"type": 2}}}}
    ],
    "settingOnError": {},
    "spaceId": "7493357645614039092",
    "type": 0,
    "workflowId": "7684899404600164358",
    "workflowVersion": "v0.0.3"
  },
  "outputs": [
    {"type": "list",    "name": "ms_list",     "schema": {"type": "object", "schema": []}, "required": false},
    {"type": "string",  "name": "ms_source",   "required": false},
    {"type": "boolean", "name": "ms_found",    "required": false},
    {"type": "string",  "name": "current_task","required": false},
    {"type": "string",  "name": "next_task",   "required": false},
    {"type": "integer", "name": "days_left",   "required": false},
    {"type": "boolean", "name": "is_overdue",  "required": false},
    {"type": "string",  "name": "out_message", "required": false},
    {"type": "string",  "name": "out_status",  "required": false}
  ]
}
```

要点（全部 `[实测]`，4/4 实例一致）：
- **`inputs` 里有两套变量**：`inputDefs[]` 是**子工作流的入参声明**（`{input:{}, name, required, type}`，顺序即子工作流的定义顺序），`inputParameters[]` 是**本次调用实际传的值**。两套的名字必须对应，一个都不能少、不能多。
- **`outputs` 是子工作流结束节点暴露的输出**（`{type, name, required:false}`）。**官方文档明确说子工作流必须先发布**，否则调用方在画布上选不到它。
- `settingOnError` 是**空对象 `{}`**（不是 `{processType:1,...}`），照抄。
- `type` 字段（在 `inputs` 里）实测为 `0`；`isImageflow` 在 `nodeMeta` 里，实测 `false`。
- **`nodeMeta` 没有 `subTitle`、没有 `mainColor`** —— 这是它和别的节点最大的外观差异。
- **`_temp.externalData` 缓存了子工作流的元数据**（`workflow_id`、`flow_version`、`inputsDefinition`、`creator`、`plugin_id`、`mainColor:"#00B83E"` 等）。缺失不影响运行（平台会按 `workflowId` 重新拉），但补齐更接近原生。
- **`title` 默认是子工作流的函数名**（如 `wf_milestone_get`），也可以改成中文（实测两种都有）。

### ⚠️ 最容易踩的坑：下游引用的输出名对不上

工作流节点的输出名 **= 子工作流结束节点的输出名**，不是你在调用方文档里随手起的名字。

真实翻车现场（本次实测）：

```
文档里写的 N05 输出：ms_out_list / ms_out_source / ms_out_current_task / ms_out_days_left …
wf_milestone_get v0.0.3 真实输出：ms_list / ms_source / current_task / days_left …
                                  ↑ 没有 ms_out_ 前缀
```

若按文档的名字写下游引用，**整条链路的变量引用全部失效**，而且不是保存时报错，是**运行时才炸**。

**做法**：拿到子工作流的「结束节点」输出名之后，先把它们抄到调用方节点的 `outputs` 里，再写下游引用。`validate_workflow.py` 的 E5 规则能查出这类断链。

## 10. 循环 `type:"21"`

```json
{
  "meta": {"position":{"x":1019,"y":-112},"canvasPosition":{"x":1128.65,"y":297.18}},
  "data": {
    "inputs": {
      "inputParameters": [
        {"name":"input","input":{"type":"list","schema":{"type":"string"},
          "value":{"type":"ref","content":{"source":"block-output","blockID":"171354","name":"paragraphs"},"rawMeta":{"type":99}}}}
      ],
      "loopCount": {"type":"integer","value":{"type":"literal","content":10,"rawMeta":{"type":2}}},
      "loopType": "array",
      "variableParameters": []
    },
    "nodeMeta": {"description":"用于通过设定循环次数和逻辑，重复执行一系列任务","icon":"…/icon-Loop-v2.jpg",
      "mainColor":"#00B2B2","subTitle":"循环","title":"循环"},
    "outputs": [
      {"name":"output","input":{"type":"list","schema":{"type":"string"},
        "value":{"type":"ref","content":{"source":"block-output","blockID":"197010","name":"output"},"rawMeta":{"type":1}}}}
    ]
  },
  "blocks": [
    { "id":"197010", "type":"3", "meta":{"position":{"x":0,"y":100}}, "data": { "…循环体里的节点…":"" } }
  ],
  "edges": [
    {"sourceNodeID":"161640","targetNodeID":"197010","sourcePortID":"loop-function-inline-output"},
    {"sourceNodeID":"197010","targetNodeID":"161640","targetPortID":"loop-function-inline-input"}
  ]
}
```

要点（循环是全套里结构最特殊的）：
- **循环体节点不是平级的 `nodes`，而是循环节点自己的顶层 `blocks` 数组**；循环体内的连线是循环节点自己的顶层 `edges`。
- 循环体里的节点 `id` 必须全局唯一，`meta.position` 是**相对坐标**（用 `x:0, y:100` 这种小值）。
- `edges` 用**三个特殊端口名**连接内与外：
  - `sourcePortID: "loop-function-inline-output"` —— 从循环节点进入循环体
  - `targetPortID: "loop-function-inline-input"` —— 从循环体回到循环节点
- `loopType` 实测 `"array"`（遍历数组）。另有"指定次数"模式，**取值未证实**。
- `loopCount` 在 array 模式下仍存在（实测为 `10`），照抄。
- **`outputs` 里 `rawMeta.type` 写 `1`**（见 `03` 的特例说明），而下游引用它时写 `99`。
- 循环节点对外的输出**只能来自循环体里某个节点**，通过 `outputs[].input.value.content.blockID` 指定。
- ⚠️ **循环体内部引用"循环变量"时，`blockID` 写循环节点自己的 id，`name` 取它的 `inputParameters` 名**（不是 `outputs` 名）。这是合法的、也是最容易误判的一条：

  ```json
  // 循环 113490 的 inputParameters = header / task_book / module（都是 list）
  // 循环体内的文本处理节点可以这样引用当前元素：
  {"type":"ref","content":{"source":"block-output","blockID":"113490","name":"header"}}
  ```

  多个 `inputParameters` 时表示**并行遍历多个数组**（`header`、`task_book`、`module` 各取当前项）。

**规格写法**（`build_workflow.py` 的字段名，2026-09-20 实测补齐 —— 这块以前是缺口）：

```jsonc
{
  "id": "100008", "type": "批处理", "title": "批量写里程碑",
  "inputs": {"input": "100007.v_stages"},   // 被遍历的数组，名字可自定义
  "outputs": [],                             // 批处理恒为空数组
  "inner_edges": [                           // ⚠️ 子画布的连线写在这里，不是 "edges"
    ["100008", "100081", "loop-function-inline-output"],      // 进入子画布
    ["100081", "100008", null, "loop-function-inline-input"]  // 回到本节点
  ],
  "blocks": [ {"id": "100081", "type": "新增数据", "title": "写里程碑"} ]
}
```

- ⚠️ **`inner_edges` 不是 `edges`**。在节点规格里写 `"edges"` 会被当成未知 kwarg 传下去、静默丢弃，
  结果子画布一条线都没有。
- ⚠️ 子画布**只有 1 个节点时也必须写这两条 inline 线** —— 它们不是业务连线，是平台的内外通道。
  漏了 `validate_workflow.py` 会报 `W11`。
- ⚠️ 顶层 `edges` 里连向下游时必须带出口端口：`["100008","100010","batch-output"]`
  （循环是 `"loop-output"`）。不带 → 也报 `W11`。
- 子画布节点 `id` 全局唯一，`meta.position` 是相对坐标。

### 10.4.1 画布上「循环节点 → 输出」那一栏怎么填（实测 UI 语义，2026-09-22）

循环节点的输出面板是**三列**，含义容易搞反：

| 列 | 填什么 | 说明 |
|---|---|---|
| **变量名** | 自己起个名，如 `items` | **下游就用这个名字引用**（`{{循环节点.items}}`）。留空 = 循环没有对外输出，下游会显示红字「未定义」 |
| **变量值** | 点「引用参数值」→ 选**循环体内某个节点的输出** | 例如 `组装单行数据 · v_is_overdue` |
| **变量类型** | **不用手填** | 有个默认占位 `str.`；选完变量值后会自动变成实际类型 |

**关键语义：循环会替你收集数组。** 你只引用「**每一轮的那一个值**」（标量，如一个 Boolean），
循环节点自动把它收集成 `Array<T>`：

```
循环体跑 3 轮，每轮产出 v_is_overdue = false / true / false
        ↓ 循环自动收集
循环输出 items（Array<Boolean>）= [false, true, false]
```

所以**不要**为了「要数组」而把体内节点的输出类型声明成 `Array<Object>`。

#### ⚠️ 陷阱：输出选成数组型变量 → 「数组套数组」→ 统计全错

如果循环输出引用的是一个 `Array<Object>` 变量（例如体内代码节点把行数据声明成 `Array<Object>`），
`items` 会变成 **`[[row],[row],…]`**（数组套数组）。此时下游那种「宽容型」判断

```python
for it in items:
    if isinstance(it, dict):
        if it.get('v_is_overdue'): overdue += 1
    elif it:                      # ← 非空 list 为真
        overdue += 1
```

每轮都走 `elif it` 分支 → **逾期数 = 总人数**，预警永远误报。
（`len(items)` 恰好还是对的，所以「总数对、逾期数恒等于总数」是它的典型症状。）

**结论**：循环输出优先选**标量**（Boolean / String / Integer），让循环去收数组。
体内节点「一行数据」这类对象**声明成 `Object`，不是 `Array<Object>`**。

#### 填完之后自检两步

1. 循环输出的「变量类型」是否已从「暂无数据」变成 `Array<Boolean>`（或对应的 `Array<T>`）；
2. 下游节点的入参是否从红字「未定义」变成 `{{循环节点.items}}`。

## 10.5 ⚠️ 哪些节点**不写** `outputs` 键（13/13 实测）

`outputs` 键**不是每个节点都有**。写错方向都会被平台判定结构异常：

| type | 类型 | `outputs` 键 | 样本数 |
|---|---|---|---|
| `"2"` | **结束** | **从不写**（输出定义挂在 `inputs.inputParameters` 上） | 13/13 无 |
| `"8"` | **选择器** | **从不写** | 12/12 无 |
| 其余全部 | 开始/大模型/插件/代码/知识库/工作流/文本处理/循环/批处理/变量聚合/问答/意图识别/数据库五兄弟/JSON 互转 | **总是写** | 全部有 |

```jsonc
// ✅ 结束节点正确形态
{ "id": "900001", "type": "2",
  "meta": {"position": {...}},
  "data": { "nodeMeta": {...}, "inputs": {"terminatePlan": "returnVariables", "inputParameters": [...]} },
  "_temp": {...} }
//                        ↑ 没有 outputs
```

> `build_workflow.py` 的 `_outputs_of()` 里对 `t in ("2","8")` 直接返回 `None`，就是这个原因。

## 11. 变量聚合 `type:"32"`

```json
{
  "data": {
    "inputs": {
      "mergeGroups": [
        {"name":"Group1","variables":[
          {"type":"list","schema":{"type":"string"},
           "value":{"type":"ref","content":{"source":"block-output","blockID":"161640","name":"output"},"rawMeta":{"type":99}}}
        ]}
      ]
    },
    "nodeMeta": {"description":"对多个分支的输出进行聚合处理","icon":"…/VariableMerge-icon.jpg",
      "mainColor":"#00B2B2","subTitle":"变量聚合","title":"变量聚合"},
    "outputs": [ {"type":"list","name":"Group1","schema":{"type":"string"}} ]
  }
}
```

要点：
- **输出变量名固定 `Group1`**（多分组递增 `Group2`、`Group3`）。
- **同一个组内所有变量的类型必须一致**；String 与 Object 要分两个组（分组建两个 `mergeGroups` 项）。
- **组名 `name` 同时就是输出变量名**：组叫 `Group1` → 下游写 `{{本节点id}}.Group1`；组叫 `v_message` → 下游写 `.v_message`。**平台没有单独的「重命名」字段**（实测：`Group1`→`Group1`、`v_message`→`v_message`、`out_tip`→`out_tip`）。
- ✅ **可以引用「不同分支」上的节点** —— 这正是变量聚合的用途。实测两处：
  - `wf_flow_guide` 的聚合节点同时引用 `150799`（主路径）和 `152208`（选择器 `122780` 的 `false` 分支）
  - `wf_stage_advance` 的 `out_tip` 组同时引用 `146039`（选择器 `147780` 的 `false` 分支）和 `104837`（另一条路径）
- ✅ **同一个组里放多个「同名变量」是平台自己的用法**（不是错误）：`wf_stage_advance` 的 `out_tip` 组里有两个都叫 `tip_text` 的变量（blockID 不同），`out_milestone` 组里有两个 `ms_obj`。
  **所以「4 条大模型分支各产出一个 `llm_answer`，全部塞进同一组」是合法且推荐的写法**，不需要拆成 4 个组。
- 取值语义：组内按顺序取**第一个非空值**（所以未走到的分支留空即被跳过）。
- 平台行为：**取多路分支中第一个非空值** → 所以主分支要排在数组前面。
- 有任一分支未运行 → 该分支读到空值 → 会导致工作流报错。所以下游**必须经聚合节点引用**，不要直接引用分支内部变量。
- 该节点没有 `meta` 之外的特殊字段，也没有 `version`。

## 12–14. 数据库三兄弟 `type:"42"/"43"/"46"`

三者共用：

```json
"inputs": {
  "databaseInfoList": [ {"databaseInfoID": "7685905538483322930"} ],
  "settingOnError": {"processType":1,"timeoutMs":60000,"retryTimes":0},
  "<selectParam|insertParam|updateParam>": { ... }
}
```

### 查询数据 `type:"43"`

```json
"selectParam": {
  "condition": {
    "conditionList": [[
      {"name":"left",     "input":{"type":"string","value":{"type":"literal","content":"review_status"}}},
      {"name":"operation","input":{"type":"string","value":{"type":"literal","content":"EQUAL"}}},
      {"name":"right",    "input":{"type":"string","value":{"type":"literal","content":"draft","rawMeta":{"type":1}}}}
    ]],
    "logic": "AND"
  },
  "fieldList": [
    {"fieldID":102,"isDistinct":false},
    {"fieldID":1832469130241,"isDistinct":false}
  ],
  "limit": 1,
  "orderByList": [ {"fieldID":103,"isAsc":false} ]
},
"outputs": [
  {"type":"list","name":"outputList","schema":{"type":"object","schema":[
    {"type":"integer","name":"id"},
    {"type":"string","name":"content_title"},
    {"type":"string","name":"review_status"},
    {"type":"string","assistType":10000,"name":"bstudio_create_time"}]}},
  {"type":"integer","name":"rowNum"}
]
```

- `conditionList` 是**二维数组**：外层是 OR 组，内层每组的三个对象是 `left` / `operation` / `right`；组间用 `logic`（实测 `"AND"`）串联。
- `operation` 已证实取值 **`"EQUAL"` 与 `"LIKE"`**（2026-09-21 补充：真实样本 `wf_flow_guide` 的
  「本校精确」用 `school EQUAL` + `stage LIKE`，共统计 13 个 EQUAL / 2 个 LIKE）。
  ⚠️ **官方文档（`open/docs/guides/database_select_node`）明文列出 8 个运算符**：
  等于 / 不等于(`!=`,`<>`) / 模糊匹配(`LIKE`) / 模糊不匹配(`NOT LIKE`) / **包含(`IN`)** /
  不包含(`NOT IN`) / 为空(`IS NULL`) / 不为空(`IS NOT NULL`)。
  **确实没有区间比较（`> >= < <= BETWEEN`）** —— 时间区间查询只能「拉全量 + 代码过滤」。
  ⚠️ 除 `EQUAL` / `LIKE` 外的 6 个，**枚举字符串仍未从真实样本拿到**，要用时先在画布上配一次再复制出来核对。
  🔴 **2026-09-25 更正**：早期本文件与 SKILL.md 都断言过「平台没有 IN / 包含于」，**该说法是错的**，
  导致下游把 `fingerprint IN [...]` 无谓地退化成逐条查。**凡是「平台不支持 X」都必须有官方文档或实测证据。**
  ⚠️ `LIKE` 的右侧**直接传值/引用，不要自己手写 `%`** —— 平台会自动在前后补 `%`（真实样本里没有 `%`）。
  ⚠️ 用 `LIKE` 还是 `EQUAL` 要看列的取值习惯：像 `stage` 这种「表里可能存『中期检查』而代码归一化成『中期』」
  的列，用 `LIKE` 才不会漏匹配。
- 条件里的 `left` / `operation` 是**纯字面量且不带 `rawMeta`**，只有 `right` 带 —— 照抄。
- ⚠️⚠️ **`left` 写的是「字段名」，不是字段 ID** —— 见下面的三种写法对照表。
- `fieldID` 是**数据库里的字段数字 ID**（**数字**，不是字符串），只能从画布上配一次再复制出来，**无法凭空生成**。
- 输出 `outputList` 是数组（即使 `limit: 1`），取值要 `{{节点.outputList}}`，LLM 里当文本用时写 `{{节点.outputList}}[0]` 或点路径 `{{节点.outputList.字段}}`。
- 实测 `assistType: 10000` 也会出现在数据库输出字段上（时间字段）。

### ★★ 数据库字段的「三种写法」—— 长得像、但三种都不一样

**这是最容易批量写错的一处**（实测踩过：整个 WF-8 的 4 个查询节点全部写反，画布上表现为
「查询字段」整列 `undefined`、「查询条件」左侧显示裸数字）。

**证据**：真实画布采集样本 `wf_onboarding` / `wf_flow_guide` / `wf_review_start` / `wf_stage_advance`。

| 位置 | 正确形态 | 真实样本 |
|---|---|---|
| `selectParam.fieldList[].fieldID` | **数字** | `{"fieldID":1832255057921,"isDistinct":false}` |
| `selectParam.orderByList[].fieldID` | **数字** | 同上 |
| `selectParam.conditionList[][].left` 的 `content` | **字段名**（字符串） | `{"name":"left","input":{"type":"string","value":{"type":"literal","content":"school"}}}` |
| `insertParam.fieldInfo[][0]` 的 `fieldID` | **字符串** | `{"name":"fieldID","input":{"type":"string","value":{"type":"literal","content":"1831982593026"}}}` |
| `updateParam` / `deleteParam` 的 `left` | **字段名**（同 select） | — |

**写错的表现（都不报错、也能粘贴，所以只能静态查）**：

- `fieldList` 的 `fieldID` 写成字符串 → 画布「查询字段」那一栏**整列显示 `undefined`**
- `conditionList` 的 `left` 写成数字 ID → 画布「查询条件」左侧**显示裸数字**而不是字段名
- 反过来（`insertParam` 的 `fieldID` 写成数字）→ 目前只见 warning，但真实样本是字符串，**照抄字符串**

**生成器**：`coze_node_lib` 里分别对应 `_as_field_id_num()`（fieldList/orderByList，返回 int）
与 `_as_field_id()`（fieldInfo，返回 str）；条件的 `left` **直接原样输出字段名**，不转换。
校验器 **`E19`** 专守这三条。

> ⚠️ 别把这三处「统一」成一种写法 —— 它们**故意不一样**，这是平台自己的实现。
> 以真实样本为准，不要凭「一致性」的直觉改。


### 新增数据 `type:"46"`

```json
"insertParam": {
  "fieldInfo": [
    [ {"name":"fieldID",  "input":{"type":"string","value":{"type":"literal","content":"1832469130241"}}},
      {"name":"fieldValue","input":{"type":"string","value":{"type":"ref","content":{"source":"block-output","blockID":"190201","name":"output"},"rawMeta":{"type":1}}}} ],
    [ {"name":"fieldID",  "input":{"type":"string","value":{"type":"literal","content":"1832469130245"}}},
      {"name":"fieldValue","input":{"type":"string","value":{"type":"literal","content":"draft","rawMeta":{"type":1}}}} ]
  ]
},
"outputs": [ {"type":"list","name":"outputList","schema":{"type":"object","schema":[]}}, {"type":"integer","name":"rowNum"} ]
```

- `fieldInfo` 是**二维数组**：每个内层是 `[fieldID, fieldValue]` 一对。
- `fieldID` 用**字符串**，值可以是 `ref`（从上游取）或 `literal`（写死）。

### 更新数据 `type:"42"`

结构和查询几乎一样，但有 `condition`（改哪些行）+ `fieldInfo`（改成什么）：

```json
"updateParam": {
  "condition": { "conditionList": [[ {left…},{operation…},{right…} ]], "logic": "AND" },
  "fieldInfo": [
    [ {"name":"fieldID","input":{"type":"string","value":{"type":"literal","content":"1832469130246"}}},
      {"name":"fieldValue","input":{"type":"string","value":{"type":"ref","content":{"source":"block-output","blockID":"100001","name":"reviewer_name"},"rawMeta":{"type":1}}}} ]
  ]
},
"outputs": [ {"type":"list","name":"outputList","schema":{"type":"object","schema":[]}}, {"type":"integer","name":"rowNum"} ]
```

- 更新/新增节点的 `outputList` 的 `schema` 是**空数组 `[]`**（无字段定义），照抄。

---


## 15. 问答 `type:"18"` · 意图识别 `type:"22"`

这两个节点的 `llmParam` 是**普通对象**，而大模型节点（`type:"3"`）的是 `[{name,input}]` **数组**。
**键名也不同：这里拼写是正确的 `modelName`，`type:"3"` 里是平台拼错的 `modleName`。**
把 `type:"3"` 的数组结构套到这两个节点上会粘贴失败。

### 问答 `"18"`

```json
{
  "nodeMeta": {"title":"问答","icon":"…/icon-Direct-Question-v2.jpg",
    "description":"支持中间向用户提问问题,支持预置选项提问和开放式问题提问两种方式",
    "mainColor":"#3071F2","subTitle":"问答"},
  "inputs": {
    "llmParam": {
      "modelType": 1772546477, "modelName": "豆包·2.0·lite",
      "generationDiversity": "balance", "frequencyPenalty": 0,
      "maxTokens": 4096, "maxOutputTokens": 4096,
      "store": true, "cachingExpireTime": 259200, "responseFormat": 2,
      "parameters": {"max_completion_tokens": 0},
      "systemPrompt": ""
    },
    "inputParameters": [
      {"name":"input","input":{"type":"string",
        "value":{"type":"ref","content":{"source":"block-output","blockID":"100001","name":"input"},"rawMeta":{"type":1}}}}
    ],
    "extra_output": false,
    "answer_type": "text",
    "option_type": "static",
    "dynamic_option": {"type":"string","value":{"type":"ref",
      "content":{"source":"block-output","blockID":"","name":""}}},
    "question": "{{input}}",
    "options": [{"name":""},{"name":""}],
    "limit": 3
  },
  "outputs": [
    {"type":"string","name":"USER_RESPONSE","required":true,"description":"用户本轮对话输入内容"},
    {"type":"list","name":"QUESTION_DATA","required":true,"description":"问题列表",
     "schema":{"type":"object","schema":[
       {"type":"string","name":"content_type"},{"type":"string","name":"content"}]}}
  ]
}
```

要点：
- `question` 里用 `{{输入参数名}}` 引用本节点输入
- `answer_type` 实测 `"text"`；`option_type` 实测 `"static"`（预置选项）。开放式提问时 `options` 为空
- **输出名固定**：`USER_RESPONSE`（用户回答）与 `QUESTION_DATA`（问题列表）。**不要改名**
- `limit: 3` 是重复提问次数上限

### 意图识别 `"22"`

```json
{
  "nodeMeta": {"title":"意图识别","icon":"…/icon-Intent-v2.jpg",
    "description":"用于用户输入的意图识别，并将其与预设意图选项进行匹配。",
    "mainColor":"#00B2B2","subTitle":"意图识别"},
  "outputs": [{"type":"integer","name":"classificationId"}],
  "inputs": {
    "chatHistorySetting": {"enableChatHistory": false, "chatHistoryRound": 3},
    "inputParameters": [
      {"name":"query","input":{"type":"string",
        "value":{"type":"ref","content":{"source":"block-output","blockID":"100001","name":"input"},"rawMeta":{"type":1}}}}
    ],
    "llmParam": {
      "modelType": 1772546477, "modelName": "豆包·2.0·lite",
      "generationDiversity": "default_val", "frequencyPenalty": 0,
      "maxTokens": 100, "maxOutputTokens": 4096,
      "store": true, "cachingExpireTime": 259200, "responseFormat": 2,
      "temperature": 0.3, "topP": 1, "thinkingType": "disabled",
      "parameters": {"max_completion_tokens": 0, "reasoning_effort": "minimal"},
      "prompt": {"type":"string","value":{"type":"literal","content":"{{query}}"}},
      "systemPrompt": {"type":"string","value":{"type":"literal","content":""}},
      "enableChatHistory": false, "chatHistoryRound": 3
    },
    "intents": [{"name":"查询进度"},{"name":"提交材料"}],
    "mode": "top_speed",
    "version": "2",
    "settingOnError": {"processType":1,"timeoutMs":60000,"retryTimes":0}
  }
}
```

要点：
- **`llmParam.prompt` / `systemPrompt` 是嵌套的值对象** `{type,value:{...}}`，而 `type:"18"` 的 `systemPrompt` 是纯字符串。这个不一致是平台自己的写法，照抄
- `intents` 数组里 `{name: 意图名}`，索引即 `classificationId` 的取值（`0` 起）
- `mode` 实测 `"top_speed"`（极速模式）；`version` 是 `"2"`（**字符串**）
- **分支端口是 `branch_0` / `branch_1` / … / `default`**（见下），不是选择器的 `"true"`/`"false"`
- 输出只有 `classificationId`（integer）

### ★★ 意图识别：N 个 intents 必须连 N 条 `branch_N` + 1 条 `default`

**用户提供的实测样本（2026-09-20，4 类意图）**：

```jsonc
"intents": [ {"name":"正常求职指导"}, {"name":"代写简历或代做测评"},
             {"name":"编造经历学历或伪造材料"}, {"name":"按性别地域等敏感属性筛选候选人"} ]

{"sourceNodeID":"100002","targetNodeID":"131427","sourcePortID":"branch_0"}   // intents[0]
{"sourceNodeID":"100002","targetNodeID":"105869","sourcePortID":"branch_1"}   // intents[1]
{"sourceNodeID":"100002","targetNodeID":"173620","sourcePortID":"branch_2"}   // intents[2]
{"sourceNodeID":"100002","targetNodeID":"134476","sourcePortID":"branch_3"}   // intents[3]
{"sourceNodeID":"100002","targetNodeID":"900001","sourcePortID":"default"}    // 没匹配上
```

- 端口名按 `intents` **数组下标**：`branch_0` = 第 1 个意图。`default` = 未命中任何意图的出口，**不能省**。
- **少连一条的后果是画布上那个分支端口「悬空」** —— 用户一眼就能看出来
  （原话："你有几个匹配项，就得创造几个分支"）。这是**结构完整性**要求，不是可选优化。
- 允许**多条分支指向同一个下游节点**（扇入合法），也允许某个 `branch_N` 直接连 `结束`。
- ⚠️ 历史翻车：一条守卫工作流给 4 类意图只连了 1 条出边（走到下游代码节点），
  另外 4 条分支全悬空 —— 而校验器当时**没有任何规则**发现它。现已补 `E18`。
- **判断该用意图识别还是选择器**：
  | 分流依据 | 用哪个 |
  |---|---|
  | 本来就是「用户想干什么」（N 种诉求） | **意图识别**（N 路，一个节点搞定） |
  | 上游节点算出来的状态量（`v_hit == 'Y'`、长度是否为 0） | **选择器**（只能 2 路，N 路要串 N-1 个） |


## 16. 批处理 `type:"28"`

结构与循环节点**同构**：顶层 `blocks[]` + 顶层 `edges[]` + `meta.canvasPosition`。

```json
{
  "meta": {"position":{"x":821,"y":-67},"canvasPosition":{"x":821,"y":133}},
  "data": {
    "nodeMeta": {"title":"批处理","icon":"…/icon-Batch-v2.jpg",
      "description":"通过设定批量运行次数和逻辑，运行批处理体内的任务",
      "mainColor":"#00B2B2","subTitle":"批处理"},
    "inputs": {
      "concurrentSize": {"type":"integer","value":{"type":"literal","content":"10"}},
      "batchSize":      {"type":"integer","value":{"type":"literal","content":"100"}},
      "inputParameters": [
        {"name":"input","input":{"type":"list","schema":{"type":"object","schema":[
          {"type":"string","name":"content_type"},{"type":"string","name":"content"}]},
          "value":{"type":"ref","content":{"source":"block-output","blockID":"156696","name":"QUESTION_DATA"},"rawMeta":{"type":103}}}}
      ]
    },
    "outputs": []
  },
  "blocks": [ /* 子画布内的节点 */ ],
  "edges":  [ /* 子画布内的连线 */ ]
}
```

要点：
- `concurrentSize`（并发数，默认 10）、`batchSize`（每批条数，默认 100）
- **`outputs` 实测为空数组 `[]`**（批处理的结果在子画布内取）
- **出口端口是 `batch-output`**（循环是 `loop-output`，不要混）
- 子画布内外端口同循环：`loop-function-inline-output` / `loop-function-inline-input`
- ⚠️ **子画布内引用 `批处理id.input` 拿到的是「当前元素」**，类型降一层（`list<object{...}>` → `object{...}`）

## 17. SQL 自定义 `type:"12"` · 删除数据 `type:"44"`

```json
// SQL 自定义（主色 #FF811A，与其他数据库节点不同）
{
  "nodeMeta": {"title":"SQL自定义","icon":"…/icon-Database-v2.jpg",
    "description":"基于用户自定义的 SQL 完成对数据库的增删改查操作",
    "mainColor":"#FF811A","subTitle":"SQL自定义"},
  "inputs": {
    "inputParameters": [ {"name":"…","input":{…}} ],
    "databaseInfoList": [ {"databaseInfoID":"7683881920299581483"} ]
  },
  "outputs": [
    {"type":"list","name":"outputList","schema":{"type":"object","schema":[]}},
    {"type":"integer","name":"rowNum"}
  ]
}
```

⚠️ **SQL 文本字段名未证实** —— 样本里这个节点没配 SQL，所以看不到字段名。写 SQL 时先在画布上配一次、复制出来看。

```json
// 删除数据
{
  "nodeMeta": {"title":"删除数据","icon":"…/icon-database-delete.jpg",
    "description":"从表中删除数据记录，用户指定删除条件来删除符合条件的记录",
    "mainColor":"#F2B600","subTitle":"删除数据"},
  "inputs": {
    "databaseInfoList": [ {"databaseInfoID":"7683881920299581483"} ],
    "deleteParam": {"condition": {"conditionList": [[
        {"name":"left","input":{"type":"string","value":{"type":"literal","content":"user_id"}}},
        {"name":"operation","input":{"type":"string","value":{"type":"literal","content":"EQUAL"}}},
        {"name":"right","input":{"type":"string","value":{"type":"literal","content":"x","rawMeta":{"type":1}}}}]],
      "logic": "AND"}}
  },
  "outputs": [
    {"type":"list","name":"outputList","schema":{"type":"object","schema":[]}},
    {"type":"integer","name":"rowNum"}
  ]
}
```

未配置条件时平台写的是 `{"condition": {"logic": "AND"}}`（没有 `conditionList`）。
**删除是不可逆操作**，生成时务必让用户确认条件——`where` 为空会删全表。

## 18. HTTP 请求 `type:"45"`

```json
{
  "nodeMeta": {"title":"HTTP 请求","icon":"…/icon-HTTP.png",
    "description":"用于发送API请求，从接口返回数据",
    "mainColor":"#3071F2","subTitle":"HTTP 请求"},
  "inputParameters": [],
  "inputs": {
    "apiInfo": {"method": "GET"},
    "body": {"bodyType": "EMPTY",
      "bodyData": {"binary": {"fileURL": {"type":"string","value":{"type":"ref",
        "content":{"source":"block-output","blockID":"","name":""}}}}}},
    "auth": {"authType": "BEARER_AUTH", "authData": {"customData": {"addTo": "header"}}},
    "setting": {"timeout": 120, "retryTimes": 3},
    "settingOnError": {}
  },
  "outputs": [
    {"type":"string","name":"body"},
    {"type":"integer","name":"statusCode"},
    {"type":"string","name":"headers"}
  ]
}
```

要点：
- ⚠️ **`inputParameters` 和 `settingOnError` 在 `data` 层级**，不在 `data.inputs` 里。这是实测的唯一一个这样的节点
- ⚠️ **url / headers / query 的字段名未证实**（样本未配置请求）。配一次真实请求再复制
- `apiInfo.method` 实测 `"GET"`；`body.bodyType` 实测 `"EMPTY"`
- `auth.authType` 实测 `"BEARER_AUTH"`；`addTo` 实测 `"header"`
- `setting` 在 `inputs` 里（不是 data 层）：`timeout: 120`（秒）、`retryTimes: 3`
- 输出名固定 `body` / `statusCode` / `headers`

## 19. JSON 序列化 `type:"58"` · 反序列化 `type:"59"`

两个节点结构极简，主色都是 `#F2B600`。

```json
// JSON 序列化：变量 → JSON 字符串
{
  "nodeMeta": {"title":"JSON 序列化","icon":"…/icon-to_json.png",
    "description":"用于把变量转化为JSON字符串","mainColor":"#F2B600","subTitle":"JSON 序列化"},
  "inputs": {"inputParameters": [ {"name":"input","input":{…}} ]},
  "outputs": [ {"type":"string","name":"output"} ]
}

// JSON 反序列化：JSON 字符串 → 变量
{
  "nodeMeta": {"title":"JSON 反序列化","icon":"…/icon-from_json.png",
    "description":"用于把JSON字符串转化为变量","mainColor":"#F2B600","subTitle":"JSON 反序列化"},
  "inputs": {"inputParameters": [ {"name":"input","input":{…}} ]},
  "outputs": [ {"type":"object","name":"output","schema":[]} ]
}
```

要点：
- **输出名固定叫 `output`**，类型分别是 `string`（序列化）/ `object`（反序列化）
- `from_json` 的 `output.schema` 是空数组 —— 平台不知道 JSON 里有什么字段，取值要靠点路径 `{{节点.output.字段名}}`
- 用途：把结构体塞进数据库文本字段（序列化），或把大模型返回的 JSON 字符串解成结构（反序列化）


## 20. 输入 `type:"30"` · 输出 `type:"13"`（中间过程的消息节点）

> ⚠️ **这两个 ≠ 开始(1) / 结束(2)。** 它们是**流程中间**向用户提问/回话用的，
> 主要在**对话流（Chatflow）**里用。别搞混（见 `02`）。

### 输入 `"30"`

```json
{
  "id": "183716", "type": "30",
  "meta": {"position": {"x": 3850, "y": -360.55}},
  "data": {
    "nodeMeta": {
      "description": "支持中间过程的信息输入",
      "icon": "…/icon-Input-v2.jpg",
      "mainColor": "#5C62FF", "subTitle": "输入", "title": "输入"},
    "outputs": [{"type": "string", "name": "input", "required": true}],
    "inputs": {
      "outputSchema": "[{\"type\":\"string\",\"name\":\"input\",\"required\":true}]"
    }
  },
  "_temp": {"bounds": {"x": 3670, "y": -360.55, "width": 360, "height": 86},
            "externalData": {"icon": "…", "description": "支持中间过程的信息输入",
                             "mainColor": "#5C62FF", "isImageflow": false, "title": "输入"}}
}
```

要点：
- ⚠️ **`inputs.outputSchema` 是 `outputs` 数组的「JSON 字符串」形态**，不是嵌套对象。
  这是全平台唯一这么干的地方。生成器已自动处理。
- `bounds.height = 86`（比结束节点的 112 矮）。
- `_temp.externalData` 多一个 **`isImageflow: false`** 键。
- 规格里这样写：
  ```json
  {"id":"183716","type":"输入","title":"输入",
   "outputs":[{"name":"input","type":"string","required":true}]}
  ```

### 输出 `"13"`（原名「消息节点」，后更名）

```json
{
  "id": "184567", "type": "13",
  "meta": {"position": {"x": 4615, "y": 105}},
  "data": {
    "nodeMeta": {
      "description": "节点从\"消息\"更名为\"输出\"，支持中间过程的消息输出，支持流式和非流式两种方式",
      "icon": "…/icon-Output-v2.jpg",
      "mainColor": "#5C62FF", "subTitle": "输出", "title": "输出"},
    "inputs": {
      "streamingOutput": false,
      "callTransferVoice": true,
      "chatHistoryWriting": "historyWrite",
      "content": {"type": "string", "value": {"type": "literal", "content": "{{output}}"}},
      "inputParameters": [
        {"name": "output", "input": {"type": "string", "value": {"type": "ref",
          "content": {"source": "block-output", "blockID": "183716", "name": "input"},
          "rawMeta": {"type": 1}}}}
      ]
    }
  },
  "_temp": {"bounds": {"x": 4435, "y": 105, "width": 360, "height": 86},
            "externalData": {"…": "同输入节点，含 isImageflow"}}
}
```

要点：
- ⚠️ **没有 `outputs` 键**，只有 `inputs`（与结束节点同类）。
- `content` 里写 `{{输入参数名}}` 引用本节点的入参。
- ⚠️ **`content` 的 `value` 里【不带 `rawMeta`】** —— 全平台其他地方都带，这里不带。**照抄，别"修正"**。
- `chatHistoryWriting` 实测 `"historyWrite"`；`callTransferVoice: true`；`streamingOutput: false`。
- 规格里这样写：
  ```json
  {"id":"184567","type":"输出","title":"输出",
   "inputs":{"output":"183716.input"}, "content":"{{output}}"}
  ```


## 21. 知识库与数据四兄弟：写入 `27` / 删除 `60` / 长期记忆 `66`·`67` / 变量赋值 `40`

这四个是 2026-09-20 实测补齐的，**原始样本未配置**（资源引用都是空数组），
所以下面标 ⚠️ 的地方是「结构已实测、配置态内容未实测」。

### 知识库写入 `type:"27"`

```json
{
  "id":"126925","type":"27",
  "data":{
    "nodeMeta":{"title":"知识库写入","icon":"…/icon-KnowledgeWriting-v2.jpg",
      "description":"写入节点可以添加 文本类型 的知识库，仅可以添加一个知识库",
      "mainColor":"#FF811A","subTitle":"知识库写入"},
    "outputs":[{"type":"string","name":"documentId"},
               {"type":"string","name":"fileName"},
               {"type":"string","name":"fileUrl"}],
    "inputs":{
      "actionType":0,
      "inputParameters":[],
      "datasetParam":[
        {"name":"datasetList","input":{"type":"list","schema":{"type":"string"},
          "value":{"type":"literal","content":[]}}},
        {"name":"documentID","input":{"type":"string","value":{"type":"literal",
          "content":"","rawMeta":{"fileName":""}}}},
        {"name":"datasetType","input":{"type":"integer","value":{"type":"literal","content":0}}},
        {"name":"VolcanoInfoList","input":{"type":"list",
          "schema":{"type":"object","schema":[{"type":"string","name":"datasetID"},
                                              {"type":"string","name":"volcanoServiceID"}]},
          "value":{"type":"literal","content":[]}}}
      ],
      "strategyParam":{"indexStrategy":{}},
      "volcanoTab":[]
    }
  }
}
```

- ⚠️ **`documentID` 的 `rawMeta` 是 `{"fileName": ""}`，不是 `{"type": N}`** —— 全平台唯一这种写法的 rawMeta。照抄。
- `bounds.height = 138`。
- 规格写法：`{"type":"知识库写入","dataset_ids":["真实知识库ID"],"document_id":"","action_type":0}`
- ⚠️ **`datasetList` 必须填真实知识库 ID**，否则粘贴时强校验失败（见 `09`）。

### 知识库删除 `type:"60"`

与写入同构，但 `datasetParam` **只有 3 项**（**没有 `documentID`**），也没有 `actionType` /
`strategyParam` / `volcanoTab`。输出只有一个 `isSuccess`（boolean）。

```json
{"id":"181239","type":"60",
 "data":{"nodeMeta":{"title":"知识库删除","icon":"…/icons-dataset-delete.png",
   "description":"用于删除知识库中的文档","mainColor":"#FF811A","subTitle":"知识库删除"},
 "outputs":[{"type":"boolean","name":"isSuccess"}],
 "inputs":{"inputParameters":[],
   "datasetParam":[ datasetList / datasetType / VolcanoInfoList ]}}}
```

规格：`{"type":"知识库删除","dataset_ids":["真实ID"]}`

### 长期记忆写入 `type:"66"`

```json
{"id":"129127","type":"66",
 "data":{"nodeMeta":{"title":"长期记忆写入","icon":"…/icon-ltm_write.png",
   "description":"写入长期记忆","mainColor":"#3071F2","subTitle":"长期记忆写入"},
 "inputs":{
   "memoryInfoList":[],
   "inputParameters":[
     {"name":"messageList","input":{"type":"list",
       "value":{"type":"literal","content":"[{\n  \"role\": \"user\",\n  \"content\": \"…\"\n}, …]",
                "rawMeta":{"type":103}},
       "schema":{"type":"object","schema":[{"name":"role","type":"string"},
                                            {"name":"content","type":"string"}]}}}]},
 "outputs":[{"type":"boolean","name":"isSuccess"}]}}
```

- ⚠️ `messageList` 的 `value.content` 是 **JSON 字符串**（和输入节点 `outputSchema` 同款手法）。
  规格里可以传 Python 列表，生成器会自动 `json.dumps(indent=2)`；也可直接传字符串。
- 规格：`{"type":"长期记忆写入","message_list":[{"role":"user","content":"…"}]}`

### 长期记忆检索 `type:"67"`

```json
{"id":"174958","type":"67",
 "data":{"nodeMeta":{"title":"长期记忆检索","icon":"…/icon-ltm_read.png",
   "description":"长期记忆检索","mainColor":"#3071F2","subTitle":"长期记忆检索"},
 "inputs":{"memoryInfoList":[],
   "inputParameters":[{"name":"limit","input":{"type":"integer",
     "value":{"type":"literal","content":20,"rawMeta":{"type":2}}}}]},
 "outputs":[{"type":"list","name":"outputList",
   "schema":{"type":"object","schema":[{"type":"string","name":"output"},
                                        {"type":"string","name":"date"}]}}]}}
```

规格：`{"type":"长期记忆检索","limit":20}`

### 变量赋值 `type:"40"`

```json
{"id":"126749","type":"40",
 "data":{"nodeMeta":{"title":"变量赋值","icon":"…/Variable.jpg",
   "description":"用于给支持写入的变量赋值，包括应用变量、用户变量",
   "mainColor":"#FF811A","subTitle":"变量赋值"},
 "inputs":{"inputParameters":[{}],"variableTypeMap":{}},
 "outputs":[{"name":"isSuccess","type":"boolean"}]}}
```

- ⚠️ **实测样本是「未配置态」**：`inputParameters` 是 `[{}]`（一个空对象！）、`variableTypeMap` 是 `{}`。
  **「已配置」时的行结构本技能尚未证实** —— 如果你配置过它，复制一份出来就能补齐。
- 生成器默认就输出这个未配置态；也可以用 `input_parameters_raw` / `variable_type_map` 显式覆盖。
- 规格：`{"type":"变量赋值"}`

---


## 22. 节点高度 `_temp.bounds.height` 不是常量 —— 部分类型随配置行数变化

`_temp.bounds.height` 是**该节点当前 UI 高度**的快照。**大部分类型是常数，但有几类是随配置行数线性增长的。**

### 已拟合出公式的（14 份真实样本，2026-09-20）

| 节点 | 公式 | 验证点 |
|---|---|---|
| **意图识别** `22` | `150 + 26 × 意图数` | 1 条→176、3 条→228 |
| **变量聚合** `32` | `54 + 60 × 分组数` | 1 组→114、2 组→174（**与组内变量数无关**）|
| **查询数据** `43` | `106 + 48 × 条件行数` | 1 行→154、2 行→202、3 行→250 |

> 📌 **反例（2026-09-20，用户样本）**：4 个意图的节点实际 `height = 278`，而公式给 `150+26×4 = 254`。
> 同一份样本里「代码」节点是 136（基准 112）、「知识库检索」162、「大模型」164。
> **推测**：平台在粘贴/交互时会按内容**重算**高度，可能还受 `nodeMeta.description` 行数影响。
> **但这对交付毫无影响** —— 该字段只决定画布上的显示尺寸，**运行不读它、粘贴也不校验它**。
> 所以：**不要为它花时间，更不要手改 JSON 去凑数**。给个合理值即可。

### 对照组：这几类**恒定**（已验证与行数无关）

| 节点 | 高度 | 反例 |
|---|---|---|
| 大模型 `3` | 163.6 | `inputParameters` 有 2/3/5/10 个时**都是 163.6** |
| 新增数据 `46` | 140 | `fieldInfo` 有 4/7/8/11 行时**都是 140** |
| 代码 `5` | 112 | — |
| 结束 `2` | 112 | — |
| 开始 `1` | 86 | — |

> ⚠️ **`BOUNDS_H` 表里存的是「基准/默认值」，不是真值。** 生成器里由 `_dyn_bounds_h()` 按公式覆盖。

### 这个字段影响什么（重要，别误判优先级）

| 影响 | 有无 |
|---|---|
| 工作流**运行** | ❌ 完全不影响，执行引擎不读它 |
| **能否粘贴** | ❌ 不影响（粘贴只看**顶层** `bounds` 是否存在 + 资源 ID） |
| **画布上的显示尺寸** | ✅ 只影响这个。高度太小 → 节点显得"像旧版" |

**但依然要算对**：这是零成本保险 ——
给对值，在「平台会按配置重算」和「平台照抄我们给的值」**两种假设下都不会错**；
给错值则在第二种假设下会露馅（用户实测反馈过：粘出来像「旧的」）。

`43` / `32` 在「未配置」（无条件行 / 无分组）时无法推断，`_dyn_bounds_h()` 会返回 None 并退回基准值。

---
## 附：规格文件（`build_workflow.py` 输入）字段表

```json
{
  "name": "工作流名（仅注释用，不写入 clipboard）",
  "space_id": "7493357645614039092",
  "workflow_id": "0",
  "nodes": [ /* 见下 */ ],
  "edges": [ ["源节点id", "目标节点id"], ["选择器id", "目标id", "true|false"] ]
}
```

`nodes[]` 各项：

| 键 | 适用类型 | 说明 |
|---|---|---|
| `id` | 全部 | 字符串，建议 6 位数字、全局唯一 |
| `type` | 全部 | 数字编号字符串 或 中文名（`开始`/`大模型`/`代码`…）或 DSL 英文名，脚本都能识别 |
| `title` | 全部 | 实例名 |
| `inputs` | 除开始 | `{参数名: "来源节点id.变量名"}` 或固定值；也可写成 `{"value":…, "type":"…"}` 显式形式 |
| `outputs` | 除选择器 | `[{name, type, items?, schema?, required?, description?, assistType?}]` |
| `code` | 代码 | Python 源码字符串 |
| `language` | 代码 | 默认 3（Python） |
| `prompt` / `system_prompt` | 大模型 | 用户/系统提示词 |
| `model` / `model_type` | 大模型 | 默认 `豆包·2.0·pro` / `1772700462` |
| `branches` | 选择器 | `[{conditions:[{operator,left,right}]}]`，left/right 支持引用简写 |
| `api` | 插件 | `{apiID, apiName, pluginID, pluginName}` |
| `datasets` | 知识库 | 知识库 ID 数组，可配 `top_k` / `min_score` |
| `loop_input` / `loop_count` / `blocks` / `inner_edges` | 循环 | `blocks` 为循环体节点数组（同 nodes 结构），`loop_input` 指向要遍历的数组；⚠️ **`inner_edges`（不是 `edges`）** 是子画布内的连线 `[src, dst, 源端口?, 目标端口?]`，必须含 `loop-function-inline-output` / `loop-function-inline-input` 两条 |
| `merge_groups` | 变量聚合 | `[{name:"Group1", variables:[{type,value}]}]` |
| `database_id` / `select` / `insert` / `update` | 数据库 | 见上 |
| `terminate_plan` / `content` | 结束 | 默认 `returnVariables` |
| `question` / `options` / `limit` / `answer_type` | 问答 | — |
| `intents` / `mode` / `prompt` | 意图识别 | `prompt`/`system_prompt` 会被包成嵌套值对象 |
| `concurrent_size` / `batch_size` / `canvas_position` / `inner_edges` | 批处理 | 默认 10 / 100；顶层 edges 连下游要带端口 **`batch-output`**（循环是 `loop-output`），否则 `W11` |
| `sql` | SQL自定义 | ⚠️ 字段名未证实 |
| `where` | 删除数据 | 与查询同格式；**留空会删全表，务必校验** |
| `method` / `body` / `auth` / `setting` | HTTP 请求 | ⚠️ url/headers 字段名未证实 |
| `language` | 代码 | 3=Python（默认），5=JavaScript |
| `outputs` | 输入(30) | 会自动序列化成 `inputs.outputSchema` 字符串 |
| `content` | 输出(13) | 默认 `"{{output}}"`；可加 `streaming_output` / `call_transfer_voice` / `chat_history_writing` |
| `dataset_ids` | 知识库写入(27)/删除(60) | **必须真实知识库 ID**，否则粘贴失败 |
| `document_id` / `action_type` | 知识库写入(27) | 默认 `""` / `0` |
| `message_list` | 长期记忆写入(66) | 列表会自动序列化成 JSON 字符串 |
| `limit` | 长期记忆检索(67) | 默认 20 |
| `input_parameters_raw` / `variable_type_map` | 变量赋值(40) | 默认未配置态 `[{}]` / `{}` |
