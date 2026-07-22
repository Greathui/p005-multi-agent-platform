# 多智能体团队协作平台 (P005)

> 面向非程序员用户的多智能体协作平台，通过主智能体调度不同 AI 智能体协作完成复杂任务。界面类似微信聊天框，支持本地单机部署。

## 功能特性

- **智能体团队协作**：主智能体作为项目经理，自动拆解任务并调度子智能体并行工作
- **多模型支持**：支持 OpenAI、DeepSeek、通义千问、月之暗面、智谱清言、硅基流动、本地 Ollama 等 8 种服务商
- **智能体记忆系统**：智能体拥有跨项目记忆，完成任务后自动提取经验，越用越聪明
- **技能系统**：可扩展的技能插件架构，支持 PPT/Excel/Word/PDF 等多种产出类型
- **蓝图系统**：团队配置可保存为蓝图，快速复用到新项目
- **元团队**：常驻专家系统，提供方案撰写、评审、融合的深度设计能力
- **权限隔离**：每个任务独立空间，子智能体严格隔离，防幻觉四层机制
- **文件版本控制**：自动备份文件修改历史，支持回滚
- **TODO 管理**：任务进度看板可视化
- **性能追踪**：智能体工作统计（任务数、平均耗时、记忆数）

## 技术栈

- **后端**：Python 3.10 + FastAPI（单文件 `backend/main.py`）
- **前端**：Vue 3 + Pinia + Element Plus + Vite
- **存储**：纯 JSON 文件存储（无数据库）
- **部署**：本地单机部署

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- npm 10+

### 安装和运行

1. **克隆仓库**

```bash
git clone https://github.com/你的用户名/P005.git
cd P005
```

2. **配置后端**

```bash
cd backend
pip install -r requirements.txt

# 复制示例配置并填入你的 API 密钥
copy config.example.json config.json
copy configs.example.json configs.json
copy data.example.json data.json
# 编辑 config.json 和 configs.json，填入你的 API 密钥
```

3. **配置前端**

```bash
cd ../frontend
npm install
```

4. **启动服务**

```bash
# 方式一：分别启动（推荐开发时用）
# 后端（监听 8000 端口，同时托管前端静态文件）
cd backend
python main.py

# 前端开发模式（可选，监听 5173 端口）
cd frontend
npm run dev

# 方式二：一键启动
# 双击根目录的 start.bat
```

5. **打开浏览器**

访问 http://localhost:8000

### 前端构建

```bash
cd frontend
npm run build
# 构建产物到 frontend/dist/，由后端自动托管
```

## 项目结构

```
P005/
├── backend/              # 后端代码
│   ├── main.py           # 核心服务（FastAPI）
│   ├── meta_team_*.py    # 元团队模块（4个独立模块）
│   ├── skill_blueprint.py # 技能蓝图模块
│   ├── requirements.txt  # Python 依赖
│   ├── .env.example      # 环境变量示例
│   ├── config.example.json    # 全局配置示例
│   ├── configs.example.json   # 多模型配置示例
│   └── data.example.json      # 智能体模板示例
├── frontend/             # 前端代码
│   ├── src/
│   │   ├── api/          # API 封装
│   │   ├── components/   # Vue 组件
│   │   ├── stores/       # Pinia 状态管理
│   │   ├── utils/        # 工具函数
│   │   └── styles/       # 样式文件
│   ├── package.json
│   └── vite.config.js
├── docs/                 # 项目文档
│   ├── README.md         # 文档总索引
│   ├── CHANGELOG.md      # 变更日志
│   ├── 01-规划/          # 技术规划
│   ├── 02-范围/          # 功能范围清单
│   ├── 03-指导/          # 文档维护规范
│   ├── 04-设计/          # 架构设计文档
│   ├── 05-审查/          # 审查报告（历史快照）
│   ├── 06-变更日志/      # 会话纪要
│   └── 07-测试/          # 测试规范
├── AGENTS.md             # AI 助手工作指南
├── .gitignore
├── LICENSE
└── README.md
```

## 重要说明

- **API 密钥**：`backend/configs.json` 和 `backend/config.json` 包含明文密钥，已在 `.gitignore` 中排除。请使用示例文件创建你自己的配置。
- **数据文件**：`backend/` 下的 `.json` 数据文件（conversations、messages、teams 等）包含用户数据，已排除上传。
- **捐赠功能**：关于页面有打赏功能，默认不显示二维码。如需显示，将收款码命名为 `alipay-qr.jpg` / `wechat-qr.jpg` 放入 `frontend/public/`。

## 许可证

## 许可证

本项目采用 [GNU AGPL-3.0](LICENSE) 协议开源。

### 双重许可模式

| 使用场景 | AGPL-3.0 开源许可（免费） | 商业许可（付费） |
|---|---|---|
| 个人学习和自用 | 可以 | — |
| 修改后开源分发 | 可以 | — |
| 修改后闭源分发 | **不可以** | 可以 |
| 部署为商业云服务 | **不可以** | 可以 |

- **开源许可**：免费使用，但修改后分发或部署为网络服务时，必须以 AGPL-3.0 开源全部修改代码
- **商业许可**：如需闭源使用或商业部署，请联系获取商业许可

详见 [LICENSE-COMMERCIAL.md](LICENSE-COMMERCIAL.md)

