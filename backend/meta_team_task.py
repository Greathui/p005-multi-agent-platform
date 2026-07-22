# -*- coding: utf-8 -*-
"""
元团队设计任务管理模块

负责元团队设计任务的存储和 CRUD 操作。设计任务独立于普通项目，
存放在 backend/meta_team_tasks/{task_id}/ 目录下。

数据存储结构（与设计文档 2.2 / 3.4 节一致）：
  backend/meta_team_tasks/
    {task_id}/
      meta.json                # 任务元数据（状态、模式、专家配置、消息历史）
      requirement.md           # 需求记录（用户输入 + 澄清对话）
      proposals/               # 各专家完整方案
        expert_1.md
        expert_2.md
        expert_3.md
      reviews/                 # 评审记录
        expert_1_review.md
        expert_2_review.md
        expert_3_review.md
      team_blueprint_v1.json   # 最终蓝图（每次迭代一个版本）
      team_blueprint_v2.json
      fusion_decision.md       # 主智能体的融合决策说明

任务状态流转：
  drafting  → 专家撰写方案中
  reviewing → 专家互相评审中
  fusing    → 主智能体融合中
  completed → 已产出最终蓝图（可被确认入库）
  archived  → 已归档（蓝图已写入蓝图库）

Phase 1 过渡期：消息历史存在 meta.json 中，简化实现。
Phase 2 将实现多专家并行调度和评审融合逻辑。
"""

import json
import uuid
import time
import shutil
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent
META_TEAM_TASKS_DIR = BASE_DIR / "meta_team_tasks"

# 任务状态
STATUS_DRAFTING = "drafting"
STATUS_REVIEWING = "reviewing"
STATUS_FUSING = "fusing"
STATUS_COMPLETED = "completed"
STATUS_ARCHIVED = "archived"

ALL_STATUSES = [STATUS_DRAFTING, STATUS_REVIEWING, STATUS_FUSING, STATUS_COMPLETED, STATUS_ARCHIVED]

# 消息角色
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_EXPERT = "expert"
ROLE_SYSTEM = "system"


# =========================================================================
# 工具函数
# =========================================================================

def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def _task_dir(task_id: str) -> Path:
    return META_TEAM_TASKS_DIR / task_id


def _meta_path(task_id: str) -> Path:
    return _task_dir(task_id) / "meta.json"


def _load_meta(task_id: str) -> dict | None:
    path = _meta_path(task_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_meta(task_id: str, meta: dict) -> None:
    path = _meta_path(task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _write_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _read_text_file(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def _write_json_file(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _read_json_file(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# =========================================================================
# 任务 CRUD
# =========================================================================

def create_task(
    title: str,
    requirement: str,
    mode: str = "deep",
    expert_ids: list[str] | None = None
) -> dict:
    """
    新建设计任务

    Args:
        title: 任务标题
        requirement: 用户的需求描述
        mode: 工作模式 deep（3专家并行）/ fast（1专家快速）
        expert_ids: 参与的专家 ID 列表，None 则用默认前 3 个

    Returns:
        任务元数据
    """
    task_id = f"mt_task_{uuid.uuid4().hex[:12]}"
    now = _now()

    # 默认专家选择
    if expert_ids is None:
        if mode == "fast":
            expert_ids = ["expert_1"]
        else:
            expert_ids = ["expert_1", "expert_2", "expert_3"]

    meta = {
        "id": task_id,
        "title": title,
        "status": STATUS_DRAFTING,
        "mode": mode,
        "requirement": requirement,
        "expert_ids": expert_ids,
        "created_at": now,
        "updated_at": now,
        "current_version": 0,
        "blueprint_id": None,
        "messages": [
            {
                "role": ROLE_USER,
                "content": requirement,
                "created_at": now
            }
        ]
    }

    # 创建目录结构
    task_dir = _task_dir(task_id)
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "proposals").mkdir(exist_ok=True)
    (task_dir / "reviews").mkdir(exist_ok=True)

    # 写入需求记录文件
    _write_text_file(task_dir / "requirement.md", f"# {title}\n\n## 用户需求\n\n{requirement}\n")

    # 写入元数据
    _save_meta(task_id, meta)

    return meta


def list_tasks(status_filter: str | None = None) -> list[dict]:
    """
    列出所有设计任务

    Args:
        status_filter: 状态筛选，None 则返回全部

    Returns:
        任务元数据列表（不含消息历史，减小体积）
    """
    if not META_TEAM_TASKS_DIR.exists():
        return []

    result = []
    for task_dir in sorted(META_TEAM_TASKS_DIR.iterdir()):
        if not task_dir.is_dir():
            continue
        meta = _load_meta(task_dir.name)
        if not meta:
            continue
        if status_filter and meta.get("status") != status_filter:
            continue
        # 列表不返回完整消息历史
        meta_summary = {k: v for k, v in meta.items() if k != "messages"}
        meta_summary["message_count"] = len(meta.get("messages", []))
        result.append(meta_summary)

    # 按创建时间倒序（最新的在前）
    result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return result


def get_task(task_id: str) -> dict | None:
    """获取任务完整信息（含消息历史和产出文件列表）"""
    meta = _load_meta(task_id)
    if not meta:
        return None

    task_dir = _task_dir(task_id)

    # 收集产出文件信息
    proposals = {}
    proposals_dir = task_dir / "proposals"
    if proposals_dir.exists():
        for f in proposals_dir.iterdir():
            if f.is_file() and f.suffix == ".md":
                expert_id = f.stem  # expert_1.md -> expert_1
                proposals[expert_id] = str(f.relative_to(task_dir))

    reviews = {}
    reviews_dir = task_dir / "reviews"
    if reviews_dir.exists():
        for f in reviews_dir.iterdir():
            if f.is_file() and f.suffix == ".md":
                expert_id = f.stem.replace("_review", "")
                reviews[expert_id] = str(f.relative_to(task_dir))

    # 蓝图版本文件
    blueprint_versions = []
    if task_dir.exists():
        for f in task_dir.iterdir():
            if f.is_file() and f.name.startswith("team_blueprint_v") and f.suffix == ".json":
                blueprint_versions.append(f.name)

    meta["proposals"] = proposals
    meta["reviews"] = reviews
    meta["blueprint_versions"] = sorted(blueprint_versions)
    meta["has_fusion_decision"] = (task_dir / "fusion_decision.md").exists()

    return meta


def delete_task(task_id: str) -> bool:
    """删除设计任务（连同目录）"""
    task_dir = _task_dir(task_id)
    if not task_dir.exists():
        return False
    try:
        shutil.rmtree(task_dir)
        return True
    except Exception:
        return False


def update_task_status(task_id: str, status: str) -> dict | None:
    """更新任务状态"""
    if status not in ALL_STATUSES:
        return None
    meta = _load_meta(task_id)
    if not meta:
        return None
    meta["status"] = status
    meta["updated_at"] = _now()
    _save_meta(task_id, meta)
    return meta


# =========================================================================
# 消息管理
# =========================================================================

def add_message(
    task_id: str,
    role: str,
    content: str,
    expert_id: str | None = None
) -> dict | None:
    """向任务追加一条消息"""
    meta = _load_meta(task_id)
    if not meta:
        return None
    msg = {
        "role": role,
        "content": content,
        "created_at": _now()
    }
    if expert_id:
        msg["expert_id"] = expert_id
    if "messages" not in meta:
        meta["messages"] = []
    meta["messages"].append(msg)
    meta["updated_at"] = _now()
    _save_meta(task_id, meta)
    return msg


def get_messages(task_id: str) -> list[dict]:
    """获取任务的消息历史"""
    meta = _load_meta(task_id)
    if not meta:
        return []
    return meta.get("messages", [])


# =========================================================================
# 产出文件管理
# =========================================================================

def save_proposal(task_id: str, expert_id: str, content: str) -> bool:
    """保存专家的方案文件"""
    task_dir = _task_dir(task_id)
    path = task_dir / "proposals" / f"{expert_id}.md"
    _write_text_file(path, content)
    return True


def get_proposal(task_id: str, expert_id: str) -> str | None:
    """读取专家的方案文件"""
    task_dir = _task_dir(task_id)
    return _read_text_file(task_dir / "proposals" / f"{expert_id}.md")


def save_review(task_id: str, expert_id: str, content: str) -> bool:
    """保存专家的评审文件"""
    task_dir = _task_dir(task_id)
    path = task_dir / "reviews" / f"{expert_id}_review.md"
    _write_text_file(path, content)
    return True


def get_review(task_id: str, expert_id: str) -> str | None:
    """读取专家的评审文件"""
    task_dir = _task_dir(task_id)
    return _read_text_file(task_dir / "reviews" / f"{expert_id}_review.md")


def save_blueprint_version(task_id: str, blueprint_data: dict) -> int:
    """
    保存一个新版本的蓝图

    Returns:
        版本号
    """
    meta = _load_meta(task_id)
    if not meta:
        return 0
    next_version = meta.get("current_version", 0) + 1
    task_dir = _task_dir(task_id)
    path = task_dir / f"team_blueprint_v{next_version}.json"
    _write_json_file(path, blueprint_data)
    meta["current_version"] = next_version
    meta["updated_at"] = _now()
    _save_meta(task_id, meta)
    return next_version


def get_blueprint_version(task_id: str, version: int | None = None) -> dict | None:
    """
    获取蓝图数据

    Args:
        version: 版本号，None 则取最新版
    """
    meta = _load_meta(task_id)
    if not meta:
        return None
    if version is None:
        version = meta.get("current_version", 0)
    if version < 1:
        return None
    task_dir = _task_dir(task_id)
    return _read_json_file(task_dir / f"team_blueprint_v{version}.json")


def save_fusion_decision(task_id: str, content: str) -> bool:
    """保存主智能体的融合决策说明"""
    task_dir = _task_dir(task_id)
    _write_text_file(task_dir / "fusion_decision.md", content)
    return True


def get_fusion_decision(task_id: str) -> str | None:
    """读取融合决策说明"""
    task_dir = _task_dir(task_id)
    return _read_text_file(task_dir / "fusion_decision.md")


def set_blueprint_id(task_id: str, blueprint_id: str) -> dict | None:
    """记录最终入库的蓝图 ID（finalize 时调用）"""
    meta = _load_meta(task_id)
    if not meta:
        return None
    meta["blueprint_id"] = blueprint_id
    meta["status"] = STATUS_ARCHIVED
    meta["updated_at"] = _now()
    _save_meta(task_id, meta)
    return meta


def get_latest_blueprint(task_id: str) -> dict | None:
    """获取最新版蓝图（用于 finalize 入库）"""
    return get_blueprint_version(task_id, None)


# =========================================================================
# 统计信息
# =========================================================================

def get_task_stats() -> dict:
    """获取设计任务统计信息（用于面板展示）"""
    tasks = list_tasks()
    stats = {
        "total": len(tasks),
        "by_status": {},
        "by_mode": {"deep": 0, "fast": 0}
    }
    for t in tasks:
        status = t.get("status", "unknown")
        stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
        mode = t.get("mode", "deep")
        stats["by_mode"][mode] = stats["by_mode"].get(mode, 0) + 1
    return stats


# =========================================================================
# 初始化入口
# =========================================================================

def ensure_initialized():
    """确保元团队任务目录已创建（后端启动时调用）"""
    META_TEAM_TASKS_DIR.mkdir(parents=True, exist_ok=True)
