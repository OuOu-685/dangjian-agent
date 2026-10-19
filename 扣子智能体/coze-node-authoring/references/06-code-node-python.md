# 06 · 代码节点：Python 写码规范

## 沙箱硬约束（官方明文，2025-09-16 代码节点服务升级后）

| 项 | 值 |
|---|---|
| Python 版本 | **3.11.3**（用标准库，大多数模块可用） |
| 内置第三方库 | **只有 `requests_async` 和 `numpy`**（其他 `import` 语句不生效） |
| 不支持的模块 | `curses` `dbm` `ensurepip` `fcntl` `grp` `idlelib` `lib2to3` `msvcrt` `pwd` `resource` `syslog` `termios` `tkinter` `turtle` `turtledemo` `venv` `winreg` `winsound` `multiprocessing` `threading` `sockets` `pty` `tty` |
| 超时 | 单请求 **60s**；可在节点上改 0.1s~60s |
| 重试 | 默认 0 次，可设为 1 次 |
| 协议 | 只支持 HTTP/HTTPS |
| `language` 字段 | **`3` = Python，`5` = JavaScript**（两者均已实测；切换语言时这个值必须跟着改）|
| 单工作流代码节点数 | 最多 **50** 个 |
| 函数限制 | **不支持编写多个函数**；即使只有一个输出也必须 `return` 一个对象 |

⚠️ **不支持 `threading`/`sockets`/`multiprocessing`**，官方推荐用 `asyncio.sleep()` 代替 `time.sleep()`（`time.sleep` 是阻塞调用，会拖慢工作流甚至触发限流）。`asyncio.sleep` 最长可延迟 1 分钟。

## 输入怎么取

官方口径：`params['输入参数名']`。

```python
async def main(args: Args) -> Output:
    params = args.params
    text = params["draft_text"]
    return {"out": text}
```

**关键事实：平台在 `args` 和你声明的输入参数之间插了一层 `params`。** 所以：

| 写法 | 结果 |
|---|---|
| `args.params["x"]` | ✅ 正确 |
| `args.params.get("x", "")` | ✅ 正确（`params` 是普通 dict） |
| `args["x"]` | ❌ 拿不到 |
| `args.get("x")` | ❌ **`Args` 不是原生 dict**，没有 `get`，沙盒运行失败 |
| `dict(args)["params"]["x"]` | ✅ 兜底写法 |

**排查手法**（拿不到值时的第一步，而不是猜）：

```python
async def main(args) -> dict:
    return {"debug_keys": list(dict(args).keys()), "debug_params": str(dict(args).get("params", {}))}
```

输出通常是 `{"debug_keys": ["params"], "debug_params": "{'input': {...}}"}` —— 一眼看出真实层级。

## 三种函数签名（实测全部可用）

```python
# 样式① 官方文档主推的旧版
async def main(args: Args) -> Output:
    params = args.params
    return {"out": params["in1"]}

# 样式② 新版：直接形参（2025-09 升级后）
def main(task_book: dict) -> dict:
    return {"is_valid": True}

# 样式③ 新版 + 异步
import json

async def main(task_book: str) -> dict:
    data = json.loads(task_book) if isinstance(task_book, str) else task_book
    return {"is_valid": bool(data.get("modules"))}
```

**怎么选**：跟同一份工作流里其他代码节点保持一致。都不确定就选样式②——最少陷阱，形参名直接就是输入参数名。

**样式②③的铁律**：**形参名必须和节点 `inputParameters[].name` 逐一对应**（数量、拼写、大小写全一致）。可以对形参做类型标注（`dict` / `str` / `int`），平台会做转换。

## 输出怎么给

```python
return {"is_valid": bool_val, "missing_modules": list_val, "check_report": str_val}
```

- **键名必须与节点 `outputs[].name` 完全一致**（包括大小写）。
- 值的 Python 类型要和 `outputs[].type` 对得上：`str`→`string`，`int`→`integer`，`float`→`float`，`bool`→`boolean`，`list`→`list`，`dict`→`object`。
- **`bool` 在 Python 里是 `int` 的子类**，`True` 传给 `integer` 输出可能被接受但语义错，别混。

## ⚠️ 头号坑：每个 `return` 都要写全所有输出键

平台的输出结构是一份**契约**。少一个键 **保存时不报错**，只有当输入走到那条路径、下游又引用了缺的那个变量时才炸，而且错误信息完全不指向"代码节点少写了键"。

```python
# ❌ 危险写法
def main(task_book: dict) -> dict:
    modules = task_book.get("modules", [])
    if not modules:
        return {"is_valid": False}                       # 少了 2 个键
    return {"is_valid": True, "missing_modules": [], "check_report": "通过"}

# ✅ 正确写法：先算好全部字段，只有最后一个 return
def main(task_book: dict) -> dict:
    modules = task_book.get("modules", [])
    names = [m.get("module", "") for m in modules if isinstance(m, dict)]
    missing = [r for r in ["选题依据", "研究内容"] if r not in names]
    ok = not missing
    return {
        "is_valid": ok,
        "missing_modules": missing,
        "check_report": "校验通过" if ok else "存在缺失模块",
    }
```

**模式：把所有分支差异收敛成变量，最后统一 `return` 一次。** 用 `validate_workflow.py` 的第 6 条规则可以静态查出这类问题。

## 待处理输入的三条防御

代码节点是"任务书原文/大模型输出/数据库结果"进入确定流程的关口，输入脏是常态：

```python
import json

def main(task_book: str) -> dict:
    # ① 解析失败要兜住，不能让 json.loads 抛异常
    try:
        data = json.loads(task_book) if isinstance(task_book, str) else task_book
    except Exception:
        data = {}
    # ② 类型不确定就先判类型
    if not isinstance(data, dict):
        data = {}
    modules = data.get("modules", [])
    # ③ 遍历前判元素类型，不要假设一定是 dict
    names = [m.get("module", "") for m in modules if isinstance(m, dict)]
    return {"is_valid": bool(names), "missing_modules": [], "check_report": ""}
```

**判空要用长度**，不要用字符串判空：数据库/知识库查询结果永远是 `Array<Object>`，对它做 `== ""` 永远为 False。正确写法 `len(q_result) == 0`。

## 什么时候该用代码节点

**纯数值/结构运算一律用代码节点，不要用大模型。** 日期减法、计数、拼接、判空、JSON 解析 —— 代码 100% 准确、零成本、毫秒级；大模型既慢又错（算日期十次错三次）。

**验收标准**：同一输入跑两次结果必须完全一致。不一致就说明用了大模型算。

典型用途清单：
- 时间计算（"距下一节点还剩几天"、"是否逾期"）——注意用 `asyncio.sleep` 而非 `time.sleep`
- JSON 提取与清洗（大模型输出常裹着 ` ```json ` 标记）
- 文本分段（`splitlines()` + `strip()` 过滤空段）
- 结构校验（必填模块是否齐全）
- 拼接话术/生成 `status` 标记
- 调用 HTTP 接口（`import requests_async as requests` + `await`）

## 常见错误速查

**JavaScript 代码节点**（`language: 5`）的入参与 Python 不同：

```javascript
async function main({ params }: Args): Promise<Output> {
    const ret = { "key0": params.input + params.input };
    return ret;                      // 同样必须 return 一个对象，键名对应 outputs
}
```

- JS 用**解构形参** `{ params }`，不是 `args.params`
- 内置依赖只有 `dayjs`(1.8.36) 和 `lodash`(4.17.20)，ES2022
- 静态校验工具只对 Python 做 AST 分析；**JS 节点会被跳过**（用 Python 解析 JS 会误报语法错）

| 现象 | 原因 |
|---|---|
| `Args` object has no attribute `get` | 用 `args.get()` 了，`Args` 不是 dict。改 `args.params.get()` |
| 输入参数一直是 `null` | 少了 `params` 那一层，或形参名与 `inputParameters` 不一致 |
| 取不到上游大模型的 output | 大模型的 `outputs[].name` 是你在画布上定义的名字，不是固定的 `output`。先去确认名字 |
| 输出了 `tako_bot_userhistory` 并报错 | 用函数遍历了所有变量。改成 `params['x']` 直接取，不要遍历 |
| `ImportError: No module named xxx` | 只允许 `requests_async` / `numpy`。要用别的库必须做成插件 |
| 运行到一半报"变量不存在" | 某个 `return` 少写了输出键 |
| `time.sleep` 后限流/超时 | 改用 `asyncio.sleep()` |
| 单请求超 60s | 拆小任务，或改用循环节点 + 异步轮询 |
| 直接 `requests.get()` 报错 | 用 `requests_async` 且必须 `await` |

## 写码前先确认的 4 件事

1. 输入变量的**确切名字和类型**（`inputParameters` 里的 `name` + `type`）——名字从哪来：上游节点 `outputs[].name`。
2. 要产出的**输出键名和类型**——必须与 `outputs[].name` 一致。
3. 用的是**哪种签名**（跟本工作流其他代码节点统一）。
4. 有没有**多条 return 路径**——有就要保证键齐。

---

## ★ 本地实测：不粘画布也能把代码真跑一遍

代码节点最贵的 bug 是**逻辑 bug**（关键词表漏一个词、判定优先级反了）——
校验器查不出来（语法合法），粘上画布也只能手工试几句，**而且是"感觉跑通了"**。
正确做法是**在本地真实执行它**：平台是 Python 3.11，本地 3.11+ 语义一致。

```python
import asyncio, json

class Args:                       # mock 沙箱内置的 Args
    def __init__(self, params): self.params = params
Output = dict                     # mock 沙箱内置的 Output

def load(path, title):            # 从剪贴板 JSON 里原样取出代码
    wf = json.load(open(path, encoding='utf-8'))
    for n in wf['json']['nodes']:                 # ⚠️ 不是 wf['nodes']
        d = n['data']; nm = d.get('nodeMeta') or {}
        if nm.get('title') == title:
            code = d['inputs']['code']            # ⚠️ 代码在 data.inputs.code
            ns = {'Args': Args, 'Output': Output}
            exec(compile(code, '<node>', 'exec'), ns)
            return ns['main']

fn = load('flow.json', '正常路径复核')
print(asyncio.run(fn(Args({'in_query': '帮我写一篇作文'}))))
```

### 三个必踩的坑

1. **`exec` 只能传一个 namespace**。写成 `exec(code, {'Args':…}, ns)`（globals + locals 分开）时，
   模块级常量（`RULES = [...]`）落在 locals 里，而函数的 `__globals__` 是另一个 dict
   → 跑到函数内部就 `NameError: name 'RULES' is not defined`。
   **只传一个 dict 当 globals，不要传第二个参数。**
2. **剪贴板 JSON 的节点不在顶层**：路径是 `wf['json']['nodes']`
   （顶层只有 `type` / `source` / `json` / `bounds`）。
3. **代码是 `data.inputs.code`**（与 `inputParameters` 平级的字符串兄弟键），
   不是 `data.inputs` 数组里的条目。

### 测试用例的顺序：**先测误伤，再测拦截**

**顺序不能反。** 先跑一批「正常问法」确认不会被拦，再去跑违规问法。
理由：拦截漏了还有下一层（LLM 意图识别）兜，**误伤拦住的是正常用户，没有兜底**。

必须专门构造「**形似违规的正常问法**」—— 最容易漏测的一类。实测中的真实 bug：

| 正常问法 | 为什么会被误伤 |
|---|---|
| 我写完了，帮我看看能得几分 | 含「帮我」+「写」→ 被判成代写 |
| 帮我改一下我写的这篇作文 | 含「帮我」+「写」 |
| 帮我写一下虚拟语气的用法总结 | 含「帮我写」，但目的是"要讲解" |

### 关键词匹配用「双词命中」，不用单关键词

单关键词（`'帮我写' in q`）漏得厉害 —— "帮我把这篇翻译做完"就不匹配。
改成 **请求词 × 动作词两组都命中**才判定：

```python
REQ = ['帮我', '替我', '给我', '代我', '帮忙', '代写', '代做']   # 请求方
ACT = ['写', '做完', '做一下', '完成', '搞定', '做一份']          # 动作
hit = any(r in q for r in REQ) and any(a in q for a in ACT)
```

误伤靠**放行词表**抵消（含"怎么 / 区别 / 讲解 / 我写的 / 看看 / 得几分"→ 直接放行）。

⚠️ **放行词表的判断必须排在拦截词表之前**。反过来会误伤一大片：
"帮我改一下我写的作文"会先命中「帮我」+「写」，再也没机会走到放行词。

⚠️ 关键词表一定做不完美，**它的定位是「第二道保险」，主力始终是 LLM 意图识别**。
所以它只该放在**"被判为正常"的那条路径上做补漏**，不该放在分类之前 ——
放前面会用概率性的词表**覆盖掉** LLM 更准确的判断。

