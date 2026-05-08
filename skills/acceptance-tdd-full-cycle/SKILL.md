---
name: acceptance-tdd-full-cycle
description: >-
  验收驱动全链路：读懂需求；歧义/缺失/争议单列「待确认」，**用户视角发问**；**逐项请用户确认**，确认后**自动带出下一项**；ATDD 主表含**场景名称**与 **Given/When/Then**；**执行记录**写入与主稿同名的 **`.execution-log.md` 侧车文件**（主稿仅一行链接）；**整体验收文档闸门**通过后再结构、TDD、外环至全绿。
  通用/领域验收细则见 references/acceptance-dimensions-general-index.md（同目录 acceptance-*.md）。产码纪律见 references/tdd-core.md；**断言 WHAT / Mock 禁区**见本包 testing-style-observable-behavior.md 与 testing-anti-patterns.md（须结合阅读）。
---

# 验收测试驱动 + TDD 全周期

**先验收、后实现；验收文档成稿后先交用户确认，再动结构与产码；先单测/集成红绿，再外环自动化；未全绿不宣称完成。**

---

## 何时启用

- 从 spec / 需求说明 / 技术方案出发，要把功能**做到可验收、可回归**。  
- 需要把「业务上验什么」与「代码上怎么证」绑在同一条链路上。

---

## 工作流（按顺序，可迭代）

### 1. 理解

通读手头 **spec、需求、技术说明**；若存在未写清的依赖、数据、环境或边界，**向需求方提问**并记录结论（可写入团队约定的需求载体）。

**执行记录留痕（硬性）**：凡**新建**或**实质修订**主验收文档（表 A/B、主表、映射、Then 等），代理**不得**在主文内维护执行引用大表。须在 **侧车文件** 中追加，约定见 **[references/atdd-checklist-template.md](references/atdd-checklist-template.md)**「执行记录（侧车）」节：与主稿 **同目录**，文件名为 **`<主文件名>.execution-log.md`**（例：`feature-acceptance.md` → `feature-acceptance.execution-log.md`）；主稿正文**仅**保留一行指向该文件的链接。侧车表内**追加**本会话**真实打开并对照过**的路径：**须含**实际用过的技能包内 `SKILL.md` 与 `references/**`（未打开则不写）；**若**为对齐 Then 还打开了 **项目 spec、主验收稿、集成/ E2E 源文件**，一并写入，用途列注明「非技能包」。**禁止**冒充未读文件；**禁止**要求用户代填。

### 1.1 待确认问题（歧义 / 缺失 / 易争议）

凡需求存在 **歧义、缺失或易引发争议** 的点，**必须单独成表**，不得混在已写死的 Then 里假装已澄清。

- 使用 **[references/atdd-checklist-template.md](references/atdd-checklist-template.md)** 中的 **「待确认问题」** 与 **「待确认 → 测试映射」** 两表；**一行一问题**，`Q-ID` 全程稳定可追溯。  
- **用户视角发问（硬性）**：表内「澄清问句」**不得**只写实现视角（如「`PUT` 是否返回 400」）。须写清 **终端用户或业务读者能代入的情境**（「我正在…」「若我…」），再落到可选方案或判据；技术名词可放在括号里作对照。问句须**可直接复制**给产研/业务复述。  
- **逐项确认 + 自动下一代（硬性）**：与用户对话时，**每次只主动推进一项**待确认（默认顺序：**表 A 阻塞项**按 `A-xx` 升序 → **表 B** 按 `B-xx` 升序；若存在依赖，以依赖先决项优先）。用户给出可执行的结论后，代理须**同一轮内**：(1) 把结论写入验收文档（表 A/B、映射表、相关场景 **Then**、必要时「已决议」归档）；(2) **在回复末尾**自动附上**下一项**的、同样**用户视角**的可复制问句（若队列已空，则明确说明「待确认项已清」，并引导进入 **§2.1** 整体验收确认）。  
- **便于审计的答复格式**：鼓励用户答复时带 **`Q-ID`**（例如 `B-01：改为方案 2`），代理回填时原样记入「结论摘要」。  
- **答复与结论**填回后，须同步改对应验收场景的 **Then**，并补全 **接口/E2E 映射** 列，便于直接落成自动化用例名与断言。

### 2. ATDD：验收测试点（Given / When / Then）

每条验收场景须用 **Given / When / Then** 编写，且**三者缺一不可**。主表（见模板）中每行还须具备：

| 项 | 须写清的内容 |
|----|----------------|
| **场景名称** | **硬性**：一两句**面向产品/业务读者**的可读短名（说明「验什么」），与 **场景 ID** 并列；**禁止**用 `S-01` 代替名称、也禁止名称与 **Then** 完全同文重复无区分度。 |
| **场景 ID** | 稳定编号（如 `S-01`），供映射表、用例名、对话引用。 |

| 段 | 须写清的内容 |
|----|----------------|
| **Given** | **前置条件**：系统/用户/数据在动作发生前已处于何种状态（已登录、购物车已有商品、第三方返回成功等）。 |
| **When** | **用户操作或系统触发动作**：具体一步交互或事件（点击按钮、提交表单、定时任务触发、收到回调等）。 |
| **Then** | **预期结果**：对外可观察的断言（HTTP 状态、页面文案、持久化状态、消息内容等），避免只写「正常」而无判据。 |

在 **正常、异常、边界、参数非法** 四类上各至少覆盖若干条；再按**当前业务领域**补充场景（支付、权限、库存等）。  
落表格式与 **满减下单** 等完整 G/W/T 示例见 **[references/atdd-checklist-template.md](references/atdd-checklist-template.md)**（文末「完整示例」）。

**通用 + 领域验收细则（Then 判据查漏）**：以本包 **[references/acceptance-dimensions-general-index.md](references/acceptance-dimensions-general-index.md)** 为入口（同目录 `acceptance-*.md`）；**领域形态判定**见 [references/domain-system-focus-areas.md](references/domain-system-focus-areas.md)，**横切维度**见 [references/cross-cutting-coverage-dimensions.md](references/cross-cutting-coverage-dimensions.md)。以上均在本技能 `references/` 内闭环，与验收场景 **互链** 即可，避免重复或矛盾。

### 2.1 验收文档交用户确认（闸门）

在 **§2 验收场景表**（及 **§1.1 待确认问题** 中**阻塞项**已有答复或已标注「接受风险暂不澄清」）成稿后：

1. **§1.1 逐项确认**可与文档起草**穿插进行**：未决的 `Q-ID` 按上节规则逐项收口径；**不得**在未答复的阻塞项上把 **Then** 写死成单一实现（除非已标注假设与风险）。  
2. **将整份验收文档交付用户 / 需求方**（路径、Issue、飞书文档等形式由项目约定），明确请对方审阅 **Given/When/Then** 与 **Then 判据** 是否与其期望一致。  
3. **取得明确结论后再进入 §3**：对方确认无修订，或已根据反馈**改表并再次确认**；将结论记入 **[references/atdd-checklist-template.md](references/atdd-checklist-template.md)** 中的 **「验收文档确认」** 表（时间、结论、是否可开发）。  
4. **禁止**在未经该确认（或用户明示跳过闸门）前，开始 **§3 结构设计** 与后续产码；避免按错误 Then 白写实现。

### 3. 结构设计

**仅在 §2.1 闸门通过之后**，由验收点反推 **模块边界与接口**；先写清「谁负责什么」再写大段代码；**非必要不扩展**（YAGNI）。

### 4. TDD：实现与修改

对**每一处行为变更**遵守本包 **[references/tdd-core.md](references/tdd-core.md)**：**红 → 验红 → 绿 → 验绿 → 重构不加行为**。  
禁止：先写实现再补一个「一跑就绿」的测；禁止把未经验红的实现当「参考」边抄边写测。

**与本包两文结合（写测时必读）**

| 文档 | 解决什么 |
|------|----------|
| **[testing-style-observable-behavior.md](testing-style-observable-behavior.md)** | 用例名与断言锁 **WHAT**（可观察结果），避免锁 **HOW**（实现细节）。 |
| **[testing-anti-patterns.md](testing-anti-patterns.md)** | Mock 禁区：不测 mock 本身、不加 test-only 产码 API、不盲目全局 mock；并与上表第四条（WHAT/HOW）**对照**。 |

**读法**：先 **`tdd-core`** 定节奏与铁律 → 写每条断言前过 **`testing-style`** → 涉及替身/边界时过 **`testing-anti-patterns`**；三份一致才收工。

### 5. 端到端自动化

在 **§2.1 通过后**，将 **§2** 中的关键验收路径落成 **E2E**（工具与目录由项目约定）。  
对 **不确定的测试数据**（账号、订单号、第三方返回值等）**先向需求方或用户澄清**，再写进用例或配置。

### 6. 外环至全绿

跑通项目约定的 **E2E / 全量测试** 命令；失败则回到 **4** 用 TDD 修，再跑 **5～6**，直至**约定范围内的自动化全部通过**。  
声称完成前须**亲自执行**验证命令并得到通过输出（证据先于结论）。

---

## 自审（收工前）

- [ ] 每条验收场景是否均含 **场景名称**、**场景 ID** 与 **Given / When / Then**，且前置、动作、预期**可执行、可断言**？  
- [ ] **验收文档是否已交用户确认**并有记录（见模板「验收文档确认」表）；未通过确认前是否**未**进入结构设计？  
- [ ] 若本轮改过主验收正文，是否在对应的 **`.execution-log.md`** 侧车文件中**如实追加**了本会话实际对照过的路径（主文仅链接、无冒充、无让用户代填）？  
- [ ] **待确认问题**是否已单独列表；每条是否含 **用户视角、可复制** 的澄清问句；已答复的是否已回填 **Then** 与 **接口/E2E 映射**？  
- [ ] 对话中是否遵守 **逐项确认**，且在用户拍板一项后**自动带出下一项**（或明示队列已空）？  
- [ ] 是否覆盖 **正常 / 异常 / 边界 / 参数非法** 与 **领域**；并已按需对照 **[references/acceptance-dimensions-general-index.md](references/acceptance-dimensions-general-index.md)**、[references/domain-system-focus-areas.md](references/domain-system-focus-areas.md)、[references/cross-cutting-coverage-dimensions.md](references/cross-cutting-coverage-dimensions.md)？  
- [ ] 是否先有结构设计再堆产码？  
- [ ] 每条新行为是否 **见过红再见绿**？  
- [ ] 单测/集成是否按 **testing-style**（WHAT）与 **testing-anti-patterns**（Mock 禁区）写，而非锁实现细节或测 mock？  
- [ ] E2E 与单测/集成是否在当前分支 **全绿**？  
- [ ] 未决需求是否已 **提问** 或标注「待提供」？

---

## 刻意不做

- 用本技能名**替换** `npm test`、`test:all` 等仓库脚本名。  
- 无验收表即大段产码；或「表上写了 TDD」却从未**验红 / 验绿**。  
- 在 E2E 未稳定时绕过失败单测去「糊」核心逻辑。

---

## 本包内文档

| 文件 | 内容 |
|------|------|
| [references/tdd-core.md](references/tdd-core.md) | 产码侧 TDD 铁律与红绿重构（本技能自洽真源） |
| [testing-style-observable-behavior.md](testing-style-observable-behavior.md) | 可观察行为：**WHAT** 断言，避免 **HOW** 锁死 |
| [testing-anti-patterns.md](testing-anti-patterns.md) | 测试反模式与 Mock 禁区（与上一文档**结合**使用） |
| [references/atdd-checklist-template.md](references/atdd-checklist-template.md) | Given/When/Then、**待确认**、**验收文档确认**、**执行记录侧车（`.execution-log.md`）**、接口/E2E 映射模板 |
| [references/acceptance-dimensions-general-index.md](references/acceptance-dimensions-general-index.md) | **通用 + 领域验收点**总览；同目录 `acceptance-*.md` 为分篇细则 |
| [references/domain-system-focus-areas.md](references/domain-system-focus-areas.md) | **领域形态**判定与备忘（本包闭环） |
| [references/cross-cutting-coverage-dimensions.md](references/cross-cutting-coverage-dimensions.md) | **横切维度（DIM）与体验**（本包闭环） |
| [references/README.md](references/README.md) | 索引 |
