# ============================================================
# Universal Test Runner - Docker Image
# 用于 Harness CI/CD 测试执行抽象层
# ============================================================
# 构建: docker build -t universal-test-runner .
# 运行: docker run --rm \
#        -v $(pwd):/workspace \
#        -e PROJECT_CONFIG=.harness-test.json \
#        universal-test-runner
# ============================================================

FROM node:20-slim AS base

# 防止 npm scripts 以 root 运行
RUN npm config set unsafe-perm true

# ============================================================
# Stage 1: 安装系统依赖
# ============================================================
FROM base AS builder

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    openjdk-17-jdk \
    curl \
    wget \
    unzip \
    git \
    # Playwright 系统依赖
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# Stage 2: 安装 Node.js 工具
# ============================================================
FROM base AS node-tools

RUN npm install -g \
    playwright@latest \
    @playwright/test@latest \
    appium@latest \
    webdriver-manager@latest \
    cypress@latest

# 安装 Playwright 浏览器
RUN npx playwright install --with-deps chromium \
    && npx playwright install --with-deps firefox \
    && npx playwright install --with-deps webkit

# ============================================================
# Stage 3: 安装 Python 工具
# ============================================================
FROM node-tools AS python-tools

RUN pip3 install --no-cache-dir \
    pytest==8.3.0 \
    pytest-xdist==3.6.1 \
    pytest-html==4.1.1 \
    pytest-junitxml==0.8.1 \
    allure-pytest==2.13.5 \
    behave==1.2.6 \
    requests==2.32.3 \
    httpx==0.27.2 \
    pymysql==1.1.1 \
    psycopg2-binary==2.9.9

# ============================================================
# Stage 4: 安装 Java 工具（可选，用于 Katalon 等）
# ============================================================
FROM python-tools AS java-tools

RUN apt-get update && apt-get install -y \
    gradle \
    maven \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# Stage 5: 最终镜像
# ============================================================
FROM java-tools AS final

# 创建非 root 用户
RUN useradd -m -s /bin/bash runner \
    && mkdir -p /workspace /reports \
    && chown -R runner:runner /workspace /reports

# 复制工具链
COPY --from=node-tools /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=node-tools /usr/local/bin/node /usr/local/bin/node
COPY --from=node-tools /usr/local/bin/npm /usr/local/bin/npm
COPY --from=node-tools /usr/local/bin/npx /usr/local/bin/npx

# 复制路由脚本
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 设置 PATH
ENV PATH="/usr/local/bin:${PATH}"
ENV PLAYWRIGHT_BROWSERS_PATH="/ms-playwright"

# 切换到非 root 用户
USER runner
WORKDIR /workspace

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--help"]
