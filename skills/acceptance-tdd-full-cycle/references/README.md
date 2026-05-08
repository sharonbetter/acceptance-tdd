# `acceptance-tdd-full-cycle` 包内索引

本技能材料位于 **`SKILL.md`**、本 `references/` 目录及**上一级**的 `testing-*.md`。**验收与领域相关内容均在本目录闭环**，不引用其它路径。

| 文件 | 说明 |
|------|------|
| [tdd-core.md](tdd-core.md) | 产码 TDD 铁律与红绿循环（产码节奏以该文为准） |
| [atdd-checklist-template.md](atdd-checklist-template.md) | **验收文档确认**、**执行记录配套文件 `*.execution-log.md`**、主表 **场景名称 + 场景 ID**、Given/When/Then、**待确认**（**用户视角问句**）、**逐项确认节奏**、映射表；文末 **满减下单** 示例 |
| [domain-system-focus-areas.md](domain-system-focus-areas.md) | **领域分类**判定表 + 与各 `acceptance-domain-*` **交叉引用** |
| [cross-cutting-coverage-dimensions.md](cross-cutting-coverage-dimensions.md) | **横切维度与体验** 摘要（文内 **DIM** 为缩写，见该文说明） |
| [acceptance-dimensions-general-index.md](acceptance-dimensions-general-index.md) | **通用验收维度**总览 → 下列各篇 |
| [acceptance-general-auth-login.md](acceptance-general-auth-login.md) | 登录态、一致性、传输与日志 |
| [acceptance-general-auth-register.md](acceptance-general-auth-register.md) | 注册唯一性、校验、密码策略 |
| [acceptance-general-permissions.md](acceptance-general-permissions.md) | 权限有效、水平/垂直越权 |
| [acceptance-general-batch-pagination.md](acceptance-general-batch-pagination.md) | 分页边界、兼容、批量幂等 |
| [acceptance-general-search.md](acceptance-general-search.md) | 搜索组合、排序 |
| [acceptance-general-ui-pages.md](acceptance-general-ui-pages.md) | 路由、参数、组件态、缓存、请求体 |
| [acceptance-general-user-interactions.md](acceptance-general-user-interactions.md) | 点击、滑动、拖拽、长按与反馈 |
| [acceptance-domain-commerce-payment.md](acceptance-domain-commerce-payment.md) | 交易 / 支付 |
| [acceptance-domain-order-fulfillment.md](acceptance-domain-order-fulfillment.md) | 订单履约 |
| [acceptance-domain-inventory-warehouse.md](acceptance-domain-inventory-warehouse.md) | 库存 / 仓储 |
| [acceptance-domain-permissions-multitenancy.md](acceptance-domain-permissions-multitenancy.md) | 权限 / 多租户 |
| [acceptance-domain-subscription-billing.md](acceptance-domain-subscription-billing.md) | 订阅 / 计费 |
| [acceptance-domain-messaging-async.md](acceptance-domain-messaging-async.md) | 消息 / 异步 |
| [acceptance-domain-live-realtime.md](acceptance-domain-live-realtime.md) | 直播 / 实时 |
| [acceptance-domain-ops-config.md](acceptance-domain-ops-config.md) | 运营后台 / 配置 |
| [acceptance-domain-ads-recommendation.md](acceptance-domain-ads-recommendation.md) | 广告 / 推荐 |

**上一级（与 `SKILL.md` 同目录）**

| 文件 | 说明 |
|------|------|
| [../testing-style-observable-behavior.md](../testing-style-observable-behavior.md) | **WHAT / HOW** |
| [../testing-anti-patterns.md](../testing-anti-patterns.md) | **反模式与 Mock 禁区** |

**阅读顺序（验收 → 产码）**  

上一级 [`../SKILL.md`](../SKILL.md) → [atdd-checklist-template.md](atdd-checklist-template.md) → [domain-system-focus-areas.md](domain-system-focus-areas.md) / [cross-cutting-coverage-dimensions.md](cross-cutting-coverage-dimensions.md) → [acceptance-dimensions-general-index.md](acceptance-dimensions-general-index.md) 及所需 **acceptance-domain-*** → [tdd-core.md](tdd-core.md) → [../testing-style-observable-behavior.md](../testing-style-observable-behavior.md) → [../testing-anti-patterns.md](../testing-anti-patterns.md)。

