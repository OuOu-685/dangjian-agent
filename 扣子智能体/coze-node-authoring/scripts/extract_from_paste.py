# -*- coding: utf-8 -*-
"""从用户回传的工作流剪贴板 JSON 里，抽取下游生成 spec 所需的真实信息。
用法：python extract_from_paste.py <回传.json> [--json]
输出：workflowId / spaceId / 开始节点入参(inputDefs 来源) / 数据库表ID / 字段ID台账
"""
import json
import sys


def load(path):
    raw = json.load(open(path, encoding="utf-8"))
    return raw["json"] if "json" in raw else raw, raw.get("source", {})


def main():
    path = sys.argv[1]
    flow, src = load(path)
    nodes = flow.get("nodes") or []
    edges = flow.get("edges") or []

    out = {
        "workflowId": src.get("workflowId"),
        "spaceId": src.get("spaceId"),
        "nodes": len(nodes),
        "edges": len(edges),
        "start_inputs": [],
        "sub_workflows": [],
        "databases": [],
        "insert_fields": [],
        "update_nodes": [],
        "unbound_kb": [],
    }

    for n in nodes:
        t = str(n.get("type"))
        d = n.get("data") or {}
        ins = d.get("inputs") or {}
        title = (d.get("nodeMeta") or {}).get("title", "")

        if t == "1":
            for o in d.get("outputs") or []:
                out["start_inputs"].append(
                    {"name": o.get("name"), "type": o.get("type"),
                     "required": bool(o.get("required"))})

        elif t == "9":
            out["sub_workflows"].append({
                "node_id": n["id"], "title": title,
                "workflowId": ins.get("workflowId"),
                "workflowVersion": ins.get("workflowVersion"),
                "spaceId": ins.get("spaceId"),
                "inputDefs": [x.get("name") for x in (ins.get("inputDefs") or [])],
                "passed": [x.get("name") for x in (ins.get("inputParameters") or [])],
            })

        elif t in ("42", "43", "46"):
            bl = ins.get("databaseInfoList") or []
            dbids = [x.get("databaseInfoID") for x in bl]
            out["databases"].append(
                {"node_id": n["id"], "title": title, "type": t, "db": dbids})
            if t == "46":
                fi = (ins.get("insertParam") or {}).get("fieldInfo") or []
                for row in fi:
                    kv = {}
                    for cell in row:
                        nm = cell.get("name")
                        v = ((cell.get("input") or {}).get("value") or {})
                        kv[nm] = {"content": v.get("content"), "vtype": v.get("type")}
                    out["insert_fields"].append(kv)
            if t == "42":
                up = ins.get("updateParam") or {}
                keys = list(up.keys())
                out["update_nodes"].append(
                    {"node_id": n["id"], "updateParam_keys": keys,
                     "has_fieldList": "fieldList" in up})

        elif t == "6":
            ds = None
            for p in ins.get("datasetParam") or []:
                if p.get("name") == "datasetList":
                    ds = ((p.get("input") or {}).get("value") or {}).get("content")
            if not ds:
                out["unbound_kb"].append({"node_id": n["id"], "title": title})

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
