"""多智能体团队软件 - 后端入口"""
import json
import re
import time
import uuid
import asyncio
import shutil
import threading
import os
import json as json_module
from pathlib import Path
from typing import AsyncGenerator, Generator, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from openai import OpenAI
from pydantic import BaseModel

# 元团队模板配置（Phase 1：元团队功能）
from meta_team_template import (
    META_TEAM_MAIN_PROMPT,
    META_TEAM_MEMBERS,
    BLUEPRINT_SCHEMA_VERSION,
    BLUEPRINT_REQUIRED_FIELDS,
    BLUEPRINT_COLLAB_TYPES,
)

# 技能与蓝图管理模块
from skill_blueprint import (
    list_skills as sb_list_skills,
    get_skill as sb_get_skill,
    create_skill as sb_create_skill,
    update_skill as sb_update_skill,
    delete_skill as sb_delete_skill,
    list_blueprints as sb_list_blueprints,
    get_blueprint as sb_get_blueprint,
    create_blueprint as sb_create_blueprint,
    update_blueprint as sb_update_blueprint,
    delete_blueprint as sb_delete_blueprint,
    increment_blueprint_apply_count as sb_inc_bp_apply,
    import_blueprint_from_data as sb_import_bp_data,
    import_blueprint_from_file as sb_import_bp_file,
    validate_blueprint_data as sb_validate_bp_data,
    increment_skill_use_count as sb_increment_use_count,
)

# 元团队常驻模块（专家管理 + 设计任务管理）
from meta_team_config import (
    list_experts as mt_list_experts,
    get_expert as mt_get_expert,
    get_experts_by_ids as mt_get_experts_by_ids,
    get_default_experts as mt_get_default_experts,
    create_expert as mt_create_expert,
    update_expert as mt_update_expert,
    delete_expert as mt_delete_expert,
    add_experience_record as mt_add_experience,
    get_experience_log as mt_get_experience_log,
    get_expert_context_for_task as mt_get_expert_context,
    get_current_prompt as mt_get_current_prompt,
    upgrade_prompt_version as mt_upgrade_prompt,
    get_prompt_history as mt_get_prompt_history,
    rollback_prompt_version as mt_rollback_prompt,
    get_global_settings as mt_get_settings,
    update_global_settings as mt_update_settings,
    ensure_initialized as mt_config_init,
    REVIEW_CRITERIA as MT_REVIEW_CRITERIA,
)
from meta_team_task import (
    create_task as mt_task_create,
    list_tasks as mt_task_list,
    get_task as mt_task_get,
    delete_task as mt_task_delete,
    update_task_status as mt_task_update_status,
    add_message as mt_task_add_msg,
    get_messages as mt_task_get_msgs,
    save_proposal as mt_task_save_proposal,
    get_proposal as mt_task_get_proposal,
    save_review as mt_task_save_review,
    get_review as mt_task_get_review,
    save_blueprint_version as mt_task_save_bp,
    get_blueprint_version as mt_task_get_bp,
    save_fusion_decision as mt_task_save_fusion,
    get_fusion_decision as mt_task_get_fusion,
    set_blueprint_id as mt_task_set_bp_id,
    get_latest_blueprint as mt_task_get_latest_bp,
    get_task_stats as mt_task_stats,
    ensure_initialized as mt_task_init,
    STATUS_DRAFTING as MT_STATUS_DRAFTING,
    STATUS_REVIEWING as MT_STATUS_REVIEWING,
    STATUS_FUSING as MT_STATUS_FUSING,
    STATUS_COMPLETED as MT_STATUS_COMPLETED,
    STATUS_ARCHIVED as MT_STATUS_ARCHIVED,
    ALL_STATUSES as MT_ALL_STATUSES,
    ROLE_USER as MT_ROLE_USER,
    ROLE_ASSISTANT as MT_ROLE_ASSISTANT,
    ROLE_EXPERT as MT_ROLE_EXPERT,
)
# 元团队工作模式引擎（Phase 2：并行专家 + 评审融合）
import meta_team_engine as mt_engine
# 元团队评审引擎（Phase 3：评审闭环与专家进化）
import meta_team_review as mt_review

app = FastAPI(title="多智能体团队软件")

# 允许前端访问（开发环境）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
CONFIGS_FILE = BASE_DIR / "configs.json"
DATA_FILE = BASE_DIR / "data.json"
MESSAGES_FILE = BASE_DIR / "messages.json"
CONVERSATIONS_FILE = BASE_DIR / "conversations.json"
TEAMS_FILE = BASE_DIR / "teams.json"


# ========== 数据模型 ==========

class ChatMessage(BaseModel):
    agent_id: str
    message: str
    conversation_id: str = ""
    direct: bool = False  # 直接对话模式：只调用指定智能体，不触发链式调度
    default_config_id: str = ""  # 会话级默认模型配置ID（智能体未单独配置模型时使用）
    enable_thinking: Optional[bool] = None  # 会话级思考模式开关（None 表示用配置默认值）


class ApiConfig(BaseModel):
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 2000


class AgentCreate(BaseModel):
    name: str
    role: str
    avatar: str = "🤖"
    system_prompt: str = ""
    allowed_paths: list[str] = []
    enabled_skills: list[str] = []          # 已启用的技能ID列表
    can_invoke_sub_agent: bool = False      # 是否允许调用子代理


class AgentUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    avatar: str | None = None
    system_prompt: str | None = None
    allowed_paths: list[str] | None = None
    model_cfg: dict | None = None
    enabled_skills: list[str] | None = None
    can_invoke_sub_agent: bool | None = None

    model_config = {"protected_namespaces": ()}


class ModelConfigCreate(BaseModel):
    name: str
    provider: str = ""
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 2000
    enable_thinking: bool = False
    context_window: int = 131072  # 模型上下文窗口大小（token数），用于 M3 截断阈值。默认 128K
    enabled: bool = True  # 是否启用该配置（False 时该配置不可被选中调用，用于付费控制）

class ModelConfigUpdate(BaseModel):
    name: str | None = None
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    enable_thinking: bool | None = None
    context_window: int | None = None
    enabled: bool | None = None  # 启用/禁用该配置


# ========== 工具函数 ==========

def load_json(path: Path, default):
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            # JSON 格式错误：文件损坏，记录日志并返回默认值
            print(f"[WARNING] JSON 文件损坏，返回默认值：{path}，错误：{e}")
            return default
        except Exception as e:
            # 其他异常（权限、IO 错误等）：记录日志并返回默认值
            print(f"[WARNING] 读取 JSON 文件失败，返回默认值：{path}，错误：{e}")
            return default
    return default


# 全局 JSON 文件写入锁：防止 ThreadPoolExecutor 并行调度时多线程写同一文件导致数据丢失
# 使用 RLock（可重入锁），因为外层事务加锁后，内部 save_json 也会尝试获取同一把锁
_json_write_lock = threading.RLock()


def save_json(path: Path, data):
    """原子写入 JSON 文件：先写临时文件，再 os.replace 覆盖目标文件。

    os.replace 是原子操作（Windows/Linux 均支持），可避免写入中途崩溃导致文件损坏。
    加锁防止并行调度时多线程同时写同一文件导致数据丢失。
    使用 RLock 允许同一线程内重入（外层事务加锁后，内部 save_json 仍可获取锁）。
    """
    tmp_path = str(path) + ".tmp"
    with _json_write_lock:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, str(path))


# 预设的服务商列表
PRESET_PROVIDERS = [
    {
        "code": "openai",
        "name": "OpenAI",
        "icon": "",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "models": [
            {"id": "gpt-4o-mini", "name": "gpt-4o-mini", "desc": "性价比高，日常用"},
            {"id": "gpt-4o", "name": "gpt-4o", "desc": "最强模型，贵"},
            {"id": "gpt-4.1-mini", "name": "gpt-4.1-mini", "desc": "最新小模型"},
            {"id": "gpt-4.1", "name": "gpt-4.1", "desc": "最新大模型"},
        ],
        "desc": "官方，模型能力最强，价格偏高",
    },
    {
        "code": "deepseek",
        "name": "深度求索",
        "icon": "🔴",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "models": [
            {"id": "deepseek-chat", "name": "deepseek-chat", "desc": "对话模型，性价比高"},
            {"id": "deepseek-reasoner", "name": "deepseek-reasoner", "desc": "思考模型，解题强"},
        ],
        "desc": "国产，性价比极高，代码能力强",
    },
    {
        "code": "qwen",
        "name": "通义千问",
        "icon": "🟠",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "models": [
            {"id": "qwen-turbo", "name": "qwen-turbo", "desc": "速度快，便宜"},
            {"id": "qwen-plus", "name": "qwen-plus", "desc": "均衡，推荐"},
            {"id": "qwen-max", "name": "qwen-max", "desc": "最强，贵"},
            {"id": "qwen-long", "name": "qwen-long", "desc": "超长上下文"},
        ],
        "desc": "阿里出品，中文理解好，新用户有免费额度",
    },
    {
        "code": "moonshot",
        "name": "月之暗面 Kimi",
        "icon": "🌙",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "models": [
            {"id": "moonshot-v1-8k", "name": "moonshot-v1-8k", "desc": "8k上下文"},
            {"id": "moonshot-v1-32k", "name": "moonshot-v1-32k", "desc": "32k上下文"},
            {"id": "moonshot-v1-128k", "name": "moonshot-v1-128k", "desc": "128k长文本"},
        ],
        "desc": "长文本处理强，适合读文档",
    },
    {
        "code": "zhipu",
        "name": "智谱清言",
        "icon": "💎",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
        "models": [
            {"id": "glm-4-flash", "name": "glm-4-flash", "desc": "免费，速度快"},
            {"id": "glm-4", "name": "glm-4", "desc": "标准模型"},
            {"id": "glm-4-plus", "name": "glm-4-plus", "desc": "高级模型"},
            {"id": "glm-4-air", "name": "glm-4-air", "desc": "性价比高"},
        ],
        "desc": "清华系，Flash 模型免费，额度多",
    },
    {
        "code": "siliconflow",
        "name": "硅基流动",
        "icon": "",
        "base_url": "https://api.siliconflow.cn/v1",
        "default_model": "Qwen/Qwen2.5-7B-Instruct",
        "models": [
            {"id": "Qwen/Qwen2.5-7B-Instruct", "name": "Qwen2.5-7B", "desc": "阿里7B模型"},
            {"id": "Qwen/Qwen2.5-72B-Instruct", "name": "Qwen2.5-72B", "desc": "阿里72B大模型"},
            {"id": "deepseek-ai/DeepSeek-V3", "name": "DeepSeek-V3", "desc": "深度求索V3"},
            {"id": "meta-llama/Llama-3.1-8B-Instruct", "name": "Llama-3.1-8B", "desc": "Meta模型"},
        ],
        "desc": "聚合多家开源模型，便宜量大",
    },
    {
        "code": "ollama",
        "name": "本地 Ollama",
        "icon": "🖥️",
        "base_url": "http://localhost:11434/v1",
        "default_model": "qwen2.5:7b",
        "models": [
            {"id": "qwen2.5:7b", "name": "qwen2.5:7b", "desc": "阿里7B，推荐"},
            {"id": "qwen2.5:14b", "name": "qwen2.5:14b", "desc": "阿里14B"},
            {"id": "llama3.1:8b", "name": "llama3.1:8b", "desc": "Meta 8B"},
            {"id": "deepseek-r1:7b", "name": "deepseek-r1:7b", "desc": "推理模型"},
        ],
        "desc": "本地运行，完全免费，数据不上传",
    },
    {
        "code": "custom",
        "name": "自定义",
        "icon": "⚙️",
        "base_url": "",
        "default_model": "",
        "models": [],
        "desc": "手动填写地址和模型，兼容所有 OpenAI 格式",
    },
]


def _default_agents():
    """默认智能体模板——只包含主智能体。
    新项目创建时是空团队，主智能体按需用 create_team_member 创建子角色。
    """
    return [
        {
            "id": "main",
            "name": "我（主智能体）",
            "role": "项目经理，负责任务分配和协调",
            "avatar": "👤",
            "system_prompt": """你是项目经理「主智能体」，负责协调团队完成用户的项目任务。你拥有项目根目录的完整读写权限，可以按需创建子智能体并调配权限。

## 核心工作模式：按需组建团队
项目创建时只有你一个人，没有预设的助手。你需要根据任务需要，用 `create_team_member` 创建合适的角色，然后调度它们协作。

## 你可以使用的工具
- list_directory：列出文件夹内容
- read_file：读取文件内容
- write_file：写入/创建文件（会自动创建目录）
- create_directory：创建文件夹
- **grep**：⭐【代码搜索】在文件内容里搜正则，定位函数/变量/错误，比 list_directory 逐个遍历快得多
- **glob**：⭐【文件名搜索】按模式快速找文件，如 `**/*.py` 找所有 Python 文件
- **edit_file**：⭐【精确编辑】用 SEARCH/REPLACE 改文件一部分，不用重写整个文件。改大文件首选
- move_file：移动文件（用于归档产出到 deliverables/）
- copy_file：复制文件
- init_project_structure：【新项目必用】初始化项目标准目录结构
- create_task：【推荐】创建任务并分配给子智能体，自动创建独立的任务文件夹（input/output）和配置权限
- create_agent_workspace：为智能体创建私有工作区
- grant_path_access：给子智能体授予额外路径的读写权限
- revoke_path_access：撤销子智能体的路径权限
- **list_team_members**：查看当前团队所有成员（重要：每次接手任务前先调用，了解可用人力）
- **create_team_member**：创建新子智能体并加入团队（自动创建工作区+授权）
- **update_team_member**：修改子智能体的职能/提示词
- **remove_team_member**：移除子智能体（保留已产出文件）

## 常见角色模板（参考，不要照抄，根据实际需求写提示词）
- 文档专员：写文档、报告、整理内容。提示词要点：擅长结构化写作、格式规范、能读 input 写 output
- 代码审查员：找bug、代码审查。提示词要点：按严重程度分类问题、给改进建议
- 翻译员：中英互译。提示词要点：保持术语一致、符合目标语言习惯
- 数据分析师：数据分析、可视化。提示词要点：读取数据、清洗、分析、生成报告
- 测试工程师：编写测试用例、验证功能。提示词要点：覆盖边界条件、写清晰测试
- 开发工程师：编码实现功能。提示词要点：遵循代码规范、写注释、保证可读性

## 项目目录结构（初始化后）
```
项目根目录/
├── .agent/tasks/    # 任务文件夹（每个任务一个子目录，含 input/output）
├── shared/          # 共享文件区（智能体间交换非任务文件）
├── agent_work/      # 智能体私有工作区（create_team_member 时自动创建）
└── deliverables/    # 最终交付物（你整理成果后放这里）
```

## 工作流程
1. 【第一步】新项目必须先调用 `init_project_structure` 创建目录结构
2. 【强制】用 `list_team_members` 查看当前团队——**每次接手任务前必须先调用**，不要假设团队是空的
3. 根据用户需求，判断需要什么角色：
   - **创建新成员前，再次检查 list_team_members 的结果**，避免创建职责重复的成员
   - 如果已有成员的 role 能胜任当前任务，直接 @它 调度，不要重复创建
   - 只有确认没有合适成员时，才用 `create_team_member` 创建
   - **推荐用 template 参数创建成员**（见下方模板表），系统自动生成高质量提示词
   - 创建后会自动建工作区和授权，无需手动调 `create_agent_workspace`
4. 用 `create_task` 创建任务并分配给对应成员：
   - 选合适 task_type：document/code_review/coding/data_analysis/testing/general
   - 系统自动建任务文件夹（.agent/tasks/{task_id}/）含 input/ 和 output/
   - 系统自动授予对应任务类型的路径权限
5. 回复中 `@成员名字` 调度它，告诉它读取 `.agent/tasks/{task_id}/TASK.md`
6. 子智能体提交结果后，检查 `.agent/tasks/{task_id}/output/`
7. 把成果整理到 `deliverables/` 目录
8. 任务完成后，临时成员可用 `remove_team_member` 清理（保留产出文件）

## ⭐ 角色模板（推荐用 template 创建成员）
创建成员时优先用模板，不用临时编 system_prompt。模板按能力分类，领域通过 domain_hint/style_guide 注入：

| 模板 | 定位 | 适用场景 |
|---|---|---|
| `creator` | 创作者（读写） | 小说作者、文案、报告撰稿、开发工程师 |
| `reviewer` | 审阅者（只读） | 试读读者、编辑审稿、Code Review、质量检验 |
| `analyst` | 分析者（只读输入+写报告） | 数据分析、市场调研、竞品分析、学术研究 |
| `worker` | 执行者（读写，通用） | 翻译、校对、格式转换、测试执行 |
| `coordinator` | 协调者（组长，复杂项目） | 开发组长、文档组长（仅10+智能体的大型项目） |

**调用示例**：
```
create_team_member(
  template="creator",
  name="作者",
  role="武侠小说创作者",
  domain_hint="小说章节",
  style_guide="金庸武侠风格，重人物心理"
)
```
- `domain_hint`：领域提示，如"小说章节"/"React 组件"/"研究报告"
- `style_guide`：风格指南，如"金庸风格"/"Airbnb 规范"/"学术规范"
- 也可不用模板，传 system_prompt 完全自定义（高级用法）

## 任务类型与权限模板
- document（文档编写）：授予 docs/ 读写，结果放 deliverables/docs/
- code_review（代码审查）：只读 input，报告放 deliverables/reviews/
- coding（代码开发）：授予 src/ 读写
- data_analysis（数据分析）：授予 data/ 读写，结果放 deliverables/analysis/
- testing（测试检查）：授予 tests/ 读写，src/ 只读
- general（通用任务）：基础权限

## 协作规则
- @ 成员时直接写「@成员名字」，系统会自动转发
- 文件交换优先用任务的 output/ 目录，其次 shared/
- 不要修改子智能体的私有工作区（agent_work/{id}/）
- 子智能体的提示词是它的"大脑"，要写清楚职责、权限范围、工作流程
- **避免重复造人**：项目里通常只需要一套核心团队。常见模板：
  - 文档类任务 → 复用「文档专员」「设定文档专员」等
  - 代码类任务 → 复用「代码审查员」「开发工程师」等
  - 只有当现有成员的专业领域完全不符时，才创建新角色

## ⚠️ 调度规则
你是项目经理，不是执行者。遇到实质性任务**必须调度子智能体**：
- 写文档、报告、翻译、整理内容 → 创建文档专员后 @它
- 代码检查、找bug、测试、审查 → 创建代码审查员后 @它
- 其他专业任务 → 创建对应角色后 @它

只有以下情况你自己处理：
- 用户只是打招呼、问问题、闲聊
- 用户询问项目状态或你的角色
- 用户明确要求你亲自处理
- 简单到不需要专业角色的任务（比如列个目录、读个文件）

**关键**：调度子智能体时，回复里**必须包含「@成员名字」字样**，否则系统不会转发。推荐格式：
1. `create_team_member` 创建成员（拿到 agent_id 和名字）
2. `create_task` 创建任务（拿到 task_id）
3. 回复写：「@成员名字 请查看 .agent/tasks/{task_id}/TASK.md，任务是...」

## ⚠️ 真实性约束（最重要）
- **禁止编造文件路径或任务 ID**：你说的每一个 `task_xxx`、`output/xxx.md` 路径，都必须是 `create_task` / `write_file` 工具真实返回的
- **禁止"假装"写了文件**：如果你没调用 `write_file` 工具，就不要说"已写入""已归档"
- **工具调用顺序**：先 `create_task` 拿到 task_id → 再 `@成员` 让它用 `write_file` 写文件 → 不要自己编 task_id
- **归档动作必须真实执行**：归档子智能体的产出时，**必须用 `move_file` 工具**把文件从 `.agent/tasks/{task_id}/output/` 移到 `deliverables/`。例如：`move_file(source_path='.agent/tasks/task_xxx/output/report.md', target_path='deliverables/report.md')`。只有看到 `✅ 已移动文件` 的返回，才能说"已归档"
- 如果你只做了规划/调度，就如实说"已安排 XX 去做"，不要说"已完成"

## ⚡ 工具使用策略（提升效率，减少 token 浪费）
- **找代码/文本**：用 `grep`（按内容找）或 `glob`（按文件名找），不要用 `list_directory` 逐层遍历
  - 找函数定义：`grep(pattern="def auth_user", glob="*.py")`
  - 找某个文件：`glob(pattern="**/config.json")`
- **读文件**：用 `read_file`，指定具体路径；不要为了"了解结构"而遍历整个目录树
- **改文件**：
  - 小改动（改几行）→ 用 `edit_file`（SEARCH/REPLACE），省 token 且安全
  - 新建文件 / 大改重写 → 用 `write_file`
  - 归档产出 → 用 `move_file`（从 .agent/tasks/.../output/ 移到 deliverables/）
- **搜索后先看再改**：grep/glob 返回结果后，先 `read_file` 确认内容，再 `edit_file` 改，不要盲改
- **批量操作要节制**：一次工具调用改一个地方，复杂任务拆成多步，每步确认结果再继续

## ⚠️ 角色边界（重要）
对话里你会收到两类消息，必须区分清楚：
- **用户指令**：来自项目负责人（用户），内容是需求或问题 → 用"收到您的需求"等语气回应
- **系统通知**：以「【系统通知：...】」开头，内容是团队成员的工作汇报 → 这是信息同步，不是新指令，回复时**不要说"已收到指令"**，而是向用户通报结果、确认产出、或安排下一步
- 你是项目经理，不是执行者。汇报由团队成员完成，你只做**收尾/通报/调度**，不要重复汇报内容

## 回复风格
- 简洁明了，先告诉用户你要做什么
- 创建成员时简要说明为什么需要这个角色
- @ 成员时明确任务内容和文件位置
- 完成后总结成果，告诉用户产出在哪个文件夹""",
            "allowed_paths": ["*"],
            "can_use_tools": True,
        },
    ]

def load_agents():
    data = load_json(DATA_FILE, {"agents": []})
    if not data.get("agents"):
        data["agents"] = _default_agents()
        save_json(DATA_FILE, data)
    else:
        # 迁移：更新内置智能体的配置（系统提示、can_use_tools、头像、角色描述）
        defaults = {a["id"]: a for a in _default_agents()}
        changed = False
        for agent in data["agents"]:
            aid = agent.get("id")
            if aid in defaults:
                # 更新内置智能体的字段（保留用户的 model_config）
                default = defaults[aid]
                if agent.get("system_prompt") != default["system_prompt"]:
                    agent["system_prompt"] = default["system_prompt"]
                    changed = True
                if agent.get("role") != default["role"]:
                    agent["role"] = default["role"]
                    changed = True
                if agent.get("avatar") != default["avatar"]:
                    agent["avatar"] = default["avatar"]
                    changed = True
                if "can_use_tools" not in agent or agent.get("can_use_tools") != default.get("can_use_tools"):
                    agent["can_use_tools"] = default.get("can_use_tools", False)
                    changed = True
            else:
                # 自定义智能体，默认给 can_use_tools
                if "can_use_tools" not in agent:
                    agent["can_use_tools"] = True
                    changed = True
            
            # 迁移：补全 v0.4.0 新增字段（enabled_skills 和 can_invoke_sub_agent）
            if "enabled_skills" not in agent:
                agent["enabled_skills"] = []
                changed = True
            if "can_invoke_sub_agent" not in agent:
                agent["can_invoke_sub_agent"] = (aid != "main")  # main 默认 True，其他默认 False
                changed = True
        if changed:
            save_json(DATA_FILE, data)
    return data["agents"]


def save_agents(agent_list):
    data = load_json(DATA_FILE, {"agents": []})
    data["agents"] = agent_list
    save_json(DATA_FILE, data)


def _get_conv_agents_with_main(conv_agents):
    """确保项目级智能体列表包含 main 主智能体。

    问题背景：项目级 conversations.json 的 agents 数组只存子智能体
    （create_team_member 创建的），main 主智能体始终在全局 data.json 里。
    旧代码用 `conv.get("agents") or load_agents()`，当 agents 非空时
    短路不回退全局，导致 main "消失"，发消息报"找不到这个智能体"。

    本函数统一处理：项目级子智能体 + 全局 main，合并返回，main 在最前。
    """
    if not conv_agents:
        return load_agents()
    global_agents = load_agents()
    main_agent = next((a for a in global_agents if a["id"] == "main"), None)
    if main_agent and not any(a.get("id") == "main" for a in conv_agents):
        return [main_agent] + conv_agents
    return conv_agents


def load_api_config():
    data = load_json(CONFIG_FILE, {"api": {}})
    return data.get("api", {})


def save_api_config(config: dict):
    data = load_json(CONFIG_FILE, {"api": {}})
    data["api"] = config
    save_json(CONFIG_FILE, data)


def load_messages():
    return load_json(MESSAGES_FILE, {"messages": []})["messages"]


def save_messages(messages):
    save_json(MESSAGES_FILE, {"messages": messages})


def append_message(msg_dict):
    """原子追加单条消息（加锁保护 load-append-save 事务，防止多项目并行时更新丢失）。

    多项目并行 SSE 场景下，generate() 中的 load → append → save 不是原子的：
    项目A load 后、save 前，项目B 也 load 了旧数据并 save，导致项目A 的消息被覆盖。
    本函数用 _json_write_lock 把 load-append-save 包成原子事务。
    """
    with _json_write_lock:
        messages = load_messages()
        messages.append(msg_dict)
        save_messages(messages)


def append_messages(msg_list):
    """原子批量追加消息（同 append_message，支持一次追加多条）。"""
    if not msg_list:
        return
    with _json_write_lock:
        messages = load_messages()
        messages.extend(msg_list)
        save_messages(messages)


def remove_messages_by_ids(ids_to_remove: set):
    """原子删除指定 ID 的消息（加锁保护 load-filter-save 事务）。

    用于 regenerate 场景：删除某条消息之后的所有回复，然后重新生成。
    """
    if not ids_to_remove:
        return
    with _json_write_lock:
        messages = load_messages()
        remaining = [m for m in messages if m.get("id") not in ids_to_remove]
        save_messages(remaining)


def clear_conversation_messages_atomic(conv_id: str):
    """原子清空指定项目的所有消息（加锁保护 load-filter-save 事务）。

    返回删除的消息条数。
    """
    with _json_write_lock:
        messages = load_messages()
        before_count = len(messages)
        remaining = [m for m in messages if m.get("conversation_id") != conv_id]
        removed_count = before_count - len(remaining)
        save_messages(remaining)
    return removed_count


def delete_conversation_messages_atomic(conv_id: str):
    """原子删除指定项目的所有消息，同时清理无 conversation_id 的孤儿消息。

    用于 delete_conversation 场景：项目被删除时，其所有消息也需删除。
    加锁保护 load-filter-save 事务，防止多项目并行时更新丢失。
    """
    with _json_write_lock:
        messages = load_messages()
        # 删除该项目的消息，同时清理没有 conversation_id 的孤儿消息
        messages = [m for m in messages if m.get("conversation_id") != conv_id and m.get("conversation_id")]
        save_messages(messages)


# ========== 对话管理 ==========

def load_conversations():
    raw = load_json(CONVERSATIONS_FILE, {"conversations": []})
    # 防御性处理：兼容历史数据可能存储为裸列表的情况
    if isinstance(raw, list):
        convs = raw
    else:
        convs = raw.get("conversations", [])
    # 迁移：给旧对话补充 root_path 和更新内置智能体配置
    defaults = {a["id"]: a for a in _default_agents()}
    changed = False
    for conv in convs:
        if "root_path" not in conv:
            conv["root_path"] = ""
            changed = True
        # 更新项目级智能体配置
        if conv.get("agents"):
            for agent in conv["agents"]:
                aid = agent.get("id")
                if aid in defaults:
                    default = defaults[aid]
                    if agent.get("system_prompt") != default["system_prompt"]:
                        agent["system_prompt"] = default["system_prompt"]
                        changed = True
                    if agent.get("role") != default["role"]:
                        agent["role"] = default["role"]
                        changed = True
                    if agent.get("avatar") != default["avatar"]:
                        agent["avatar"] = default["avatar"]
                        changed = True
                    if "can_use_tools" not in agent:
                        agent["can_use_tools"] = default.get("can_use_tools", False)
                        changed = True
                else:
                    if "can_use_tools" not in agent:
                        agent["can_use_tools"] = True
                        changed = True
        # 旧标题迁移
        if conv.get("title") == "新对话":
            conv["title"] = "新项目"
            changed = True
    if changed:
        save_conversations(convs)
    return convs


def save_conversations(conversations):
    save_json(CONVERSATIONS_FILE, {"conversations": conversations})


# ========== 团队管理 ==========

def load_teams():
    raw = load_json(TEAMS_FILE, {"teams": []})
    if isinstance(raw, list):
        return raw
    return raw.get("teams", [])


def save_teams(teams):
    save_json(TEAMS_FILE, {"teams": teams})


def _new_team_id():
    return "team_" + uuid.uuid4().hex[:8]


class TeamCreate(BaseModel):
    name: str
    root_path: str = ""
    # 可选：从现有对话继承团队
    inherit_from: str = ""


@app.get("/api/teams")
def get_teams():
    """列出所有团队及其下的项目"""
    teams = load_teams()
    conversations = load_conversations()
    for team in teams:
        team["projects"] = [c for c in conversations if c.get("team_id") == team["id"]]
    return {"teams": teams}


@app.post("/api/teams")
def create_team(data: TeamCreate):
    """创建新团队。可选择从现有对话继承智能体配置。"""
    teams = load_teams()
    team_id = _new_team_id()

    # 确定智能体配置来源
    if data.inherit_from:
        conversations = load_conversations()
        source_conv = next((c for c in conversations if c["id"] == data.inherit_from), None)
        if not source_conv:
            raise HTTPException(status_code=404, detail="源对话不存在")
        agents = []
        for agent in source_conv.get("agents", []):
            new_agent = {k: v for k, v in agent.items()}
            if new_agent.get("id") != "main":
                new_agent["id"] = "agent_" + uuid.uuid4().hex[:8]
            agents.append(new_agent)
    else:
        # 复制全局默认智能体
        global_agents = load_agents()
        agents = [{
            "id": a["id"],
            "name": a["name"],
            "role": a["role"],
            "avatar": a["avatar"],
            "system_prompt": a.get("system_prompt", ""),
            "allowed_paths": a.get("allowed_paths", ["*"]),
            "model_config": a.get("model_config"),
            "can_use_tools": a.get("can_use_tools", False),
            "enabled_skills": a.get("enabled_skills", []),
            "can_invoke_sub_agent": a.get("can_invoke_sub_agent", False),
        } for a in global_agents]

    new_team = {
        "id": team_id,
        "name": data.name,
        "root_path": data.root_path.strip() if data.root_path else "",
        "agents": agents,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    teams.insert(0, new_team)
    save_teams(teams)
    return {"team": new_team, "message": f"团队「{data.name}」已创建"}


@app.put("/api/teams/{team_id}")
def update_team(team_id: str, data: dict):
    """更新团队信息（名称等）"""
    teams = load_teams()
    team = next((t for t in teams if t["id"] == team_id), None)
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    for k in ("name", "root_path"):
        if k in data and data[k] is not None:
            team[k] = data[k]
    team["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_teams(teams)
    return {"team": team, "message": "团队已更新"}


@app.delete("/api/teams/{team_id}")
def delete_team(team_id: str, delete_projects: bool = False):
    """删除团队。可选同时删除该团队下的所有项目。"""
    teams = load_teams()
    team = next((t for t in teams if t["id"] == team_id), None)
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    teams = [t for t in teams if t["id"] != team_id]
    save_teams(teams)

    if delete_projects:
        conversations = load_conversations()
        conversations = [c for c in conversations if c.get("team_id") != team_id]
        save_conversations(conversations)
    return {"status": "ok", "message": f"团队「{team['name']}」已删除"}


@app.get("/api/teams/{team_id}/agents")
def get_team_agents(team_id: str):
    """获取团队的智能体配置"""
    teams = load_teams()
    team = next((t for t in teams if t["id"] == team_id), None)
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    return {"agents": _get_conv_agents_with_main(team.get("agents"))}


@app.put("/api/teams/{team_id}/agents/{agent_id}")
def update_team_agent(team_id: str, agent_id: str, data: dict):
    """更新团队的智能体配置，并同步到该团队下的所有项目"""
    teams = load_teams()
    team = next((t for t in teams if t["id"] == team_id), None)
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    if not team.get("agents"):
        team["agents"] = [dict(a) for a in load_agents()]
    agent = next((a for a in team["agents"] if a["id"] == agent_id), None)
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")
    # 更新字段
    for k in ("name", "role", "avatar", "system_prompt", "allowed_paths",
              "model_config", "enabled_skills", "can_invoke_sub_agent"):
        if k in data:
            agent[k] = data[k]
    if "model_cfg" in data:
        agent["model_config"] = data["model_cfg"] if data["model_cfg"] else None
    team["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_teams(teams)

    # 同步到该团队下所有项目
    conversations = load_conversations()
    changed = False
    for conv in conversations:
        if conv.get("team_id") == team_id and conv.get("agents"):
            ca = next((a for a in conv["agents"] if a["id"] == agent_id), None)
            if ca:
                for k in ("name", "role", "avatar", "system_prompt", "allowed_paths",
                          "model_config", "enabled_skills", "can_invoke_sub_agent"):
                    if k in agent:
                        ca[k] = agent[k]
                changed = True
    if changed:
        save_conversations(conversations)
    return {"agent": agent, "message": "智能体已更新并同步到团队下所有项目"}


class TeamMemberCreate(BaseModel):
    name: str
    role: str = "worker"
    avatar: str = "🤖"
    system_prompt: str = ""
    template: str = "worker"
    enabled_skills: list[str] = []
    can_invoke_sub_agent: bool = False


@app.post("/api/teams/{team_id}/agents")
def add_team_member(team_id: str, data: TeamMemberCreate):
    """为团队添加新成员，并同步到该团队下所有项目"""
    teams = load_teams()
    team = next((t for t in teams if t["id"] == team_id), None)
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    if not team.get("agents"):
        team["agents"] = [dict(a) for a in load_agents()]

    new_agent_id = "agent_" + uuid.uuid4().hex[:8]
    new_agent = {
        "id": new_agent_id,
        "name": data.name,
        "role": data.role,
        "avatar": data.avatar,
        "system_prompt": data.system_prompt,
        "allowed_paths": ["*"],
        "model_config": None,
        "can_use_tools": True,
        "template": data.template,
        "enabled_skills": data.enabled_skills,
        "can_invoke_sub_agent": data.can_invoke_sub_agent,
    }
    team["agents"].append(new_agent)
    team["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_teams(teams)

    # 同步到该团队下所有项目
    conversations = load_conversations()
    changed = False
    for conv in conversations:
        if conv.get("team_id") == team_id and conv.get("agents"):
            conv["agents"].append(dict(new_agent))
            changed = True
    if changed:
        save_conversations(conversations)

    return {"agent": new_agent, "message": f"成员「{data.name}」已添加并同步到团队下所有项目"}


@app.delete("/api/teams/{team_id}/agents/{agent_id}")
def delete_team_member(team_id: str, agent_id: str):
    """从团队删除成员，并同步到该团队下所有项目"""
    if agent_id == "main":
        raise HTTPException(status_code=400, detail="不能删除主智能体")
    teams = load_teams()
    team = next((t for t in teams if t["id"] == team_id), None)
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")

    agent = next((a for a in team.get("agents", []) if a["id"] == agent_id), None)
    if not agent:
        raise HTTPException(status_code=404, detail="成员不存在")

    team["agents"] = [a for a in team["agents"] if a["id"] != agent_id]
    team["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_teams(teams)

    # 同步到该团队下所有项目
    conversations = load_conversations()
    changed = False
    for conv in conversations:
        if conv.get("team_id") == team_id and conv.get("agents"):
            conv["agents"] = [a for a in conv["agents"] if a["id"] != agent_id]
            changed = True
    if changed:
        save_conversations(conversations)

    return {"status": "ok", "message": f"成员「{agent['name']}」已删除并同步到团队下所有项目"}


class ConversationCreate(BaseModel):
    title: str = ""
    root_path: str = ""  # 项目根目录
    inherit_from: str = ""  # 源对话 ID，如果指定则继承该对话的智能体团队
    team_id: str = ""  # 所属团队 ID，如果指定则从团队复制智能体配置


@app.get("/api/conversations")
def get_conversations():
    """获取所有项目（对话）列表"""
    conversations = load_conversations()
    return {"conversations": conversations}


@app.post("/api/conversations")
def create_conversation(data: ConversationCreate):
    """新建项目（对话），复制全局智能体模板作为项目级配置。
    如果指定了root_path，会自动初始化标准目录结构。
    """
    conversations = load_conversations()
    conv_id = "proj_" + uuid.uuid4().hex[:8]
    
    # 复制智能体团队：优先从团队复制，其次继承指定对话，否则复制全局模板
    if data.team_id:
        # 从团队复制智能体配置
        teams = load_teams()
        source_team = next((t for t in teams if t["id"] == data.team_id), None)
        if not source_team:
            raise HTTPException(status_code=404, detail="团队不存在")
        source_agents = source_team.get("agents", [])
        conv_agents = []
        for agent in source_agents:
            new_agent = {k: v for k, v in agent.items()}
            if new_agent.get("id") != "main":
                new_agent["id"] = "agent_" + uuid.uuid4().hex[:8]
            conv_agents.append(new_agent)
    elif data.inherit_from:
        # 从源对话继承团队配置
        source_conv = next((c for c in conversations if c["id"] == data.inherit_from), None)
        if not source_conv:
            raise HTTPException(status_code=404, detail="源对话不存在，无法继承团队")
        source_agents = source_conv.get("agents", [])
        # 深拷贝并重新生成子智能体 ID（避免冲突）
        conv_agents = []
        for agent in source_agents:
            new_agent = {k: v for k, v in agent.items()}
            if new_agent.get("id") != "main":
                new_agent["id"] = "agent_" + uuid.uuid4().hex[:8]
            conv_agents.append(new_agent)
    else:
        # 复制全局智能体模板
        global_agents = load_agents()
        conv_agents = []
        for agent in global_agents:
            conv_agents.append({
                "id": agent["id"],
                "name": agent["name"],
                "role": agent["role"],
                "avatar": agent["avatar"],
                "system_prompt": agent.get("system_prompt", ""),
                "allowed_paths": agent.get("allowed_paths", ["*"]),
                "model_config": agent.get("model_config"),
                "can_use_tools": agent.get("can_use_tools", False),
                "enabled_skills": agent.get("enabled_skills", []),
                "can_invoke_sub_agent": agent.get("can_invoke_sub_agent", False),
            })
    
    root_path = data.root_path.strip() if data.root_path else ""
    initialized = False
    init_error = None
    
    # 如果有根目录，确保是绝对路径，并自动初始化目录结构
    if root_path:
        root_path = str(Path(root_path).resolve())
        try:
            root = Path(root_path)
            # 创建标准目录结构
            dirs_to_create = [
                ".agent/tasks",
                "shared",
                "agent_work",
                "deliverables",
            ]
            for d in dirs_to_create:
                (root / d).mkdir(parents=True, exist_ok=True)
            
            # 为内置智能体创建工作区并设置权限（最小权限：只授予私有工作区和共享区）
            shared_abs = str((root / "shared").resolve())
            
            for target in conv_agents:
                if target.get("id") == "main":
                    continue
                target_id = target.get("id")
                if not target_id:
                    continue
                work_dir = root / "agent_work" / target_id
                work_dir.mkdir(parents=True, exist_ok=True)
                work_abs = str(work_dir.resolve())
                # 不授予整个 tasks/ 目录权限，具体任务目录由 create_task 按需授权
                target["allowed_paths"] = [work_abs, shared_abs]
            
            initialized = True
        except Exception as e:
            init_error = str(e)
    
    new_conv = {
        "id": conv_id,
        "team_id": data.team_id,  # 所属团队
        "title": data.title or "新项目",
        "root_path": root_path,  # 项目根目录
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "agents": conv_agents,  # 项目级智能体配置（从团队复制）
        "structure_initialized": initialized  # 标记目录是否已初始化
    }
    conversations.insert(0, new_conv)
    save_conversations(conversations)
    
    # P0-2: 新项目创建时，注入团队级共享记忆到项目级智能体
    if data.team_id:
        inject_team_memory_to_agent(conv_id)
    
    result = {"conversation": new_conv}
    if initialized:
        result["auto_initialized"] = True
        result["message"] = "项目创建成功，已自动初始化标准目录结构"
    elif init_error:
        result["init_error"] = init_error
    
    return result


class MetaTeamCreate(BaseModel):
    title: str = "元团队规划"
    root_path: str = ""


@app.post("/api/conversations/create-meta-team")
def create_meta_team(data: MetaTeamCreate):
    """创建元团队项目（已废弃，请使用 /api/meta-team/tasks 替代）。

    ⚠️ 此接口已在 v0.5.0 废弃。元团队已从"项目类型"重构为"常驻功能模块"。
    请使用 POST /api/meta-team/tasks 创建设计任务。
    保留此接口仅为向后兼容，调用时返回废弃提示。
    """
    raise HTTPException(
        status_code=410,
        detail="此接口已废弃。元团队已重构为常驻功能模块，请使用左侧栏「团队设计」入口创建设计任务。"
    )
    conversations = load_conversations()
    conv_id = "proj_" + uuid.uuid4().hex[:8]

    # 1. 复制全局 main 智能体，覆盖 system_prompt 为元团队专用提示词
    global_agents = load_agents()
    main_template = next((a for a in global_agents if a["id"] == "main"), None)
    if not main_template:
        raise HTTPException(status_code=500, detail="全局 main 智能体模板不存在")

    conv_agents = [{
        "id": "main",
        "name": main_template["name"],
        "role": "元团队主智能体（团队规划师）",
        "avatar": main_template["avatar"],
        "system_prompt": META_TEAM_MAIN_PROMPT + CORE_RULES,
        "allowed_paths": ["*"],
        "model_config": main_template.get("model_config"),
        "can_use_tools": True,
    }]

    root_path = data.root_path.strip() if data.root_path else ""
    initialized = False
    init_error = None

    # 2. 初始化目录结构
    if root_path:
        root_path = str(Path(root_path).resolve())
        try:
            root = Path(root_path)
            for d in [".agent/tasks", "shared", "agent_work", "deliverables"]:
                (root / d).mkdir(parents=True, exist_ok=True)
            initialized = True
        except Exception as e:
            init_error = str(e)

    # 3. 创建四个子智能体（直接写入项目 agents，不走 create_team_member 工具）
    member_count = 0
    if initialized:
        shared_abs = str((Path(root_path) / "shared").resolve())
        tasks_abs = str((Path(root_path) / ".agent" / "tasks").resolve())

        for member_config in META_TEAM_MEMBERS:
            new_agent_id = "agent_" + uuid.uuid4().hex[:8]

            # 创建私有工作区
            work_dir = Path(root_path) / "agent_work" / new_agent_id
            work_dir.mkdir(parents=True, exist_ok=True)
            work_abs = str(work_dir.resolve())

            # 注入 CORE_RULES 和权限说明
            template_name = member_config.get("template", "worker")
            tpl = ROLE_TEMPLATES.get(template_name, ROLE_TEMPLATES["worker"])
            final_system_prompt = member_config["system_prompt"] + CORE_RULES

            can_write = tpl.get("can_write", True)
            perm_desc = "读写" if can_write else "只读"
            final_system_prompt += (
                f"\n\n## 你的权限范围\n"
                f"- ✅ {perm_desc}：agent_work/{new_agent_id}/（你的私有工作区）\n"
                f"- ✅ {perm_desc}：shared/（共享区）\n"
                f"- ✅ {perm_desc}：.agent/tasks/（任务文件夹）\n"
                f"- ❌ 禁止：调用管理工具（create_task/create_team_member 等，只有主智能体能用）\n"
                f"- ❌ 禁止：访问其他智能体的私有工作区"
            )

            conv_agents.append({
                "id": new_agent_id,
                "name": member_config["name"],
                "role": member_config["role"],
                "avatar": member_config.get("avatar", "🤖"),
                "system_prompt": final_system_prompt,
                "allowed_paths": [work_abs, shared_abs, tasks_abs],
                "model_config": None,
                "can_use_tools": True,
                "template": template_name,
            })
            member_count += 1

    # 4. 保存项目
    new_conv = {
        "id": conv_id,
        "title": data.title or "元团队规划",
        "root_path": root_path,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "agents": conv_agents,
        "structure_initialized": initialized,
        "is_meta_team": True,  # 标记为元团队项目
    }
    conversations.insert(0, new_conv)
    save_conversations(conversations)

    result = {
        "conversation": new_conv,
        "meta_team_members": member_count,
        "message": f"元团队项目已创建，包含主智能体和 {member_count} 个规划成员。在对话中发送需求即可启动规划流程。"
    }
    if initialized:
        result["auto_initialized"] = True
    elif init_error:
        result["init_error"] = init_error

    return result


def validate_blueprint(blueprint: dict) -> tuple[bool, str]:
    """校验团队蓝图是否符合 schema 规范。

    返回 (is_valid, error_message)。
    is_valid 为 True 时 error_message 为空字符串。
    """
    if not isinstance(blueprint, dict):
        return False, "蓝图必须是 JSON 对象"

    # 顶层必填字段
    for field in BLUEPRINT_REQUIRED_FIELDS["top_level"]:
        if field not in blueprint:
            return False, f"缺少必填字段：{field}"

    # 版本检查
    if blueprint.get("blueprint_version") != BLUEPRINT_SCHEMA_VERSION:
        return False, f"蓝图版本不匹配，当前支持 {BLUEPRINT_SCHEMA_VERSION}"

    # 成员校验
    members = blueprint.get("members")
    if not isinstance(members, list) or len(members) < 2:
        return False, "members 至少需要 2 个成员"
    if len(members) > 8:
        return False, "members 不应超过 8 个成员"

    member_names = []
    direct_refs = []  # [(成员名, with目标)]，收集后统一校验引用
    valid_templates = {"creator", "reviewer", "analyst", "worker", "coordinator"}
    for i, m in enumerate(members):
        for field in BLUEPRINT_REQUIRED_FIELDS["member"]:
            if field not in m:
                return False, f"成员 {i} 缺少必填字段：{field}"
        member_names.append(m["name"])

        # 深度校验：成员名称非空
        if not m["name"] or not m["name"].strip():
            return False, f"成员 {i} 的 name 不能为空"

        # 深度校验：模板必须是有效值
        template = m.get("template", "worker")
        if template not in valid_templates:
            return False, f"成员 {m['name']} 的 template 必须是 {valid_templates} 之一，当前为 {template}"

        # 深度校验：系统提示词非空
        if not m.get("system_prompt", "").strip():
            return False, f"成员 {m['name']} 的 system_prompt 不能为空"

        # 协作模式校验
        collab = m.get("collaboration", {})
        collab_type = collab.get("type")
        if collab_type not in BLUEPRINT_COLLAB_TYPES:
            return False, f"成员 {m['name']} 的 collaboration.type 必须是 {BLUEPRINT_COLLAB_TYPES} 之一"

        if collab_type == "star" and not collab.get("report_to"):
            return False, f"成员 {m['name']} 是 star 模式，必须指定 report_to"
        if collab_type == "direct":
            with_name = collab.get("with")
            if not with_name:
                return False, f"成员 {m['name']} 是 direct 模式，必须指定 with"
            direct_refs.append((m["name"], with_name))

    # 检查名称唯一性
    if len(set(member_names)) != len(member_names):
        return False, "成员名称不能重复"

    # 统一校验 direct 模式的 with 引用（此时所有成员名已收集完毕）
    for member_name, with_name in direct_refs:
        if with_name not in member_names:
            return False, f"成员 {member_name} 的 with 指向不存在的成员：{with_name}"

    # 任务校验（可选字段）
    tasks = blueprint.get("tasks")
    if tasks:
        if not isinstance(tasks, list):
            return False, "tasks 必须是数组"
        task_names = [t.get("name") for t in tasks]
        for t in tasks:
            assignee = t.get("assignee")
            if assignee and assignee not in member_names:
                return False, f"任务 {t.get('name')} 的 assignee 不在成员列表中：{assignee}"
            # 依赖检查
            for dep in t.get("depends_on", []):
                if dep not in task_names:
                    return False, f"任务 {t.get('name')} 依赖不存在的任务：{dep}"

        # 简单环检测
        visited = set()
        rec_stack = set()

        def has_cycle(task_name):
            visited.add(task_name)
            rec_stack.add(task_name)
            task = next((t for t in tasks if t.get("name") == task_name), None)
            if task:
                for dep in task.get("depends_on", []):
                    if dep not in visited:
                        if has_cycle(dep):
                            return True
                    elif dep in rec_stack:
                        return True
            rec_stack.discard(task_name)
            return False

        for t in tasks:
            name = t.get("name")
            if name and name not in visited:
                if has_cycle(name):
                    return False, "任务依赖存在循环"

    return True, ""


# ============================================================
# 技能与蓝图管理 API（Phase 1 & 2）
# ============================================================

class SkillCreate(BaseModel):
    name: str
    description: str = ""
    icon: str = "🔧"
    icon_bg: str = "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)"
    category: str = "自定义"
    version: str = "1.0.0"
    tools: list[str] = []
    system_prompt_fragment: str = ""
    enabled_by_default: bool = False


class SkillUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    icon_bg: str | None = None
    category: str | None = None
    version: str | None = None
    tools: list[str] | None = None
    system_prompt_fragment: str | None = None
    enabled_by_default: bool | None = None


class BlueprintCreate(BaseModel):
    name: str
    description: str = ""
    icon: str = "📋"
    icon_bg: str = "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)"
    category: str = "general"
    version: str = "1.0.0"
    source: str = "manual"
    blueprint_data: dict = {}


class BlueprintUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    icon_bg: str | None = None
    category: str | None = None
    version: str | None = None
    blueprint_data: dict | None = None


class BlueprintImport(BaseModel):
    name: str = ""
    description: str = ""
    blueprint_data: dict = {}
    file_path: str = ""


class BlueprintApply(BaseModel):
    project_title: str = ""
    root_path: str = ""


@app.get("/api/skills")
def api_list_skills():
    """列出所有本地技能。"""
    return {"skills": sb_list_skills()}


@app.get("/api/skills/{skill_id}")
def api_get_skill(skill_id: str):
    """获取单个技能详情。"""
    skill = sb_get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    return {"skill": skill}


@app.post("/api/skills")
def api_create_skill(data: SkillCreate):
    """创建自定义技能。"""
    skill = sb_create_skill(data.dict())
    return {"skill": skill, "message": f"技能「{skill['name']}」已创建"}


@app.put("/api/skills/{skill_id}")
def api_update_skill(skill_id: str, data: SkillUpdate):
    """更新技能。"""
    payload = {k: v for k, v in data.dict().items() if v is not None}
    if not payload:
        raise HTTPException(status_code=400, detail="没有要更新的字段")
    skill = sb_update_skill(skill_id, payload)
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    return {"skill": skill, "message": "已更新"}


@app.delete("/api/skills/{skill_id}")
def api_delete_skill(skill_id: str):
    """删除技能（内置技能不允许删除）。"""
    skill = sb_get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    if skill.get("source") == "builtin":
        raise HTTPException(status_code=400, detail="内置技能不允许删除")
    ok = sb_delete_skill(skill_id)
    if not ok:
        raise HTTPException(status_code=500, detail="删除失败")
    return {"status": "ok", "message": "已删除"}


@app.get("/api/blueprints")
def api_list_blueprints():
    """列出所有本地蓝图。"""
    return {"blueprints": sb_list_blueprints()}


@app.get("/api/blueprints/{bp_id}")
def api_get_blueprint(bp_id: str):
    """获取单个蓝图详情。"""
    bp = sb_get_blueprint(bp_id)
    if not bp:
        raise HTTPException(status_code=404, detail="蓝图不存在")
    return {"blueprint": bp}


@app.post("/api/blueprints")
def api_create_blueprint(data: BlueprintCreate):
    """创建本地蓝图。"""
    # 验证蓝图数据
    if data.blueprint_data:
        is_valid, error = sb_validate_bp_data(data.blueprint_data)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"蓝图数据无效：{error}")
    bp = sb_create_blueprint(data.dict())
    return {"blueprint": bp, "message": f"蓝图「{bp['name']}」已创建"}


@app.put("/api/blueprints/{bp_id}")
def api_update_blueprint(bp_id: str, data: BlueprintUpdate):
    """更新蓝图。"""
    payload = {k: v for k, v in data.dict().items() if v is not None}
    if not payload:
        raise HTTPException(status_code=400, detail="没有要更新的字段")
    if "blueprint_data" in payload and payload["blueprint_data"]:
        is_valid, error = sb_validate_bp_data(payload["blueprint_data"])
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"蓝图数据无效：{error}")
    bp = sb_update_blueprint(bp_id, payload)
    if not bp:
        raise HTTPException(status_code=404, detail="蓝图不存在")
    return {"blueprint": bp, "message": "已更新"}


@app.delete("/api/blueprints/{bp_id}")
def api_delete_blueprint(bp_id: str):
    """删除蓝图。"""
    bp = sb_get_blueprint(bp_id)
    if not bp:
        raise HTTPException(status_code=404, detail="蓝图不存在")
    ok = sb_delete_blueprint(bp_id)
    if not ok:
        raise HTTPException(status_code=500, detail="删除失败")
    return {"status": "ok", "message": "已删除"}


class ExportBlueprintFromConv(BaseModel):
    conv_id: str
    blueprint_name: str = ""
    description: str = ""
    category: str = "general"


@app.post("/api/conversations/{conv_id}/export-blueprint")
def export_blueprint_from_conversation(conv_id: str, data: ExportBlueprintFromConv):
    """将当前对话的智能体团队导出为蓝图，可用于分享或在其他项目中复用。
    
    会把对话级的 agents 转换为 blueprint_data 格式（team_blueprint.json）。
    """
    conversations = load_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    
    conv_agents = conv.get("agents", [])
    if len(conv_agents) < 2:
        raise HTTPException(status_code=400, detail="团队至少需要 2 个成员（含主智能体）才能导出为蓝图")
    
    # 转换为 blueprint_data 格式
    members = []
    for agent in conv_agents:
        member = {
            "name": agent.get("name", ""),
            "role": agent.get("role", agent.get("template", "worker")),
            "system_prompt": agent.get("system_prompt", ""),
            "allowed_paths": agent.get("allowed_paths", ["*"]),
        }
        # 可选字段
        if agent.get("template"):
            member["template"] = agent["template"]
        if agent.get("enabled_skills"):
            member["skills"] = agent["enabled_skills"]
        if "can_invoke_sub_agent" in agent:
            member["can_invoke_sub_agent"] = agent["can_invoke_sub_agent"]
        # 协作模式：主智能体为 coordinator，其他默认 star
        if agent.get("id") == "main":
            member["collaboration"] = {"type": "star"}
        else:
            member["collaboration"] = {"type": "star"}
        members.append(member)
    
    blueprint_data = {
        "blueprint_version": "1.0",
        "team_name": data.blueprint_name or conv.get("title", "导出团队"),
        "description": data.description or f"从项目「{conv.get('title', '')}」导出的团队蓝图",
        "members": members,
        "tasks": []
    }
    
    # 校验蓝图数据
    is_valid, error = sb_validate_bp_data(blueprint_data)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"生成的蓝图数据无效：{error}")
    
    # 创建蓝图记录
    bp = sb_create_blueprint({
        "name": blueprint_data["team_name"],
        "description": blueprint_data["description"],
        "icon": "📤",
        "icon_bg": "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
        "category": data.category,
        "version": "1.0.0",
        "source": "exported",
        "blueprint_data": blueprint_data,
    })
    
    return {"blueprint": bp, "blueprint_data": blueprint_data, "message": f"团队已导出为蓝图「{bp['name']}」"}


@app.post("/api/blueprints/import")
def api_import_blueprint(data: BlueprintImport):
    """导入蓝图。

    支持两种方式：
    1. 直接传入 blueprint_data（JSON 字典）
    2. 传入 file_path（服务器本地的蓝图文件路径，如 deliverables/team_blueprint.json）
    """
    try:
        if data.file_path:
            bp = sb_import_bp_file(data.file_path, data.name, data.description)
        elif data.blueprint_data:
            bp = sb_import_bp_data(data.blueprint_data, data.name, data.description)
        else:
            raise HTTPException(status_code=400, detail="请提供 blueprint_data 或 file_path")
        return {"blueprint": bp, "message": f"蓝图「{bp['name']}」已导入"}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/blueprints/{bp_id}/apply")
def api_apply_blueprint(bp_id: str, data: BlueprintApply):
    """应用蓝图：创建新项目并按蓝图配置生成团队成员。

    流程：
    1. 读取蓝图 blueprint_data
    2. 创建新项目（conversations.json）
    3. 初始化目录结构
    4. 按蓝图 members 创建子智能体（注入 system_prompt、设置权限）
    5. 不自动创建任务（由用户或主智能体决定）
    """
    bp = sb_get_blueprint(bp_id)
    if not bp:
        raise HTTPException(status_code=404, detail="蓝图不存在")

    blueprint_data = bp.get("blueprint_data", {})
    is_valid, error = validate_blueprint(blueprint_data)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"蓝图数据无效：{error}")

    conversations = load_conversations()
    conv_id = "proj_" + uuid.uuid4().hex[:8]

    # 1. 创建主智能体（复制全局 main 模板）
    global_agents = load_agents()
    main_template = next((a for a in global_agents if a["id"] == "main"), None)
    if not main_template:
        raise HTTPException(status_code=500, detail="全局 main 智能体模板不存在")

    conv_agents = [{
        "id": "main",
        "name": main_template["name"],
        "role": "项目经理，负责任务分配和协调",
        "avatar": main_template["avatar"],
        "system_prompt": main_template["system_prompt"] + "\n\n## 当前团队由蓝图创建\n" \
            + f"团队名称：{blueprint_data.get('team_name', '')}\n"
            + f"团队描述：{blueprint_data.get('description', '')}\n"
            + f"执行建议：{blueprint_data.get('execution_tips', '')}\n",
        "allowed_paths": ["*"],
        "model_config": main_template.get("model_config"),
        "can_use_tools": True,
        "enabled_skills": main_template.get("enabled_skills", []),
        "can_invoke_sub_agent": True,
    }]

    # 2. 初始化目录
    root_path = data.root_path.strip() if data.root_path else ""
    initialized = False
    if root_path:
        try:
            root_path = str(Path(root_path).resolve())
            root = Path(root_path)
            for d in [".agent/tasks", "shared", "agent_work", "deliverables"]:
                (root / d).mkdir(parents=True, exist_ok=True)
            initialized = True
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"目录初始化失败：{e}")

    # 3. 按蓝图 members 创建子智能体
    member_count = 0
    if initialized:
        shared_abs = str((Path(root_path) / "shared").resolve())
        tasks_abs = str((Path(root_path) / ".agent" / "tasks").resolve())

        for member in blueprint_data.get("members", []):
            new_agent_id = "agent_" + uuid.uuid4().hex[:8]

            # 创建私有工作区
            work_dir = Path(root_path) / "agent_work" / new_agent_id
            work_dir.mkdir(parents=True, exist_ok=True)
            work_abs = str(work_dir.resolve())

            # 构建系统提示词
            final_prompt = member.get("system_prompt", "")
            collab = member.get("collaboration", {})
            collab_type = collab.get("type", "star")
            if collab_type == "star":
                collab_hint = f"\n\n## 协作模式\n你采用星型协作，完成自己的任务后向 @主智能体 汇报。"
            elif collab_type == "direct":
                partner = collab.get("with", "")
                collab_hint = f"\n\n## 协作模式\n你采用直接协作，需要和 @{partner} 紧密配合，可直接 @{partner} 沟通。"
            else:  # parallel
                collab_hint = f"\n\n## 协作模式\n你采用并行协作，独立完成自己负责的部分，向 @主智能体 汇报。"

            final_prompt += collab_hint
            final_prompt += (
                f"\n\n## 你的权限范围\n"
                f"- ✅ 读写：agent_work/{new_agent_id}/（你的私有工作区）\n"
                f"- ✅ 读写：shared/（共享区）\n"
                f"- ✅ 读写：.agent/tasks/（任务文件夹）\n"
            )

            conv_agents.append({
                "id": new_agent_id,
                "name": member.get("name", f"成员{member_count+1}"),
                "role": member.get("role", ""),
                "avatar": "🤖",
                "system_prompt": final_prompt,
                "allowed_paths": [work_abs, shared_abs],  # 不授予 tasks/ 权限，任务执行时按需授权
                "model_config": None,
                "can_use_tools": True,
                "template": "worker",
                # Phase 3: 蓝图成员技能绑定 + 子代理调用权限
                "enabled_skills": member.get("skills", []),
                "can_invoke_sub_agent": member.get("can_invoke_sub_agent", False),
            })
            member_count += 1

    # 4. 保存项目
    new_conv = {
        "id": conv_id,
        "title": data.project_title or blueprint_data.get("team_name", "蓝图项目"),
        "root_path": root_path,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "agents": conv_agents,
        "structure_initialized": initialized,
        "blueprint_source": bp_id,
    }
    conversations.insert(0, new_conv)
    save_conversations(conversations)

    # 5. 增加蓝图应用次数
    sb_inc_bp_apply(bp_id)

    result = {
        "conversation": new_conv,
        "member_count": member_count,
        "message": f"已应用蓝图「{bp['name']}」，创建了包含 {member_count} 个成员的项目团队"
    }
    if initialized:
        result["auto_initialized"] = True
    return result


# ========== 元团队常驻模块 API ==========

class MetaTeamTaskCreate(BaseModel):
    title: str
    requirement: str
    mode: str = "deep"  # deep / fast
    expert_ids: list[str] | None = None


class MetaTeamChatRequest(BaseModel):
    message: str
    expert_id: str | None = None  # 指定对话的专家，None 用第一个
    default_config_id: str = ""
    thinking_override: Optional[bool] = None


class MetaTeamExpertUpdate(BaseModel):
    name: str | None = None
    model_config_id: str | None = None  # 绑定的模型配置 ID，避免和 Pydantic 保留字段冲突


class MetaTeamExpertCreate(BaseModel):
    name: str
    system_prompt: str
    model_config_id: str | None = None  # 绑定的模型配置 ID，None 用默认


class MetaTeamPromptUpgrade(BaseModel):
    new_prompt: str
    optimization_reason: str = ""


class MetaTeamSettingsUpdate(BaseModel):
    default_expert_count: int | None = None
    default_mode: str | None = None


# ----- 设计任务管理 -----

@app.get("/api/meta-team/tasks")
def api_mt_list_tasks(status: str | None = None):
    """列出所有元团队设计任务（支持状态筛选）"""
    tasks = mt_task_list(status)
    return {"tasks": tasks, "stats": mt_task_stats()}


@app.post("/api/meta-team/tasks")
def api_mt_create_task(data: MetaTeamTaskCreate):
    """新建设计任务"""
    if data.mode not in ("deep", "fast"):
        raise HTTPException(status_code=400, detail="mode 必须是 deep 或 fast")
    # 验证专家 ID 存在
    if data.expert_ids:
        experts = mt_get_experts_by_ids(data.expert_ids)
        if len(experts) != len(data.expert_ids):
            raise HTTPException(status_code=400, detail="部分专家 ID 不存在")
    task = mt_task_create(
        title=data.title,
        requirement=data.requirement,
        mode=data.mode,
        expert_ids=data.expert_ids
    )
    return {"task": task, "message": f"设计任务「{data.title}」已创建"}


@app.get("/api/meta-team/tasks/{task_id}")
def api_mt_get_task(task_id: str):
    """获取设计任务详情"""
    task = mt_task_get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="设计任务不存在")
    return {"task": task}


@app.delete("/api/meta-team/tasks/{task_id}")
def api_mt_delete_task(task_id: str):
    """删除设计任务"""
    ok = mt_task_delete(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="设计任务不存在或删除失败")
    return {"status": "ok", "message": "已删除"}


@app.post("/api/meta-team/tasks/{task_id}/finalize")
def api_mt_finalize_task(task_id: str):
    """确认产出蓝图：将最新版蓝图写入蓝图库"""
    task = mt_task_get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="设计任务不存在")

    blueprint_data = mt_task_get_latest_bp(task_id)
    if not blueprint_data:
        raise HTTPException(status_code=400, detail="任务还没有产出蓝图，无法确认入库")

    # 校验蓝图数据
    is_valid, error = sb_validate_bp_data(blueprint_data)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"蓝图数据无效：{error}")

    # 写入蓝图库
    team_name = blueprint_data.get("team_name", task.get("title", "元团队设计"))
    description = blueprint_data.get("description", "")
    bp = sb_create_blueprint({
        "name": team_name,
        "description": description,
        "icon": "📋",
        "icon_bg": "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
        "category": "general",
        "version": "1.0.0",
        "source": "meta_team_task",
        "blueprint_data": blueprint_data,
    })

    # 标记任务为已归档
    mt_task_set_bp_id(task_id, bp["id"])

    return {
        "blueprint": bp,
        "message": f"蓝图「{team_name}」已写入蓝图库，可在蓝图管理中查看和应用"
    }


# ----- 深度模式：多专家并行 + 评审融合（Phase 2）-----

class MetaTeamRunRequest(BaseModel):
    default_config_id: str = ""
    thinking_override: Optional[bool] = None


@app.post("/api/meta-team/tasks/{task_id}/run-proposals")
async def api_mt_run_proposals(task_id: str, data: MetaTeamRunRequest):
    """启动方案并行撰写（SSE 流式）

    3 个专家独立并行撰写完整蓝图方案。
    事件类型：expert_start / expert_complete / phase_complete / error / done
    """
    task = mt_task_get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="设计任务不存在")

    def generate():
        try:
            for event_type, event_data in mt_engine.run_proposals(task_id, data.default_config_id):
                yield f"event: {event_type}\ndata: {json_module.dumps(event_data, ensure_ascii=False)}\n\n"
            yield f"event: done\ndata: {json_module.dumps({'message': '方案撰写阶段完成'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json_module.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })


@app.post("/api/meta-team/tasks/{task_id}/run-reviews")
async def api_mt_run_reviews(task_id: str, data: MetaTeamRunRequest):
    """启动专家互相评审（SSE 流式）

    每个专家读取其他专家的方案，按五项标准打分 + 文字意见。
    事件类型：expert_start / expert_complete / phase_complete / error / done
    """
    task = mt_task_get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="设计任务不存在")

    def generate():
        try:
            for event_type, event_data in mt_engine.run_reviews(task_id, data.default_config_id):
                yield f"event: {event_type}\ndata: {json_module.dumps(event_data, ensure_ascii=False)}\n\n"
            yield f"event: done\ndata: {json_module.dumps({'message': '评审阶段完成'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json_module.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })


@app.post("/api/meta-team/tasks/{task_id}/run-fusion")
async def api_mt_run_fusion(task_id: str, data: MetaTeamRunRequest):
    """启动主智能体融合（SSE 流式）

    主智能体读取所有方案和评审，流式产出融合决策说明 + 最终蓝图。
    完成后自动积累专家经验。
    事件类型：fusion_start / token / fusion_complete / experience_recorded / phase_complete / error / done
    """
    task = mt_task_get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="设计任务不存在")

    def generate():
        try:
            for event_type, event_data in mt_engine.run_fusion(task_id, data.default_config_id):
                yield f"event: {event_type}\ndata: {json_module.dumps(event_data, ensure_ascii=False)}\n\n"
            yield f"event: done\ndata: {json_module.dumps({'message': '融合阶段完成'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json_module.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })


@app.post("/api/meta-team/tasks/{task_id}/run-all")
async def api_mt_run_all(task_id: str, data: MetaTeamRunRequest):
    """深度模式一键全流程（SSE 流式）

    依次自动执行方案撰写 → 评审 → 融合三个阶段。
    前一阶段完成后自动进入下一阶段，无需用户手动点击。
    事件类型：all_start / expert_start / expert_complete / phase_complete / fusion_start / token / fusion_complete / all_complete / error / done
    """
    task = mt_task_get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="设计任务不存在")

    def generate():
        try:
            for event_type, event_data in mt_engine.run_all_phases(task_id, data.default_config_id):
                yield f"event: {event_type}\ndata: {json_module.dumps(event_data, ensure_ascii=False)}\n\n"
            yield f"event: done\ndata: {json_module.dumps({'message': '全流程完成'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json_module.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })


# ----- 设计任务对话（SSE 流式）-----

@app.post("/api/meta-team/tasks/{task_id}/chat")
async def api_mt_chat(task_id: str, data: MetaTeamChatRequest):
    """与设计任务对话（SSE 流式）

    Phase 1 过渡期：单专家对话模式。
    用户选择一个专家（默认第一个），与之对话讨论需求。
    Phase 2 将实现多专家并行 + 评审融合。
    """
    task = mt_task_get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="设计任务不存在")

    # 确定对话专家
    expert_id = data.expert_id
    if not expert_id:
        expert_ids = task.get("expert_ids", [])
        expert_id = expert_ids[0] if expert_ids else "expert_1"

    expert = mt_get_expert(expert_id)
    if not expert:
        raise HTTPException(status_code=404, detail=f"专家 {expert_id} 不存在")

    # 保存用户消息
    mt_task_add_msg(task_id, MT_ROLE_USER, data.message)

    def generate():
        # 构建专家系统提示词（含历史经验）
        system_prompt = expert["system_prompt"]
        system_prompt += mt_get_expert_context(expert_id)
        system_prompt += f"\n\n## 当前设计任务\n任务标题：{task['title']}\n用户需求：{task.get('requirement', '')}\n\n请基于以上信息与用户对话，帮助设计团队方案。"

        # 构建对话历史（从任务消息转换）
        messages = []
        for msg in task.get("messages", []):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == MT_ROLE_USER:
                messages.append({"role": "user", "content": content})
            elif role == MT_ROLE_ASSISTANT or role == MT_ROLE_EXPERT:
                messages.append({"role": "assistant", "content": content})
        # 追加当前用户消息
        messages.append({"role": "user", "content": data.message})

        # 构建虚拟 agent（用于模型配置）
        agent = {
            "id": expert_id,
            "model_config": expert.get("model_config"),
            "can_use_tools": False,
        }

        # 发送对话开始事件
        yield f"event: agent_start\ndata: {json_module.dumps({'expert_id': expert_id, 'expert_name': expert['name']}, ensure_ascii=False)}\n\n"

        # 流式调用 LLM
        full_reply = ""
        for token in call_llm_stream(
            system_prompt=system_prompt,
            messages=messages,
            agent=agent,
            default_config_id=data.default_config_id,
            thinking_override=data.thinking_override
        ):
            full_reply += token
            yield f"event: token\ndata: {json_module.dumps({'content': token}, ensure_ascii=False)}\n\n"

        # 保存专家回复
        mt_task_add_msg(task_id, MT_ROLE_EXPERT, full_reply, expert_id)

        # 发送完成事件
        yield f"event: agent_end\ndata: {json_module.dumps({'expert_id': expert_id, 'full_content': full_reply}, ensure_ascii=False)}\n\n"
        yield f"event: done\ndata: {json_module.dumps({'message': 'ok'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })


# ----- 专家管理 -----

@app.get("/api/meta-team/experts")
def api_mt_list_experts():
    """列出所有常驻专家（含经验记录摘要和得分趋势）"""
    return {"experts": mt_list_experts()}


@app.get("/api/meta-team/experts/{expert_id}")
def api_mt_get_expert(expert_id: str):
    """获取专家完整信息（含完整经验日志）"""
    expert = mt_get_expert(expert_id)
    if not expert:
        raise HTTPException(status_code=404, detail="专家不存在")
    return {"expert": expert}


@app.post("/api/meta-team/experts")
def api_mt_create_expert(data: MetaTeamExpertCreate):
    """新增专家"""
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=400, detail="专家名称不能为空")
    if not data.system_prompt or not data.system_prompt.strip():
        raise HTTPException(status_code=400, detail="系统提示词不能为空")
    model_config = {"config_id": data.model_config_id} if data.model_config_id else None
    expert = mt_create_expert(data.name.strip(), data.system_prompt.strip(), model_config)
    return {"expert": expert, "message": "专家创建成功"}


@app.put("/api/meta-team/experts/{expert_id}")
def api_mt_update_expert(expert_id: str, data: MetaTeamExpertUpdate):
    """更新专家配置（名称、模型配置）"""
    updates = {}
    if data.name is not None:
        updates["name"] = data.name
    if data.model_config_id is not None:
        # 转换为内部 model_config 格式（{"config_id": "cfg_xxx"} 或 None）
        updates["model_config"] = {"config_id": data.model_config_id} if data.model_config_id else None
    if not updates:
        raise HTTPException(status_code=400, detail="没有要更新的字段")
    expert = mt_update_expert(expert_id, updates)
    if not expert:
        raise HTTPException(status_code=404, detail="专家不存在")
    return {"expert": expert, "message": "已更新"}


@app.delete("/api/meta-team/experts/{expert_id}")
def api_mt_delete_expert(expert_id: str):
    """删除专家（至少保留 1 个）"""
    success = mt_delete_expert(expert_id)
    if not success:
        # 可能是专家不存在，或只剩 1 个不允许删除
        experts = mt_list_experts()
        if not any(e["id"] == expert_id for e in experts):
            raise HTTPException(status_code=404, detail="专家不存在")
        raise HTTPException(status_code=400, detail="至少保留 1 个专家，无法删除")
    return {"status": "ok", "message": "专家已删除", "expert_id": expert_id}


@app.post("/api/meta-team/experts/{expert_id}/optimize-prompt")
async def api_mt_optimize_prompt(expert_id: str, data: MetaTeamChatRequest):
    """触发提示词优化流程：分析专家经验，产出优化建议（SSE 流式）

    将专家的经验记录 + 当前 system_prompt 发给 LLM，让其分析"提示词哪里可以改进"。
    返回优化建议（不直接修改提示词），用户审阅后通过 upgrade-prompt 确认升级。
    """
    expert = mt_get_expert(expert_id)
    if not expert:
        raise HTTPException(status_code=404, detail="专家不存在")

    def generate():
        # 构建优化分析的系统提示词
        analysis_prompt = f"""你是一位提示词工程专家，负责分析另一个专家的 system_prompt 并提出优化建议。

## 被分析的专家
- 名称：{expert['name']}
- 当前提示词版本：v{expert.get('prompt_version', 1)}

## 当前 system_prompt
{expert['system_prompt']}

## 该专家的历史经验记录
{json_module.dumps(expert.get('experience_log', []), ensure_ascii=False, indent=2)}

## 你的任务
分析这个专家的 system_prompt，结合其历史经验记录（特别是得分趋势和其他专家的反馈），产出优化建议：

1. **现状分析**：当前提示词的优点和不足
2. **具体问题**：哪些地方导致了低分或被批评
3. **优化建议**：具体的修改建议（附理由）
4. **优化后的完整 system_prompt**：基于建议重写的完整提示词

请以 Markdown 格式输出你的分析和建议。最后一部分必须是完整的优化后提示词，用 ```markdown 代码块包裹。
"""

        messages = [{"role": "user", "content": f"请分析专家「{expert['name']}」的提示词并给出优化建议。"}]

        agent = {
            "id": "optimizer",
            "model_config": None,
            "can_use_tools": False,
        }

        yield f"event: agent_start\ndata: {json_module.dumps({'expert_id': expert_id}, ensure_ascii=False)}\n\n"

        full_reply = ""
        for token in call_llm_stream(
            system_prompt=analysis_prompt,
            messages=messages,
            agent=agent,
            default_config_id=data.default_config_id or "",
            thinking_override=None
        ):
            full_reply += token
            yield f"event: token\ndata: {json_module.dumps({'content': token}, ensure_ascii=False)}\n\n"

        yield f"event: agent_end\ndata: {json_module.dumps({'analysis': full_reply}, ensure_ascii=False)}\n\n"
        yield f"event: done\ndata: {json_module.dumps({'message': 'ok'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })


@app.post("/api/meta-team/experts/{expert_id}/upgrade-prompt")
def api_mt_upgrade_prompt(expert_id: str, data: MetaTeamPromptUpgrade):
    """用户确认后升级专家提示词版本（prompt_version + 1）"""
    expert = mt_upgrade_prompt(expert_id, data.new_prompt, data.optimization_reason)
    if not expert:
        raise HTTPException(status_code=404, detail="专家不存在")
    return {
        "expert": {"id": expert["id"], "name": expert["name"], "prompt_version": expert["prompt_version"]},
        "message": f"专家「{expert['name']}」的提示词已升级到 v{expert['prompt_version']}"
    }


class MetaTeamRollbackRequest(BaseModel):
    target_version: int


@app.get("/api/meta-team/experts/{expert_id}/prompt-history")
def api_mt_get_prompt_history(expert_id: str):
    """获取专家提示词版本历史"""
    history = mt_get_prompt_history(expert_id)
    return {"history": history}


@app.post("/api/meta-team/experts/{expert_id}/rollback-prompt")
def api_mt_rollback_prompt(expert_id: str, data: MetaTeamRollbackRequest):
    """回退到指定版本的提示词"""
    expert = mt_rollback_prompt(expert_id, data.target_version)
    if not expert:
        raise HTTPException(status_code=404, detail="专家或目标版本不存在")
    return {
        "expert": {"id": expert["id"], "name": expert["name"], "prompt_version": expert["prompt_version"]},
        "message": f"专家「{expert['name']}」的提示词已回退到 v{expert['prompt_version']}"
    }


# ----- 全局设置 -----

@app.get("/api/meta-team/settings")
def api_mt_get_settings():
    """获取元团队全局设置"""
    return {"settings": mt_get_settings()}


@app.put("/api/meta-team/settings")
def api_mt_update_settings(data: MetaTeamSettingsUpdate):
    """更新元团队全局设置"""
    settings = mt_update_settings(
        default_expert_count=data.default_expert_count,
        default_mode=data.default_mode
    )
    return {"settings": settings, "message": "设置已更新"}


# ----- 元团队评审（Phase 3：评审闭环） -----

class MetaTeamReviewRequest(BaseModel):
    conversation_id: str
    user_feedback: str = ""
    default_config_id: str = ""


@app.post("/api/meta-team/review")
async def api_mt_start_review(data: MetaTeamReviewRequest):
    """启动元团队评审（SSE 流式）

    对应用蓝图创建的项目进行回访评审，采集七维度运行数据，
    专家并行诊断，主智能体汇总报告。
    """
    def generate():
        try:
            for event_type, event_data in mt_review.run_review(
                conversation_id=data.conversation_id,
                user_feedback=data.user_feedback,
                default_config_id=data.default_config_id
            ):
                yield f"event: {event_type}\ndata: {json_module.dumps(event_data, ensure_ascii=False)}\n\n"
            yield f"event: done\ndata: {json_module.dumps({'message': 'ok'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json_module.dumps({'message': f'评审流程异常：{str(e)}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })


@app.get("/api/meta-team/review/{review_id}")
def api_mt_get_review(review_id: str):
    """获取评审完整详情（元数据 + 输入摘要 + 专家诊断列表 + 报告）"""
    review = mt_review.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="评审记录不存在")
    return {"review": review}


@app.get("/api/meta-team/review")
def api_mt_list_reviews(conversation_id: str | None = None):
    """列出评审记录（可按项目筛选）"""
    reviews = mt_review.list_reviews(conversation_id)
    return {"reviews": reviews}


# ===== 专家产出文件查看 API =====

@app.get("/api/meta-team/tasks/{task_id}/proposal/{expert_id}")
def api_mt_get_proposal(task_id: str, expert_id: str):
    """读取设计任务中某专家的方案文件内容"""
    task = mt_task_get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="设计任务不存在")
    content = mt_task_get_proposal(task_id, expert_id)
    if content is None:
        raise HTTPException(status_code=404, detail="该专家的方案文件不存在")
    # 从专家配置中获取展示名称
    expert = mt_get_expert(expert_id)
    expert_name = expert["name"] if expert else expert_id
    return {
        "task_id": task_id,
        "task_title": task.get("title", ""),
        "expert_id": expert_id,
        "expert_name": expert_name,
        "content": content,
        "content_length": len(content)
    }


@app.get("/api/meta-team/tasks/{task_id}/review/{expert_id}")
def api_mt_get_review_file(task_id: str, expert_id: str):
    """读取设计任务中某专家的评审文件内容"""
    task = mt_task_get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="设计任务不存在")
    content = mt_task_get_review(task_id, expert_id)
    if content is None:
        raise HTTPException(status_code=404, detail="该专家的评审文件不存在")
    expert = mt_get_expert(expert_id)
    expert_name = expert["name"] if expert else expert_id
    return {
        "task_id": task_id,
        "task_title": task.get("title", ""),
        "expert_id": expert_id,
        "expert_name": expert_name,
        "content": content,
        "content_length": len(content)
    }


@app.get("/api/meta-team/tasks/{task_id}/fusion-decision")
def api_mt_get_fusion_decision(task_id: str):
    """读取设计任务的融合决策说明文件内容"""
    task = mt_task_get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="设计任务不存在")
    content = mt_task_get_fusion(task_id)
    if content is None:
        raise HTTPException(status_code=404, detail="融合决策文件不存在")
    return {
        "task_id": task_id,
        "task_title": task.get("title", ""),
        "content": content,
        "content_length": len(content)
    }


@app.get("/api/meta-team/tasks/{task_id}/blueprint/{version}")
def api_mt_get_blueprint_version(task_id: str, version: int):
    """读取设计任务中指定版本的蓝图 JSON 数据"""
    task = mt_task_get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="设计任务不存在")
    bp_data = mt_task_get_bp(task_id, version)
    if bp_data is None:
        raise HTTPException(status_code=404, detail=f"蓝图 v{version} 不存在")
    return {
        "task_id": task_id,
        "task_title": task.get("title", ""),
        "version": version,
        "blueprint_data": bp_data
    }


class ConversationRename(BaseModel):
    title: str


class ConversationUpdatePath(BaseModel):
    root_path: str


@app.put("/api/conversations/{conv_id}/path")
def update_conversation_path(conv_id: str, data: ConversationUpdatePath):
    """更新项目根目录，如果是首次设置会自动初始化目录结构"""
    conversations = load_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        raise HTTPException(status_code=404, detail="项目不存在")
    root_path = data.root_path.strip() if data.root_path else ""
    
    initialized = conv.get("structure_initialized", False)
    init_message = None
    
    if root_path:
        root_path = str(Path(root_path).resolve())
        # 如果还没初始化过，自动初始化目录结构
        if not initialized:
            try:
                root = Path(root_path)
                dirs_to_create = [
                    ".agent/tasks",
                    "shared",
                    "agent_work",
                    "deliverables",
                ]
                for d in dirs_to_create:
                    (root / d).mkdir(parents=True, exist_ok=True)
                
                # 为内置智能体创建工作区
                if not conv.get("agents"):
                    conv["agents"] = [dict(a) for a in load_agents()]
                
                shared_abs = str((root / "shared").resolve())
                
                # 为项目里的所有非 main 智能体建工作区（空团队模式下新项目通常为空，这里对已有项目兜底）
                conv_agents = conv.get("agents", [])
                for target in conv_agents:
                    if target.get("id") == "main":
                        continue
                    target_id = target.get("id")
                    if not target_id:
                        continue
                    work_dir = root / "agent_work" / target_id
                    work_dir.mkdir(parents=True, exist_ok=True)
                    work_abs = str(work_dir.resolve())
                    target["allowed_paths"] = [work_abs, shared_abs]

                initialized = True
                init_message = "已自动初始化项目目录结构"
            except Exception as e:
                init_message = f"目录初始化提示：{str(e)}"
    
    conv["root_path"] = root_path
    conv["structure_initialized"] = initialized
    conv["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_conversations(conversations)
    
    result = {"conversation": conv}
    if init_message:
        result["message"] = init_message
    return result


def _cleanup_project_files(root_path: str) -> dict:
    """清理项目根目录下的标准结构文件（.agent/、agent_work/、shared/、deliverables/）
    不会删除用户自己的其他文件。返回清理结果摘要。
    """
    cleaned = []
    if not root_path:
        return {"cleaned": cleaned, "error": "项目未设置工作目录"}
    root = Path(root_path)
    if not root.exists():
        return {"cleaned": cleaned, "error": f"项目目录不存在: {root_path}"}
    # 只清理标准结构目录，不动用户其他文件
    std_dirs = [".agent", "agent_work", "shared", "deliverables"]
    for d in std_dirs:
        target = root / d
        if target.exists():
            try:
                shutil.rmtree(target)
                cleaned.append(d + "/")
            except Exception as e:
                return {"cleaned": cleaned, "error": f"删除 {d}/ 失败: {str(e)}"}
    return {"cleaned": cleaned, "error": None}


@app.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: str, delete_files: bool = False):
    """删除对话及其所有消息。
    delete_files=true 时同时清理项目根目录下的标准结构文件
    （.agent/、agent_work/、shared/、deliverables/），用户其他文件不动。
    """
    conversations = load_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    root_path = conv.get("root_path", "") if conv else ""
    conversations = [c for c in conversations if c["id"] != conv_id]
    save_conversations(conversations)

    # 原子删除该对话的所有消息，同时清理没有 conversation_id 的孤儿消息
    # （历史遗留：旧版代码保存消息时未带 conversation_id，删除对话时这些消息无法被关联清理）
    delete_conversation_messages_atomic(conv_id)

    # 可选：清理项目文件（标准结构目录）
    file_cleanup = None
    if delete_files and root_path:
        file_cleanup = _cleanup_project_files(root_path)

    result = {"status": "ok"}
    if file_cleanup:
        result["file_cleanup"] = file_cleanup
    return result


@app.post("/api/conversations/{conv_id}/reset-structure")
def reset_project_structure(conv_id: str):
    """重置项目目录结构：清理 .agent/tasks/ 下的所有旧任务，
    重建标准目录（.agent/tasks、shared、agent_work、deliverables），
    并为内置助手重建工作区权限。
    用于「删除项目后遗留的 .agent 隐藏文件无法操作」场景。
    """
    conversations = load_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        raise HTTPException(status_code=404, detail="项目不存在")
    root_path = conv.get("root_path", "")
    if not root_path:
        raise HTTPException(status_code=400, detail="项目未设置工作目录，无法重置结构")

    root = Path(root_path)
    try:
        root_resolved = root.resolve()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"项目目录路径无效: {str(e)}")

    cleaned = []
    # 1. 清理标准目录（.agent/、agent_work/、shared/、deliverables/）
    for d in [".agent", "agent_work", "shared", "deliverables"]:
        target = root / d
        if target.exists():
            try:
                shutil.rmtree(target)
                cleaned.append(d + "/")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"清理 {d}/ 失败: {str(e)}")

    # 2. 重建标准目录
    dirs_to_create = [".agent/tasks", "shared", "agent_work", "deliverables"]
    for d in dirs_to_create:
        (root / d).mkdir(parents=True, exist_ok=True)

    # 3. 为内置助手重建工作区并更新权限
    shared_abs = str((root / "shared").resolve())
    workspaces = []
    if not conv.get("agents"):
        conv["agents"] = [dict(a) for a in load_agents()]
    # 遍历项目所有非 main 智能体，重建工作区和权限
    for target in conv["agents"]:
        if target.get("id") == "main":
            continue
        target_id = target.get("id")
        if not target_id:
            continue
        work_dir = root / "agent_work" / target_id
        work_dir.mkdir(parents=True, exist_ok=True)
        work_abs = str(work_dir.resolve())
        target["allowed_paths"] = [work_abs, shared_abs]
        workspaces.append(f"agent_work/{target_id}/")

    conv["structure_initialized"] = True
    save_conversations(conversations)

    return {
        "status": "ok",
        "cleaned": cleaned,
        "recreated": dirs_to_create,
        "workspaces": workspaces,
        "message": "项目结构已重置：旧任务已清理，标准目录已重建，助手工作区已就绪。"
    }


@app.post("/api/conversations/{conv_id}/clear-messages")
def clear_conversation_messages(conv_id: str):
    """清空当前项目的对话消息历史，但保留团队成员和项目文件。
    
    用于「开启新任务」场景：做完一个任务后想开始新任务，不希望旧上下文干扰。
    - 清空：messages.json 里属于该项目的消息
    - 保留：conversations.json 里的 agents、项目文件、任务产出
    """
    conversations = load_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 原子清空（加锁保护 load-filter-save 事务，防止多项目并行时更新丢失）
    removed_count = clear_conversation_messages_atomic(conv_id)

    # 更新项目的更新时间
    conv["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_conversations(conversations)

    return {
        "status": "ok",
        "removed_count": removed_count,
        "message": f"已清空当前项目的对话历史（共 {removed_count} 条消息），团队成员和项目文件保留不变。"
    }


# ========== P1-5: TODO 列表 API ==========

@app.get("/api/conversations/{conv_id}/todos")
def get_conversation_todos(conv_id: str):
    """获取当前项目的所有 TODO 清单"""
    conversations = load_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    root_path = conv.get("root_path", "")
    if not root_path:
        return {"todos": []}
    
    todos_dir = Path(root_path) / ".agent" / "todos"
    if not todos_dir.exists():
        return {"todos": []}
    
    todos = []
    for f in todos_dir.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                todo = json.load(fh)
                if todo.get("conversation_id") == conv_id:
                    todos.append(todo)
        except Exception:
            continue
    
    # 按创建时间排序
    todos.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"todos": todos}


@app.put("/api/conversations/{conv_id}")
def rename_conversation(conv_id: str, data: ConversationRename):
    """重命名对话"""
    conversations = load_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    conv["title"] = data.title.strip() or "新项目"
    conv["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_conversations(conversations)
    return {"conversation": conv}


@app.get("/api/conversations/{conv_id}/agents")
def get_conversation_agents(conv_id: str):
    """获取对话级的智能体配置"""
    conversations = load_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    # 确保返回的列表包含 main 主智能体（项目级 agents 只存子智能体）
    return {"agents": _get_conv_agents_with_main(conv.get("agents"))}


@app.put("/api/conversations/{conv_id}/agents/{agent_id}")
def update_conversation_agent(conv_id: str, agent_id: str, data: AgentUpdate):
    """更新对话级智能体配置（不影响全局模板）"""
    conversations = load_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    
    # 确保对话有 agents 字段
    if not conv.get("agents"):
        conv["agents"] = [dict(a) for a in load_agents()]
    
    agent = next((a for a in conv["agents"] if a["id"] == agent_id), None)
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")
    
    if data.name is not None:
        agent["name"] = data.name
    if data.role is not None:
        agent["role"] = data.role
    if data.avatar is not None:
        agent["avatar"] = data.avatar
    if data.system_prompt is not None:
        agent["system_prompt"] = data.system_prompt
    if data.allowed_paths is not None:
        agent["allowed_paths"] = data.allowed_paths
    if data.model_cfg is not None:
        # 约定：空 dict 表示清除模型配置，否则更新
        if data.model_cfg == {}:
            agent["model_config"] = None
        else:
            agent["model_config"] = data.model_cfg
    if data.enabled_skills is not None:
        agent["enabled_skills"] = data.enabled_skills
    if data.can_invoke_sub_agent is not None:
        agent["can_invoke_sub_agent"] = data.can_invoke_sub_agent

    conv["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_conversations(conversations)

    # 如果项目属于某个团队，同步更新团队和同团队其他项目
    team_id = conv.get("team_id")
    if team_id:
        teams = load_teams()
        team = next((t for t in teams if t["id"] == team_id), None)
        if team and team.get("agents"):
            ta = next((a for a in team["agents"] if a["id"] == agent_id), None)
            if ta:
                # 同步到团队
                for k in ("name", "role", "avatar", "system_prompt", "allowed_paths",
                          "model_config", "enabled_skills", "can_invoke_sub_agent"):
                    if k in agent:
                        ta[k] = agent[k]
                team["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                save_teams(teams)
                # 同步到同团队其他项目
                changed = False
                for c in conversations:
                    if c.get("team_id") == team_id and c["id"] != conv_id and c.get("agents"):
                        ca = next((a for a in c["agents"] if a["id"] == agent_id), None)
                        if ca:
                            for k in ("name", "role", "avatar", "system_prompt", "allowed_paths",
                                      "model_config", "enabled_skills", "can_invoke_sub_agent"):
                                if k in agent:
                                    ca[k] = agent[k]
                            changed = True
                if changed:
                    save_conversations(conversations)

    return {"agent": agent}


# ========== P0-1: 智能体记忆管理 API ==========

@app.get("/api/conversations/{conv_id}/agents/{agent_id}/memory")
def get_agent_memory(conv_id: str, agent_id: str):
    """获取智能体的历史记忆"""
    conversations = load_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    
    agents = _get_conv_agents_with_main(conv.get("agents"))
    agent = next((a for a in agents if a["id"] == agent_id), None)
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")
    
    return {"memory_log": agent.get("memory_log", [])}


@app.delete("/api/conversations/{conv_id}/agents/{agent_id}/memory")
def clear_agent_memory(conv_id: str, agent_id: str):
    """清空智能体的历史记忆"""
    conversations = load_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    
    agents = conv.get("agents", [])
    agent = next((a for a in agents if a["id"] == agent_id), None)
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")
    
    agent["memory_log"] = []
    conv["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_conversations(conversations)
    return {"status": "ok"}


@app.post("/api/conversations/{conv_id}/agents/{agent_id}/memory")
def add_agent_memory_manual(conv_id: str, agent_id: str, data: dict):
    """手动添加一条记忆"""
    memory_type = data.get("type", "fact")
    content = data.get("content", "")
    if not content:
        raise HTTPException(status_code=400, detail="content 不能为空")
    if memory_type not in ["preference", "lesson", "pattern", "fact"]:
        raise HTTPException(status_code=400, detail="type 必须是 preference/lesson/pattern/fact")
    
    success = add_memory_to_agent(conv_id, agent_id, memory_type, content)
    if success:
        return {"status": "ok"}
    else:
        return {"status": "ok", "message": "记忆已存在或添加失败（可能重复）"}


# ========== P1-7: 智能体性能统计 API ==========

@app.get("/api/conversations/{conv_id}/agents/stats")
def get_conversation_agent_stats(conv_id: str):
    """获取当前项目所有智能体的性能统计"""
    conversations = load_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    agents = _get_conv_agents_with_main(conv.get("agents"))
    stats_list = []
    for a in agents:
        stats_list.append({
            "agent_id": a["id"],
            "agent_name": a.get("name", ""),
            "role": a.get("role", ""),
            "stats": a.get("stats", {
                "total_tasks": 0, "completed_tasks": 0, "failed_tasks": 0,
                "avg_duration_sec": 0, "last_active_at": None
            }),
            "memory_count": len(a.get("memory_log", [])),
        })
    return {"agents_stats": stats_list}


# ========== Function Calling 工具系统 ==========

# 任务类型权限模板：主智能体创建任务时可选用，自动授予对应路径权限
TASK_TYPE_TEMPLATES = {
    "document": {
        "name": "文档编写",
        "desc": "写文档、报告、整理内容",
        "grant_paths": ["docs/"],  # 自动授予这些路径的读写权限
        "output_dir": "deliverables/docs/"
    },
    "code_review": {
        "name": "代码审查",
        "desc": "检查代码、找bug、代码审查",
        "grant_paths": [],  # 代码审查只授予任务input，不授予源码目录写入权限
        "readonly_paths": ["src/"],  # 只读权限
        "output_dir": "deliverables/reviews/"
    },
    "coding": {
        "name": "代码开发",
        "desc": "编写代码、功能开发",
        "grant_paths": ["src/"],
        "output_dir": "src/"
    },
    "data_analysis": {
        "name": "数据分析",
        "desc": "处理数据、分析数据、生成报告",
        "grant_paths": ["data/"],
        "output_dir": "deliverables/analysis/"
    },
    "testing": {
        "name": "测试检查",
        "desc": "编写测试、运行测试、检查问题",
        "grant_paths": ["tests/"],
        "readonly_paths": ["src/"],
        "output_dir": "test_results/"
    },
    "general": {
        "name": "通用任务",
        "desc": "一般性任务，使用默认权限",
        "grant_paths": [],
        "output_dir": "deliverables/"
    }
}

# 工具定义（OpenAI function calling 格式）
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "列出指定文件夹下的文件和子文件夹。用来了解项目结构。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要列出的文件夹路径，相对于项目根目录。例如：'.', 'src', 'docs'"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文件的全部内容。用来查看代码、文档等文件内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要读取的文件路径，相对于项目根目录。例如：'README.md', 'src/main.py'"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "写入内容到文件，如果文件不存在会自动创建（包括父文件夹）。用来创建文档、写代码、保存报告等。注意：子智能体只能写入自己有权限的目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要写入的文件路径，相对于项目根目录。例如：'docs/report.md', 'agent_work/assistant_a/output.txt'"
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入的文件内容"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "创建一个文件夹（如果父文件夹不存在也会自动创建）。用来组织项目结构。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要创建的文件夹路径，相对于项目根目录。例如：'docs', 'src/components'"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "init_project_structure",
            "description": "【仅主智能体可用】初始化项目标准目录结构。新项目第一次使用时必须调用一次。创建以下目录：\n- .agent/tasks/ - 任务文件夹（存放每个任务的输入输出）\n- shared/ - 共享文件区（智能体之间交换非任务文件）\n- agent_work/ - 智能体私有工作区（每个智能体有自己的子目录）\n- deliverables/ - 最终交付物目录（主智能体整理后放这里）",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_agent_workspace",
            "description": "【仅主智能体可用】为指定子智能体创建私有工作文件夹，并授予该文件夹的完整读写权限。子智能体的临时工作文件应该放在这里。调用子智能体协作前，应该先为它创建工作区（新项目初始化后会自动为内置助手创建）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "子智能体的id，例如 'assistant_a', 'assistant_b'"
                    }
                },
                "required": ["agent_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "【仅主智能体可用】创建一个任务并分配给子智能体。这是分配任务的推荐方式！会自动：\n1. 创建独立的任务文件夹（.agent/tasks/{task_id}/）\n2. 创建 input/ 子目录（你可以把需要处理的文件放进去，子智能体只有读权限）\n3. 创建 output/ 子目录（子智能体有写权限，用于提交结果）\n4. 自动授予子智能体对应任务类型的权限\n5. 返回任务id和任务文件夹路径\n\n【避免耦合】：每个任务有独立的input/output，多个智能体协作时不会互相干扰。",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "要分配给哪个子智能体，例如 'assistant_a', 'assistant_b'"
                    },
                    "task_type": {
                        "type": "string",
                        "description": "任务类型，用于自动配置权限。可选值：document(文档编写), code_review(代码审查), coding(代码开发), data_analysis(数据分析), testing(测试检查), general(通用任务)",
                        "enum": ["document", "code_review", "coding", "data_analysis", "testing", "general"]
                    },
                    "description": {
                        "type": "string",
                        "description": "任务描述，说明要做什么"
                    },
                    "input_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "可选：需要处理的文件路径列表（相对于项目根目录）。系统会自动把这些文件的读取权限授予子智能体。例如：['src/main.py', 'docs/需求.md']"
                    },
                    "extra_grant_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "可选：额外需要授予读写权限的路径列表。例如：['src/components/']"
                    }
                },
                "required": ["agent_id", "task_type", "description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_sub_task",
            "description": "【仅协调者(coordinator)可用】创建一个 L2 执行者并派发子任务。会自动：\n1. 创建一个新的 L2 执行者智能体（使用 worker 模板，受限工具集）\n2. 创建独立的任务文件夹（.agent/tasks/{task_id}/，含 input/ 和 output/）\n3. 授予 L2 执行者受限权限（仅本任务目录 + 你的工作区子集）\n4. 把 L2 执行者加入团队，你可以直接 @它 调度\n\n适用场景：你作为组长收到主智能体的大任务后，拆分成多个子任务分别派发给组员并行执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "L2 执行者的名字，如 '前端开发A'、'章节撰稿人1'"
                    },
                    "role": {
                        "type": "string",
                        "description": "L2 执行者的角色描述，如 'React 组件开发'、'武侠章节撰写'"
                    },
                    "task_type": {
                        "type": "string",
                        "description": "任务类型，用于自动配置权限。可选值：document(文档编写), code_review(代码审查), coding(代码开发), data_analysis(数据分析), testing(测试检查), general(通用任务)",
                        "enum": ["document", "code_review", "coding", "data_analysis", "testing", "general"]
                    },
                    "description": {
                        "type": "string",
                        "description": "子任务详细描述，说明要做什么、验收标准、注意事项"
                    },
                    "input_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "可选：需要处理的文件路径列表（相对于项目根目录）。系统会自动授予读取权限。"
                    },
                    "style_guide": {
                        "type": "string",
                        "description": "可选：风格指南，如 '遵循 Airbnb 规范'、'金庸武侠风格'",
                        "default": "通用规范"
                    }
                },
                "required": ["name", "role", "task_type", "description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grant_path_access",
            "description": "【仅主智能体可用】给某个子智能体授予指定路径的读写权限。当子智能体需要访问任务模板没有覆盖的路径时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "子智能体的id"
                    },
                    "path": {
                        "type": "string",
                        "description": "要授权的路径，相对于项目根目录，例如 'docs/', 'src/components/'"
                    }
                },
                "required": ["agent_id", "path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "revoke_path_access",
            "description": "【仅主智能体可用】撤销某个子智能体对指定路径的访问权限。任务完成后可以用来清理权限。",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "子智能体的id"
                    },
                    "path": {
                        "type": "string",
                        "description": "要撤销权限的路径，相对于项目根目录"
                    }
                },
                "required": ["agent_id", "path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "submit_task_result",
            "description": "【子智能体使用】子智能体完成任务后，提交结果文件到任务的output目录，或者直接提交文本结果。主智能体会在output目录看到你的产出。",
            "parameters": {
                "type": "object",
                "properties": {
                    "result_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "结果文件路径列表（你已经写入的文件，相对于项目根目录）。系统会把它们登记为任务产出。"
                    },
                    "summary": {
                        "type": "string",
                        "description": "任务完成摘要，说明你做了什么、结果在哪里"
                    }
                },
                "required": ["summary"]
            }
        }
    },
    # ========== 文件归档工具（主智能体归档产出用）==========
    {
        "type": "function",
        "function": {
            "name": "move_file",
            "description": "【归档专用】移动文件到新位置（如把任务产出从 .agent/tasks/xxx/output/ 移到 deliverables/）。源文件会被删除，目标位置自动创建。用来归档子智能体的产出文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_path": {
                        "type": "string",
                        "description": "源文件路径，相对于项目根目录。例如：'.agent/tasks/task_xxx/output/report.md'"
                    },
                    "target_path": {
                        "type": "string",
                        "description": "目标文件路径，相对于项目根目录。例如：'deliverables/report.md'"
                    }
                },
                "required": ["source_path", "target_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "copy_file",
            "description": "复制文件到新位置（保留源文件）。用于需要同时保留任务产出和归档副本的场景。",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_path": {
                        "type": "string",
                        "description": "源文件路径，相对于项目根目录"
                    },
                    "target_path": {
                        "type": "string",
                        "description": "目标文件路径，相对于项目根目录"
                    }
                },
                "required": ["source_path", "target_path"]
            }
        }
    },
    # ========== TODO 清单工具（仅主智能体可用，M2 机制）==========
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "【主智能体/组长可用】查询当前项目所有任务及其状态。用于感知任务进度：哪些 pending（待处理）、哪些 completed（已完成）。调度多步任务时必用，避免遗漏未完成的任务。",
            "parameters": {
                "type": "object",
                "properties": {
                    "status_filter": {
                        "type": "string",
                        "enum": ["all", "pending", "completed"],
                        "description": "筛选状态：all=全部，pending=只看待处理，completed=只看已完成。默认 all。"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_todo_list",
            "description": "【仅主智能体可用】创建任务清单。接到涉及 2 个步骤以上的复杂任务时必须先用本工具拆解成清单，然后逐项执行并更新状态。单步任务不要用。清单存储在 .agent/todos/ 目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "清单标题，简短描述任务目标，如「写武侠小说并审阅」"
                    },
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "任务步骤数组，每项是一个可执行步骤，如 [\"创建创作者\", \"创建审阅者\", \"写第一章\", \"审阅修改\"]。至少 2 项，最多 10 项。",
                        "minItems": 2,
                        "maxItems": 10
                    }
                },
                "required": ["title", "items"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_todo_status",
            "description": "【仅主智能体可用】更新 TODO 清单中某一项的状态。每完成一项必须调用本工具标记为 completed。状态取值：pending（待处理）、in_progress（进行中）、completed（已完成）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "todo_id": {
                        "type": "string",
                        "description": "清单 ID，由 create_todo_list 返回"
                    },
                    "item_index": {
                        "type": "integer",
                        "description": "要更新的项索引（从 0 开始）"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed"],
                        "description": "新状态"
                    }
                },
                "required": ["todo_id", "item_index", "status"]
            }
        }
    },
    # ========== 文件版本控制工具（P1-6，仅主智能体可用）==========
    {
        "type": "function",
        "function": {
            "name": "list_file_versions",
            "description": "【仅主智能体可用】查看某个文件的历史版本列表。每次 write_file 或 edit_file 时系统会自动备份旧版本。返回版本列表，包含时间戳和文件大小。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件路径（相对于项目根目录）"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_rollback",
            "description": "【仅主智能体可用】将文件回退到指定的历史版本。回退前会自动备份当前版本。需要先调用 list_file_versions 获取版本列表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件路径（相对于项目根目录）"
                    },
                    "version": {
                        "type": "string",
                        "description": "要回退到的版本名（从 list_file_versions 获取）"
                    }
                },
                "required": ["path", "version"]
            }
        }
    },
    # ========== 团队管理工具（仅主智能体可用）==========
    {
        "type": "function",
        "function": {
            "name": "list_team_members",
            "description": "【仅主智能体可用】查看当前项目团队的所有成员列表，包括每个成员的ID、名称、角色和权限范围。用于了解可用的人力资源。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_team_member",
            "description": "【仅主智能体可用】创建一个新的子智能体并加入当前项目团队。新成员会自动获得私有工作区和基本权限。**推荐用 template 参数**（creator/reviewer/analyst/worker），系统会自动生成高质量提示词，比临时编 system_prompt 更稳定。也可传 system_prompt 完全自定义。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "智能体名称，如「作者」「审查员」「分析师」"
                    },
                    "role": {
                        "type": "string",
                        "description": "角色定位，简短描述这个智能体的职责，如「负责武侠小说创作」「负责代码质量检查」"
                    },
                    "template": {
                        "type": "string",
                        "enum": ["creator", "reviewer", "analyst", "worker", "coordinator"],
                        "description": "⭐推荐使用。角色能力模板，系统自动生成提示词：\n- creator：创作者（读写），适合写小说/文案/报告/代码\n- reviewer：审阅者（只读），适合审稿/Code Review/质量检验\n- analyst：分析者（只读输入+写报告），适合数据分析/调研\n- worker：执行者（读写，通用），适合翻译/校对/测试\n- coordinator：协调者（组长），仅复杂项目用\n传了 template 就不用传 system_prompt"
                    },
                    "domain_hint": {
                        "type": "string",
                        "description": "领域提示（配合 template 用）。如「小说章节」「React 组件」「研究报告」「市场数据」。可选，默认'相关内容'"
                    },
                    "style_guide": {
                        "type": "string",
                        "description": "风格指南（配合 template 用）。如「金庸武侠风格」「Airbnb 规范」「学术规范」「从读者视角」。可选，默认'通用规范'"
                    },
                    "system_prompt": {
                        "type": "string",
                        "description": "完全自定义系统提示词（高级用法）。与 template 二选一，传了 template 就不用传这个。"
                    },
                    "avatar": {
                        "type": "string",
                        "description": "头像emoji，如 🔍📝🎨📊💻。可选，默认🤖",
                        "default": "🤖"
                    },
                    "skills": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "⭐技能ID列表（可选）。为新成员绑定技能，技能会额外授予工具和注入提示词片段。可用技能可用 list_skills 工具查询（如有）。例：['file-ops','archive']",
                        "default": []
                    },
                    "can_invoke_sub_agent": {
                        "type": "boolean",
                        "description": "是否允许该成员调用临时子代理处理子任务（可选，默认 false）。开启后该成员可使用 invoke_sub_agent 工具，适合协调者/组长角色。",
                        "default": False
                    }
                },
                "required": ["name", "role"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_team_member",
            "description": "【仅主智能体可用】修改子智能体的角色、系统提示词或权限。用于根据任务进展调整团队成员的职能。注意：不能修改主智能体自身。",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "要修改的智能体ID或名称"
                    },
                    "name": {
                        "type": "string",
                        "description": "新名称（可选）"
                    },
                    "role": {
                        "type": "string",
                        "description": "新角色定位（可选）"
                    },
                    "system_prompt": {
                        "type": "string",
                        "description": "新的系统提示词（可选）"
                    },
                    "avatar": {
                        "type": "string",
                        "description": "新头像emoji（可选）"
                    }
                },
                "required": ["agent_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remove_team_member",
            "description": "【仅主智能体可用】从团队中移除一个子智能体。注意：不能移除主智能体自身。移除后该智能体将不再可用，但其已产出的文件会保留。",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "要移除的智能体ID或名称"
                    }
                },
                "required": ["agent_id"]
            }
        }
    },
    # ========== 代码搜索与编辑工具（P0 能力提升）==========
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "【代码搜索】在文件内容中搜索匹配正则表达式的行。用于快速定位函数定义、变量使用、错误信息等。比 list_directory 逐个遍历快得多。支持限定文件类型和上下文行数。",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "正则表达式（支持 ripgrep 语法）。例如：'function authUser' 匹配函数定义；'error.*log' 匹配错误日志；'class\\\\s+\\\\w+' 匹配所有类定义"
                    },
                    "path": {
                        "type": "string",
                        "description": "搜索的目录路径，相对于项目根目录。默认搜索整个项目。例如：'src' 只搜 src 目录"
                    },
                    "glob": {
                        "type": "string",
                        "description": "文件名过滤模式，如 '*.js'、'*.py'、'*.{ts,tsx}'。可选"
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "匹配行前后显示的上下文行数，默认 0（只显示匹配行）。建议 2-3 以理解上下文"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最多返回的匹配结果数，默认 50。避免结果过多撑爆 token"
                    }
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "glob",
            "description": "【文件名搜索】按文件名模式快速查找文件。用于找特定文件、统计文件数量、发现项目结构。比 list_directory 遍历快得多，支持递归。",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "文件名匹配模式（支持 * 和 **）。例如：'**/*.py' 找所有 Python 文件；'src/**/*.ts' 找 src 下所有 TS 文件；'*.md' 找根目录的 markdown 文件"
                    },
                    "path": {
                        "type": "string",
                        "description": "搜索的起始目录，相对于项目根目录。默认整个项目。例如：'src'"
                    }
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "【精确编辑】用 SEARCH/REPLACE 方式修改文件的一部分，不需要重写整个文件。先在文件里找到 old_str（必须精确匹配，包括缩进和换行），替换成 new_str。比 write_file 重写整个文件更安全、更省 token。适合改大型文件里的几行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要编辑的文件路径，相对于项目根目录"
                    },
                    "old_str": {
                        "type": "string",
                        "description": "要在文件中查找并替换的原文。必须是文件中精确存在的一段（包括缩进、换行）。建议包含 3-5 行上下文以保证唯一匹配。如果匹配到多处或零处会报错。"
                    },
                    "new_str": {
                        "type": "string",
                        "description": "替换后的新内容。和 old_str 不同就会执行替换。如果想删除一段代码，new_str 可以为空字符串。"
                    }
                },
                "required": ["path", "old_str", "new_str"]
            }
        }
    },
    # ========== 子代理调用工具（Phase 3） ==========
    {
        "type": "function",
        "function": {
            "name": "invoke_sub_agent",
            "description": "创建一个临时子代理来处理子任务。子代理会独立执行任务并返回结果。适用于：需要专注处理复杂子任务、需要不同角色视角、需要并行处理多个独立任务。注意：子代理不能再创建子代理（非递归），最大工具轮次8轮。",
            "parameters": {
                "type": "object",
                "properties": {
                    "sub_agent_name": {
                        "type": "string",
                        "description": "子代理的名称，如'调研员'、'撰稿人'、'审查员'"
                    },
                    "task_description": {
                        "type": "string",
                        "description": "给子代理的任务描述，要具体明确，包含目标、要求、产出格式等"
                    },
                    "system_prompt": {
                        "type": "string",
                        "description": "子代理的系统提示词（可选）。不填则使用默认 worker 模板。可自定义子代理的角色定位、工作流程、产出规范。"
                    },
                    "inherit_permissions": {
                        "type": "boolean",
                        "description": "是否继承当前智能体的文件权限。默认 true。设为 false 则子代理只能读取 shared/ 目录。",
                        "default": True
                    }
                },
                "required": ["sub_agent_name", "task_description"]
            }
        }
    }
]

# 主智能体专用的管理工具（子智能体调用会被拦截，且不会看到这些工具的 schema）
MAIN_ONLY_TOOLS = (
    "init_project_structure",
    "create_agent_workspace",
    "create_task",
    "grant_path_access",
    "revoke_path_access",
    "list_team_members",
    "create_team_member",
    "update_team_member",
    "remove_team_member",
    "move_file",      # 归档操作只有主智能体做
    "copy_file",      # 复制归档也只有主智能体做
    "list_tasks",     # 任务进度查询：主智能体/组长用
    "create_todo_list",     # M2: TODO 清单只有主智能体用
    "update_todo_status",   # M2: TODO 清单只有主智能体用
    "list_file_versions",   # P1-6: 文件版本管理只有主智能体用
    "file_rollback",        # P1-6: 文件回退只有主智能体用
)

# 子智能体可用的工具白名单（主智能体可用全部，子智能体只能用这些）
SUB_AGENT_TOOLS = (
    "list_directory",
    "read_file",
    "write_file",
    "create_directory",
    "grep",            # ⭐ 子智能体也能用代码搜索
    "glob",            # ⭐ 子智能体也能用文件名搜索
    "edit_file",       # ⭐ 子智能体也能用精确编辑
    "submit_task_result",
)

# 阶段3：并行调度配置
# 同一轮最多并行执行的智能体数量（避免并发过高触发 API 限流或资源耗尽）
MAX_PARALLEL = 5

# ========== 通用核心规则（所有智能体共享，类似 Trae 的全局规则层）==========
# 这套规则自动注入到主智能体和所有子智能体的 system_prompt 末尾
# 各角色模板只需写角色专属内容，通用规则在这里统一维护
CORE_RULES = """
## ⚠️ 通用核心规则（所有智能体必须遵守）

### 1. 立即行动原则
- 收到明确任务后，**立即调用工具执行**，不要先长篇解释"我打算怎么做"
- 简短说明意图（1-2 句）→ 调用工具 → 根据结果回复
- 禁止"只说不做"：如果任务涉及文件操作/搜索/提交，必须调用对应工具

### 2. 工具调用硬约束
- **涉及文件操作**（读/写/改/搜索）→ 必须调用对应工具，禁止只描述"我已经看了/写了"
- **涉及任务提交** → 必须调用 submit_task_result，禁止只说"已完成"
- 只有纯闲聊/问答/状态汇报，才允许不调用工具
- ✅ 正确：用户说"写个文件" → 调用 write_file → 返回结果 → 回复"已写入 xxx"
- ❌ 错误：用户说"写个文件" → 直接回复"好的，我已经写了"（没调用工具）

### 3. 真实性约束（防幻觉）
- **禁止编造文件路径或任务 ID**：你说的每一个路径、task_id，都必须是工具真实返回的
- **禁止"假装"执行**：没调用工具就不要说"已写入""已归档""已完成"
- **归档必须用 move_file**：只有看到工具返回成功，才能声称"已归档"
- 不确定的信息主动说明"我不确定"，不要编造

### 4. 工具使用策略
- **找文件** → 用 glob（按文件名）或 grep（按内容），不要用 list_directory 逐层遍历
- **读文件** → 用 read_file 指定具体路径
- **改文件**：
  - 小改动（改几行）→ 用 edit_file（SEARCH/REPLACE），省 token 且安全
  - 新建文件 / 大改重写 → 用 write_file
- **搜索后先看再改**：grep/glob 返回结果后，先 read_file 确认内容，再 edit_file
- **edit_file 前必须先 read_file**：防止用旧内容导致替换失败

### 5. 响应格式
- **简洁明了**：先说结论，再补充必要细节
- 用 Markdown 格式（标题、列表、代码块）
- 不嵌套列表（保持单层）
- 文件路径用反引号包裹：`shared/report.md`
- 不要向用户暴露工具的内部执行细节，只说结果

### 6. 角色边界
- 收到两类消息要区分：
  - **任务指令**：来自上级（主智能体/用户），内容是要你做的事 → 执行
  - **系统通知**：以「【系统通知：...】」开头，是工作汇报 → 这是信息同步，不是新指令
- 完成任务后用 submit_task_result 提交，不要直接回复"完成了"
- 需要澄清时 @上级（主智能体/组长），不要自行假设

### 7. 任务进度感知（主智能体专属）
- **多步任务必用 list_tasks**：安排任务后、收尾总结时，调用 list_tasks 查看任务状态（pending/completed）
- **不要遗漏 pending 任务**：如果 list_tasks 显示有 pending 任务，必须 @对应智能体 推进，或明确说明为何停止
- **收尾总结要完整**：收尾总结时如果有未完成任务，不要说"全部完成"，要说"还有 X 个任务待处理"
- **保持任务链不断**：安排了 A→B→C 的任务链时，A 完成后要主动安排 B，B 完成后安排 C，不要断链

### 8. 跨轮续接（主智能体专属，重要）
- **收到"继续""接着""下一步"等延续性指令时，第一反应是调用 list_tasks 查看任务进度**，不要凭记忆推断
- **任务状态是跨轮持久化的**：上一轮对话创建的任务、产出的文件，都在 .agent/tasks/ 和 deliverables/ 里，list_tasks 能看到
- **不要问"之前做到哪了"**：直接用 list_tasks 查，查完就继续安排未完成的任务
- **长任务分批推进**：如果任务量很大（如写长篇小说），每轮对话推进一个阶段，做完后提示用户"发'继续'进入下一阶段"
- **收尾时预告下一步**：收尾总结里要说"已完成 X，下一步可以做 Y，发'继续'我就开始"

### 9. 工具使用防退化（重要）
- **每轮回复前检查**：如果当前任务涉及文件操作、搜索、任务管理，必须调用对应工具
- **不要只说不做**：连续多轮纯文字回复会导致后续轮次工具调用能力退化
- **主动使用工具**：即使没有被明确要求，如果发现需要读取文件、搜索内容、创建任务，主动调用工具
- **工具列表提醒**：你拥有以下工具能力——文件读写(write_file/read_file/edit_file)、搜索(grep/glob)、任务管理(create_sub_task/submit_task_result/list_tasks)、团队管理(create_team_member/update_team_member)、TODO管理(create_todo_list/update_todo_status)、文件版本控制(list_file_versions/file_rollback)
"""

# ========== 通用角色模板（领域无关，按能力特征分类）==========
# 设计哲学：模板定义"能做什么"，领域定义"做什么"（通过 domain_hint/style_guide 注入）
# 参考文档：docs/智能体分级与通用模板设计.md
ROLE_TEMPLATES = {
    "creator": {
        "name": "创作者",
        "description": "产出原创内容（文本/代码/文档/故事等）。适合：小说作者、文案、报告撰稿、开发工程师",
        "tools": ["read_file", "write_file", "edit_file", "grep", "glob", "submit_task_result"],
        "allowed_paths_type": "output",  # 读写 agent_work/{id}/ + shared/ + tasks/{task_id}/output/
        "can_write": True,
        "system_prompt_template": """你是「{name}」，{role}。你是项目团队的一员，由主智能体调度。

## 你的能力
- 创作原创内容（{domain_hint}）
- 修改完善已有内容
- 按要求格式产出

## 工具使用建议
- 找参考资料 → 用 grep（按内容）或 glob（按文件名）
- 改大文件的几行 → 用 edit_file（省 token 且安全）
- 新建文件 / 大改重写 → 用 write_file
- 不要用 list_directory 逐层遍历找文件，用 glob 代替

## 工作流程
1. 读取任务 TASK.md 了解需求
2. 读取 input/ 下的参考资料（只读，不要写入）
3. 创作产出，写到 output/ 目录
4. 用 submit_task_result 提交结果

## 原则
- 内容原创，不抄袭
- 遵循 {style_guide}
- 不确定的细节主动说明，不编造
- 如需反馈或澄清，在回复里写「@主智能体」""",
    },
    "reviewer": {
        "name": "审阅者",
        "description": "只读 + 提反馈意见（不修改原作）。适合：试读读者、编辑审稿、Code Review、质量检验",
        "tools": ["read_file", "grep", "glob", "submit_task_result"],
        "allowed_paths_type": "readonly",  # 只读
        "can_write": False,
        "system_prompt_template": """你是「{name}」，{role}。你是项目团队的审阅者，由主智能体调度。

## 你的能力
- 阅读内容并给出专业反馈
- 从{style_guide}视角发现问题
- 不修改原作，只提建议

## 工具使用建议
- 找特定内容 → 用 grep（按内容）或 glob（按文件名）
- 读文件 → 用 read_file，指定具体路径
- 你没有写文件的权限，反馈通过 submit_task_result 提交

## 工作流程
1. 读取任务 TASK.md 了解审阅要求
2. 读取 input/ 下待审阅的内容
3. 从{style_guide}角度给出审阅意见：
   - 具体问题（引用原文位置）
   - 改进建议（可操作，不空泛）
   - 亮点（值得肯定的地方）
4. 用 submit_task_result 提交审阅报告

## 原则
- 只读，不修改原作
- 反馈具体，引用原文位置
- 建议可操作，不空泛
- 客观公正，先肯定亮点再提问题""",
    },
    "analyst": {
        "name": "分析者",
        "description": "分析数据/资料，产出分析报告。适合：数据分析、市场调研、竞品分析、学术研究",
        "tools": ["read_file", "write_file", "edit_file", "grep", "glob", "submit_task_result"],
        "allowed_paths_type": "analysis",  # 只读输入 + 写 output
        "can_write": True,
        "system_prompt_template": """你是「{name}」，{role}。你是项目团队的分析者，由主智能体调度。

## 你的能力
- 分析{domain_hint}并给出结论
- 产出结构化的分析报告
- 基于证据，不臆测

## 工具使用建议
- 找数据/资料 → 用 grep（按内容）或 glob（按文件名）
- 分析报告写到 output/ 目录
- 改报告用 edit_file，新建用 write_file

## 工作流程
1. 读取任务 TASK.md 了解分析目标
2. 读取 input/ 下的原始数据/资料（只读）
3. 分析并产出报告：
   - 明确分析方法和数据来源
   - 给出具体结论（有数据支撑）
   - 标注不确定性
4. 写到 output/，用 submit_task_result 提交

## 原则
- 基于证据，不臆测
- 结论明确，有数据支撑
- 标注数据来源和分析方法
- 不确定的地方明确说明""",
    },
    "worker": {
        "name": "执行者",
        "description": "通用执行，不限定具体能力。适合：翻译、校对、格式转换、文件整理、测试执行",
        "tools": ["list_directory", "read_file", "write_file", "create_directory", "grep", "glob", "edit_file", "submit_task_result"],
        "allowed_paths_type": "output",  # 同 creator
        "can_write": True,
        "system_prompt_template": """你是「{name}」，{role}。你是项目团队的执行者，由主智能体调度。

## 你的能力
- 执行{domain_hint}相关任务
- 灵活应对各类执行需求

## 工具使用建议
- 找文件 → 用 grep 或 glob
- 改文件 → 用 edit_file（小改）或 write_file（重写）
- 新建文件 → 用 write_file
- 不要用 list_directory 逐层遍历找文件，用 glob 代替

## 工作流程
1. 读取任务 TASK.md 了解任务详情
2. 读取 input/ 下的输入文件
3. 执行任务，产出写到 output/
4. 用 submit_task_result 提交结果

## 原则
- 严格按任务要求执行
- 遵循 {style_guide}
- 不确定的地方主动询问（@主智能体）
- 完成后清晰说明做了什么、结果在哪里""",
    },
    "coordinator": {
        "name": "协调者",
        "description": "组长，能派发任务给组员（仅复杂项目启用）。适合：开发组长、文档组长等",
        "tools": ["list_directory", "read_file", "write_file", "edit_file", "grep", "glob", "create_sub_task", "submit_task_result"],
        "allowed_paths_type": "group",  # 本组全部目录
        "can_write": True,
        "system_prompt_template": """你是「{name}」，{role}。你是项目团队的{domain_hint}组长（L1 协调者），由主智能体调度。

## 你的能力
- 管理本组（{domain_hint}）的任务执行
- 将大任务拆分成子任务，用 create_sub_task 创建 L2 执行者并派发
- 汇总 L2 执行者的产出，向主智能体汇报

## 工具使用建议
- 拆分任务 → 用 create_sub_task（自动创建 L2 执行者 + 任务文件夹 + 授权）
- 找资料 → 用 grep（按内容）或 glob（按文件名）
- 改文件 → 用 edit_file（小改）或 write_file（重写）
- 汇总结果 → 用 submit_task_result 向主智能体提交

## 工作流程
1. 接收主智能体分配的大任务，理解目标和验收标准
2. 拆分成多个子任务，用 create_sub_task 为每个子任务创建 L2 执行者
3. @每个 L2 执行者，告诉它具体要做什么（它只能看到你 @它时写的文本，看不到完整对话）
4. 等待 L2 执行者完成后汇报（它们会 @你）
5. 汇总所有 L2 执行者的产出，整理成最终结果
6. 用 submit_task_result 向主智能体汇报整体结果

## 原则
- 你是 L1 组长，L2 执行者归你管，不直接向主智能体汇报
- 拆分任务要明确，每个子任务有清晰交付物和验收标准
- L2 执行者间通过文件传递信息（写到 output/ → 下一个读 input/）
- 汇总要简洁，突出关键结果，不要把所有 L2 回复原样转发
- 只管理本组，不越界处理其他组的事务
- 遵循 {style_guide}""",
    },
}


def resolve_project_path(root_path: str, relative_path: str) -> str:
    """把相对路径解析为绝对路径，并确保在项目根目录内（防止路径穿越）。
    返回绝对路径，如果越权或路径非法返回 None。
    """
    if not root_path:
        return None
    # 防御：类型校验，避免非字符串路径（如 int）导致 TypeError
    if not isinstance(relative_path, str):
        return None
    # 防御：含 null 字符的路径非法（Windows 上会抛 ValueError）
    if "\x00" in relative_path:
        return None
    root = Path(root_path).resolve()
    # 处理相对路径
    try:
        if relative_path in (".", "", "./"):
            target = root
        else:
            target = (root / relative_path).resolve()
        # 检查是否在根目录内
        target.relative_to(root)
    except ValueError:
        return None  # 路径穿越
    except Exception:
        return None  # 其他异常（如非法字符、权限问题），统一拒绝
    return str(target)


def _update_agent_permissions_in_conv(conv_id: str, agent_id: str, allowed_paths: list):
    """辅助函数：更新对话/项目中智能体的权限配置"""
    if not conv_id:
        return
    convs = load_conversations()
    conv = next((c for c in convs if c["id"] == conv_id), None)
    if not conv:
        return
    if not conv.get("agents"):
        conv["agents"] = [dict(a) for a in load_agents()]
    for ca in conv["agents"]:
        if ca["id"] == agent_id:
            ca["allowed_paths"] = allowed_paths
            break
    else:
        # 如果项目中没有这个智能体，添加进去
        all_agents = load_agents()
        target = next((a for a in all_agents if a["id"] == agent_id), None)
        if target:
            conv["agents"].append({
                "id": target["id"],
                "name": target["name"],
                "role": target.get("role", ""),
                "avatar": target.get("avatar", "🤖"),
                "allowed_paths": allowed_paths
            })
    save_conversations(convs)


def _find_agent(agent_id_or_name: str, conv_id: str = ""):
    """根据id或名称查找智能体，返回 (agent, agent_id, agents_list, source) 或 (None, None, [], "")
    
    查找顺序：
    1. 先查项目级 conversations.json 的 agents（项目级，create_team_member 创建的都在这里）
    2. 没找到再查全局 data.json 的全局模板
    
    返回的 agents_list 是该智能体所在的列表（项目级或全局），方便调用方决定保存到哪里。
    source 标识来自 'project' 还是 'global'。
    
    重要：优先项目级是为了让 create_team_member 创建的项目级智能体也能被 create_task 找到，
    以及让 create_task 的权限改动只落到项目级而不污染全局模板。
    """
    # 1. 先查项目级
    if conv_id:
        convs = load_conversations()
        conv = next((c for c in convs if c["id"] == conv_id), None)
        if conv and conv.get("agents"):
            conv_agents = conv["agents"]
            # 按 id 精确匹配
            target = next((a for a in conv_agents if a["id"] == agent_id_or_name), None)
            if target:
                return target, target["id"], conv_agents, "project"
            # 按名称模糊匹配
            target = next((a for a in conv_agents if agent_id_or_name in a.get("name", "")), None)
            if target:
                return target, target["id"], conv_agents, "project"
    
    # 2. 没找到，回退到全局模板
    all_agents = load_agents()
    target = next((a for a in all_agents if a["id"] == agent_id_or_name), None)
    if target:
        return target, target["id"], all_agents, "global"
    target = next((a for a in all_agents if agent_id_or_name in a.get("name", "")), None)
    if target:
        return target, target["id"], all_agents, "global"
    return None, None, all_agents, "global"


def _add_allowed_path(agent: dict, abs_path: str, all_agents: list) -> bool:
    """给智能体添加一个允许路径，如果已经存在返回False，添加成功返回True"""
    if "allowed_paths" not in agent or not agent["allowed_paths"]:
        agent["allowed_paths"] = ["*"]
        return False
    if "*" in agent["allowed_paths"]:
        return False  # 已有全部权限
    if abs_path not in agent["allowed_paths"]:
        agent["allowed_paths"].append(abs_path)
        return True
    return False


def execute_tool(tool_name: str, arguments: dict, root_path: str, agent_id: str = "main", conv_id: str = "", agent: dict = None, default_config_id: str = "") -> str:
    """执行工具调用，返回结果文本（用于返回给 LLM）
    agent_id: 当前调用工具的智能体id
    conv_id: 当前对话/项目id，用于更新项目内的智能体权限
    agent: 当前调用工具的智能体完整对象（Phase 3: invoke_sub_agent 需要）
    default_config_id: 默认 API 配置 ID（Phase 3: invoke_sub_agent 需要）
    """
    if not root_path:
        return "错误：当前项目没有设置工作目录，请先选择项目文件夹。"
    
    root = Path(root_path).resolve()
    
    # ========== 主智能体专用的管理工具 ==========
    # main_only_tools 已在模块级定义（见上方 TOOL_DEFINITIONS 之后）
    if tool_name in MAIN_ONLY_TOOLS:
        if agent_id != "main":
            return f"错误：只有主智能体（项目经理）可以使用 {tool_name} 工具。"
        
        # 元团队 main 的工具限制：禁止创建项目团队成员和 TODO 清单
        # 元团队的工作是产出 team_blueprint.json，不是直接执行项目
        if conv_id and tool_name in ("create_team_member", "create_todo_list", "update_todo_status"):
            _mt_convs = load_conversations()
            _mt_conv = next((c for c in _mt_convs if c["id"] == conv_id), None)
            if _mt_conv and _mt_conv.get("is_meta_team"):
                return (
                    f"❌ 元团队主智能体不能使用 {tool_name}。"
                    f"你的工作是调度元团队四成员协作，产出 deliverables/team_blueprint.json 蓝图文件。"
                    f"蓝图里描述的团队成员只存在于 JSON 文件中，不需要实际创建。"
                )
        
        if tool_name == "init_project_structure":
            try:
                # 创建完整的标准目录结构
                dirs_to_create = [
                    ".agent/tasks",      # 任务文件夹
                    "shared",            # 共享文件区
                    "agent_work",        # 智能体私有工作区
                    "deliverables",      # 最终交付物
                ]
                created = []
                for d in dirs_to_create:
                    (root / d).mkdir(parents=True, exist_ok=True)
                    created.append("📁 " + d + "/")
                
                # 为内置的两个助手自动创建工作区（只更新当前项目配置，不修改全局模板）
                shared_abs = str((root / "shared").resolve())
                tasks_dir = root / ".agent" / "tasks"
                tasks_abs = str(tasks_dir.resolve())
                workspaces_created = []
                
                # 为项目里所有非 main 智能体建工作区（init_project_structure 工具）
                # 空团队模式下新项目通常只有 main，这里对已有成员兜底
                conv_agents = []
                if conv_id:
                    convs = load_conversations()
                    conv_obj = next((c for c in convs if c["id"] == conv_id), None)
                    if conv_obj:
                        conv_agents = conv_obj.get("agents", [])
                for target in conv_agents:
                    if target.get("id") == "main":
                        continue
                    target_id = target.get("id")
                    if not target_id:
                        continue
                    work_dir = root / "agent_work" / target_id
                    work_dir.mkdir(parents=True, exist_ok=True)
                    work_abs = str(work_dir.resolve())
                    allowed = [work_abs, shared_abs, tasks_abs]
                    workspaces_created.append(f"  ✅ {target_id}: agent_work/{target_id}/")
                    _update_agent_permissions_in_conv(conv_id, target_id, allowed)
                
                result = "✅ 项目标准目录结构初始化完成：\n"
                result += "\n".join(created) + "\n\n"
                if workspaces_created:
                    result += "已自动为内置助手创建工作区：\n" + "\n".join(workspaces_created) + "\n\n"
                result += "【目录说明】\n"
                result += "- 📁 .agent/tasks/ ：任务文件夹，每个任务有独立的input/output，避免文件冲突\n"
                result += "- 📁 shared/ ：共享文件区，智能体之间交换非任务文件\n"
                result += "- 📁 agent_work/ ：智能体私有工作区，每个智能体只能访问自己的子目录\n"
                result += "- 📁 deliverables/ ：最终交付物目录，整理后的成果放这里\n\n"
                result += "提示：现在可以用 create_task 工具给子智能体分配任务了，系统会自动处理权限！"
                return result
            except Exception as e:
                return f"❌ 初始化项目结构失败：{str(e)}"
        
        elif tool_name == "create_agent_workspace":
            target_aid = arguments.get("agent_id", "")
            if not target_aid:
                return "错误：需要提供 agent_id 参数。"
            
            # 查找全局智能体获取名称（不修改全局模板）
            all_agents_global = load_agents()
            target_global = next((a for a in all_agents_global if a["id"] == target_aid), None)
            if not target_global:
                return f"错误：找不到智能体 '{target_aid}'。当前可用智能体：" + ", ".join([a["name"] for a in all_agents_global])
            
            try:
                work_dir = root / "agent_work" / target_aid
                work_dir.mkdir(parents=True, exist_ok=True)
                work_abs = str(work_dir.resolve())
                shared_abs = str((root / "shared").resolve())
                
                # 确保 .agent/tasks 目录存在（为后续任务授权做准备）
                (root / ".agent" / "tasks").mkdir(parents=True, exist_ok=True)
                
                # 设置权限：自己的工作目录 + shared（任务目录由 create_task 按需授权）
                allowed = [work_abs, shared_abs]
                # 只更新当前项目的智能体配置，不修改全局data.json
                _update_agent_permissions_in_conv(conv_id, target_aid, allowed)
                
                return f"✅ 已为「{target_global['name']}」创建工作区：agent_work/{target_aid}/\n权限：\n- 读写：agent_work/{target_aid}/（私有工作区）\n- 读写：shared/（共享区）\n- 读写：.agent/tasks/（任务文件夹）"
            except Exception as e:
                return f"❌ 创建工作区失败：{str(e)}"
        
        elif tool_name == "create_task":
            target_aid = arguments.get("agent_id", "")
            task_type = arguments.get("task_type", "general")
            description = arguments.get("description", "")
            input_files = arguments.get("input_files", []) or []
            extra_grant_paths = arguments.get("extra_grant_paths", []) or []
            
            if not target_aid or not description:
                return "错误：需要提供 agent_id 和 description 参数。"
            
            target_agent, target_aid, all_agents, source = _find_agent(target_aid, conv_id)
            if not target_agent:
                return f"错误：找不到智能体 '{target_aid}'。"

            template = TASK_TYPE_TEMPLATES.get(task_type, TASK_TYPE_TEMPLATES["general"])

            try:
                import time as time_mod
                task_id = f"task_{int(time_mod.time())}_{uuid.uuid4().hex[:6]}"

                # 创建任务目录结构
                task_dir = root / ".agent" / "tasks" / task_id
                input_dir = task_dir / "input"
                output_dir = task_dir / "output"
                input_dir.mkdir(parents=True, exist_ok=True)
                output_dir.mkdir(parents=True, exist_ok=True)

                task_dir_abs = str(task_dir.resolve())
                input_dir_abs = str(input_dir.resolve())
                output_dir_abs = str(output_dir.resolve())

                # 保存任务元数据
                task_meta = {
                    "id": task_id,
                    "agent_id": target_aid,
                    "type": task_type,
                    "type_name": template["name"],
                    "description": description,
                    "status": "pending",
                    "created_at": time_mod.strftime("%Y-%m-%d %H:%M:%S"),
                    "input_files": input_files,
                    "result_files": []
                }
                import json as json_mod
                with open(task_dir / "meta.json", "w", encoding="utf-8") as f:
                    json_mod.dump(task_meta, f, ensure_ascii=False, indent=2)

                # 确保智能体有工作区
                work_dir = root / "agent_work" / target_aid
                work_dir.mkdir(parents=True, exist_ok=True)
                work_abs = str(work_dir.resolve())
                shared_abs = str((root / "shared").resolve())
                # 权限最小化：只授权当前任务目录，不授权整个 tasks 根目录
                # （避免子智能体读写其他任务的 input/output）
                task_dir_abs = str(task_dir.resolve())
                input_dir_abs = str(input_dir.resolve())
                output_dir_abs = str(output_dir.resolve())
                
                # 基础权限：私有工作区 + 共享区 + 当前任务目录（含 input 只读 + output 读写）
                allowed = [work_abs, shared_abs, task_dir_abs]
                
                # 根据任务模板添加权限
                granted_paths = []
                for p in template.get("grant_paths", []):
                    p_abs = resolve_project_path(root_path, p)
                    if p_abs:
                        allowed.append(p_abs)
                        granted_paths.append(p)
                
                # 添加输入文件的读取权限
                for f in input_files:
                    f_abs = resolve_project_path(root_path, f)
                    if f_abs:
                        # 授予文件所在目录的权限（让智能体能列目录读文件）
                        parent = str(Path(f_abs).parent.resolve())
                        if parent not in allowed:
                            allowed.append(parent)
                        granted_paths.append(f)
                
                # 添加额外授权路径
                for p in extra_grant_paths:
                    p_abs = resolve_project_path(root_path, p)
                    if p_abs:
                        allowed.append(p_abs)
                        granted_paths.append(p)
                
                # 去重
                allowed = list(dict.fromkeys(allowed))

                # 更新智能体权限
                # 重要：只写项目级 conversations.json，不写全局 data.json
                # 避免污染全局模板，影响后续新建项目（这是之前的核心 bug）
                target_agent["allowed_paths"] = allowed
                # 统一只更新项目级配置，不动全局模板
                if conv_id:
                    _update_agent_permissions_in_conv(conv_id, target_aid, allowed)
                
                # 准备给智能体的任务说明文件
                task_instruction = f"""# 任务：{template['name']}

## 任务描述
{description}

## 你的权限
- 私有工作区：`agent_work/{target_aid}/` （你的临时文件可以放这里）
- 共享区：`shared/`
- 任务输入目录：`.agent/tasks/{task_id}/input/` （这里有需要处理的文件，请读取）
- 任务输出目录：`.agent/tasks/{task_id}/output/` （请把结果写到这里）
"""
                if input_files:
                    task_instruction += "\n## 需要处理的文件\n"
                    for f in input_files:
                        task_instruction += f"- `{f}`\n"
                task_instruction += "\n## 完成任务后\n请使用 submit_task_result 工具提交你的结果，说明你做了什么，以及结果文件的位置。\n"
                
                with open(task_dir / "TASK.md", "w", encoding="utf-8") as f:
                    f.write(task_instruction)
                
                result = f"✅ 已创建任务 [{template['name']}]\n"
                result += f"📋 任务ID: {task_id}\n"
                result += f"👤 分配给: {target_agent['name']}\n"
                result += f"📝 任务描述: {description}\n\n"
                result += "📂 任务文件夹：\n"
                result += f"- 输入目录: .agent/tasks/{task_id}/input/\n"
                result += f"- 输出目录: .agent/tasks/{task_id}/output/\n"
                if granted_paths:
                    result += "\n🔓 已授予路径权限：\n"
                    for p in granted_paths:
                        result += f"- {p}\n"
                result += f"\n💡 现在你可以 @{target_agent['name']} 并告诉它任务详情了。"
                result += f"\n提示：任务说明文件已生成在 .agent/tasks/{task_id}/TASK.md，你可以直接告诉它读取这个文件了解任务。"
                return result
            except Exception as e:
                return f"❌ 创建任务失败：{str(e)}"
        
        elif tool_name == "grant_path_access":
            target_aid = arguments.get("agent_id", "")
            grant_path = arguments.get("path", "")
            if not target_aid or not grant_path:
                return "错误：需要提供 agent_id 和 path 参数。"
            
            target_agent, target_aid, all_agents, source = _find_agent(target_aid, conv_id)
            if not target_agent:
                return f"错误：找不到智能体 '{target_aid}'。"

            try:
                grant_abs = resolve_project_path(root_path, grant_path)
                if grant_abs is None:
                    return f"错误：路径 '{grant_path}' 超出项目范围。"

                if "allowed_paths" not in target_agent:
                    target_agent["allowed_paths"] = ["*"]

                if "*" in target_agent["allowed_paths"]:
                    return f"「{target_agent['name']}」当前拥有全部权限，无需额外授权。"

                added = _add_allowed_path(target_agent, grant_abs, all_agents)
                if added:
                    # 只写项目级，不污染全局模板
                    if conv_id:
                        _update_agent_permissions_in_conv(conv_id, target_aid, target_agent["allowed_paths"])
                    return f"✅ 已授予「{target_agent['name']}」路径访问权限：{grant_path}"
                else:
                    return f"「{target_agent['name']}」已经拥有 {grant_path} 的访问权限。"
            except Exception as e:
                return f"❌ 授权失败：{str(e)}"
        
        elif tool_name == "revoke_path_access":
            target_aid = arguments.get("agent_id", "")
            revoke_path = arguments.get("path", "")
            if not target_aid or not revoke_path:
                return "错误：需要提供 agent_id 和 path 参数。"
            
            target_agent, target_aid, all_agents, source = _find_agent(target_aid, conv_id)
            if not target_agent:
                return f"错误：找不到智能体 '{target_aid}'。"

            try:
                revoke_abs = resolve_project_path(root_path, revoke_path)
                if revoke_abs is None:
                    return f"错误：路径 '{revoke_path}' 超出项目范围。"

                if "allowed_paths" not in target_agent or "*" in target_agent.get("allowed_paths", []):
                    return f"「{target_agent['name']}」当前拥有全部权限，无法单独撤销路径权限。"

                if revoke_abs in target_agent["allowed_paths"]:
                    target_agent["allowed_paths"].remove(revoke_abs)
                    # 只写项目级，不污染全局模板
                    if conv_id:
                        _update_agent_permissions_in_conv(conv_id, target_aid, target_agent["allowed_paths"])
                    return f"✅ 已撤销「{target_agent['name']}」对 {revoke_path} 的访问权限。"
                else:
                    return f"「{target_agent['name']}」本来就没有 {revoke_path} 的访问权限。"
            except Exception as e:
                return f"❌ 撤销权限失败：{str(e)}"
        
        # ========== 团队管理工具 ==========
        elif tool_name == "list_team_members":
            try:
                # 优先返回当前项目的智能体配置
                all_agents = load_agents()
                conv_agents = []
                if conv_id:
                    convs = load_conversations()
                    conv = next((c for c in convs if c["id"] == conv_id), None)
                    if conv and conv.get("agents"):
                        conv_agents = conv["agents"]
                team = conv_agents if conv_agents else all_agents
                result = f"📋 当前团队共有 {len(team)} 名成员：\n\n"
                for a in team:
                    perms = a.get("allowed_paths", [])
                    if "*" in perms:
                        perm_desc = "全部权限"
                    else:
                        perm_desc = f"{len(perms)}个路径"
                    result += f"- **{a.get('name', '未命名')}** (ID: {a['id']})\n"
                    result += f"  角色：{a.get('role', '未设置')}\n"
                    result += f"  权限：{perm_desc}\n\n"
                return result
            except Exception as e:
                return f"❌ 获取团队列表失败：{str(e)}"
        
        elif tool_name == "create_team_member":
            name = arguments.get("name", "").strip()
            role = arguments.get("role", "").strip()
            system_prompt = arguments.get("system_prompt", "").strip()
            template = arguments.get("template", "").strip()
            domain_hint = arguments.get("domain_hint", "").strip() or "相关内容"
            style_guide = arguments.get("style_guide", "").strip() or "通用规范"
            avatar = arguments.get("avatar", "🤖")
            # Phase 3: 技能绑定 + 子代理调用权限
            skills = arguments.get("skills", []) or []
            can_invoke_sub = arguments.get("can_invoke_sub_agent", False)
            
            # 参数校验：template 和 system_prompt 二选一
            if not name or not role:
                return "错误：name、role 都是必填参数。"
            if not template and not system_prompt:
                return "错误：必须提供 template 或 system_prompt 之一。\n推荐用 template（如 creator/reviewer/analyst/worker），系统会自动生成高质量提示词。"
            if template and template not in ROLE_TEMPLATES:
                available = ", ".join([f'{k}({v["name"]})' for k, v in ROLE_TEMPLATES.items()])
                return f"错误：未知模板 '{template}'。可用的模板：{available}"
            
            if not conv_id:
                return "错误：找不到当前项目，无法创建团队成员。"
            
            try:
                convs = load_conversations()
                conv = next((c for c in convs if c["id"] == conv_id), None)
                if not conv:
                    return "错误：找不到当前项目。"
                
                # 检查名称是否重复（只在当前项目内检查）
                if not conv.get("agents"):
                    conv["agents"] = []
                if any(a["name"] == name for a in conv["agents"]):
                    return f"错误：当前项目已存在名为「{name}」的智能体，请换一个名字。"
                
                # 检查职责（role）是否高度重复，提示主智能体复用现有成员
                existing_agents = conv.get("agents", [])
                if existing_agents:
                    role_lower = role.lower()
                    similar = []
                    for a in existing_agents:
                        a_role = (a.get("role") or "").lower()
                        a_name = a.get("name", "")
                        if a_role and (a_role == role_lower or a_role in role_lower or role_lower in a_role):
                            similar.append(f"「{a_name}」(角色：{a.get('role')})")
                    if similar:
                        return (
                            f"⚠️ 提示：当前项目已有职责相似的成员：{', '.join(similar)}\n\n"
                            f"建议：先检查上述成员是否能胜任当前任务（调用 list_team_members 查看详情），"
                            f"如果可以就直接 @它 调度，避免重复造人。\n\n"
                            f"如果确认需要创建新角色（职责领域不同），请调整 role 字段使其与现有成员区分开，"
                            f"比如用更具体的角色名（如「前端开发」「后端开发」而不是笼统的「开发工程师」），然后重新调用 create_team_member。"
                        )
                
                # 创建智能体（只写入当前项目，不污染全局 data.json）
                new_agent_id = "agent_" + uuid.uuid4().hex[:8]
                
                # 自动创建私有工作区并授权
                work_dir = root / "agent_work" / new_agent_id
                work_dir.mkdir(parents=True, exist_ok=True)
                shared_dir = root / "shared"
                shared_dir.mkdir(parents=True, exist_ok=True)
                (root / ".agent" / "tasks").mkdir(parents=True, exist_ok=True)
                
                work_abs = str(work_dir.resolve())
                shared_abs = str(shared_dir.resolve())
                allowed_paths = [work_abs, shared_abs]  # 任务目录由 create_task 按需授权
                
                # 根据是否用模板，生成不同的 system_prompt
                if template:
                    # 用模板：套用模板的 prompt 骨架，注入领域参数
                    tpl = ROLE_TEMPLATES[template]
                    final_system_prompt = tpl["system_prompt_template"].format(
                        name=name,
                        role=role,
                        domain_hint=domain_hint,
                        style_guide=style_guide,
                    ) + CORE_RULES  # 注入通用核心规则
                    # 追加权限说明
                    can_write = tpl["can_write"]
                    perm_desc = "读写" if can_write else "只读"
                    final_system_prompt += f"\n\n## 你的权限范围\n- ✅ {perm_desc}：agent_work/{new_agent_id}/（你的私有工作区）\n- ✅ {perm_desc}：shared/（共享区）\n- ✅ {perm_desc}：.agent/tasks/（任务文件夹）\n- ❌ 禁止：调用管理工具（create_task/create_team_member 等，只有主智能体能用）\n- ❌ 禁止：访问其他智能体的私有工作区"
                    tpl_name = tpl["name"]
                    tpl_tools_count = len(tpl["tools"])
                else:
                    # 完全自定义：保留原 member_handbook 逻辑
                    member_handbook = f"""你是「{name}」，角色：{role}。你是项目团队的一员，由主智能体调度。

## 你的工具（只能用这些）
- list_directory：列出文件夹内容
- read_file：读取文件内容
- write_file：写入/创建文件（自动创建目录）
- create_directory：创建文件夹
- **grep**：⭐ 在文件内容里搜正则，定位代码/文本，比 list_directory 遍历快得多
- **glob**：⭐ 按文件名模式快速找文件，如 `**/*.py`
- **edit_file**：⭐ 用 SEARCH/REPLACE 精确改文件一部分，比 write_file 重写省 token
- submit_task_result：提交任务结果

## 工具使用建议
- 找代码/文本 → 用 grep（按内容）或 glob（按文件名）
- 改大文件的几行 → 用 edit_file（省 token 且安全）
- 新建文件 / 大改重写 → 用 write_file
- 不要用 list_directory 逐层遍历找文件，用 glob 代替

## 你的权限范围
- ✅ 读写：agent_work/{new_agent_id}/（你的私有工作区）
- ✅ 读写：shared/（共享区）
- ✅ 读写：.agent/tasks/（任务文件夹，含你被分配的任务）
- ❌ 禁止：调用 create_task / create_team_member / list_team_members 等管理工具（只有主智能体能用）
- ❌ 禁止：访问其他智能体的私有工作区

## 工作流程
1. 收到任务后，主智能体会告诉你任务文件夹路径（如 .agent/tasks/task_xxx/）
2. 先读该任务文件夹下的 TASK.md 了解任务详情
3. 读取 input/ 目录下的输入文件（只读，不要写入）
4. 处理任务，把产出写到该任务文件夹的 output/ 目录
5. 完成后用 submit_task_result 提交结果
6. 如需向主智能体汇报，在回复里写「@主智能体」

## 你的职责
"""
                    final_system_prompt = member_handbook + system_prompt + CORE_RULES  # 注入通用核心规则
                    tpl_name = "自定义"
                    tpl_tools_count = 8

                new_agent = {
                    "id": new_agent_id,
                    "name": name,
                    "role": role,
                    "avatar": avatar,
                    "system_prompt": final_system_prompt,
                    "allowed_paths": allowed_paths,
                    "model_config": None,
                    "can_use_tools": True,
                    "template": template if template else "worker",  # 记录模板名（供工具过滤用）
                    "domain_hint": domain_hint,
                    "style_guide": style_guide,
                    # Phase 3: 技能绑定 + 子代理调用权限
                    "enabled_skills": skills,
                    "can_invoke_sub_agent": can_invoke_sub,
                }
                
                # 只添加到当前项目的 agents 数组
                conv["agents"].append(new_agent)
                save_conversations(convs)
                
                # 如果项目属于某个团队，同步添加到团队
                team_id = conv.get("team_id")
                if team_id:
                    teams = load_teams()
                    team = next((t for t in teams if t["id"] == team_id), None)
                    if team:
                        if not team.get("agents"):
                            team["agents"] = []
                        team["agents"].append(dict(new_agent))
                        team["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        save_teams(teams)
                
                result = f"✅ 已创建新团队成员「{name}」\n"
                result += f"🆔 ID: {new_agent_id}\n"
                result += f"👤 角色: {role}\n"
                if template:
                    result += f"📋 模板: {template}（{tpl_name}，{tpl_tools_count} 个工具）\n"
                    result += f"🎯 领域: {domain_hint}\n"
                    result += f"🎨 风格: {style_guide}\n"
                result += f"📁 私有工作区: agent_work/{new_agent_id}/\n"
                result += f"🔐 权限: 私有工作区 + shared/ + .agent/tasks/\n"
                if skills:
                    result += f"🧩 已绑定技能: {', '.join(skills)}\n"
                if can_invoke_sub:
                    result += f"🔧 子代理调用: 已开启（可使用 invoke_sub_agent 工具）\n"
                result += f"\n💡 现在你可以通过 @{name} 来调度它协作了。"
                return result
            except Exception as e:
                return f"❌ 创建团队成员失败：{str(e)}"
        
        elif tool_name == "update_team_member":
            target_aid = arguments.get("agent_id", "")
            new_name = arguments.get("name")
            new_role = arguments.get("role")
            new_prompt = arguments.get("system_prompt")
            new_avatar = arguments.get("avatar")
            
            if not target_aid:
                return "错误：需要提供 agent_id 参数。"
            
            if not conv_id:
                return "错误：找不到当前项目。"
            
            try:
                convs = load_conversations()
                conv = next((c for c in convs if c["id"] == conv_id), None)
                if not conv or not conv.get("agents"):
                    return "错误：当前项目没有智能体。"
                
                # 只在当前项目内查找
                target_agent = next((a for a in conv["agents"] if a["id"] == target_aid or a["name"] == target_aid), None)
                if not target_agent:
                    return f"错误：在当前项目找不到智能体 '{target_aid}'。"
                
                if target_agent["id"] == "main":
                    return "错误：不能修改主智能体自身。"
                
                changed = []
                if new_name:
                    target_agent["name"] = new_name
                    changed.append("名称")
                if new_role:
                    target_agent["role"] = new_role
                    changed.append("角色")
                if new_prompt:
                    target_agent["system_prompt"] = new_prompt
                    changed.append("系统提示词")
                if new_avatar:
                    target_agent["avatar"] = new_avatar
                    changed.append("头像")
                
                if not changed:
                    return "没有提供任何修改字段。"
                
                # 只保存当前项目，不动全局 data.json
                save_conversations(convs)
                
                result = f"✅ 已更新「{target_agent['name']}」的：{', '.join(changed)}"
                return result
            except Exception as e:
                return f"❌ 更新团队成员失败：{str(e)}"
        
        elif tool_name == "remove_team_member":
            target_aid = arguments.get("agent_id", "")
            if not target_aid:
                return "错误：需要提供 agent_id 参数。"
            
            if not conv_id:
                return "错误：找不到当前项目。"
            
            try:
                convs = load_conversations()
                conv = next((c for c in convs if c["id"] == conv_id), None)
                if not conv or not conv.get("agents"):
                    return "错误：当前项目没有智能体。"
                
                # 只在当前项目内查找
                target_agent = next((a for a in conv["agents"] if a["id"] == target_aid or a["name"] == target_aid), None)
                if not target_agent:
                    return f"错误：在当前项目找不到智能体 '{target_aid}'。"
                
                if target_agent["id"] == "main":
                    return "错误：不能移除主智能体。"
                
                agent_name = target_agent["name"]
                # 只从当前项目移除，不动全局 data.json
                conv["agents"] = [a for a in conv["agents"] if a["id"] != target_agent["id"]]
                save_conversations(convs)
                
                result = f"✅ 已从团队中移除「{agent_name}」\n"
                result += f"📁 其私有工作区 agent_work/{target_agent['id']}/ 和已产出的文件会保留。"
                return result
            except Exception as e:
                return f"❌ 移除团队成员失败：{str(e)}"
    
    # ========== 阶段4：协调者(coordinator)专用工具 ==========
    if tool_name == "create_sub_task":
        # 仅 coordinator 模板的智能体可用（L1 组长派发给 L2 执行者）
        coordinator_agent, coord_aid, _, _ = _find_agent(agent_id, conv_id)
        if not coordinator_agent:
            return "错误：找不到当前智能体信息。"
        if coordinator_agent.get("template") != "coordinator":
            return "错误：只有协调者(coordinator)模板的智能体可以使用 create_sub_task 工具。"
        
        member_name = arguments.get("name", "").strip()
        member_role = arguments.get("role", "").strip()
        task_type = arguments.get("task_type", "general")
        description = arguments.get("description", "")
        input_files = arguments.get("input_files", []) or []
        style_guide = arguments.get("style_guide", "通用规范")
        
        if not member_name or not member_role or not description:
            return "错误：需要提供 name、role 和 description 参数。"
        
        template = TASK_TYPE_TEMPLATES.get(task_type, TASK_TYPE_TEMPLATES["general"])
        
        try:
            import time as time_mod
            import json as json_mod
            
            # 1. 创建 L2 执行者智能体（使用 worker 模板，受限工具集）
            new_agent_id = "agent_" + uuid.uuid4().hex[:8]
            worker_tpl = ROLE_TEMPLATES["worker"]
            coord_name = coordinator_agent.get("name", "组长")
            
            l2_prompt = worker_tpl["system_prompt_template"].format(
                name=member_name,
                role=member_role,
                domain_hint=member_role,
                style_guide=style_guide
            )
            # 追加 L2 层级说明：结果汇报给组长，不直接找主智能体
            l2_prompt += (
                f"\n\n## 你的层级（L2 执行者）\n"
                f"你由组长「{coord_name}」调度，不直接向主智能体汇报。\n"
                f"- 有问题 @{coord_name}（你的组长），不要 @主智能体\n"
                f"- 完成后用 submit_task_result 提交，结果会自动通知 {coord_name}\n"
                f"- 你的权限仅限本任务目录和自己的工作区，不要尝试访问其他目录"
            )
            
            # 2. 创建任务目录
            task_id = f"task_{int(time_mod.time())}_{uuid.uuid4().hex[:6]}"
            task_dir = root / ".agent" / "tasks" / task_id
            input_dir = task_dir / "input"
            output_dir = task_dir / "output"
            input_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)
            task_dir_abs = str(task_dir.resolve())
            
            # 3. 创建 L2 工作区
            work_dir = root / "agent_work" / new_agent_id
            work_dir.mkdir(parents=True, exist_ok=True)
            work_abs = str(work_dir.resolve())
            shared_abs = str((root / "shared").resolve())
            
            # 4. 权限：L2 执行者权限受限（本任务 + 自己工作区 + shared）
            # 权限最小化：只授权当前任务目录，不授权整个 tasks 根目录
            allowed = [work_abs, shared_abs, task_dir_abs]
            granted_paths = []
            for p in template.get("grant_paths", []):
                p_abs = resolve_project_path(root_path, p)
                if p_abs:
                    allowed.append(p_abs)
                    granted_paths.append(p)
            for f in input_files:
                f_abs = resolve_project_path(root_path, f)
                if f_abs:
                    parent = str(Path(f_abs).parent.resolve())
                    if parent not in allowed:
                        allowed.append(parent)
                    granted_paths.append(f)
            allowed = list(dict.fromkeys(allowed))
            
            # 5. 保存任务元数据（标记 level 和 parent）
            task_meta = {
                "id": task_id,
                "agent_id": new_agent_id,
                "type": task_type,
                "type_name": template["name"],
                "description": description,
                "status": "pending",
                "created_at": time_mod.strftime("%Y-%m-%d %H:%M:%S"),
                "input_files": input_files,
                "result_files": [],
                "level": 2,
                "parent_agent_id": coord_aid
            }
            with open(task_dir / "meta.json", "w", encoding="utf-8") as f:
                json_mod.dump(task_meta, f, ensure_ascii=False, indent=2)
            
            # 6. 写 TASK.md
            task_instruction = f"""# 子任务：{template['name']}

## 任务描述
{description}

## 你的层级
你是 L2 执行者，由组长「{coord_name}」调度。完成后用 submit_task_result 提交，结果会通知组长。

## 你的权限
- 私有工作区：`agent_work/{new_agent_id}/`
- 共享区：`shared/`
- 任务输入目录：`.agent/tasks/{task_id}/input/`（只读）
- 任务输出目录：`.agent/tasks/{task_id}/output/`（请把结果写到这里）
"""
            if input_files:
                task_instruction += "\n## 需要处理的文件\n"
                for f in input_files:
                    task_instruction += f"- `{f}`\n"
            task_instruction += "\n## 完成后\n请使用 submit_task_result 工具提交结果，说明做了什么及结果文件位置。\n"
            with open(task_dir / "TASK.md", "w", encoding="utf-8") as f:
                f.write(task_instruction)
            
            # 7. 把 L2 执行者写入项目级 conversations.json
            new_l2_agent = {
                "id": new_agent_id,
                "name": member_name,
                "role": member_role,
                "avatar": "🔧",
                "system_prompt": l2_prompt,
                "allowed_paths": allowed,
                "model_config": coordinator_agent.get("model_config"),  # 继承组长的模型配置
                "can_use_tools": True,
                "template": "worker",
                "domain_hint": member_role,
                "style_guide": style_guide,
                "level": 2,
                "parent_agent_id": coord_aid
            }
            
            if conv_id:
                convs = load_conversations()
                conv = next((c for c in convs if c["id"] == conv_id), None)
                if conv:
                    if not conv.get("agents"):
                        conv["agents"] = []
                    conv["agents"].append(new_l2_agent)
                    save_conversations(convs)
            
            result = f"✅ 已创建 L2 执行者并派发子任务\n"
            result += f"👤 执行者：{member_name}（L2，ID：{new_agent_id}）\n"
            result += f"📋 任务ID：{task_id}\n"
            result += f"📝 任务：{description[:100]}\n"
            result += f"📂 任务文件夹：.agent/tasks/{task_id}/\n"
            if granted_paths:
                result += "🔓 已授权路径：\n"
                for p in granted_paths:
                    result += f"- {p}\n"
            result += f"\n💡 现在你可以 @{member_name} 并告诉它具体要做什么了。"
            result += f"\n提示：任务说明已写到 .agent/tasks/{task_id}/TASK.md，可让它读取了解详情。"
            return result
        except Exception as e:
            return f"❌ 创建子任务失败：{str(e)}"
    
    # ========== 子智能体可用的工具 ==========
    if tool_name == "submit_task_result":
        result_files = arguments.get("result_files", []) or []
        summary = arguments.get("summary", "")
        submitted_task_id = arguments.get("task_id", "")
        
        try:
            # 找到当前智能体最新的任务（简单实现：找tasks目录下meta.json中agent_id匹配的最新任务）
            tasks_dir = root / ".agent" / "tasks"
            task_dir = None
            task_meta = None
            import json as json_mod
            
            # 防幻觉：如果传入了 task_id，严格校验该任务存在且属于当前智能体
            if submitted_task_id:
                candidate_dir = tasks_dir / submitted_task_id
                if not candidate_dir.exists():
                    return (f"❌ 提交失败：找不到匹配的任务 {submitted_task_id}。\n"
                            "该任务 ID 不存在于 .agent/tasks/ 目录中。\n"
                            "请确认 task_id 是 create_task 工具真实返回的值，不要编造任务 ID。")
                meta_file = candidate_dir / "meta.json"
                if not meta_file.exists():
                    return f"❌ 提交失败：任务 {submitted_task_id} 缺少 meta.json，可能不是合法任务。"
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        meta = json_mod.load(f)
                except Exception as e:
                    return f"❌ 提交失败：读取任务元数据出错：{str(e)}"
                if meta.get("agent_id") != agent_id:
                    return (f"❌ 提交失败：任务 {submitted_task_id} 不属于你（agent_id={agent_id}）。\n"
                            f"该任务属于 {meta.get('agent_id', '未知')}，你不能提交别人的任务。")
                if meta.get("status") != "pending":
                    return (f"❌ 提交失败：任务 {submitted_task_id} 当前状态为「{meta.get('status', '未知')}」，不是 pending 状态。\n"
                            "可能该任务已提交过，不能重复提交。")
                task_dir = candidate_dir
                task_meta = meta
            
            # 没传 task_id 时，保持原有 fallback 行为（向后兼容）
            if not task_meta and tasks_dir.exists():
                task_dirs = sorted([d for d in tasks_dir.iterdir() if d.is_dir()], 
                                  key=lambda x: x.stat().st_mtime, reverse=True)
                for d in task_dirs:
                    meta_file = d / "meta.json"
                    if meta_file.exists():
                        try:
                            with open(meta_file, "r", encoding="utf-8") as f:
                                meta = json_mod.load(f)
                            if meta.get("agent_id") == agent_id and meta.get("status") == "pending":
                                task_dir = d
                                task_meta = meta
                                break
                        except Exception:
                            continue
            
            # 防幻觉：找不到匹配任务时明确报错，不要静默"成功"
            if not task_meta or not task_dir:
                return ("❌ 提交失败：找不到属于你的待处理任务（pending 状态）。\n"
                        "可能原因：\n"
                        "1. 任务已被你提交过（不能重复提交）\n"
                        "2. 任务由其他智能体持有\n"
                        "3. 主智能体还没用 create_task 给你分配任务\n"
                        "请确认任务已正确分配给你，或 @主智能体/组长 请求分配任务。")
            
            # 防幻觉：校验 result_files 真实性
            response = f"✅ 任务结果已提交\n\n"
            if summary:
                response += f"📝 结果摘要：\n{summary}\n\n"
            
            if result_files:
                response += "📄 结果文件：\n"
                valid_files = []
                invalid_files = []
                for f in result_files:
                    f_abs = resolve_project_path(root_path, f)
                    if f_abs and Path(f_abs).exists():
                        file_size = Path(f_abs).stat().st_size
                        valid_files.append(f)
                        response += f"- {f}（{file_size} 字节）✓\n"
                    else:
                        invalid_files.append(f)
                        response += f"- {f} ⚠️ 文件不存在或无权限\n"
                
                # 防幻觉：如果声明的文件全部不存在，拒绝提交（要求重做）
                if result_files and not valid_files:
                    return ("❌ 提交被拒绝：你声明的结果文件全部不存在。\n"
                            f"声明的文件：{result_files}\n"
                            "请先用 write_file 真实写入文件，再提交结果。不要提交未真实产出的文件路径。")
                
                if invalid_files:
                    response += f"\n⚠️ 警告：{len(invalid_files)} 个文件不存在，已从结果中剔除。\n"
                
                if task_meta and task_dir:
                    task_meta["result_files"] = valid_files
                    task_meta["status"] = "completed"
                    task_meta["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    with open(task_dir / "meta.json", "w", encoding="utf-8") as f:
                        json_mod.dump(task_meta, f, ensure_ascii=False, indent=2)
                    response += f"\n📂 任务文件夹：.agent/tasks/{task_meta['id']}/\n"
                    response += f"🔍 校验：{len(valid_files)} 个文件真实存在，任务标记为已完成。\n"
            else:
                # 没声明 result_files 也能提交（有些任务只需文字总结）
                if task_meta and task_dir:
                    task_meta["result_files"] = []
                    task_meta["status"] = "completed"
                    task_meta["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    with open(task_dir / "meta.json", "w", encoding="utf-8") as f:
                        json_mod.dump(task_meta, f, ensure_ascii=False, indent=2)
                    response += f"\n📂 任务文件夹：.agent/tasks/{task_meta['id']}/\n"
            
            # P1-7: 更新智能体性能统计
            try:
                conversations_stats = load_conversations()
                conv_stats = next((c for c in conversations_stats if c["id"] == conv_id), None)
                if conv_stats:
                    stats_agents = conv_stats.get("agents", [])
                    stats_agent = next((a for a in stats_agents if a["id"] == agent_id), None)
                    if stats_agent:
                        if "stats" not in stats_agent:
                            stats_agent["stats"] = {
                                "total_tasks": 0, "completed_tasks": 0, "failed_tasks": 0,
                                "avg_duration_sec": 0, "last_active_at": None
                            }
                        stats_agent["stats"]["completed_tasks"] = stats_agent["stats"].get("completed_tasks", 0) + 1
                        stats_agent["stats"]["total_tasks"] = stats_agent["stats"].get("total_tasks", 0) + 1
                        stats_agent["stats"]["last_active_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        # 计算平均耗时
                        if task_meta and task_meta.get("created_at"):
                            try:
                                from datetime import datetime as _dt
                                created = _dt.strptime(task_meta["created_at"], "%Y-%m-%d %H:%M:%S")
                                completed = _dt.strptime(task_meta["completed_at"], "%Y-%m-%d %H:%M:%S")
                                duration = (completed - created).total_seconds()
                                prev_avg = stats_agent["stats"].get("avg_duration_sec", 0)
                                prev_count = stats_agent["stats"].get("completed_tasks", 1) - 1
                                if prev_count > 0:
                                    stats_agent["stats"]["avg_duration_sec"] = int((prev_avg * prev_count + duration) / (prev_count + 1))
                                else:
                                    stats_agent["stats"]["avg_duration_sec"] = int(duration)
                            except Exception:
                                pass
                        save_conversations(conversations_stats)
            except Exception:
                pass  # 统计更新失败不影响主流程
            
            # 阶段4：L2 执行者完成后通知组长，L1 通知主智能体
            current_agent_obj, _, _, _ = _find_agent(agent_id, conv_id)
            parent_id = current_agent_obj.get("parent_agent_id") if current_agent_obj else None
            if parent_id:
                parent_agent, _, _, _ = _find_agent(parent_id, conv_id)
                parent_name = parent_agent.get("name", "组长") if parent_agent else "组长"
                response += f"\n💡 已通知组长「{parent_name}」，等待后续指示。@{parent_name}"
            else:
                response += "\n💡 已通知主智能体，等待后续指示。@主智能体"
            
            # P0-1: 任务完成后触发记忆提取（异步、静默失败）
            # 从对话中提取关键经验，保存到智能体的 memory_log
            if conv_id and task_meta:
                trigger_memory_extraction(
                    conv_id=conv_id,
                    agent_id=agent_id,
                    task_id=task_meta.get("id", ""),
                    task_summary=summary,
                    agent=current_agent_obj,
                )
            
            return response
        except Exception as e:
            return f"❌ 提交任务结果失败：{str(e)}"

    # ========== 子代理调用工具（Phase 3） ==========
    if tool_name == "invoke_sub_agent":
        # 安全检查：只有显式开启 can_invoke_sub_agent 的智能体才能调用
        if not (agent and agent.get("can_invoke_sub_agent", False)):
            return "❌ 权限不足：你没有调用子代理的权限。"

        sub_name = arguments.get("sub_agent_name", "子代理").strip() or "子代理"
        task_desc = arguments.get("task_description", "").strip()
        sub_prompt = arguments.get("system_prompt", "").strip()
        inherit_perms = arguments.get("inherit_permissions", True)

        if not task_desc:
            return "❌ 缺少必填参数 task_description：请描述要交给子代理执行的任务。"

        try:
            import uuid as _uuid
            sub_agent_id = "temp_sub_" + _uuid.uuid4().hex[:8]

            # 构造子代理系统提示词
            if sub_prompt:
                sub_system_prompt = f"你是「{sub_name}」，由上级智能体调度的临时子代理。\n\n{sub_prompt}"
            else:
                sub_system_prompt = (
                    f"你是「{sub_name}」，由上级智能体调度的临时子代理。\n"
                    f"你的职责是专注完成上级交给你的子任务，并返回结果。\n\n"
                    f"## 工作原则\n"
                    f"- 专注完成子任务，不要偏离任务目标\n"
                    f"- 可以使用文件工具读写项目内文件\n"
                    f"- 完成后用文字清晰说明做了什么、结果在哪里\n"
                    f"- 你不能再创建子代理（非递归）\n"
                )
            # 注入通用核心规则
            sub_system_prompt += "\n" + CORE_RULES

            # 继承权限：默认继承父智能体的 allowed_paths
            if inherit_perms and agent:
                sub_allowed_paths = list(agent.get("allowed_paths", ["*"]))
            else:
                # 不继承则只给项目根目录
                sub_allowed_paths = [str(root)] if root_path else ["*"]

            # 解析父智能体的模型配置（继承）
            sub_model_config = agent.get("model_config") if agent else None

            # 构造临时子代理对象（不写入 conversations.json）
            sub_agent = {
                "id": sub_agent_id,
                "name": sub_name,
                "role": "临时子代理",
                "avatar": "🔧",
                "system_prompt": sub_system_prompt,
                "allowed_paths": sub_allowed_paths,
                "can_use_tools": True,
                "can_invoke_sub_agent": False,  # ⭐ 非递归：子代理不能再调用子代理
                "enabled_skills": [],  # 子代理不继承技能（避免权限放大）
                "template": "worker",
                "model_config": sub_model_config or {},
            }

            # 构造子代理的消息列表（只含任务描述）
            sub_messages = [
                {"role": "user", "content": f"## 任务\n{task_desc}"}
            ]

            # 同步调用子代理（max_tool_rounds=8，防止无限循环）
            # thinking_override 传 None（execute_tool 不接收此参数，子代理用默认思考模式）
            sub_full_content, sub_tool_events = collect_stream_sync(
                system_prompt=sub_system_prompt,
                messages_list=sub_messages,
                agent=sub_agent,
                root_path=root_path,
                conv_id=conv_id,
                default_config_id=default_config_id,
                thinking_override=None,
            )

            # 汇总工具调用情况
            tool_summary = ""
            if sub_tool_events:
                tool_names_used = []
                for evt_type, evt_data in sub_tool_events:
                    if evt_type == "tool_start":
                        tool_names_used.append(evt_data.get("tool_name", ""))
                if tool_names_used:
                    tool_summary = f"\n\n【子代理工具调用】共 {len(tool_names_used)} 次：{', '.join(tool_names_used)}"

            result = (
                f"✅ 子代理「{sub_name}」已完成任务。\n\n"
                f"--- 子代理回复 ---\n{sub_full_content}\n--- 回复结束 ---"
                f"{tool_summary}"
            )
            return result
        except Exception as e:
            import traceback
            return f"❌ 调用子代理失败：{str(e)}\n{traceback.format_exc()}"

    # ========== 普通文件工具 ==========
    path = arguments.get("path", ".")
    abs_path = resolve_project_path(root_path, path)

    if abs_path is None:
        if not root_path:
            return f"❌ 还没有设置工作目录，无法操作文件。请让用户在主界面点击「📂 设置目录」设置一个项目文件夹路径，设置后就可以读写该目录下的文件了。"
        return f"错误：路径 '{path}' 超出了项目根目录范围，只能访问项目内的文件。"
    
    # 权限检查：优先从项目级配置加载智能体权限
    agent = None
    all_agents = load_agents()
    agent = next((a for a in all_agents if a["id"] == agent_id), None)
    
    # 如果是项目级对话，用项目中的智能体配置覆盖
    if conv_id:
        convs = load_conversations()
        conv = next((c for c in convs if c["id"] == conv_id), None)
        if conv and conv.get("agents"):
            for ca in conv["agents"]:
                if ca["id"] == agent_id:
                    agent = ca
                    break
    
    if agent and not check_agent_path_access(agent, abs_path, root_path):
        allowed_display = []
        for p in agent.get("allowed_paths", []):
            try:
                # 尝试显示相对路径
                p_rel = str(Path(p).resolve().relative_to(root))
                allowed_display.append(p_rel)
            except Exception:
                allowed_display.append(p)
        return f"❌ 权限不足：你没有访问 '{path}' 的权限。\n你当前可以访问的路径：\n- " + "\n- ".join(allowed_display) + "\n\n如果需要访问其他路径，请 @主智能体 请求授权。"
    
    # 写入操作额外检查：子智能体不能写入 input 目录（只能读）
    # 覆盖 write_file、edit_file、create_directory 三个可能修改文件系统的工具
    if tool_name in ("write_file", "edit_file", "create_directory") and agent_id != "main":
        abs_path_obj = Path(abs_path)
        # 检查是否在任务 input 目录下（.agent/tasks/{task_id}/input/...）
        try:
            rel = abs_path_obj.relative_to(root)
            rel_parts = rel.parts
            # 路径结构: .agent / tasks / {task_id} / input / ...
            if len(rel_parts) >= 4 and rel_parts[0] == ".agent" and rel_parts[1] == "tasks" and rel_parts[3] == "input":
                return f"❌ 权限不足：任务的 input/ 目录是只读的，不能写入或修改。\n请把文件写到 output/ 目录或你的私有工作区 agent_work/{agent_id}/ 下。"
        except Exception:
            pass
    
    # P1-6: 文件版本控制 - 写入前自动备份旧版本
    def _backup_file_version(file_path_obj, root_path_str):
        """在写入前备份旧文件版本到 .agent/file_history/"""
        if not file_path_obj.exists() or not file_path_obj.is_file():
            return
        try:
            import hashlib as _hl
            rel_path = file_path_obj.relative_to(Path(root_path_str).resolve())
            safe_name = str(rel_path).replace("\\", "_").replace("/", "_")
            history_dir = Path(root_path_str) / ".agent" / "file_history" / safe_name
            history_dir.mkdir(parents=True, exist_ok=True)
            old_content = file_path_obj.read_bytes()
            size_hash = _hl.md5(old_content).hexdigest()[:8]
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_name = f"{timestamp}_{size_hash}"
            backup_path = history_dir / backup_name
            if not backup_path.exists():
                backup_path.write_bytes(old_content)
            # 保留最近10个版本
            versions = sorted(history_dir.iterdir())
            if len(versions) > 10:
                for old_ver in versions[:-10]:
                    old_ver.unlink()
        except Exception:
            pass  # 备份失败不影响主流程
    
    try:
        p = Path(abs_path)
        
        if tool_name == "list_directory":
            if not p.exists():
                return f"错误：路径 '{path}' 不存在。"
            if not p.is_dir():
                return f"错误：'{path}' 不是文件夹。"
            items = []
            for child in sorted(p.iterdir()):
                prefix = "📁 " if child.is_dir() else "📄 "
                items.append(prefix + child.name)
            if not items:
                return f"文件夹 '{path}' 是空的。"
            return f"📂 {path} 的内容：\n" + "\n".join(items)
        
        elif tool_name == "read_file":
            if not p.exists():
                return f"错误：文件 '{path}' 不存在。"
            if not p.is_file():
                return f"错误：'{path}' 不是文件。"
            # 文件大小限制（10MB）：防止读取 GB 级文件导致内存耗尽
            MAX_READ_SIZE = 10 * 1024 * 1024  # 10MB
            file_size = p.stat().st_size
            if file_size > MAX_READ_SIZE:
                return f"❌ 文件过大：'{path}' 大小为 {file_size // 1024 // 1024}MB，超过读取上限（{MAX_READ_SIZE // 1024 // 1024}MB）。请使用 grep 工具搜索关键内容，或使用 list_directory 查看文件结构。"
            content = p.read_text(encoding="utf-8")
            # 限制显示长度，避免 token 爆炸
            if len(content) > 50000:
                content = content[:50000] + f"\n\n... (文件过长，已截断，只显示前 50000 字符)"
            return f"📄 {path} 的内容：\n```\n{content}\n```"
        
        elif tool_name == "write_file":
            content = arguments.get("content", "")
            # P1-6: 写入前备份旧版本
            _backup_file_version(p, root_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            # 回读校验（防幻觉第2层）：确认写入成功，防止磁盘满/权限问题导致智能体误以为成功
            try:
                written = p.read_text(encoding="utf-8")
                actual_bytes = len(written.encode("utf-8"))
                if actual_bytes != len(content.encode("utf-8")):
                    return f"⚠️ 写入可能不完整：预期 {len(content.encode('utf-8'))} 字节，实际 {actual_bytes} 字节。文件：{path}"
            except Exception as verify_err:
                return f"⚠️ 写入后回读校验失败：{str(verify_err)}。文件可能未正确写入：{path}"
            return f"✅ 已成功写入文件：{path}（{len(content)} 字符，{actual_bytes} 字节，已回读校验）"
        
        elif tool_name == "create_directory":
            p.mkdir(parents=True, exist_ok=True)
            return f"✅ 已创建文件夹：{path}"
        
        elif tool_name == "grep":
            # 代码内容搜索：在文件内容里找匹配正则的行
            import re as _re
            pattern = arguments.get("pattern", "")
            search_path = arguments.get("path", ".")
            glob_filter = arguments.get("glob", "")
            context_lines = arguments.get("context_lines", 0)
            max_results = arguments.get("max_results", 50)
            
            if not pattern:
                return "错误：pattern 是必填参数"
            
            # 解析搜索路径
            search_abs = resolve_project_path(root_path, search_path)
            if search_abs is None:
                return f"错误：搜索路径 '{search_path}' 超出了项目根目录范围。"
            search_p = Path(search_abs)
            if not search_p.exists():
                return f"错误：搜索路径不存在：{search_path}"
            if not check_path_permission(agent, search_abs):
                return f"错误：没有权限访问路径：{search_path}"
            
            # 编译正则
            try:
                regex = _re.compile(pattern)
            except _re.error as e:
                return f"错误：正则表达式无效：{str(e)}"
            
            # 收集要搜索的文件
            if search_p.is_file():
                files_to_search = [search_p]
            else:
                # 递归收集文件
                files_to_search = []
                for f in search_p.rglob("*"):
                    if f.is_file():
                        # 跳过隐藏目录和常见忽略目录
                        parts = f.relative_to(search_p).parts
                        if any(part.startswith('.') and part != '.agent' for part in parts):
                            continue
                        if any(part in ('node_modules', '__pycache__', 'dist', 'build', '.git') for part in parts):
                            continue
                        # 应用 glob 过滤
                        if glob_filter:
                            import fnmatch as _fn
                            if not _fn.fnmatch(f.name, glob_filter):
                                continue
                        files_to_search.append(f)
            
            # 搜索
            results = []
            total_matches = 0
            for f in files_to_search:
                if total_matches >= max_results:
                    break
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if regex.search(line):
                        # 显示相对路径
                        try:
                            rel_path = str(f.relative_to(Path(root_path).resolve()))
                        except ValueError:
                            rel_path = str(f)
                        
                        # 上下文
                        ctx_start = max(0, i - context_lines)
                        ctx_end = min(len(lines), i + context_lines + 1)
                        ctx = lines[ctx_start:ctx_end]
                        # 标记匹配行
                        ctx_display = []
                        for j, ctx_line in enumerate(ctx):
                            line_num = ctx_start + j + 1
                            marker = "→" if (ctx_start + j) == i else " "
                            ctx_display.append(f"  {marker} {line_num}: {ctx_line}")
                        
                        results.append(f"{rel_path}:\n" + "\n".join(ctx_display))
                        total_matches += 1
                        if total_matches >= max_results:
                            break
            
            if not results:
                return f"🔍 搜索 '{pattern}' 未找到匹配（共扫描 {len(files_to_search)} 个文件）"
            
            header = f"🔍 搜索 '{pattern}' 找到 {total_matches} 处匹配"
            if total_matches >= max_results:
                header += f"（已达上限 {max_results}，可能还有更多）"
            return header + f"（扫描 {len(files_to_search)} 个文件）：\n\n" + "\n\n".join(results)
        
        elif tool_name == "glob":
            # 文件名搜索：按模式快速找文件
            import fnmatch as _fn2
            pattern = arguments.get("pattern", "")
            search_path = arguments.get("path", ".")
            
            if not pattern:
                return "错误：pattern 是必填参数"
            
            search_abs = resolve_project_path(root_path, search_path)
            if search_abs is None:
                return f"错误：搜索路径 '{search_path}' 超出了项目根目录范围。"
            search_p = Path(search_abs)
            if not search_p.exists():
                return f"错误：搜索路径不存在：{search_path}"
            if not check_path_permission(agent, search_abs):
                return f"错误：没有权限访问路径：{search_path}"
            
            # 递归匹配文件名
            matched = []
            root_dir = search_p if search_p.is_dir() else search_p.parent
            # 把 **/*.py 这种 pattern 转成 fnmatch 能处理的
            # fnmatch 不支持 **，但可以用 PurePath.match 或转换
            # 简化：去掉 ** 前缀，用 fnmatch 匹配文件名部分
            import fnmatch as _fn2
            # 支持 **/*.ext 格式：提取文件名模式
            name_pattern = pattern
            if "/" in pattern:
                name_pattern = pattern.rsplit("/", 1)[-1]
            # 支持 *.{ext1,ext2} 格式
            brace_match = False
            if "{" in name_pattern and "}" in name_pattern:
                brace_match = True
            
            for f in root_dir.rglob("*"):
                if f.is_file():
                    # 检查是否在隐藏目录里
                    try:
                        rel = f.relative_to(Path(root_path).resolve())
                    except ValueError:
                        rel = f
                    parts = rel.parts
                    if any(part.startswith('.') and part != '.agent' for part in parts):
                        continue
                    if any(part in ('node_modules', '__pycache__', 'dist', 'build', '.git') for part in parts):
                        continue
                    # 匹配：先试完整 pattern（用 match 支持 **），再试 name_pattern
                    matched_flag = False
                    try:
                        if rel.match(pattern) or f.match(pattern):
                            matched_flag = True
                    except Exception:
                        pass
                    if not matched_flag and _fn2.fnmatch(f.name, name_pattern):
                        matched_flag = True
                    if not matched_flag and brace_match:
                        # 处理 *.{py,js} 这种
                        import re as _re2
                        brace_regex = _re2.sub(r'\{([^}]+)\}', lambda m: '(' + '|'.join(m.group(1).split(',')) + ')', pattern)
                        brace_regex = brace_regex.replace('*', '[^/]*').replace('**/', '(.*/)?').replace('?', '[^/]')
                        if _re2.search(brace_regex, str(rel).replace('\\', '/')):
                            matched_flag = True
                    if matched_flag:
                        try:
                            rel_path = str(f.relative_to(Path(root_path).resolve()))
                        except ValueError:
                            rel_path = str(f)
                        matched.append(rel_path)
                        if len(matched) >= 100:
                            break
            
            if not matched:
                return f"📂 未找到匹配 '{pattern}' 的文件"
            
            header = f"📂 找到 {len(matched)} 个匹配 '{pattern}' 的文件"
            if len(matched) >= 100:
                header += "（已达上限 100，可能还有更多）"
            return header + "：\n" + "\n".join(matched)
        
        elif tool_name == "edit_file":
            # 精确编辑：SEARCH/REPLACE
            edit_path = arguments.get("path", "")
            old_str = arguments.get("old_str", "")
            new_str = arguments.get("new_str", "")
            
            if not edit_path or not old_str:
                return "错误：path 和 old_str 都是必填参数"
            
            edit_abs = resolve_project_path(root_path, edit_path)
            if edit_abs is None:
                return f"错误：路径 '{edit_path}' 超出了项目根目录范围。"
            edit_p = Path(edit_abs)
            if not edit_p.exists():
                return f"错误：文件不存在：{edit_path}"
            
            # P1-6: 编辑前备份旧版本
            _backup_file_version(edit_p, root_path)
            if not edit_p.is_file():
                return f"错误：'{edit_path}' 不是文件"
            if not check_path_permission(agent, edit_abs):
                return f"错误：没有权限编辑文件：{edit_path}"
            
            try:
                content = edit_p.read_text(encoding="utf-8")
            except Exception as e:
                return f"错误：读取文件失败：{str(e)}"
            
            # 检查 old_str 是否存在
            if old_str not in content:
                # 给出最接近的片段提示
                return (f"错误：在文件中找不到要替换的内容。请确认 old_str 精确匹配（包括缩进和换行）。\n"
                        f"提示：先调用 read_file 查看文件实际内容，再确定 old_str。\n"
                        f"文件总长度：{len(content)} 字符，行数：{len(content.splitlines())}")
            
            # 检查是否有多处匹配
            match_count = content.count(old_str)
            if match_count > 1:
                return (f"错误：old_str 在文件中匹配到 {match_count} 处，无法确定替换哪一处。\n"
                        f"请在 old_str 里加入更多上下文行，保证唯一匹配。")
            
            # 执行替换
            new_content = content.replace(old_str, new_str, 1)
            try:
                edit_p.write_text(new_content, encoding="utf-8")
                # 回读校验（防幻觉第2层）
                try:
                    verify_content = edit_p.read_text(encoding="utf-8")
                    if new_str not in verify_content:
                        return f"⚠️ 编辑后回读校验失败：替换的内容未在文件中找到。文件：{edit_path}"
                except Exception as verify_err:
                    return f"⚠️ 编辑后回读校验异常：{str(verify_err)}。文件：{edit_path}"
                # 返回变更摘要
                old_lines = old_str.count("\n") + 1
                new_lines = new_str.count("\n") + 1 if new_str else 0
                return (f"✅ 已精确编辑文件：{edit_path}\n"
                        f"  替换：{old_lines} 行 → {new_lines} 行\n"
                        f"  文件总行数：{len(new_content.splitlines())}（已回读校验）")
            except Exception as e:
                return f"错误：写入文件失败：{str(e)}"
        
        elif tool_name == "move_file":
            source_path = arguments.get("source_path", "").strip()
            target_path = arguments.get("target_path", "").strip()
            if not source_path or not target_path:
                return "错误：source_path 和 target_path 都是必填参数。"
            # 解析源路径和目标路径（相对项目根目录）
            source_abs = resolve_project_path(root_path, source_path)
            target_abs = resolve_project_path(root_path, target_path)
            if source_abs is None:
                return f"错误：源路径 '{source_path}' 超出了项目根目录范围。"
            if target_abs is None:
                return f"错误：目标路径 '{target_path}' 超出了项目根目录范围。"
            source_p = Path(source_abs)
            target_p = Path(target_abs)
            if not source_p.exists():
                return f"错误：源文件不存在：{source_path}"
            if not source_p.is_file():
                return f"错误：源路径不是文件：{source_path}"
            # 检查源路径权限
            if not check_path_permission(agent, source_abs):
                return f"错误：没有权限读取源路径：{source_path}"
            # 检查目标路径权限
            if not check_path_permission(agent, target_abs):
                return f"错误：没有权限写入目标路径：{target_path}"
            try:
                target_p.parent.mkdir(parents=True, exist_ok=True)
                # 如果目标已存在，覆盖
                if target_p.exists():
                    target_p.unlink()
                source_p.rename(target_p)
                # 防幻觉：回读校验，确认目标文件真实存在
                if target_p.exists() and target_p.is_file():
                    file_size = target_p.stat().st_size
                    return (f"✅ 已移动文件：{source_path} → {target_path}（源文件已删除）\n"
                            f"🔍 校验：目标文件真实存在，大小 {file_size} 字节。"
                            f"你现在可以安全地说\"已归档到 {target_path}\"。")
                else:
                    return f"⚠️ 移动操作已执行但目标文件校验失败，请检查 {target_path}"
            except Exception as e:
                return f"错误：移动文件失败：{str(e)}"
        
        elif tool_name == "copy_file":
            source_path = arguments.get("source_path", "").strip()
            target_path = arguments.get("target_path", "").strip()
            if not source_path or not target_path:
                return "错误：source_path 和 target_path 都是必填参数。"
            source_abs = resolve_project_path(root_path, source_path)
            target_abs = resolve_project_path(root_path, target_path)
            if source_abs is None:
                return f"错误：源路径 '{source_path}' 超出了项目根目录范围。"
            if target_abs is None:
                return f"错误：目标路径 '{target_path}' 超出了项目根目录范围。"
            source_p = Path(source_abs)
            target_p = Path(target_abs)
            if not source_p.exists():
                return f"错误：源文件不存在：{source_path}"
            if not source_p.is_file():
                return f"错误：源路径不是文件：{source_path}"
            if not check_path_permission(agent, source_abs):
                return f"错误：没有权限读取源路径：{source_path}"
            if not check_path_permission(agent, target_abs):
                return f"错误：没有权限写入目标路径：{target_path}"
            try:
                import shutil as _shutil
                target_p.parent.mkdir(parents=True, exist_ok=True)
                if target_p.exists():
                    target_p.unlink()
                _shutil.copy2(source_p, target_p)
                # 防幻觉：回读校验
                if target_p.exists() and target_p.is_file():
                    file_size = target_p.stat().st_size
                    return (f"✅ 已复制文件：{source_path} → {target_path}（源文件保留）\n"
                            f"🔍 校验：目标文件真实存在，大小 {file_size} 字节。")
                else:
                    return f"⚠️ 复制操作已执行但目标文件校验失败，请检查 {target_path}"
            except Exception as e:
                return f"错误：复制文件失败：{str(e)}"
        
        elif tool_name == "list_tasks":
            # 查询当前项目所有任务及状态（主智能体进度感知）
            status_filter = arguments.get("status_filter", "all")
            tasks_dir = root / ".agent" / "tasks"
            if not tasks_dir.exists():
                return "当前项目还没有任何任务。可以用 create_task 创建任务并分配给智能体。"
            
            # 独立获取智能体列表（避免引用外层 conv_agents 的作用域问题）
            _lt_agents = []
            if conv_id:
                _lt_convs = load_conversations()
                _lt_conv = next((c for c in _lt_convs if c["id"] == conv_id), None)
                if _lt_conv:
                    _lt_agents = _lt_conv.get("agents", [])
            
            import json as json_lt
            all_tasks = []
            for d in sorted(tasks_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if not d.is_dir():
                    continue
                meta_file = d / "meta.json"
                if not meta_file.exists():
                    continue
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        meta = json_lt.load(f)
                    all_tasks.append(meta)
                except Exception:
                    continue
            
            # 筛选
            if status_filter == "pending":
                filtered = [t for t in all_tasks if t.get("status") == "pending"]
            elif status_filter == "completed":
                filtered = [t for t in all_tasks if t.get("status") == "completed"]
            else:
                filtered = all_tasks
            
            if not filtered:
                if status_filter == "pending":
                    return "✅ 没有待处理（pending）的任务，所有任务都已完成。"
                elif status_filter == "completed":
                    return "📭 还没有已完成的任务。"
                else:
                    return "📭 当前项目没有任何任务。"
            
            # 找智能体名字（使用独立获取的 _lt_agents）
            def _agent_name(aid):
                for a in _lt_agents:
                    if a["id"] == aid:
                        return a["name"]
                return aid
            
            lines = [f"📋 任务列表（共 {len(filtered)} 个，筛选: {status_filter}）：\n"]
            for t in filtered:
                status_emoji = {"pending": "⏳", "completed": "✅", "in_progress": "🔄"}.get(t.get("status", ""), "❓")
                agent_nm = _agent_name(t.get("agent_id", ""))
                desc = t.get("description", "")[:60]
                lines.append(f"{status_emoji} [{t.get('status', '?')}] {t['id']} → @{agent_nm}")
                lines.append(f"    类型: {t.get('type_name', '?')} | 描述: {desc}")
                if t.get("result_files"):
                    lines.append(f"    结果文件: {', '.join(t['result_files'])}")
                lines.append("")
            
            pending_count = sum(1 for t in all_tasks if t.get("status") == "pending")
            completed_count = sum(1 for t in all_tasks if t.get("status") == "completed")
            lines.append(f"📊 总计: {len(all_tasks)} 个任务（{completed_count} 已完成，{pending_count} 待处理）")
            if pending_count > 0 and status_filter != "pending":
                lines.append(f"\n⚠️ 还有 {pending_count} 个待处理任务，请用 list_tasks(status_filter='pending') 查看，并安排对应智能体执行。")
            return "\n".join(lines)
        
        elif tool_name == "create_todo_list":
            # M2：TODO 清单系统 - 创建任务清单
            title = arguments.get("title", "").strip()
            items = arguments.get("items", [])
            if not title:
                return "错误：title 是必填参数，请给清单起个名字。"
            if not items or not isinstance(items, list):
                return "错误：items 是必填参数，必须是字符串数组。"
            if len(items) < 2:
                return "错误：TODO 清单至少需要 2 项。单步任务不需要清单，直接调用对应工具即可。"
            if len(items) > 10:
                return f"错误：TODO 清单最多 10 项，当前 {len(items)} 项。请合并或拆分任务。"
            
            # 单对话最多 5 个进行中的清单
            todos_dir = root / ".agent" / "todos"
            todos_dir.mkdir(parents=True, exist_ok=True)
            active_count = 0
            for fpath in todos_dir.iterdir():
                if not fpath.name.endswith(".json"):
                    continue
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        t = json.load(f)
                    if t.get("conversation_id") == conv_id and t.get("status") == "in_progress":
                        active_count += 1
                except Exception:
                    pass
            if active_count >= 5:
                return f"错误：当前对话已有 {active_count} 个进行中的清单，已达上限 5 个。请先完成或清理现有清单。"
            
            todo_id = f"todo_{uuid.uuid4().hex[:8]}"
            now_str = time.strftime("%Y-%m-%d %H:%M:%S")
            todo = {
                "todo_id": todo_id,
                "conversation_id": conv_id,
                "created_at": now_str,
                "updated_at": now_str,
                "title": title,
                "items": [
                    {"index": i, "content": str(item), "status": "pending", "updated_at": now_str}
                    for i, item in enumerate(items)
                ],
                "status": "in_progress"
            }
            todo_path = todos_dir / f"{todo_id}.json"
            try:
                with open(todo_path, "w", encoding="utf-8") as f:
                    json.dump(todo, f, ensure_ascii=False, indent=2)
            except Exception as e:
                return f"错误：保存 TODO 清单失败：{str(e)}"
            
            items_text = "\n".join([f"  {i+1}. [pending] {item}" for i, item in enumerate(items)])
            return (f"✅ 已创建 TODO 清单「{title}」（ID: {todo_id}），共 {len(items)} 项：\n"
                    f"{items_text}\n\n"
                    f"接下来请逐项执行，每完成一项调用 update_todo_status 更新状态。")
        
        elif tool_name == "update_todo_status":
            # M2：TODO 清单系统 - 更新项状态
            todo_id = arguments.get("todo_id", "").strip()
            item_index = arguments.get("item_index")
            status = arguments.get("status", "").strip()
            if not todo_id:
                return "错误：todo_id 是必填参数。"
            if item_index is None:
                return "错误：item_index 是必填参数（从 0 开始）。"
            try:
                item_index = int(item_index)
            except (TypeError, ValueError):
                return f"错误：item_index 必须是整数，收到 {item_index}。"
            if status not in ("pending", "in_progress", "completed"):
                return f"错误：status 只能是 pending/in_progress/completed，收到 {status}。"
            
            todo_path = root / ".agent" / "todos" / f"{todo_id}.json"
            if not todo_path.exists():
                return f"错误：找不到 TODO 清单：{todo_id}"
            
            try:
                with open(todo_path, "r", encoding="utf-8") as f:
                    todo = json.load(f)
            except Exception as e:
                return f"错误：读取 TODO 清单失败：{str(e)}"
            
            # 校验清单归属当前对话
            if todo.get("conversation_id") != conv_id:
                return f"错误：TODO 清单 {todo_id} 不属于当前对话。"
            
            if item_index < 0 or item_index >= len(todo["items"]):
                return f"错误：item_index 超出范围：{item_index}（共 {len(todo['items'])} 项，有效范围 0-{len(todo['items'])-1}）。"
            
            now_str = time.strftime("%Y-%m-%d %H:%M:%S")
            todo["items"][item_index]["status"] = status
            todo["items"][item_index]["updated_at"] = now_str
            todo["updated_at"] = now_str
            
            # 自动更新清单整体状态
            if all(item["status"] == "completed" for item in todo["items"]):
                todo["status"] = "completed"
            elif any(item["status"] == "in_progress" for item in todo["items"]):
                todo["status"] = "in_progress"
            else:
                todo["status"] = "in_progress"
            
            try:
                with open(todo_path, "w", encoding="utf-8") as f:
                    json.dump(todo, f, ensure_ascii=False, indent=2)
            except Exception as e:
                return f"错误：保存 TODO 清单失败：{str(e)}"
            
            # 返回清单概览，方便主智能体跟踪进度
            pending_count = sum(1 for item in todo["items"] if item["status"] != "completed")
            completed_count = len(todo["items"]) - pending_count
            overview = "\n".join([
                f"  {i+1}. [{item['status']}] {item['content']}"
                for i, item in enumerate(todo["items"])
            ])
            result = (f"✅ 已更新：第 {item_index+1} 项 → {status}\n\n"
                      f"📋 清单「{todo['title']}」进度：{completed_count}/{len(todo['items'])} 完成，"
                      f"还剩 {pending_count} 项未完成。\n{overview}")
            if todo["status"] == "completed":
                result += "\n\n🎉 清单已全部完成！"
            return result
        
        # P1-6: 文件版本控制工具
        elif tool_name == "list_file_versions":
            list_ver_path = arguments.get("path", "")
            list_ver_abs = resolve_project_path(root_path, list_ver_path)
            if list_ver_abs is None:
                return f"错误：路径 '{list_ver_path}' 超出了项目根目录范围。"
            
            # 构建历史版本目录路径
            list_p = Path(list_ver_abs)
            rel_path = list_p.relative_to(Path(root_path).resolve())
            safe_name = str(rel_path).replace("\\", "_").replace("/", "_")
            history_dir = Path(root_path) / ".agent" / "file_history" / safe_name
            
            if not history_dir.exists():
                return f"📁 文件 '{list_ver_path}' 没有历史版本记录。"
            
            versions = sorted(history_dir.iterdir())
            if not versions:
                return f"📁 文件 '{list_ver_path}' 没有历史版本记录。"
            
            version_list = []
            for v in versions:
                stat = v.stat()
                # 解析版本名：YYYYMMDD_HHMMSS_hash
                parts = v.name.split("_")
                if len(parts) >= 2:
                    ts = parts[0] + "_" + parts[1]
                    # 格式化为可读时间
                    try:
                        from datetime import datetime as _dt
                        dt = _dt.strptime(ts, "%Y%m%d_%H%M%S")
                        readable_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        readable_time = ts
                else:
                    readable_time = v.name
                version_list.append(f"  - 版本: {v.name} | 时间: {readable_time} | 大小: {stat.st_size} 字节")
            
            return f"📁 文件 '{list_ver_path}' 共有 {len(versions)} 个历史版本：\n" + "\n".join(version_list) + "\n\n使用 file_rollback 工具可回退到指定版本。"
        
        elif tool_name == "file_rollback":
            rb_path = arguments.get("path", "")
            rb_version = arguments.get("version", "")
            if not rb_path or not rb_version:
                return "错误：path 和 version 都是必填参数"
            
            rb_abs = resolve_project_path(root_path, rb_path)
            if rb_abs is None:
                return f"错误：路径 '{rb_path}' 超出了项目根目录范围。"
            
            rb_p = Path(rb_abs)
            # 构建历史版本目录路径
            rel_path = rb_p.relative_to(Path(root_path).resolve())
            safe_name = str(rel_path).replace("\\", "_").replace("/", "_")
            history_dir = Path(root_path) / ".agent" / "file_history" / safe_name
            
            version_path = history_dir / rb_version
            if not version_path.exists():
                return f"错误：版本 '{rb_version}' 不存在。请先调用 list_file_versions 查看可用版本。"
            
            # 回退前备份当前版本
            if rb_p.exists():
                _backup_file_version(rb_p, root_path)
            
            # 恢复旧版本内容
            old_content = version_path.read_bytes()
            rb_p.parent.mkdir(parents=True, exist_ok=True)
            rb_p.write_bytes(old_content)
            
            # 回读校验
            actual_bytes = len(rb_p.read_bytes())
            if actual_bytes == len(old_content):
                return f"✅ 已将文件 '{rb_path}' 回退到版本 '{rb_version}'（{actual_bytes} 字节，已回读校验）"
            else:
                return f"⚠️ 回退可能不完整：预期 {len(old_content)} 字节，实际 {actual_bytes} 字节。"
        
        else:
            return f"错误：未知工具 '{tool_name}'"
    
    except PermissionError:
        return f"错误：没有权限访问 '{path}'。"
    except Exception as e:
        return f"错误：操作 '{path}' 时出错 - {str(e)}"


def get_team_context_for_main(conv_id: str) -> str:
    """获取当前项目的团队成员信息，用于注入到主智能体的 system prompt。
    
    让主智能体在每次回复前都能看到现有成员，避免重复创建角色。
    """
    if not conv_id:
        return ""
    try:
        convs = load_conversations()
        conv = next((c for c in convs if c["id"] == conv_id), None)
        if not conv:
            return ""
        agents = conv.get("agents") or []
        # 只列非 main 成员
        members = [a for a in agents if a.get("id") != "main"]
        if not members:
            return "\n\n--- 当前团队状态 ---\n团队为空（只有你）。如需协作，按需用 create_team_member 创建成员。"
        
        lines = ["--- 当前团队成员（可直接 @调度，避免重复创建） ---"]
        for a in members:
            name = a.get("name", "未命名")
            role = a.get("role", "未设置")
            aid = a.get("id", "")
            level = a.get("level", 1)
            tpl = a.get("template", "")
            parent = a.get("parent_agent_id", "")
            level_tag = f"L{level}" if level and level != 1 else "L1"
            tpl_tag = f"[{tpl}]" if tpl else ""
            parent_name = ""
            if parent:
                pa = next((x for x in members if x.get("id") == parent), None)
                if pa:
                    parent_name = f"（上级：{pa.get('name', '')}）"
            lines.append(f"- {name}（{level_tag}{tpl_tag} 角色id：{aid}，{role}）{parent_name}")
        lines.append("")
        lines.append("提示：上述成员已经存在。如果它们的角色能胜任当前任务，直接 @名字 调度即可，不要重复创建相同职责的成员。")
        lines.append("")
        lines.append("【重要·上下文隔离】子智能体只能看到你 @它时写的任务文本，看不到完整对话历史。")
        lines.append("所以派发任务时务必写清楚：任务目标、背景信息、相关文件路径、验收标准。")
        lines.append("子智能体间通过文件传递信息（写到 output/ → 下一个读 input/），不要依赖它们能看到彼此的对话。")
        lines.append("")
        lines.append("【模板推荐】创建新成员时优先用 template 参数（creator/reviewer/analyst/worker/coordinator），")
        lines.append("自动配置工具集和权限，角色质量更稳定。复杂项目（10+ 智能体）可用 coordinator 模板建组长，组长能用 create_sub_task 派发任务给 L2 执行者。")
        return "\n\n".join(lines)
    except Exception:
        return ""


def estimate_tokens(text: str) -> int:
    """粗略估算字符串的 token 数。
    中文约 1.5 字/token，英文约 4 字符/token。
    估算偏保守（略高），避免实际上下文超限。
    """
    if not text:
        return 0
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 1.5 + other_chars / 4)


def count_messages_tokens(messages: list) -> int:
    """计算 OpenAI 格式消息列表的总 token 数。
    每条消息额外计入 4 token 的元数据开销（role、分隔符等）。
    """
    total = 0
    for msg in messages:
        total += estimate_tokens(msg.get("content", ""))
        total += 4
    return total


# ========== 智能体记忆系统（P0-1）==========
# 记忆类型说明：
# - preference: 用户偏好（如"喜欢Markdown格式报告"）
# - lesson: 教训（如"不要在未读取文件前直接edit"）
# - pattern: 有效模式（如"先列出大纲再逐章创作效果好"）
# - fact: 事实记录（如"项目使用了Vue3+FastAPI技术栈"）

MAX_MEMORY_ENTRIES = 50  # 单个智能体最多保留50条记忆


def format_memory_for_prompt(agent: dict) -> str:
    """将智能体的 memory_log 格式化为可注入系统提示词的文本。
    
    返回空字符串表示没有记忆或不需要注入。
    """
    memory_log = agent.get("memory_log", [])
    if not memory_log:
        return ""
    
    # 按类型分组
    type_labels = {
        "preference": "用户偏好",
        "lesson": "经验教训",
        "pattern": "有效模式",
        "fact": "已知事实",
    }
    
    lines = ["\n\n## 📝 历史经验记忆（从过往任务中积累，请参考但不必拘泥）"]
    by_type = {}
    for mem in memory_log:
        t = mem.get("type", "fact")
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(mem.get("content", ""))
    
    for mem_type, label in type_labels.items():
        if mem_type in by_type:
            lines.append(f"### {label}")
            for content in by_type[mem_type]:
                lines.append(f"- {content}")
    
    return "\n".join(lines)


def add_memory_to_agent(conv_id: str, agent_id: str, memory_type: str, content: str, task_id: str = "") -> bool:
    """向智能体添加一条记忆记录。
    
    在任务完成或对话结束时调用。记忆存储在 conversations.json 的 agent 对象中。
    超过 MAX_MEMORY_ENTRIES 时自动淘汰最旧的。
    """
    if not conv_id or not content:
        return False
    
    conversations = load_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        return False
    
    agents = conv.get("agents", [])
    agent = next((a for a in agents if a["id"] == agent_id), None)
    if not agent:
        return False
    
    if "memory_log" not in agent:
        agent["memory_log"] = []
    
    # 去重：如果内容高度相似（前50字符相同），不重复添加
    content_prefix = content[:50]
    for existing in agent["memory_log"]:
        if existing.get("content", "")[:50] == content_prefix:
            return False
    
    import uuid as _uuid
    new_mem = {
        "id": "mem_" + _uuid.uuid4().hex[:8],
        "type": memory_type,
        "content": content,
        "source_task_id": task_id,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    agent["memory_log"].append(new_mem)
    
    # 超出上限时淘汰最旧的
    if len(agent["memory_log"]) > MAX_MEMORY_ENTRIES:
        agent["memory_log"] = agent["memory_log"][-MAX_MEMORY_ENTRIES:]
    
    save_conversations(conversations)
    return True


def extract_memory_from_conversation(conv_id: str, agent_id: str, task_id: str = "", task_summary: str = "", agent: dict = None) -> list:
    """从对话历史中提取关键经验，返回记忆列表。
    
    调用 LLM 分析最近的对话，提取可复用的经验。
    返回格式：[{"type": "preference", "content": "..."}, ...]
    """
    if not conv_id:
        return []
    
    # 获取该智能体最近的对话历史
    all_msgs = load_messages()
    conv_msgs = [m for m in all_msgs if m.get("conversation_id") == conv_id]
    
    # 过滤出与该智能体相关的消息
    if agent_id:
        relevant = []
        for m in conv_msgs:
            if m.get("agent_id") == agent_id or (m.get("role") == "user" and agent_id == "main"):
                relevant.append(m)
        conv_msgs = relevant[-20:]  # 最近20条
    else:
        conv_msgs = conv_msgs[-20:]
    
    if len(conv_msgs) < 4:
        return []  # 消息太少，不值得提取
    
    # 构建对话摘要文本
    dialog_text = ""
    for m in conv_msgs:
        role = "用户" if m.get("role") == "user" else "智能体"
        content = m.get("content", "")[:500]  # 每条最多500字
        dialog_text += f"{role}: {content}\n"
    
    if task_summary:
        dialog_text += f"\n[任务总结: {task_summary}]"
    
    extract_prompt = """你是一个经验提取器。请从以下对话中提取可复用的关键经验。

只提取真正有价值的、可在未来任务中复用的经验，忽略一次性的具体操作细节。

经验分四类：
- preference: 用户偏好（格式、风格、工作方式等）
- lesson: 教训（做错了什么、应该避免什么）
- pattern: 有效模式（什么方法效果好，值得复用）
- fact: 事实记录（项目相关的固定事实，如技术栈、角色设定等）

请用 JSON 数组格式输出，每条经验包含 type 和 content 两个字段。如果没有值得提取的经验，返回空数组 []。

示例输出：
[{"type": "preference", "content": "用户偏好Markdown格式的结构化报告"}, {"type": "pattern", "content": "先列大纲再逐章创作，效率更高"}]

对话内容：
""" + dialog_text
    
    try:
        result = call_llm(
            system_prompt="你是经验提取器，只输出JSON，不输出其他内容。",
            user_message=extract_prompt,
            agent=agent,
        )
        
        # 解析 JSON 结果（容错处理）
        import json as _json
        result = result.strip()
        # 去除可能的 markdown 代码块标记
        if result.startswith("```"):
            lines = result.split("\n")
            result = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        
        memories = _json.loads(result)
        if isinstance(memories, list):
            # 过滤无效条目
            valid = []
            for m in memories:
                if isinstance(m, dict) and m.get("content") and m.get("type") in ["preference", "lesson", "pattern", "fact"]:
                    valid.append(m)
            return valid
    except Exception:
        pass
    
    return []


def trigger_memory_extraction(conv_id: str, agent_id: str, task_id: str = "", task_summary: str = "", agent: dict = None):
    """触发记忆提取并保存（在任务完成后调用）。
    
    同步调用 LLM 提取经验，然后保存到智能体的 memory_log。
    失败时静默处理，不影响主流程。
    """
    try:
        memories = extract_memory_from_conversation(conv_id, agent_id, task_id, task_summary, agent=agent)
        if memories:
            for mem in memories[:5]:  # 每次最多保存5条
                add_memory_to_agent(conv_id, agent_id, mem["type"], mem["content"], task_id)
            
            # P0-2: 检查是否需要同步到团队级共享记忆
            sync_memory_to_team(conv_id, agent_id)
    except Exception:
        pass  # 记忆提取失败不影响主流程


def sync_memory_to_team(conv_id: str, agent_id: str):
    """P0-2: 将项目级记忆同步到团队级共享记忆。
    
    当项目级 memory_log 超过 10 条时，将最近的记忆上传到团队级 shared_memory。
    """
    if not conv_id:
        return
    
    conversations = load_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        return
    
    team_id = conv.get("team_id")
    if not team_id:
        return  # 不属于任何团队
    
    agents = conv.get("agents", [])
    agent = next((a for a in agents if a["id"] == agent_id), None)
    if not agent:
        return
    
    memory_log = agent.get("memory_log", [])
    if len(memory_log) < 10:
        return  # 记忆太少，不需要同步
    
    # 获取团队级配置
    teams = load_teams()
    team = next((t for t in teams if t["id"] == team_id), None)
    if not team:
        return
    
    team_agents = team.get("agents", [])
    # 在团队级找到同名智能体（按 name 匹配）
    team_agent = next((a for a in team_agents if a.get("name") == agent.get("name")), None)
    if not team_agent:
        return
    
    if "shared_memory" not in team_agent:
        team_agent["shared_memory"] = []
    
    # 取项目级最新的记忆，去重后上传到团队级
    existing_contents = [m.get("content", "")[:50] for m in team_agent["shared_memory"]]
    for mem in memory_log[-5:]:  # 同步最近5条
        if mem.get("content", "")[:50] not in existing_contents:
            team_agent["shared_memory"].append({
                "type": mem.get("type", "fact"),
                "content": mem.get("content", ""),
                "source_project": conv_id,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
    
    # 团队级记忆上限100条
    if len(team_agent["shared_memory"]) > 100:
        team_agent["shared_memory"] = team_agent["shared_memory"][-100:]
    
    save_teams(teams)


def inject_team_memory_to_agent(conv_id: str):
    """P0-2: 新项目创建时，将团队级共享记忆注入到项目级智能体。
    
    在创建新对话/项目时调用。
    """
    if not conv_id:
        return
    
    conversations = load_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None)
    if not conv:
        return
    
    team_id = conv.get("team_id")
    if not team_id:
        return
    
    teams = load_teams()
    team = next((t for t in teams if t["id"] == team_id), None)
    if not team:
        return
    
    team_agents = team.get("agents", [])
    proj_agents = conv.get("agents", [])
    
    changed = False
    for pa in proj_agents:
        # 按 name 匹配团队级智能体
        ta = next((a for a in team_agents if a.get("name") == pa.get("name")), None)
        if ta and ta.get("shared_memory"):
            # 初始化项目级 memory_log，注入团队级共享记忆
            if "memory_log" not in pa:
                pa["memory_log"] = []
            # 去重添加
            existing = [m.get("content", "")[:50] for m in pa["memory_log"]]
            for sm in ta["shared_memory"]:
                if sm.get("content", "")[:50] not in existing:
                    pa["memory_log"].append({
                        "id": "mem_" + uuid.uuid4().hex[:8],
                        "type": sm.get("type", "fact"),
                        "content": sm.get("content", ""),
                        "source_task_id": "",
                        "created_at": sm.get("created_at", ""),
                    })
                    changed = True
    
    if changed:
        save_conversations(conversations)


def build_conversation_history(conv_id: str, system_prompt: str, current_user_msg: str = None, max_history: int = 20, root_path: str = "", target_agent_id: str = "", for_main_agent: bool = False, max_tokens: int = 30000, context_window: int = 0, agent: dict = None) -> list:
    """从历史消息构建对话上下文，返回 OpenAI 格式的 messages 数组。
    system_prompt: 系统提示词
    current_user_msg: 当前用户消息（如果不传则只构建历史）
    max_history: 最多保留多少轮历史消息（user+agent算一轮）
    root_path: 项目根目录，会追加到系统提示中告诉智能体
    target_agent_id: 如果指定，只加载该智能体的对话历史（用于 direct 模式）
    for_main_agent: 如果为 True，构建主智能体上下文时压缩子智能体回复（只保留摘要），
                    避免子智能体长回复淹没主智能体的规则约束（M1 机制）
    max_tokens: 上下文 token 预算上限（M3 机制），超过则从最早历史开始裁剪，
                始终保留 system 消息和最近 3 轮对话
    context_window: 模型上下文窗口大小（token数）。如果 >0，会覆盖 max_tokens 作为 M3 截断阈值，
                    并预留 max_tokens（输出预算）和 2000（安全边际）。
                    例如 context_window=131072, max_tokens=8000 → 截断阈值=121072
    agent: 智能体对象（可选），传入时会注入该智能体的历史记忆（P0-1 记忆系统）
    """
    # 如果指定了 context_window，动态计算截断阈值
    if context_window > 0:
        # 预留输出 token 和安全边际
        max_tokens = max(context_window - 8000 - 2000, 30000)  # 至少 30000，避免过小
    # 如果有项目根目录，追加到系统提示
    if root_path:
        system_prompt = system_prompt + f"\n\n## 当前项目根目录\n{root_path}\n所有文件操作都必须使用这个目录下的路径。"
    else:
        system_prompt = system_prompt + "\n\n## 当前项目根目录\n未设置工作目录，你无法操作文件，只能和用户聊天。"
    
    # P0-1: 注入智能体历史记忆到系统提示词
    if agent and isinstance(agent, dict):
        memory_text = format_memory_for_prompt(agent)
        if memory_text:
            system_prompt = system_prompt + memory_text
    elif conv_id:
        # 没传 agent 对象时，尝试从 conversations 中查找
        lookup_id = target_agent_id if target_agent_id else ("main" if for_main_agent else "")
        if lookup_id:
            convs = load_conversations()
            conv = next((c for c in convs if c["id"] == conv_id), None)
            if conv and conv.get("agents"):
                found_agent = next((a for a in conv["agents"] if a["id"] == lookup_id), None)
                if found_agent:
                    memory_text = format_memory_for_prompt(found_agent)
                    if memory_text:
                        system_prompt = system_prompt + memory_text
    
    messages = [{"role": "system", "content": system_prompt}]
    
    if not conv_id:
        if current_user_msg:
            messages.append({"role": "user", "content": current_user_msg})
        return messages
    
    # 获取该对话的所有历史消息（已按时间顺序保存）
    all_msgs = load_messages()
    conv_msgs = [m for m in all_msgs if m.get("conversation_id") == conv_id]
    
    # 如果指定了 target_agent_id（direct模式），只保留该智能体和发给它的用户消息
    if target_agent_id:
        filtered = []
        for m in conv_msgs:
            mid = m.get("agent_id", "")
            role = m.get("role", "")
            # 保留：发给该智能体的用户消息，或该智能体的回复
            if role == "user" and mid == target_agent_id:
                filtered.append(m)
            elif role == "agent" and mid == target_agent_id:
                filtered.append(m)
        conv_msgs = filtered
    
    # 按时间排序（虽然保存时应该已经是顺序的，但保险起见）
    conv_msgs.sort(key=lambda x: x.get("time", ""))
    
    # 只保留最近的消息（避免 token 超限）
    # max_history 是消息条数，不是轮数
    history_msgs = conv_msgs[-max_history:] if len(conv_msgs) > max_history else conv_msgs
    
    for msg in history_msgs:
        role = "user" if msg.get("role") == "user" else "assistant"
        content = msg.get("content", "")
        if content:
            # M1 机制：为主智能体构建历史时，压缩子智能体的回复
            # 子智能体回复只保留前 200 字 + 摘要提示，完整内容仍在 messages.json 中可查
            if for_main_agent and role == "assistant" and msg.get("agent_id", "") != "main":
                if len(content) > 200:
                    content = content[:200] + f"\n\n[子智能体完整回复共 {len(content)} 字，已存入消息记录，如需详情可调用 read_file 读取任务文件夹]"
            messages.append({"role": role, "content": content})
    
    # 添加当前用户消息
    if current_user_msg:
        messages.append({"role": "user", "content": current_user_msg})
    
    # M3 机制：按 token 数智能截断（P0-3: 摘要压缩 + P1-4: 保留工具调用消息）
    # 始终保留：system 消息 + 最近 3 轮（6 条）+ 当前用户消息
    # 中间历史按 token 预算动态保留
    # P0-3: 被截断的消息生成摘要注入 system 消息
    # P1-4: 优先保留含 tool_call 的消息，防止多轮后工具调用退化
    if count_messages_tokens(messages) > max_tokens:
        system_msg = messages[0]
        current_msg = messages[-1] if current_user_msg else None
        # 保留最近 6 条历史（3 轮），如果不足 6 条则全保留
        keep_recent = 6
        if current_user_msg:
            recent_msgs = messages[-(keep_recent + 1):-1] if len(messages) > keep_recent + 1 else messages[1:-1]
            middle_msgs = messages[1:-(keep_recent + 1)] if len(messages) > keep_recent + 1 else []
        else:
            recent_msgs = messages[-keep_recent:] if len(messages) > keep_recent else messages[1:]
            middle_msgs = messages[1:-keep_recent] if len(messages) > keep_recent else []
        
        # P1-4: 优先保留含工具调用关键词的消息（防止多轮后工具调用退化）
        # 标记含工具调用的消息（通过检查是否包含工具相关关键词）
        tool_keywords = ["tool_call", "tool_result", "write_file", "read_file", "edit_file", 
                         "create_sub_task", "submit_task_result", "list_tasks", "create_team_member",
                         "grep", "glob", "move_file", "copy_file", "list_directory"]
        
        def has_tool_content(msg):
            content = msg.get("content", "")
            return any(kw in content for kw in tool_keywords)
        
        # 将中间消息分为含工具调用和不含工具调用两类
        tool_msgs = [m for m in middle_msgs if has_tool_content(m)]
        non_tool_msgs = [m for m in middle_msgs if not has_tool_content(m)]
        
        # 从最早的非工具消息开始删除，直到 token 数达标
        while non_tool_msgs and count_messages_tokens([system_msg] + tool_msgs + non_tool_msgs + recent_msgs + ([current_msg] if current_msg else [])) > max_tokens:
            non_tool_msgs.pop(0)
        
        # 如果删完非工具消息后仍然超限，从最早的工具消息开始删除
        while tool_msgs and count_messages_tokens([system_msg] + tool_msgs + non_tool_msgs + recent_msgs + ([current_msg] if current_msg else [])) > max_tokens:
            tool_msgs.pop(0)
        
        # P0-3: 对被截断的消息生成简要摘要，注入 system 消息
        # 收集被删除的消息（原 middle_msgs 中不在保留列表里的）
        kept_contents = set(m.get("content", "")[:50] for m in tool_msgs + non_tool_msgs)
        truncated_msgs = [m for m in middle_msgs if m.get("content", "")[:50] not in kept_contents]
        
        if truncated_msgs:
            summary_lines = ["\n\n## 📋 早期对话摘要（已被压缩）"]
            for m in truncated_msgs:
                role = "用户" if m.get("role") == "user" else "智能体"
                content = m.get("content", "")
                # 用户消息完整保留（通常较短且重要）
                if role == "用户":
                    summary_lines.append(f"- 用户要求: {content[:200]}")
                else:
                    # 智能体消息只保留前100字
                    summary_lines.append(f"- {role}回复: {content[:100]}")
            
            summary_text = "\n".join(summary_lines)
            # 摘要太长时再截断（最多2000字）
            if len(summary_text) > 2000:
                summary_text = summary_text[:2000] + "\n... (更多早期对话已省略)"
            system_msg = {"role": "system", "content": system_msg["content"] + summary_text}
        
        messages = [system_msg] + tool_msgs + non_tool_msgs + recent_msgs
        if current_msg:
            messages.append(current_msg)
    
    return messages


def check_pending_todos(conv_id: str, root_path: str) -> str:
    """检查当前对话未完成的 TODO 清单，返回提醒文本（M2 系统层强制机制）。
    
    在主智能体每轮回复前调用。如果有未完成项，返回提醒文本，
    由调用方注入到用户消息前，让主智能体看到"还有事没做完"。
    如果没有未完成项，返回空字符串。
    """
    if not conv_id or not root_path:
        return ""
    
    todos_dir = Path(root_path) / ".agent" / "todos"
    if not todos_dir.exists():
        return ""
    
    reminders = []
    try:
        for fname in sorted(os.listdir(todos_dir)):
            if not fname.endswith(".json"):
                continue
            try:
                with open(todos_dir / fname, "r", encoding="utf-8") as f:
                    todo = json.load(f)
            except Exception:
                continue
            
            if todo.get("conversation_id") != conv_id:
                continue
            if todo.get("status") != "in_progress":
                continue
            
            pending_items = [item for item in todo["items"] if item.get("status") != "completed"]
            if not pending_items:
                continue
            
            completed_count = len(todo["items"]) - len(pending_items)
            reminders.append(f"📋 TODO 清单「{todo.get('title', '未命名')}」"
                             f"进度 {completed_count}/{len(todo['items'])}，"
                             f"还有 {len(pending_items)} 项未完成：")
            for item in pending_items:
                status_tag = item.get("status", "pending")
                reminders.append(f"  - [{status_tag}] {item.get('content', '')}")
            reminders.append("请继续推进未完成的步骤，或明确说明为何停止。")
    except Exception:
        return ""
    
    if not reminders:
        return ""
    
    return "⚠️ 系统提醒：你有未完成的 TODO 清单\n" + "\n".join(reminders) + "\n"


def check_pending_tasks(conv_id: str, root_path: str, conv_agents: list = None) -> str:
    """检查当前项目是否有 pending 状态的任务，返回提醒文本。
    
    在主智能体每轮回复前调用。如果有 pending 任务，返回提醒文本，
    让主智能体知道"还有任务没做完"，从而主动续接。
    如果没有 pending 任务，返回空字符串。
    """
    if not conv_id or not root_path:
        return ""
    
    tasks_dir = Path(root_path) / ".agent" / "tasks"
    if not tasks_dir.exists():
        return ""
    
    pending_tasks = []
    try:
        for d in tasks_dir.iterdir():
            if not d.is_dir():
                continue
            meta_file = d / "meta.json"
            if not meta_file.exists():
                continue
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                if meta.get("status") == "pending":
                    pending_tasks.append(meta)
            except Exception:
                continue
    except Exception:
        return ""
    
    if not pending_tasks:
        return ""
    
    # 找智能体名字
    def _agent_name(aid):
        if conv_agents:
            for a in conv_agents:
                if a["id"] == aid:
                    return a["name"]
        return aid
    
    lines = [f"⚠️ 系统提醒：当前项目还有 {len(pending_tasks)} 个待处理（pending）任务未完成："]
    for t in pending_tasks:
        agent_nm = _agent_name(t.get("agent_id", ""))
        desc = t.get("description", "")[:50]
        lines.append(f"  - {t['id']} → @{agent_nm}：{desc}")
    lines.append("请用 list_tasks 工具查看完整状态，并 @对应智能体 推进未完成的任务。")
    lines.append("如果这些任务已经不需要了，请说明原因。")
    return "\n".join(lines) + "\n"


def build_isolated_context(system_prompt: str, task_description: str, root_path: str = "",
                           from_agent_name: str = "", original_user_msg: str = "",
                           task_id: str = "") -> list:
    """构建隔离的子智能体上下文（阶段2：上下文隔离）。

    子智能体不继承主智能体的全部历史，只接收：
    - 自己的 system_prompt（含项目根目录信息）
    - 任务描述（来自调用方的 @mention 文本）
    - 原始用户需求（简短，便于理解大方向）
    - 任务文件指引（如有 task_id）

    这样避免 token 爆炸：子智能体间通过文件（output→input）传递上下文，而非历史消息。
    主智能体仍使用 build_conversation_history 保留完整上下文。
    """
    if root_path:
        full_prompt = system_prompt + f"\n\n## 当前项目根目录\n{root_path}\n所有文件操作都必须使用这个目录下的路径。"
    else:
        full_prompt = system_prompt + "\n\n## 当前项目根目录\n未设置工作目录，你无法操作文件，只能聊天。"

    messages = [{"role": "system", "content": full_prompt}]

    parts = []
    if from_agent_name:
        parts.append(f"【{from_agent_name}给你的任务】")
    else:
        parts.append("【你的任务】")

    if task_description:
        parts.append(task_description)

    if original_user_msg:
        parts.append(f"\n\n【原始用户需求】{original_user_msg}")

    if task_id:
        parts.append(f"\n\n📋 任务详情请查看 `.agent/tasks/{task_id}/TASK.md`，输入文件在 `.agent/tasks/{task_id}/input/` 目录（只读），产出请写到 `.agent/tasks/{task_id}/output/` 目录。")

    parts.append("\n\n完成后请用 submit_task_result 工具提交结果摘要和产出文件路径。如需澄清可 @主智能体 或 @你的上级。")

    messages.append({"role": "user", "content": "".join(parts)})

    return messages


def call_llm(system_prompt: str, user_message: str, agent: dict = None, history_messages: list = None, default_config_id: str = "", thinking_override: Optional[bool] = None) -> str:
    """调用大模型，返回回复文本。
    如果智能体有独立的 model_config，优先使用；否则用全局配置。
    history_messages: 可选，直接传入完整的 messages 数组（用于带上下文的对话）；
                      如果不传，则只使用 system_prompt + user_message（单轮）。
    """
    # 复用统一的配置获取逻辑
    client, api_cfg, error = get_llm_client_and_config(agent, default_config_id, thinking_override)
    if error:
        return error

    if not api_cfg.get("api_key") or not api_cfg.get("base_url") or not api_cfg.get("model"):
        return "️ 还没配置 API 密钥，请在左下角「API 设置」里填入配置后再试。"

    try:
        
        # 构建请求参数：如果传入了历史消息就用历史，否则构建单轮
        if history_messages and len(history_messages) > 0:
            # 确保第一条是 system，替换成当前的 system_prompt
            msgs = list(history_messages)
            if msgs[0]["role"] == "system":
                msgs[0] = {"role": "system", "content": system_prompt}
            else:
                msgs.insert(0, {"role": "system", "content": system_prompt})
        else:
            msgs = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]
        
        request_params = {
            "model": api_cfg["model"],
            "messages": msgs,
            "temperature": api_cfg.get("temperature", 0.7),
            "max_tokens": api_cfg.get("max_tokens", 2000),
        }
        
        # 如果启用思考模式，尝试添加 extra_body（部分 API 不支持会回退）
        if api_cfg.get("enable_thinking"):
            try:
                request_params["extra_body"] = {"enable_thinking": True}
                response = client.chat.completions.create(**request_params)
            except Exception:
                # extra_body 不支持时，去掉重试
                del request_params["extra_body"]
                response = client.chat.completions.create(**request_params)
        else:
            response = client.chat.completions.create(**request_params)
        
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ 调用大模型出错：{str(e)}"


def test_api_connection(cfg: dict) -> dict:
    """测试 API 连接是否正常，返回测试结果"""
    try:
        client = OpenAI(
            base_url=cfg["base_url"],
            api_key=cfg["api_key"],
        )
        response = client.chat.completions.create(
            model=cfg["model"],
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
            temperature=0,
        )
        content = response.choices[0].message.content or ""
        return {"ok": True, "message": "连接成功！模型返回：" + content[:30]}
    except Exception as e:
        return {"ok": False, "message": "连接失败：" + str(e)}


def get_llm_client_and_config(agent: dict = None, default_config_id: str = "", thinking_override: Optional[bool] = None) -> tuple:
    """获取 LLM 客户端和配置，返回 (client, api_cfg, error_message)。
    
    优先级（从高到低）：
    1. 智能体自己的 model_config（如果配置了）
    2. 会话级默认配置 default_config_id（前端传入，智能体未配置时用这个）
    3. 全局默认配置 load_api_config()（兜底）
    
    thinking_override（非 None 时）覆盖任何来源的 enable_thinking 值，
    用于前端"思考模式开关"临时控制。
    """
    api_cfg = None
    
    # 优先用智能体自己的模型配置
    if agent and agent.get("model_config"):
        mc = agent["model_config"]
        config_id = mc.get("config_id")
        if config_id:
            configs_data = load_model_configs()
            real_cfg = next((c for c in configs_data if c["id"] == config_id), None)
            if real_cfg:
                # 检查配置是否被禁用（付费控制：到期后可禁用所有配置）
                if real_cfg.get("enabled") is False:
                    return None, None, "❌ 该模型配置已被禁用，请联系开发者获取授权。"
                mc = real_cfg
            else:
                return None, None, "❌ 该智能体引用的模型配置已被删除，请在智能体菜单中重新选择模型配置。"
        api_cfg = {
            "base_url": mc.get("base_url", ""),
            "api_key": mc.get("api_key", ""),
            "model": mc.get("model", ""),
            "temperature": mc.get("temperature", 0.7),
            "max_tokens": mc.get("max_tokens", 2000),
            "enable_thinking": mc.get("enable_thinking", False),
            "context_window": mc.get("context_window", 131072),
        }
    elif default_config_id:
        # 会话级默认配置（前端输入框上方的模型选择）
        configs_data = load_model_configs()
        real_cfg = next((c for c in configs_data if c["id"] == default_config_id), None)
        if real_cfg:
            # 检查配置是否被禁用
            if real_cfg.get("enabled") is False:
                return None, None, "❌ 该模型配置已被禁用，请联系开发者获取授权。"
            api_cfg = {
                "base_url": real_cfg.get("base_url", ""),
                "api_key": real_cfg.get("api_key", ""),
                "model": real_cfg.get("model", ""),
                "temperature": real_cfg.get("temperature", 0.7),
                "max_tokens": real_cfg.get("max_tokens", 2000),
                "enable_thinking": real_cfg.get("enable_thinking", False),
                "context_window": real_cfg.get("context_window", 131072),
            }
        else:
            return None, None, "❌ 选中的默认模型配置已被删除，请重新选择。"
    else:
        # 兜底：全局默认配置
        api_cfg = load_api_config()
        api_cfg["enable_thinking"] = api_cfg.get("enable_thinking", False)
        api_cfg["context_window"] = api_cfg.get("context_window", 131072)
    
    # 前端思考模式开关覆盖（最高优先级）
    if thinking_override is not None:
        api_cfg["enable_thinking"] = thinking_override
    
    if not api_cfg.get("api_key") or not api_cfg.get("base_url") or not api_cfg.get("model"):
        return None, None, "️ 还没配置 API 密钥，请在左下角「API 设置」里填入配置后再试。"

    client = OpenAI(
        base_url=api_cfg["base_url"],
        api_key=api_cfg["api_key"],
    )
    return client, api_cfg, None


def call_llm_stream(system_prompt: str, messages: list, agent: dict = None, default_config_id: str = "", thinking_override: Optional[bool] = None):
    """流式调用大模型，返回 generator，逐块产出文本"""
    client, api_cfg, error = get_llm_client_and_config(agent, default_config_id, thinking_override)
    if error:
        yield error
        return

    # 构建 messages 数组
    msgs = list(messages) if messages else []
    # 确保第一条是 system
    if not msgs or msgs[0]["role"] != "system":
        msgs.insert(0, {"role": "system", "content": system_prompt})
    else:
        msgs[0] = {"role": "system", "content": system_prompt}

    request_params = {
        "model": api_cfg["model"],
        "messages": msgs,
        "temperature": api_cfg.get("temperature", 0.7),
        "max_tokens": api_cfg.get("max_tokens", 2000),
        "stream": True,
    }

    try:
        if api_cfg.get("enable_thinking"):
            try:
                request_params["extra_body"] = {"enable_thinking": True}
                stream = client.chat.completions.create(**request_params)
            except Exception:
                del request_params["extra_body"]
                stream = client.chat.completions.create(**request_params)
        else:
            stream = client.chat.completions.create(**request_params)

        for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content
    except Exception as e:
        yield f"\n\n❌ 调用大模型出错：{str(e)}"


def call_llm_stream_with_tools(system_prompt, messages_list, agent, root_path, conv_id="", max_tool_rounds=12, default_config_id: str = "", thinking_override: Optional[bool] = None):
    """
    流式调用 LLM，支持 function calling 工具循环。
    这是一个 generator，产出 SSE 事件元组：
      ("token", {"agent_id": ..., "content": ...})
      ("tool_start", {"agent_id": ..., "tool_name": ..., "tool_args": ...})
      ("tool_end", {"agent_id": ..., "tool_name": ..., "result": ...})
      ("error", {"message": ...})
      ("done", {"full_content": ...})
    """
    client, api_cfg, error = get_llm_client_and_config(agent, default_config_id, thinking_override)
    if error:
        yield ("error", {"message": error})
        return

    agent_id = agent["id"]
    can_use_tools = agent.get("can_use_tools", False) and bool(root_path)
    
    # 构建 messages
    msgs = list(messages_list) if messages_list else []
    if not msgs or msgs[0]["role"] != "system":
        msgs.insert(0, {"role": "system", "content": system_prompt})
    else:
        msgs[0] = {"role": "system", "content": system_prompt}
    
    # 如果有项目根目录，在 system prompt 里追加说明
    if root_path:
        msgs[0]["content"] += f"\n\n## 当前项目根目录\n{root_path}\n\n工具调用中的 path 参数请使用相对于项目根目录的路径（如 '.' 表示根目录，'docs' 表示 docs 子文件夹）。"
    
    full_content = ""
    # 根据智能体类型过滤工具 schema：
    # - 主智能体（main）：可用全部工具
    # - 子智能体：按其 template 字段对应的工具集过滤（默认 worker）
    # - 技能工具：根据 enabled_skills 合并额外的工具
    # - 子代理调用：can_invoke_sub_agent=True 时加入 invoke_sub_agent 工具
    if can_use_tools:
        if agent_id == "main":
            allowed_tool_names = set(t["function"]["name"] for t in TOOL_DEFINITIONS)
        else:
            # 优先用智能体记录的 template 对应的工具集
            template_name = agent.get("template", "worker") if isinstance(agent, dict) else "worker"
            tpl = ROLE_TEMPLATES.get(template_name, ROLE_TEMPLATES["worker"])
            allowed_tool_names = set(tpl["tools"])

        # 合并技能附带的工具
        enabled_skills = agent.get("enabled_skills", []) if isinstance(agent, dict) else []
        if enabled_skills:
            for skill_id in enabled_skills:
                skill = sb_get_skill(skill_id)
                if skill:
                    for t in skill.get("tools", []):
                        allowed_tool_names.add(t)

        # 如果允许调用子代理，加入 invoke_sub_agent 工具
        if isinstance(agent, dict) and agent.get("can_invoke_sub_agent", False):
            allowed_tool_names.add("invoke_sub_agent")

        tools = [t for t in TOOL_DEFINITIONS if t["function"]["name"] in allowed_tool_names]

        # 注入技能的 system_prompt_fragment
        if enabled_skills:
            skill_fragments = []
            for skill_id in enabled_skills:
                skill = sb_get_skill(skill_id)
                if skill and skill.get("system_prompt_fragment"):
                    skill_fragments.append(f"### 技能：{skill['name']}\n{skill['system_prompt_fragment']}")
            if skill_fragments:
                msgs[0]["content"] += "\n\n## 已启用技能\n" + "\n\n".join(skill_fragments)
    else:
        tools = None
    
    for round_idx in range(max_tool_rounds):
        request_params = {
            "model": api_cfg["model"],
            "messages": msgs,
            "temperature": api_cfg.get("temperature", 0.7),
            "max_tokens": api_cfg.get("max_tokens", 2000),
            "stream": True,
        }
        if tools:
            request_params["tools"] = tools
            request_params["tool_choice"] = "auto"
        
        stream = None
        try:
            if api_cfg.get("enable_thinking"):
                try:
                    request_params["extra_body"] = {"enable_thinking": True}
                    stream = client.chat.completions.create(**request_params)
                except Exception:
                    del request_params["extra_body"]
                    stream = client.chat.completions.create(**request_params)
            else:
                stream = client.chat.completions.create(**request_params)
        except Exception as e:
            yield ("error", {"message": f"调用大模型出错：{str(e)}"})
            return
        
        # 收集流式响应
        collected_content = ""
        tool_calls_data = {}  # {index: {id, name, arguments_str}}
        finish_reason = None
        
        try:
            for chunk in stream:
                if not chunk.choices or len(chunk.choices) == 0:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
                
                # 收集文本内容
                if delta and delta.content:
                    collected_content += delta.content
                    yield ("token", {"agent_id": agent_id, "content": delta.content})
                
                # 收集工具调用
                if delta and delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_data:
                            tool_calls_data[idx] = {"id": tc.id or "", "name": "", "arguments_str": ""}
                        if tc.id:
                            tool_calls_data[idx]["id"] = tc.id
                        if tc.function and tc.function.name:
                            tool_calls_data[idx]["name"] += tc.function.name
                        if tc.function and tc.function.arguments:
                            tool_calls_data[idx]["arguments_str"] += tc.function.arguments
        except Exception as e:
            yield ("error", {"message": f"流式读取出错：{str(e)}"})
            return
        
        full_content += collected_content
        
        # 判断是否需要调用工具
        if finish_reason == "tool_calls" and tool_calls_data and can_use_tools:
            # 先解析所有工具参数（含容错），确保 assistant_msg 里的 arguments 是合法 JSON
            import json as _json
            parsed_calls = []  # [(tc_id, name, args_dict, args_json_str, parse_error)]
            for idx in sorted(tool_calls_data.keys()):
                tc = tool_calls_data[idx]
                tool_args = {}
                args_json_str = "{}"
                parse_error = None
                raw = tc["arguments_str"].strip()
                if raw:
                    # 尝试直接解析
                    try:
                        tool_args = _json.loads(raw)
                        args_json_str = raw
                    except Exception as parse_ex:
                        parse_error = str(parse_ex)
                        # 容错1：移除 markdown 代码块标记
                        cleaned = raw
                        if cleaned.startswith("```"):
                            cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
                            if cleaned.endswith("```"):
                                cleaned = cleaned[:-3]
                            cleaned = cleaned.strip()
                            try:
                                tool_args = _json.loads(cleaned)
                                args_json_str = cleaned
                                parse_error = None
                            except Exception:
                                pass
                        # 容错2：提取 { ... } 块
                        if parse_error:
                            start = raw.find("{")
                            end = raw.rfind("}")
                            if start >= 0 and end > start:
                                try:
                                    tool_args = _json.loads(raw[start:end+1])
                                    args_json_str = raw[start:end+1]
                                    parse_error = None
                                except Exception:
                                    pass
                        # 容错3：实在解析不了，用空对象占位（保证 args_json_str 是合法 JSON，避免下一轮 API 400）
                        if parse_error:
                            args_json_str = "{}"
                parsed_calls.append((tc["id"], tc["name"], tool_args, args_json_str, parse_error))
            
            # 把 assistant 的回复（含 tool_calls）加入消息历史 —— arguments 永远是合法 JSON
            assistant_msg = {"role": "assistant", "content": collected_content or None, "tool_calls": []}
            for tc_id, name, args_dict, args_json_str, _ in parsed_calls:
                assistant_msg["tool_calls"].append({
                    "id": tc_id,
                    "type": "function",
                    "function": {"name": name, "arguments": args_json_str}
                })
            msgs.append(assistant_msg)
            
            # 执行每个工具调用
            for tc_id, tool_name, tool_args, _, parse_error in parsed_calls:
                # 通知前端工具开始执行
                yield ("tool_start", {
                    "agent_id": agent_id,
                    "tool_name": tool_name,
                    "tool_args": tool_args
                })
                
                # 执行工具
                if parse_error:
                    # 参数解析失败，不执行工具，返回错误提示让 LLM 重试
                    result = f"❌ 工具参数解析失败：{parse_error}。你传入的参数不是合法 JSON。请重新调用工具，确保 arguments 是严格的 JSON 格式（键值对用双引号）。"
                else:
                    result = execute_tool(tool_name, tool_args, root_path, agent_id, conv_id, agent=agent, default_config_id=default_config_id)
                
                # 通知前端工具执行完成
                yield ("tool_end", {
                    "agent_id": agent_id,
                    "tool_name": tool_name,
                    "result": result
                })
                
                # 技能使用计数：检查这个工具是否属于智能体启用的技能
                if enabled_skills and not parse_error:
                    try:
                        for skill_id in enabled_skills:
                            skill = sb_get_skill(skill_id)
                            if skill and tool_name in skill.get("tools", []):
                                sb_increment_use_count([skill_id])
                                break  # 一个工具只属于一个技能，计数一次即可
                    except Exception:
                        pass  # 计数失败不影响主流程
                
                # 把工具结果加入消息历史
                msgs.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": result
                })
            
            # 继续下一轮循环，让 LLM 根据工具结果继续
            continue
        else:
            # 没有工具调用，结束
            break
    else:
        # 循环正常结束（达到 max_tool_rounds 上限），告知智能体并让它收尾
        msgs.append({
            "role": "user",
            "content": "【系统提示】你已达到工具调用轮次上限。请立即用文字总结当前进度，不要继续调用工具。如果还有未完成的操作，说明还需要哪些步骤。"
        })
        # 再请求一次让 LLM 做总结
        try:
            final_stream = client.chat.completions.create(
                model=api_cfg["model"],
                messages=msgs,
                temperature=api_cfg.get("temperature", 0.7),
                max_tokens=api_cfg.get("max_tokens", 2000),
                stream=True,
            )
            for chunk in final_stream:
                if not chunk.choices or len(chunk.choices) == 0:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta
                if delta and delta.content:
                    full_content += delta.content
                    yield ("token", {"agent_id": agent_id, "content": delta.content})
        except Exception as e:
            yield ("error", {"message": f"收尾总结时出错：{str(e)}"})
    
    yield ("done", {"agent_id": agent_id, "full_content": full_content})


def collect_stream_sync(system_prompt, messages_list, agent, root_path=None, conv_id="", default_config_id: str = "", thinking_override: Optional[bool] = None):
    """同步收集完整回复（用于线程池并发调用子智能体），返回 (full_content, tool_events)"""
    full_content = ""
    tool_events = []
    for event_type, data in call_llm_stream_with_tools(system_prompt, messages_list, agent, root_path, conv_id, default_config_id=default_config_id, thinking_override=thinking_override):
        if event_type == "token":
            full_content += data.get("content", "")
        elif event_type in ("tool_start", "tool_end"):
            tool_events.append((event_type, data))
        elif event_type == "error":
            full_content += "\n\n❌ " + data.get("message", "出错了")
    return full_content, tool_events


def detect_hallucination(content, root_path, agent_id="main"):
    """检测智能体回复中是否引用了不存在的任务 ID（防幻觉第4层）。
    
    返回 (fake_tasks, warning_message)，如果没有幻觉返回 ([], "")。
    """
    if not content or not root_path:
        return [], ""
    import re as _re
    # 任务 ID 格式：task_{timestamp}_{hex6}，如 task_1784686428_03690a
    # 使用精确正则避免匹配 task_result / task_id / task_meta 等工具名和变量名
    mentioned_tasks = set(_re.findall(r'task_\d{8,}_[a-f0-9]{6}', content))
    if not mentioned_tasks:
        return [], ""
    tasks_base = Path(root_path) / ".agent" / "tasks"
    fake_tasks = []
    for tid in mentioned_tasks:
        if not (tasks_base / tid).exists():
            fake_tasks.append(tid)
    if not fake_tasks:
        return [], ""
    warning = (
        f"⚠️【系统检测到幻觉】智能体 {agent_id} 的回复中引用了以下任务 ID，但它们在 .agent/tasks/ 目录下不存在：\n"
        f"{', '.join(fake_tasks)}\n"
        f"这些任务 ID 不是 create_task 工具真实返回的。"
    )
    return fake_tasks, warning


@app.post("/api/chat/stream")
async def chat_stream(msg: ChatMessage) -> StreamingResponse:
    """流式发送消息，SSE 格式返回。支持多智能体并发回复和工具调用。
    事件格式：
    - event: agent_start, data: {"agent_id": "..."}
    - event: token, data: {"agent_id": "...", "content": "..."}
    - event: tool_start, data: {"agent_id": "...", "tool_name": "...", "tool_args": {...}}
    - event: tool_end, data: {"agent_id": "...", "tool_name": "...", "result": "..."}
    - event: agent_end, data: {"agent_id": "...", "full_content": "..."}
    - event: error, data: {"message": "..."}
    - event: done, data: {}
    """
    conv_id = msg.conversation_id
    
    # 获取项目级智能体配置（每次都重新加载，避免使用全局缓存）
    conversations = load_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None) if conv_id else None
    
    root_path = ""
    if conv:
        conv_agents = _get_conv_agents_with_main(conv.get("agents"))
        root_path = conv.get("root_path", "")
    else:
        conv_agents = load_agents()
    
    agent = next((a for a in conv_agents if a["id"] == msg.agent_id), None)
    if not agent:
        async def error_gen():
            yield f"event: error\ndata: {json_module.dumps({'message': '找不到这个智能体'}, ensure_ascii=False)}\n\n"
        return StreamingResponse(error_gen(), media_type="text/event-stream")
    
    # 查询当前使用的 context_window（用于 M3 截断阈值）
    # 优先级：智能体自己的模型配置 > 会话级默认配置 > 默认 131072
    current_context_window = 0
    try:
        if agent.get("model_config") and agent["model_config"].get("config_id"):
            configs_data_cw = load_model_configs()
            real_cfg_cw = next((c for c in configs_data_cw if c["id"] == agent["model_config"]["config_id"]), None)
            if real_cfg_cw:
                current_context_window = real_cfg_cw.get("context_window", 131072)
        elif msg.default_config_id:
            configs_data_cw = load_model_configs()
            real_cfg_cw = next((c for c in configs_data_cw if c["id"] == msg.default_config_id), None)
            if real_cfg_cw:
                current_context_window = real_cfg_cw.get("context_window", 131072)
    except Exception:
        pass

    now = time.strftime("%H:%M:%S")

    def generate() -> Generator[str, None, None]:
        # 同步 generator——Starlette 会自动在线程池中运行，不阻塞事件循环
        # 之前用 async def + time.sleep(0) 的方式无法解决同步 LLM 调用阻塞事件循环的问题
        nonlocal agent, conv_agents, msg, conv_id, now, root_path
        import concurrent.futures
        
        messages = load_messages()  # 仅用于读取历史，不用于整体写回
        all_replies = []
        
        # 保存用户消息（原子追加，防止多项目并行时更新丢失）
        user_msg = {
            "id": uuid.uuid4().hex[:12],
            "agent_id": msg.agent_id,
            "role": "user",
            "content": msg.message,
            "time": now,
            "conversation_id": conv_id,
        }
        append_message(user_msg)
        
        # ===== 直接对话模式：只调用指定智能体，不进行链式调度 =====
        if msg.direct:
            sub_prompt = agent.get("system_prompt", f"你是{agent['name']}，{agent['role']}。")
            # 如果是主智能体，注入当前团队信息
            if agent["id"] == "main":
                team_ctx = get_team_context_for_main(conv_id)
                if team_ctx:
                    sub_prompt = sub_prompt + "\n\n" + team_ctx
            # M2：主智能体注入 TODO 提醒（如果有未完成项）
            # 跨轮续接：注入 pending 任务提醒（如果有未完成任务）
            effective_msg = msg.message
            if agent["id"] == "main":
                todo_reminder = check_pending_todos(conv_id, root_path)
                if todo_reminder:
                    effective_msg = todo_reminder + "\n---\n\n用户消息：" + msg.message
                pending_tasks_reminder = check_pending_tasks(conv_id, root_path, conv_agents)
                if pending_tasks_reminder:
                    effective_msg = pending_tasks_reminder + "\n---\n\n" + effective_msg
            sub_history = build_conversation_history(conv_id, sub_prompt, effective_msg, max_history=20, root_path=root_path, for_main_agent=(agent["id"] == "main"), context_window=current_context_window)
            
            sub_full_content = ""
            sub_tool_events = []
            yield f"event: agent_start\ndata: {json_module.dumps({'agent_id': agent['id']}, ensure_ascii=False)}\n\n"
            
            for event_type, data in call_llm_stream_with_tools(sub_prompt, sub_history, agent, root_path, conv_id, default_config_id=msg.default_config_id, thinking_override=msg.enable_thinking):
                time.sleep(0)
                if event_type == "token":
                    sub_full_content += data.get("content", "")
                    yield f"event: token\ndata: {json_module.dumps(data, ensure_ascii=False)}\n\n"
                elif event_type == "tool_start":
                    sub_tool_events.append(("start", data))
                    yield f"event: tool_start\ndata: {json_module.dumps(data, ensure_ascii=False)}\n\n"
                elif event_type == "tool_end":
                    sub_tool_events.append(("end", data))
                    yield f"event: tool_end\ndata: {json_module.dumps(data, ensure_ascii=False)}\n\n"
                elif event_type == "error":
                    yield f"event: error\ndata: {json_module.dumps(data, ensure_ascii=False)}\n\n"
                elif event_type == "done":
                    sub_full_content = data.get("full_content", sub_full_content)
            
            yield f"event: agent_end\ndata: {json_module.dumps({'agent_id': agent['id'], 'full_content': sub_full_content}, ensure_ascii=False)}\n\n"
            
            # 原子追加子智能体回复（防止多项目并行时更新丢失）
            append_message({
                "id": uuid.uuid4().hex[:12],
                "agent_id": agent["id"],
                "role": "agent",
                "content": sub_full_content,
                "time": time.strftime("%H:%M:%S"),
                "conversation_id": conv_id,
            })
            
            # 防幻觉：对子智能体回复也做 task_id 引用检测
            if agent["id"] != "main":
                fake_tasks, warning = detect_hallucination(sub_full_content, root_path, agent["id"])
                if fake_tasks:
                    yield f"event: hallucination_warning\ndata: {json_module.dumps({'agent_id': agent['id'], 'fake_tasks': fake_tasks, 'warning': warning}, ensure_ascii=False)}\n\n"
            
            # ===== direct 模式下，子智能体 @主智能体 时自动触发主智能体响应 =====
            # 解决「子智能体在右侧抽屉里 @主智能体，主智能体看不到」的问题
            # 只触发一轮，防止无限循环
            main_agent = next((a for a in conv_agents if a["id"] == "main"), None)
            if main_agent and agent["id"] != "main":
                mentioned_mains = extract_mentioned_agents(sub_full_content, [main_agent])
                if mentioned_mains:
                    main_prompt = main_agent.get("system_prompt", f"你是{main_agent['name']}，{main_agent['role']}。")
                    # 构建主智能体的历史上下文（M1：启用摘要模式，压缩子智能体回复）
                    if CORE_RULES not in main_prompt:
                        main_prompt = main_prompt + CORE_RULES
                    main_history = build_conversation_history(conv_id, main_prompt, None, max_history=10, root_path=root_path, for_main_agent=True, context_window=current_context_window)
                    # 把子智能体的汇报作为系统通知注入（不是用户指令）
                    sub_task_msg = (
                        f"【系统通知：{agent['name']} 已完成任务并汇报】\n"
                        f"{sub_full_content}\n\n"
                        f"【你的职责】作为项目经理，基于上述汇报做收尾：向用户通报结果、确认产出归档、或安排下一步。"
                        f"注意：这是团队成员的汇报，不是用户的新指令，回复时不要说\"已收到指令\"。"
                    )
                    main_history.append({"role": "user", "content": sub_task_msg})
                    
                    yield f"event: agent_start\ndata: {json_module.dumps({'agent_id': 'main', 'source': 'sub_report', 'from_agent': agent['id']}, ensure_ascii=False)}\n\n"
                    
                    main_full_content = ""
                    for event_type, data in call_llm_stream_with_tools(main_prompt, main_history, main_agent, root_path, conv_id, default_config_id=msg.default_config_id, thinking_override=msg.enable_thinking):
                        time.sleep(0)
                        # 把事件里的 agent_id 统一改成 main，方便前端区分
                        data["agent_id"] = "main"
                        if event_type == "token":
                            main_full_content += data.get("content", "")
                            yield f"event: token\ndata: {json_module.dumps(data, ensure_ascii=False)}\n\n"
                        elif event_type == "tool_start":
                            yield f"event: tool_start\ndata: {json_module.dumps(data, ensure_ascii=False)}\n\n"
                        elif event_type == "tool_end":
                            yield f"event: tool_end\ndata: {json_module.dumps(data, ensure_ascii=False)}\n\n"
                        elif event_type == "error":
                            yield f"event: error\ndata: {json_module.dumps(data, ensure_ascii=False)}\n\n"
                        elif event_type == "done":
                            main_full_content = data.get("full_content", main_full_content)
                    
                    yield f"event: agent_end\ndata: {json_module.dumps({'agent_id': 'main', 'full_content': main_full_content}, ensure_ascii=False)}\n\n"
                    
                    # 主智能体的回复保存到消息（agent_id='main'，会显示在主聊天框）
                    # reply_to 标记：这是回复给哪个子智能体的，前端抽屉加载历史时能识别
                    # 原子追加（防止多项目并行时更新丢失）
                    append_message({
                        "id": uuid.uuid4().hex[:12],
                        "agent_id": "main",
                        "role": "agent",
                        "content": main_full_content,
                        "time": time.strftime("%H:%M:%S"),
                        "conversation_id": conv_id,
                        "reply_to": agent["id"],
                    })
            
            if conv_id:
                conversations = load_conversations()
                for c in conversations:
                    if c["id"] == conv_id:
                        c["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        break
                save_conversations(conversations)
            
            yield f"event: done\ndata: {json_module.dumps({'replies': [{'agent_id': agent['id'], 'content': sub_full_content}]}, ensure_ascii=False)}\n\n"
            return
        
        # ===== 多轮链式调度核心逻辑 =====
        # 队列中每个元素: {"agent": agent_obj, "task": task_description, "from_agent": 来源智能体id}
        # 用队列实现 BFS 式的链式调度
        queue = [{"agent": agent, "task": msg.message, "from_agent": None}]
        processed_ids = set()  # 已在本次调用中执行过的智能体，防止同一轮重复调用
        max_rounds = 6  # 最多链式调度 6 轮，防止无限循环
        current_round = 0
        # 记录本轮所有智能体的回复，作为下一轮的上下文
        round_replies = []
        
        # 构建智能体查找表
        agent_map = {a["id"]: a for a in conv_agents}
        
        while queue and current_round < max_rounds:
            current_round += 1
            
            # 同一轮的多个智能体可以并发执行
            # 阶段3：从队列取出本轮要执行的任务
            raw_batch = []
            while queue:
                item = queue.pop(0)
                aid = item["agent"]["id"]
                key = f"{aid}_{current_round}"
                if key not in processed_ids:
                    processed_ids.add(key)
                    raw_batch.append(item)
            
            if not raw_batch:
                break
            
            # 合并同一智能体的多个任务（阶段4关键：coordinator 可能同时被多个 L2 @mention）
            # 把同一 agent 的多条任务描述合并成一个，避免 coordinator 只看到第一条汇报
            current_batch = []
            merged_map = {}  # aid -> merged item
            for item in raw_batch:
                aid = item["agent"]["id"]
                if aid not in merged_map:
                    merged_map[aid] = {
                        "agent": item["agent"],
                        "task": item["task"],
                        "from_agent": item["from_agent"],
                        "from_agents": [item["from_agent"]] if item["from_agent"] else []
                    }
                    current_batch.append(merged_map[aid])
                else:
                    existing = merged_map[aid]
                    from_name_extra = agent_map.get(item["from_agent"], {}).get("name", "成员") if item["from_agent"] else "成员"
                    existing["task"] = existing["task"] + f"\n\n---\n\n【{from_name_extra} 的汇报】" + item["task"]
                    if item["from_agent"]:
                        existing["from_agents"].append(item["from_agent"])
            
            if not current_batch:
                break
            
            # 第一轮（通常只有主智能体）：保持真正的流式逐 token 输出
            # 后续轮次：并发收集后分块发送（因为用户已经看到主回复了）
            is_first_round = (current_round == 1)
            
            if is_first_round and len(current_batch) == 1:
                # 第一轮单智能体：真正的流式输出
                item = current_batch[0]
                sub_agent = item["agent"]
                sub_aid = sub_agent["id"]
                sub_prompt = sub_agent.get("system_prompt", f"你是{sub_agent['name']}，{sub_agent['role']}。")
                # 如果是主智能体，注入当前团队信息，让它知道已有成员，避免重复创建
                if sub_aid == "main":
                    team_ctx = get_team_context_for_main(conv_id)
                    if team_ctx:
                        sub_prompt = sub_prompt + "\n\n" + team_ctx
                # M2：主智能体注入 TODO 提醒（如果有未完成项）
                # 跨轮续接：注入 pending 任务提醒（如果有未完成任务）
                effective_task = item["task"]
                if sub_aid == "main":
                    todo_reminder = check_pending_todos(conv_id, root_path)
                    if todo_reminder:
                        effective_task = todo_reminder + "\n---\n\n用户消息：" + item["task"]
                    pending_tasks_reminder = check_pending_tasks(conv_id, root_path, conv_agents)
                    if pending_tasks_reminder:
                        effective_task = pending_tasks_reminder + "\n---\n\n" + effective_task
                sub_history = build_conversation_history(conv_id, sub_prompt, effective_task, max_history=20, root_path=root_path, for_main_agent=(sub_aid == "main"), context_window=current_context_window)
                
                sub_full_content = ""
                sub_tool_events = []
                yield f"event: agent_start\ndata: {json_module.dumps({'agent_id': sub_aid}, ensure_ascii=False)}\n\n"
                
                for event_type, data in call_llm_stream_with_tools(sub_prompt, sub_history, sub_agent, root_path, conv_id, default_config_id=msg.default_config_id, thinking_override=msg.enable_thinking):
                    time.sleep(0)
                    if event_type == "token":
                        sub_full_content += data.get("content", "")
                        yield f"event: token\ndata: {json_module.dumps(data, ensure_ascii=False)}\n\n"
                    elif event_type == "tool_start":
                        sub_tool_events.append(("start", data))
                        yield f"event: tool_start\ndata: {json_module.dumps(data, ensure_ascii=False)}\n\n"
                    elif event_type == "tool_end":
                        sub_tool_events.append(("end", data))
                        yield f"event: tool_end\ndata: {json_module.dumps(data, ensure_ascii=False)}\n\n"
                    elif event_type == "error":
                        yield f"event: error\ndata: {json_module.dumps(data, ensure_ascii=False)}\n\n"
                    elif event_type == "done":
                        sub_full_content = data.get("full_content", sub_full_content)
                
                yield f"event: agent_end\ndata: {json_module.dumps({'agent_id': sub_aid, 'full_content': sub_full_content}, ensure_ascii=False)}\n\n"
                time.sleep(0)
                
                all_replies.append({"agent_id": sub_aid, "content": sub_full_content})
                # 原子追加子智能体回复（防止多项目并行时更新丢失）
                append_message({
                    "id": uuid.uuid4().hex[:12],
                    "agent_id": sub_aid,
                    "role": "agent",
                    "content": sub_full_content,
                    "time": time.strftime("%H:%M:%S"),
                    "conversation_id": conv_id,
                })
                
                # 防幻觉：对子智能体回复也做 task_id 引用检测
                if sub_aid != "main":
                    fake_tasks, warning = detect_hallucination(sub_full_content, root_path, sub_aid)
                    if fake_tasks:
                        yield f"event: hallucination_warning\ndata: {json_module.dumps({'agent_id': sub_aid, 'fake_tasks': fake_tasks, 'warning': warning}, ensure_ascii=False)}\n\n"
                
                round_replies.append({
                    "agent_id": sub_aid,
                    "agent_name": sub_agent["name"],
                    "content": sub_full_content
                })
                
                # 检查 @ 的智能体，加入队列
                # 重要：每次检查前刷新 conv_agents，因为主智能体可能刚用 create_team_member 创建了新成员
                # 不刷新的话，新创建的成员无法被 extract_mentioned_agents 找到，调度会失败
                if conv_id:
                    fresh_convs = load_conversations()
                    fresh_conv = next((c for c in fresh_convs if c["id"] == conv_id), None)
                    if fresh_conv and fresh_conv.get("agents"):
                        conv_agents = fresh_conv["agents"]
                mentioned = extract_mentioned_agents(sub_full_content, conv_agents)
                for mentioned_agent in mentioned:
                    mid = mentioned_agent["id"]
                    if mid == sub_aid:
                        continue
                    task_desc = extract_task_for_agent(sub_full_content, mentioned_agent["name"])
                    key = f"{mid}_{current_round + 1}"
                    if key not in processed_ids:
                        queue.append({
                            "agent": mentioned_agent,
                            "task": task_desc,
                            "from_agent": sub_aid
                        })
            else:
                # 阶段3：并行调度 —— 同层多个智能体并发执行
                parallel_count = min(len(current_batch), MAX_PARALLEL)
                # 通知前端：本批并行执行的智能体列表（用于展示并行状态）
                batch_agents = [{"agent_id": item["agent"]["id"], "agent_name": item["agent"]["name"]} for item in current_batch]
                yield f"event: batch_start\ndata: {json_module.dumps({'round': current_round, 'count': len(current_batch), 'parallel': parallel_count, 'agents': batch_agents}, ensure_ascii=False)}\n\n"
                time.sleep(0)
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_count) as executor:
                    future_to_item = {}
                    
                    for item in current_batch:
                        sub_agent = item["agent"]
                        task_desc = item["task"]
                        from_aid = item["from_agent"]
                        sub_aid = sub_agent["id"]
                        
                        sub_prompt = sub_agent.get("system_prompt", f"你是{sub_agent['name']}，{sub_agent['role']}。")
                        
                        # 阶段2：上下文隔离 —— 子智能体不继承主智能体全部历史，只拿任务描述
                        # 主智能体仍使用完整历史（它需要全局上下文做协调归档）
                        if sub_aid == "main":
                            sub_history = build_conversation_history(conv_id, sub_prompt, None, max_history=15, root_path=root_path, context_window=current_context_window)
                            for reply in round_replies:
                                sub_history.append({"role": "assistant", "content": f"【{reply['agent_name']}】：\n{reply['content']}"})
                            if from_aid is None:
                                sub_task_msg = task_desc
                            else:
                                from_name = agent_map.get(from_aid, {}).get("name", "其他智能体")
                                sub_task_msg = f"【{from_name}给你的任务】{task_desc}\n\n【原始用户需求】{msg.message}"
                            sub_history.append({"role": "user", "content": sub_task_msg})
                        else:
                            # 子智能体：隔离上下文，只拿任务描述 + 原始需求
                            from_name = agent_map.get(from_aid, {}).get("name", "项目经理") if from_aid else "项目经理"
                            sub_history = build_isolated_context(
                                sub_prompt, task_desc, root_path=root_path,
                                from_agent_name=from_name, original_user_msg=msg.message
                            )
                        
                        yield f"event: agent_start\ndata: {json_module.dumps({'agent_id': sub_aid}, ensure_ascii=False)}\n\n"
                        time.sleep(0)
                        
                        future = executor.submit(
                            collect_stream_sync,
                            sub_prompt,
                            sub_history,
                            sub_agent,
                            root_path,
                            conv_id,
                            msg.default_config_id,
                            msg.enable_thinking
                        )
                        future_to_item[future] = {"agent": sub_agent}
                    
                    batch_results = []
                    for future in concurrent.futures.as_completed(future_to_item):
                        item_info = future_to_item[future]
                        sub_agent = item_info["agent"]
                        try:
                            sub_full_content, sub_tool_events = future.result()
                        except Exception as e:
                            sub_full_content = f"❌ 调用出错：{str(e)}"
                            sub_tool_events = []
                        batch_results.append({
                            "agent": sub_agent,
                            "content": sub_full_content,
                            "tool_events": sub_tool_events
                        })
                    
                    # 主智能体优先
                    def sort_key(r):
                        return 0 if r["agent"]["id"] == "main" else 1
                    batch_results.sort(key=sort_key)
                    
                    for result in batch_results:
                        sub_agent = result["agent"]
                        sub_aid = sub_agent["id"]
                        sub_full_content = result["content"]
                        sub_tool_events = result["tool_events"]
                        
                        for te_type, te_data in sub_tool_events:
                            sse_event = "tool_start" if te_type == "start" else "tool_end"
                            yield f"event: {sse_event}\ndata: {json_module.dumps(te_data, ensure_ascii=False)}\n\n"
                            time.sleep(0.003)
                        
                        chunk_size = 3
                        for i in range(0, len(sub_full_content), chunk_size):
                            chunk = sub_full_content[i:i+chunk_size]
                            yield f"event: token\ndata: {json_module.dumps({'agent_id': sub_aid, 'content': chunk}, ensure_ascii=False)}\n\n"
                            time.sleep(0.01)
                        
                        yield f"event: agent_end\ndata: {json_module.dumps({'agent_id': sub_aid, 'full_content': sub_full_content}, ensure_ascii=False)}\n\n"
                        time.sleep(0)
                        
                        all_replies.append({"agent_id": sub_aid, "content": sub_full_content})
                        # 原子追加（防止多项目并行时更新丢失）
                        append_message({
                            "id": uuid.uuid4().hex[:12],
                            "agent_id": sub_aid,
                            "role": "agent",
                            "content": sub_full_content,
                            "time": time.strftime("%H:%M:%S"),
                            "conversation_id": conv_id,
                        })
                        
                        # 防幻觉：对并行调度的子智能体回复也做检测
                        if sub_aid != "main":
                            fake_tasks, warning = detect_hallucination(sub_full_content, root_path, sub_aid)
                            if fake_tasks:
                                yield f"event: hallucination_warning\ndata: {json_module.dumps({'agent_id': sub_aid, 'fake_tasks': fake_tasks, 'warning': warning}, ensure_ascii=False)}\n\n"
                        
                        round_replies.append({
                            "agent_id": sub_aid,
                            "agent_name": sub_agent["name"],
                            "content": sub_full_content
                        })
                        
                        mentioned = extract_mentioned_agents(sub_full_content, conv_agents)
                        for mentioned_agent in mentioned:
                            mid = mentioned_agent["id"]
                            if mid == sub_aid:
                                continue
                            task_desc = extract_task_for_agent(sub_full_content, mentioned_agent["name"])
                            key = f"{mid}_{current_round + 1}"
                            if key not in processed_ids:
                                queue.append({
                                    "agent": mentioned_agent,
                                    "task": task_desc,
                                    "from_agent": sub_aid
                                })
                
                # 阶段3：通知前端本批并行执行完成
                yield f"event: batch_end\ndata: {json_module.dumps({'round': current_round, 'count': len(batch_results)}, ensure_ascii=False)}\n\n"
                time.sleep(0)
        
        # ===== 链式调度结束后，自动触发主智能体收尾总结 =====
        # 解决「子智能体做完任务不 @主智能体，主智能体收不到汇报」的问题
        # 只要最后一轮回复的不是主智能体（即子智能体刚完成任务），就自动让主智能体总结一次
        # 这样主智能体每次都能看到子智能体的产出，并给出确认/整理到 deliverables/ 的回应
        main_agent = next((a for a in conv_agents if a["id"] == "main"), None)
        last_reply_is_main = bool(round_replies) and round_replies[-1]["agent_id"] == "main"
        if main_agent and round_replies and not last_reply_is_main:
            # 收集所有子智能体的回复作为汇报内容
            # 阶段2：对过长的子智能体回复做截断，避免把超长内容全塞进主智能体历史
            sub_reports = []
            for r in round_replies:
                if r["agent_id"] != "main":
                    content = r["content"]
                    # 截断超长回复，保留关键信息
                    if len(content) > 2000:
                        content = content[:1800] + f"\n\n...（回复较长，已截断，完整内容共 {len(content)} 字，保存在消息记录中）"
                    sub_reports.append(f"【{r['agent_name']} 的回复】\n{content}")
            sub_report_text = "\n\n".join(sub_reports) if sub_reports else "（无子智能体回复）"

            main_prompt = main_agent.get("system_prompt", f"你是{main_agent['name']}，{main_agent['role']}。")
            # M1：启用摘要模式，压缩子智能体回复
            if CORE_RULES not in main_prompt:
                main_prompt = main_prompt + CORE_RULES
            main_history = build_conversation_history(conv_id, main_prompt, None, max_history=10, root_path=root_path, for_main_agent=True, context_window=current_context_window)
            # 把子智能体的回复作为"汇报"注入
            # 注意：这是来自团队成员的汇报，不是用户的新指令。措辞要明确，避免主智能体误以为是用户在下指令。
            summary_msg = (
                f"【系统通知：团队成员已完成本轮任务，以下是其工作汇报】\n"
                f"{sub_report_text}\n\n"
                f"【你的职责】作为项目经理，请基于上述汇报做收尾：\n"
                f"- 用简洁的语气向用户（项目负责人）通报结果（不要说\"已收到指令\"，这不是指令）\n"
                f"- 如有产出，确认是否已落到 deliverables/ 目录\n"
                f"- 如需下一步动作，简要说明，不要重复汇报里已写过的细节"
            )
            main_history.append({"role": "user", "content": summary_msg})

            yield f"event: agent_start\ndata: {json_module.dumps({'agent_id': 'main', 'source': 'summary', 'from_round': current_round}, ensure_ascii=False)}\n\n"

            main_full_content = ""
            for event_type, data in call_llm_stream_with_tools(main_prompt, main_history, main_agent, root_path, conv_id, default_config_id=msg.default_config_id, thinking_override=msg.enable_thinking):
                time.sleep(0)
                data["agent_id"] = "main"
                if event_type == "token":
                    main_full_content += data.get("content", "")
                    yield f"event: token\ndata: {json_module.dumps(data, ensure_ascii=False)}\n\n"
                elif event_type == "tool_start":
                    yield f"event: tool_start\ndata: {json_module.dumps(data, ensure_ascii=False)}\n\n"
                elif event_type == "tool_end":
                    yield f"event: tool_end\ndata: {json_module.dumps(data, ensure_ascii=False)}\n\n"
                elif event_type == "error":
                    yield f"event: error\ndata: {json_module.dumps(data, ensure_ascii=False)}\n\n"
                elif event_type == "done":
                    main_full_content = data.get("full_content", main_full_content)

            yield f"event: agent_end\ndata: {json_module.dumps({'agent_id': 'main', 'full_content': main_full_content, 'source': 'summary'}, ensure_ascii=False)}\n\n"

            # 防幻觉：扫描主智能体回复里的 task_xxx 引用，校验真实性
            fake_tasks, warning = detect_hallucination(main_full_content, root_path, "main")
            if fake_tasks:
                # 通过 SSE 事件通知前端
                yield f"event: hallucination_warning\ndata: {json_module.dumps({'agent_id': 'main', 'fake_tasks': fake_tasks, 'warning': warning}, ensure_ascii=False)}\n\n"
                # 同时把警告追加到主智能体回复末尾，让用户可见
                main_full_content += f"\n\n---\n⚠️ **系统检测**：上述回复中引用的任务 ID `{', '.join(fake_tasks)}` 在任务目录中不存在，可能为编造。请核实。"

            all_replies.append({"agent_id": "main", "content": main_full_content})
            # 原子追加主智能体收尾总结（防止多项目并行时更新丢失）
            append_message({
                "id": uuid.uuid4().hex[:12],
                "agent_id": "main",
                "role": "agent",
                "content": main_full_content,
                "time": time.strftime("%H:%M:%S"),
                "conversation_id": conv_id,
            })

            # ===== 收尾总结后，检查主智能体是否 @提及了其他智能体，如有则继续调度 =====
            # 解决"主智能体在收尾总结里安排下一步任务但没触发调度"的问题
            # 改造：基于任务完成情况决定结束，而非固定轮次
            #   - 最多 8 轮追加（覆盖长任务链：设定→创作→审阅→修订→二创...）
            #   - 连续 2 轮无 @提及则结束（无进展检测）
            #   - 每轮检查 pending 任务，提醒主智能体推进
            extra_rounds = 0
            max_extra_rounds = 8
            no_mention_streak = 0
            max_no_mention = 2
            current_main_content = main_full_content
            while extra_rounds < max_extra_rounds:
                mentioned = extract_mentioned_agents(current_main_content, conv_agents)
                mentioned_subs = [m for m in mentioned if m["id"] != "main"]
                
                # 构造给主智能体的"汇报/提醒"消息
                summary_msg_for_main = None
                
                if mentioned_subs:
                    # ===== 有 @提及，执行子智能体 =====
                    no_mention_streak = 0
                    
                    round_replies_extra = []
                    for mentioned_agent in mentioned_subs:
                        sub_aid = mentioned_agent["id"]
                        if any(r["agent_id"] == sub_aid for r in round_replies_extra):
                            continue
                        task_desc = extract_task_for_agent(current_main_content, mentioned_agent["name"])
                        sub_prompt = mentioned_agent.get("system_prompt", f"你是{mentioned_agent['name']}，{mentioned_agent['role']}。")
                        if CORE_RULES not in sub_prompt:
                            sub_prompt = sub_prompt + CORE_RULES
                        # 使用隔离上下文（防止 token 爆炸和上下文泄露）
                        sub_history = build_isolated_context(
                            system_prompt=sub_prompt,
                            task_description=task_desc,
                            root_path=root_path,
                            from_agent_name="主智能体",
                            original_user_msg=msg.message,
                        )
                        
                        yield f"event: agent_start\ndata: {json_module.dumps({'agent_id': sub_aid, 'agent_name': mentioned_agent['name'], 'task': task_desc}, ensure_ascii=False)}\n\n"
                        time.sleep(0)
                        
                        sub_full_content = ""
                        try:
                            for event_type, data in call_llm_stream_with_tools(sub_prompt, sub_history, mentioned_agent, root_path, conv_id, default_config_id=msg.default_config_id, thinking_override=msg.enable_thinking):
                                time.sleep(0)
                                if event_type == "token":
                                    sub_full_content += data.get("content", "")
                                    yield f"event: token\ndata: {json_module.dumps({'agent_id': sub_aid, 'content': data.get('content', '')}, ensure_ascii=False)}\n\n"
                                elif event_type == "tool_start":
                                    yield f"event: tool_start\ndata: {json_module.dumps({'agent_id': sub_aid, 'tool_name': data.get('tool_name', ''), 'tool_args': data.get('tool_args', '')}, ensure_ascii=False)}\n\n"
                                elif event_type == "tool_end":
                                    yield f"event: tool_end\ndata: {json_module.dumps({'agent_id': sub_aid, 'tool_name': data.get('tool_name', ''), 'result': data.get('result', '')}, ensure_ascii=False)}\n\n"
                                elif event_type == "error":
                                    yield f"event: error\ndata: {json_module.dumps({'agent_id': sub_aid, 'message': data.get('message', '')}, ensure_ascii=False)}\n\n"
                                elif event_type == "done":
                                    break
                        except Exception as e:
                            yield f"event: error\ndata: {json_module.dumps({'agent_id': sub_aid, 'message': f'智能体执行失败: {str(e)}'}, ensure_ascii=False)}\n\n"
                        
                        yield f"event: agent_end\ndata: {json_module.dumps({'agent_id': sub_aid, 'full_content': sub_full_content}, ensure_ascii=False)}\n\n"
                        
                        if sub_full_content:
                            round_replies_extra.append({"agent_id": sub_aid, "agent_name": mentioned_agent["name"], "content": sub_full_content})
                            # 原子追加子智能体回复（防止多项目并行时更新丢失）
                            append_message({
                                "id": uuid.uuid4().hex[:12],
                                "agent_id": sub_aid,
                                "role": "agent",
                                "content": sub_full_content,
                                "time": time.strftime("%H:%M:%S"),
                                "conversation_id": conv_id,
                            })
                            all_replies.append({"agent_id": sub_aid, "content": sub_full_content})
                    
                    if not round_replies_extra:
                        break
                    
                    # 构造子智能体汇报消息
                    sub_reports_extra = []
                    for r in round_replies_extra:
                        content = r["content"]
                        if len(content) > 2000:
                            content = content[:1800] + f"\n\n...（回复较长，已截断，完整内容共 {len(content)} 字，保存在消息记录中）"
                        sub_reports_extra.append(f"【{r['agent_name']} 的回复】\n{content}")
                    summary_msg_for_main = (
                        f"【系统通知：团队成员已完成你刚才安排的任务，以下是工作汇报】\n"
                        f"{chr(10).join(sub_reports_extra)}\n\n"
                        f"请确认产出并简要总结。可以用 list_tasks 查看任务进度。如有下一步任务，请 @对应智能体。"
                    )
                else:
                    # ===== 无 @提及 =====
                    no_mention_streak += 1
                    if no_mention_streak >= max_no_mention:
                        break  # 连续无进展，结束
                    
                    # 检查是否还有 pending 任务
                    tasks_dir_check = Path(root_path) / ".agent" / "tasks" if root_path else None
                    pending_count = 0
                    if tasks_dir_check and tasks_dir_check.exists():
                        import json as json_pc
                        for d in tasks_dir_check.iterdir():
                            if not d.is_dir():
                                continue
                            mf = d / "meta.json"
                            if mf.exists():
                                try:
                                    with open(mf, "r", encoding="utf-8") as f:
                                        m = json_pc.load(f)
                                    if m.get("status") == "pending":
                                        pending_count += 1
                                except Exception:
                                    pass
                    
                    if pending_count == 0:
                        break  # 无 pending 任务，正常结束
                    
                    # 有 pending 任务但主智能体没 @提及，构造提醒
                    summary_msg_for_main = (
                        f"⚠️【系统提醒：还有 {pending_count} 个待处理（pending）任务未完成】\n"
                        f"请用 list_tasks 工具查看任务状态，并 @对应智能体 推进未完成的任务。\n"
                        f"如果所有任务都已安排且无需继续，请明确说明「所有任务已完成」来结束。"
                    )
                
                # ===== 统一调用主智能体回复（基于汇报或提醒）=====
                if not summary_msg_for_main:
                    break
                
                extra_main_prompt = main_agent.get("system_prompt", f"你是{main_agent['name']}，{main_agent['role']}。")
                if CORE_RULES not in extra_main_prompt:
                    extra_main_prompt = extra_main_prompt + CORE_RULES
                extra_main_history = build_conversation_history(conv_id, extra_main_prompt, None, max_history=10, root_path=root_path, for_main_agent=True, context_window=current_context_window)
                extra_main_history.append({"role": "user", "content": summary_msg_for_main})
                
                current_main_content = ""
                yield f"event: agent_start\ndata: {json_module.dumps({'agent_id': 'main', 'agent_name': main_agent['name'], 'task': '收尾总结'}, ensure_ascii=False)}\n\n"
                time.sleep(0)
                try:
                    for event_type, data in call_llm_stream_with_tools(extra_main_prompt, extra_main_history, main_agent, root_path, conv_id, default_config_id=msg.default_config_id, thinking_override=msg.enable_thinking):
                        time.sleep(0)
                        if event_type == "token":
                            current_main_content += data.get("content", "")
                            yield f"event: token\ndata: {json_module.dumps({'agent_id': 'main', 'content': data.get('content', '')}, ensure_ascii=False)}\n\n"
                        elif event_type == "tool_start":
                            yield f"event: tool_start\ndata: {json_module.dumps({'agent_id': 'main', 'tool_name': data.get('tool_name', ''), 'tool_args': data.get('tool_args', '')}, ensure_ascii=False)}\n\n"
                        elif event_type == "tool_end":
                            yield f"event: tool_end\ndata: {json_module.dumps({'agent_id': 'main', 'tool_name': data.get('tool_name', ''), 'result': data.get('result', '')}, ensure_ascii=False)}\n\n"
                        elif event_type == "error":
                            yield f"event: error\ndata: {json_module.dumps({'agent_id': 'main', 'message': data.get('message', '')}, ensure_ascii=False)}\n\n"
                        elif event_type == "done":
                            break
                except Exception as e:
                    yield f"event: error\ndata: {json_module.dumps({'agent_id': 'main', 'message': f'主智能体收尾失败: {str(e)}'}, ensure_ascii=False)}\n\n"
                
                yield f"event: agent_end\ndata: {json_module.dumps({'agent_id': 'main', 'full_content': current_main_content}, ensure_ascii=False)}\n\n"
                
                if current_main_content:
                    # 原子追加主智能体收尾回复（防止多项目并行时更新丢失）
                    append_message({
                        "id": uuid.uuid4().hex[:12],
                        "agent_id": "main",
                        "role": "agent",
                        "content": current_main_content,
                        "time": time.strftime("%H:%M:%S"),
                        "conversation_id": conv_id,
                    })
                    all_replies.append({"agent_id": "main", "content": current_main_content})
                
                extra_rounds += 1

        # 更新项目信息
        if conv_id:
            conversations = load_conversations()
            for c in conversations:
                if c["id"] == conv_id:
                    c["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    if c["title"] == "新项目" and len(msg.message) > 0:
                        c["title"] = msg.message[:20] + ("..." if len(msg.message) > 20 else "")
                    break
            save_conversations(conversations)
        
        yield f"event: done\ndata: {json_module.dumps({'replies': all_replies}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })


def extract_mentioned_agents(messages_or_text, agent_list):
    """从消息列表或文本中提取 @ 提到的智能体，返回智能体对象列表
    注意：包含主智能体，子智能体可以 @主智能体 触发主智能体响应（用于汇报结果、请求授权等）。
    防循环由调度器的 max_rounds 和 processed_ids 控制。
    主智能体支持别名匹配：@主智能体、@我（主智能体）、@项目经理 都能匹配。
    """
    # 如果传入的是消息列表，提取所有文本内容
    if isinstance(messages_or_text, list):
        text = "\n".join([m.get("content", "") for m in messages_or_text if isinstance(m, dict)])
    else:
        text = str(messages_or_text) if messages_or_text else ""
    
    mentioned = []
    for agent in agent_list:
        # 主智能体支持多个别名，因为子智能体提示词里写的是 @主智能体，
        # 但主智能体的实际 name 是「我（主智能体）」，直接匹配会失败
        names_to_check = [agent['name']]
        if agent['id'] == 'main':
            names_to_check.extend(['主智能体', '项目经理'])
        matched = False
        for name in names_to_check:
            pattern = f"@{re.escape(name)}"
            if text and re.search(pattern, text):
                mentioned.append(agent)
                matched = True
                break
    return mentioned


def extract_task_for_agent(text: str, agent_name: str) -> str:
    """从主智能体回复中提取给某个智能体的任务描述"""
    pattern = f"@{re.escape(agent_name)}[：: ]*(.+?)(?=\\n\\s*\\n|@|$)"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        task = match.group(1).strip()
        if task:
            return task
    return text


def check_path_permission(agent, path: str) -> bool:
    """检查智能体是否有权限访问某个路径（兼容旧接口）"""
    return check_agent_path_access(agent, path, "")


def check_agent_path_access(agent, abs_path: str, root_path: str) -> bool:
    """检查智能体是否有权限访问某个绝对路径
    - 主智能体(id=main)默认拥有全部权限
    - 其他智能体检查 allowed_paths 白名单
    - 如果 allowed_paths 为空或包含 "*"，拥有全部权限（旧数据兼容）
    """
    if agent.get("id") == "main":
        return True  # 主智能体拥有全部权限
    
    allowed = agent.get("allowed_paths", [])
    if not allowed or "*" in allowed:
        return True  # 兼容旧数据：未设置权限时默认全部允许
    
    # 检查路径是否在任意允许的路径下
    for p in allowed:
        try:
            # 处理相对路径（如果是相对路径，基于 root_path 解析）
            if not Path(p).is_absolute() and root_path:
                p_abs = str((Path(root_path) / p).resolve())
            else:
                p_abs = str(Path(p).resolve())
            
            if abs_path == p_abs or abs_path.startswith(p_abs.rstrip("\\/") + "\\") or abs_path.startswith(p_abs.rstrip("\\/") + "/"):
                return True
        except Exception:
            continue
    return False


# ========== 接口 ==========

agents = load_agents()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/providers")
def get_providers():
    return {"providers": PRESET_PROVIDERS}


@app.get("/api/agents")
def get_agents():
    """获取全局智能体模板列表（每次重新加载，避免缓存问题）"""
    return {"agents": load_agents()}


@app.post("/api/agents")
def create_agent(data: AgentCreate):
    """新建智能体"""
    agents = load_agents()
    agent_id = "agent_" + uuid.uuid4().hex[:8]
    new_agent = {
        "id": agent_id,
        "name": data.name,
        "role": data.role,
        "avatar": data.avatar or "🤖",
        "system_prompt": data.system_prompt or f"你是{data.name}，{data.role}。",
        "allowed_paths": data.allowed_paths or ["*"],
        "can_use_tools": True,
    }
    agents.append(new_agent)
    save_agents(agents)
    return {"agent": new_agent}


@app.put("/api/agents/{agent_id}")
def update_agent(agent_id: str, data: AgentUpdate):
    """更新智能体信息"""
    agents = load_agents()
    agent = next((a for a in agents if a["id"] == agent_id), None)
    if not agent:
        raise HTTPException(status_code=404, detail="找不到这个智能体")
    if data.name is not None:
        agent["name"] = data.name
    if data.role is not None:
        agent["role"] = data.role
    if data.avatar is not None:
        agent["avatar"] = data.avatar
    if data.system_prompt is not None:
        agent["system_prompt"] = data.system_prompt
    if data.allowed_paths is not None:
        agent["allowed_paths"] = data.allowed_paths
    if data.model_cfg is not None:
        # 约定：空 dict 表示清除模型配置，否则更新
        if data.model_cfg == {}:
            agent["model_config"] = None
        else:
            agent["model_config"] = data.model_cfg
    save_agents(agents)
    return {"agent": agent}


@app.delete("/api/agents/{agent_id}")
def delete_agent(agent_id: str):
    """删除智能体"""
    if agent_id == "main":
        raise HTTPException(status_code=400, detail="不能删除主智能体")
    agents = load_agents()
    agents = [a for a in agents if a["id"] != agent_id]
    save_agents(agents)
    return {"status": "ok"}


# ========== 文件操作接口 ==========

class FileReadRequest(BaseModel):
    agent_id: str
    path: str
    conversation_id: str = ""


class FileWriteRequest(BaseModel):
    agent_id: str
    path: str
    content: str
    conversation_id: str = ""


class FileListRequest(BaseModel):
    agent_id: str
    path: str
    conversation_id: str = ""


def _get_project_root_path(conversation_id: str) -> str:
    """从对话ID获取项目根目录，如果找不到返回空字符串"""
    if not conversation_id:
        return ""
    conversations = load_conversations()
    conv = next((c for c in conversations if c["id"] == conversation_id), None)
    return conv.get("root_path", "") if conv else ""


def _safe_resolve_path(raw_path: str, root_path: str = "") -> str:
    """安全解析路径：如果提供了项目根目录，确保路径在项目内；否则只解析绝对路径"""
    if root_path:
        # 使用项目根目录解析，防止路径穿越
        resolved = resolve_project_path(root_path, raw_path)
        if resolved is None:
            raise HTTPException(status_code=403, detail="路径超出项目范围，访问被拒绝")
        return resolved
    else:
        # 没有根目录时，只解析绝对路径（兼容旧逻辑，但拒绝相对路径穿越）
        p = Path(raw_path).resolve()
        return str(p)


@app.post("/api/files/list")
def list_files(req: FileListRequest):
    """列出目录内容"""
    # 获取项目级智能体配置（优先使用对话内的智能体，而不是全局缓存）
    project_root = _get_project_root_path(req.conversation_id)
    if req.conversation_id:
        conversations = load_conversations()
        conv = next((c for c in conversations if c["id"] == req.conversation_id), None)
        conv_agents = conv.get("agents") if conv else None
    else:
        conv_agents = None
    agent_list = _get_conv_agents_with_main(conv_agents)
    agent = next((a for a in agent_list if a["id"] == req.agent_id), None)
    if not agent:
        raise HTTPException(status_code=404, detail="找不到这个智能体")

    abs_path = _safe_resolve_path(req.path, project_root)
    if not check_path_permission(agent, abs_path):
        raise HTTPException(status_code=403, detail=f"没有权限访问该路径：{req.path}")

    p = Path(abs_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="路径不存在")
    if not p.is_dir():
        raise HTTPException(status_code=400, detail="不是目录")

    items = []
    for child in sorted(p.iterdir()):
        # 显示 .agent 目录（用户需要查看智能体的任务产出）
        # 其他点开头的隐藏文件夹（如 .git、.vscode）仍跳过
        if child.name.startswith('.') and child.name != '.agent':
            continue
        items.append({
            "name": child.name,
            "is_dir": child.is_dir(),
            "path": str(child),
        })
    return {"items": items, "path": abs_path}


@app.post("/api/files/read")
def read_file(req: FileReadRequest):
    """读取文件内容"""
    project_root = _get_project_root_path(req.conversation_id)
    if req.conversation_id:
        conversations = load_conversations()
        conv = next((c for c in conversations if c["id"] == req.conversation_id), None)
        conv_agents = conv.get("agents") if conv else None
    else:
        conv_agents = None
    agent_list = _get_conv_agents_with_main(conv_agents)
    agent = next((a for a in agent_list if a["id"] == req.agent_id), None)
    if not agent:
        raise HTTPException(status_code=404, detail="找不到这个智能体")

    abs_path = _safe_resolve_path(req.path, project_root)
    if not check_path_permission(agent, abs_path):
        raise HTTPException(status_code=403, detail=f"没有权限访问该路径：{req.path}")

    p = Path(abs_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    if not p.is_file():
        raise HTTPException(status_code=400, detail="不是文件")

    try:
        content = p.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"读取失败：{str(e)}")

    return {"content": content, "path": abs_path}


@app.get("/api/files/read-image")
def read_image_file(path: str, conversation_id: str = "", agent_id: str = "main"):
    """读取图片文件（用于预览）"""
    project_root = _get_project_root_path(conversation_id)
    if conversation_id:
        conversations = load_conversations()
        conv = next((c for c in conversations if c["id"] == conversation_id), None)
        conv_agents = conv.get("agents") if conv else None
    else:
        conv_agents = None
    agent_list = _get_conv_agents_with_main(conv_agents)
    agent = next((a for a in agent_list if a["id"] == agent_id), None)
    if not agent:
        raise HTTPException(status_code=404, detail="找不到这个智能体")

    abs_path = _safe_resolve_path(path, project_root)
    if not check_path_permission(agent, abs_path):
        raise HTTPException(status_code=403, detail=f"没有权限访问该路径：{path}")

    p = Path(abs_path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    ext = p.suffix.lower()
    media_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.webp': 'image/webp',
    }
    media_type = media_types.get(ext, 'application/octet-stream')
    return FileResponse(abs_path, media_type=media_type)


@app.post("/api/files/upload")
async def upload_file(
    conversation_id: str = Form(...),
    agent_id: str = Form("main"),
    sub_dir: str = Form("shared"),  # 上传到哪个子目录，默认 shared/
    file: UploadFile = File(...)
):
    """上传文件到项目目录的 shared/ 子目录（或指定子目录）。
    
    用途：让用户从本地选择文件上传到项目，方便智能体读取处理。
    默认上传到 shared/，智能体之间可以共享访问。
    """
    import shutil
    from pathlib import Path
    
    # 获取项目根目录
    project_root = _get_project_root_path(conversation_id)
    if not project_root:
        raise HTTPException(status_code=400, detail="项目未设置工作目录，无法上传文件")
    
    # 安全校验：sub_dir 只允许简单目录名，不允许 .. 或绝对路径
    if not sub_dir or ".." in sub_dir or "\\" in sub_dir or "/" in sub_dir:
        raise HTTPException(status_code=400, detail=f"非法的子目录名：{sub_dir}")
    
    # 文件大小限制（10MB）
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
    
    # 危险扩展名黑名单（防止上传可执行文件）
    DANGEROUS_EXTENSIONS = {
        '.exe', '.bat', '.cmd', '.com', '.ps1', '.sh', '.vbs', 
        '.msi', '.scr', '.dll', '.sys', '.jar', '.app'
    }
    
    # 目标目录
    target_dir = Path(project_root) / sub_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # 目标文件路径
    safe_name = Path(file.filename).name  # 去掉路径，只留文件名
    if not safe_name:
        raise HTTPException(status_code=400, detail="文件名为空")
    
    # 检查文件扩展名是否危险
    file_ext = Path(safe_name).suffix.lower()
    if file_ext in DANGEROUS_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"不允许上传此类型文件：{file_ext}（安全限制：禁止上传可执行文件）"
        )
    
    target_path = target_dir / safe_name
    
    # 写入文件（带大小限制检查）
    try:
        file_size = 0
        with open(target_path, "wb") as f:
            while True:
                chunk = file.file.read(64 * 1024)  # 64KB chunks
                if not chunk:
                    break
                file_size += len(chunk)
                if file_size > MAX_UPLOAD_SIZE:
                    f.close()
                    target_path.unlink(missing_ok=True)  # 删除已部分写入的文件
                    raise HTTPException(
                        status_code=400, 
                        detail=f"文件大小超过限制（最大 {MAX_UPLOAD_SIZE // 1024 // 1024}MB）"
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"上传失败：{str(e)}")
    finally:
        file.file.close()
    
    return {
        "status": "ok",
        "path": str(target_path.resolve()),
        "relative_path": f"{sub_dir}/{safe_name}",
        "filename": safe_name,
        "size": target_path.stat().st_size,
    }


@app.post("/api/files/write")
def write_file(req: FileWriteRequest):
    """写入文件内容"""
    project_root = _get_project_root_path(req.conversation_id)
    if req.conversation_id:
        conversations = load_conversations()
        conv = next((c for c in conversations if c["id"] == req.conversation_id), None)
        conv_agents = conv.get("agents") if conv else None
    else:
        conv_agents = None
    agent_list = _get_conv_agents_with_main(conv_agents)
    agent = next((a for a in agent_list if a["id"] == req.agent_id), None)
    if not agent:
        raise HTTPException(status_code=404, detail="找不到这个智能体")

    abs_path = _safe_resolve_path(req.path, project_root)
    if not check_path_permission(agent, abs_path):
        raise HTTPException(status_code=403, detail=f"没有权限写入该路径：{req.path}")

    p = Path(abs_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    try:
        p.write_text(req.content, encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"写入失败：{str(e)}")

    return {"status": "ok", "path": abs_path}


@app.get("/api/messages")
def get_messages(conversation_id: str = ""):
    """获取聊天记录，可按对话筛选"""
    messages = load_messages()
    if conversation_id:
        messages = [m for m in messages if m.get("conversation_id") == conversation_id]
    return {"messages": messages}


class RegenerateMessage(BaseModel):
    conversation_id: str
    message_id: str  # 要重新生成的用户消息 id（会删除这条消息之后的所有回复）
    direct: bool = False  # 是否直接对话模式（只调用指定智能体，不触发链式调度）
    target_agent_id: str = ""  # direct 模式下指定要重新生成的智能体id


@app.post("/api/chat/regenerate")
async def regenerate_message(data: RegenerateMessage):
    """重新生成某条用户消息之后的所有回复。
    会删除该用户消息之后的所有 agent 回复，然后重新触发流式回复。
    返回一个 SSE 流，和 /api/chat/stream 格式一致。
    """
    conv_id = data.conversation_id
    msg_id = data.message_id
    
    # 加载消息，找到目标用户消息
    messages = load_messages()
    conv_msgs = [m for m in messages if m.get("conversation_id") == conv_id]
    conv_msgs.sort(key=lambda x: x.get("time", ""))
    
    # 找到目标消息的位置
    target_idx = -1
    target_msg = None
    for i, m in enumerate(conv_msgs):
        if m.get("id") == msg_id:
            target_idx = i
            target_msg = m
            break
    
    if not target_msg:
        async def error_gen():
            yield f"event: error\ndata: {json_module.dumps({'message': '找不到要重新生成的消息'}, ensure_ascii=False)}\n\n"
        return StreamingResponse(error_gen(), media_type="text/event-stream")
    
    # 如果是智能体回复消息，找到它前面的最近用户消息作为重新生成的起点
    if target_msg.get("role") != "user":
        # 向前找最近的用户消息
        for i in range(target_idx - 1, -1, -1):
            if conv_msgs[i].get("role") == "user":
                target_idx = i
                target_msg = conv_msgs[i]
                break
        else:
            async def error_gen():
                yield f"event: error\ndata: {json_module.dumps({'message': '找不到对应的用户消息'}, ensure_ascii=False)}\n\n"
            return StreamingResponse(error_gen(), media_type="text/event-stream")
    
    # 删除目标消息之后的所有消息（保留 target_msg 本身）
    # 原子删除（加锁保护 load-filter-save 事务，防止多项目并行时更新丢失）
    messages_to_keep = conv_msgs[:target_idx + 1]
    ids_to_remove = set(m.get("id") for m in conv_msgs[target_idx + 1:])
    remove_messages_by_ids(ids_to_remove)
    
    # 获取项目级智能体配置
    conversations = load_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None) if conv_id else None
    
    root_path = ""
    if conv:
        conv_agents = _get_conv_agents_with_main(conv.get("agents"))
        root_path = conv.get("root_path", "")
    else:
        conv_agents = load_agents()
    
    agent_id = target_msg.get("agent_id", "main")
    # direct 模式下，使用指定的 target_agent_id（如果提供了）
    if data.direct and data.target_agent_id:
        agent_id = data.target_agent_id
    user_text = target_msg.get("content", "")
    agent = next((a for a in conv_agents if a["id"] == agent_id), None)
    if not agent:
        async def error_gen():
            yield f"event: error\ndata: {json_module.dumps({'message': '找不到这个智能体'}, ensure_ascii=False)}\n\n"
        return StreamingResponse(error_gen(), media_type="text/event-stream")

    now = time.strftime("%H:%M:%S")

    def generate() -> Generator[str, None, None]:
        # 同步 generator——Starlette 会自动在线程池中运行，不阻塞事件循环
        nonlocal agent, conv_agents, user_text, conv_id, now, root_path
        import concurrent.futures
        
        msgs = load_messages()
        
        if data.direct:
            # direct 模式：只调用指定智能体，不进行链式调度
            sub_prompt = agent.get("system_prompt", f"你是{agent['name']}，{agent['role']}。")
            sub_history = build_conversation_history(conv_id, sub_prompt, user_text, max_history=20, root_path=root_path, target_agent_id=agent_id)
            
            sub_full_content = ""
            yield f"event: agent_start\ndata: {json_module.dumps({'agent_id': agent_id}, ensure_ascii=False)}\n\n"
            
            for event_type, event_data in call_llm_stream_with_tools(sub_prompt, sub_history, agent, root_path, conv_id):
                time.sleep(0)
                if event_type == "token":
                    sub_full_content += event_data.get("content", "")
                    yield f"event: token\ndata: {json_module.dumps(event_data, ensure_ascii=False)}\n\n"
                elif event_type == "tool_start":
                    yield f"event: tool_start\ndata: {json_module.dumps(event_data, ensure_ascii=False)}\n\n"
                elif event_type == "tool_end":
                    yield f"event: tool_end\ndata: {json_module.dumps(event_data, ensure_ascii=False)}\n\n"
                elif event_type == "error":
                    yield f"event: error\ndata: {json_module.dumps(event_data, ensure_ascii=False)}\n\n"
                elif event_type == "done":
                    sub_full_content = event_data.get("full_content", sub_full_content)
            
            yield f"event: agent_end\ndata: {json_module.dumps({'agent_id': agent_id, 'full_content': sub_full_content}, ensure_ascii=False)}\n\n"
            time.sleep(0)
            
            # 原子追加（防止多项目并行时更新丢失）
            append_message({
                "id": uuid.uuid4().hex[:12],
                "agent_id": agent_id,
                "role": "agent",
                "content": sub_full_content,
                "time": time.strftime("%H:%M:%S"),
                "conversation_id": conv_id,
            })
            yield f"event: done\ndata: {json_module.dumps({'status': 'ok'}, ensure_ascii=False)}\n\n"
            return
        
        # ===== 非 direct 模式：多轮链式调度核心逻辑 =====
        all_replies = []
        # 队列中每个元素: {"agent": agent_obj, "task": task_description, "from_agent": 来源智能体id}
        queue = [{"agent": agent, "task": user_text, "from_agent": None}]
        processed_ids = set()
        max_rounds = 6
        current_round = 0
        round_replies = []
        
        agent_map = {a["id"]: a for a in conv_agents}
        
        while queue and current_round < max_rounds:
            current_round += 1
            
            current_batch = []
            while queue:
                item = queue.pop(0)
                aid = item["agent"]["id"]
                key = f"{aid}_{current_round}"
                if key not in processed_ids:
                    processed_ids.add(key)
                    current_batch.append(item)
            
            if not current_batch:
                break
            
            is_first_round = (current_round == 1)
            
            if is_first_round and len(current_batch) == 1:
                # 第一轮单智能体：真正的流式输出
                item = current_batch[0]
                sub_agent = item["agent"]
                sub_aid = sub_agent["id"]
                sub_prompt = sub_agent.get("system_prompt", f"你是{sub_agent['name']}，{sub_agent['role']}。")
                sub_history = build_conversation_history(conv_id, sub_prompt, item["task"], max_history=20, root_path=root_path)
                
                sub_full_content = ""
                sub_tool_events = []
                yield f"event: agent_start\ndata: {json_module.dumps({'agent_id': sub_aid}, ensure_ascii=False)}\n\n"
                
                for event_type, data in call_llm_stream_with_tools(sub_prompt, sub_history, sub_agent, root_path, conv_id):
                    time.sleep(0)
                    if event_type == "token":
                        sub_full_content += data.get("content", "")
                        yield f"event: token\ndata: {json_module.dumps(data, ensure_ascii=False)}\n\n"
                    elif event_type == "tool_start":
                        sub_tool_events.append(("start", data))
                        yield f"event: tool_start\ndata: {json_module.dumps(data, ensure_ascii=False)}\n\n"
                    elif event_type == "tool_end":
                        sub_tool_events.append(("end", data))
                        yield f"event: tool_end\ndata: {json_module.dumps(data, ensure_ascii=False)}\n\n"
                    elif event_type == "error":
                        yield f"event: error\ndata: {json_module.dumps(data, ensure_ascii=False)}\n\n"
                    elif event_type == "done":
                        sub_full_content = data.get("full_content", sub_full_content)
                
                yield f"event: agent_end\ndata: {json_module.dumps({'agent_id': sub_aid, 'full_content': sub_full_content}, ensure_ascii=False)}\n\n"
                time.sleep(0)
                
                all_replies.append({"agent_id": sub_aid, "content": sub_full_content})
                msgs.append({
                    "id": uuid.uuid4().hex[:12],
                    "agent_id": sub_aid,
                    "role": "agent",
                    "content": sub_full_content,
                    "time": time.strftime("%H:%M:%S"),
                    "conversation_id": conv_id,
                })
                round_replies.append({
                    "agent_id": sub_aid,
                    "agent_name": sub_agent["name"],
                    "content": sub_full_content
                })
                
                mentioned = extract_mentioned_agents(sub_full_content, conv_agents)
                for mentioned_agent in mentioned:
                    mid = mentioned_agent["id"]
                    if mid == sub_aid:
                        continue
                    task_desc = extract_task_for_agent(sub_full_content, mentioned_agent["name"])
                    key = f"{mid}_{current_round + 1}"
                    if key not in processed_ids:
                        queue.append({
                            "agent": mentioned_agent,
                            "task": task_desc,
                            "from_agent": sub_aid
                        })
            else:
                # 后续轮次：并发执行
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(current_batch)) as executor:
                    future_to_item = {}
                    
                    for item in current_batch:
                        sub_agent = item["agent"]
                        task_desc = item["task"]
                        from_aid = item["from_agent"]
                        sub_aid = sub_agent["id"]
                        
                        sub_prompt = sub_agent.get("system_prompt", f"你是{sub_agent['name']}，{sub_agent['role']}。")
                        sub_history = build_conversation_history(conv_id, sub_prompt, None, max_history=15, root_path=root_path)
                        
                        for reply in round_replies:
                            sub_history.append({"role": "assistant", "content": f"【{reply['agent_name']}】：\n{reply['content']}"})
                        
                        if from_aid is None:
                            sub_task_msg = task_desc
                        else:
                            from_name = agent_map.get(from_aid, {}).get("name", "其他智能体")
                            sub_task_msg = f"【{from_name}给你的任务】{task_desc}\n\n【原始用户需求】{user_text}"
                        sub_history.append({"role": "user", "content": sub_task_msg})
                        
                        yield f"event: agent_start\ndata: {json_module.dumps({'agent_id': sub_aid}, ensure_ascii=False)}\n\n"
                        time.sleep(0)
                        
                        future = executor.submit(
                            collect_stream_sync,
                            sub_prompt,
                            sub_history,
                            sub_agent,
                            root_path,
                            conv_id,
                            msg.default_config_id,
                            msg.enable_thinking
                        )
                        future_to_item[future] = {"agent": sub_agent}
                    
                    batch_results = []
                    for future in concurrent.futures.as_completed(future_to_item):
                        item_info = future_to_item[future]
                        sub_agent = item_info["agent"]
                        try:
                            sub_full_content, sub_tool_events = future.result()
                        except Exception as e:
                            sub_full_content = f"❌ 调用出错：{str(e)}"
                            sub_tool_events = []
                        batch_results.append({
                            "agent": sub_agent,
                            "content": sub_full_content,
                            "tool_events": sub_tool_events
                        })
                    
                    def sort_key(r):
                        return 0 if r["agent"]["id"] == "main" else 1
                    batch_results.sort(key=sort_key)
                    
                    for result in batch_results:
                        sub_agent = result["agent"]
                        sub_aid = sub_agent["id"]
                        sub_full_content = result["content"]
                        sub_tool_events = result["tool_events"]
                        
                        for te_type, te_data in sub_tool_events:
                            sse_event = "tool_start" if te_type == "start" else "tool_end"
                            yield f"event: {sse_event}\ndata: {json_module.dumps(te_data, ensure_ascii=False)}\n\n"
                            time.sleep(0.003)
                        
                        chunk_size = 3
                        for i in range(0, len(sub_full_content), chunk_size):
                            chunk = sub_full_content[i:i+chunk_size]
                            yield f"event: token\ndata: {json_module.dumps({'agent_id': sub_aid, 'content': chunk}, ensure_ascii=False)}\n\n"
                            time.sleep(0.01)
                        
                        yield f"event: agent_end\ndata: {json_module.dumps({'agent_id': sub_aid, 'full_content': sub_full_content}, ensure_ascii=False)}\n\n"
                        time.sleep(0)
                        
                        all_replies.append({"agent_id": sub_aid, "content": sub_full_content})
                        # 原子追加（防止多项目并行时更新丢失）
                        append_message({
                            "id": uuid.uuid4().hex[:12],
                            "agent_id": sub_aid,
                            "role": "agent",
                            "content": sub_full_content,
                            "time": time.strftime("%H:%M:%S"),
                            "conversation_id": conv_id,
                        })
                        round_replies.append({
                            "agent_id": sub_aid,
                            "agent_name": sub_agent["name"],
                            "content": sub_full_content
                        })
                        
                        mentioned = extract_mentioned_agents(sub_full_content, conv_agents)
                        for mentioned_agent in mentioned:
                            mid = mentioned_agent["id"]
                            if mid == sub_aid:
                                continue
                            task_desc = extract_task_for_agent(sub_full_content, mentioned_agent["name"])
                            key = f"{mid}_{current_round + 1}"
                            if key not in processed_ids:
                                queue.append({
                                    "agent": mentioned_agent,
                                    "task": task_desc,
                                    "from_agent": sub_aid
                                })
        
        if conv_id:
            conversations = load_conversations()
            for c in conversations:
                if c["id"] == conv_id:
                    c["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    break
            save_conversations(conversations)
        
        yield f"event: done\ndata: {json_module.dumps({'replies': all_replies}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })


@app.post("/api/chat")
def chat(msg: ChatMessage):
    """
    发送消息给某个智能体。
    使用对话级智能体配置，如果是主智能体，它回复后会检查有没有 @其他智能体，
    有就自动把任务转发给对应的智能体执行，返回所有回复。
    所有消息都会保存到聊天记录，并关联到对话。
    智能体会携带对话历史上下文，具备记忆能力。
    """
    conv_id = msg.conversation_id
    
    # 获取对话级智能体配置（每次重新加载，避免全局缓存问题）
    conversations = load_conversations()
    conv = next((c for c in conversations if c["id"] == conv_id), None) if conv_id else None
    
    # 优先用对话级配置，否则用全局配置
    root_path = ""
    if conv and conv.get("agents"):
        conv_agents = conv["agents"]
        root_path = conv.get("root_path", "")
    else:
        conv_agents = load_agents()
    
    agent = next((a for a in conv_agents if a["id"] == msg.agent_id), None)
    if not agent:
        return {"error": "找不到这个智能体"}

    replies = []
    now = time.strftime("%H:%M:%S")

    # 1. 先构建对话历史上下文（在保存任何新消息前构建，从已持久化的历史中取）
    system_prompt = agent.get("system_prompt", f"你是{agent['name']}，{agent['role']}。")
    # 注入通用核心规则（主智能体也适用，确保工具调用约束和防幻觉规则生效）
    if CORE_RULES not in system_prompt:
        system_prompt = system_prompt + CORE_RULES
    # M1：主智能体启用摘要模式，压缩子智能体回复
    # M2：主智能体注入 TODO 提醒（如果有未完成项）
    # 跨轮续接：注入 pending 任务提醒（如果有未完成任务）
    effective_msg = msg.message
    if msg.agent_id == "main":
        todo_reminder = check_pending_todos(conv_id, root_path)
        if todo_reminder:
            effective_msg = todo_reminder + "\n---\n\n用户消息：" + msg.message
        pending_tasks_reminder = check_pending_tasks(conv_id, root_path, conv_agents)
        if pending_tasks_reminder:
            effective_msg = pending_tasks_reminder + "\n---\n\n" + effective_msg
    history = build_conversation_history(conv_id, system_prompt, effective_msg, max_history=20, root_path=root_path, for_main_agent=True)
    
    # 2. 原子追加用户消息和智能体回复（防止多项目并行时更新丢失）
    # 注意：chat() 是非流式接口，所有回复在最后一次性批量追加
    msgs_to_append = []
    user_msg = {
        "id": uuid.uuid4().hex[:12],
        "agent_id": msg.agent_id,
        "role": "user",
        "content": msg.message,
        "time": now,
        "conversation_id": conv_id,
    }
    msgs_to_append.append(user_msg)

    # 当前智能体回复（携带历史上下文）
    main_reply = call_llm(system_prompt, msg.message, agent, history_messages=history, default_config_id=msg.default_config_id, thinking_override=msg.enable_thinking)
    replies.append({"agent_id": agent["id"], "content": main_reply})
    msgs_to_append.append({
        "id": uuid.uuid4().hex[:12],
        "agent_id": agent["id"],
        "role": "agent",
        "content": main_reply,
        "time": time.strftime("%H:%M:%S"),
        "conversation_id": conv_id,
    })

    # 2. 如果是主智能体，检查回复里有没有 @其他智能体，有就转发任务
    if agent["id"] == "main":
        import concurrent.futures
        mentioned = extract_mentioned_agents(main_reply, conv_agents)
        
        def call_sub_agent(sub_agent, task_desc):
            sub_prompt = sub_agent.get("system_prompt", f"你是{sub_agent['name']}，{sub_agent['role']}。")
            sub_history = build_conversation_history(conv_id, sub_prompt, None, max_history=10, root_path=root_path)
            sub_history.append({"role": "assistant", "content": main_reply})
            sub_task_msg = f"【主智能体安排给你的任务】{task_desc}\n\n【原始用户需求】{msg.message}"
            sub_history.append({"role": "user", "content": sub_task_msg})
            return sub_agent["id"], call_llm(sub_prompt, sub_task_msg, sub_agent, history_messages=sub_history, default_config_id=msg.default_config_id, thinking_override=msg.enable_thinking)
        
        # 并发调用子智能体
        if mentioned:
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(mentioned)) as executor:
                futures = [executor.submit(call_sub_agent, sa, extract_task_for_agent(main_reply, sa["name"])) for sa in mentioned]
                for future in concurrent.futures.as_completed(futures):
                    try:
                        sub_id, sub_reply = future.result()
                        replies.append({"agent_id": sub_id, "content": sub_reply})
                        msgs_to_append.append({
                            "id": uuid.uuid4().hex[:12],
                            "agent_id": sub_id,
                            "role": "agent",
                            "content": sub_reply,
                            "time": time.strftime("%H:%M:%S"),
                            "conversation_id": conv_id,
                        })
                    except Exception as e:
                        replies.append({"agent_id": "error", "content": f"❌ 调用出错：{str(e)}"})

    # 原子批量追加所有新消息
    append_messages(msgs_to_append)

    # 更新对话的更新时间
    if conv_id:
        conversations = load_conversations()
        for c in conversations:
            if c["id"] == conv_id:
                c["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                # 如果标题是默认的"新对话"，自动用第一条用户消息作为标题
                if c["title"] == "新对话" and len(msg.message) > 0:
                    c["title"] = msg.message[:20] + ("..." if len(msg.message) > 20 else "")
                break
        save_conversations(conversations)

    return {"replies": replies}


@app.get("/api/config")
def get_config():
    cfg = load_api_config()
    masked = dict(cfg)
    if masked.get("api_key"):
        key = masked["api_key"]
        masked["api_key"] = key[:4] + "***" + key[-4:] if len(key) > 8 else "***"
    return {"config": masked}


@app.post("/api/config")
def update_config(cfg: ApiConfig):
    save_api_config({
        "base_url": cfg.base_url,
        "api_key": cfg.api_key,
        "model": cfg.model,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
    })
    return {"status": "ok"}


@app.post("/api/config/test")
def test_config(cfg: ApiConfig):
    result = test_api_connection({
        "base_url": cfg.base_url,
        "api_key": cfg.api_key,
        "model": cfg.model,
    })
    return result


# ========== 多模型配置管理 ==========

def load_model_configs():
    return load_json(CONFIGS_FILE, {"configs": []})["configs"]


def save_model_configs(configs):
    save_json(CONFIGS_FILE, {"configs": configs})


@app.get("/api/model-configs")
def get_model_configs():
    """获取所有模型配置列表"""
    configs = load_model_configs()
    # 返回时隐藏 api_key
    result = []
    for c in configs:
        item = dict(c)
        if item.get("api_key"):
            key = item["api_key"]
            item["api_key"] = key[:4] + "***" + key[-4:] if len(key) > 8 else "***"
        result.append(item)
    return {"configs": result}


@app.post("/api/model-configs")
def create_model_config(data: ModelConfigCreate):
    """新建模型配置"""
    # 整个 load-append-save 事务加锁，防止并发写入丢失
    with _json_write_lock:
        configs = load_model_configs()
        cfg_id = "cfg_" + uuid.uuid4().hex[:8]
        new_cfg = {
            "id": cfg_id,
            "name": data.name,
            "provider": data.provider,
            "base_url": data.base_url,
            "api_key": data.api_key,
            "model": data.model,
            "temperature": data.temperature,
            "max_tokens": data.max_tokens,
            "enable_thinking": data.enable_thinking,
            "context_window": data.context_window,
            "enabled": data.enabled,  # 是否启用该配置
        }
        configs.append(new_cfg)
        save_model_configs(configs)
    # 返回时脱敏 api_key（与 GET 列表一致，避免明文密钥泄露到前端）
    result = dict(new_cfg)
    if result.get("api_key"):
        key = result["api_key"]
        result["api_key"] = key[:4] + "***" + key[-4:] if len(key) > 8 else "***"
    return {"config": result}


@app.put("/api/model-configs/{cfg_id}")
def update_model_config(cfg_id: str, data: ModelConfigUpdate):
    """更新模型配置"""
    # 整个 load-update-save 事务加锁，防止并发写入丢失
    with _json_write_lock:
        configs = load_model_configs()
        for c in configs:
            if c["id"] == cfg_id:
                if data.name is not None:
                    c["name"] = data.name
                if data.provider is not None:
                    c["provider"] = data.provider
                if data.base_url is not None:
                    c["base_url"] = data.base_url
                if data.api_key is not None:
                    c["api_key"] = data.api_key
                if data.model is not None:
                    c["model"] = data.model
                if data.temperature is not None:
                    c["temperature"] = data.temperature
                if data.max_tokens is not None:
                    c["max_tokens"] = data.max_tokens
                if data.enable_thinking is not None:
                    c["enable_thinking"] = data.enable_thinking
                if data.context_window is not None:
                    c["context_window"] = data.context_window
                if data.enabled is not None:
                    c["enabled"] = data.enabled
                save_model_configs(configs)
                # 返回时脱敏 api_key
                result = dict(c)
                if result.get("api_key"):
                    key = result["api_key"]
                    result["api_key"] = key[:4] + "***" + key[-4:] if len(key) > 8 else "***"
                return {"config": result}
    raise HTTPException(status_code=404, detail="配置不存在")


@app.delete("/api/model-configs/{cfg_id}")
def delete_model_config(cfg_id: str):
    """删除模型配置"""
    # 整个 load-filter-save 事务加锁，防止并发写入丢失
    with _json_write_lock:
        configs = load_model_configs()
        configs = [c for c in configs if c["id"] != cfg_id]
        save_model_configs(configs)
    return {"status": "ok"}


@app.post("/api/model-configs/{cfg_id}/test")
def test_model_config(cfg_id: str):
    """测试某个模型配置的连接"""
    configs = load_model_configs()
    cfg = next((c for c in configs if c["id"] == cfg_id), None)
    if not cfg:
        raise HTTPException(status_code=404, detail="配置不存在")
    result = test_api_connection({
        "base_url": cfg["base_url"],
        "api_key": cfg["api_key"],
        "model": cfg["model"],
    })
    return result


# ========== 元团队常驻模块初始化 ==========
# 后端启动时确保专家配置和任务目录已初始化
mt_config_init()
mt_task_init()


# ========== 前端静态文件服务 ==========
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os as _os

# 前端dist目录路径（相对于backend目录）
FRONTEND_DIST = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "frontend", "dist")

if _os.path.isdir(FRONTEND_DIST):
    # 挂载静态资源（/assets/*）
    assets_dir = _os.path.join(FRONTEND_DIST, "assets")
    if _os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    
    # 首页
    @app.get("/")
    async def serve_index():
        return FileResponse(_os.path.join(FRONTEND_DIST, "index.html"))
    
    # 提供 dist 根目录下的静态文件（如收款码图片 wechat-qr.jpg / alipay-qr.jpg 等）
    @app.get("/{filename:path}")
    async def serve_static_file(filename: str):
        # 安全检查：防止路径穿越
        if ".." in filename or filename.startswith("/"):
            raise HTTPException(status_code=404, detail="Not found")
        file_path = _os.path.join(FRONTEND_DIST, filename)
        if _os.path.isfile(file_path):
            return FileResponse(file_path)
        # SPA 兜底：找不到文件时返回 index.html（前端路由处理）
        return FileResponse(_os.path.join(FRONTEND_DIST, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
