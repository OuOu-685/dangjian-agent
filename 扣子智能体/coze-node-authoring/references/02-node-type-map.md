# 02 · 节点 type 编号对照表

## 怎么用这张表（比记编号更重要）

**推荐做法：不要背编号，去读 `data.nodeMeta.subTitle`。** 每个节点的 `subTitle` 就是它的中文类型名，能直接告诉你这是什么节点：

```python
n["data"]["nodeMeta"]["subTitle"]   # → "大模型" / "代码" / "选择器" / "循环" …
```

编号表只在两种场景下需要：**从零造节点**（要给 `type` 填值）、**写校验脚本**（要按类型分支）。其余情况一律以 `subTitle` 为准。


## ⚠️ 「开始/结束」与「输入/输出」是**两对不同的节点**（本项目踩过的最反复的坑）

这两对节点极易搞混，**我本人在这里连续判断错了两次**（先以为有独立类型 → 又以为没有 → 实测证明确实有）。
记录如下，避免再犯。

### 正确的对应关系

| 面板上的位置/名字 | 数据里的 `type` | 本技能叫法 | 作用 | 用在哪种工作流 |
|---|---|---|---|---|
| 开始 | `"1"` | **开始** | 工作流的**入口**，定义启动参数 | 全部 |
| 结束 | `"2"` | **结束** | 工作流的**出口**，定义返回结果 | 全部 |
| 输入 | `"30"` | **输入** | **中间过程**的信息输入 | 以对话流为主 |
| 输出 | `"13"` | **输出** | **中间过程**的消息输出（原名「消息节点」，后更名） | 以对话流为主 |

### 四个别名，一个东西 —— 别被绕晕

- 开始节点在官方文档里被归到「**输入和输出节点**」这一节（那是**分组名**），
  社区文章里也常写「输入节点（开始节点）」。
- 但同时，面板里**真的另有一个叫「输入」的节点**，它就是 `type:"30"`。
- 结束节点同理：`type:"2"`，官方描述写「工作流的**最终**节点」；
  而面板里另有个叫「输出」的节点 = `type:"13"`。

### 判定类型的优先级（唯一权威是数据）

1. `type` 编号 —— **最终依据**
2. `nodeMeta.icon` 文件名 —— `icon-Start-v2.jpg` → 开始；`icon-End-v2.jpg` → 结束；
   `icon-Input-v2.jpg` → 输入；`icon-Output-v2.jpg` → 输出。**文件名最不容易骗人**
3. `nodeMeta.description` 官方描述原文 —— 含「起始 / 最终 / 中间过程」等字眼
4. `nodeMeta.subTitle` —— 可能是空的，别依赖
5. 用户口头说的名字 —— **只能当线索，绝不能当判据**

### 结构上最省事的区分

| 节点 | 有没有 `outputs` 键 | 关键字段 |
|---|---|---|
| 开始 `1` | 有 | `data.outputs` + `data.trigger_parameters` |
| 结束 `2` | **没有** | `data.inputs.terminatePlan` |
| 输入 `30` | 有 | `data.inputs.outputSchema`（是 **JSON 字符串**，不是嵌套对象） |
| 输出 `13` | **没有** | `data.inputs.content` / `streamingOutput` / `callTransferVoice` / `chatHistoryWriting` |

> 另一个实操教训：**不要从"官方文档目录里的名词"反推节点类型**。
> 文档目录既有分组名（如「输入和输出节点」），也有节点名（如「变量节点」），混在一起，
> 按目录名去猜类型一定会错。**要编号就只有一个办法：在画布上复制一个节点出来看 `type`。**

---

## 已实测的编号 `[实测]`

来源：**13 份**真实工作流剪贴板文件，共 **131 个顶层节点**（含循环/批处理体内节点为 149 个）。判定依据是 `type` 与 `subTitle`（以及节点内部字段特征）三方一致。

| `type` | `subTitle`（中文名） | 官方 DSL 英文名 | 主色 | 关键判别特征（内部字段） |
|---|---|---|---|---|
| `"1"` | 开始 | `start` | `#5C62FF` | 有 `outputs[]` + `trigger_parameters[]`，**没有** `inputs` |
| `"2"` | 结束 | `end` | `#5C62FF` | 有 `inputs.terminatePlan` + `inputs.inputParameters[]` |
| `"3"` | 大模型 | `llm` | `#5C62FF` | 有 `inputs.llmParam[]`（固定 **18** 项）+ `data.version:"3"` |
| `"4"` | 插件 | `plugin` | — | 有 `inputs.apiParam[]`（7 项）；`nodeMeta` 用**小写 `subtitle`** |
| `"5"` | 代码 | `code` | `#00B2B2` | 有 `inputs.code`(字符串) + `inputs.language` + `data.version:"v2"` |
| `"6"` | 知识库检索 | `knowledge` | — | 有 `inputs.datasetParam[]`（9 项，含 `datasetList`）|
| `"8"` | 选择器 | `condition` | `#00B2B2` | 有 `inputs.branches[].condition{logic,conditions[]}` |
| `"12"` | SQL自定义 | `database` | `#FF811A` | 有 `inputs.databaseInfoList`（SQL 文本字段名未证实，样本未配置）|
| `"9"` | 工作流（子工作流） | `subflow` | `#00B83E` | 有 `inputs.inputDefs[]` + `inputs.workflowId` / `workflowVersion` / `spaceId` / `type:0`；`nodeMeta` 只有 `description/icon/isImageflow/title` |
| `"15"` | 文本处理 | `text` | `#3071F2` | 有 `inputs.method`（如 `"concat"`）+ `inputs.concatParams[]` |
| `"18"` | 问答 | `question` | `#3071F2` | 有 `inputs.question` / `inputs.options[]` / `inputs.answer_type`；`llmParam` 是**对象**；输出固定 `USER_RESPONSE` + `QUESTION_DATA` |
| `"22"` | 意图识别 | `intent` | `#00B2B2` | 有 `inputs.intents[]` / `inputs.mode` / `inputs.version:"2"`；`llmParam` 是**对象**；输出 `classificationId` |
| `"28"` | 批处理 | `batch` | `#00B2B2` | 有 `inputs.concurrentSize` + `inputs.batchSize`；**顶层 `blocks[]`**（同循环）；`outputs` 为 `[]` |
| `"27"` | 知识库写入 | `dataset_write` | `#FF811A` | 有 `inputs.datasetParam[]`（4 项）+ `actionType` / `strategyParam` / `volcanoTab`；输出 `documentId`/`fileName`/`fileUrl` |
| `"21"` | 循环 | `loop` | `#00B2B2` | 有 `inputs.loopType:"array"` + **节点顶层 `blocks[]` 与 `edges[]`** |
| `"32"` | 变量聚合 | `variable_merge` | `#00B2B2` | 有 `inputs.mergeGroups[]`，每项含 `name` + `variables[]` |
| `"40"` | 变量赋值 | `variable_assign` | `#FF811A` | `inputs.inputParameters` + `variableTypeMap`；输出 `isSuccess`(boolean) |
| `"42"` | 更新数据 | `update_database` | `#F2B600` | 有 `inputs.updateParam{condition,fieldInfo}` |
| `"43"` | 查询数据 | `select_database` | `#F2B600` | 有 `inputs.selectParam{condition,fieldList,limit,orderByList}` |
| `"44"` | 删除数据 | `delete_database` | `#F2B600` | 有 `inputs.deleteParam{condition}` |
| `"45"` | HTTP 请求 | `http` | `#3071F2` | 有 `inputs.apiInfo{method}` / `body` / `auth` / `setting`；**`inputParameters` 与 `settingOnError` 在 `data` 层级**（不在 `inputs` 里）|
| `"46"` | 新增数据 | `insert_database` | `#F2B600` | 有 `inputs.insertParam{fieldInfo}` |
| `"60"` | 知识库删除 | `dataset_delete` | `#FF811A` | `inputs.datasetParam[]`（**3 项**，比写入少 `documentID`）；输出 `isSuccess` |
| `"66"` | 长期记忆写入 | `ltm_write` | `#3071F2` | `inputs.memoryInfoList` + `inputParameters[messageList]`（值是 **JSON 字符串**）；输出 `isSuccess` |
| `"67"` | 长期记忆检索 | `ltm_read` | `#3071F2` | `inputs.memoryInfoList` + `inputParameters[limit]`；输出 `outputList`（每项 `output`/`date`）|
| `"58"` | JSON 序列化 | `to_json` | `#F2B600` | 极简：`inputs.inputParameters[]`；输出固定 `output`（string）|
| `"59"` | JSON 反序列化 | `from_json` | `#F2B600` | 极简：`inputs.inputParameters[]`；输出固定 `output`（object，`schema:[]`）|

> 三个数据库节点共用 `inputs.databaseInfoList: [{"databaseInfoID": "…"}]`。

## 未证实的编号（**不要猜，去实测**）

官方 DSL 的类型名单里还有很多节点，但**它们在样本中一次都没出现**，因此剪贴板格式的对应数字**未知**：

`intent`(意图识别)、`batch`(批处理)、`subflow`(工作流)、`input`/`output`(输入/输出)、`question`(问答)、`http`(HTTP请求)、`to_json`/`from_json`、`database`(SQL自定义)、`delete_database`(删除数据)、`drawing_board`(画板)、`image_generate`、`video_generation`、`video_audio_extractor`、`video_frame_extractor`、`ltm`/`ltm_write`/`ltm_read`、`dataset_write`/`dataset_delete`、`conversation_*`、`message_*`、`comment`(注释)、`variable`(变量赋值)。

**已知编号的空缺**（说明这些号被别的类型占了，但不知道是哪个）：
`7`、`10`、`11`、`13`、`14`、`16`、`17`、`19`、`20`、`23`–`27`、`29`–`31`、`33`–`41`、`47`–`57`、`60+`。

⚠️ **不要用"顺序推断"填空**（例如"42/43/44 都是数据库，那 45 就是…"）。
已实测编号：`1,2,3,4,5,6,8,9,12,15,18,21,22,28,32,42,43,44,45,46,58,59` —— **跳号极其严重**（12 在 8 和 15 之间、18 在 15 和 21 之间、28 在 22 和 32 之间、58/59 跳到 60 附近），说明它是一张内部注册表的 ID，不是顺序枚举。

**已实锤的教训**：`9`（工作流）和 `12/18/22/28/44/45/58/59`（SQL/问答/意图/批处理/删除/HTTP/JSON 互转）**全都无法从已有编号推出来**，必须实测。**猜一次就可能整份 JSON 粘不上。**

> **已实锤的教训**：`type:"9"` 一度是空缺（前 8 份样本里没有工作流节点）。后来拿到 4 份含子工作流调用的样本才确认 `9 = subflow`。
> **如果当初按顺序猜成 `7` 或 `10`，这 4 份文件就全部解读错了。** 这就是"不猜"的价值。

### 补全未知编号的标准动作（30 秒，比查文章可靠）

1. 在任意工作流画布上点「添加节点」，加一个你要的那个类型
2. 单击该节点，`Ctrl+C`
3. 打开记事本 `Ctrl+V`（或粘到任意文本框/`pbpaste`）
4. 看 `"type":"N"` 就是它的编号，同时能看到**完整的空节点字段骨架**

这比任何二手文章都准，而且顺手把该节点的完整字段也拿到了。

## `subTitle` 与 `title` 的区别

- `title` = **实例名**，用户在画布上给它起的名（"信息解析大模型"、"格式校验"）
- `subTitle` = **类型名**，由平台按类型自动填（"大模型"、"代码"）
- 插件节点是唯一例外：它用全小写 `subtitle`，值是 `"头条搜索:search"` 这种 `插件名:API名` 形式

生成节点时 `title` 按业务起名（建议和变量前缀呼应，如"格式校验"对应输出 `is_valid`），`subTitle` 按上表照抄。

## 数字编号与官方 DSL 名的对应关系（可放心使用）

已实测编号与官方文档英文名是**一一对应**的，可直接用括号里的英文名去对照官方文档查字段语义：

```
1 start · 2 end · 3 llm · 4 plugin · 5 code · 6 knowledge · 8 condition
15 text · 21 loop · 32 variable_merge
42 update_database · 43 select_database · 46 insert_database
```

官方 DSL 完整类型表（原样照录，供查询语义）：
`start` `end` `llm` `plugin` `subflow` `code` `intent` `condition` `loop` `batch` `variable_merge` `input` `output` `database` `update_database` `select_database` `delete_database` `insert_database` `ltm` `ltm_write` `ltm_read` `dataset_write` `dataset_delete` `knowledge` `drawing_board` `image_generate` `video_audio_extractor` `video_frame_extractor` `video_generation` `text` `question` `to_json` `from_json` `http` `conversation_list` `conversation_delete` `conversation_create` `conversation_update` `conversation_clear` `conversation_history_list` `message_list` `message_create` `message_update` `message_delete`

（另有 DSL 示例中出现过的 `comment` 节点，用于画布注释，`parameters` 为 `{note, schemaType}`。）
