#!/bin/bash
set -e

# ============================================================
# Universal Test Runner - 路由引擎
# 用法: entrypoint.sh 或 entrypoint.sh <project_config_json>
# ============================================================

PROJECT_CONFIG="${PROJECT_CONFIG:-.harness-test.json}"
PROJECT_TYPE="${PROJECT_TYPE:-$(grep -o '"project_type": *"[^"]*"' "$PROJECT_CONFIG" 2>/dev/null | head -1 | cut -d'"' -f4)}"
TARGET_TOOL="${TARGET_TOOL:-$(grep -o '"target_tool": *"[^"]*"' "$PROJECT_CONFIG" 2>/dev/null | head -1 | cut -d'"' -f4)}"
TEST_SUITE="${TEST_SUITE:-$(grep -o '"test_suite": *"[^"]*"' "$PROJECT_CONFIG" 2>/dev/null | head -1 | cut -d'"' -f4)}"
REPORTER_OUTPUT="${REPORTER_OUTPUT:-reports/junit.xml}"

echo "[Router] ==========================================="
echo "[Router] Universal Test Runner v1.0"
echo "[Router] ==========================================="
echo "[Router] project_type=$PROJECT_TYPE"
echo "[Router] target_tool=$TARGET_TOOL"
echo "[Router] test_suite=$TEST_SUITE"
echo "[Router] reporter_output=$REPORTER_OUTPUT"
echo "[Router] ==========================================="

# 创建报告目录
mkdir -p "$(dirname "$REPORTER_OUTPUT")"

# 执行路由
case "$TARGET_TOOL" in
  playwright)
    echo "[Router] → Launching Playwright..."
    PLAYWRIGHT_CONFIG="${PLAYWRIGHT_CONFIG:-$(grep -o '"config_file": *"[^"]*"' "$PROJECT_CONFIG" 2>/dev/null | cut -d'"' -f4)}"
    PLAYWRIGHT_CONFIG="${PLAYWRIGHT_CONFIG:-playwright.config.ts}"
    npx playwright test \
      --config="$PLAYWRIGHT_CONFIG" \
      --reporter=junit \
      --reporter-output-path="$REPORTER_OUTPUT" \
      "$TEST_SUITE"
    echo "[Router] → Playwright completed."
    ;;

  appium)
    echo "[Router] → Launching Appium..."
    PLATFORM="$(grep -o '"platform": *"[^"]*"' "$PROJECT_CONFIG" 2>/dev/null | cut -d'"' -f4)"
    pytest tests/mobile/ \
      --driver=appium \
      --platform="$PLATFORM" \
      --junitxml="$REPORTER_OUTPUT" \
      -v
    echo "[Router] → Appium completed."
    ;;

  pytest)
    echo "[Router] → Launching Pytest..."
    PYTEST_CONFIG="${PYTEST_CONFIG:-$(grep -o '"config_file": *"[^"]*"' "$PROJECT_CONFIG" 2>/dev/null | cut -d'"' -f4)}"
    pytest \
      "$TEST_SUITE" \
      --junitxml="$REPORTER_OUTPUT" \
      --tb=short \
      ${PYTEST_CONFIG:+-c "$PYTEST_CONFIG"} \
      -v
    echo "[Router] → Pytest completed."
    ;;

  cypress)
    echo "[Router] → Launching Cypress..."
    npx cypress run \
      --reporter=junit \
      --reporter-output-path="$REPORTER_OUTPUT"
    echo "[Router] → Cypress completed."
    ;;

  selenium)
    echo "[Router] → Launching Selenium..."
    python3 run_selenium.py --suite="$TEST_SUITE" --output="$REPORTER_OUTPUT"
    echo "[Router] → Selenium completed."
    ;;

  katalon)
    echo "[Router] → Launching Katalon..."
    katalon-execute.sh \
      -browser="ChromeHeadless" \
      -testSuiteCollection="$TEST_SUITE" \
      -reportFolder="reports" \
      -reportFileName="junit.xml"
    echo "[Router] → Katalon completed."
    ;;

  *)
    echo "[Router] ✗ Unknown tool: $TARGET_TOOL"
    echo "[Router] ✗ Supported tools: playwright, appium, pytest, cypress, selenium, katalon"
    exit 1
    ;;
esac

echo "[Router] ==========================================="
echo "[Router] Test execution completed successfully."
echo "[Router] Report: $REPORTER_OUTPUT"
echo "[Router] ==========================================="
