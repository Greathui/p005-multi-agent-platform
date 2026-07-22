# 变更日志（CHANGELOG）

> 本文件记录 P005 项目的所有需求变更、功能增改、缺陷修复。
> 遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 规范，使用[语义化版本](https://semver.org/lang/zh-CN/)。
> **只追加，不删改历史记录**。

## 版本说明

- **主版本**（v1 → v2）：不兼容的大重构
- **次版本**（v0.3 → v0.4）：新增功能
- **修订号**（v0.3.0 → v0.3.1）：bug 修复、小调整

## 分类说明

- `新增`：新加的功能
- `变更`：对已有功能的修改
- `废弃`：即将移除的功能
- `移除`：本版本已删除的功能
- `修复`：bug 修复
- `文档`：文档相关改动

---

## [未发布]

### 修复
- **记忆提取模型配置缺失**（2026-07-22）：`trigger_memory_extraction` / `extract_memory_from_conversation` 函数缺少 `agent` 参数，导致 `call_llm` 回退到全局默认配置而非智能体自身配置。修复：添加 `agent: dict = None` 参数，`submit_task_result` 传入 `current_agent_obj`
- **幻觉检测正则误报**（2026-07-22）：`detect_hallucination` 正则 `r'task_[a-z0-9_]{6,}'` 误匹配工具名 `submit_task_result` 中的 `task_result`。修复：改为 `r'task_\d{8,}_[a-f0-9]{6}'` 精确匹配任务 ID 格式

### 文档
- **长程任务测试报告**（2026-07-22）：使用 DeepSeek V4 进行 29 分钟 20 章小说自主协作测试，验证全部 v0.5 功能，报告含 ECharts 图表
- **未来规划文档**（2026-07-22）：基于用户愿景整理，从"多智能体工具"到"智能体元宇宙"的四层架构规划（持久化→元宇宙→经济系统→数据反哺），含技术路线图和商业化路径

### 新增
- **P0-1 智能体记忆系统**（2026-07-22）：agent 对象新增 `memory_log` 字段，任务完成后自动调用 LLM 提取关键经验（preference/lesson/pattern/fact 四类），构建上下文时注入到系统提示词。新增 3 个 API：GET/DELETE/POST `/api/conversations/{id}/agents/{agent_id}/memory`。记忆上限 50 条，自动去重
- **P0-2 跨项目经验迁移**（2026-07-22）：teams.json agent 新增 `shared_memory` 字段，项目级记忆超 10 条时自动同步到团队级（最近 5 条），新项目创建时自动继承团队级共享记忆
- **P0-3 对话摘要压缩**（2026-07-22）：`build_conversation_history` 截断时生成被截断消息的摘要（用户消息保留 200 字，智能体消息保留 100 字），注入 system 消息，避免早期决策丢失
- **P1-4 调度轮次优化**（2026-07-22）：截断策略优先保留含工具调用的消息防止退化；CORE_RULES 新增第 9 条"工具使用防退化"规则，每轮提醒可用工具列表
- **P1-5 TODO 前端可视化**（2026-07-22）：新增 `GET /api/conversations/{id}/todos` API；新建 `TodoPanel.vue` 组件（卡片式看板，状态颜色区分，折叠展开）；ChatWindow 顶部栏集成 TODO 切换按钮；stores/agent.js 新增 `todoRefreshTrigger` 自动刷新机制
- **P1-6 文件版本控制**（2026-07-22）：`write_file`/`edit_file` 执行前自动备份旧版本到 `.agent/file_history/`（保留最近 10 版）；新增 `list_file_versions` 和 `file_rollback` 两个主智能体工具；回退前自动备份当前版本
- **P1-7 智能体性能追踪**（2026-07-22）：agent 对象新增 `stats` 字段（total_tasks/completed_tasks/avg_duration_sec/last_active_at）；`submit_task_result` 成功后自动更新统计；新增 `GET /api/conversations/{id}/agents/stats` API；Sidebar 智能体管理弹窗展示记忆与统计
- **v0.5 优化推进规划文档**（2026-07-22）：`docs/04-设计/v0.5优化推进规划.md`，分三阶段 8 项任务的详细技术设计
- **代码架构说明书**（2026-07-21）：后端 9 模块划分、核心调用链、前端组件树、数据文件关系、开发环境搭建、新增功能指引
- **API 接口清单**（2026-07-21）：83 个 API 端点的参数和返回格式，14 个模块分组，含 SSE 事件汇总
- **软件开发经验总结**（2026-07-21）：从 P005 完整开发过程提炼的可复用方法论，覆盖文档管理、开发流程、测试策略、架构决策、AI 辅助开发五个维度，HTML 格式含图表和避坑清单，面向后续项目参考
- **用户记忆文件更新**（2026-07-21）：在 user_profile.md 补充文档去重规则、文档命名规范（活文档 vs 死文档）、定期清理节奏，并新增"新项目 AGENTS.md 必须包含文档维护规则"强制章节，让文档维护规则跨项目生效并传导到每个新项目的 AGENTS.md
- **过程文档整理**（2026-07-21）：按经验总结规则整理 P005 文档——AGENTS.md 补 3 条新规则（权威源/命名规范/定期清理）、重命名无日期前缀的审查报告、删除 README 与 CHANGELOG 重复的迭代记录表、文档维护规范升级 v1.2（新增单一权威来源和定期清理两节）

### 新增
- **TODO 看板面板**（2026-07-22）：新增 `TodoPanel.vue` 组件，以卡片形式展示对话级 TODO 清单，支持折叠/展开、状态颜色区分（pending=灰色/in_progress=蓝色/completed=绿色）、空状态提示、刷新按钮。`ChatWindow.vue` 顶部栏新增 TODO 切换按钮，右侧可展开侧边面板（默认折叠，仅在有当前对话时显示）。`stores/agent.js` 新增 `todoRefreshTrigger` 状态变量，在 `tool_end` 事件中检测 `create_todo_list`/`update_todo_status` 工具调用后自动触发 TodoPanel 刷新
- **API 配置开关控制 + 捐赠打赏页面**（2026-07-22）：模型配置新增 `enabled` 字段，可独立启用/禁用每个配置（禁用后调用返回提示）；设置面板新增"关于与支持"页面，含项目介绍、捐赠二维码占位、使用说明。后端：`ModelConfigCreate/Update` 加 `enabled` 字段 + `get_llm_client_and_config` 检查开关。前端：`ModelConfigPage` 表单加开关 + 列表禁用标记 + 新建 `AboutPage.vue`
- **智能体管理弹窗记忆与统计展示**（2026-07-22）：在 `Sidebar.vue` 智能体管理弹窗中，每个智能体条目下方新增折叠式"记忆与统计"区域。弹窗打开时并行加载所有智能体的记忆条数（`api.getAgentMemory`）和性能统计（`api.getAgentStats`），展示记忆条数、已完成任务数、最后活跃时间，并提供清空记忆按钮（`api.clearAgentMemory`，含确认对话框）。使用 `el-collapse` 折叠展示，scoped 样式，记忆区域浅灰背景、统计数字蓝色突出、清空按钮红色文字

### 修复
- **多项目并行时消息并发写入丢失**（2026-07-22）：`messages.json` 的 `load → append → save` 不是原子事务，两个项目同时 SSE 时后保存的会覆盖先保存的（lost update）。新增 5 个原子消息函数（`append_message`/`append_messages`/`remove_messages_by_ids`/`clear_conversation_messages_atomic`/`delete_conversation_messages_atomic`），用 `_json_write_lock` 包住整个 load-modify-save 事务。改造 14 处保存点（chat_stream 8处 + regenerate 3处 + chat 1处 + clear/delete conversation 2处）。3项目×3轮并发测试 21 条消息零丢失

- **后端事件循环阻塞 + 前端竞态条件综合修复**（2026-07-22）：根因是后端 `async def generate()` 内部调用同步 LLM 函数阻塞 FastAPI 事件循环，导致 SSE 运行时所有 API 请求挂起；前端 `selectConversation` 的 `await` 期间 SSE 事件丢失。后端：2 处 `generate()` 改为同步 generator（Starlette 自动线程池运行）+ 23 处 `await asyncio.sleep()` 改为 `time.sleep()` + `Generator` 类型标注修正。前端：新增 `_isSwitching` 标志（切换期间 SSE 事件走缓存）+ `loadMessages` 加 convId 参数防过期覆盖 + finally 块条件重置 loading + `clearConversationMessages` 加 stopGeneration。浏览器端到端测试全部通过（连续 3 次切换均正常，后端非阻塞验证通过）

- **后台运行消息显示异常**（2026-07-21）：`_swapToStream` 引用交换方案有异步 bug（`done` 事件的 `loadMessages` 在 swap 恢复后执行，用错误的 convId 加载）。用"事件缓存+重放"方案替换：SSE 事件在用户切走时缓存到 `pendingEvents`，切回来时从快照恢复+重放。删除了 swap 机制和 localStorage 兜底

### 修复
- **页面切换时项目丢失**（2026-07-21）：修复两个 Bug——(A) 项目间切换时 SSE 未中止导致消息污染，(B) 切到团队/元团队视图时流式消息仅存内存导致返回时丢失。在 `selectConversation`、`selectTeam`、`showMetaTeamPanel` 中增加 SSE 中止 + 消息保存到 localStorage 机制，返回时自动恢复
- **P0/P1 遗留问题修复**（2026-07-21，第二轮审查后续）：
  - P0-01：tasks 目录权限最小化——移除 6 处代码中的 `tasks_abs` 权限授予（`create_conversation`、`api_apply_blueprint`、`update_conversation_path`、`reset_structure`、`init_project_structure` 工具、`create_team_member` 工具），`create_task` 流程已按任务授权
  - P0-02：蓝图深度校验接入 `api_apply_blueprint`——将 `sb_validate_bp_data`（浅层校验）替换为 `validate_blueprint`（深度校验：模板有效性、名称非空、提示词非空、成员唯一性、循环依赖检测）
  - P1-01：`skill_blueprint.py` `_save_json` 改为原子写入（`threading.RLock` + `tempfile.mkstemp` + `os.replace`），`_load_json` 区分 `JSONDecodeError` 和 `OSError`
  - P1-02：3 个组件 5 处 SSE 解析 `.slice(5).trim()` 改为 `.slice(6)`（AgentThread.vue、MetaTeamTask.vue、MetaTeamReviewDialog.vue）
  - P1-03：移除 Sidebar.vue 中未实现的"快速模式" UI 选项
  - 5 项 API 功能测试全部通过 + 前端构建验证通过

### 变更
- **文档维护规范 v2.0 撤回**（2026-07-21）：上一轮误创建的 v2.0（给 P005 内部智能体用的规范）方向错误，与用户意图（总结可复用开发经验）不符，已删除。其可复用部分（单一权威来源、追加式记录、活文档 vs 死文档、定期清理）已提炼到软件开发经验总结报告中。P005 内部文档规范仍以 v1.1（`20260719-文档维护规范.md`）为准

### 修复
- **2 个严重 bug**（2026-07-21，LLM 长任务测试发现）：
  - `msg.thinking_override` 属性不存在（字段名是 `enable_thinking`），导致多智能体协作时 SSE 流中断
  - `execute_tool` 中 invoke_sub_agent 引用未定义的 `thinking_override` 变量

## [v0.4.0] - 2026-07-21

### 修复
- **5 项 P2 原型阶段优化**（2026-07-21）：
  - TeamHome 技能图标字段错误（sk.emoji → sk.icon）
  - 技能使用计数函数接入（工具执行后增加计数）
  - read_file 添加 10MB 大小上限（防止内存耗尽）
  - 5 个 DELETE 接口返回格式统一为 `{status:"ok"}`
  - 确认死代码已在之前清理完毕
  - 8 项测试全部通过
- **4 项 P1 代码重复和元团队逻辑修复**（2026-07-21）：
  - 代码重复：抽取 `utils/fileIcons.js`（统一 4 处文件图标映射）+ `utils/toolIcons.js`（统一 3 处工具图标和名称映射，修复 AgentThread 只有 4 个工具映射的不一致问题）
  - 元团队逻辑：评审专家优先使用蓝图原设计成员（回退到默认专家）+ 异常事件检测改为基于消息元数据字段（不再字符串匹配误报）
  - 8 项测试全部通过
- **14 项 P1 问题修复**（2026-07-21）：
  - 安全加固：tasks 目录权限最小化 + 文件上传限制（10MB+危险扩展名黑名单）+ 幻觉检测覆盖子智能体 + write_file/edit_file 回读校验
  - 数据一致性：create_conversation/create_team/load_agents/apply_blueprint 补全 enabled_skills 和 can_invoke_sub_agent + populateEditForm 补全三字段
  - 功能完善：invoke_sub_agent 传递 thinking_override + extra_rounds 改用隔离上下文 + 蓝图导入校验 + load_json 异常处理改进
  - 前端清理：删除 ApiConfigDialog.vue 死代码 + SSE data 解析修复 .trim() 问题
  - 10 项 API 功能测试全部通过（详见 `docs/05-审查/20260721-P1优化计划.md`）
- **12 项 P0/P1 问题修复**（2026-07-21）：
  - `backend/main.py`：save_json 原子写入（临时文件+os.replace）+ 并发锁（RLock）+ POST/PUT model-configs api_key 脱敏 + read_image_file 权限校验 + 并行调度传递 default_config_id/thinking_override + 蓝图深度校验（模板/名称/提示词）+ input 目录保护扩展到 edit_file/create_directory + conv_agents 未定义变量修复 + import os
  - `backend/skill_blueprint.py` + `backend/skills.json`：移除未实现的 create_meta_task 工具声明
  - `frontend/src/stores/agent.js`：regenerateMessage 添加 AbortController 支持和中止处理
  - `frontend/src/components/ChatWindow.vue` + `AgentThread.vue`：移除 deep watch messages 改为轻量监听 + 添加 onBeforeUnmount 清理 SSE
  - `frontend/src/components/MetaTeamTask.vue` + `MetaTeamReviewDialog.vue`：添加 onBeforeUnmount 清理 SSE
  - `frontend/src/api/index.js`：getImageUrl 添加 agent_id 参数
  - 8 项 API 功能测试全部通过

### 文档
- **审查报告交叉对比**（2026-07-21）：逐项验证豆包报告的 11 个 P0 问题，9 个确认属实，2 个有偏差；合并两份报告形成优先修复清单（10 个 P0 + 2 个 P1）（详见 `docs/05-审查/20260721-审查报告交叉对比.html`）
- **AGENTS.md 重写**（2026-07-21）：从 522 行精简到 230 行（精简 56%）；新增"编写规范"6 条原则和"文件放置规则"表格；删除所有行号引用、历史问题表格、操作手册式内容；定位从"操作手册"改为"指向性指导"
- **死代码清理**（2026-07-21）：删除前端 4 个死代码 Store Action + 10 个死代码 API 方法 + 后端 2 个废弃占位端点（blueprint/validate、meta-team rerun）；前端构建和后端导入均验证通过
- **文档目录整理**（2026-07-21）：根目录 2 个报告移入 docs/05-审查；旧版功能范围清单 HTML 归档到 05-审查；删除已被 AGENTS.md 替代的旧版项目修改指南；更新 README.md 链接和状态标记
- **死代码与孤儿接口核查**（2026-07-21）：对后端 84 个 API 端点与前端全部 API 方法/Store Action 交叉比对，确认 0 项功能丢失；发现 4 个死代码 Store Action + 10 个死代码 API 方法 + 2 个废弃占位端点（详见 `docs/05-审查/20260721-死代码与孤儿接口核查报告.html`）
- **技术文档全面整理**（2026-07-21）：
  - `AGENTS.md`：更新元团队架构（从"固定四成员"改为"3 常驻专家 + 三阶段引擎"）；补充 teams.json、meta_team_config.json、meta_team_tasks/、meta_team_reviews/ 等数据文件；修正行号引用（偏差约 1071 行）；补充 v0.4.0 新增的 5 个后端文件和 5 个前端组件
  - `docs/02-范围/软件功能范围清单.md`：重写 3.12 元团队章节（常驻化、三阶段、评审闭环、专家管理）；修正项目结构（补充 10 个新文件）；更新 API 端点数量（45→60）；补充团队管理功能描述
  - `docs/README.md`：统一版本号为 v0.4.0；补充 07-测试 文档清单；补充元团队设计文档条目；修正实现状态表
  - `docs/04-设计/团队蓝图Schema规范.md`：状态从"Phase 1 实现中"更新为"已实现 v1.0"
  - `docs/04-设计/智能体分级与通用模板设计.md`：补充 v0.4.0 更新说明（工具数 19→24、模板分配机制）
  - `docs/03-指导/文档维护规范.md`：补全 07-测试 目录；统一 06-变更日志 为"每次有产出对话后及时维护"
- **数据文件字段补齐**（2026-07-21）：
  - `backend/data.json`：main 智能体补齐 model_config、enabled_skills、can_invoke_sub_agent 字段
  - `backend/teams.json`：main 智能体补齐 enabled_skills、can_invoke_sub_agent 字段
- **审查报告修订**（2026-07-21）：
  - `p005-code-review-report/p005-code-review-report.html`：经核实前端实际使用项目级接口（功能正常），将原 BE-S4/S5 从"严重"降级为"中级 BE-M11"；严重问题从 10 项调整为 8 项；更新统计图表和修复路线图
- **全面代码审查报告**（2026-07-21）：
  - 5个并行子代理分模块深度审查（后端/前端/安全/数据一致性/元团队蓝图），覆盖 ~19300 行代码
  - 发现 66 个问题：11 严重(P0) + 25 中级(P1) + 30 轻微(P2)
  - 关键问题：JSON无并发锁、非原子写入、明文api_key返回、权限绕过、并行配置丢失、蓝图深度校验缺失、SSE中止问题、deep watch性能问题
  - 总体评分 66/100，功能完整度 87%
  - 输出三阶段修复路线图（紧急加固1-2天/功能完善3-5天/架构优化1-2周）
  - 报告位置：`docs/05-审查/p005-comprehensive-code-review/p005-comprehensive-code-review.html`
- **第二轮代码审查报告**（2026-07-21）：
  - 3 个并行子代理逐项验证第一轮 66 项问题的修复情况
  - 54 项验证结果：36 已修复 + 7 部分修复 + 11 未修复（修复率 64%）
  - 综合评分 82/100（+16 vs 第一轮 66），功能完整度 95%
  - 遗留问题：2 严重(P0) + 4 中级(P1) + 7 轻微(P2)
  - 报告位置：`docs/05-审查/p005-code-review-round2/p005-code-review-round2.html`

### 新增
- **团队主页（TeamHome）**：
  - `frontend/src/components/TeamHome.vue`：新增团队主页组件，含团队信息卡、成员管理（添加/编辑/删除）、项目列表、创建项目入口
  - `backend/main.py`：新增 `POST/DELETE /api/teams/{team_id}/agents` 成员管理 API，自动同步到同团队所有项目
  - 点击团队名称进入主页，类似元团队的管理面板
- **新项目继承当前团队**：
  - `backend/main.py`：`POST /api/conversations` 支持 `inherit_from` 参数，从源对话复制智能体团队
  - `frontend/src/components/Sidebar.vue`：新建项目弹窗新增"继承团队"开关
- **导出当前团队为蓝图**：
  - `backend/main.py`：新增 `POST /api/conversations/{conv_id}/export-blueprint` 端点
  - `frontend/src/components/ChatWindow.vue`：顶部新增"📤 导出蓝图"按钮和导出对话框
- **删除专家功能**：
  - `backend/main.py`：`DELETE /api/meta-team/experts/{id}` 端点（至少保留 1 个专家）
  - `frontend/src/api/index.js`：`deleteMetaTeamExpert` 方法
  - `frontend/src/components/MetaTeamExperts.vue`：详情弹窗 footer 新增"删除专家"按钮（带确认对话框）
- **团队主页增强**：
  - `frontend/src/components/TeamHome.vue`：顶部栏新增"删除团队"按钮（红色 danger 样式，带项目数确认提示）；编辑成员弹窗新增"🧩 技能"多选下拉框和"🔧 子代理"开关（非 main 智能体）；添加成员弹窗完善为 7 字段（名称/头像/角色/模板下拉/系统提示/技能多选/子代理开关），支持模板自动生成提示词
  - `backend/main.py`：`POST/PUT /api/teams/{team_id}/agents` 支持 enabled_skills、can_invoke_sub_agent、template 字段
- **会话内创建成员自动同步团队**：
  - `backend/main.py`：`create_team_member` 工具在写入项目级 agents 后，检查 `team_id` 并同步追加到 `teams.json`
  - `frontend/src/stores/agent.js`：流式对话结束的 `finally` 块自动调用 `loadTeams()` 和 `loadConversationAgents()` 刷新数据

### 变更
- **侧边栏改为团队→项目两级树结构**：
  - `backend/main.py`：新增 teams.json 数据文件和团队 CRUD API；项目新增 team_id 字段；编辑智能体自动同步到同团队所有项目
  - `frontend/src/components/Sidebar.vue`：项目列表改为两级树（团队 > 项目）；"+ 新项目"改为"+ 新团队"
  - `frontend/src/stores/agent.js`：新增 teams 状态和团队管理 actions
- **侧边栏团队栏目 UI 优化**：
  - `frontend/src/components/Sidebar.vue`：团队卡片改为浅紫背景（`#e0e7ff`）+ 紫色边框（`#a5b4fc`）+ 阴影 + 左侧 3px 紫色竖条；团队头部字号 14px 加粗、图标 18px；项目数 badge 改为白字紫底；箭头紫色加粗；项目项独立白色背景卡片 + 选中态紫色；"＋/×"操作按钮改为透明无边框融入栏目（hover 时淡紫/淡红底色）；view-tabs 标签"📁 项目"改为"📁 团队"，搜索框 placeholder 改为"搜索团队或项目"
- **完善编辑智能体弹窗**：
  - `frontend/src/components/ChatWindow.vue`：编辑弹窗新增模型配置下拉框、技能绑定（非 main）、子代理开关（非 main），恢复原智能体管理弹窗的完整功能
- **左上角改为 Logo + 应用名称**：
  - `frontend/src/components/Sidebar.vue`：移除"我（主智能体）"下拉菜单，替换为 SVG Logo + "多智能体团队" + "Multi-Agent Studio" 品牌标识
- **项目对话右侧增加产出文件浏览面板**：
  - `frontend/src/components/ChatWindow.vue`：右侧面板改为 tab 切换式（📂 文件 / 📦 产出），产出 tab 自动提取对话中的代码块，点击可查看代码内容
- **首页卡片恢复模型配置等完整功能**：
  - `frontend/src/components/MetaTeamHome.vue`：卡片增加平均得分、经验次数、得分趋势、模型配置绑定下拉框、"查看详情"和"优化提示词"按钮
  - `frontend/src/components/MetaTeamExperts.vue`：新增 `openOptimize` prop，支持从首页直接打开优化弹窗
- **移除专家管理列表弹窗，整合到首页**：
  - `frontend/src/components/MetaTeamExperts.vue`：移除列表弹窗（外层 el-dialog），只保留详情弹窗、产出文件弹窗、优化弹窗
  - `frontend/src/components/Sidebar.vue`：移除"👥 专家管理"按钮和 MetaTeamExperts 组件
  - `frontend/src/components/MetaTeamHome.vue`：专家卡片列表直接作为管理入口，点击卡片打开详情
- **团队设计首页改造 + 新增专家 + 任务选择专家**：
  - `backend/main.py`：`POST /api/meta-team/experts` 端点 + `MetaTeamExpertCreate` 模型（名称+系统提示词+模型配置）
  - `frontend/src/components/MetaTeamHome.vue`：新建团队设计首页组件（专家卡片网格 + 新建任务按钮 + 新增专家表单）
  - `frontend/src/api/index.js`：`createMetaTeamExpert` 方法
  - `frontend/src/App.vue`：空状态替换为 MetaTeamHome 组件
  - `frontend/src/components/Sidebar.vue`：新建设计任务弹窗增加"参与专家"多选下拉框
  - `frontend/src/components/MetaTeamExperts.vue`：新增 `focusExpertId` prop，点击卡片自动打开对应专家详情
- **右侧产出文件面板点击查看**：
  - `backend/main.py`：`GET /api/meta-team/tasks/{id}/fusion-decision` 和 `GET /api/meta-team/tasks/{id}/blueprint/{version}` 端点
  - `frontend/src/api/index.js`：`getMetaTeamFusionDecision` 和 `getMetaTeamBlueprintVersion` 方法
  - `frontend/src/components/MetaTeamTask.vue`：右侧面板所有文件项（方案/评审/蓝图/融合决策）可点击查看，弹窗展示内容，蓝图 JSON 格式化为 Markdown
- **元团队 UI 优化（专家胶囊栏 + 搜索框 + 产出文件查看）**：
  - `backend/main.py`：`GET /api/meta-team/tasks/{id}/proposal/{expert_id}` 和 `GET /api/meta-team/tasks/{id}/review/{expert_id}` 端点（读取专家在设计任务中的方案/评审文件内容）
  - `frontend/src/api/index.js`：`getMetaTeamProposal` 和 `getMetaTeamReviewFile` 方法
  - `frontend/src/components/MetaTeamTask.vue`：顶部专家胶囊栏（头像+名称+版本号，点击切换对话对象，渐变高亮选中状态）
  - `frontend/src/components/Sidebar.vue`：团队设计任务列表上方搜索框（实时按标题关键词过滤）
  - `frontend/src/components/MetaTeamExperts.vue`：经验记录卡片新增"📄 查看方案"和"📝 查看评审"按钮，弹出子对话框展示产出文件内容（Markdown 渲染）
- **元团队 Phase 4 优化（第二批：提示词版本历史 + 诊断对比）**：
  - `backend/meta_team_config.py`：`upgrade_prompt_version` 升级时自动保存旧版本到 `prompt_history`；`get_prompt_history` 获取版本历史；`rollback_prompt_version` 回退到指定版本（当前版本自动备份）
  - `backend/main.py`：`GET /api/meta-team/experts/{id}/prompt-history` 和 `POST /api/meta-team/experts/{id}/rollback-prompt` 端点
  - `frontend/src/api/index.js`：`getMetaTeamExpertPromptHistory` 和 `rollbackMetaTeamExpertPrompt` 方法
  - `frontend/src/components/MetaTeamExperts.vue`：版本历史时间线 UI（版本标签+日期+升级原因+提示词内容折叠+回退按钮+确认对话框）
  - `frontend/src/components/MetaTeamReviewDialog.vue`：专家诊断对比折叠面板（展示各专家完整诊断内容）
- **元团队 Phase 4 优化（第一批：自动流转 + 超时处理 + 报告导出）**：
  - `backend/meta_team_engine.py`：`_call_with_retry` 超时重试辅助函数（90s 超时 + 1 次重试）
  - `backend/meta_team_engine.py`：`run_all_phases` 深度模式一键全流程生成器（方案撰写→评审→融合自动流转）
  - `backend/main.py`：`POST /api/meta-team/tasks/{id}/run-all` SSE 端点
  - `frontend/src/api/index.js`：`metaTeamRunAllStream` 方法
  - `frontend/src/components/MetaTeamTask.vue`："🚀 一键全流程"按钮 + `all` 模式事件处理
  - `frontend/src/components/MetaTeamReviewDialog.vue`："📄 导出报告"功能（Blob 下载 Markdown 文件）
- **元团队常驻化 Phase 3（评审闭环与专家进化）**：
  - `backend/meta_team_review.py`：元团队评审引擎（七维度输入采集 + 专家并行诊断 + 主智能体汇总报告 + 评审记录存储 + 专家经验联动）
  - `backend/main.py`：3 个评审 API 端点（POST /review 启动 SSE、GET /review/{id} 获取报告、GET /review 列表）
  - `frontend/src/api/index.js`：3 个评审 API 方法
  - `frontend/src/components/MetaTeamReviewDialog.vue`：评审对话框（数据预览 + 主观反馈 + 三阶段进度步骤条 + 实时日志 + 报告展示 + 历史评审列表）
  - `frontend/src/components/ChatWindow.vue`：顶部栏增加"🔍 元团队评审"按钮（仅 blueprint_source 存在时显示）
- **元团队常驻化 Phase 2（深度模式多专家并行调度）**：
  - `backend/meta_team_engine.py`：三阶段执行引擎（方案撰写 / 评审 / 融合），ThreadPoolExecutor 并行调用专家，SSE 流式推送进度
  - `backend/main.py`：3 个 SSE 端点（run-proposals / run-reviews / run-fusion）
  - `frontend/src/api/index.js`：3 个流式 API 方法
  - `frontend/src/components/MetaTeamTask.vue`：阶段控制按钮 + 系统消息渲染 + SSE 事件处理
- **元团队常驻化 Phase 1（架构持久化）**：
  - `backend/meta_team_config.py`：常驻专家管理模块（CRUD + 经验记录 + 提示词版本管理 + 3 个默认专家初始化）
  - `backend/meta_team_task.py`：设计任务存储模块（CRUD + 消息管理 + 产出文件管理 + 蓝图版本管理）
  - `backend/main.py`：注册 14 个 `/api/meta-team/*` API 端点（任务 CRUD + SSE 对话 + finalize + 专家管理 + 提示词优化/升级 + 全局设置）
  - `frontend/src/components/MetaTeamTask.vue`：设计任务详情页组件（SSE 流式对话 + 产出文件面板 + 确认产出）
  - `frontend/src/components/MetaTeamExperts.vue`：专家管理弹窗（专家卡片 + 经验记录 + 提示词优化升级 SSE 流程）
  - `frontend/src/api/index.js`：元团队 API 封装（15 个方法）
  - `frontend/src/stores/agent.js`：元团队状态管理（sidebarView + metaTeamTasks + 元团队 actions）
  - `frontend/src/components/Sidebar.vue`：视图切换标签栏（项目/团队设计）+ 元团队任务列表 + 新建设计任务弹窗
  - `frontend/src/App.vue`：主区域视图切换（ChatWindow/MetaTeamTask）
- AGENTS.md 第十二节"过程文档维护规则"：定义过程文档分类、维护频率、触发门槛和维护边界
- 用户记忆追加"工作偏好：项目过程文档自动维护"
- `docs/06-变更日志/20260720-会话纪要.md`：首次创建会话纪要文件
- `docs/04-设计/20260720-元团队常驻化与工作模式重构方案.md`：元团队常驻化架构方案 + 全栈专家并行工作模式
- 元团队重构方案核心决策确认（14 项 D1-D14）

### 变更
- 元团队从"项目类型"重构为"常驻功能模块"（侧边栏一级入口）
- `frontend/src/components/Sidebar.vue`：新建项目弹窗移除"元团队规划"选项
- `backend/main.py`：`create_meta_team` 接口标记为废弃（返回 410 Gone）
- 后端启动时自动初始化元团队专家配置和任务目录
- `frontend/src/components/MetaTeamTask.vue`：`loadTask` 改为保留前端系统消息，避免阶段进度被刷新覆盖
- `backend/meta_team_review.py`：`get_review` 返回专家诊断时 `content_preview` 改为 `content`（返回完整内容而非截断预览）

### 修复
- `frontend/src/components/TeamHome.vue`：点击项目卡片无法进入对话——`handleSelectProject` 改为先 `exitTeamHome()` 再 `await selectConversation()`（原顺序导致视图切换时数据未就绪）
- `frontend/src/components/Sidebar.vue`：侧边栏点击团队下项目无法进入对话——`handleSelectConv` 新增 `store.exitTeamHome()` 调用（原仅 `selectConversation` 未退出团队主页，导致 App.vue 仍渲染 TeamHome）
- `frontend/src/stores/agent.js`：删除团队内项目后 UI 不实时更新——`deleteConversation` action 新增 `this.loadTeams()` 刷新团队数据（原仅更新 conversations，团队主页项目列表和侧边栏 count 未刷新）
- `frontend/src/components/Sidebar.vue`：团队操作按钮（＋/×）默认不可见——根因是 `action-btn`/`delete-btn` class 命中了项目列表的 `opacity: 0` 规则；改为独立 class 名 `team-action-btn`/`team-delete-btn`
- `backend/meta_team_engine.py`：`get_expert_context` 函数名修正为 `get_expert_context_for_task`
- `backend/meta_team_engine.py`：`call_llm_complete` 增加错误检测（`call_llm_stream` yield 的 "❌" 开头错误消息识别为异常抛出）
- `frontend/src/components/MetaTeamTask.vue`：中止阶段后 `loadTask` 未调用导致按钮状态错误，改为在 `finally` 块中同步任务状态
- `frontend/src/components/MetaTeamReviewDialog.vue`：`defineProps` TypeScript 语法改为 JavaScript 运行时声明

### 文档
- 文档维护体系：CHANGELOG.md + 文档维护规范 + 状态标签机制
- `docs/06-变更日志/` 目录（重大变更的详细记录）

---

## [v0.4.0] - 2026-07-20

### 新增
- **技能绑定到智能体**（Phase 3 缺失1）：
  - `AgentCreate`/`AgentUpdate` 新增 `enabled_skills` 字段
  - `call_llm_stream_with_tools` 工具过滤逻辑增强：按 `enabled_skills` 合并技能附带的工具，并注入技能 `system_prompt_fragment` 到系统提示词
  - 前端智能体管理弹窗新增技能多选下拉框（支持 collapse-tags 折叠显示）
- **子代理调用插件**（Phase 3 缺失2）：
  - `invoke_sub_agent` 工具定义加入 `TOOL_DEFINITIONS`
  - `execute_tool` 实现完整子代理执行逻辑：创建临时子代理（不写入 conversations.json）、非递归（强制 `can_invoke_sub_agent=False`）、最大 8 轮工具循环、继承父智能体权限和模型配置、使用 `collect_stream_sync` 同步收集回复
  - `can_invoke_sub_agent` 字段加入 `AgentCreate`/`AgentUpdate`
  - 前端智能体管理弹窗新增子代理开关（el-switch）
- **蓝图应用技能分配**（Phase 3 缺失3）：
  - `api_apply_blueprint` 读取 `member.skills` 和 `member.can_invoke_sub_agent`，应用到创建的智能体上
- **`create_team_member` 工具支持新字段**：
  - 工具定义新增 `skills` 和 `can_invoke_sub_agent` 参数
  - 执行逻辑读取并保存这两个字段
  - 创建结果提示显示技能绑定和子代理能力状态
- **UI 布局调整**：
  - "管理智能体"入口合并到左上角智能体下拉菜单底部（分隔线 + "👥 管理智能体…" 选项）
  - "设置"按钮从侧边栏中部移到左下角 footer
  - 清理不再使用的 settings-entry/settings-btn 相关 CSS
- **跨组件状态管理**：agent store 新增 `agentManageDialogVisible` 状态，支持 ChatWindow 等其他组件触发智能体管理弹窗

### 变更
- 智能体管理弹窗的 `agentDialogVisible` 改为 computed 绑定 store，支持跨组件控制
- 前端 `handleSelectAgent` 函数增加 `manage` 命令分支，用于打开管理弹窗
- `execute_tool` 函数签名扩展：新增 `agent: dict = None` 和 `default_config_id: str = ""` 参数（为 `invoke_sub_agent` 提供上下文）

### 文档
- 更新 `AGENTS.md`（项目修改指南）至 v0.3.0 配套版本，新增工具分配规则、三大扩展系统说明、防幻觉机制四层防御、已修复历史问题表
- 更新 `docs/02-范围/20260720-软件功能范围清单.md` 至 v1.1，补充技能绑定、子代理调用、蓝图技能分配、UI 调整等内容
- 新增 `docs/06-变更日志/20260720-v0.4.0-Phase3技能与子代理.md` 详细变更记录

### 测试
- 新增 Phase 3 端到端测试脚本（`skill_blueprint_e2e_test.py` 扩展），23/23 项全部通过
- 覆盖：技能系统基础、智能体技能绑定持久化、蓝图应用技能分配、工具定义与字段验证

---

## [v0.3.0] - 2026-07-19

### 新增
- **智能体分级与通用模板系统**：5 个通用角色模板（creator/reviewer/analyst/worker/coordinator）
  - `create_team_member` 支持 `template` / `domain_hint` / `style_guide` 参数
  - 工具 schema 按模板过滤（reviewer 只读、creator 读写等）
  - 智能体对象新增 `template` 字段
- **代码搜索与编辑工具**（P0 能力提升）：
  - `grep` 工具：文件内容正则搜索
  - `glob` 工具：文件名模式匹配
  - `edit_file` 工具：SEARCH/REPLACE 精确编辑
- **文件归档工具**：
  - `move_file` 工具：移动文件（归档产出用）
  - `copy_file` 工具：复制文件
- **开启新任务功能**：清空当前项目对话历史，保留团队成员和项目文件
  - 后端接口 `POST /api/conversations/{id}/clear-messages`
  - 前端"✨ 开启新任务"按钮
- **团队上下文自动注入**：主智能体被调用时自动看到现有成员列表
- **`.agent` 目录在文件面板可见**：用户可查看智能体的任务产出

### 变更
- `max_tool_rounds` 从 8 提到 12（归档场景需要更多轮次）
- 工具调用达上限时追加一轮让 LLM 收尾总结（不再卡在"正在归档"）
- 主智能体系统提示词强化：
  - 新增"角色边界"规则（区分用户指令和系统通知）
  - 新增"真实性约束"（禁止编造文件路径和 task_id）
  - 新增"工具使用策略"（何时用 grep/glob/edit_file）
- 子智能体工作手册更新：明确列出可用工具和使用建议
- `create_team_member` 工具 schema 的 `system_prompt` 改为可选（与 template 二选一）

### 修复
- **主智能体重复造人**：新增 `get_team_context_for_main` 自动注入团队信息 + role 相似度检测
- **创建成员后页面不刷新**：`tool_end` 事件触发 `loadConversationAgents()`
- **主智能体把汇报当指令**：汇报消息改用"【系统通知：...】"措辞
- **归档失败但说已归档**：根因是缺少 `move_file` 工具（已在本次新增）
- **`.agent/tasks` 目录在文件面板不显示**：`list_files` 不再跳过 `.agent`

### 文档
- 新增 `docs/04-设计/20260719-智能体分级与通用模板设计.md`
- 整理文档目录：根目录散落文件统一归入 `docs/` 分类目录
- 文件名加日期前缀（YYYYMMDD-中文名.扩展名）
- 新建 `docs/README.md` 总索引

---

## [v0.2.0] - 2026-07-18

### 新增
- 项目修改指南 `agents.md`（给 AI 助手的修改指引）
- 软件功能范围清单（`feature-scope/`）
- 项目代码检查报告（`项目检查报告.html`）
- 代码审查报告（`code-review-report/`）

### 变更
- 后端代码扩展到约 2770 行（`backend/main.py`）
- 工具体系从基础读写扩展到任务管理、团队管理

---

## [v0.1.0] - 2026-07-17

### 新增
- **项目初始版本**：多智能体团队协作平台
- 核心功能 F1-F8 全部实现：
  - F1 聊天主界面（Vue 3 + Element Plus）
  - F2 智能体角色配置
  - F3 文件夹权限（白名单控制）
  - F4 主智能体调度（@mention 链式调度）
  - F5 API 配置面板（本地/云端多模型）
  - F6 智能体新建/删除
  - F7 聊天记录保存（messages.json 持久化）
  - F8 多模型切换
- 技术规划文档（`技术规划.md`）

---

## 维护说明

### 如何新增一条记录

1. 在 `[未发布]` 节点下，按分类（新增/变更/修复/文档）添加一行
2. 格式：`- **功能名**：简短描述`
3. 如果是大改动，在 `docs/06-变更日志/` 建详细文档

### 如何发版

1. 把 `[未发布]` 改成 `[vX.Y.Z] - YYYY-MM-DD`
2. 在顶部新增一个空的 `[未发布]` 节点
3. 更新 `README.md` 的"当前版本"字段

### 参考规范
- [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)
- [语义化版本](https://semver.org/lang/zh-CN/)
