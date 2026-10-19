#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
validate_workflow.py —— Coze 工作流剪贴板 JSON 体检（16 条规则）

    python validate_workflow.py flow.json
    python validate_workflow.py flow.json --json      # 机器可读
    python validate_workflow.py flow.json --quiet     # 只输出 error

规则清单（E=error 必修 / W=warning 建议修）见 references/05-edges-and-ports.md

E16 顶层 bounds 必须存在，且 == 所有根节点 _temp.bounds 的并集（缺了粘贴会毫无反应）
E17 根层节点必须从「开始」可达（不可达的节点永远不执行，且完全静默）
E18 意图识别的出边必须连完整：N 个 intents → branch_0…branch_{N-1} + default
E19 数据库字段三种写法：fieldList.fieldID=数字 ｜ conditionList.left=字段名 ｜ fieldInfo.fieldID=字符串
E1  节点 id（含循环体）全局唯一
E2  恰好 1 个开始(type 1) + 1 个结束(type 2)
E3  每条边的两端节点存在
E4  每个 ref 的 blockID 存在
E5  每个 ref 的变量名能在目标节点 outputs 里解析（支持点路径）
E6  代码节点：每个 return 字面量的键集合覆盖 outputs[].name
E7  代码节点：直接形参签名时，形参名与 inputParameters[].name 一致
W8  大模型节点 llmParam 含 18 个固定键
W9  插件节点 apiParam 含 7 个固定键
W10 选择器分支数与带端口出边数匹配
W11 循环/批处理节点有 blocks，且内层边含两个 inline 端口、出边带 loop-output / batch-output
W12 出现了本技能未证实过的 type 编号
W19 提示词 / 输出节点的 {{变量}} 必须在本节点 inputParameters 里存在
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from collections import Counter, defaultdict

CONFIRMED_TYPES = {"1", "2", "3", "4", "5", "6", "8", "9", "12", "13", "15", "18", "21",
                    "22", "27", "28", "30", "32", "40", "42", "43", "44", "45", "46", "58",
                    "59", "60", "66", "67"}
TYPE_NAME = {
    "1": "开始", "2": "结束", "3": "大模型", "4": "插件", "5": "代码", "6": "知识库检索",
    "8": "选择器", "9": "工作流", "12": "SQL自定义", "13": "输出",
    "15": "文本处理", "18": "问答", "27": "知识库写入", "30": "输入",
    "40": "变量赋值", "60": "知识库删除", "66": "长期记忆写入", "67": "长期记忆检索",
    "21": "循环", "22": "意图识别", "28": "批处理", "32": "变量聚合",
    "42": "更新数据", "43": "查询数据", "44": "删除数据", "45": "HTTP 请求",
    "46": "新增数据", "58": "JSON 序列化", "59": "JSON 反序列化",
}
#: 带 blocks（子画布）的类型
BLOCK_TYPES = {"21", "28"}
LLM_KEYS = ["modelType", "modleName", "generationDiversity", "frequencyPenalty", "maxTokens",
            "spCurrentTime", "spAntiLeak", "responseFormat", "parameters", "prompt",
            "enableChatHistory", "chatHistoryRound", "systemPrompt", "stableSystemPrompt",
            "canContinue", "loopPromptVersion", "loopPromptName", "loopPromptId"]
API_KEYS = ["apiID", "apiName", "pluginID", "pluginName",
            "pluginVersion", "tips", "outDocLink"]


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, rule, where, msg):
        self.items.append({"level": level, "rule": rule, "where": where, "msg": msg})

    def err(self, rule, where, msg):
        self.add("E", rule, where, msg)

    def warn(self, rule, where, msg):
        self.add("W", rule, where, msg)

    def unconfigured(self, where, msg):
        """
        「未配置态」记录 —— **不是问题**，不计入 error/warning。

        实测：平台原生支持「空配置态」节点（例如没选数据库的查询节点写
        `databaseInfoList: []`、没选知识库的检索节点写 `datasetList: []`），
        这类节点**可以正常粘贴**（不触发任何资源查询），粘上去后在画布上补配置即可。
        所以单列出来提示用户「这里是要自己补的」，而不是当成错误。
        """
        self.add("U", "-", where, msg)

    @property
    def errors(self):
        return [i for i in self.items if i["level"] == "E"]

    @property
    def warnings(self):
        return [i for i in self.items if i["level"] == "W"]

    @property
    def unconfigs(self):
        return [i for i in self.items if i["level"] == "U"]


# ------------------------------------------------------------------ 工具

def walk_refs(o, out, path=""):
    """收集所有 ref 值对象，带上 JSON 路径"""
    if isinstance(o, dict):
        if o.get("type") == "ref" and isinstance(o.get("content"), dict):
            out.append((path, o["content"]))
        for k, v in o.items():
            walk_refs(v, out, f"{path}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk_refs(v, out, f"{path}[{i}]")


def collect_all_nodes(js):
    """返回 [(node, owner_loop_id_or_None)]，含循环体"""
    res = []
    for n in js.get("nodes", []):
        res.append((n, None))
        for b in n.get("blocks", []) or []:
            res.append((b, n.get("id")))
    return res


def outputs_map(all_nodes):
    """
    建立「可被引用的变量名」表。

    注意（实测，曾因此误报）：**循环节点可被引用的名字不止 outputs，
    还包括它的 inputParameters**——循环体内通过 `<循环id>.<输入参数名>` 取当前元素（循环变量）。
    例：循环 113490 的 inputParameters = header/task_book/module，
    循环体内的文本处理节点引用 `113490.header` 是合法的。
    """
    m = {}
    for n, _owner in all_nodes:
        bag = {}
        outs = n.get("data", {}).get("outputs")
        for o in outs or []:
            if not isinstance(o, dict):
                continue
            name = o.get("name")
            if not name:
                continue
            bag[name] = o
        # 循环 / 批处理节点：把 inputParameters 也登记为可引用名
        # （子画布内通过 <本节点id>.<输入参数名> 取当前批次/当前元素）
        if str(n.get("type")) in ("21", "28"):
            for p in (n.get("data", {}).get("inputs", {}) or {}).get("inputParameters", []) or []:
                pname = p.get("name")
                if not pname or pname in bag:
                    continue
                ip = p.get("input") or {}
                ip_type, ip_schema = ip.get("type"), ip.get("schema")
                # 子画布内取到的是「当前元素」：list<T> → T
                if ip_type == "list" and isinstance(ip_schema, dict):
                    ip_type, ip_schema = ip_schema.get("type", "string"), ip_schema.get("schema")
                bag[pname] = {"name": pname, "type": ip_type,
                              "schema": ip_schema, "_from_block_input": True}
        # 工作流（子工作流）节点：inputDefs 同样可作为引用名（保守起见一并登记）
        if str(n.get("type")) == "9":
            for d in (n.get("data", {}).get("inputs", {}) or {}).get("inputDefs", []) or []:
                pname = d.get("name")
                if pname and pname not in bag:
                    bag[pname] = {"name": pname, "type": d.get("type"), "_from_input_def": True}
        m[str(n.get("id"))] = bag
    return m


def resolve_path(bag, name):
    """在输出表里解析变量名（支持 a.b / a[0].b），返回 (ok, reason)"""
    head = re.split(r"[.\[]", name)[0]
    if head not in bag:
        return False, f"节点 outputs 里没有变量 {head}"
    if head == name:
        return True, None
    tail = name[len(head):].lstrip(".")
    if not tail:
        return True, None
    cur = bag[head]
    while tail:
        m = re.match(r"^([A-Za-z_]\w*)(?:\[(\d+)\])?\.?", tail)
        if not m:
            return True, None          # 无法解析的形态（如 * 通配）→ 放行
        fname = m.group(1)
        schema = cur.get("schema")
        if isinstance(schema, list):          # object: schema 是字段数组
            nxt = next((f for f in schema if f.get("name") == fname), None)
        elif isinstance(schema, dict):        # list: schema 是元素定义
            inner = schema.get("schema")
            if isinstance(inner, list):
                nxt = next((f for f in inner if f.get("name") == fname), None)
            else:
                return True, None             # list<string> 之类的点路径，不深究
        else:
            return True, None                 # 无 schema（如 DB outputList）→ 放行
        if nxt is None:
            return False, f"在 {head} 的 schema 里找不到字段 {fname}（schema 可能为空，请人工确认）"
        cur = nxt
        tail = tail[m.end():]
    return True, None


def main_params(tree):
    """找到 main 函数，返回 (kind, names)；kind ∈ {'args','kwargs','none'}"""
    for nodex in ast.walk(tree):
        if isinstance(nodex, (ast.FunctionDef, ast.AsyncFunctionDef)) and nodex.name == "main":
            a = nodex.args
            names = [x.arg for x in a.posonlyargs + a.args if x.arg != "self"]
            if a.kwonlyargs:
                names += [x.arg for x in a.kwonlyargs]
            if names == ["args"]:
                return "args", names
            if len(names) == 1 and not names[0]:
                return "args", names
            return "kwargs", names
    return "none", []


def _dict_keys(nodex):
    """ast.Dict → 键集合；键非字面量则返回 None"""
    ks = set()
    for k in nodex.keys:
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            ks.add(k.value)
        else:
            return None
    return ks


def return_key_sets(tree):
    """
    收集 main 里所有可能被 return 的键集合。

    同时支持两种写法：
        ① return {"a": 1}                    直接返回字面量 dict
        ② ret = {"a": 1}; return ret         先赋值再返回（官方文档默认写法）
    无法静态判定时返回 [None]（调用方会降级为 warning）。
    """
    for nodex in ast.walk(tree):
        if not (isinstance(nodex, (ast.FunctionDef, ast.AsyncFunctionDef)) and nodex.name == "main"):
            continue

        # 第一遍：收集「变量名 → dict 键集合」的绑定
        binds = defaultdict(list)
        for sub in ast.walk(nodex):
            if isinstance(sub, ast.Assign) and isinstance(sub.value, (ast.Dict, ast.Name)):
                if isinstance(sub.value, ast.Dict):
                    ks = _dict_keys(sub.value)
                else:
                    ks = None
                if ks is None:
                    continue
                for tgt in sub.targets:
                    if isinstance(tgt, ast.Name):
                        binds[tgt.id].append(ks)
            elif isinstance(sub, ast.AnnAssign) and isinstance(sub.value, (ast.Dict, ast.Name)):
                if isinstance(sub.value, ast.Dict):
                    ks = _dict_keys(sub.value)
                    if ks is not None and isinstance(sub.target, ast.Name):
                        binds[sub.target.id].append(ks)

        # 第二遍：看所有 return
        res = []
        for sub in ast.walk(nodex):
            if not isinstance(sub, ast.Return):
                continue
            v = sub.value
            if v is None:
                res.append(set())
            elif isinstance(v, ast.Dict):
                res.append(_dict_keys(v))
            elif isinstance(v, ast.Name) and v.id in binds:
                got = binds[v.id]
                if len(got) == 1:
                    res.append(got[0])
                else:
                    res.append(None)      # 多次赋值 → 无法确定，放弃
            else:
                res.append(None)          # 返回变量但没有可追踪的 dict 赋值
        return res or [None]
    return [None]


# ------------------------------------------------------------------ 规则

def clip_bounds_of(nodes):
    """根节点 _temp.bounds 的并集（平台顶层 bounds 的定义，13/13 实测一致）"""
    xs, ys, xe, ye = [], [], [], []
    for n in nodes:
        b = (n.get("_temp") or {}).get("bounds")
        if not isinstance(b, dict):
            continue
        try:
            xs.append(float(b["x"])); ys.append(float(b["y"]))
            xe.append(float(b["x"]) + float(b["width"]))
            ye.append(float(b["y"]) + float(b["height"]))
        except (KeyError, TypeError, ValueError):
            continue
    if not xs:
        return None
    return {"x": min(xs), "y": min(ys),
            "width": max(xe) - min(xs), "height": max(ye) - min(ys)}


def check(js, wf_name="<flow>", envelope=None):
    rep = Report()
    all_nodes = collect_all_nodes(js)
    omap = outputs_map(all_nodes)

    # E16 顶层 bounds —— 平台粘贴必需，缺了「按 Ctrl+V 毫无反应」
    if isinstance(envelope, dict) and envelope.get("type") == "coze-workflow-clipboard-data":
        if "bounds" not in envelope:
            rep.err("E16", wf_name,
                    "顶层缺少 bounds —— 平台粘贴时要用它算落位包围盒，"
                    "缺了会**静默中止**（表现为按 Ctrl+V 完全没反应）。"
                    "它应等于所有根节点 _temp.bounds 的并集")
        else:
            want = clip_bounds_of(js.get("nodes") or [])
            got = envelope.get("bounds")
            if want is None:
                rep.warn("W17", wf_name,
                         "顶层有 bounds，但节点缺 _temp.bounds，无法校验二者是否一致")
            elif not isinstance(got, dict) or any(
                    abs(float(got.get(k, 0)) - want[k]) > 1e-6
                    for k in ("x", "y", "width", "height")):
                rep.warn("W17", wf_name,
                         f"顶层 bounds={got} 与根节点包围盒并集={want} 不一致")

    # E1 id 唯一
    ids = [str(n.get("id")) for n, _ in all_nodes]
    for nid, cnt in Counter(ids).items():
        if cnt > 1:
            rep.err("E1", f"id={nid}", f"节点 id 重复出现 {cnt} 次（含循环体）")

    # E2 单开始单结束
    roots = [n for n, owner in all_nodes if owner is None]
    n_start = [n for n in roots if str(n.get("type")) == "1"]
    n_end = [n for n in roots if str(n.get("type")) == "2"]
    if len(n_start) != 1:
        rep.err("E2", wf_name, f"开始节点应为 1 个，实际 {len(n_start)} 个（官方硬约束）")
    if len(n_end) != 1:
        rep.err("E2", wf_name, f"结束节点应为 1 个，实际 {len(n_end)} 个（官方硬约束：输出定义挂在结束节点上）")
    # 「这是一份完整工作流」—— 部分规则（E17/E18）只在这个前提下启用，
    # 否则 assets/example_*_nodes.json 这类单节点采集片段会被大量误报。
    _full_wf = (len(n_start) == 1 and len(n_end) == 1)

    # E3 边端点存在
    id_set = set(ids)
    for i, e in enumerate(js.get("edges", []) or []):
        s, t = str(e.get("sourceNodeID")), str(e.get("targetNodeID"))
        if s not in id_set:
            rep.err("E3", f"edges[{i}]", f"sourceNodeID={s} 不存在")
        if t not in id_set:
            rep.err("E3", f"edges[{i}]", f"targetNodeID={t} 不存在")

    # E17 从「开始」不可达的节点 —— 它永远不会执行，而且**完全静默**
    #     实测翻车：一条守卫工作流的「写日志」节点漏了两条边，画布上孤零零飘在角落，
    #     校验器当时没有这条规则，工作流照样「error 0」通过。
    #     ⚠️ 判据必须是「从开始节点 BFS 可达」，**不是**「出现在某条边里」。
    #        反例：某节点只漏了入边、出边还在（日志→结束 仍在），
    #        「出现在边里」判据会放过它，而它其实永远不会执行 —— 实测过，会漏。
    #     ⚠️ 只在「这是一份完整工作流」时启用（恰好 1 开始 + 1 结束）。
    #        节点样本片段（如 assets/example_*_nodes.json 这种单节点采集文件）本来就互不相连，
    #        在那里报不可达只会淹没真正的问题 —— 那种文件由 E2 负责指出「它不是一个完整工作流」。
    if _full_wf:
        root_edges = js.get("edges") or []
        adj = {}
        for e in root_edges:
            adj.setdefault(str(e.get("sourceNodeID")), []).append(str(e.get("targetNodeID")))
        reached, stack = set(), [str(n_start[0].get("id"))]
        while stack:
            cur = stack.pop()
            if cur in reached:
                continue
            reached.add(cur)
            for nxt in adj.get(cur, []):
                if nxt not in reached:
                    stack.append(nxt)
        for n, owner in all_nodes:
            if owner is not None:
                continue                  # 子画布节点由 W11 负责（那里的「空」可能是合法未配置态）
            nid = str(n.get("id"))
            if nid in reached:
                continue
            sub = (n.get("data") or {}).get("nodeMeta", {}).get("subTitle") or f"type={n.get('type')}"
            rep.err("E17", f"id={nid}",
                    f"「{sub}」从开始节点不可达 —— 它永远不会执行，而且不会报错。"
                    f"检查 edges 是否漏写了连向它（或从它出发）的那一条（画布上它可能看着挺正常）")

    # E18 意图识别的分支必须连完整 —— N 个 intents → branch_0…branch_{N-1} + default
    #     实测样本（用户 2026-09-20 提供，4 类意图）确认端口名就是 branch_0/branch_1/…
    #     加一条 default（未匹配出口）。⚠️ 这条是「画布上肉眼可见」的错：
    #     少连一条，那个分支端口就悬空，用户会直接说「你有几个匹配项就得连几条」。
    #     同类历史上翻过车：意图识别只连了 1 条出边（走到下游代码节点），
    #     另外几条分支既没连、也没有任何机制提醒 —— 全靠人眼看画布。
    if _full_wf:
        for n, owner in all_nodes:
            if owner is not None or str(n.get("type")) != "22":
                continue
            nid = str(n.get("id"))
            intents = [i.get("name") for i in ((n.get("data") or {}).get("inputs") or {})
                       .get("intents", []) or []]
            k = len(intents)
            outs = [e for e in (js.get("edges") or []) if str(e.get("sourceNodeID")) == nid]
            ports = {str(e.get("sourcePortID")) for e in outs if e.get("sourcePortID")}
            note = f"id={nid}（{k} 个意图）"
            expect = {"branch_%d" % i for i in range(k)}
            miss = sorted(expect - ports)
            if miss:
                rep.err("E18", note,
                        f"缺少出边端口 {miss} —— 这 {len(miss)} 条意图分支在画布上是悬空的。"
                        f"有几个 intents 就要连几条 branch_N（按 intents 数组下标）")
            if "default" not in ports:
                rep.err("E18", note,
                        "缺少 `default` 出边 —— 它是「没匹配上任何意图」的唯一出口，不能省")
            extra = sorted(p for p in ports if p not in expect and p != "default")
            if extra:
                rep.warn("E18", note,
                         f"出现了超出意图数量的端口 {extra}（intents 只有 {k} 个，合法端口是 "
                         f"{sorted(expect) + ['default']}）")

    # E19 数据库节点的「字段三种写法」—— 写错不报错，但画布上是肉眼可见的坏状态
    #   实测来源：真实画布采集样本 wf_onboarding / wf_flow_guide / wf_review_start / wf_stage_advance
    #     selectParam.fieldList[].fieldID   → **数字**   1832255057921
    #     selectParam.conditionList[].left  → **字段名** "school"
    #     insertParam.fieldInfo[][0].fieldID→ **字符串** "1831982593026"（与上面两个都不同！）
    #   写错的表现（都不报错、也能粘贴，所以只能静态查）：
    #     fieldID 写成字符串 → 画布「查询字段」整列显示 undefined
    #     left 写成数字 ID  → 画布「查询条件」左侧显示裸数字而不是字段名
    for n, owner in all_nodes:
        if owner is not None:
            continue
        ins = (n.get("data") or {}).get("inputs") or {}
        sp = ins.get("selectParam")
        if isinstance(sp, dict):
            note = f"id={n.get('id')}"
            fl = sp.get("fieldList") or []
            bad = [f.get("fieldID") for f in fl
                   if isinstance(f, dict) and isinstance(f.get("fieldID"), str)]
            if bad:
                rep.err("E19", note,
                        f"fieldList 里有 {len(bad)} 个 fieldID 是字符串 {bad[:3]}… —— "
                        f"实测这里必须是**数字**。写成字符串时画布「查询字段」那一栏整列显示 undefined")
            ob = [f.get("fieldID") for f in (sp.get("orderByList") or [])
                  if isinstance(f, dict) and isinstance(f.get("fieldID"), str)]
            if ob:
                rep.err("E19", note, f"orderByList 的 fieldID 也要数字，实际是字符串 {ob[:3]}")
            nums = []
            for row in ((sp.get("condition") or {}).get("conditionList") or []):
                for c in row:
                    if c.get("name") == "left":
                        content = (c.get("input") or {}).get("value", {}).get("content")
                        if isinstance(content, str) and content.isdigit():
                            nums.append(content)
            if nums:
                rep.err("E19", note,
                        f"条件左侧写的是字段 ID {nums[:3]} —— 实测这里要写**字段名**（如 \"user_id\"）。"
                        f"写 ID 时画布「查询条件」左侧显示裸数字而不是字段名")
        for key in ("insertParam", "updateParam"):
            p = ins.get(key)
            if not isinstance(p, dict):
                continue
            for pair in p.get("fieldInfo") or []:
                for c in pair:
                    if c.get("name") == "fieldID":
                        content = (c.get("input") or {}).get("value", {}).get("content")
                        if isinstance(content, (int, float)) and not isinstance(content, bool):
                            rep.warn("E19", f"id={n.get('id')}",
                                     f"{key} 的 fieldID 是数字 {content} —— 实测真实样本这里是**字符串**"
                                     f"（与 fieldList 相反），建议照抄字符串形态")

    # E4/E5 ref 可解析
    refs = []
    walk_refs(js, refs)
    for path, c in refs:
        bid, name = str(c.get("blockID", "")), c.get("name")
        if not bid and not name:
            # 面板上还没选变量的「未配置引用」——粘贴能过，运行时才会出问题
            rep.warn("W16", path, "该引用未配置（blockID 与 name 都为空）—— 需在画布上选一个上游变量")
            continue
        if not bid:
            rep.err("E4", path, "ref 缺少 content.blockID（但 name 非空，疑似配置错误）")
            continue
        if bid not in id_set:
            rep.err("E4", path, f"ref 指向不存在的节点 blockID={bid}")
            continue
        if not name:
            rep.warn("W16", path, "ref 的 content.name 为空（未配置变量名）")
            continue
        ok, why = resolve_path(omap.get(bid, {}), str(name))
        if not ok:
            rep.err("E5", path, f"引用 {bid}.{name} —— {why}")

    # 逐节点规则
    for n, owner in all_nodes:
        nid = str(n.get("id"))
        t = str(n.get("type"))
        note = f"type={t}({TYPE_NAME.get(t,'?')}) id={nid}" + (f" 在循环 {owner} 内" if owner else "")
        inputs = (n.get("data") or {}).get("inputs") or {}

        # W12 未知类型
        if t not in CONFIRMED_TYPES:
            rep.warn("W12", note, f"type={t} 未在本技能实测表中，字段结构可能不同 —— 请先在画布复制一个同类节点核对")

        # E6/E7 代码节点
        if t == "5":
            code = inputs.get("code") or ""
            declared = [p.get("name") for p in inputs.get("inputParameters", []) or []]
            out_names = [o.get("name") for o in (n.get("data", {}).get("outputs") or [])]
            lang = inputs.get("language")
            if lang == 5:
                # 实测：language 5 = JavaScript。不做 AST 校验（Python 解析器会误报语法错）
                if not code.strip():
                    rep.err("E6", note, "代码为空（JavaScript）")
            elif lang != 3:
                rep.warn("E6", note, f"language={lang} 未在本技能实测表中（已证实 3=Python、5=JavaScript）—— 跳过代码校验")
            elif not code.strip():
                rep.err("E6", note, "代码为空")
            else:
                try:
                    tree = ast.parse(code)
                except SyntaxError as exc:
                    rep.err("E6", note, f"代码语法错误：{exc}")
                    tree = None
                if tree is not None:
                    kind, params = main_params(tree)
                    if kind == "none":
                        rep.err("E7", note, "没有找到 main 函数（代码节点只支持一个 main）")
                    elif kind == "kwargs":
                        if set(params) != set(declared):
                            rep.err("E7", note,
                                    f"函数形参 {params} 与 inputParameters {declared} 不一致"
                                    f"（差集：缺 {sorted(set(declared)-set(params))} / 多 {sorted(set(params)-set(declared))}）")
                    ks = return_key_sets(tree)
                    if ks and ks[0] is None:
                        rep.warn("E6", note, "存在 return 变量或动态键，跳过 return 键齐校验（建议改写成字面量 dict）")
                    else:
                        want = set(out_names)
                        for idx, k in enumerate(ks):
                            if k is None:
                                continue
                            miss = want - k
                            extra = k - want
                            if miss:
                                rep.err("E6", note, f"第 {idx+1} 个 return 少写输出键 {sorted(miss)} —— 走到该路径下游会报“变量不存在”")
                            if extra:
                                rep.warn("E6", note, f"第 {idx+1} 个 return 多写了未声明的键 {sorted(extra)}")

        # W8 大模型 llmParam
        if t == "3":
            keys = [p.get("name") for p in inputs.get("llmParam", []) or []]
            miss = [k for k in LLM_KEYS if k not in keys]
            extra = [k for k in keys if k not in LLM_KEYS]
            if miss:
                rep.warn("W8", note, f"llmParam 缺少固定键 {miss}")
            if extra:
                rep.warn("W8", note, f"llmParam 出现未实测的键 {extra}")
            if "modelName" in keys:
                rep.err("W8", note, "写成了 modelName —— 剪贴板格式里这个字段名是平台拼错的 modleName，必须照抄")

        # W9 插件 apiParam
        if t == "4":
            keys = [p.get("name") for p in inputs.get("apiParam", []) or []]
            miss = [k for k in API_KEYS if k not in keys]
            if miss:
                rep.warn("W9", note, f"apiParam 缺少固定键 {miss}")
            nm = (n.get("data") or {}).get("nodeMeta") or {}
            if "subTitle" in nm and "subtitle" not in nm:
                rep.warn("W9", note, "插件节点的 nodeMeta 应用全小写 subtitle（实测 3/3 如此）")
            if not inputs.get("inputParameters"):
                rep.warn("W9", note, "插件节点的 inputParameters 为空 —— 需与插件 API 的入参名一致")

        # W10 选择器分支边
        if t == "8":
            brs = (inputs.get("branches") or [])
            outs = [e for e in (js.get("edges") or []) if str(e.get("sourceNodeID")) == nid]
            ported = [e for e in outs if e.get("sourcePortID") is not None]
            if len(brs) > len(ported):
                rep.warn("W10", note,
                         f"有 {len(brs)} 个分支，但只找到 {len(ported)} 条带 sourcePortID 的出边"
                         f"（实测端口名：'true' / 'false'；缺省端口表示“否则”分支）")

        # W18 选择器 branches 项数（实测平台恒为 1 项）
        if t == "8":
            brs = inputs.get("branches")
            if isinstance(brs, list) and len(brs) != 1:
                rep.warn("W18", note,
                         f"选择器的 branches 有 {len(brs)} 项；实测平台恒为 1 项"
                         "（false 是隐式「否则」端口）。多出的项会变成端口名未实测的"
                         "「否则如果」分支，无法连线。多路分流请串多个二分支选择器。")

        # W11 循环体 / 批处理体
        if t in BLOCK_TYPES:
            blocks = n.get("blocks") or []
            if not blocks:
                rep.err("W11", note, f"{TYPE_NAME.get(t,'?')}节点没有 blocks（子画布），跑不起来")
            ie = n.get("edges") or []
            has_out = any(e.get("sourcePortID") == "loop-function-inline-output" for e in ie)
            has_in = any(e.get("targetPortID") == "loop-function-inline-input" for e in ie)
            if not ie:
                rep.warn("W11", note, "顶层 edges 为空 —— 子画布内的节点还没连线（未配置状态）")
            else:
                if not has_out:
                    rep.err("W11", note, "内层 edges 缺少 sourcePortID='loop-function-inline-output'（进入子画布的入口线）")
                if not has_in:
                    rep.err("W11", note, "内层 edges 缺少 targetPortID='loop-function-inline-input'（回到本节点的出口线）")
            expect = "loop-output" if t == "21" else "batch-output"
            outs = [e for e in (js.get("edges") or []) if str(e.get("sourceNodeID")) == nid]
            if not any(e.get("sourcePortID") == expect for e in outs):
                rep.warn("W11", note, f"连向下游时未使用 sourcePortID='{expect}'")

        # W14 工作流（子工作流）节点
        if t == "9":
            defs = [d.get("name") for d in (inputs.get("inputDefs") or [])]
            passed = [p.get("name") for p in (inputs.get("inputParameters") or [])]
            missing = [d for d in defs if d not in passed]
            extra = [p for p in passed if p not in defs]
            if missing:
                rep.err("E14", note, f"子工作流入参 {missing} 未传值 —— inputDefs 里声明了但 inputParameters 里没有")
            if extra:
                rep.err("E14", note, f"inputParameters 里多出 {extra} —— 子工作流没有这个入参，会导致运行报错")
            if not inputs.get("workflowId"):
                rep.err("E14", note, "缺少 workflowId —— 工作流节点必须绑定一个已发布的子工作流（且子工作流必须先发布）")
            if not inputs.get("workflowVersion"):
                rep.warn("W14", note, "缺少 workflowVersion —— 建议显式填版本号，避免子工作流更新后行为漂移")
            if not inputs.get("spaceId"):
                rep.warn("W14", note, "缺少 spaceId")

        # E15 资源 ID 占位 —— 平台在【粘贴时】就会校验资源存在性，FILL_ME 会直接弹红条阻断导入
        if t == "6":
            for p in (inputs.get("datasetParam") or []):
                if p.get("name") != "datasetList":
                    continue
                v = (p.get("input") or {}).get("value") or {}
                ds = v.get("content") or []
                if not ds:
                    rep.unconfigured(note,
                                     "知识库检索节点未选知识库（datasetList 为空数组）"
                                     "—— 属合法未配置态，粘上后在画布上选知识库即可")
                for d in ds:
                    if isinstance(d, str) and d.startswith("FILL_ME"):
                        rep.err("E15", note,
                                f"知识库 ID 是占位符 {d!r} —— 平台粘贴时会直接报「知识库 xx 不存在」。"
                                f"必须填真实 datasetList（从已发布的工作流里挖，或在画布上选知识库后复制出来）")
        if t == "9":
            if str(inputs.get("workflowId", "")).startswith("FILL_ME"):
                rep.err("E15", note, "子工作流 ID 是占位符 —— 粘贴时会报「工作流不存在」")
        if t == "4":
            for p in (inputs.get("apiParam") or []):
                if p.get("name") in ("apiID", "pluginID"):
                    c = str(((p.get("input") or {}).get("value") or {}).get("content", ""))
                    if c.startswith("FILL_ME"):
                        rep.err("E15", note, f"插件 {p['name']} 是占位符 —— 粘贴时会报「插件不存在」")

        # 数据库节点：区分「未配置态」（合法）与「畸形 ID / 占位符」（要拦）
        #
        # ⚠️ 实测：空数组 `databaseInfoList: []` 是平台原生的**未配置态**，
        #    粘贴时不会触发任何资源查询 → 能正常粘上。所以**不是错误**。
        #    反过来，`[{"databaseInfoID": ""}]` 这种「有条目但 ID 为空」是**畸形值** ——
        #    平台会拿空 ID 去查资源，查不到就阻断导入。这才是要拦的。
        if t in ("42", "43", "44", "46", "12"):
            dbs = inputs.get("databaseInfoList")
            if not dbs:
                rep.unconfigured(note,
                                 f"{TYPE_NAME.get(t, '?')}节点未选数据库（databaseInfoList 为空数组）"
                                 f"—— 属合法未配置态，粘上后在画布上选库表即可")
                # 未配置态下，字段 ID 也必然没有，跳过字段检查
            else:
                dbid = str((dbs[0] or {}).get("databaseInfoID", ""))
                if not dbid:
                    rep.err("E5", note,
                            "databaseInfoList 有条目但 databaseInfoID 是空字符串 —— "
                            "这是「有引用无 ID」的畸形值，平台会拿它去查资源并失败。"
                            "未配置请写空数组 []，而不是空 ID 对象")
                elif dbid.startswith("FILL_ME"):
                    rep.err("E15", note,
                            f"databaseInfoID 是占位符 {dbid!r} —— 粘贴时会报「数据库不存在」。"
                            f"必须填真实 ID（从已发布的工作流里挖最省事）")
                elif not re.match(r"^\d{6,}$", dbid):
                    rep.warn("W13", note, f"databaseInfoID={dbid!r} 不像平台格式的数字 ID —— 待替换后才能跑通")
                # 字段 ID 占位检查
                blob = json.dumps(inputs, ensure_ascii=False)
                for m in sorted(set(re.findall(r'"content":\s*"(FILL_ME[^"]*)"', blob))):
                    rep.err("E15", note, f"字段 ID 是占位符 {m!r} —— 需替换为数据库里的真实字段 ID")

        # W19 提示词变量引用自洽 —— 实测踩过的坑
        #   例：意图识别 inputParameters 的 name 是 `data`，而 llmParam.prompt 写 `{{query}}`
        #   → 运行时取不到值；但平台保存/粘贴都不报错（它只是一段字符串）。只能静态查。
        #   空配置态（inputParameters 为空）**豁免** —— 平台自己的空态正是 prompt={{query}} + 无参数。
        if t in ("3", "18", "22"):
            names = {p.get("name") for p in (inputs.get("inputParameters") or [])}
            if names:
                texts = []
                lp = inputs.get("llmParam")
                if isinstance(lp, list):                 # type 3：llmParam 是数组
                    for p in lp:
                        c = ((p.get("input") or {}).get("value") or {}).get("content")
                        if isinstance(c, str) and c:
                            texts.append((p.get("name") or "?", c))
                elif isinstance(lp, dict):               # type 18 / 22：llmParam 是对象
                    for k in ("systemPrompt", "prompt", "userPrompt"):
                        v = lp.get(k)
                        if isinstance(v, str) and v:
                            texts.append((f"llmParam.{k}", v))
                        elif isinstance(v, dict):
                            c = (v.get("value") or {}).get("content")
                            if isinstance(c, str) and c:
                                texts.append((f"llmParam.{k}", c))
                for k in ("question", "content"):        # type 18 的提问文本
                    v = inputs.get(k)
                    if isinstance(v, str) and v:
                        texts.append((k, v))
                for where, txt in texts:
                    used = set(re.findall(r"\{\{\s*([A-Za-z_][\w.\[\]]*)", txt))
                    miss = sorted(u for u in used
                                  if u.split(".")[0].split("[")[0] not in names)
                    if miss:
                        rep.warn("W19", note,
                                 f"{where} 引用了不存在的输入参数 {miss}"
                                 f"（本节点 inputParameters 只有 {sorted(names)}）"
                                 f" —— 平台不报错，但运行时这些变量取不到值")

    return rep


# ------------------------------------------------------------------ CLI

def main():
    ap = argparse.ArgumentParser(description="Coze 工作流剪贴板 JSON 体检")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    ap.add_argument("--quiet", action="store_true", help="只输出 error")
    args = ap.parse_args()

    allout = {}
    total_e = total_w = total_u = 0
    for path in args.files:
        with open(path, "r", encoding="utf-8-sig") as f:
            obj = json.load(f)
        if obj.get("type") == "coze-workflow-clipboard-data":
            js = obj.get("json", {})
        else:
            js = obj.get("json", obj)
        rep = check(js, wf_name=os.path.basename(path), envelope=obj)
        allout[path] = {"errors": len(rep.errors), "warnings": len(rep.warnings),
                        "unconfigured": len(rep.unconfigs), "items": rep.items}
        total_e += len(rep.errors)
        total_w += len(rep.warnings)
        total_u += len(rep.unconfigs)
        if args.json:
            continue
        print(f"\n{'='*78}\n{path}\n{'='*78}")
        print(f"节点 {len(js.get('nodes', []))} 个 / 连线 {len(js.get('edges', []))} 条 "
              f"→ error {len(rep.errors)}，warning {len(rep.warnings)}，"
              f"未配置项 {len(rep.unconfigs)}")
        shown = rep.errors + ([] if args.quiet else rep.warnings)
        if not shown:
            print("  ✅ 未发现问题")
        for it in shown:
            mark = "❌" if it["level"] == "E" else "⚠️ "
            print(f"  {mark} [{it['rule']}] {it['where']}\n        {it['msg']}")
        if rep.unconfigs and not args.quiet:
            print(f"  ℹ️  以下 {len(rep.unconfigs)} 处是「未配置态」（不是问题，"
                  f"粘上后在画布上补配置即可）：")
            for it in rep.unconfigs:
                print(f"      · {it['where']}\n        {it['msg']}")

    if args.json:
        print(json.dumps(allout, ensure_ascii=False, indent=2))
    else:
        print(f"\n总计：error {total_e}，warning {total_w}，未配置项 {total_u}（未配置项不影响粘贴）")
        if total_e == 0:
            print("→ 可以粘贴：打开工作流画布 Ctrl+V，然后立刻用画布「试运行」单测")
    return 1 if total_e else 0


if __name__ == "__main__":
    sys.exit(main())
