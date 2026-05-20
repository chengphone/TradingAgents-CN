# TradingAgents-CN 测试要求与验收标准

> 版本日期：2026-05-20  
> 适用范围：`chengphone/TradingAgents-CN` 当前微信小程序版 / FastAPI 后端 / CloudBase 架构  
> 文档目的：作为后续补充测试代码、接口验收、CI 检查和回归测试的统一标准

---

## 1. 测试目标

前两轮代码审查修复完成后，下一阶段的核心目标不是继续增加功能，而是通过自动化测试锁住主链路，避免后续修改再次破坏以下关键路径：

```text
微信登录
  → 获取用户信息
  → 提交股票分析任务
  → 查询任务状态
  → 获取分析结果
  → 查看报告列表
  → 查看报告详情
  → 查看报告模块内容
```

测试体系应优先保证：

- API 路径一致。
- 登录 token 结构一致。
- CloudBase 兼容层行为稳定。
- 分析任务可创建、可查询、可完成。
- 报告可保存、可分页、可读取。
- 用户之间不能越权读取任务和报告。
- Docker/CI 环境与本地环境行为一致。

---

## 2. 测试优先级

### P0：必须优先覆盖

P0 测试用于保护主链路。如果 P0 测试不通过，不应继续合并功能代码。

| 测试类别 | 目标 |
|---|---|
| 认证接口测试 | 登录返回 token，`/api/auth/me` 可识别当前用户 |
| 分析任务接口测试 | 能提交单股分析任务，返回 `task_id` |
| 任务状态测试 | 能查询任务状态，状态字段结构稳定 |
| 分析结果测试 | 任务完成后能读取分析结果 |
| 报告接口测试 | 能读取报告列表、详情、模块内容 |
| 权限隔离测试 | 用户 A 不能读取用户 B 的任务和报告 |
| CloudBase 兼容层测试 | `find_one`、`insert_one`、`update_one(upsert=True)`、`$setOnInsert`、`$inc` 行为正确 |

### P1：主链路稳定后覆盖

| 测试类别 | 目标 |
|---|---|
| Docker 构建测试 | 镜像能构建，`VERSION` 文件存在，服务能启动 |
| 健康检查测试 | `/api/health`、`/api/healthz`、`/api/readyz` 返回正常 |
| 小程序 API 路径静态检查 | 避免再次出现 `/auth/me` 与 `/api/auth/me` 不一致 |
| 配额测试 | 今日配额统计准确，超额后返回 429 |
| 报告分页测试 | 第二页及后续页能正常返回 |
| JWT 过期时间测试 | `ACCESS_TOKEN_EXPIRE_MINUTES` 配置生效 |

### P2：后续增强覆盖

| 测试类别 | 目标 |
|---|---|
| LLM 配置测试 | 多模型供应商配置读取正确 |
| 数据源降级测试 | Tushare / AKShare / yfinance 等数据源失败时可回退 |
| 性能测试 | 多任务并发下无明显状态串扰 |
| 长任务恢复测试 | 任务中断、超时、僵尸任务清理逻辑正常 |

---

## 3. 推荐测试目录结构

建议新增 `tests/` 目录：

```text
tests/
  conftest.py
  test_auth_routes.py
  test_analysis_routes.py
  test_reports_routes.py
  test_cloudbase_client.py
  test_security_permissions.py
  test_health_routes.py
  test_runtime_config.py
```

各文件职责：

| 文件 | 作用 |
|---|---|
| `conftest.py` | 测试 fixture、FastAPI TestClient、假用户、假 CloudBase 数据层 |
| `test_auth_routes.py` | 登录、JWT、`/api/auth/me` |
| `test_analysis_routes.py` | 单股分析任务提交、任务状态查询、结果查询 |
| `test_reports_routes.py` | 报告列表、报告详情、模块内容、分页 |
| `test_cloudbase_client.py` | CloudBase MongoDB 兼容层单元测试 |
| `test_security_permissions.py` | 用户权限隔离、越权访问拦截 |
| `test_health_routes.py` | 健康检查接口 |
| `test_runtime_config.py` | 环境变量、版本号、JWT 过期时间等运行时配置 |

---

## 4. 后端 API 冒烟测试要求

### 4.1 认证链路

#### 接口

```text
POST /api/auth/login
GET  /api/auth/me
```

#### 测试要求

`POST /api/auth/login` 应返回：

```json
{
  "success": true,
  "data": {
    "token": "...",
    "openid": "...",
    "daily_quota": 10
  }
}
```

必须验证：

- `success == true`
- `data.token` 存在
- `data.openid` 存在
- `data.daily_quota` 为数字
- token 可用于访问 `/api/auth/me`

`GET /api/auth/me` 应返回：

```json
{
  "success": true,
  "data": {
    "openid": "...",
    "daily_quota": 10,
    "daily_used": 0
  }
}
```

必须验证：

- 无 token 时返回 401。
- 无效 token 时返回 401。
- 有效 token 时返回当前用户。
- 返回字段包含 `daily_quota` 和 `daily_used`。

---

### 4.2 分析任务链路

#### 接口

```text
POST /api/analysis/single
GET  /api/analysis/tasks/{task_id}/status
GET  /api/analysis/tasks/{task_id}/result
```

#### 请求示例

```json
{
  "symbol": "600519",
  "stock_code": "600519",
  "parameters": {
    "market_type": "A股",
    "research_depth": "标准",
    "selected_analysts": ["market", "fundamentals"]
  }
}
```

#### 测试要求

`POST /api/analysis/single` 必须验证：

- 无 token 返回 401。
- 缺少 `symbol` 或 `stock_code` 返回 400 或 422。
- 合法请求返回 `success == true`。
- 返回 `data.task_id`。
- 返回 `data.status == pending`。
- 数据库中写入对应任务。

`GET /api/analysis/tasks/{task_id}/status` 必须验证：

- 查询自己的任务成功。
- 查询不存在任务返回 404。
- 查询他人任务返回 403 或 404。
- 返回字段包含：

```text
task_id
status
progress
message
symbol 或 stock_code
elapsed_time
```

`GET /api/analysis/tasks/{task_id}/result` 必须验证：

- 任务未完成时应返回明确错误或空结果。
- 任务完成后返回 `decision`、`summary`、`recommendation`、`reports`。
- 查询他人结果返回 403 或 404。

---

### 4.3 报告链路

#### 接口

```text
GET /api/reports/list
GET /api/reports/{report_id}/detail
GET /api/reports/{report_id}/content/{module}
```

#### 测试要求

`GET /api/reports/list` 必须验证：

- 无 token 返回 401。
- 只返回当前用户报告。
- 支持 `page` 与 `page_size`。
- 支持 `stock_code` 过滤。
- 返回字段包含：

```text
reports
total
page
page_size
```

`GET /api/reports/{report_id}/detail` 必须验证：

- 当前用户读取自己的报告成功。
- 当前用户读取他人报告失败。
- 不存在的报告返回 404。
- 返回字段包含：

```text
analysis_id
stock_symbol
stock_name
decision
summary
recommendation
reports
created_at
```

`GET /api/reports/{report_id}/content/{module}` 必须验证：

- 当前用户读取自己的报告模块成功。
- 当前用户读取他人报告模块失败。
- 不存在模块返回 404。
- 返回字段包含：

```text
module
content
```

---

## 5. CloudBase 兼容层测试要求

### 5.1 基础 CRUD

测试对象：

```text
app/core/cloudbase_client.py
```

必须覆盖：

```python
find_one()
find()
insert_one()
update_one()
delete_one()
replace_one()
count_documents()
```

### 5.2 `update_one` 行为

必须覆盖以下场景：

#### `$set`

```python
await col.update_one(
    {"task_id": "t1"},
    {"$set": {"status": "completed"}}
)
```

期望：

```json
{
  "task_id": "t1",
  "status": "completed"
}
```

#### `$setOnInsert` + `upsert=True`

```python
await col.update_one(
    {"task_id": "t2"},
    {"$setOnInsert": {"task_id": "t2", "status": "pending"}},
    upsert=True
)
```

期望：

- 文档不存在时插入。
- 文档存在时不覆盖 `$setOnInsert` 字段。

#### `$inc`

```python
await col.update_one(
    {"key": "openid:2026-05-20"},
    {"$inc": {"count": 1}}
)
```

期望：

- `count` 正确自增。
- 缺失字段按 0 处理。

#### `$unset`

```python
await col.update_one(
    {"task_id": "t1"},
    {"$unset": {"last_error": ""}}
)
```

期望：

- 字段被删除或被置空，行为需在实现中固定并测试。

---

### 5.3 查询与分页

必须覆盖：

```python
find(query).sort(field, direction).limit(n)
```

如果实现了 skip，还应覆盖：

```python
find(query).sort(field, -1).skip(20).limit(20)
```

报告分页测试必须验证：

- 第 1 页有数据。
- 第 2 页有数据。
- `total` 与实际数量一致。

---

## 6. 权限隔离测试要求

必须构造两个用户：

```text
user_a_openid = "openid_a"
user_b_openid = "openid_b"
```

### 6.1 任务权限

测试数据：

```json
{
  "task_id": "task_a",
  "openid": "openid_a",
  "user_id": "openid_a",
  "status": "completed"
}
```

测试要求：

- 用户 A 查询 `task_a` 成功。
- 用户 B 查询 `task_a` 失败。
- 用户 B 获取 `task_a` 结果失败。

### 6.2 报告权限

测试数据：

```json
{
  "analysis_id": "report_a",
  "task_id": "task_a",
  "openid": "openid_a",
  "user_id": "openid_a",
  "reports": {
    "final_trade_decision": "test content"
  }
}
```

测试要求：

- 用户 A 读取 `report_a` 成功。
- 用户 B 读取 `report_a` 详情失败。
- 用户 B 读取 `report_a` 模块失败。

### 6.3 推荐失败状态码

建议统一为：

```text
404 Not Found
```

原因：避免向攻击者暴露资源是否存在。

---

## 7. 小程序端静态检查要求

小程序端暂时可以先做轻量静态检查，不必一开始引入完整 E2E。

必须检查：

```text
/auth/me 不应再出现
/api/auth/me 应存在
/api/reports/list 应存在
/api/reports/{id}/detail 应存在
/api/reports/{id}/content/{module} 应存在
res.data.token 不应作为登录 token 来源
res.data.data.token 应作为登录 token 来源
your-env-id 不应出现在生产构建配置中
```

建议添加脚本：

```bash
grep -R "'/auth/me'\|\"/auth/me\"" miniprogram && exit 1 || true
grep -R "res.data.token" miniprogram && exit 1 || true
grep -R "your-env-id" miniprogram cloudbaserc.json && exit 1 || true
```

---

## 8. Docker 与运行时配置测试要求

### 8.1 Docker 构建

必须验证：

```bash
docker build -t tradingagents-cn:test .
```

构建应成功。

### 8.2 VERSION 文件

容器内必须存在：

```text
/app/VERSION
```

API 返回版本应与根目录 `VERSION` 一致。

### 8.3 健康检查

必须验证：

```text
GET /api/health
GET /api/healthz
GET /api/readyz
```

返回状态应为成功。

### 8.4 环境变量一致性

必须验证：

```text
CLOUDBASE_ENV_ID
CLOUDBASE_API_TOKEN
WECHAT_APPID
WECHAT_SECRET
JWT_SECRET
ACCESS_TOKEN_EXPIRE_MINUTES
```

生产环境中不得使用：

```text
change-me-in-production
your-env-id
your-api-key
wx1234567890
```

---

## 9. 推荐 GitHub Actions CI

建议新增：

```text
.github/workflows/test.yml
```

基础 CI 内容：

```yaml
name: tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e .
          pip install pytest pytest-asyncio httpx

      - name: Compile Python files
        run: |
          python -m compileall app tradingagents

      - name: Run tests
        run: |
          pytest -q
```

后续可增加：

```bash
ruff check .
docker build -t tradingagents-cn:test .
```

不建议一开始强制大量 lint 规则，否则历史代码会拖慢主链路测试落地。

---

## 10. 最小通过标准

在继续开发新功能前，至少满足以下标准：

```text
pytest 能正常运行
认证链路测试通过
分析任务提交测试通过
任务状态查询测试通过
报告列表测试通过
报告详情测试通过
报告模块内容测试通过
用户权限隔离测试通过
CloudBase 兼容层核心操作测试通过
GitHub Actions 每次提交自动运行测试
```

---

## 11. 暂不建议优先投入的方向

在测试体系落地前，不建议优先投入：

```text
新页面开发
新模型供应商接入
UI 美化
模拟交易
批量分析
复杂数据源调度
大规模 README 重写
```

原因：主链路没有自动化保护时，新增功能会放大不确定性。

---

## 12. 推荐下一步执行计划

### 第一步：搭建测试目录

```bash
mkdir -p tests
```

新增：

```text
tests/conftest.py
tests/test_auth_routes.py
tests/test_analysis_routes.py
tests/test_reports_routes.py
tests/test_cloudbase_client.py
tests/test_security_permissions.py
```

### 第二步：先写 API 冒烟测试

优先覆盖：

```text
POST /api/auth/login
GET  /api/auth/me
POST /api/analysis/single
GET  /api/analysis/tasks/{task_id}/status
GET  /api/reports/list
```

### 第三步：写权限测试

重点覆盖：

```text
用户 A 不能读取用户 B 的任务
用户 A 不能读取用户 B 的报告
```

### 第四步：写 CloudBase 兼容层测试

重点覆盖：

```text
upsert
$setOnInsert
$inc
count_documents
分页
```

### 第五步：接入 CI

新增 GitHub Actions，要求每次提交自动执行：

```bash
python -m compileall app tradingagents
pytest -q
```

---

## 13. 结论

当前项目已经完成了前两轮审查修复，下一阶段应进入测试固化阶段。

最重要的不是一次性追求高覆盖率，而是先用自动化测试锁住主链路：

```text
登录 → 用户信息 → 提交分析 → 查询状态 → 获取结果 → 查看报告
```

只要这条链路被测试保护住，后续继续开发小程序 UI、报告优化、模型配置、数据源扩展时，风险会显著降低。
