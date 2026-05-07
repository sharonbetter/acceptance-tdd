# acceptance-tdd

**验收测试驱动 + TDD 全链路开发方法论**

---

## 🎯 这个 Skill 是做什么的？

当你有 `spec / 需求说明 / 技术方案`，需要把功能**做到可验收、可回归**时，使用本技能。

它将「业务上做什么」（验收）与「代码上怎么证」（测试）绑定在同一条链路，确保交付物真正符合业务预期。

---

## 🔄 工作流（按顺序执行）

### 1️⃣ 理解与澄清
通读需求文档，识别**歧义点 / 缺失点 / 争议点**，用用户视角提问并记录结论。

### 2️⃣ ATDD 验收场景定义（Given / When / Then）
- **Given**：前置条件
- **When**：触发动作
- **Then**：可观察预期结果（HTTP 响应 / UI 变化 / DB 状态 / 日志输出）

### 3️⃣ 验收文档确认（闸门）
阻塞性问题闭环后，将完整验收文档交付**业务方审阅确认**，**未经确认禁止进入结构设计与开发**。

### 4️⃣ 结构设计
从验收点反推模块职责、接口契约与数据模型。

### 5️⃣ TDD 产码
严格遵循 **红→绿→重构** 铁律：
- 先写一条失败用例
- 只写最少代码使其通过
- 在仍绿前提下重构

### 6️⃣ 外环自动化覆盖
按横切维度 + 领域专项补全测试覆盖。

---

## 📁 目录结构

```
acceptance-tdd/
├── SKILL.md                         # 主技能定义（方法论核心）
├── testing-anti-patterns.md         # ❌ 禁止使用的测试反模式
├── testing-style-observable-behavior.md  # ✅ 正确的断言风格
└── references/
    ├── README.md                    # 参考文档索引
    ├── tdd-core.md                  # TDD 产码铁律
    ├── atdd-checklist-template.md  # ATDD 验收文档模板
    ├── cross-cutting-coverage-dimensions.md  # 横切维度覆盖
    ├── domain-system-focus-areas.md # 业务重域判定
    │
    ├── acceptance-general-*.md      # 通用验收点（所有系统适用）
    │   ├── auth-login.md
    │   ├── auth-register.md
    │   ├── permissions.md
    │   ├── batch-pagination.md
    │   ├── search.md
    │   ├── ui-pages.md
    │   └── user-interactions.md
    │
    └── acceptance-domain-*.md       # 领域专项验收（垂直业务）
        ├── commerce-payment.md      # 电商支付
        ├── order-fulfillment.md     # 订单履约
        ├── inventory-warehouse.md   # 库存仓储
        ├── messaging-async.md       # 异步消息
        ├── ops-config.md            # 运营配置
        ├── ads-recommendation.md    # 广告推荐
        ├── subscription-billing.md  # 订阅计费
        └── permissions-multitenancy.md  # 多租户权限
```

---

## ⚡ 核心原则

| 原则 | 说明 |
|------|------|
| **验收先行** | 无确认的验收文档，不写一行代码 |
| **用户视角** | 验收口径从用户/业务视角出发，非纯技术视角 |
| **可观察断言** | Then 必须可被 HTTP/UI/DB/日志直接验证，禁止空话 |
| **全程追溯** | 从需求澄清到自动化用例，全程可追溯、可审计 |
| **先红后绿** | TDD 产码必须先有失败用例，再写实现 |

---

## 📝 执行记录管理

- 新建/实质修订验收文档时，必须在**同名的侧车文件** `*.execution-log.md` 追加记录
- 主文档只保留执行记录引用，**不内嵌大表**
- 侧车记录真实用到的文档路径，禁止重写未读文件

---

## 🏷️ 适用场景

- 从 0 到 1 的新功能开发
- 需求变更导致的功能重构
- 需要对接第三方系统的集成验证
- 需要满足合规或审计要求的验收文档

---

## 🔗 相关文档

- `references/atdd-checklist-template.md` — ATDD 正式验收文档模板
- `references/tdd-core.md` — TDD 产码铁律详解
- `testing-style-observable-behavior.md` — 断言风格指南
- `testing-anti-patterns.md` — 测试反模式清单
