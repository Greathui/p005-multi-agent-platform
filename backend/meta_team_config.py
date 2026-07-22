# -*- coding: utf-8 -*-
"""
元团队专家常驻管理模块

负责管理全局常驻的元团队设计专家（非项目级智能体），包括：
- 专家基础配置（名称、提示词、模型配置）
- 经验记录自动积累（每次设计任务后追加）
- 提示词版本管理（用户主导升级，非自动修改）

数据存储：backend/meta_team_config.json

专家数据模型：
{
  "id": "expert_1",
  "name": "团队设计专家A",
  "system_prompt": "...（当前版本提示词）",
  "prompt_version": 2,
  "model_config": {"config_id": "cfg_xxx"},   # 绑定的模型配置 ID，null 表示用全局默认
  "created_at": "2026-07-20T...",
  "updated_at": "2026-07-20T...",
  "experience_log": [
    {
      "record_id": "exp_xxx",
      "task_id": "mt_task_xxx",
      "task_title": "科幻小说团队设计",
      "score_received": 7.5,                   # 本次方案收到的平均得分
      "score_breakdown": {                     # 其他专家给的评分明细（按评审项）
        "团队结构": 8, "提示词质量": 7, "协作机制": 8,
        "需求匹配": 7, "成本效率": 7.5
      },
      "feedback_summary": "...",               # 其他专家的文字评审意见摘要
      "fusion_adopted": ["..."],               # 主智能体融合时采纳的本专家方案要点
      "fusion_not_adopted": ["..."],           # 未被采纳的要点
      "created_at": "2026-07-20T..."
    }
  ]
}

全局配置字段：
{
  "experts": [...],
  "default_expert_count": 3,    # 默认专家数量（深度模式）
  "default_mode": "deep"        # 默认工作模式：deep / fast
}
"""

import json
import uuid
import time
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent
META_TEAM_CONFIG_FILE = BASE_DIR / "meta_team_config.json"

# 评审五项标准（与设计文档 3.5 节一致）
REVIEW_CRITERIA = ["团队结构", "提示词质量", "协作机制", "需求匹配", "成本效率"]


# =========================================================================
# JSON 读写工具
# =========================================================================

def _load_config() -> dict:
    """加载元团队专家配置，不存在则返回空骨架并初始化默认专家"""
    if not META_TEAM_CONFIG_FILE.exists():
        config = _default_config()
        _save_config(config)
        return config
    try:
        with open(META_TEAM_CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        # 兼容性补全
        if "experts" not in config:
            config["experts"] = []
        if "default_expert_count" not in config:
            config["default_expert_count"] = 3
        if "default_mode" not in config:
            config["default_mode"] = "deep"
        # 若专家列表为空，初始化默认专家
        if not config["experts"]:
            config = _default_config()
            _save_config(config)
        return config
    except Exception:
        config = _default_config()
        _save_config(config)
        return config


def _save_config(config: dict) -> None:
    """保存配置到文件"""
    META_TEAM_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(META_TEAM_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


# =========================================================================
# 默认专家初始化
# =========================================================================

# 三个默认专家的提示词风格略有差异，保证方案多样性：
# - 专家 A：偏重团队结构合理性，强调角色分工清晰、无冗余
# - 专家 B：偏重提示词质量，强调成员 system_prompt 的可执行性
# - 专家 C：偏重协作机制，强调任务流转和依赖关系设计

_EXPERT_A_PROMPT = """你是「团队设计专家A」，一位资深的多智能体团队架构师。你的核心能力是设计结构清晰、分工合理的团队。

## 你的设计理念
- 角色分工必须清晰，每个成员有明确的职责边界，避免重叠
- 成员数量追求最优，宁可少一个也不要多一个冗余角色
- 协作模式优先考虑星型（所有子智能体向主智能体汇报），除非任务确实需要直接协作
- 权限遵循最小化原则，只授予完成任务所需的最小权限

## 你的工作流程
1. 仔细阅读用户需求，识别任务类型、规模、关键约束
2. 设计团队结构：确定需要几个成员、每个成员的角色定位
3. 为每个成员编写 system_prompt（200-500字），包含角色定位、工作流程、产出规范、权限边界
4. 设计任务清单：列出团队需要执行的主要任务及其依赖关系
5. 产出完整的 team_blueprint.json 方案

## 你能参考的历史经验
系统会提供你过去参与的设计任务经验记录（其他专家对你的评分和意见、主智能体融合时的采纳情况）。请参考这些反馈改进本次设计，但不要被历史经验过度束缚。

## 产出格式要求
你必须产出一份完整的 team_blueprint.json 方案（合法 JSON），结构如下：
```json
{
  "blueprint_version": "1.0",
  "team_name": "团队名称",
  "description": "团队适用场景的一句话描述",
  "members": [
    {
      "name": "成员名称",
      "role": "角色定位",
      "system_prompt": "该成员的完整系统提示词",
      "collaboration": {
        "type": "star 或 direct 或 parallel",
        "report_to": "star模式填main",
        "with": "direct模式填协作对象名称"
      }
    }
  ],
  "tasks": [
    {
      "name": "任务名称",
      "assignee": "负责成员名称",
      "depends_on": ["依赖的前置任务名称"],
      "description": "任务描述"
    }
  ],
  "recommended_config": {
    "context_window": 131072,
    "enable_thinking": true,
    "max_tokens": 8000
  },
  "execution_tips": "执行建议"
}
```

## 评审其他专家方案时
你会看到其他专家的方案，需要按五项标准打分（1-10分）并给出文字意见：
- 团队结构合理性：成员配置是否合理、分工是否清晰、有无冗余或缺失
- 提示词质量：清晰度、可执行性、角色边界是否明确
- 协作机制设计：谁向谁汇报、并行还是串行、协作模式是否匹配任务
- 需求匹配度：团队设计是否覆盖了需求的全部要点、有无偏离
- 成本效率：有无过度设计、成员数量是否最优

打分要客观公正，先肯定亮点再指出问题。意见要具体，引用方案中的具体设计点。
"""

_EXPERT_B_PROMPT = """你是「团队设计专家B」，一位专注于提示词工程和智能体行为设计的专家。你的核心能力是编写高质量、可执行的成员系统提示词。

## 你的设计理念
- 成员的 system_prompt 是团队的"大脑"，质量决定执行效果
- 提示词必须可执行：包含具体的工作流程、工具使用策略、产出规范
- 角色边界必须明确：每个成员知道自己能做什么、不能做什么
- 提示词要适配 LLM 的理解方式：结构化、分点陈述、避免歧义
- 协作模式根据任务特点灵活选择，不拘泥于单一模式

## 你的工作流程
1. 分析用户需求，识别需要什么样的角色和能力
2. 设计团队结构，确定成员数量和分工
3. 为每个成员编写精心设计的 system_prompt：
   - 角色定位（你是谁、负责什么）
   - 工作流程（收到任务后怎么做、分几步）
   - 工具使用策略（什么场景用什么工具）
   - 产出规范（输出什么格式、放哪里）
   - 权限边界（能访问什么、不能访问什么）
   - 协作规则（如何与主智能体和其他成员配合）
4. 设计任务清单和依赖关系
5. 产出完整的 team_blueprint.json 方案

## 你能参考的历史经验
系统会提供你过去参与的设计任务经验记录。请参考这些反馈改进本次设计，特别注意其他专家对你"提示词质量"项的评分和意见。

## 产出格式要求
同专家 A，产出完整的 team_blueprint.json 方案（合法 JSON）。

## 评审其他专家方案时
按五项标准打分（1-10分），但你特别关注"提示词质量"这一项：
- 成员的 system_prompt 是否清晰、可执行
- 角色边界是否明确
- 工具使用策略是否合理
- 产出规范是否具体
对提示词质量方面的问题要给出具体的改进建议。
"""

_EXPERT_C_PROMPT = """你是「团队设计专家C」，一位专注于多智能体协作机制设计的专家。你的核心能力是设计高效的任务流转和协作模式。

## 你的设计理念
- 团队的核心不是成员本身，而是成员之间的协作关系
- 任务流转必须顺畅：前置任务的产出能自然地成为后置任务的输入
- 协作模式要匹配任务特点：创作类适合星型、开发类适合直接协作、分析类适合并行
- 依赖关系要清晰：哪些任务可以并行、哪些必须串行
- 避免协作瓶颈：不要让某个成员成为所有任务的必经节点（除非它是主智能体）

## 你的工作流程
1. 分析用户需求，识别任务的关键流程和依赖关系
2. 设计协作模式：确定成员之间的汇报关系和信息流转路径
3. 基于协作模式设计成员配置：每个成员在流程中的位置决定其角色和权限
4. 为每个成员编写 system_prompt，特别强调协作规则和信息交接规范
5. 设计任务清单，明确标注依赖关系和并行机会
6. 产出完整的 team_blueprint.json 方案

## 你能参考的历史经验
系统会提供你过去参与的设计任务经验记录。请参考这些反馈改进本次设计，特别注意其他专家对你"协作机制设计"项的评分和意见。

## 产出格式要求
同专家 A，产出完整的 team_blueprint.json 方案（合法 JSON）。

## 评审其他专家方案时
按五项标准打分（1-10分），但你特别关注"协作机制设计"这一项：
- 协作模式是否匹配任务特点
- 任务依赖关系是否合理
- 有无协作瓶颈或信息断点
- 并行机会是否被充分利用
对协作机制方面的问题要给出具体的改进建议。
"""


def _default_config() -> dict:
    """生成默认配置（3 个常驻专家）"""
    now = _now()
    return {
        "experts": [
            {
                "id": "expert_1",
                "name": "团队设计专家A",
                "system_prompt": _EXPERT_A_PROMPT,
                "prompt_version": 1,
                "model_config": None,  # None 表示用全局默认配置
                "created_at": now,
                "updated_at": now,
                "experience_log": []
            },
            {
                "id": "expert_2",
                "name": "团队设计专家B",
                "system_prompt": _EXPERT_B_PROMPT,
                "prompt_version": 1,
                "model_config": None,
                "created_at": now,
                "updated_at": now,
                "experience_log": []
            },
            {
                "id": "expert_3",
                "name": "团队设计专家C",
                "system_prompt": _EXPERT_C_PROMPT,
                "prompt_version": 1,
                "model_config": None,
                "created_at": now,
                "updated_at": now,
                "experience_log": []
            }
        ],
        "default_expert_count": 3,
        "default_mode": "deep"
    }


# =========================================================================
# 专家 CRUD
# =========================================================================

def list_experts() -> list[dict]:
    """列出所有常驻专家（含经验记录摘要，不含完整经验日志）"""
    config = _load_config()
    result = []
    for exp in config["experts"]:
        # 计算得分趋势
        exp_log = exp.get("experience_log", [])
        avg_score = None
        recent_scores = []
        if exp_log:
            scores = [r.get("score_received", 0) for r in exp_log if r.get("score_received") is not None]
            if scores:
                avg_score = round(sum(scores) / len(scores), 2)
                recent_scores = scores[-5:]  # 最近 5 次的得分

        result.append({
            "id": exp["id"],
            "name": exp["name"],
            "prompt_version": exp.get("prompt_version", 1),
            "model_config": exp.get("model_config"),
            "created_at": exp.get("created_at"),
            "updated_at": exp.get("updated_at"),
            "experience_count": len(exp_log),
            "avg_score": avg_score,
            "recent_scores": recent_scores
        })
    return result


def get_expert(expert_id: str) -> dict | None:
    """获取专家完整信息（含完整经验日志）"""
    config = _load_config()
    for exp in config["experts"]:
        if exp["id"] == expert_id:
            return exp
    return None


def get_experts_by_ids(expert_ids: list[str]) -> list[dict]:
    """根据 ID 列表批量获取专家完整信息"""
    config = _load_config()
    id_set = set(expert_ids)
    return [exp for exp in config["experts"] if exp["id"] in id_set]


def get_default_experts(count: int = 3) -> list[dict]:
    """获取前 N 个专家（用于深度模式默认选择）"""
    config = _load_config()
    return config["experts"][:count]


def create_expert(name: str, system_prompt: str, model_config: dict | None = None) -> dict:
    """新增专家"""
    config = _load_config()
    now = _now()
    # 生成 ID：取现有最大序号 +1
    existing_nums = []
    for exp in config["experts"]:
        if exp["id"].startswith("expert_"):
            try:
                existing_nums.append(int(exp["id"].split("_")[1]))
            except (IndexError, ValueError):
                pass
    next_num = max(existing_nums, default=0) + 1

    expert = {
        "id": f"expert_{next_num}",
        "name": name,
        "system_prompt": system_prompt,
        "prompt_version": 1,
        "model_config": model_config,
        "created_at": now,
        "updated_at": now,
        "experience_log": []
    }
    config["experts"].append(expert)
    _save_config(config)
    return expert


def update_expert(expert_id: str, updates: dict) -> dict | None:
    """更新专家配置（名称、模型配置等，不直接改 system_prompt——走版本升级流程）"""
    config = _load_config()
    for exp in config["experts"]:
        if exp["id"] == expert_id:
            # 允许更新的字段
            if "name" in updates:
                exp["name"] = updates["name"]
            if "model_config" in updates:
                exp["model_config"] = updates["model_config"]
            exp["updated_at"] = _now()
            _save_config(config)
            return exp
    return None


def delete_expert(expert_id: str) -> bool:
    """删除专家（保留至少 1 个）"""
    config = _load_config()
    if len(config["experts"]) <= 1:
        return False  # 至少保留 1 个专家
    original_len = len(config["experts"])
    config["experts"] = [e for e in config["experts"] if e["id"] != expert_id]
    if len(config["experts"]) < original_len:
        _save_config(config)
        return True
    return False


# =========================================================================
# 经验记录管理（第一层成长机制：自动积累）
# =========================================================================

def add_experience_record(
    expert_id: str,
    task_id: str,
    task_title: str,
    score_received: float | None,
    score_breakdown: dict | None,
    feedback_summary: str,
    fusion_adopted: list[str],
    fusion_not_adopted: list[str]
) -> dict | None:
    """为专家追加一条经验记录（设计任务完成后自动调用）"""
    config = _load_config()
    for exp in config["experts"]:
        if exp["id"] == expert_id:
            record = {
                "record_id": f"exp_{uuid.uuid4().hex[:12]}",
                "task_id": task_id,
                "task_title": task_title,
                "score_received": score_received,
                "score_breakdown": score_breakdown or {},
                "feedback_summary": feedback_summary,
                "fusion_adopted": fusion_adopted or [],
                "fusion_not_adopted": fusion_not_adopted or [],
                "created_at": _now()
            }
            if "experience_log" not in exp:
                exp["experience_log"] = []
            exp["experience_log"].append(record)
            exp["updated_at"] = _now()
            _save_config(config)
            return record
    return None


def get_experience_log(expert_id: str) -> list[dict]:
    """获取专家的完整经验记录"""
    expert = get_expert(expert_id)
    if not expert:
        return []
    return expert.get("experience_log", [])


def get_expert_context_for_task(expert_id: str) -> str:
    """构建专家参与新设计任务时的上下文片段（历史经验摘要）"""
    expert = get_expert(expert_id)
    if not expert:
        return ""
    log = expert.get("experience_log", [])
    if not log:
        return "\n\n## 你的历史经验\n你目前还没有参与过设计任务，这是你的第一次设计。请充分发挥你的设计理念。"

    lines = [f"\n\n## 你的历史经验（共 {len(log)} 次设计任务）"]
    # 只展示最近 5 次经验，避免上下文过长
    recent = log[-5:]
    for i, record in enumerate(recent, 1):
        lines.append(f"\n### 第 {len(log) - len(recent) + i} 次：{record.get('task_title', '未命名任务')}")
        if record.get("score_received") is not None:
            lines.append(f"- 你收到的平均得分：{record['score_received']}/10")
        if record.get("score_breakdown"):
            breakdown = "、".join([f"{k} {v}" for k, v in record["score_breakdown"].items()])
            lines.append(f"- 评分明细：{breakdown}")
        if record.get("feedback_summary"):
            lines.append(f"- 其他专家评审意见：{record['feedback_summary']}")
        if record.get("fusion_adopted"):
            lines.append(f"- 被主智能体采纳的要点：{', '.join(record['fusion_adopted'])}")
        if record.get("fusion_not_adopted"):
            lines.append(f"- 未被采纳的要点：{', '.join(record['fusion_not_adopted'])}")

    lines.append("\n请参考以上经验改进本次设计。")
    return "\n".join(lines)


# =========================================================================
# 提示词版本管理（第二层成长机制：用户主导升级）
# =========================================================================

def get_current_prompt(expert_id: str) -> tuple[str, int] | None:
    """获取专家当前提示词和版本号"""
    expert = get_expert(expert_id)
    if not expert:
        return None
    return expert.get("system_prompt", ""), expert.get("prompt_version", 1)


def upgrade_prompt_version(expert_id: str, new_prompt: str, optimization_reason: str = "") -> dict | None:
    """用户确认后升级专家提示词版本（prompt_version + 1）

    升级时自动将旧版本保存到 prompt_history 数组，支持后续回退。
    """
    config = _load_config()
    for exp in config["exps"] if "exps" in config else config["experts"]:
        if exp["id"] == expert_id:
            old_version = exp.get("prompt_version", 1)
            old_prompt = exp.get("system_prompt", "")
            # 保存旧版本到 prompt_history
            if "prompt_history" not in exp:
                exp["prompt_history"] = []
            exp["prompt_history"].append({
                "version": old_version,
                "system_prompt": old_prompt,
                "upgraded_at": _now(),
                "upgrade_reason": optimization_reason or "用户手动升级"
            })
            # 更新为新版本
            exp["system_prompt"] = new_prompt
            exp["prompt_version"] = old_version + 1
            exp["updated_at"] = _now()
            # 在经验记录里追加一条升级记录（标记为 prompt_upgrade 类型）
            if "experience_log" not in exp:
                exp["experience_log"] = []
            upgrade_record = {
                "record_id": f"exp_{uuid.uuid4().hex[:12]}",
                "task_id": None,
                "task_title": f"提示词版本升级 v{old_version} → v{old_version + 1}",
                "score_received": None,
                "score_breakdown": {},
                "feedback_summary": f"用户主导的提示词升级。原因：{optimization_reason or '用户手动升级'}",
                "fusion_adopted": [],
                "fusion_not_adopted": [],
                "created_at": _now()
            }
            exp["experience_log"].append(upgrade_record)
            _save_config(config)
            return exp
    return None


def get_prompt_history(expert_id: str) -> list[dict]:
    """获取专家的提示词版本历史（按版本倒序，最新版本在前）"""
    expert = get_expert(expert_id)
    if not expert:
        return []
    history = expert.get("prompt_history", [])
    # 当前版本也加入列表头部
    current = {
        "version": expert.get("prompt_version", 1),
        "system_prompt": expert.get("system_prompt", ""),
        "upgraded_at": expert.get("updated_at", ""),
        "upgrade_reason": "当前版本",
        "is_current": True
    }
    # 历史版本按版本号倒序
    sorted_history = sorted(history, key=lambda x: x.get("version", 0), reverse=True)
    return [current] + sorted_history


def rollback_prompt_version(expert_id: str, target_version: int) -> dict | None:
    """回退到指定版本的提示词

    将当前提示词保存到 prompt_history，然后恢复目标版本。
    prompt_version 设为目标版本（不是 +1），表示这是回退操作。
    """
    config = _load_config()
    experts = config.get("exps", config.get("experts", []))
    for exp in experts:
        if exp["id"] == expert_id:
            current_version = exp.get("prompt_version", 1)
            current_prompt = exp.get("system_prompt", "")
            # 找到目标版本
            history = exp.get("prompt_history", [])
            target = next((h for h in history if h.get("version") == target_version), None)
            if not target:
                return None
            # 保存当前版本到历史
            if "prompt_history" not in exp:
                exp["prompt_history"] = []
            exp["prompt_history"].append({
                "version": current_version,
                "system_prompt": current_prompt,
                "upgraded_at": _now(),
                "upgrade_reason": f"回退到 v{target_version} 前的自动备份"
            })
            # 恢复目标版本
            exp["system_prompt"] = target["system_prompt"]
            exp["prompt_version"] = target_version
            exp["updated_at"] = _now()
            # 追加经验记录
            if "experience_log" not in exp:
                exp["experience_log"] = []
            rollback_record = {
                "record_id": f"exp_{uuid.uuid4().hex[:12]}",
                "task_id": None,
                "task_title": f"提示词版本回退 v{current_version} → v{target_version}",
                "score_received": None,
                "score_breakdown": {},
                "feedback_summary": f"用户回退到 v{target_version} 版本的提示词",
                "fusion_adopted": [],
                "fusion_not_adopted": [],
                "created_at": _now()
            }
            exp["experience_log"].append(rollback_record)
            _save_config(config)
            return exp
    return None


# =========================================================================
# 全局配置
# =========================================================================

def get_global_settings() -> dict:
    """获取全局配置（默认专家数、默认模式）"""
    config = _load_config()
    return {
        "default_expert_count": config.get("default_expert_count", 3),
        "default_mode": config.get("default_mode", "deep")
    }


def update_global_settings(default_expert_count: int | None = None, default_mode: str | None = None) -> dict:
    """更新全局配置"""
    config = _load_config()
    if default_expert_count is not None:
        config["default_expert_count"] = max(1, min(10, default_expert_count))
    if default_mode is not None and default_mode in ("deep", "fast"):
        config["default_mode"] = default_mode
    _save_config(config)
    return {
        "default_expert_count": config.get("default_expert_count", 3),
        "default_mode": config.get("default_mode", "deep")
    }


# =========================================================================
# 初始化入口
# =========================================================================

def ensure_initialized():
    """确保元团队专家配置已初始化（后端启动时调用）"""
    _load_config()
