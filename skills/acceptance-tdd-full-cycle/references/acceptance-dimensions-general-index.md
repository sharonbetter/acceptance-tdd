# 通用验收维度（详细）— 总览与索引

**用途**：在编写 **验收场景**（每条须 **Given / When / Then**）时，除 **正常、异常、边界、参数非法** 外，按本目录下列文档**逐项查漏**，把可验收点写进你的验收文档（结构见同包 [atdd-checklist-template.md](atdd-checklist-template.md)）。

**与本包 `SKILL.md` 第 2 节（ATDD）对齐**：每条验收场景须 **Given / When / Then** 齐全，**Then** 为对外可观察判据；在 **正常、异常、边界、参数非法** 之外再按 **当前业务领域** 补充。本目录各 **`acceptance-*.md`** 用于 **Then 判据查漏** 与场景备忘，落表格式、**待确认** 与 **2.1 验收文档交用户确认（闸门）** 见同包 [atdd-checklist-template.md](atdd-checklist-template.md)。

**与「领域形态」及横切维度的分工（本技能内）**：**本目录 `acceptance-*.md`** 负责 **通用业务面**（登录、权限、分页、搜索、页面、手势等）与 **分领域 Then 展开**（各 `acceptance-domain-*`）。「本迭代命中 [domain-system-focus-areas.md](domain-system-focus-areas.md) 表中哪些形态」的判定与备忘见该文件；**横切质量与体验（DIM+UX）** 见 [cross-cutting-coverage-dimensions.md](cross-cutting-coverage-dimensions.md)。三处与 **验收场景表** 之间只 **互链** 场景标题或编号，**勿**各写一套矛盾的 Then。

---

## 文档索引（建议按迭代涉及模块勾选阅读）

| 主题 | 文档 | 典型触发 |
|------|------|-----------|
| 登录与会话 | [acceptance-general-auth-login.md](acceptance-general-auth-login.md) | 有账号体系、会话、Cookie/Token |
| 注册与开户 | [acceptance-general-auth-register.md](acceptance-general-auth-register.md) | 有自助注册、邀请码、企业开户 |
| 权限与越权 | [acceptance-general-permissions.md](acceptance-general-permissions.md) | 有角色、资源级权限、多用户 |
| 批量与分页 | [acceptance-general-batch-pagination.md](acceptance-general-batch-pagination.md) | 列表、导入导出、历史数据迁移 |
| 搜索与筛选 | [acceptance-general-search.md](acceptance-general-search.md) | 有查询、排序、组合条件 |
| 页面与数据流 | [acceptance-general-ui-pages.md](acceptance-general-ui-pages.md) | 有 Web/App 页面、路由、缓存 |
| 交互与手势 | [acceptance-general-user-interactions.md](acceptance-general-user-interactions.md) | 有复杂手势、移动端、可访问性 |

---

## 落表建议

1. 从本索引勾选相关子文档，将其中 **「须写进 Then 的判据」** 摘成验收场景行或子场景。  
2. 与安全、合规、**不可观察**内部相关的点：在 **Then** 写**可验证 proxy**（如 HTTPS、响应头、审计日志字段存在性由集成测约定），或标 **手工 / 安全专项**。  
3. 与 **多份 acceptance-** 或「领域形态概要」重叠时（如登录 + 多租户）：在一处写全 Then，他处只 **互链** 场景名/编号，避免两套矛盾判据。
