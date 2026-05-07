# references 参考文档目录

本目录归集所有：模板、规范、通用验收点、领域验收点、TDD 纪律底座。

## 文件分类

### 1. 基础底座
- `tdd-core.md`：产码 TDD 铁律流程
- `atdd-checklist-template.md`：ATDD 正式验收文档模板

### 2. 质量横切维度
- `cross-cutting-coverage-dimensions.md`：逆向/多入口/体验/运维横切覆盖
- `domain-system-focus-areas.md`：判断当前需求属于哪些业务重域

### 3. 通用公共验收（所有系统通用）
`acceptance-general-*` 开头：
- `acceptance-general-auth-login.md` — 登录与会话
- `acceptance-general-auth-register.md` — 注册与开户
- `acceptance-general-permissions.md` — 权限管理
- `acceptance-general-batch-pagination.md` — 批量与分页
- `acceptance-general-search.md` — 搜索与筛选
- `acceptance-general-ui-pages.md` — 页面功能与数据流
- `acceptance-general-user-interactions.md` — 页面操作与手势

### 4. 领域专项验收（垂直业务）
`acceptance-domain-*` 开头：
- `acceptance-domain-commerce-payment.md` — 支付交易
- `acceptance-domain-order-fulfillment.md` — 订单履约
- `acceptance-domain-inventory-warehouse.md` — 库存仓储
- `acceptance-domain-messaging-async.md` — 异步消息
- `acceptance-domain-ops-config.md` — 运营配置
- `acceptance-domain-ads-recommendation.md` — 广告推荐
- `acceptance-domain-subscription-billing.md` — 订阅计费
- `acceptance-domain-permissions-multitenancy.md` — 多租户权限

## 使用顺序

1. 先用 `domain-system-focus-areas.md` 判定领域形态
2. 套用 `atdd-checklist-template.md` 编写验收清单
3. 对照 `cross-cutting-coverage-dimensions.md` 补全质量边角
4. 对应领域/通用 md 补齐专业验收点
5. 落地开发遵守 `tdd-core.md`
