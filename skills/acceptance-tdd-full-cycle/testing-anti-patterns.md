# 测试反模式（禁止使用）

- 测 mock 行为而非真实行为。  
- 为通过测试给生产类加 test-only API。  
- 未理解依赖就全局 mock。  
- 断言实现细节而非可观察行为：用例名与断言应写 **WHAT**（用户/调用方可观察结果），避免只锁 **HOW**（详见 [testing-style-observable-behavior.md](testing-style-observable-behavior.md)）。

**产码纪律**仍以本包 [references/tdd-core.md](references/tdd-core.md) 为准。

