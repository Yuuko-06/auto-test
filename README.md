# AI 接口自动化测试 Agent

基于 AI 的轻量级接口自动化测试工具，采用分布式微服务架构，单机多端口模拟分布式部署。

## 架构

```
用户请求 → 任务调度服务(:8080) → 接口扫描(:8081) → AI规划(:8082) → 执行报告(:8083)
                ↑                        ↑                ↑               ↑
                └────────────────────────┴────────────────┴───────────────┘
                                    Nacos 注册中心
```

### 4 个微服务

| 服务 | 端口 | 职责 |
|------|------|------|
| task-scheduler | 8080 | 统一入口，编排测试工作流 |
| api-scanner | 8081 | 自动抓取解析 OpenAPI 文档 |
| ai-planner | 8082 | 调用 AI 生成测试用例 |
| test-executor | 8083 | 执行测试、AI 校验、生成报告 |

## 快速开始

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 AI_API_KEY
```

### 2. Docker Compose 启动

```bash
docker compose up -d
```

### 3. 本地开发（不依赖 Docker）

```bash
# 终端1：启动 Nacos（如果不需要可跳过，使用静态配置降级）
docker compose up nacos -d

# 终端2-5：分别启动 4 个服务
cd task-scheduler && PYTHONPATH=.. python main.py
cd api-scanner && PYTHONPATH=.. python main.py
cd ai-planner && PYTHONPATH=.. python main.py
cd test-executor && PYTHONPATH=.. python main.py
```

## API 使用示例

### 创建并启动测试任务

```bash
# 1. 创建任务
curl -X POST http://localhost:8080/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"target_url": "https://petstore.swagger.io/v2", "name": "Petstore测试"}'

# 2. 启动测试流程
curl -X POST http://localhost:8080/api/v1/tasks/{task_id}/start

# 3. 查询进度
curl http://localhost:8080/api/v1/tasks/{task_id}

# 4. 获取报告
curl http://localhost:8080/api/v1/tasks/{task_id}/report
```

## 工作流

1. **提交被测系统地址** → 创建任务
2. **接口扫描** → 自动探测 OpenAPI 文档，提取所有接口
3. **AI 生成用例** → 为每个接口生成正常/异常/边界三类用例
4. **自动执行** → 逐条调用接口，AI 校验返回结果
5. **生成报告** → HTML 可视化报告 + JSON 数据

## 技术栈

- **语言**: Python 3.13
- **框架**: FastAPI
- **数据库**: SQLite + aiosqlite + SQLAlchemy 2.0
- **服务注册**: Nacos (HTTP API)
- **服务通信**: httpx + Nacos 服务发现
- **AI**: OpenAI / Anthropic Claude 双 SDK
- **部署**: Docker Compose

## 降级方案

Nacos 不可用时，`shared/service_client.py` 自动降级到 `.env` 中的静态地址配置，本地开发无需启动 Nacos。

## 项目结构

```
auto-test-agent/
├── docker-compose.yml
├── .env.example
├── shared/              # 共享库
├── task-scheduler/      # 任务调度服务
├── api-scanner/         # 接口扫描服务
├── ai-planner/          # AI测试规划服务
├── test-executor/       # 测试执行与报告服务
└── nacos/conf/          # Nacos 配置
```
