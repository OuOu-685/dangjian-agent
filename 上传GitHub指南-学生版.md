# 把项目上传到 GitHub · 学生版操作指南

**案例项目**：`dangjian-agent`（党建工作智能体）
**适用环境**：Windows 10/11 · Git 2.45+（Git for Windows）· 拿到的是项目 zip 压缩包（解压后目录里**没有** `.git`）
**配套材料**：《一小时台本-本地上传到GitHub.md》（老师照着讲）
**目标**：60 分钟内把你本地的项目副本推送到**你自己的** GitHub 账号，并且保证没有任何敏感文件混进去。

---

## 0. 一分钟速览

| 项目 | 结论 |
|---|---|
| 核心命令 | 就 6 条（见下方代码块） |
| 认证方式 | 弹窗浏览器登录（最省事）或 个人访问令牌 PAT（最通用） |
| 三条红线 | 不传 `.env`、不传虚拟环境/依赖目录、不传 >100MB 单文件 |
| GitHub 连不上 | 先做 §2 网络体检；仍不行走 Gitee 兜底（§11） |
| 最容易翻车的一步 | 不是 push，是**上传前的安全检查**（§7） |

**最快路径**（每个概念后面都有详解，别怕）：

```powershell
cd D:\code\dangjian-agent              # ① 进入项目目录
git init                               # ② 初始化仓库
git branch -M main                     # ③ 统一分支名（GitHub 网页默认 main）
git add .                              # ④ 把文件放进"待提交区"
git commit -m "chore: 首次提交"         # ⑤ 生成一个提交
git remote add origin https://github.com/<你的用户名>/dangjian-agent.git   # ⑥ 关联远程仓库
git push -u origin main                # ⑦ 推送（会弹窗要认证）
```

**本项目的关键数字**（先建立直觉，正文会反复用到）：

```
项目文件夹总大小 ≈ 1,059 MB
真正需要上传的代码 ≈ 8.3 MB（546 个文件；从零 init 首次提交 539 个，见 §6.2 小知识）
仓库历史打包后 ≈ 11 MB
多出来的 1,000+ MB，几个大头：
  venv-lock 434MB ｜ .venv 258MB ｜ .mypy_cache 186MB ｜ frontend/node_modules 120MB ｜ tmp 14MB
——这些目录必须要靠 .gitignore 挡在门外，一个都不能传。
```

---

## 一、前置准备

### 1.1 软件清单

| 软件 | 用途 | 检查命令 | 预期输出 |
|---|---|---|---|
| Git for Windows | 全部 Git 操作（自带来 Git Credential Manager 弹窗登录能力） | `git --version` | `git version 2.4x.x.windows.1` |
| VS Code（可选） | 学 §10 的图形界面路线 | `code --version` | 版本号三行 |
| 浏览器 | 操作 GitHub 网页 | — | 能打开 `https://github.com` |

没装 Git 的先装（下一步才能进行）：官网 `https://git-scm.com/download/win` 一路默认下一步即可。

### 1.2 GitHub 账号要点

- 注册入口：`https://github.com/signup`
- **用户名**建议用「拼音 + 学号后四位」这类可辨认的写法，别用 `asdf1234`——这是要写在简历和结业作品里的
- 邮箱要能收信（需要验证）
- **提前一天注册好**：现场注册要过邮箱验证和人机验证，很浪费时间

### 1.3 配置你的提交身份（第一次用 Git 必做）

```powershell
git config --global user.name "张三"
git config --global user.email "zhangsan@example.com"
```

**为什么重要**：这两个值会写进每一个提交、公开可见。如果填得像本机反面案例这样——

```
user.name  = manice
user.email = 2474629226        # ← 没有 @，不是邮箱
```

——GitHub 就没法把你的提交关联到你的账号头像上，绿格子也不会亮。

**检查是否配好**：

```powershell
git config --global user.name
git config --global user.email
```

---

## 二、网络体检（GitHub 需要代理时的必修课）

**先记住一个高频困惑：Git 不会自动使用你浏览器/系统代理。**
浏览器能打开 GitHub ≠ `git push` 能成功。Git 有自己的代理配置，要单独设置。

### 2.1 三步体检

```powershell
# ① 看 Git 当前有没有代理配置（没配就什么都不输出）
git config --global --get http.proxy
git config --global --get https.proxy
```

```powershell
# ② 看代理软件是否真的开着（端口换成你自己代理软件的端口）
Test-NetConnection 127.0.0.1 -Port 7897
# 输出里要有：TcpTestSucceeded : True   ← 这才是通
```

```powershell
# ③ 实测能不能访问 GitHub（最权威）
git ls-remote https://github.com/git/git.git HEAD
# 正常：输出一行 <40位哈希>  HEAD
# 失败：报 Could not resolve host / 卡住不动 = 网络不通
```

### 2.2 本机真实翻车案例（务必认识这条报错）

```
fatal: unable to access 'https://github.com/jaimelove67/dangjian-agent.git/':
Failed to connect to 127.0.0.1 port 7897 after 2049 ms: Couldn't connect to server
```

**含义**：Git 代理配置指向 `127.0.0.1:7897`，但代理软件没开（或换了端口）。
**处理**：二选一——① 打开代理软件；② 清掉配置见 2.4。

### 2.3 需要走代理：配置命令

```powershell
# 把 7897 换成你自己代理软件的端口（下同）
git config --global http.proxy  http://127.0.0.1:7897
git config --global https.proxy http://127.0.0.1:7897
```

常见代理软件端口对照：

| 代理软件 | 常见端口 |
|---|---|
| Clash for Windows / ClashX | 7890 |
| Clash Verge / Mihomo（本机就是） | **7897** |
| v2rayN | 10808 / 10809 |
| 不确定 | 打开代理软件 → 设置 → 找「端口 / 混合端口 / HTTP 端口」 |

⚠️ 配好之后**代理软件必须一直开着**。放假回家关了代理软件，push 报错，就是 2.2 那条。

### 2.4 不需要代理：清掉旧配置

```powershell
git config --global --unset http.proxy
git config --global --unset https.proxy
```

（如果报 `error: could not lock config file`，说明有别的 Git 进程在跑，关掉 VS Code 再试。）

---

## 三、第一步：在 GitHub 上建一个空仓库

1. 浏览器登录 GitHub，打开 `https://github.com/new`
2. **Repository name**：`dangjian-agent`
3. **Description**：可填可不填
4. **可见性**：选 **Private**（课程作业推荐先私有；确认没有敏感内容后再考虑公开）
5. **三个初始化选项全部不勾**：
   - ❌ Add a README file
   - ❌ Add .gitignore
   - ❌ Choose a license
   
   > 为什么不勾？勾了远程仓库就会先有一个提交，你第一次 push 会被拒绝（`non-fast-forward`），要多一步 `git pull --rebase` 才能化解。对新手来说少一步少一个坑。
6. 点 **Create repository**
7. 在跳转后的页面上，复制 HTTPS 地址框里的内容：

```
https://github.com/<你的用户名>/dangjian-agent.git
```

**记住这个地址**，§8 关联远程仓库要用。

---

## 四、第二步：解压 zip，确认目录"干净"

**建议解压到纯英文短路径**，比如 `D:\code\dangjian-agent`，不要放桌面（路径里有中文/空格，Git 和后续工具容易出幺蛾子）。

解压后打开 PowerShell 检查：

```powershell
cd D:\code\dangjian-agent
Get-ChildItem -Force | Select-Object Name
```

✅ **应该看到**：

```
.gitignore          ← 最重要！没有它，1GB 全部上传
.gitattributes
.env.example        ← 配置模板（可以上传）
README.md
START_HERE.txt
app\  frontend\  docs\  ...
```

❌ **不应该看到**：

```
.env            ← 里面有你的真实密钥！
.venv  venv-lock\  node_modules\   ← 虚拟环境和依赖，共 800+ MB
uploads\  logs\  tmp\              ← 运行时产物/用户上传文件
```

（如果解压出来还有个 `.git\` 文件夹，别慌，看 §9 支线。）

---

## 五、第三步：初始化仓库

```powershell
cd D:\code\dangjian-agent
git init
git branch -M main
```

解释：

- `git init`：在目录里建一个隐形文件夹 `.git\`，从此这个目录成为"仓库"
- `git branch -M main`：把默认分支名统一为 `main`（GitHub 网页默认用它；老教程里的 `master` 是历史遗留）

**顺手配置本项目身份**（§1.3 配过可跳过）：

```powershell
git config user.name "张三"
git config user.email "zhangsan@example.com"
```

---

## 六、第四步：安全门禁（最容易跳过、后果最严重的一步）

> 原则：**先检查，再 `git add`**。顺序反了，就得重来。

### 6.1 红线一：`.env` 只能留在你自己的电脑上

本项目 `.env` 里的变量名（值在你的机器上，我不看，你也不许上传）：

```
DASHSCOPE_API_KEY   ← 百炼 API Key，能花钱的
POSTGRES_PASSWORD / REDIS_PASSWORD   ← 数据库密码
SECRET_KEY          ← 登录凭证签名密钥
```

`.env.example` 是**模板**（值为空/占位），它是专门给别人抄的，**可以也建议上传**。
所以你上传的仓库里出现 `.env.example` 是正常的，出现 `.env` 就是事故。

**万一误传了怎么办（顺序不能反）**：

1. **先去平台作废/轮换密钥**（比如百炼控制台删掉旧 Key 重建一个）——因为提交历史里还留着
2. 再 `git rm --cached .env` 并从 `.gitignore` 层面确认已忽略
3. 提交并 push
4. 记住：**换钥匙比删文件重要**，历史里的旧 key 拿不回来了

### 6.2 红线二：虚拟环境 / 依赖目录不进仓库

这就是"1GB 项目"的真相：

| 目录 | 大小 | 有 `.gitignore` 挡着吗 |
|---|---|---|
| `venv-lock\`（虚拟环境） | **434 MB** | ✅ 它内含虚拟环境自带的 `.gitignore`（内容就一行 `*`） |
| `.venv\`（虚拟环境） | **258 MB** | ✅ `.gitignore` 第 102 行 |
| `.mypy_cache\`（类型检查缓存） | **186 MB** | ✅ `.gitignore` 第 120 行 |
| `frontend\node_modules\` | **120 MB** | ✅ 由 `frontend/.gitignore` 挡 |
| `tmp\` | **14 MB** | ✅ `.gitignore` |
| 真正要上传的代码 | **8.3 MB** | — |

本项目自带 `.gitignore`，关键条目如下，**别删**：

```gitignore
.env                 # ← .env 及其变体全部忽略
.env.*
!.env.example        # ← 但放行模板文件（! 表示"反向/例外"）
.venv                # ← 虚拟环境
logs/  tmp/  uploads/  audit-spool/
.mypy_cache/  .pytest_cache/  .playwright-mcp/
```

**可选补强**：项目根的 `.gitignore` 里没有显式的 `.ruff_cache/` 规则。
你本地跑过 ruff 的话它其实已经"自保"（ruff 会在缓存目录里自动生成一个内容为 `*` 的小 `.gitignore`，`venv-lock` 同理），但"不依赖工具自动生成的文件"才是稳妥习惯，建议显式补一条：

```powershell
".ruff_cache/" | Add-Content -Path .gitignore -Encoding UTF8
```

（或者用 VS Code 打开 `.gitignore` 手动加。）

**小知识**：`.gitignore` 对**已经跟踪过的文件**无效。
本项目有两个真实例子：`.idea/` 和 `.workbuddy/` 都写在忽略表里，但历史上已有 7 个文件被跟踪（`.idea` 5 个 + `.workbuddy` 2 个）——所以你从零 `git init` 的首次提交是 **539** 个文件，比老师的 `git ls-files`（546 个）正好少这 7 个。
不用去改它，知道这条规则就行：**忽略要趁早，第一次 `git add` 之前就位。**

### 6.3 红线三：单文件 100MB 是硬上限

- 单文件 > 100MB：GitHub 直接拒绝整个 push
- 单文件 > 50MB：给警告
- 真有大文件需求（视频/数据集）→ 课后了解 Git LFS，课堂不展开

### 6.4 四条自查命令（做完才算过关）

```powershell
# ① 应该输出 .gitignore:99:.env   ← 说明 .env 被挡
git check-ignore -v .env

# ② 看"被忽略的文件/目录"名单（!! 开头）。你的学生包很干净，输出少是正常的；
#    换到你自己的开发机上，会看到 .venv/、node_modules/ 这类目录出现在这里
git status --ignored --porcelain | Select-String '^!!'

# ③ 演习一遍"将来会被提交的文件"里有没有 .env（只允许出现 .env.example）
git add -n . | Select-String '\.env'

# ④ 预估提交文件数：本项目从零 init 约 539 个。如果是几万，说明门卫失守了
git add -n . | Measure-Object -Line
```

> `git add -n` 是"演习"：只显示会加什么，不真的加，也不会写坏任何东西。

---

## 七、第五步：提交

```powershell
cd D:\code\dangjian-agent

git status          # 看一眼：文件多但数字合理（本项目约 540 条），不该出现 .venv 之类的目录
git add .
git ls-files | Select-String '\.env'    # 最后复查：只允许出现 .env.example
git commit -m "chore: 项目首次提交"
```

**关于提交信息**（和《开发规范文档》呼应）：首次提交用 `chore:` 前缀即可。以后：

| 前缀 | 用途 | 例 |
|---|---|---|
| `feat:` | 新功能 | `feat: 添加党员培训提醒` |
| `fix:` | 修 bug | `fix: 修复登录超时` |
| `docs:` | 改文档 | `docs: 补充部署说明` |
| `test:` | 测试 | `test: 增加回归用例` |
| `chore:` | 杂项/初始化 | `chore: 项目首次提交` |

---

## 八、第六步：关联远程仓库 + 第一次推送

```powershell
# 把地址换成 §3 复制的、你自己的仓库地址
git remote add origin https://github.com/<你的用户名>/dangjian-agent.git

git remote -v       # 验证：应显示 fetch/push 两行你的地址

git push -u origin main
```

`-u` 的含义：把本地 `main` 和远程 `main` 绑定，**以后只要 `git push` 一条命令**即可。

### 8.1 认证：第一次 push 会弹窗，两条路

**路线 A：浏览器登录（最省事，推荐）**

弹窗里选 **Sign in with your browser** → 浏览器打开 GitHub → 登录并授权 → 弹窗显示 success，Push 自动继续。
之后这台电脑会记住凭证（Windows 凭据管理器），不用每次登录。

**路线 B：个人访问令牌 PAT（通用，机房电脑无法登录浏览器时用）**

1. 浏览器打开 `https://github.com/settings/tokens` → **Generate new token (classic)**
2. Note 随便写（如 `classroom-push`），Expiration 建议 30 天
3. 勾选 **`repo`** 这一大项（推送私有/公开仓库都够用）
4. 点生成，**立刻复制** `ghp_` 开头的令牌——**只显示这一次**
5. 回到弹出的认证窗口选 **Personal access token**，粘贴令牌

用户名 = 你的 GitHub 用户名，密码 = 你的 PAT。**不要再输 GitHub 登录密码**（密码认证 2021 年就被 GitHub 废除了，报错见 §12）。

**换过 PAT / 换过账号之后推送失败？** 清掉旧凭证：控制面板 → 凭据管理器 → Windows 凭据 → 找到 `git:https://github.com` → 删除，再 push 会重新弹窗。

### 8.2 推送成功的验证

```powershell
git status                    # On branch main / up to date
git log --oneline -1          # 一条提交，作者是你
git ls-remote --heads origin  # 能列出远程 main，说明推上去了
```

再打开浏览器刷新仓库页面：**文件列表出现了 → 成功。**

---

## 九、支线：拿到的拷贝带着 `.git`（老师的仓库历史）

判断方法：

```powershell
git remote -v
# origin  https://github.com/jaimelove67/dangjian-agent.git   ← 老师的地址，不是你的
```

**做法一（推荐，当学生作业）：切断历史重新开始**

```powershell
Remove-Item -Recurse -Force .git     # 删掉历史，回到"没有 .git"的状态
# 然后从 §5 重新开始（git init ...）
```

**做法二（进阶）：保留历史，只换远程地址**

```powershell
git remote set-url origin https://github.com/<你的用户名>/dangjian-agent.git
git push -u origin main
```

⚠️ 做法二会把原有的全部提交历史一起推上去（包括老师写的提交记录），且历史里如果曾经有过敏感信息，也会一并带过去。**给老师交付作业用做法一。**

---

## 十、VS Code 图形界面路线（怕命令行的同学看这里）

命令行和界面是**同一件事的两种操作方式**，对照表：

| 命令行 | VS Code 图形界面 |
|---|---|
| `git init` | 左侧「源代码管理」面板 → **Initialize Repository** |
| 改动文件出现在待提交区 | 打开/保存文件后，面板自动列出改动，点 `+` 暂存 |
| `git commit -m "..."` | 顶部输入框写信息 → Ctrl+Enter（或点 ✓） |
| `git remote add origin ...` | 不用配：点 **Publish Branch** 自动创建 |
| `git push -u origin main` | 点 **Publish Branch** → 选 GitHub 登录 → 选 public/private |
| 后续 `git push` | 点 **Sync Changes**（同步）= push + pull |

步骤：

1. VS Code → 文件 → 打开文件夹 → 选 `D:\code\dangjian-agent`
2. 左侧点第三个图标（源代码管理，快捷键 `Ctrl+Shift+G`）
3. 点 **Initialize Repository**
4. 在消息框输入 `chore: 首次提交`，点 **Commit**（会提示"是否暂存所有更改"，选是）
5. 点 **Publish Branch** → 选 **Sign in to GitHub**（浏览器授权）→ 私有/公开
6. 完成，浏览器刷新即见

⚠️ 用 GUI 之前，请先用 §6.4 的三条命令做过**安全门禁**——界面里没有这么细的检查。

---

## 十一、Gitee 兜底（GitHub 连不上 / 没有代理时）

命令流程**完全一样**，只换两样：仓库地址 + 认证方式。

1. 到 `https://gitee.com` 注册（国内直连，快）
2. 新建仓库：右上角 `+` → 新建仓库 → 同样**不勾**初始化选项
3. 本地操作：

```powershell
git remote add origin https://gitee.com/<你的用户名>/dangjian-agent.git
# 如果 origin 已存在（比如之前配过 GitHub）：
git remote set-url origin https://gitee.com/<你的用户名>/dangjian-agent.git

git push -u origin main
```

4. 认证：Gitee 弹窗输账号密码即可；开了两步验证的话用**私人令牌**（`https://gitee.com/profile/personal_access_tokens`）

**差异对照**：

| 对比项 | GitHub | Gitee |
|---|---|---|
| 访问速度（国内） | 常需代理 | 直连快 |
| 默认分支 | `main` | 多为 `master`（以仓库页提示为准） |
| HTTPS 认证 | PAT / 浏览器登录 | 密码 / 私人令牌 |
| 私有仓库 | 免费 | 免费 |

**小技巧：一个项目推到两家**（GitHub + Gitee 双保险）：

```powershell
git remote add gitee https://gitee.com/<你>/dangjian-agent.git
git push -u gitee main

# 以后一条命令推两家：
git push origin main; git push gitee main
```

---

## 十二、常见报错对照表（收藏这一节）

| 报错（关键片段） | 原因 | 处理 |
|---|---|---|
| `fatal: not a git repository ...` | 终端不在项目目录，或没 `git init` | `cd` 到项目目录；`dir -Force` 确认有 `.git` |
| `Failed to connect to 127.0.0.1 port 7897 ... Couldn't connect to server` | 代理配置指向的端口没服务（代理软件没开/换端口了） | 开代理软件；或 `git config --global --unset http.proxy`（同时 unset `https.proxy`） |
| `Could not resolve host: github.com` / push 一直卡住 | 网络不通 / 没走代理 | 按 §2 体检；或走 Gitee |
| `Support for password authentication was removed on August 13, 2021` | 在密码框输了 GitHub 登录密码 | 用 PAT（§8.1 路线 B）或浏览器登录 |
| `remote: Invalid username or password` | PAT 过期 / 复制不全 / 权限不够 | 重新生成 PAT，确认勾选 `repo` |
| `fatal: remote origin already exists.` | 之前配过 origin | `git remote set-url origin <新地址>` |
| `src refspec main does not match any` | 还没提交，或分支名是 `master` | 先 `git commit`；`git branch -M main` |
| `! [rejected] main -> main (non-fast-forward)` | 远程仓库不空（建仓库时勾了 README 等） | `git pull --rebase origin main` 后重新 push；建仓库时不勾就没有这个错 |
| `refusing to merge unrelated histories` | 两段无关历史强行合并（改 remote 场景） | 确认后 `git pull origin main --allow-unrelated-histories`，或删 `.git` 重来（§9 做法一） |
| `warning: LF will be replaced by CRLF` | Windows 换行符提示 | **无害，不用管**；本项目 `.gitattributes` 已统一规则 |
| `File xxx is 123.45 MB; this exceeds GitHub's file size limit of 100.00 MB` | 混进了大文件 | `git rm --cached <文件>` → 写进 `.gitignore` → 重新提交 |
| `unable to create '.git/index.lock': File exists` | 有别的 Git 进程没退出（常见于 VS Code + 命令行同时操作） | 关掉其它 Git 操作，删 `.git/index.lock`，重试 |
| `detected dubious ownership in repository` | 目录属主与当前用户不一致 | `git config --global --add safe.directory <项目路径>` |
| `Filename too long` | 路径超长 | `git config --global core.longpaths true` |

---

## 十三、验收清单（交作业前逐条打勾）

- [ ] 浏览器打开 `https://github.com/<你>/dangjian-agent`：能看到文件列表，README 正常渲染
- [ ] 仓库里搜不到 `.env`（搜到的只能是 `.env.example`）
- [ ] 仓库体积正常（几百 KB ~ 几 MB 级，不能是几百 MB）
- [ ] Commits 页第一条提交，作者是你的名字/邮箱（点头像能跳到你主页）
- [ ] 换台电脑验证：

```powershell
git clone https://github.com/<你>/dangjian-agent.git D:\tmp\check
cd D:\tmp\check
Get-ChildItem -Force        # 代码在、.env 不在，就对了
```

---

## 附录 A：本项目实测数据（都是真跑出来的）

| 指标 | 数值 | 出处 |
|---|---|---|
| 项目文件夹总大小 | ≈ 1,059 MB | 资源管理器 |
| `.git` 目录 | 25 MB（其中打包历史 10.9 MB） | `git count-objects -vH` |
| 需要上传的文件 | 546 个 / 8.3 MB | `git ls-files` |
| 从零 init 的首次提交 | 539 个 | `git add -n . | Measure-Object -Line` |
| 学生包 zip（老师发的） | 4.8 MB / 615 条目 | `git archive -o 学生包.zip HEAD` |
| `venv-lock/` | 434 MB | 虚拟环境，内含一行 `*` 的 `.gitignore` 自保 |
| `.venv/` | 258 MB | `.gitignore` 挡 |
| `.mypy_cache/` | 186 MB | `.gitignore` 挡 |
| `frontend/`（含 node_modules 120 MB） | 123 MB | `frontend/.gitignore` 挡 |
| `tmp/` | 14 MB | `.gitignore` 挡 |

**结论**：上传的本质是"从 1GB 里挑出真正要传的那 8MB 代码"，而不是"把 1GB 搬上去"。`.gitignore` 就是你雇的门卫。

## 附录 B：命令速查卡

```powershell
git --version                                  # 装没装
git config --global user.name "张三"            # 身份（全局）
git config --global user.email "xxx@xx.com"

cd D:\code\dangjian-agent                      # 进项目
git init                                       # 初始化
git branch -M main                             # 分支名统一
git status                                     # 看状态
git add .                                      # 暂存全部
git commit -m "chore: 首次提交"                 # 提交
git remote add origin <地址>                    # 关联远程
git push -u origin main                        # 首次推送
git push                                       # 以后推送

git config --global --get http.proxy           # 看代理
git config --global http.proxy http://127.0.0.1:7897    # 配代理
git config --global --unset http.proxy                  # 清代理
```
