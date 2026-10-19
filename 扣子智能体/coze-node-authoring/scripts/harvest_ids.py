#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
harvest_ids.py —— 从已有工作流里挖出「平台侧生成的资源 ID」

为什么需要它：
  databaseInfoID / fieldID / 知识库 datasetList / 插件 apiID+pluginID / 子工作流 workflowId
  都是**平台侧生成**的，代码里生不出来。但它们**一定会出现在你已发布的工作流里**。
  与其一个个在画布上点，不如批量挖出来复用 —— 30 秒搞定几十个 ID。

核心技巧（很多人不知道）：
  **查询数据节点的 `selectParam.fieldList[]`（字段 ID 数组）和该节点 `outputs[0].schema.schema[]`
  （字段名数组）是同一顺序。** 两者 zip 一下，就得到「字段 ID → 字段名」对照表。

用法：
    python harvest_ids.py 工作流1.json 工作流2.md ...            # 人类可读报告
    python harvest_ids.py *.json --json                          # 机器可读
    python harvest_ids.py *.json --emit-field-map field_map.json # 直接生成 field_map 片段

产出的 field_map 可直接粘进 build_workflow.py 的规格文件（按 databaseInfoID 分表）。
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys


def load_clipboard(path):
    """读剪贴板 JSON；也容忍被包在 .md / .txt 里的单个 JSON 对象"""
    raw = open(path, "rb").read().decode("utf-8-sig", errors="replace").strip()
    try:
        obj = json.loads(raw)
    except Exception:
        i, j = raw.find("{"), raw.rfind("}")
        if i < 0 or j < 0:
            raise ValueError("找不到 JSON 对象")
        obj = json.loads(raw[i:j + 1])
    if obj.get("type") == "coze-workflow-clipboard-data":
        return obj.get("source", {}), obj.get("json", obj)
    return obj.get("source", {}), obj.get("json", obj)


def walk(node, report, owner_path=""):
    data = node.get("data") or {}
    inputs = data.get("inputs") or {}
    ntype = str(node.get("type"))
    title = (data.get("nodeMeta") or {}).get("title", "") or node.get("id")
    label = f"{owner_path}>{title}" if owner_path else title

    # ---- 数据库 ----
    if ntype in ("42", "43", "46"):
        dbs = inputs.get("databaseInfoList") or []
        if dbs:
            dbid = str(dbs[0].get("databaseInfoID"))
            report["db_titles"][dbid].add(label)
            # 条件字段名
            par = inputs.get("selectParam") or inputs.get("updateParam") or {}
            for grp in (par.get("condition") or {}).get("conditionList") or []:
                for item in grp:
                    if item.get("name") == "left":
                        c = ((item.get("input") or {}).get("value") or {}).get("content")
                        if c and not str(c).isdigit():
                            report["db_cond_fields"][dbid].add(str(c))
            # 字段 ID → 字段名（关键：fieldList 与 output schema 同序）
            if ntype == "43":
                flist = [f.get("fieldID") for f in
                         ((inputs.get("selectParam") or {}).get("fieldList") or [])]
                outs = data.get("outputs") or []
                names = []
                if outs:
                    names = [x.get("name") for x in
                             ((outs[0].get("schema") or {}).get("schema") or [])]
                if flist and names and len(flist) == len(names):
                    for fid, nm in zip(flist, names):
                        report["field_map"][dbid].setdefault(str(fid), nm)
                elif flist:
                    report["unpaired"][dbid].add((label, len(flist), len(names)))
            # 写入字段（只有 ID 没有名，配合条件字段与文档反推）
            if ntype in ("42", "46"):
                for grp in (par.get("fieldInfo") or []):
                    fid = str(grp[0]["input"]["value"].get("content"))
                    v = grp[1]["input"]["value"]
                    if v.get("type") == "ref":
                        c = v.get("content") or {}
                        val = f"REF {c.get('blockID')}.{c.get('name')}"
                    else:
                        val = f"LIT {v.get('content')!r}"
                    report["write_fields"][dbid].append((fid, val, label))

    # ---- 知识库 ----
    if ntype == "6":
        for p in inputs.get("datasetParam") or []:
            if p.get("name") == "datasetList":
                v = (p.get("input") or {}).get("value") or {}
                for d in (v.get("content") or []):
                    report["datasets"][str(d)] += 1

    # ---- 插件 ----
    if ntype == "4":
        d = {p["name"]: ((p.get("input") or {}).get("value") or {}).get("content")
             for p in inputs.get("apiParam") or []}
        report["plugins"][f"{d.get('pluginName')}:{d.get('apiName')}"] = {
            "apiID": d.get("apiID"), "apiName": d.get("apiName"),
            "pluginID": d.get("pluginID"), "pluginName": d.get("pluginName"),
            "pluginVersion": d.get("pluginVersion")}

    # ---- 子工作流 ----
    if ntype == "9":
        report["subflows"][str(inputs.get("workflowId"))] = {
            "workflowVersion": inputs.get("workflowVersion"),
            "spaceId": inputs.get("spaceId"),
            "title": (data.get("nodeMeta") or {}).get("title"),
            "plugin_id": (node.get("_temp") or {}).get("externalData", {}).get("plugin_id"),
            "inputDefs": [x.get("name") for x in (inputs.get("inputDefs") or [])],
            "outputs": [x.get("name") for x in (data.get("outputs") or [])],
        }

    # ---- 模型 ----
    if ntype == "3":
        for p in inputs.get("llmParam") or []:
            if p.get("name") == "modleName":
                mt = next((q for q in inputs["llmParam"] if q["name"] == "modelType"), None)
                report["models"][str((p.get("input") or {}).get("value", {}).get("content"))] = \
                    str((mt or {}).get("input", {}).get("value", {}).get("content"))

    for b in node.get("blocks") or []:
        walk(b, report, label)


def new_report():
    return {
        "db_titles": collections.defaultdict(set),
        "db_cond_fields": collections.defaultdict(set),
        "field_map": collections.defaultdict(dict),
        "write_fields": collections.defaultdict(list),
        "unpaired": collections.defaultdict(set),
        "datasets": collections.Counter(),
        "plugins": {},
        "subflows": {},
        "models": {},
    }


def main():
    ap = argparse.ArgumentParser(description="从已有 Coze 工作流里挖出平台侧生成的资源 ID")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    ap.add_argument("--emit-field-map", metavar="OUT.json",
                    help="把挖到的 field_map 直接写成可用的 JSON 文件")
    args = ap.parse_args()

    rep = new_report()
    for p in args.files:
        try:
            src, js = load_clipboard(p)
        except Exception as exc:
            print(f"[SKIP] {p}: {exc}", file=sys.stderr)
            continue
        for n in js.get("nodes") or []:
            walk(n, rep)

    if args.emit_field_map:
        out = {dbid: dict(sorted(m.items())) for dbid, m in rep["field_map"].items()}
        with open(args.emit_field_map, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"[OK] field_map 已写入 {args.emit_field_map}"
              f"（{len(out)} 张表 / {sum(len(v) for v in out.values())} 个字段）")

    if args.json:
        print(json.dumps({
            "database_ids": {k: sorted(v) for k, v in rep["db_titles"].items()},
            "database_condition_fields": {k: sorted(v) for k, v in rep["db_cond_fields"].items()},
            "field_map": {k: dict(v) for k, v in rep["field_map"].items()},
            "write_fields": {k: v for k, v in rep["write_fields"].items()},
            "knowledge_dataset_ids": dict(rep["datasets"]),
            "plugins": rep["plugins"],
            "subflows": rep["subflows"],
            "models": rep["models"],
        }, ensure_ascii=False, indent=2))
        return 0

    print("=" * 84)
    print("数据库（databaseInfoID）：用「条件字段 + 字段名」认表")
    print("=" * 84)
    for dbid in sorted(rep["db_titles"]):
        print(f"\ndbid = {dbid}")
        print(f"  出现在节点: {sorted(rep['db_titles'][dbid])}")
        if rep["db_cond_fields"][dbid]:
            print(f"  条件里用过的字段名: {sorted(rep['db_cond_fields'][dbid])}")
        fm = rep["field_map"][dbid]
        if fm:
            print(f"  字段 ID→名 ({len(fm)}): {dict(sorted(fm.items()))}")
        if rep["unpaired"][dbid]:
            print(f"  ⚠️ 有节点 fieldList 与 output schema 长度不一致，未能配对: "
                  f"{sorted(rep['unpaired'][dbid])}")
        if rep["write_fields"][dbid]:
            print("  写入用到的字段（靠值反推名字）:")
            seen = set()
            for fid, val, lbl in rep["write_fields"][dbid]:
                if fid in seen:
                    continue
                seen.add(fid)
                print(f"     {fid}  ←  {val}   ({lbl})")

    print()
    print("=" * 84)
    print("知识库 datasetList:", dict(rep["datasets"]) or "（无）")
    print("插件:", rep["plugins"] or "（无）")
    print("子工作流:")
    for wid, info in rep["subflows"].items():
        print(f"  {wid}  {info['title']}  {info['workflowVersion']}")
        print(f"     inputDefs: {info['inputDefs']}")
        print(f"     outputs  : {info['outputs']}")
    print("模型 modleName→modelType:", rep["models"] or "（无）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
