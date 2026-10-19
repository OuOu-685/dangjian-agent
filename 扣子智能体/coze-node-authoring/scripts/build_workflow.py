#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_workflow.py —— 规格 JSON → Coze 剪贴板 JSON（可直接 Ctrl+V 粘进画布）

    python build_workflow.py spec.json -o out.json
    python build_workflow.py spec.json --base real_flow.json -o out.json   # 继承真实信封
    python build_workflow.py spec.json --stdout

规格文件格式见 assets/spec-template.json 与 references/04-node-schemas.md 末尾的字段表。
零第三方依赖。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coze_node_lib import Workflow, node, TYPE_ALIAS  # noqa: E402


def build_node(spec):
    """把规格里的一项转成节点对象（递归处理循环/批处理的 blocks）"""
    nid = str(spec.get("id", "auto"))
    ntype = spec.get("type")
    title = spec.get("title") or str(TYPE_ALIAS.get(str(ntype), ntype))
    RESERVED = ("id", "type", "title", "inputs", "outputs", "position",
                "description", "subtitle", "icon", "bounds")
    kwargs = {k: v for k, v in spec.items() if k not in RESERVED}
    if "position" in spec:
        kwargs["position"] = spec["position"]
    # 循环 / 批处理的子画布节点：必须递归构造成节点对象再交给库
    blocks = spec.get("blocks")
    if blocks:
        kwargs["blocks"] = [build_node(b) for b in blocks]
    n = node(nid, ntype, title,
             inputs=spec.get("inputs"),
             outputs=spec.get("outputs"),
             description=spec.get("description"),
             subtitle=spec.get("subtitle"),
             icon=spec.get("icon"),
             **kwargs)
    return n


def main():
    ap = argparse.ArgumentParser(description="生成 Coze 剪贴板工作流 JSON")
    ap.add_argument("spec", help="规格 JSON 文件")
    ap.add_argument("-o", "--out", help="输出文件（默认 <spec 同名>.out.json）")
    ap.add_argument("--base", help="继承信封的真实剪贴板 JSON（推荐：从画布复制一份空工作流）")
    ap.add_argument("--stdout", action="store_true", help="只打印到标准输出")
    ap.add_argument("--no-bounds", action="store_true",
                    help="【诊断用】故意不写顶层 bounds，用来复现「按 Ctrl+V 毫无反应」的对照实验。"
                         "正常交付绝对不要加这个参数")
    ap.add_argument("--indent", type=int, default=None,
                    help="缩进；默认 None=单行紧凑（与平台剪贴板格式一致，粘贴最稳）。"
                         "传 2 可读但体积翻倍")
    args = ap.parse_args()

    with open(args.spec, "r", encoding="utf-8") as f:
        spec = json.load(f)

    wf = Workflow(
        name=spec.get("name", "workflow"),
        space_id=spec.get("space_id", ""),
        workflow_id=spec.get("workflow_id", "0"),
        base=args.base,
        field_map=spec.get("field_map"),
    )

    for s in spec.get("nodes", []):
        wf.add(build_node(s))

    for e in spec.get("edges", []):
        if isinstance(e, (list, tuple)):
            port = e[2] if len(e) > 2 else None
            tport = e[3] if len(e) > 3 else None
            wf.link(e[0], e[1], port=port, target_port=tport)
        else:
            wf.link(e["source"], e["target"], port=e.get("port"),
                    target_port=e.get("target_port"))

    try:
        wf.build()
    except Exception as exc:
        print("[FAIL] 构建失败：", exc, file=sys.stderr)
        traceback.print_exc()
        return 1

    # 覆盖 _temp.bounds 宽度/高度（允许规格里指定）
    for s, n in zip(spec.get("nodes", []), wf.nodes):
        b = (s.get("bounds") or {})
        if b:
            n["_temp"]["bounds"].update({k: v for k, v in b.items()
                                         if k in ("width", "height")})

    out = wf.dumps(indent=args.indent)
    if args.stdout:
        print(out)
    else:
        path = args.out or (os.path.splitext(args.spec)[0] + ".out.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(out)
        if args.no_bounds:
            import json as _json
            _o = _json.load(open(path, encoding="utf-8"))
            _o.pop("bounds", None)
            open(path, "w", encoding="utf-8", newline="\n").write(
                _json.dumps(_o, ensure_ascii=False, separators=(",", ":")))
            print("[WARN] --no-bounds：已故意删除顶层 bounds。此文件粘到画布会【毫无反应】，"
                  "仅用于对照实验。")

        print(f"[OK] 已生成 {path}  ({len(wf.nodes)} 节点 / {len(wf.edges)} 连线 / {len(out)} 字节"
              f" / {'单行' if args.indent is None else str(args.indent) + ' 空格缩进'})")

    for w in getattr(wf, "warnings", []):
        print("  [WARN]", w, file=sys.stderr)

    print("\n下一步：改用 validate_workflow.py 体检，然后再粘到画布：")
    print("  1) 打开工作流画布  2) Ctrl+V  3) 画布「试运行」单测")
    return 0


if __name__ == "__main__":
    sys.exit(main())
