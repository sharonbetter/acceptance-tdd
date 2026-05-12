# Harness 测试执行抽象层 (Test Execution Abstraction Layer)

让 Harness CI/CD 通过「路由引擎」对接多端测试工具，而非直接耦合具体工具实现。

---

## 核心架构

```
Harness Pipeline
      │
      ▼
┌─────────────────────────────────────────┐
│     Universal Test Runner Docker Image    │
│  ┌───────────────────────────────────┐  │
│  │     entrypoint.sh (路由引擎)       │  │
│  │  读取 .harness-test.json          │  │
│  │  根据 project_type 动态拼接 CLI   │  │
│  └───────────────────────────────────┘  │
│            │           │           │    │
│      Web/Playwright  App/Appium   API/Pytest │
└─────────────────────────────────────────┘
      │
      ▼
JUnit XML 统一报告
      │
      ▼
Harness Tests Tab (统一仪表盘)
```

---

## 文件约定

| 文件 | 位置 | 用途 |
|------|------|------|
| `.harness-test.json` | 代码库根目录 | 声明项目类型、目标工具、测试套件路径 |
| `entrypoint.sh` | Runner 镜像内 | 路由脚本，根据环境变量调用对应工具 |
| `test-config.yaml` | 可选，项目级 | 扩展配置（超时、报告路径、重试次数等） |
| `*.feature` | 测试目录 | BDD Gherkin 格式测试用例 |

---

## 元数据驱动任务定义

### .harness-test.json（必填）

```json
{
  "project_name": "my-service",
  "project_type": "web | mobile | desktop | api",
  "target_tool": "playwright | appium | katalon | pytest | cypress",
  "test_suite": "tests/e2e/**/*.feature",
  "tool_config": {
    "playwright": {
      "config_file": "playwright.config.ts",
      "reporter": "junit",
      "reporter_output": "reports/junit.xml"
    },
    "appium": {
      "platform": "android | ios",
      "app_package": "com.example.app",
      "reporter": "junit",
      "reporter_output": "reports/junit.xml"
    },
    "pytest": {
      "config_file": "pytest.ini",
      "reporter": "junitxml",
      "reporter_output": "reports/junit.xml"
    }
  },
  "harness": {
    "delegate_profile": "k8s-delegate",
    "timeout_minutes": 30,
    "retry_count": 1
  }
}
```

### test-config.yaml（可选）

```yaml
project_name: my-service
project_type: web
target_tool: playwright

timeout_minutes: 30
retry_count: 1

report:
  format: junit
  path: reports/junit.xml

tools:
  playwright:
    config: playwright.config.ts
    browser: chromium
    headless: true
  appium:
    platform: android
    app_package: com.example.app
  pytest:
    markers:
      - smoke
      - regression
```

---

## 工具与项目类型映射

| project_type | 推荐 target_tool | 说明 |
|-------------|-----------------|------|
| `web` | `playwright` / `cypress` / `selenium` | 浏览器自动化 |
| `mobile` | `appium` | iOS/Android 原生应用 |
| `desktop` | `playwright-desktop` / `win-app-driver` | Windows/Mac 桌面应用 |
| `api` | `pytest` / `postman-newman` | REST/GraphQL API 测试 |

---

## 执行器镜像构建

### Dockerfile 示例

```dockerfile
FROM node:20-slim AS base

# 安装运行时
RUN apt-get update && apt-get install -y \
    python3 python3-pip openjdk-17-jdk \
    curl unzip \
    && rm -rf /var/lib/apt/lists/*

# Playwright
RUN npm install -g playwright@latest \
    && npx playwright install --with-deps chromium

# Appium
RUN npm install -g appium@latest \
    && npx appium --version

# Python 测试工具
RUN pip3 install pytest pytest-xdist pytest-html \
    pytest-junitxml allure-pytest

# 路由入口
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /workspace
ENTRYPOINT ["/entrypoint.sh"]
```

### entrypoint.sh 路由脚本

```bash
#!/bin/bash
set -e

# 读取项目元数据
PROJECT_CONFIG="${PROJECT_CONFIG:-.harness-test.json}"
PROJECT_TYPE="${PROJECT_TYPE:-$(grep -o '"project_type": *"[^"]*"' $PROJECT_CONFIG | cut -d'"' -f4)}"
TARGET_TOOL="${TARGET_TOOL:-$(grep -o '"target_tool": *"[^"]*"' $PROJECT_CONFIG | cut -d'"' -f4)}"
TEST_SUITE="${TEST_SUITE:-$(grep -o '"test_suite": *"[^"]*"' $PROJECT_CONFIG | cut -d'"' -f4)}"

echo "[Router] project_type=$PROJECT_TYPE, target_tool=$TARGET_TOOL, test_suite=$TEST_SUITE"

# 执行路由
case "$TARGET_TOOL" in
  playwright)
    echo "[Router] Launching Playwright..."
    npx playwright test \
      --config="${PLAYWRIGHT_CONFIG:-playwright.config.ts}" \
      --reporter=junit \
      --reporter=line \
      "$TEST_SUITE"
    ;;

  appium)
    echo "[Router] Launching Appium..."
    pytest tests/mobile/ \
      --driver=appium \
      --junitxml=reports/junit.xml \
      -v
    ;;

  pytest)
    echo "[Router] Launching Pytest..."
    pytest \
      "$TEST_SUITE" \
      --junitxml=reports/junit.xml \
      --tb=short \
      -v
    ;;

  cypress)
    echo "[Router] Launching Cypress..."
    npx cypress run \
      --reporter=junit \
      --reporter-output-path=reports/junit.xml
    ;;

  *)
    echo "[Router] Unknown tool: $TARGET_TOOL, falling back to Selenium..."
    python3 run_selenium.py --suite="$TEST_SUITE"
    ;;
esac

echo "[Router] Test execution completed."
```

---

## BDD Gherkin 格式标准化

### 为什么用 Gherkin？

- **平台无关**：`Given/When/Then` 描述业务行为，不依赖工具
- **多端复用**：同一 `.feature` 文件可对接 Playwright（Web）、Appium（Mobile）、Pytest（API）
- **Prompt 友好**：AI 生成测试用例时直接输出 Gherkin 文本

### 多端 Steps Definition 示例

**Web (Playwright):**
```typescript
// steps/web-steps.ts
import { Given, When, Then } from '@playwright/test';

Given('用户在登录页面', async ({ page }) => {
  await page.goto('/login');
});

When('用户输入用户名 {string} 和密码 {string}', async ({ page }, username, password) => {
  await page.fill('#username', username);
  await page.fill('#password', password);
});

Then('系统显示登录成功消息', async ({ page }) => {
  await expect(page.locator('.success-message')).toBeVisible();
});
```

**Mobile (Appium):**
```python
# steps/mobile_steps.py
from behave import given, when, then

@given('用户在移动端登录页面')
def step_user_on_mobile_login(context):
    context.driver.start_activity('com.example.app', '.LoginActivity')

@when('用户输入用户名和密码')
def step_user_inputs_credentials(context):
    context.driver.find_element_by_id('username').send_keys('testuser')
    context.driver.find_element_by_id('password').send_keys('password123')

@then('系统显示登录成功')
def step_login_success(context):
    assert context.driver.find_element_by_id('success').is_displayed()
```

**API (Pytest):**
```python
# steps/api_steps.py
from behave import given, when, then
import requests

@given('API 服务可用')
def step_api_available(context):
    response = requests.get('https://api.example.com/health')
    assert response.status_code == 200

@when('发送 POST 请求到 {endpoint}，body 为 {body}')
def step_send_post(context, endpoint, body):
    context.response = requests.post(f'https://api.example.com/{endpoint}', json=eval(body))

@then('响应状态码为 {status_code}')
def step_check_status(context, status_code):
    assert context.response.status_code == int(status_code)
```

---

## Harness Pipeline 配置

### 方案 A：单入口路由脚本（推荐）

在 Harness Step 中使用 `Shell Script`：

```bash
# 1. 读取项目元数据
PROJECT_CONFIG=".harness-test.json"
PROJECT_TYPE=$(grep -o '"project_type": *"[^"]*"' $PROJECT_CONFIG | cut -d'"' -f4)
TARGET_TOOL=$(grep -o '"target_tool": *"[^"]*"' $PROJECT_CONFIG | cut -d'"' -f4)

echo "Detecting project type: $PROJECT_TYPE, target tool: $TARGET_TOOL..."

# 2. 根据类型选择工具并运行
case "$TARGET_TOOL" in
  playwright)
    echo "Launching Playwright..."
    npx playwright test --config=playwright.config.ts --reporter=junit
    ;;
  appium)
    echo "Launching Appium..."
    pytest tests/mobile/ --driver=appium --junitxml=reports/junit.xml
    ;;
  pytest)
    echo "Launching Pytest..."
    pytest tests/api/ --junitxml=reports/junit.xml
    ;;
  cypress)
    echo "Launching Cypress..."
    npx cypress run --reporter=junit --reporter-output-path=reports/junit.xml
    ;;
  *)
    echo "Unknown platform, exiting..."
    exit 1
    ;;
esac
```

### 方案 B：Harness 矩阵执行

```yaml
pipeline:
  stages:
    - stage:
        name: Test Execution
        spec:
          execution:
            steps:
              - stepGroup:
                  name: Multi-Platform Tests
                  parallel:
                    - step:
                        name: Web Tests
                        type: ShellScript
                        spec:
                          shell: Bash
                          command: npx playwright test --reporter=junit
                          environmentVariables:
                            TARGET_TOOL: playwright
                    - step:
                        name: API Tests
                        type: ShellScript
                        spec:
                          shell: Bash
                          command: pytest tests/api/ --junitxml=reports/junit.xml
                          environmentVariables:
                            TARGET_TOOL: pytest
```

---

## JUnit 报告归一化

所有工具统一输出 JUnit XML 格式，Harness Tests Tab 原生支持。

| 工具 | JUnit 输出参数 |
|------|--------------|
| Playwright | `--reporter=junit` |
| Pytest | `--junitxml=reports/junit.xml` |
| Cypress | `mocha-junit-reporter` |
| Appium | `--junitxml=reports/junit.xml` |

Harness 配置：
```
Tests Tab → Add Test Coverage
  Path: reports/junit.xml
  Format: JUnit
```

---

## 决策流

| 判断维度 | 实现方式 |
|---------|---------|
| 项目类型识别 | 代码库根目录 `.harness-test.json` 声明 |
| 动态工具调用 | entrypoint.sh 读取 JSON，动态拼接 CLI |
| 用例生成适配 | AI 生成 `.feature` 文件 + 对应 Steps Definition |
| 环境隔离 | Harness Delegate 部署在 K8s 集群，容器按需挂载工具 |

---

## 快速开始

1. **在代码库根目录添加 `.harness-test.json`**，声明 project_type 和 target_tool
2. **编写 `.feature` Gherkin 测试用例**
3. **为项目类型编写对应的 Steps Definition**（Web/App/API）
4. **在 Harness Pipeline 中添加 Shell Script Step**，调用 entrypoint.sh 或直接执行路由脚本
5. **配置 Harness Tests Tab**，路径指向 `reports/junit.xml`

---

## 注意事项

- **环境依赖**：跑 Web 需要浏览器二进制，跑 Mobile 需要 Android SDK/模拟器。Runner 镜像应按需预装。
- **超时设置**：不同工具耗时差异大，建议在 `.harness-test.json` 的 `harness.timeout_minutes` 中配置。
- **失败重试**：API 不稳定场景建议 `retry_count: 1`，Web/App 可设为 0。
