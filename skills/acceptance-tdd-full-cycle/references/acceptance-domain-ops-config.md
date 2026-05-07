# 领域验收：运营后台 / 配置

**适用**：涉及「运营后台 / 配置」时展开。与 **通用权限** 强相关：[acceptance-general-permissions.md](acceptance-general-permissions.md)

---

## 1. 发布生效

| 验收点 | Then 判据示例 |
| --- | --- |
| 配置草稿 vs 线上 | 发布后 C 端/B 端读取到新值；**无**半套新旧混杂（除非灰度） |
| 生效时间 | 定时生效到点可验 |

---

## 2. 灰度

| 验收点 | Then 判据示例 |
| --- | --- |
| 按用户/百分比/地域 | 命中规则的用户行为与未命中区分清晰 |
| 回滚 | 关闭灰度后恢复基线 |

---

## 3. 误操作回滚

| 验收点 | Then 判据示例 |
| --- | --- |
| 版本历史 | 可恢复到指定版本；审计 who/when |
| 破坏性操作二次确认 | 与 spec 一致 |

---

## 4. 批量导入校验

| 验收点 | Then 判据示例 |
| --- | --- |
| 行级校验错误报告 | 可下载错误行；修正后可重导 |
| 与 [acceptance-general-batch-pagination.md](acceptance-general-batch-pagination.md) | 大文件分片、超时、幂等 |
