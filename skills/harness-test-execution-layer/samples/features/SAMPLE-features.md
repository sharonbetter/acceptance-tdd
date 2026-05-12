# Sample E2E Feature Files
# 展示如何用 Gherkin 描述跨平台测试用例

## 目录结构

```
samples/
├── features/
│   ├── web/
│   │   ├── login.feature
│   │   └── checkout.feature
│   ├── api/
│   │   └── user-api.feature
│   └── mobile/
│       └── login-mobile.feature
└── steps/
    ├── web-steps.ts
    ├── api-steps.py
    └── mobile-steps.py
```

## 示例：登录功能（Web）

```gherkin
Feature: 用户登录

  Scenario: 使用有效凭据登录成功
    Given 用户在登录页面
    When 用户输入用户名 "testuser@example.com" 和密码 "ValidPass123"
    And 用户点击登录按钮
    Then 系统显示登录成功消息
    And 系统跳转到首页

  Scenario: 使用无效凭据登录失败
    Given 用户在登录页面
    When 用户输入用户名 "testuser@example.com" 和密码 "WrongPassword"
    And 用户点击登录按钮
    Then 系统显示错误消息 "用户名或密码错误"
    And 系统保持在登录页面

  Scenario: 用户名格式错误
    Given 用户在登录页面
    When 用户输入用户名 "not-an-email"
    And 用户点击登录按钮
    Then 系统显示验证错误 "请输入有效的邮箱地址"
```

## 示例：API 端点（API）

```gherkin
Feature: 用户管理 API

  Scenario: 创建新用户成功
    Given API 服务可用
    When 发送 POST 请求到 "/users"，body 为
      """
      {
        "name": "张三",
        "email": "zhangsan@example.com",
        "password": "SecurePass123"
      }
      """
    Then 响应状态码为 201
    And 响应 body 包含 "id"
    And 响应 body 包含 "email"

  Scenario: 创建用户 - 邮箱格式错误
    Given API 服务可用
    When 发送 POST 请求到 "/users"，body 为
      """
      {
        "name": "张三",
        "email": "invalid-email",
        "password": "SecurePass123"
      }
      """
    Then 响应状态码为 400
    And 响应 body 包含 "email" 字段的验证错误

  Scenario: 查询用户详情
    Given 用户 "testuser@example.com" 已存在
    When 发送 GET 请求到 "/users/{id}"
    Then 响应状态码为 200
    And 响应 body 包含 "name" 和 "email"
```

## 示例：移动端登录（Mobile）

```gherkin
Feature: 移动端登录

  Scenario: 在 iOS 设备上登录成功
    Given 用户在 iOS 应用的登录页面
    When 用户输入邮箱 "testuser@example.com"
    And 用户输入密码 "ValidPass123"
    And 用户点击 "登录" 按钮
    Then 系统显示加载动画
    And 几秒后系统跳转到首页
    And 用户头像显示在导航栏

  Scenario: 在 Android 设备上登录 - 密码错误
    Given 用户在 Android 应用的登录页面
    When 用户输入邮箱 "testuser@example.com"
    And 用户输入密码 "WrongPassword"
    And 用户点击 "登录" 按钮
    Then 系统显示 Toast 提示 "登录失败，请检查凭据"
```

## Steps Definition 框架映射

| 平台 | 框架 | Steps Definition 文件 |
|------|------|----------------------|
| Web | Playwright | `steps/web-steps.ts` |
| Mobile | Appium + Behave | `steps/mobile-steps.py` |
| API | Pytest + Behave | `steps/api-steps.py` |
| Web | Cypress + Cucumber | `steps/cypress-steps.js` |
