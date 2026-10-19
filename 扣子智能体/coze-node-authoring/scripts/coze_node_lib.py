# -*- coding: utf-8 -*-
"""
coze_node_lib —— Coze 工作流剪贴板 JSON 的节点构造器库

用途：用 Python 代码「拼」出 Coze 节点，而不是在画布上手工点。
     产出物是可直接 Ctrl+V 粘进 Coze 工作流画布的 coze-workflow-clipboard-data JSON。

设计要点（全部对齐实测样本）：
  · 两遍构建：先登记各节点 outputs 的类型，再回填 inputs —— 这样 ref 才能带上正确的 rawMeta 与 input.type
  · 规格里引用写成 "100001.draft_text" 的简写，本库负责展开成完整 ref 结构
  · literal 的 rawMeta 按 Python 值的类型自动推断

用法：
    from coze_node_lib import Workflow, node
    wf = Workflow(space_id="7493357645614039092")
    wf.add(node("100001", "start", "开始", outputs=[("draft_text", "string", True)]))
    wf.add(node("171354", "code", "文本分段",
                inputs={"draft_text": "100001.draft_text"},
                code="async def main(draft_text: str) -> dict:\\n    return {'out': draft_text}",
                outputs=[("out", "string")]))
    wf.link("100001", "171354")
    wf.dump("out.json")
"""

from __future__ import annotations

import copy
import json
import os
import re

# ---------------------------------------------------------------- 常量表

#: 已实测的 type 编号 → (中文名, 官方 DSL 英文名)
TYPE_TABLE = {
    "1":  ("开始",       "start"),
    "2":  ("结束",       "end"),
    "3":  ("大模型",     "llm"),
    "4":  ("插件",       "plugin"),
    "5":  ("代码",       "code"),
    "6":  ("知识库检索", "knowledge"),
    "8":  ("选择器",     "condition"),
    "9":  ("工作流",     "subflow"),
    "12": ("SQL自定义",  "database"),
    "13": ("输出",       "output"),
    "15": ("文本处理",   "text"),
    "18": ("问答",       "question"),
    "21": ("循环",       "loop"),
    "27": ("知识库写入", "dataset_write"),
    "22": ("意图识别",   "intent"),
    "28": ("批处理",     "batch"),
    "30": ("输入",       "input"),
    "32": ("变量聚合",   "variable_merge"),
    "40": ("变量赋值",   "variable_assign"),
    "42": ("更新数据",   "update_database"),
    "43": ("查询数据",   "select_database"),
    "44": ("删除数据",   "delete_database"),
    "45": ("HTTP 请求",  "http"),
    "46": ("新增数据",   "insert_database"),
    "60": ("知识库删除", "dataset_delete"),
    "66": ("长期记忆写入", "ltm_write"),
    "67": ("长期记忆检索", "ltm_read"),
    "58": ("JSON 序列化", "to_json"),
    "59": ("JSON 反序列化", "from_json"),
}
TYPE_ALIAS = {}
for _n, (_cn, _en) in TYPE_TABLE.items():
    TYPE_ALIAS[_n] = _n
    TYPE_ALIAS[_cn] = _n
    TYPE_ALIAS[_en] = _n
# 允许的简写
TYPE_ALIAS.update({
    "llm": "3", "大模型节点": "3",
    "code": "5", "代码节点": "5",
    "condition": "8", "选择器节点": "8", "分支": "8", "条件判断": "8",
    "subflow": "9", "工作流节点": "9", "子工作流": "9",
    "question": "18", "问答节点": "18",
    "intent": "22", "意图识别节点": "22",
    "batch": "28", "批处理节点": "28",
    "database": "12", "sql": "12", "SQL节点": "12", "SQL自定义节点": "12",
    # ---- 实测：type 13 = 输出（原「消息节点」更名而来）、type 30 = 输入 ----
    # 注意：这两个是「中间过程的信息输入 / 消息输出」节点，用于对话流，
    #       ≠ 开始(1) / 结束(2)。面板上分别叫「输入」「输出」。
    "output": "13", "输出": "13", "输出节点": "13",
    "message": "13", "消息节点": "13", "消息": "13",
    "input": "30", "输入": "30", "输入节点": "30",
    "delete_database": "44", "删除数据节点": "44",
    "http": "45", "HTTP节点": "45", "HTTP请求节点": "45",
    "to_json": "58", "JSON序列化": "58", "json序列化": "58",
    "from_json": "59", "JSON反序列化": "59", "json反序列化": "59",
    # ---- 实测 2026-09-20：知识库写入/删除、变量赋值、长期记忆写入/检索 ----
    "dataset_write": "27", "知识库写入": "27", "knowledge_write": "27",
    "variable_assign": "40", "变量赋值": "40", "变量节点": "40", "set_variable": "40",
    "dataset_delete": "60", "知识库删除": "60", "knowledge_delete": "60",
    "ltm_write": "66", "长期记忆写入": "66", "memory_write": "66",
    "ltm_read": "67", "长期记忆检索": "67", "memory_read": "67",
    "loop": "21", "循环节点": "21",
    "variable_merge": "32", "变量聚合节点": "32",
    "plugin": "4", "插件节点": "4",
    "knowledge": "6", "知识库": "6", "知识库检索节点": "6",
    "text": "15", "文本处理节点": "15",
    "select_database": "43", "查询数据节点": "43",
    "insert_database": "46", "新增数据节点": "46",
    "update_database": "42", "更新数据节点": "42",
})

#: rawMeta.type 编码（实测）
RAW = {
    "string":  1,
    "integer": 2,
    "boolean": 3,
    "float":   4,
    "number":  4,
    "object":  6,
    "list":    None,   # 由元素类型决定：99 / 103
}

#: 数组元素的 rawMeta 编码（实测；100/101/102 未证实，不使用）
RAW_ARRAY = {
    "string": 99,
    "object": 103,
}

MAIN_COLOR = {
    "1": "#5C62FF", "2": "#5C62FF", "3": "#5C62FF", "4": "#5C62FF",
    "13": "#5C62FF", "30": "#5C62FF",
    "27": "#FF811A", "40": "#FF811A", "60": "#FF811A",
    "66": "#3071F2", "67": "#3071F2",
    "5": "#00B2B2", "8": "#00B2B2", "21": "#00B2B2", "22": "#00B2B2", "28": "#00B2B2",
    "32": "#00B2B2",
    "6": "#5C62FF", "9": "#00B83E", "15": "#3071F2", "18": "#3071F2", "45": "#3071F2",
    "12": "#FF811A",
    "42": "#F2B600", "43": "#F2B600", "44": "#F2B600", "46": "#F2B600",
    "58": "#F2B600", "59": "#F2B600",
}

ICON_BASE = ("https://lf3-static.bytednsdoc.com/obj/eden-cn/dvsmryvd_avi_dvsm/"
             "ljhwZthlaukjlkulzlp/icon/")
ICON = {
    "1":  "icon-Start-v2.jpg", "2": "icon-End-v2.jpg", "3": "icon-LLM-v2.jpg",
    "4":  "icon-Plugin-v2.jpg", "5": "icon-Code-v2.jpg", "6": "icon-StrConcat-v2.jpg",
    "8":  "icon-Condition-v2.jpg", "9": "icon-Workflow-v2.jpg", "12": "icon-Database-v2.jpg",
    "15": "icon-StrConcat-v2.jpg", "18": "icon-Direct-Question-v2.jpg",
    "21": "icon-Loop-v2.jpg", "22": "icon-Intent-v2.jpg", "28": "icon-Batch-v2.jpg", "32": "VariableMerge-icon.jpg",
    "44": "icon-database-delete.jpg", "45": "icon-HTTP.png",
    "13": "icon-Output-v2.jpg", "30": "icon-Input-v2.jpg",
    "27": "icon-KnowledgeWriting-v2.jpg", "40": "Variable.jpg",
    "60": "icons-dataset-delete.png",
    "66": "icon-ltm_write.png", "67": "icon-ltm_read.png",
    "46": "icon-database-insert.jpg", "58": "icon-to_json.png", "59": "icon-from_json.png",
    "42": "icaon-database-update.jpg", "43": "icaon-database-select.jpg",
    "46": "icon-database-insert.jpg",
}

DESC = {
    "1":  "工作流的起始节点，用于设定启动工作流需要的信息",
    "2":  "工作流的最终节点，用于返回工作流运行后的结果信息",
    "3":  "调用大语言模型,使用变量和提示词生成回复",
    "4":  "…插件描述…",
    "5":  "编写代码，处理输入变量来生成返回值",
    "6":  "在选定的知识中,根据输入变量召回最匹配的信息,并以列表形式返回",
    "8":  "连接多个下游分支，若设定的条件成立则仅运行对应的分支，若均不成立则只运行“否则”分支",
    "9":  "调用已发布的工作流，实现工作流嵌套复用",
    "12": "基于用户自定义的 SQL 完成对数据库的增删改查操作",
    "13": "节点从\"消息\"更名为\"输出\"，支持中间过程的消息输出，支持流式和非流式两种方式",
    "30": "支持中间过程的信息输入",
    "27": "写入节点可以添加 文本类型 的知识库，仅可以添加一个知识库",
    "40": "用于给支持写入的变量赋值，包括应用变量、用户变量",
    "60": "用于删除知识库中的文档",
    "66": "写入长期记忆",
    "67": "长期记忆检索",
    "18": "支持中间向用户提问问题,支持预置选项提问和开放式问题提问两种方式",
    "22": "用于用户输入的意图识别，并将其与预设意图选项进行匹配。",
    "28": "通过设定批量运行次数和逻辑，运行批处理体内的任务",
    "44": "从表中删除数据记录，用户指定删除条件来删除符合条件的记录",
    "45": "用于发送API请求，从接口返回数据",
    "58": "用于把变量转化为JSON字符串",
    "59": "用于把JSON字符串转化为变量",
    "15": "用于处理多个字符串类型变量的格式",
    "21": "用于通过设定循环次数和逻辑，重复执行一系列任务",
    "32": "对多个分支的输出进行聚合处理",
    "42": "修改表中已存在的数据记录，用户指定更新条件和内容来更新数据",
    "43": "从表获取数据，用户可定义查询条件、选择列等，输出符合条件的数据",
    "46": "向表添加新数据记录，用户输入数据内容后插入数据库",
}

#: _temp.bounds 高度（实测值，仅影响视觉，不影响功能）
#: 节点包围盒宽度（13/13 平台文件的 _temp.bounds.width 都是 360）
BOUNDS_W = 360

BOUNDS_H = {
    "1": 86, "2": 112, "3": 163.6, "4": 111.1, "5": 112, "6": 138,
    "8": 137.2, "9": 112, "12": 138, "15": 120, "18": 165, "21": 160, "22": 176,
    "28": 112, "32": 120, "42": 138, "43": 138, "44": 138, "45": 114, "46": 138,
    "58": 112, "59": 112, "13": 86, "30": 86,
    "40": 112, "27": 138, "60": 138, "66": 138, "67": 138,
}

DEFAULT_MODEL = "豆包·2.0·pro"
DEFAULT_MODEL_TYPE = "1772700462"

#: 官方 DSL 里有、但本技能**没有实测编号**的类型。
#: 这些类型的剪贴板数字编号必须实测后写入 node_type_overrides.json，禁止猜测。
#: 官方 DSL 里有、但本技能**仍然没有实测编号**的类型（2026-09-20 更新：
#: 意图识别/批处理/输入/输出/问答/HTTP/JSON互转/SQL/删除数据 均已实测，已移出本表）
UNVERIFIED_TYPES = {
    # 以下都是「面板里确实存在、但本技能还没有实测编号」的（2026-09-20 更新，
    # 变量赋值/知识库写入/知识库删除/长期记忆写入/长期记忆检索 均已实测并移出）
    "async_task": "异步任务",
    "ct_sess_create": "创建会话", "ct_sess_update": "修改会话",
    "ct_sess_delete": "删除会话", "ct_sess_list": "查询会话列表",
    "ct_sess_history": "查询会话历史", "ct_sess_clear": "清空会话历史",
    "ct_msg_create": "创建消息", "ct_msg_update": "修改消息",
    "ct_msg_delete": "删除消息", "ct_msg_list": "查询消息列表",
    "image_generate": "图像生成", "image_matting": "抠图",
    "image_upscale": "画质提升", "drawing_board": "画板",
    "prompt_optimize": "提示词优化",
    "video_generation": "视频生成", "video_audio_extract": "视频提取音频",
    "video_frame": "视频抽帧",
}

OVERRIDE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "node_type_overrides.json")


def load_type_overrides(path=None):
    """
    读取实测得到的类型编号覆盖表。格式：
        {"subflow": "13", "delete_database": "44"}
    这些值必须来自"在画布上复制一个该类节点出来看 type"的实测。
    """
    path = path or OVERRIDE_FILE
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                if str(k).startswith("_"):
                    continue
                TYPE_ALIAS[str(k)] = str(v)
                if str(v) not in TYPE_TABLE:
                    TYPE_TABLE[str(v)] = (UNVERIFIED_TYPES.get(str(k), str(k)), str(k))
                    TYPE_ALIAS[UNVERIFIED_TYPES.get(str(k), str(k))] = str(v)
            return dict(data)
        except Exception:
            return {}
    return {}


#: 空格不敏感的别名索引（"HTTP 请求" / "HTTP请求" / "http请求" 都能命中）
def _nospace(s):
    return re.sub(r"\s+", "", str(s)).lower()


def resolve_type(name):
    """类型名 → 数字编号；支持数字 / 中文名 / DSL 英文名，空格与大小写不敏感"""
    s = str(name).strip()
    if s in TYPE_ALIAS:
        return TYPE_ALIAS[s]
    return TYPE_ALIAS_NOSPACE.get(_nospace(s), s)


_OVERRIDES = load_type_overrides()
TYPE_ALIAS_NOSPACE = {_nospace(k): v for k, v in TYPE_ALIAS.items()}

#: 大模型节点 llmParam 的 19 个固定键（实测 21/21 一致，含平台拼写错误 modleName）
LLM_PARAM_ORDER = [
    "modelType", "modleName", "generationDiversity", "frequencyPenalty", "maxTokens",
    "spCurrentTime", "spAntiLeak", "responseFormat", "parameters", "prompt",
    "enableChatHistory", "chatHistoryRound", "systemPrompt", "stableSystemPrompt",
    "canContinue", "loopPromptVersion", "loopPromptName", "loopPromptId",
]

#: 插件节点 apiParam 的 7 个固定键（实测 3/3 一致）
API_PARAM_ORDER = ["apiID", "apiName", "pluginID", "pluginName",
                   "pluginVersion", "tips", "outDocLink"]

REF_RE = re.compile(r"^\s*(\d{3,})\s*\.\s*([A-Za-z_][\w.\[\]]*)\s*$")


# ---------------------------------------------------------------- 值编码

def _norm_type(t):
    if not t:
        return "string"
    t = str(t).strip().lower()
    return {"str": "string", "int": "integer", "bool": "boolean",
            "num": "float", "double": "float", "dict": "object",
            "array": "list", "arr": "list"}.get(t, t)


def decl_schema(typ, items=None):
    """生成 input.schema —— list 用 {'type':x}，object 用 [字段...]"""
    typ = _norm_type(typ)
    if typ == "list":
        it = _norm_type(items or "string")
        if it == "object":
            return {"type": "object", "schema": []}
        return {"type": it}
    if typ == "object":
        return []
    return None


def raw_code(typ, items=None):
    """rawMeta.type 编码"""
    typ = _norm_type(typ)
    if typ == "list":
        it = _norm_type(items or "string")
        return RAW_ARRAY.get(it, 99)
    return RAW.get(typ, 1)


def lit(value, typ=None, items=None):
    """固定值 → value 对象"""
    if typ is None:
        typ = infer_type(value)
    typ = _norm_type(typ)
    v = {"type": "literal", "content": value}
    rc = raw_code(typ, items)
    if rc is not None:
        v["rawMeta"] = {"type": rc}
    return v


def ref(block_id, name, typ="string", items=None):
    """引用 → value 对象"""
    typ = _norm_type(typ)
    v = {
        "type": "ref",
        "content": {"source": "block-output", "blockID": str(block_id), "name": name},
    }
    rc = raw_code(typ, items)
    if rc is not None:
        v["rawMeta"] = {"type": rc}
    return v


def infer_type(value):
    """从 Python 值推断 Coze 类型"""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return "string"


def infer_items(value):
    """从 Python 列表推断元素类型"""
    if isinstance(value, list) and value:
        return infer_type(value[0])
    return "string"


# ---------------------------------------------------------------- 输出声明规范化

def norm_outputs(outputs):
    """
    支持多种简写：
      ("名字", "类型")                 / ["名字", "类型"]
      ("名字", "类型", True)           → required
      {"name":…, "type":…, "items":…, "schema":…, "required":…, "description":…, "assistType":…}
    """
    out = []
    for o in outputs or []:
        if isinstance(o, dict):
            item = {"type": _norm_type(o.get("type", "string")), "name": o["name"]}
            if item["type"] == "list":
                it = _norm_type(o.get("items", "string"))
                if it == "object":
                    item["schema"] = o.get("schema", {"type": "object", "schema": []})
                else:
                    item["schema"] = {"type": it}
            elif item["type"] == "object":
                item["schema"] = o.get("schema", [])
            if o.get("assistType"):
                item["assistType"] = o["assistType"]
            if "required" in o:
                item["required"] = bool(o["required"])
            if o.get("description"):
                item["description"] = o["description"]
            out.append(item)
        else:
            name, typ = o[0], o[1]
            item = {"type": _norm_type(typ), "name": name}
            if item["type"] == "list":
                item["schema"] = {"type": "string"}
            if len(o) > 2 and o[2] is not None:
                item["required"] = bool(o[2])
            out.append(item)
    return out


# ---------------------------------------------------------------- 节点工厂

def _meta_block(nid, ntype, title, description=None, icon=None,
                subtitle=None, extra_external=None, bounds_w=360):
    typ_cn, _ = TYPE_TABLE.get(ntype, ("", ""))
    icon = icon or (ICON_BASE + ICON.get(ntype, "icon-Plugin-v2.jpg"))
    desc = description or DESC.get(ntype, "")
    color = MAIN_COLOR.get(ntype, "#5C62FF")
    sub_bag = {"icon": icon, "description": desc, "title": title, "mainColor": color}
    if extra_external:
        sub_bag.update(extra_external)

    node_meta = {
        "description": desc,
        "icon": icon,
        "subTitle": subtitle if subtitle is not None else typ_cn,
        "title": title,
    }
    # 实测：开始 / 结束节点的 nodeMeta 既没有 mainColor，subTitle 也是空串
    if ntype in ("1", "2"):
        node_meta.pop("mainColor", None)
        if subtitle is None:
            node_meta["subTitle"] = ""
    else:
        # 实测：其他节点 nodeMeta 的键序为 description, icon, mainColor, subTitle, title
        node_meta = {
            "description": desc,
            "icon": icon,
            "mainColor": color,
            "subTitle": subtitle if subtitle is not None else typ_cn,
            "title": title,
        }
    return {"_nodeMeta": node_meta, "_temp": {
        "bounds": {"x": 0, "y": 0, "width": bounds_w,
                   "height": BOUNDS_H.get(ntype, 150)},
        "externalData": sub_bag,
    }}


def node(nid, ntype, title, *, inputs=None, outputs=None, description=None,
         subtitle=None, icon=None, position=None, **kw):
    """
    造一个节点。
    ntype 可以是数字字符串 / 中文名 / DSL 英文名。
    inputs 的值可以是：
        "100001.var"                    引用简写
        {"ref": "100001.var"}           显式引用
        字面 Python 值                   自动推断类型
        {"value":…, "type":…, "items":…} 显式字面量
        {"raw": {...}}                  完全手写的 input 对象（逃生舱）
    """
    ntype = resolve_type(ntype)
    if ntype not in TYPE_TABLE:
        hint = ""
        if str(ntype).strip() in UNVERIFIED_TYPES:
            hint = (f"\n  {ntype}（{UNVERIFIED_TYPES[str(ntype).strip()]}）的剪贴板数字编号本技能没有实测样本。"
                    f"\n  正确做法（30 秒）：画布上添加一个该类型节点 → 单击 Ctrl+C → 粘到记事本看 \"type\":\"N\""
                    f"\n  然后把 N 写进 scripts/node_type_overrides.json，例如：{{\"{ntype}\": \"N\"}}")
        raise ValueError(
            f"未知节点类型 {ntype!r}；已实测的类型只有 {sorted(TYPE_TABLE)}。{hint}")
    n = {"id": str(nid), "type": ntype,
         "meta": {"position": dict(position or {"x": 0, "y": 0})},
         "data": {}, "_input_spec": inputs or {}, "_raw_kw": kw}
    n["_title"] = title
    n["_desc"] = description
    n["_sub"] = subtitle
    n["_icon"] = icon
    n["_outputs_raw"] = outputs
    return n


def _input_obj(declared_type, value_obj, items=None, schema=None):
    """组装 {name, input:{...}} 里的 input（schema 优先用调用方传来的真实结构）"""
    declared_type = _norm_type(declared_type)
    inp = {"type": declared_type}
    if declared_type == "list":
        inp["schema"] = schema if schema is not None else decl_schema(declared_type, items)
    elif declared_type == "object":
        inp["schema"] = schema if schema is not None else (
            decl_schema(declared_type, items) or [])
    inp["value"] = value_obj
    return inp


def _expand_inputs(spec, registry, owner_id, warnings):
    """把简写 inputs 展开成 [{name, input}]"""
    out = []
    for name, raw in (spec or {}).items():
        if isinstance(raw, dict) and "raw" in raw:
            out.append({"name": name, "input": raw["raw"]})
            continue
        if isinstance(raw, dict) and "ref" in raw:
            m = REF_RE.match(str(raw["ref"]))
            if not m:
                raise ValueError(f"ref 简写格式错误：{raw['ref']!r}，应为 '节点id.变量名'")
            bid, vname = m.group(1), m.group(2)
            typ, items, schema = registry.lookup(bid, vname, warnings)
            out.append({"name": name, "input": _input_obj(typ, ref(bid, vname, typ, items), items, schema)})
            continue
        if isinstance(raw, str) and REF_RE.match(raw):
            m = REF_RE.match(raw)
            bid, vname = m.group(1), m.group(2)
            typ, items, schema = registry.lookup(bid, vname, warnings)
            out.append({"name": name, "input": _input_obj(typ, ref(bid, vname, typ, items), items, schema)})
            continue
        if isinstance(raw, dict) and ("value" in raw or "literal" in raw):
            val = raw.get("value", raw.get("literal"))
            typ = raw.get("type") or infer_type(val)
            items = raw.get("items") or (infer_items(val) if _norm_type(typ) == "list" else None)
            out.append({"name": name, "input": _input_obj(typ, lit(val, typ, items), items)})
            continue
        # 纯字面量
        typ = infer_type(raw)
        items = infer_items(raw) if typ == "list" else None
        out.append({"name": name, "input": _input_obj(typ, lit(raw, typ, items), items)})
    return out


class Registry:
    """节点 outputs 登记表：用于把 ref 解析到正确的类型"""

    def __init__(self):
        self.map = {}          # node_id -> {var_name: (type, items, output_item)}

    def register(self, nid, outputs):
        bag = {}
        for o in outputs or []:
            name = o.get("name")
            if not name:
                continue
            inp = o.get("input") or {}
            typ = o.get("type") or inp.get("type")
            schema = o.get("schema") or inp.get("schema")
            items = schema.get("type") if isinstance(schema, dict) else None
            bag[name] = (typ, items, {**o, "schema": schema})
        self.map[str(nid)] = bag

    def lookup(self, nid, vname, warnings):
        """
        返回 (type, items, schema)。
        schema 会原样带过去，这样 `list<object>{...}` 引用时下游能拿到**完整元素结构**，
        而不是一个空 schema（早期版本丢了这个，导致生成的结构与平台不一致）。
        """
        bag = self.map.get(str(nid))
        if bag is None:
            warnings.append(f"引用了不存在的节点 {nid}（变量 {vname}）")
            return "string", None, None
        head = vname.split(".")[0].split("[")[0]
        if head not in bag:
            warnings.append(f"引用了 {nid} 上不存在的输出变量 {vname}")
            return "string", None, None
        typ, items, o = bag[head]
        schema = o.get("schema")
        if "." not in vname and "[" not in vname:
            return typ, items, schema
        # 点路径：尽量下钻
        rest = vname.split(".", 1)[1].split(".")
        pool = (schema or {}).get("schema", []) if (typ == "list" and items == "object") else (
            schema if typ == "object" else [])
        for f in pool or []:
            if f.get("name") == rest[0]:
                return f.get("type", "string"), (f.get("schema") or {}).get("type"), f.get("schema")
        warnings.append(f"{nid}.{vname}：未在 {head} 的 schema 里找到字段 {rest[0]}（schema 可能为空）")
        return "string", None, None


# ---------------------------------------------------------------- 工作流

class Workflow:
    def __init__(self, *, name="workflow", space_id="", workflow_id="0",
                 host="www.coze.cn", flow_mode=0, is_douyin=False, base=None,
                 grid_x=460, origin=(180, 0), field_map=None):
        self.name = name
        self.nodes = []
        self.edges = []
        self.warnings = []
        self.grid_x = grid_x
        self.origin = origin
        self._auto_id = 100000
        #: 字段名 → 字段 ID 映射。
        #: ⚠️ **字段 ID 是「每张表独立」的**——`school` / `stage` 在 student_profile 和
        #: school_rules 里是不同的数字，所以必须按数据库分开映射，不能用一个全局表。
        #: 支持两种写法：
        #:   {"字段名": "ID"}                          → 全局兜底（只适合只有一张表时）
        #:   {"databaseInfoID": {"字段名": "ID"}}      → 按库分表（推荐）
        raw = field_map or {}
        self.field_maps = {}
        self.field_map_flat = {}
        for k, v in raw.items():
            if str(k).startswith("_"):
                continue
            if isinstance(v, dict):
                self.field_maps[str(k)] = {kk: str(vv) for kk, vv in v.items()
                                           if not str(kk).startswith("_")}
            else:
                self.field_map_flat[str(k)] = str(v)
        self._active_field_map = dict(self.field_map_flat)
        if base:
            with open(base, "r", encoding="utf-8") as f:
                b = json.load(f)
            src = b.get("source", {})
            space_id = space_id or src.get("spaceId", "")
            host = src.get("host", host)
            flow_mode = src.get("flowMode", flow_mode)
            is_douyin = src.get("isDouyin", is_douyin)
            workflow_id = src.get("workflowId", workflow_id)
        self.space_id = str(space_id) or "0"
        self.workflow_id = str(workflow_id)
        self.host = host
        self.flow_mode = flow_mode
        self.is_douyin = is_douyin
        self.registry = Registry()

    def resolve_field(self, f):
        """
        fieldList / fieldInfo 里的字段项，支持三种写法：
          1831982593025          → 直接用
          ["user_id", 1831982…]  → 用第二个元素
          "user_id"              → 经「当前数据库」的字段映射查表
        """
        if isinstance(f, (list, tuple)):
            return str(f[1]) if len(f) > 1 else str(f[0])
        s = str(f)
        if s.isdigit():
            return s
        if s in self._active_field_map:
            return str(self._active_field_map[s])
        if s in self.field_map_flat:
            return str(self.field_map_flat[s])
        self.warnings.append(f"字段名 {s!r} 不在字段映射里，先用占位 FILL_ME_{s}")
        return f"FILL_ME_{s}"

    def _use_db(self, dbid):
        """切到某张表的字段映射（数据库节点的字段 ID 是按表独立的）"""
        fm = dict(self.field_map_flat)
        fm.update(self.field_maps.get(str(dbid), {}))
        self._active_field_map = fm
        return self._active_field_map

    # ---- 组装 ----
    def add(self, n):
        if not n.get("id") or n["id"] == "auto":
            self._auto_id += 1
            n["id"] = str(self._auto_id)
        self.nodes.append(n)
        return n

    def link(self, src, dst, port=None, target_port=None, edge_repr=0):
        """
        edge_repr: 0=根层  1=循环节点内层
        """
        e = {"sourceNodeID": str(src), "targetNodeID": str(dst)}
        if port is not None:
            e["sourcePortID"] = str(port)
        if target_port is not None:
            e["targetPortID"] = str(target_port)
        self.edges.append(e)
        return e

    # ---- 构建 ----
    def build(self):
        if getattr(self, "_built", False):
            return self
        self._built = True
        # 1) 布局
        for i, n in enumerate(self.nodes):
            if n["meta"]["position"] == {"x": 0, "y": 0} or "auto_pos" in (n.get("_raw_kw") or {}):
                n["meta"]["position"] = {"x": self.origin[0] + i * self.grid_x,
                                         "y": self.origin[1]}
        # 2) 两遍：先让所有节点算出 outputs 并登记
        for n in self.nodes:
            outs = self._outputs_of(n)
            if outs is None:
                n["data"].pop("outputs", None)     # 选择器等无输出的节点：不写该键
            else:
                n["data"]["outputs"] = outs
            self.registry.register(n["id"], outs or [])

        # 2.5) 循环 / 批处理：把 inputParameters 按「元素类型」登记
        #      子画布内引用 `<本节点id>.<输入参数名>` 拿到的**不是整个数组，而是当前元素**，
        #      所以类型要降一层：list<object{...}> → object{...}；list<string> → string
        for n in self.nodes:
            if n["type"] not in ("21", "28"):
                continue
            for name, src in (n.get("_input_spec") or {}).items():
                typ, items, schema = "string", None, None
                if isinstance(src, str) and REF_RE.match(src):
                    m = REF_RE.match(src)
                    typ, items, schema = self.registry.lookup(m.group(1), m.group(2), [])
                if typ == "list" and isinstance(schema, dict):
                    self.registry.map.setdefault(n["id"], {})[name] = (
                        schema.get("type", "string"), schema.get("type"),
                        {"name": name, "type": schema.get("type", "string"),
                         "schema": schema.get("schema")})
                else:
                    self.registry.map.setdefault(n["id"], {})[name] = (
                        typ, items, {"name": name, "type": typ, "schema": schema})
        # 循环体的 outputs 也登记（外部可能引用）
        for n in self.nodes:
            for b in n["_raw_kw"].get("blocks", []) or []:
                self._finalize_block(b)
        # 3) 填 inputs
        for n in self.nodes:
            self._fill_inputs(n)
        return self

    def _finalize_block(self, b):
        outs = self._outputs_of(b)
        if outs is None:
            b["data"].pop("outputs", None)
        else:
            b["data"]["outputs"] = outs
        self.registry.register(b["id"], outs or [])
        self._fill_inputs(b)
        b.pop("_outputs_raw", None)
        b.pop("_input_spec", None)
        b.pop("_raw_kw", None)
        b.pop("_title", None)
        b.pop("_desc", None)
        b.pop("_sub", None)
        b.pop("_icon", None)

    def _outputs_of(self, n):
        t = n["type"]
        kw = n.get("_raw_kw") or {}
        # 逃生舱：整块 data 由规格提供（用于未实测类型的节点，从画布复制一次即可）
        if kw.get("raw_data"):
            return copy.deepcopy(kw["raw_data"]).get("outputs")
        if t in ("2", "8", "13"):
            # 实测：type 2（结束）13/13、type 8（选择器）12/12 没有 outputs 键；
            # type 13（输出节点，原消息节点）实测也【没有】outputs 键，只有 inputs。
            # 多写这个键会破坏结构一致性。
            return None
        if t == "6":
            # 知识库检索的默认输出（实测平台真实默认）：outputList[{output, documentId}]
            # 规格里显式给了 outputs 就用规格的（WF-8 的自定义名也被平台接受过）
            outs = norm_outputs(n.get("_outputs_raw"))
            return outs or [{"type": "list", "name": "outputList",
                             "schema": {"type": "object", "schema": [
                                 {"type": "string", "name": "output"},
                                 {"type": "string", "name": "documentId"}]}}]
        if t == "30":
            # 输入节点：outputs 是它对外暴露的变量（实测样例为 [{type:string, name:input, required:true}]）
            outs = norm_outputs(n.get("_outputs_raw"))
            return outs or [{"type": "string", "name": "input", "required": True}]
        if t == "21":
            # 循环节点的 outputs 是「name + input(ref 到循环体内某节点)」形态（实测）
            kw = n.get("_raw_kw") or {}
            lo = kw.get("loop_output")
            if not lo:
                outs_raw = n.get("_outputs_raw")
                if outs_raw and all(isinstance(x, dict) and "input" in x for x in outs_raw):
                    return outs_raw
                self.warnings.append(
                    f"循环节点 {n['id']} 未给 loop_output，循环没有对外输出。"
                    f"规格里加 \"loop_output\": {{\"name\":\"out\",\"block\":\"<循环体内节点id>\",\"var\":\"output\",\"type\":\"list\",\"items\":\"string\"}}")
                return None
            name = lo.get("name", "out")
            typ = _norm_type(lo.get("type", "list"))
            items = _norm_type(lo.get("items", "string"))
            bid, var = str(lo["block"]), lo.get("var", "output")
            # 实测：循环 outputs 里 rawMeta.type 写 1（平台的既有写法，不要“修正”）
            vobj = {"type": "ref",
                    "content": {"source": "block-output", "blockID": bid, "name": var},
                    "rawMeta": {"type": 1}}
            inp = {"type": typ, "value": vobj}
            if typ == "list":
                inp["schema"] = {"type": items}
            return [{"name": name, "input": inp}]
        if t == "32":
            # 变量聚合的输出名固定 Group1/Group2…（官方），类型由组内变量推出
            outs = norm_outputs(n.get("_outputs_raw"))
            if not outs:
                outs = []
                for g in (kw.get("merge_groups") or []):
                    gname = g.get("name", "Group1")
                    typ, items = "string", None
                    for v in (g.get("variables") or []):
                        if isinstance(v, str) and REF_RE.match(v):
                            m = REF_RE.match(v)
                            it, iitems, _isch = self.registry.lookup(m.group(1), m.group(2), [])
                            if it:
                                typ, items = it, iitems
                                break
                        elif isinstance(v, dict) and v.get("type"):
                            typ, items = _norm_type(v["type"]), v.get("items")
                            break
                    o = {"type": typ, "name": gname}
                    if typ == "list":
                        o["schema"] = {"type": items or "string"}
                    outs.append(o)
            return outs
        outs = norm_outputs(n.get("_outputs_raw"))
        if t == "1":       # 开始节点：加 assistType
            for o in outs:
                if o["name"].endswith("_date") and "assistType" not in o:
                    o["assistType"] = 10000
            return outs
        if t == "18":
            return outs or [
                {"type": "string", "name": "USER_RESPONSE", "required": True,
                 "description": "用户本轮对话输入内容"},
                {"type": "list", "name": "QUESTION_DATA", "required": True,
                 "description": "问题列表",
                 "schema": {"type": "object", "schema": [
                     {"type": "string", "name": "content_type"},
                     {"type": "string", "name": "content"}]}}]
        if t == "22":
            return outs or [{"type": "integer", "name": "classificationId"}]
        if t == "28":
            return outs if outs is not None else []      # 实测批处理 outputs 为空数组
        if t in ("12", "44"):
            return outs or [{"type": "list", "name": "outputList",
                             "schema": {"type": "object", "schema": []}},
                            {"type": "integer", "name": "rowNum"}]
        if t == "58":
            return outs or [{"type": "string", "name": "output"}]
        if t == "59":
            return outs or [{"type": "object", "name": "output", "schema": []}]
        if t == "45":
            return outs or [{"type": "string", "name": "body"},
                            {"type": "integer", "name": "statusCode"},
                            {"type": "string", "name": "headers"}]
        if t in ("40", "60", "66"):
            # 实测：变量赋值 / 知识库删除 / 长期记忆写入 都只输出一个 isSuccess
            return outs or [{"type": "boolean", "name": "isSuccess"}]
        if t == "27":
            # 实测：知识库写入输出 documentId / fileName / fileUrl
            return outs or [{"type": "string", "name": "documentId"},
                            {"type": "string", "name": "fileName"},
                            {"type": "string", "name": "fileUrl"}]
        if t == "67":
            # 实测：长期记忆检索输出 outputList（每项含 output / date）
            return outs or [{"type": "list", "name": "outputList",
                             "schema": {"type": "object", "schema": [
                                 {"type": "string", "name": "output"},
                                 {"type": "string", "name": "date"}]}}]
        if t in ("42", "43", "46"):
            # 数据库节点强制标准输出
            if not outs:
                outs = [{"type": "list", "name": "outputList",
                         "schema": {"type": "object", "schema": []}},
                        {"type": "integer", "name": "rowNum"}]
            for o in outs:
                if o["name"] == "outputList" and "schema" not in o:
                    o["schema"] = {"type": "object", "schema": []}
            return outs
        return outs

    def _fill_inputs(self, n):
        t = n["type"]
        spec = n.get("_input_spec") or {}
        kw = n.get("_raw_kw") or {}

        # 逃生舱：未实测类型的节点，整块 data 由规格提供（画布上复制一次，之后批量复用）
        if kw.get("raw_data"):
            rd = copy.deepcopy(kw["raw_data"])
            rd["inputs"] = self._patch_raw_inputs(rd.get("inputs") or {}, spec)
            n["data"] = rd
            n["data"].setdefault("nodeMeta", {})
            if n.get("_title"):
                n["data"]["nodeMeta"]["title"] = n["_title"]
            self._cleanup_node(n)
            bounds = {
                "x": n["meta"]["position"]["x"] - 180,
                "y": n["meta"]["position"]["y"],
                "width": kw.get("bounds", {}).get("width", 360),
                "height": kw.get("bounds", {}).get("height", BOUNDS_H.get(t, 150)),
            }
            n["_temp"] = {"bounds": bounds, "externalData": {
                "icon": n["data"]["nodeMeta"].get("icon", ""),
                "description": n["data"]["nodeMeta"].get("description", ""),
                "title": n["data"]["nodeMeta"].get("title", ""),
                "mainColor": n["data"]["nodeMeta"].get("mainColor", "#5C62FF")}}
            return

        _extra = dict(kw.get("extra_external") or {})
        if t in ("13", "30"):
            # 实测：输入/输出节点的 _temp.externalData 带 isImageflow 键
            _extra.setdefault("isImageflow", bool(kw.get("is_imageflow", False)))
        meta_blk = _meta_block(n["id"], t, n.get("_title", ""),
                               n.get("_desc"), n.get("_icon"), n.get("_sub"),
                               extra_external=_extra or None)
        inputs = {}

        if t == "1":
            inputs = {}
            tp = kw.get("trigger_parameters")
            if tp is None and kw.get("sync_trigger_params"):
                # 实测：较新的平台会把 outputs 镜像进 trigger_parameters（2 份样本如此），
                # 较老的为 []（11 份）。两种都能粘，默认保持 []（已验证安全）。
                tp = copy.deepcopy(n["data"].get("outputs") or [])
            n["data"]["trigger_parameters"] = tp if tp is not None else []
        elif t == "2":
            terminate = kw.get("terminate_plan", "returnVariables")
            inputs["terminatePlan"] = terminate
            if terminate == "useAnswerContent":
                inputs["streamingOutput"] = bool(kw.get("streaming_output", False))
            inputs["inputParameters"] = _expand_inputs(spec, self.registry, n["id"], self.warnings)
            if terminate == "useAnswerContent" and kw.get("content") is not None:
                inputs["content"] = lit(kw["content"], "string")
        elif t == "3":
            inputs["inputParameters"] = _expand_inputs(spec, self.registry, n["id"], self.warnings)
            inputs["llmParam"] = self._llm_param(kw)
            inputs["fcParamVar"] = {"knowledgeFCParam": {}}
            inputs["settingOnError"] = kw.get("setting_on_error",
                                              {"processType": 1, "timeoutMs": 180000, "retryTimes": 0})
        elif t == "4":
            inputs["apiParam"] = self._api_param(kw)
            inputs["inputParameters"] = _expand_inputs(spec, self.registry, n["id"], self.warnings)
            inputs["settingOnError"] = kw.get("setting_on_error",
                                              {"processType": 1, "timeoutMs": 180000, "retryTimes": 0})
        elif t == "5":
            inputs["inputParameters"] = _expand_inputs(spec, self.registry, n["id"], self.warnings)
            inputs["code"] = kw.get("code", "")
            inputs["language"] = kw.get("language", 3)
            inputs["settingOnError"] = kw.get("setting_on_error",
                                              {"processType": 1, "timeoutMs": 60000, "retryTimes": 0})
        elif t == "6":
            inputs["datasetParam"] = self._dataset_param(kw)
            inputs["inputParameters"] = self._kb_input_params(spec, kw, n["id"])
        elif t == "8":
            inputs["branches"] = self._branches(kw)
        elif t == "9":
            # 工作流（子工作流）节点 —— 实测 4/4 结构一致
            defs = kw.get("input_defs") or []
            inputs["inputDefs"] = [
                {"input": {}, "name": d["name"],
                 "required": bool(d.get("required", True)),
                 "type": _norm_type(d.get("type", "string"))}
                for d in defs
            ]
            inputs["inputParameters"] = _expand_inputs(spec, self.registry, n["id"], self.warnings)
            inputs["settingOnError"] = kw.get("setting_on_error", {})
            inputs["spaceId"] = str(kw.get("sub_space_id") or self.space_id)
            inputs["type"] = int(kw.get("sub_type", 0))
            inputs["workflowId"] = str(kw.get("sub_workflow_id", ""))
            inputs["workflowVersion"] = str(kw.get("sub_workflow_version", ""))
        elif t == "18":
            # 问答节点 —— 注意 llmParam 是【对象】不是数组
            inputs["llmParam"] = self._obj_llm_param(kw, kind="question")
            inputs["inputParameters"] = _expand_inputs(spec, self.registry, n["id"], self.warnings)
            inputs["extra_output"] = bool(kw.get("extra_output", False))
            inputs["answer_type"] = kw.get("answer_type", "text")
            inputs["option_type"] = kw.get("option_type", "static")
            inputs["dynamic_option"] = {"type": "string", "value": {
                "type": "ref", "content": {"source": "block-output", "blockID": "", "name": ""}}}
            inputs["question"] = kw.get("question", "")
            inputs["options"] = [{"name": o} for o in (kw.get("options") or ["", ""])]
            inputs["limit"] = int(kw.get("limit", 3))
        elif t == "22":
            inputs["chatHistorySetting"] = {
                "enableChatHistory": bool(kw.get("enable_chat_history", False)),
                "chatHistoryRound": int(kw.get("chat_history_round", 3))}
            inputs["inputParameters"] = _expand_inputs(spec, self.registry, n["id"], self.warnings)
            inputs["llmParam"] = self._obj_llm_param(kw, kind="intent",
                                                     params=inputs["inputParameters"])
            inputs["intents"] = [{"name": x} for x in (kw.get("intents") or [""])]
            inputs["mode"] = kw.get("mode", "top_speed")
            inputs["version"] = str(kw.get("intent_version", "2"))
            inputs["settingOnError"] = kw.get("setting_on_error", {
                "processType": 1, "timeoutMs": 60000, "retryTimes": 0})
        elif t == "28":
            inputs["concurrentSize"] = {"type": "integer", "value": {
                "type": "literal", "content": str(kw.get("concurrent_size", 10))}}
            inputs["batchSize"] = {"type": "integer", "value": {
                "type": "literal", "content": str(kw.get("batch_size", 100))}}
            inputs["inputParameters"] = _expand_inputs(spec, self.registry, n["id"], self.warnings)
        elif t == "12":
            dbid = str(kw.get("database_id", ""))
            self._use_db(dbid)
            inputs["inputParameters"] = _expand_inputs(spec, self.registry, n["id"], self.warnings)
            inputs["databaseInfoList"] = [{"databaseInfoID": dbid}] if dbid else []
            # ⚠️ SQL 文本的字段名**未证实**（平台样本里该节点未配置 SQL）。
            #    不猜、不自动生成 —— 需要时用 raw_extra 原样注入实测过的字段。
            if kw.get("raw_extra"):
                inputs.update(kw["raw_extra"])
            for _k in ("sql", "sqlText", "query", "statement"):
                if kw.get(_k):
                    self.warnings.append(
                        f"节点 {n['id']} 的 {_k!r} 被忽略 —— SQL 文本字段名未证实，"
                        f"请用 raw_extra 传实测到的字段名")
        # 实测（真实画布样本）：删除数据/更新数据的条件左侧同样是**字段名**，与查询一致
        elif t == "44":
            dbid = str(kw.get("database_id", ""))
            self._use_db(dbid)
            inputs["databaseInfoList"] = [{"databaseInfoID": dbid}] if dbid else []
            inputs["deleteParam"] = {"condition": self._db_condition(
                {"where": kw.get("where", []), "logic": kw.get("logic", "AND")},
                table="delete")["condition"]}
        elif t == "45":
            # ⚠️ HTTP 节点的 url/headers/query 结构未实测（样本未配置），
            #    这里只保证已观察到的字段，其余用 raw_extra 原样带上
            inputs["apiInfo"] = {"method": kw.get("method", "GET")}
            if kw.get("url"):
                inputs["apiInfo"]["url"] = kw["url"]
            inputs["body"] = kw.get("body") or {
                "bodyType": "EMPTY",
                "bodyData": {"binary": {"fileURL": {"type": "string", "value": {
                    "type": "ref", "content": {"source": "block-output",
                                               "blockID": "", "name": ""}}}}}}
            inputs["auth"] = kw.get("auth") or {
                "authType": "BEARER_AUTH", "authData": {"customData": {"addTo": "header"}}}
            inputs["setting"] = kw.get("setting") or {"timeout": 120, "retryTimes": 3}
            inputs["settingOnError"] = kw.get("setting_on_error", {})
            if kw.get("raw_extra"):
                inputs.update(kw["raw_extra"])
            # 实测：HTTP 节点把这两项放在 data 层级（不在 data.inputs 里）
            n["_data_level"] = {"inputParameters": _expand_inputs(
                spec, self.registry, n["id"], self.warnings),
                "settingOnError": kw.get("setting_on_error", {})}
        elif t in ("58", "59"):
            inputs["inputParameters"] = _expand_inputs(spec, self.registry, n["id"], self.warnings)
        elif t == "30":
            # 输入节点（中间过程信息输入）。实测 inputs 只有 outputSchema 一个键，
            # 而且它是把 outputs 数组 **序列化成 JSON 字符串** 塞进去的 —— 不是嵌套对象。
            outs = n["data"].get("outputs") or []
            inputs["outputSchema"] = json.dumps(outs, ensure_ascii=False,
                                                separators=(",", ":"))
            if kw.get("raw_extra"):
                inputs.update(kw["raw_extra"])
        elif t == "13":
            # 输出节点（原名「消息节点」）。实测无 outputs 键，只有 inputs 五个字段。
            inputs["streamingOutput"] = bool(kw.get("streaming_output", False))
            inputs["callTransferVoice"] = bool(kw.get("call_transfer_voice", True))
            inputs["chatHistoryWriting"] = kw.get("chat_history_writing", "historyWrite")
            # ⚠️ 实测：这个位置的 value 里【不带 rawMeta】，与其他节点惯例不同，照抄
            inputs["content"] = {
                "type": "string",
                "value": {"type": "literal",
                          "content": kw.get("content", "{{output}}")}}
            inputs["inputParameters"] = _expand_inputs(spec, self.registry,
                                                      n["id"], self.warnings)
            if kw.get("raw_extra"):
                inputs.update(kw["raw_extra"])
        elif t == "40":
            # 变量赋值。⚠️ 实测样本是【未配置态】：inputParameters=[{}]、variableTypeMap={}。
            #    「已配置」时的行结构本技能尚未证实 —— 配置后请复制一份核对。
            raw_ip = kw.get("input_parameters_raw")
            if raw_ip is not None:
                inputs["inputParameters"] = raw_ip
            elif spec:
                inputs["inputParameters"] = _expand_inputs(spec, self.registry,
                                                          n["id"], self.warnings)
            else:
                inputs["inputParameters"] = [{}]
            inputs["variableTypeMap"] = kw.get("variable_type_map", {})
            if kw.get("raw_extra"):
                inputs.update(kw["raw_extra"])
        elif t == "66":
            # 长期记忆写入。messageList 的 value.content 是 **JSON 字符串**（与输入节点同款手法）。
            inputs["memoryInfoList"] = kw.get("memory_info_list", [])
            ip = _expand_inputs(spec, self.registry, n["id"], self.warnings)
            if not any(p.get("name") == "messageList" for p in ip):
                ml = kw.get("message_list")
                if not isinstance(ml, str):
                    if ml is None:
                        ml = [{"role": "user", "content": ""},
                              {"role": "assistant", "content": ""}]
                    ml = json.dumps(ml, ensure_ascii=False, indent=2)
                ip = [{"name": "messageList", "input": {
                    "type": "list",
                    "value": {"type": "literal", "content": ml,
                              "rawMeta": {"type": 103}},
                    "schema": {"type": "object", "schema": [
                        {"name": "role", "type": "string"},
                        {"name": "content", "type": "string"}]}}}] + ip
            inputs["inputParameters"] = ip
            inputs["memoryInfoList"] = kw.get("memory_info_list", [])
        elif t == "67":
            # 长期记忆检索。实测只观察到 limit（默认 20）。
            inputs["memoryInfoList"] = kw.get("memory_info_list", [])
            ip = _expand_inputs(spec, self.registry, n["id"], self.warnings)
            if not any(p.get("name") == "limit" for p in ip):
                try:
                    lim = int(kw.get("limit", 20))
                except (TypeError, ValueError):
                    lim = 20
                ip.append({"name": "limit", "input": {
                    "type": "integer",
                    "value": {"type": "literal", "content": lim,
                              "rawMeta": {"type": 2}}}})
            inputs["inputParameters"] = ip
        elif t in ("27", "60"):
            # 知识库写入(27) / 知识库删除(60)
            inputs["inputParameters"] = _expand_inputs(spec, self.registry,
                                                      n["id"], self.warnings)
            inputs["datasetParam"] = self._dataset_write_param(kw, with_doc=(t == "27"))
            if t == "27":
                inputs["actionType"] = kw.get("action_type", 0)
                inputs["strategyParam"] = kw.get("strategy_param",
                                                 {"indexStrategy": {}})
                inputs["volcanoTab"] = kw.get("volcano_tab", [])
            if kw.get("raw_extra"):
                inputs.update(kw["raw_extra"])
        elif t == "15":
            inputs["method"] = kw.get("method", "concat")
            inputs["inputParameters"] = _expand_inputs(spec, self.registry, n["id"], self.warnings)
            inputs["concatParams"] = self._concat_params(kw)
        elif t == "21":
            inputs["inputParameters"] = _expand_inputs(spec, self.registry, n["id"], self.warnings)
            inputs["loopCount"] = {"type": "integer",
                                   "value": lit(kw.get("loop_count", 10), "integer")}
            inputs["loopType"] = kw.get("loop_type", "array")
            inputs["variableParameters"] = []
        elif t == "32":
            inputs["mergeGroups"] = self._merge_groups(kw, n["id"])
        elif t in ("42", "43", "46"):
            self._db_node(inputs, kw, t)
        else:
            raise ValueError(f"类型 {t} 的组装尚未实现")

        n["data"]["nodeMeta"] = meta_blk["_nodeMeta"]
        if t == "9":
            # 实测：工作流节点的 nodeMeta 只有 description/icon/isImageflow/title，无 subTitle/mainColor
            n["data"]["nodeMeta"] = {
                "description": n["data"]["nodeMeta"]["description"],
                "icon": n["data"]["nodeMeta"]["icon"],
                "isImageflow": bool(kw.get("is_imageflow", False)),
                "title": n["data"]["nodeMeta"]["title"],
            }
        if t == "4":
            # 插件节点：nodeMeta 用全小写 subtitle
            n["data"]["nodeMeta"].pop("subTitle", None)
            sub = kw.get("subtitle") or n.get("_sub") or kw.get("api", {}).get("pluginName", "")
            api_name = kw.get("api", {}).get("apiName", "")
            n["data"]["nodeMeta"]["subtitle"] = f"{sub}:{api_name}" if sub and api_name else (sub or "")
        n["data"]["inputs"] = inputs
        if n.get("_data_level"):
            n["data"].update(n["_data_level"])
            n.pop("_data_level", None)
        if t == "1":
            # 实测：开始节点没有 inputs 键，只有 outputs + trigger_parameters
            n["data"].pop("inputs", None)
        if t == "3":
            n["data"]["version"] = "3"
        if t == "5":
            n["data"]["version"] = "v2"

        # 循环体 / 批处理体（两者都是顶层 blocks + 顶层 edges + canvasPosition）
        if t in ("21", "28"):
            blocks = []
            for b in kw.get("blocks", []) or []:
                b["meta"]["position"] = dict(b["meta"]["position"])
                blocks.append(b)
            n["blocks"] = blocks
            inner = []
            for e in kw.get("inner_edges", []) or []:
                if isinstance(e, (list, tuple)):
                    ee = {"sourceNodeID": str(e[0]), "targetNodeID": str(e[1])}
                    if len(e) > 2 and e[2]:
                        ee["sourcePortID"] = str(e[2])
                    if len(e) > 3 and e[3]:
                        ee["targetPortID"] = str(e[3])
                    inner.append(ee)
                else:
                    inner.append(e)
            if inner:
                n["edges"] = inner      # 实测：平台在空的时候**不写**这个键

        # 清内部字段
        n.pop("_outputs_raw", None)
        n.pop("_input_spec", None)
        n.pop("_raw_kw", None)
        n.pop("_title", None)
        n.pop("_desc", None)
        n.pop("_sub", None)
        n.pop("_icon", None)
        n["_temp"] = meta_blk["_temp"]
        n["_temp"]["bounds"]["x"] = n["meta"]["position"]["x"] - BOUNDS_W / 2
        n["_temp"]["bounds"]["y"] = n["meta"]["position"]["y"]
        # 一部分节点的高度随「配置行数」变化 —— 用实测公式覆盖基准值
        _dh = self._dyn_bounds_h(t, inputs)
        if _dh is not None:
            n["_temp"]["bounds"]["height"] = _dh
        if t in ("21", "28") and kw.get("canvas_position"):
            n["meta"]["canvasPosition"] = dict(kw["canvas_position"])
        if t == "9":
            # 实测：工作流节点的 externalData 缓存了「子工作流」的元数据（画布右侧面板用它渲染）。
            # 缺了不影响执行（平台会按 workflowId 重新拉），但补齐更接近原生。
            wfid = str(kw.get("sub_workflow_id", ""))
            ver = str(kw.get("sub_workflow_version", ""))
            ed = {
                "description": n["data"]["nodeMeta"]["description"],
                "icon": n["data"]["nodeMeta"]["icon"],
                "isImageflow": n["data"]["nodeMeta"]["isImageflow"],
                "title": n["data"]["nodeMeta"]["title"],
                "mainColor": MAIN_COLOR["9"],
                "workflow_id": wfid,
                "name": kw.get("sub_workflow_name", kw.get("sub_workflow_title", "")),
                "desc": n["data"]["nodeMeta"]["description"],
                "space_id": str(kw.get("sub_space_id") or self.space_id),
                "flow_mode": 0,
                "end_type": 0,
                "is_project": False,
                "flow_version": ver,
                "latest_flow_version": ver,
                "latestVersion": ver,
                "flow_version_desc": "",
                "latest_flow_version_desc": "",
                "version": "",
                "output_nodes": [],
                "plugin_id": str(kw.get("sub_plugin_id", "")),
                "inputsDefinition": n["data"]["inputs"]["inputDefs"],
            }
            ed.update(kw.get("sub_workflow_meta") or {})
            n["_temp"]["externalData"] = ed

    # ---- 各类型内部参数 ----
    def _llm_param(self, kw):
        bag = {}
        for k, v in kw.get("llm_param", {}).items():
            bag[k] = v
        defaults = {
            "modelType": (DEFAULT_MODEL_TYPE, "integer", 2),
            "modleName": (kw.get("model", DEFAULT_MODEL), "string", 1),
            "generationDiversity": ("balance", "string", 1),
            "frequencyPenalty": ("0", "float", 4),
            "maxTokens": ("4096", "integer", 2),
            "spCurrentTime": (False, "boolean", 3),
            "spAntiLeak": (False, "boolean", 3),
            "responseFormat": ("2", "integer", 2),
            "prompt": (kw.get("prompt", ""), "string", 1),
            "enableChatHistory": (False, "boolean", 3),
            "chatHistoryRound": ("3", "integer", 2),
            "systemPrompt": (kw.get("system_prompt", ""), "string", 1),
            "stableSystemPrompt": ("", "string", 1),
            "canContinue": (False, "boolean", 3),
            "loopPromptVersion": ("", "string", 1),
            "loopPromptName": ("", "string", 1),
            "loopPromptId": ("", "string", 1),
        }
        out = []
        for key in LLM_PARAM_ORDER:
            if key == "parameters":
                out.append({"name": "parameters", "input": {
                    "value": {"type": "object_ref"},
                    "type": "object",
                    "schema": [{"name": "max_completion_tokens", "input": {
                        "type": "integer",
                        "value": lit("0", "integer")}}]}})
                continue
            if key in bag:
                content, typ, rc = bag[key], _norm_type(infer_type(bag[key])), None
                if key in ("spCurrentTime", "spAntiLeak", "canContinue", "enableChatHistory"):
                    typ = "boolean"
                elif key in ("modelType", "maxTokens", "chatHistoryRound", "responseFormat"):
                    typ = "integer"
                elif key == "frequencyPenalty":
                    typ = "float"
                else:
                    typ = "string"
                out.append({"name": key, "input": {"type": typ,
                                                   "value": lit(content, typ)}})
                continue
            content, typ, rc = defaults[key]
            out.append({"name": key, "input": {"type": typ, "value": lit(content, typ)}})
        return out

    def _obj_llm_param(self, kw, kind="question", params=None):
        """
        问答(18) / 意图识别(22) 的 llmParam 是**普通对象**，
        而大模型(3) 的是 `[{name, input}]` **数组**。两者键名也不同：
          · 这里是 `modelName`（拼写正确）；type 3 是平台拼错的 `modleName`
        ⚠️ 容易踩：把 type 3 的数组结构套到这两个节点上，会粘贴失败。
        """
        over = dict(kw.get("llm_param") or {})
        model = kw.get("model", "豆包·2.0·lite")
        try:
            mtype = int(kw.get("model_type", 1772546477))
        except (TypeError, ValueError):
            mtype = 1772546477
        base = {
            "modelType": mtype,
            "modelName": model,
            "generationDiversity": "balance" if kind == "question" else "default_val",
            "frequencyPenalty": 0,
            "maxTokens": 4096 if kind == "question" else 100,
            "maxOutputTokens": 4096,
            "store": True,
            "cachingExpireTime": 259200,
            "responseFormat": 2,
            "parameters": {"max_completion_tokens": 0},
        }
        if kind == "question":
            base["systemPrompt"] = kw.get("system_prompt", "")
        else:
            base.update({"temperature": 0.3, "topP": 1, "thinkingType": "disabled"})
            base["parameters"]["reasoning_effort"] = "minimal"
            # ⚠️ prompt 默认引用「本节点第一个输入参数的 name」，**不是**写死 `{{query}}`。
            #    踩过的坑：输入参数名是 `data` 而 prompt 写死 `{{query}}` → 运行时取不到值，
            #    平台却不报错（它只是一段字符串）。这类断链由校验器 W19 兜底。
            dft = next((p.get("name") for p in (params or []) if p.get("name")), "query")
            base["prompt"] = {"type": "string", "value": {
                "type": "literal", "content": kw.get("prompt") or ("{{%s}}" % dft)}}
            base["systemPrompt"] = {"type": "string", "value": {
                "type": "literal", "content": kw.get("system_prompt", "")}}
            base["enableChatHistory"] = bool(kw.get("enable_chat_history", False))
            base["chatHistoryRound"] = int(kw.get("chat_history_round", 3))
        for k, v in over.items():
            if not str(k).startswith("_"):
                base[k] = v
        return base

    def _dyn_bounds_h(self, t, inputs):
        """
        按实测公式计算「随配置行数变化」的节点高度。
        返回 None 表示该类节点高度恒定，用 BOUNDS_H 里的基准值。

        公式来源：14 份真实样本拟合（2026-09-20）：
          意图识别 22 ：150 + 26 × 意图数      （1→176、3→228）
          变量聚合 32 ： 54 + 60 × 分组数      （1→114、2→174；与组内变量数无关）
          查询数据 43 ：106 + 48 × 条件行数    （1→154、2→202、3→250）
        对照组（恒定，已验证与行数无关）：大模型 3 / 新增数据 46 / 代码 5 / 结束 2。
        """
        if t == "22":
            return 150 + 26 * len(inputs.get("intents") or [])
        if t == "32":
            n = len(inputs.get("mergeGroups") or [])
            return 54 + 60 * n if n else None
        if t == "43":
            sp = inputs.get("selectParam") or {}
            cl = (sp.get("condition") or {}).get("conditionList") or []
            return 106 + 48 * len(cl) if cl else None
        return None

    def _dataset_write_param(self, kw, with_doc=False):
        """
        知识库写入(27) / 知识库删除(60) 的 `inputs.datasetParam`。
        实测结构四/三项：
          datasetList       list<string>            ← 真实知识库 ID，粘贴时强校验
          documentID        string（仅写入有）       ⚠️ 它的 rawMeta 是 {"fileName":""}，不是 {"type":N}
          datasetType       integer（0）
          VolcanoInfoList   list<object{datasetID, volcanoServiceID}>
        规格里用 `dataset_ids` / `document_id` / `dataset_type` / `volcano_info_list` 提供。
        """
        ids = kw.get("dataset_ids")
        if ids is None:
            ids = kw.get("dataset_list") or []
        if isinstance(ids, str):
            ids = [ids]
        out = [{"name": "datasetList",
                "input": {"type": "list", "schema": {"type": "string"},
                          "value": {"type": "literal", "content": list(ids)}}}]
        if with_doc:
            out.append({"name": "documentID",
                        "input": {"type": "string",
                                  "value": {"type": "literal",
                                            "content": kw.get("document_id", ""),
                                            "rawMeta": {"fileName": ""}}}})
        out.append({"name": "datasetType",
                    "input": {"type": "integer",
                              "value": {"type": "literal",
                                        "content": int(kw.get("dataset_type", 0))}}})
        out.append({"name": "VolcanoInfoList",
                    "input": {"type": "list",
                              "schema": {"type": "object", "schema": [
                                  {"type": "string", "name": "datasetID"},
                                  {"type": "string", "name": "volcanoServiceID"}]},
                              "value": {"type": "literal",
                                        "content": list(kw.get("volcano_info_list") or [])}}})
        if not ids:
            self.warnings.append(
                "知识库写入/删除节点的 datasetList 为空 —— 知识库 ID 只能从画布取，"
                "粘贴时平台会强校验存在性，空着或填错都会失败。规格里用 \"dataset_ids\" 传真实 ID。")
        return out

    def _api_param(self, kw):
        api = kw.get("api", {})
        vals = {
            "apiID": api.get("apiID", ""), "apiName": api.get("apiName", ""),
            "pluginID": api.get("pluginID", ""), "pluginName": api.get("pluginName", ""),
            "pluginVersion": api.get("pluginVersion", ""), "tips": api.get("tips", ""),
            "outDocLink": api.get("outDocLink", ""),
        }
        return [{"name": k, "input": {"type": "string",
                                      "value": {"content": vals[k], "rawMeta": {"type": 1},
                                                "type": "literal"}}}
                for k in API_PARAM_ORDER]

    def _db_node(self, inputs, kw, t):
        """
        数据库三兄弟（42 更新 / 43 查询 / 46 新增）的 inputs 组装。

        ⚠️ 核心原则：**「未配置态」是一等公民，也是合法目标态**

        实测（平台自己的空配置样本）：
            databaseInfoList : []                                   ← 空数组
            selectParam      : {"condition": {"logic": "AND"}}      ← 没有 conditionList
            updateParam      : {"condition": {"logic": "AND"}}
            新增数据          : **完全没有 insertParam 键**
            settingOnError   : **没有这个键**
            未配置态的字段的键（fieldList / orderByList / limit）也**省略**

        **绝不能填 `[{"databaseInfoID": ""}]`** —— 那是「有引用但 ID 为空」的畸形态。
        平台粘贴时会拿它去查资源，查不到就**阻断导入**
        （与「知识库 xxx 不存在」红条同源）。空数组则不触发任何资源查询 → 能粘。

        结论：**不选数据库也能生成可粘贴的节点**，粘上去就是画布上的「未配置节点」，
        用户在画布上再选一次库表即可。
        """
        dbid = str(kw.get("database_id", "") or "")
        self._use_db(dbid)          # 切到该表的字段映射（字段 ID 按表独立）
        inputs["databaseInfoList"] = [{"databaseInfoID": dbid}] if dbid else []

        def _empty(cfg):
            return not (cfg.get("where") or cfg.get("fields") or cfg.get("order_by")
                        or cfg.get("set") or cfg.get("limit") is not None)

        if t == "43":
            cfg = kw.get("select") or {}
            if _empty(cfg):
                # 未配置：只有 logic，连 fieldList / orderByList / limit 都不写
                inputs["selectParam"] = {"condition": {"logic": cfg.get("logic", "AND")}}
            else:
                inputs["selectParam"] = self._db_condition(cfg, table="select")
                inputs["settingOnError"] = kw.get("setting_on_error",
                                                  {"processType": 1, "timeoutMs": 60000,
                                                   "retryTimes": 0})
        elif t == "42":
            cfg = kw.get("update") or {}
            if _empty(cfg):
                inputs["updateParam"] = {"condition": {"logic": cfg.get("logic", "AND")}}
            else:
                inputs["updateParam"] = self._db_condition(cfg, table="update")
                inputs["settingOnError"] = kw.get("setting_on_error",
                                                  {"processType": 1, "timeoutMs": 60000,
                                                   "retryTimes": 0})
        else:                       # 46 新增
            rows = kw.get("insert") or []
            if rows:
                inputs["insertParam"] = {"fieldInfo": self._db_field_info(rows)}
                inputs["settingOnError"] = kw.get("setting_on_error",
                                                  {"processType": 1, "timeoutMs": 60000,
                                                   "retryTimes": 0})
            # 未配置：**完全不给 insertParam 键**（实测平台如此）

    def _dataset_param(self, kw):
        """
        知识库检索（type 6）的 `inputs.datasetParam`。

        ⚠️ 实测：**项数随「是否选了知识库」变化**
            未配置（datasetList 为空）→ **7 项**（到 VolcanoInfoList 为止）
            已配置                  → **9 项**（多 minScore、strategy）
        """
        ds = [str(x) for x in (kw.get("datasets") or [])]
        items = [
            {"name": "datasetList", "input": {"type": "list", "schema": {"type": "string"},
                                              "value": {"type": "literal", "content": ds}}},
            {"name": "topK", "input": {"type": "integer",
                                       "value": lit(str(kw.get("top_k", 5)), "integer")}},
            {"name": "useRerank", "input": {"type": "boolean",
                                            "value": lit(kw.get("use_rerank", True), "boolean")}},
            {"name": "useRewrite", "input": {"type": "boolean",
                                             "value": lit(kw.get("use_rewrite", True), "boolean")}},
            {"name": "isPersonalOnly", "input": {"type": "boolean",
                                                 "value": lit(kw.get("personal_only", True), "boolean")}},
            {"name": "datasetType", "input": {"type": "integer",
                                              "value": lit(str(kw.get("dataset_type", 0)), "integer")}},
            {"name": "VolcanoInfoList", "input": {
                "type": "list",
                "schema": {"type": "object", "schema": [
                    {"type": "string", "name": "datasetID"},
                    {"type": "string", "name": "volcanoServiceID"}]},
                "value": {"type": "literal", "content": []}}},
        ]
        if ds:
            items += [
                {"name": "minScore", "input": {"type": "float",
                                               "value": lit(str(kw.get("min_score", 0.5)), "float")}},
                {"name": "strategy", "input": {"type": "integer",
                                               "value": lit(str(kw.get("strategy", 1)), "integer")}},
            ]
        return items

    def _kb_input_params(self, spec, kw, nid):
        """
        知识库检索的 `inputs.inputParameters`。

        ⚠️ 实测顺序：**上游引用参数在前，两个开关在后**
            [Query(引用), enableChatHistory(boolean), chatHistoryRound(float)]

        且 `chatHistoryRound` 的 `input.type` 是 `"float"`，但 `content` 是**数字**（不是字符串）——
        全平台少见，照抄。
        """
        ip = _expand_inputs(spec, self.registry, nid, self.warnings)
        ip.append({"name": "enableChatHistory",
                   "input": {"type": "boolean",
                             "value": lit(bool(kw.get("enable_chat_history", False)), "boolean")}})
        ip.append({"name": "chatHistoryRound",
                   "input": {"type": "float",
                             "value": {"type": "literal",
                                       "content": kw.get("chat_history_round", 3),
                                       "rawMeta": {"type": 4}}}})
        return ip

    def _branches(self, kw):
        """
        选择器（type 8）的 `inputs.branches`。

        ⚠️ 实测（13/13 真实选择器）：`branches` **恒为 1 项**。
        平台的结构是：
            branches[0].condition = {logic, conditions[]}   ← 连到 true 端口
            否则（else）是**隐式**的，直接走 `false` 端口，不占 branches 项。
        所以规格里**只需写 1 个条件**；多写的项会被平台当成「否则如果」分支，
        而它对应的端口名本技能**未实测**（无法连线），因此这里给出警告。
        """
        specs = kw.get("branches", []) or []
        if len(specs) > 1:
            self.warnings.append(
                "选择器「%s」的 branches 有 %d 项；实测平台恒为 1 项（否则分支隐式走 false 端口）。"
                "多出的项会变成「否则如果」分支，其端口名未实测、无法连线。"
                "简单 if/else 请只写 1 个条件。"
                % (kw.get("_title") or kw.get("title") or "?", len(specs)))
        brs = []
        for b in specs:
            conds = []
            for c in b.get("conditions", []) or []:
                left = c.get("left")
                right = c.get("right")
                ltyp = c.get("type") or (infer_type(left) if not _is_ref_shorthand(left) else "string")
                ltyp = _norm_type(ltyp)
                lval, litems, lschema = self._cond_value(left, ltyp)
                rval = lit(right, ltyp)
                conds.append({"operator": c.get("operator", 1),
                              "left": {"input": _input_obj(ltyp, lval, litems, lschema)},
                              "right": {"input": _input_obj(ltyp, rval, litems)}})
            brs.append({"condition": {"logic": b.get("logic", 2), "conditions": conds}})
        return brs

    def _cond_value(self, v, typ):
        if isinstance(v, dict) and "ref" in v:
            m = REF_RE.match(str(v["ref"]))
            bid, vname = m.group(1), m.group(2)
            t, items, schema = self.registry.lookup(bid, vname, self.warnings)
            if t != typ and typ == "string":
                typ = t
            return ref(bid, vname, typ, items), items, schema
        if isinstance(v, str) and REF_RE.match(v):
            m = REF_RE.match(v)
            bid, vname = m.group(1), m.group(2)
            t, items, schema = self.registry.lookup(bid, vname, self.warnings)
            return ref(bid, vname, typ, items), items, schema
        return lit(v, typ), None, None

    def _concat_params(self, kw):
        chars = kw.get("item_chars") or [
            {"isDefault": True, "label": "换行", "value": "\n"},
            {"isDefault": True, "label": "制表符", "value": "\t"},
            {"isDefault": True, "label": "句号", "value": "。"},
            {"isDefault": True, "label": "逗号", "value": "，"},
            {"isDefault": True, "label": "分号", "value": "；"},
        ]
        return [
            {"name": "concatResult", "input": {"type": "string",
                                               "value": lit(kw.get("concat_result", ""), "string")}},
            {"name": "arrayItemConcatChar", "input": {"type": "string",
                                                      "value": lit(kw.get("array_char", "，"), "string")}},
            {"name": "allArrayItemConcatChars", "input": {
                "type": "list",
                "schema": {"type": "object", "schema": [
                    {"type": "string", "name": "label", "required": True},
                    {"type": "string", "name": "value", "required": True},
                    {"type": "boolean", "name": "isDefault", "required": True}]},
                "value": {"type": "literal", "content": chars}}},
        ]

    def _merge_groups(self, spec, nid):
        groups = []
        for g in spec.get("merge_groups", []) or []:
            name = g.get("name", "Group1")
            vars_ = []
            for v in g.get("variables", []) or []:
                if isinstance(v, str) and REF_RE.match(v):
                    m = REF_RE.match(v)
                    bid, vname = m.group(1), m.group(2)
                    t, items, schema = self.registry.lookup(bid, vname, self.warnings)
                    vars_.append(_input_obj(t, ref(bid, vname, t, items), items, schema))
                else:
                    t = _norm_type(v.get("type", "string"))
                    vars_.append(_input_obj(t, lit(v.get("value"), t), v.get("items")))
            groups.append({"name": name, "variables": vars_})
        return groups

    def _db_condition(self, cfg, table):
        clist = []
        for grp in cfg.get("where", []) or []:
            row = []
            # ⚠️⚠️ 实测（真实画布样本 wf_onboarding 等 4 份）：条件左侧写的是**字段名**
            #      （"content":"school"），**不是字段 ID**。
            #      写成数字 ID 的话画布上那一格会显示裸数字（平台按字段名查不到）。
            #      早期生成器这里错误地调了 _as_field_id() 转成 ID —— 已修正为原样输出字段名。
            row.append({"name": "left", "input": {"type": "string",
                                                  "value": {"type": "literal",
                                                            "content": grp["field"]}}})
            row.append({"name": "operation", "input": {"type": "string",
                                                       "value": {"type": "literal",
                                                                 "content": grp.get("op", "EQUAL")}}})
            rv = grp["value"]
            vobj, _t = self._db_value(rv)
            row.append({"name": "right", "input": {"type": "string", "value": vobj}})
            clist.append(row)
        # 实测：没有条件行时，平台只写 {"logic": "AND"}，**不写 conditionList 键**。
        # 有了条件行才写 {"conditionList": [...], "logic": "AND"}。
        cond = {}
        if clist:
            cond["conditionList"] = clist
        cond["logic"] = cfg.get("logic", "AND")
        if table == "select":
            # ⚠️ 实测：fieldList / orderByList 里的 fieldID 是**数字**（1832255057921），
            #     不是字符串。写成字符串时画布「查询字段」那一栏会整列显示 undefined。
            fields = [{"fieldID": self._as_field_id_num(f), "isDistinct": False}
                      for f in cfg.get("fields", [])]
            order = [{"fieldID": self._as_field_id_num(f[0]), "isAsc": bool(f[1])}
                     for f in cfg.get("order_by", [])]
            return {"condition": cond, "fieldList": fields,
                    "limit": cfg.get("limit", 1), "orderByList": order}
        # ⚠️ 对照：insertParam/updateParam 的 fieldInfo 里 fieldID 是**字符串**
        #     （"content":"1831982593026"，实测真实样本），与 fieldList 相反，不要"统一"它们。
        return {"condition": cond, "fieldInfo": self._db_field_info(cfg.get("set", []))}

    def _as_field_id_num(self, f):
        """fieldList / orderByList 用：字段项 → **数字** ID（数字字符串转 int，字段名走 field_map）"""
        fid = self._as_field_id(f)
        s = str(fid)
        return int(s) if s.isdigit() else fid

    def _db_field_info(self, pairs):
        rows = []
        for p in pairs or []:
            fid, fval = p[0], p[1]
            vobj, typ = self._db_value(fval)
            rows.append([
                {"name": "fieldID", "input": {"type": "string",
                                              "value": {"type": "literal",
                                                        "content": self._as_field_id(fid)}}},
                {"name": "fieldValue", "input": _input_obj(typ, vobj)},
            ])
        return rows

    def _db_value(self, fval):
        # 显式引用哨兵：字段值里既可能有引用又可能有普通文本，用 __REF__ 前缀区分
        if isinstance(fval, str) and fval.startswith("__REF__"):
            fval = fval[len("__REF__"):]
        if isinstance(fval, dict) and "ref" in fval:
            m = REF_RE.match(str(fval["ref"]))
            bid, vname = m.group(1), m.group(2)
            t, items, _s = self.registry.lookup(bid, vname, self.warnings)
            return ref(bid, vname, t, items), t
        if isinstance(fval, str) and REF_RE.match(fval):
            m = REF_RE.match(fval)
            bid, vname = m.group(1), m.group(2)
            t, items, _s = self.registry.lookup(bid, vname, self.warnings)
            return ref(bid, vname, t, items), t
        return lit(fval, infer_type(fval)), infer_type(fval)

    def _as_field_id(self, f):
        """字段项 → 字符串 ID；数字直接用，字段名走 field_map"""
        if isinstance(f, (int, str)) and str(f).isdigit():
            return str(f)
        return self.resolve_field(f)

    # ---- 逃生舱辅助 ----
    def _patch_raw_inputs(self, inputs, spec):
        """在原始 inputs 里按参数名替换值（用于 raw_data 节点）"""
        if not spec:
            return inputs
        expanded = {p["name"]: p["input"] for p in
                    _expand_inputs(spec, self.registry, "raw", self.warnings)}

        def rec(o, key=None):
            if isinstance(o, dict):
                if "name" in o and "input" in o and o["name"] in expanded and key != "apiParam":
                    o["input"] = expanded[o["name"]]
                    return o
                for k, v in list(o.items()):
                    rec(v, k)
            elif isinstance(o, list):
                for v in o:
                    rec(v, key)
            return o

        return rec(inputs)

    @staticmethod
    def _cleanup_node(n):
        for k in ("_outputs_raw", "_input_spec", "_raw_kw", "_title", "_desc", "_sub", "_icon"):
            n.pop(k, None)

    def clip_bounds(self):
        """
        **顶层 `bounds`** = 所有根节点 `_temp.bounds` 的并集。

        ⚠️ 这是实测出来的硬要求（13/13 平台文件精确一致）：
        平台粘贴时要用它算落位包围盒，**缺了会静默中止 —— 按 Ctrl+V 毫无反应**。
        这是本技能踩过最贵的一个坑。
        """
        xs, ys, xe, ye = [], [], [], []
        for n in self.nodes:
            b = (n.get("_temp") or {}).get("bounds")
            if not b:
                pos = (n.get("meta") or {}).get("position") or {"x": 0, "y": 0}
                w = BOUNDS_W
                h = BOUNDS_H.get(str(n.get("type")), 150)
                b = {"x": pos["x"] - w / 2, "y": pos["y"], "width": w, "height": h}
            xs.append(b["x"]); ys.append(b["y"])
            xe.append(b["x"] + b["width"]); ye.append(b["y"] + b["height"])
        if not xs:
            return None
        return {"x": min(xs), "y": min(ys),
                "width": max(xe) - min(xs), "height": max(ye) - min(ys)}

    # ---- 输出 ----
    def to_clipboard(self):
        self.build()
        out = {
            "type": "coze-workflow-clipboard-data",
            "source": {
                "workflowId": self.workflow_id,
                "flowMode": self.flow_mode,
                "spaceId": self.space_id,
                "isDouyin": self.is_douyin,
                "host": self.host,
            },
            "json": {"nodes": self.nodes, "edges": self.edges},
        }
        b = self.clip_bounds()
        if b is not None:
            out["bounds"] = b          # ← 少了它粘贴会「毫无反应」
        return out

    def dump(self, path, indent=None):
        """
        写文件。indent=None → **单行紧凑**（平台自己的剪贴板载荷就是这个形态）。

        ⚠️ 实测教训：缩进版体积会翻倍（WF-8：93KB/2865 行 vs 平台 44KB/1 行），
        粘贴时可能出现「按了 Ctrl+V 完全没反应」。**交付给用户粘贴的一律用单行。**
        """
        self.build()
        obj = self.to_clipboard()
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(obj, ensure_ascii=False, indent=indent,
                               separators=(",", ":") if indent is None else None))
        return path

    def dumps(self, indent=None):
        self.build()
        return json.dumps(self.to_clipboard(), ensure_ascii=False, indent=indent,
                          separators=(",", ":") if indent is None else None)


def _is_ref_shorthand(v):
    return isinstance(v, str) and bool(REF_RE.match(v))
