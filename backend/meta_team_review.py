# -*- coding: utf-8 -*-
"""
元团队评审引擎（Phase 3）

实现"设计-使用-反馈"闭环：蓝图应用后的项目运行一段时间，用户可触发元团队评审，
让专家回头看这个团队设计得好不好，产出评审报告。

七维度评审输入采集：
  1. 原始蓝图（当初的设计意图）
  2. 团队配置现状（对比设计 vs 现状）
  3. 任务执行统计（完成率、失败率）
  4. 任务结果摘要（最近 N 个任务）
  5. 消息交互摘要（总消息数、按智能体统计）
  6. 异常事件记录（幻觉警告、工具失败）
  7. 用户主观反馈（可选文字）

执行流程：
  1. 采集评审输入包
  2. 专家并行诊断（每位专家独立看输入包，产出诊断意见）
  3. 主智能体汇总报告（健康度评分 + 问题诊断 + 改进建议 + 是否建议重新设计）
  4. 评审报告存档 + 追加专家经验

存储结构：
  backend/meta_team_reviews/{review_id}/
    ├── meta.json              # 评审元数据
    ├── input.json             # 评审输入包（七维度）
    ├── expert_diagnoses/      # 各专家诊断
    │   ├── expert_1.md
    │   └── ...
    └── report.md              # 最终评审报告
"""

import json
import uuid
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import meta_team_config as mtc
from meta_team_engine import call_llm_complete, auto_select_models, MAX_EXPERT_PARALLEL, _call_with_retry

BASE_DIR = Path(__file__).parent
REVIEWS_DIR = BASE_DIR / "meta_team_reviews"

# 最近 N 个任务结果摘要（避免 token 爆炸）
MAX_TASK_SUMMARIES = 10
# 最近消息摘要的时间窗口（按消息条数限制）
MAX_RECENT_MESSAGES = 50


# =========================================================================
# 评审记录存储管理
# =========================================================================

def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def _review_dir(review_id: str) -> Path:
    d = REVIEWS_DIR / review_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "expert_diagnoses").mkdir(exist_ok=True)
    return d


def create_review_record(conversation_id: str, project_title: str,
                         blueprint_source: str) -> dict:
    """创建评审记录，返回元数据"""
    review_id = "review_" + uuid.uuid4().hex[:12]
    meta = {
        "review_id": review_id,
        "conversation_id": conversation_id,
        "project_title": project_title,
        "blueprint_source": blueprint_source,
        "status": "collecting",   # collecting -> diagnosing -> summarizing -> completed
        "created_at": _now(),
        "updated_at": _now(),
    }
    d = _review_dir(review_id)
    with open(d / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return meta


def update_review_status(review_id: str, status: str):
    """更新评审状态"""
    meta_path = REVIEWS_DIR / review_id / "meta.json"
    if not meta_path.exists():
        return
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    meta["status"] = status
    meta["updated_at"] = _now()
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def save_review_input(review_id: str, input_data: dict):
    """保存评审输入包"""
    d = REVIEWS_DIR / review_id
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "input.json", "w", encoding="utf-8") as f:
        json.dump(input_data, f, ensure_ascii=False, indent=2)


def save_expert_diagnosis(review_id: str, expert_id: str, content: str):
    """保存单个专家的诊断"""
    d = REVIEWS_DIR / review_id / "expert_diagnoses"
    d.mkdir(parents=True, exist_ok=True)
    with open(d / f"{expert_id}.md", "w", encoding="utf-8") as f:
        f.write(content)


def save_review_report(review_id: str, report: str, report_data: dict | None = None):
    """保存最终评审报告"""
    d = REVIEWS_DIR / review_id
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "report.md", "w", encoding="utf-8") as f:
        f.write(report)
    if report_data:
        with open(d / "report_data.json", "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
    update_review_status(review_id, "completed")


def get_review(review_id: str) -> dict | None:
    """获取评审完整详情（元数据 + 输入包摘要 + 专家诊断列表 + 报告）"""
    d = REVIEWS_DIR / review_id
    if not d.exists():
        return None

    # 读取元数据
    with open(d / "meta.json", "r", encoding="utf-8") as f:
        meta = json.load(f)

    # 读取输入包（可能很大，只返回摘要字段）
    input_summary = {}
    input_path = d / "input.json"
    if input_path.exists():
        with open(input_path, "r", encoding="utf-8") as f:
            input_data = json.load(f)
        input_summary = {
            "has_blueprint": bool(input_data.get("original_blueprint")),
            "team_name": input_data.get("original_blueprint", {}).get("name", ""),
            "current_member_count": len(input_data.get("current_agents", [])),
            "task_stats": input_data.get("task_stats", {}),
            "message_stats": input_data.get("message_stats", {}),
            "anomaly_stats": input_data.get("anomaly_stats", {}),
            "user_feedback": input_data.get("user_feedback", ""),
        }

    # 读取专家诊断列表
    diagnoses = []
    diag_dir = d / "expert_diagnoses"
    if diag_dir.exists():
        for f in diag_dir.glob("*.md"):
            expert_id = f.stem
            content = f.read_text(encoding="utf-8")
            expert = mtc.get_expert(expert_id)
            diagnoses.append({
                "expert_id": expert_id,
                "expert_name": expert["name"] if expert else expert_id,
                "content_length": len(content),
                "content": content
            })

    # 读取报告
    report = ""
    report_path = d / "report.md"
    if report_path.exists():
        report = report_path.read_text(encoding="utf-8")

    return {
        **meta,
        "input_summary": input_summary,
        "expert_diagnoses": diagnoses,
        "report": report
    }


def list_reviews(conversation_id: str | None = None) -> list[dict]:
    """列出评审记录（可按项目筛选），按时间倒序"""
    if not REVIEWS_DIR.exists():
        return []
    result = []
    for d in REVIEWS_DIR.iterdir():
        if not d.is_dir():
            continue
        meta_path = d / "meta.json"
        if not meta_path.exists():
            continue
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if conversation_id and meta.get("conversation_id") != conversation_id:
                continue
            result.append({
                "review_id": meta.get("review_id"),
                "conversation_id": meta.get("conversation_id"),
                "project_title": meta.get("project_title"),
                "blueprint_source": meta.get("blueprint_source"),
                "status": meta.get("status"),
                "created_at": meta.get("created_at"),
                "has_report": (d / "report.md").exists()
            })
        except Exception:
            continue
    result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return result


# =========================================================================
# 七维度评审输入采集
# =========================================================================

def collect_review_input(conversation_id: str, user_feedback: str = "") -> dict:
    """
    采集七维度评审输入包

    Args:
        conversation_id: 项目 ID
        user_feedback: 用户主观反馈（可选）

    Returns:
        包含七维度信息的字典
    """
    # 延迟导入避免循环依赖
    from main import load_conversations, load_messages
    from skill_blueprint import get_blueprint as sb_get_blueprint

    conversations = load_conversations()
    conv = next((c for c in conversations if c["id"] == conversation_id), None)
    if not conv:
        raise ValueError(f"项目 {conversation_id} 不存在")

    blueprint_source = conv.get("blueprint_source", "")
    root_path = conv.get("root_path", "")

    # ===== 维度 1：原始蓝图 =====
    original_blueprint = None
    if blueprint_source:
        bp = sb_get_blueprint(blueprint_source)
        if bp:
            original_blueprint = {
                "id": bp.get("id"),
                "name": bp.get("name"),
                "blueprint_data": bp.get("blueprint_data", {})
            }

    # ===== 维度 2：团队配置现状 =====
    current_agents = []
    for a in conv.get("agents", []):
        current_agents.append({
            "id": a.get("id"),
            "name": a.get("name"),
            "role": a.get("role", ""),
            "template": a.get("template", ""),
            "allowed_paths_count": len(a.get("allowed_paths", [])),
            "has_model_config": bool(a.get("model_config")),
            "enabled_skills": a.get("enabled_skills", []),
            "can_invoke_sub_agent": a.get("can_invoke_sub_agent", False),
        })

    # ===== 维度 3 & 4：任务执行统计 + 任务结果摘要 =====
    task_stats = {"total": 0, "completed": 0, "pending": 0, "failed": 0}
    task_summaries = []
    if root_path:
        tasks_dir = Path(root_path) / ".agent" / "tasks"
        if tasks_dir.exists():
            for task_dir in tasks_dir.iterdir():
                if not task_dir.is_dir():
                    continue
                meta_file = task_dir / "meta.json"
                if not meta_file.exists():
                    continue
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        task_meta = json.load(f)
                    task_stats["total"] += 1
                    status = task_meta.get("status", "unknown")
                    if status in ("completed", "done"):
                        task_stats["completed"] += 1
                    elif status in ("pending", "in_progress", "running"):
                        task_stats["pending"] += 1
                    elif status in ("failed", "error"):
                        task_stats["failed"] += 1
                    # 收集任务摘要
                    task_summaries.append({
                        "task_id": task_meta.get("task_id", task_dir.name),
                        "description": task_meta.get("description", "")[:200],
                        "status": status,
                        "assignee": task_meta.get("assignee", ""),
                        "result_files": task_meta.get("result_files", []),
                        "created_at": task_meta.get("created_at", "")
                    })
                except Exception:
                    continue
    # 只保留最近 N 个任务摘要
    task_summaries.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    task_summaries = task_summaries[:MAX_TASK_SUMMARIES]

    # ===== 维度 5 & 6：消息交互摘要 + 异常事件记录 =====
    message_stats = {
        "total": 0,
        "by_agent": {},
        "last_message_time": ""
    }
    anomaly_stats = {
        "hallucination_warnings": 0,
        "tool_errors": 0,
        "error_messages": 0
    }

    all_messages = load_messages()
    conv_messages = [m for m in all_messages if m.get("conversation_id") == conversation_id]
    message_stats["total"] = len(conv_messages)

    for msg in conv_messages:
        agent_id = msg.get("agent_id", "main")
        message_stats["by_agent"][agent_id] = message_stats["by_agent"].get(agent_id, 0) + 1

        # 检测异常事件（P1-M03 修复：改为基于消息元数据字段，不用字符串匹配）
        role = msg.get("role", "")

        # 幻觉警告：检查消息是否有幻觉检测标记字段
        # 后端 detect_hallucination 检测到幻觉时会在消息上设置此字段
        if msg.get("hallucination_detected") or msg.get("has_hallucination"):
            anomaly_stats["hallucination_warnings"] += 1
        # 回退：检查内容中是否有系统注入的幻觉警告标记（以特定前缀开头）
        elif content := msg.get("content", ""):
            if content.startswith("⚠️【系统检测到幻觉】"):
                anomaly_stats["hallucination_warnings"] += 1

        # 工具调用错误：检查工具状态字段，而非字符串匹配
        if role == "tool":
            if msg.get("tool_status") == "error" or msg.get("is_error"):
                anomaly_stats["tool_errors"] += 1

        # 错误消息
        if role == "error" or msg.get("is_error"):
            anomaly_stats["error_messages"] += 1

    if conv_messages:
        message_stats["last_message_time"] = conv_messages[-1].get("created_at", "")

    # ===== 维度 7：用户主观反馈 =====
    # 直接使用参数传入的 user_feedback

    return {
        "conversation_id": conversation_id,
        "project_title": conv.get("title", ""),
        "blueprint_source": blueprint_source,
        "original_blueprint": original_blueprint,
        "current_agents": current_agents,
        "task_stats": task_stats,
        "task_summaries": task_summaries,
        "message_stats": message_stats,
        "anomaly_stats": anomaly_stats,
        "user_feedback": user_feedback,
        "collected_at": _now()
    }


def _format_review_input_for_llm(input_data: dict) -> str:
    """将评审输入包格式化为 LLM 可读的文本"""
    parts = []

    # 原始蓝图
    bp = input_data.get("original_blueprint")
    if bp:
        parts.append("## 1. 原始蓝图（当初的设计意图）")
        parts.append(f"蓝图名称：{bp.get('name', '未命名')}")
        bp_data = bp.get("blueprint_data", {})
        parts.append(f"团队名称：{bp_data.get('team_name', '')}")
        parts.append(f"团队描述：{bp_data.get('description', '')}")
        parts.append(f"成员数量：{len(bp_data.get('members', []))}")
        # 列出成员概况
        for m in bp_data.get("members", []):
            parts.append(f"  - {m.get('name', '')}（{m.get('role', '')}）")
        parts.append(f"任务数量：{len(bp_data.get('tasks', []))}")
        parts.append(f"执行建议：{bp_data.get('execution_tips', '')}")
    else:
        parts.append("## 1. 原始蓝图\n（未找到原始蓝图数据）")

    # 团队配置现状
    agents = input_data.get("current_agents", [])
    parts.append(f"\n## 2. 团队配置现状（共 {len(agents)} 个成员）")
    for a in agents:
        skills = ", ".join(a.get("enabled_skills", [])) or "无"
        parts.append(
            f"  - {a['name']}（ID: {a['id']}）\n"
            f"    角色: {a['role']}\n"
            f"    模板: {a['template']}\n"
            f"    权限路径数: {a['allowed_paths_count']}\n"
            f"    技能: {skills}\n"
            f"    可调用子代理: {'是' if a['can_invoke_sub_agent'] else '否'}"
        )

    # 任务执行统计
    ts = input_data.get("task_stats", {})
    parts.append(f"\n## 3. 任务执行统计")
    parts.append(f"  总任务数: {ts.get('total', 0)}")
    parts.append(f"  已完成: {ts.get('completed', 0)}")
    parts.append(f"  进行中: {ts.get('pending', 0)}")
    parts.append(f"  失败: {ts.get('failed', 0)}")
    if ts.get("total", 0) > 0:
        completion_rate = round(ts["completed"] / ts["total"] * 100, 1)
        parts.append(f"  完成率: {completion_rate}%")

    # 任务结果摘要
    summaries = input_data.get("task_summaries", [])
    if summaries:
        parts.append(f"\n## 4. 最近任务摘要（最多 {MAX_TASK_SUMMARIES} 个）")
        for s in summaries:
            files = ", ".join(s.get("result_files", [])) or "无"
            parts.append(
                f"  - [{s['status']}] {s['description'][:80]}\n"
                f"    负责人: {s.get('assignee', '未知')}\n"
                f"    产出文件: {files}"
            )
    else:
        parts.append("\n## 4. 最近任务摘要\n（暂无任务记录）")

    # 消息交互摘要
    ms = input_data.get("message_stats", {})
    parts.append(f"\n## 5. 消息交互摘要")
    parts.append(f"  总消息数: {ms.get('total', 0)}")
    by_agent = ms.get("by_agent", {})
    if by_agent:
        parts.append(f"  按智能体统计:")
        for aid, count in sorted(by_agent.items(), key=lambda x: -x[1]):
            parts.append(f"    {aid}: {count} 条")
    parts.append(f"  最近消息时间: {ms.get('last_message_time', '无')}")

    # 异常事件记录
    ans = input_data.get("anomaly_stats", {})
    parts.append(f"\n## 6. 异常事件记录")
    parts.append(f"  幻觉警告次数: {ans.get('hallucination_warnings', 0)}")
    parts.append(f"  工具调用错误次数: {ans.get('tool_errors', 0)}")
    parts.append(f"  错误消息数: {ans.get('error_messages', 0)}")

    # 用户主观反馈
    feedback = input_data.get("user_feedback", "")
    parts.append(f"\n## 7. 用户主观反馈")
    parts.append(feedback if feedback else "（用户未提供反馈）")

    return "\n".join(parts)


# =========================================================================
# 专家诊断
# =========================================================================

DIAGNOSIS_SYSTEM_PROMPT_TEMPLATE = """你是「{expert_name}」，元团队设计专家。现在你需要对一份已应用的团队蓝图进行回访评审。

## 评审背景
这个团队是你（们）当初设计的，现在已经应用到一个项目中运行了一段时间。你需要根据运行数据，诊断这个团队设计得好不好，暴露了哪些问题。

## 你的设计理念
{expert_prompt}

## 评审输入（七维度运行数据）
{review_input}

## 你的任务
请从你的专业视角出发，诊断以下内容：

1. **设计问题诊断**：团队在运行中暴露了哪些设计缺陷？分类列出：
   - 成员配置问题（成员是否冗余或缺失、角色是否重叠）
   - 提示词问题（成员的 system_prompt 是否导致了执行偏差）
   - 协作机制问题（任务流转是否顺畅、有无协作瓶颈）
   - 权限设计问题（权限是否过大或过小）

2. **改进建议**：针对每个问题，建议怎么改（但不直接改蓝图）

3. **健康度评分**（1-10 分）：基于任务完成率、异常事件、协作频率等，给团队设计健康度打分

4. **是否建议重新设计**：是/否，附理由

请以 Markdown 格式输出你的诊断报告。
"""


def _build_diagnosis_prompt(expert: dict, input_text: str) -> str:
    """构建专家诊断的系统提示词"""
    return DIAGNOSIS_SYSTEM_PROMPT_TEMPLATE.format(
        expert_name=expert["name"],
        expert_prompt=expert["system_prompt"][:500] + "..." if len(expert["system_prompt"]) > 500 else expert["system_prompt"],
        review_input=input_text
    )


def _run_single_diagnosis(expert: dict, input_text: str, model_config: dict | None,
                          default_config_id: str) -> dict:
    """单个专家执行诊断（在工作线程中执行，带超时和重试）"""
    try:
        system_prompt = _build_diagnosis_prompt(expert, input_text)
        messages = [{"role": "user", "content": "请根据运行数据诊断这个团队的设计问题，输出诊断报告。"}]
        agent = {
            "id": expert["id"],
            "model_config": model_config,
            "can_use_tools": False,
        }
        content = _call_with_retry(
            system_prompt=system_prompt,
            messages=messages,
            agent=agent,
            default_config_id=default_config_id
        )
        return {
            "expert_id": expert["id"],
            "expert_name": expert["name"],
            "success": True,
            "content": content
        }
    except Exception as e:
        return {
            "expert_id": expert["id"],
            "expert_name": expert["name"],
            "success": False,
            "content": "",
            "error": str(e)
        }


# =========================================================================
# 主智能体汇总报告
# =========================================================================

SUMMARY_SYSTEM_PROMPT = """你是「元团队评审主智能体」，负责汇总各位专家的诊断意见，产出最终的评审报告。

## 评审输入数据
{review_input}

## 各专家诊断意见
{expert_diagnoses}

## 你的任务
综合所有专家的诊断意见，产出一份完整的评审报告。报告必须包含以下部分：

### 1. 团队设计健康度评分（1-10 分）
基于任务完成率、异常事件频率、协作活跃度等给出综合评分。

### 2. 设计问题诊断（分类列出）
汇总各专家发现的问题，去重合并后按以下分类列出：
- **成员配置问题**：成员是否冗余或缺失、角色是否重叠
- **提示词问题**：成员的 system_prompt 是否导致了执行偏差
- **协作机制问题**：任务流转是否顺畅、有无协作瓶颈
- **权限设计问题**：权限是否过大或过小

每个问题标注是哪位专家发现的，并附上严重程度（严重/警告/建议）。

### 3. 改进建议
针对每个问题，给出具体的改进建议（但不直接改蓝图）。

### 4. 是否建议重新设计
明确给出"是"或"否"，并说明理由。如果建议重新设计，说明应该重点关注哪些方面。

### 5. 专家意见分歧（如有）
如果专家之间有明显的意见分歧，列出来供用户参考。

请以 Markdown 格式输出完整报告。
"""


def _run_summary(input_text: str, diagnoses: list[dict], default_config_id: str) -> str:
    """主智能体汇总报告（流式输出）"""
    from main import call_llm_stream

    # 构建专家诊断汇总
    diag_parts = []
    for d in diagnoses:
        if d.get("success") and d.get("content"):
            diag_parts.append(f"### 专家「{d['expert_name']}」的诊断\n{d['content']}")
    expert_diagnoses_text = "\n\n---\n\n".join(diag_parts) if diag_parts else "（无专家诊断）"

    system_prompt = SUMMARY_SYSTEM_PROMPT.format(
        review_input=input_text,
        expert_diagnoses=expert_diagnoses_text
    )
    messages = [{"role": "user", "content": "请汇总各专家诊断，产出最终评审报告。"}]
    agent = {"id": "review_summary", "model_config": None, "can_use_tools": False}

    full_content = ""
    for token in call_llm_stream(
        system_prompt=system_prompt,
        messages=messages,
        agent=agent,
        default_config_id=default_config_id
    ):
        full_content += token
        yield token

    if full_content.startswith("❌"):
        raise RuntimeError(full_content)


# =========================================================================
# 评审主流程（generator，产出 SSE 事件）
# =========================================================================

def run_review(conversation_id: str, user_feedback: str = "",
               default_config_id: str = ""):
    """
    元团队评审主流程（generator，产出 SSE 事件）

    事件格式：
        ("review_start", {"review_id": "...", "message": "..."})
        ("input_collected", {"dimensions": 7, "task_total": int, ...})
        ("expert_start", {"expert_id": "...", "expert_name": "..."})
        ("expert_complete", {"expert_id": "...", "success": bool, ...})
        ("diagnosis_complete", {"success_count": int, "total": int})
        ("summary_start", {"message": "..."})
        ("token", {"content": "..."})
        ("review_complete", {"review_id": "...", "success": bool})
        ("error", {"message": "..."})
    """
    # 延迟导入
    from main import load_conversations

    # 找到项目
    conversations = load_conversations()
    conv = next((c for c in conversations if c["id"] == conversation_id), None)
    if not conv:
        yield ("error", {"message": f"项目 {conversation_id} 不存在"})
        return

    blueprint_source = conv.get("blueprint_source", "")
    if not blueprint_source:
        yield ("error", {"message": "该项目不是通过蓝图应用创建的，无法进行元团队评审"})
        return

    # 创建评审记录
    review_meta = create_review_record(conversation_id, conv.get("title", ""), blueprint_source)
    review_id = review_meta["review_id"]
    yield ("review_start", {"review_id": review_id, "message": "评审已启动，开始采集运行数据..."})

    # ===== 第一步：采集评审输入包 =====
    try:
        input_data = collect_review_input(conversation_id, user_feedback)
        save_review_input(review_id, input_data)
        update_review_status(review_id, "diagnosing")
        yield ("input_collected", {
            "dimensions": 7,
            "task_total": input_data.get("task_stats", {}).get("total", 0),
            "message_total": input_data.get("message_stats", {}).get("total", 0),
            "anomaly_count": sum(input_data.get("anomaly_stats", {}).values()),
            "member_count": len(input_data.get("current_agents", []))
        })
    except Exception as e:
        yield ("error", {"message": f"采集评审输入失败：{str(e)}"})
        return

    # 准备 LLM 输入文本
    input_text = _format_review_input_for_llm(input_data)

    # ===== 第二步：专家并行诊断 =====
    # 优先使用蓝图原设计成员作为评审专家（P1-M01 修复）
    # 如果蓝图有成员配置，用蓝图成员；否则回退到全局默认专家
    experts = []
    bp_data = input_data.get("original_blueprint", {}).get("blueprint_data", {})
    bp_members = bp_data.get("members", [])
    if bp_members:
        # 从蓝图成员中构造评审专家
        for m in bp_members:
            experts.append({
                "id": f"bp_member_{m.get('name', 'unknown')}",
                "name": m.get("name", ""),
                "system_prompt": m.get("system_prompt", ""),
                "model_config": m.get("model_config"),
            })
    
    # 如果蓝图没有成员或成员不足，用全局默认专家补充
    if len(experts) < 1:
        experts = mtc.get_default_experts(mtc.get_global_settings().get("default_expert_count", 3))
    
    if not experts:
        yield ("error", {"message": "没有可用的专家"})
        return

    model_configs = auto_select_models(len(experts), default_config_id)

    diagnoses = []
    with ThreadPoolExecutor(max_workers=min(len(experts), MAX_EXPERT_PARALLEL)) as executor:
        future_to_expert = {}
        for i, expert in enumerate(experts):
            mc = expert.get("model_config") or model_configs[i] if i < len(model_configs) else None
            future = executor.submit(_run_single_diagnosis, expert, input_text, mc, default_config_id)
            future_to_expert[future] = expert
            yield ("expert_start", {"expert_id": expert["id"], "expert_name": expert["name"]})

        for future in as_completed(future_to_expert):
            expert = future_to_expert[future]
            try:
                result = future.result()
                diagnoses.append(result)
                if result["success"]:
                    save_expert_diagnosis(review_id, result["expert_id"], result["content"])
                    yield ("expert_complete", {
                        "expert_id": result["expert_id"],
                        "expert_name": result["expert_name"],
                        "success": True,
                        "content_length": len(result["content"])
                    })
                else:
                    yield ("expert_complete", {
                        "expert_id": result["expert_id"],
                        "expert_name": result["expert_name"],
                        "success": False,
                        "error": result.get("error", "未知错误")
                    })
            except Exception as e:
                yield ("expert_complete", {
                    "expert_id": expert["id"],
                    "expert_name": expert["name"],
                    "success": False,
                    "error": str(e)
                })

    success_count = sum(1 for d in diagnoses if d["success"])
    yield ("diagnosis_complete", {"success_count": success_count, "total": len(experts)})

    # 如果所有专家都失败了，提前结束
    if success_count == 0:
        yield ("error", {"message": "所有专家诊断均失败，无法生成评审报告"})
        return

    # ===== 第三步：主智能体汇总报告（流式输出）=====
    update_review_status(review_id, "summarizing")
    yield ("summary_start", {"message": "主智能体正在汇总各专家诊断，生成评审报告..."})

    try:
        full_report = ""
        for token in _run_summary(input_text, diagnoses, default_config_id):
            full_report += token
            yield ("token", {"content": token})

        # 保存报告
        save_review_report(review_id, full_report)
        yield ("review_complete", {"review_id": review_id, "success": True})

    except Exception as e:
        # 即使汇总失败，也保存已有的专家诊断
        error_msg = f"汇总报告生成失败：{str(e)}"
        save_review_report(review_id, f"# 评审报告（汇总失败）\n\n{error_msg}\n\n## 专家诊断已保存\n")
        yield ("error", {"message": error_msg})
        return

    # ===== 追加专家经验（与评审联动）=====
    try:
        for d in diagnoses:
            if d["success"]:
                mtc.add_experience_record(
                    expert_id=d["expert_id"],
                    task_id=f"review_{review_id}",
                    task_title=f"评审：{conv.get('title', '')}",
                    score_received=None,
                    score_breakdown=None,
                    feedback_summary=f"参与了项目「{conv.get('title', '')}」的元团队评审，诊断了团队运行中暴露的设计问题。",
                    fusion_adopted=[],
                    fusion_not_adopted=[]
                )
        yield ("experience_recorded", {"message": "专家评审经验已记录"})
    except Exception as e:
        # 经验记录失败不影响主流程
        pass
