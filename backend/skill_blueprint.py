# -*- coding: utf-8 -*-
"""
技能（Skill）与团队蓝图（Blueprint）管理模块

数据存储结构：
  backend/
    skills.json            # 本地技能库
    blueprints.json        # 本地蓝图库
    blueprints/            # 蓝图文件目录（每个蓝图一个 JSON 文件，便于导入导出）
      <blueprint_id>.json

技能数据模型：
{
  "id": "skill_xxx",
  "name": "文件操作",
  "description": "提供文件读写、目录管理能力",
  "icon": "📁",
  "icon_bg": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
  "category": "基础",          // 分类：基础/创作/开发/分析/效率
  "version": "1.0.0",
  "source": "builtin",        // builtin/custom/market/imported
  "tools": ["read_file", "write_file", ...],   // 包含的工具列表
  "system_prompt_fragment": "", // 注入到智能体 system_prompt 的片段
  "enabled_by_default": true,  // 是否默认启用
  "created_at": "2026-07-19T...",
  "updated_at": "2026-07-19T...",
  "use_count": 0               // 使用次数统计
}

蓝图数据模型：
{
  "id": "bp_xxx",
  "name": "科幻长篇小说创作团队",
  "description": "专攻50章+长篇科幻小说",
  "icon": "🚀",
  "icon_bg": "linear-gradient(...)",
  "version": "1.0.0",
  "source": "manual",         // manual/meta/market/imported
  "category": "novel",
  "blueprint_data": {         // 实际的 team_blueprint.json 内容
    "blueprint_version": "1.0",
    "team_name": "...",
    "members": [...],
    "tasks": [...],
    ...
  },
  "apply_count": 0,
  "created_at": "...",
  "updated_at": "..."
}
"""

import json
import os
import tempfile
import threading
import uuid
import time
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent
SKILLS_FILE = BASE_DIR / "skills.json"
BLUEPRINTS_FILE = BASE_DIR / "blueprints.json"
BLUEPRINTS_DIR = BASE_DIR / "blueprints"

# 线程安全锁，保护 JSON 文件读写
_json_lock = threading.RLock()


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with _json_lock:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except json.JSONDecodeError:
        return default
    except (OSError, IOError):
        return default


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _json_lock:
        tmp_fd, tmp_path = tempfile.mkstemp(
            suffix=".json", prefix="tmp_", dir=str(path.parent)
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, str(path))
        except Exception:
            # 清理临时文件
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            raise


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _gen_id(prefix: str = "skill") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# ============================================================
# 内置技能定义
# ============================================================

BUILTIN_SKILLS = [
    {
        "id": "builtin-file-ops",
        "name": "文件操作",
        "description": "提供文件读写、目录管理、文件搜索等基础能力",
        "icon": "📁",
        "icon_bg": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
        "category": "基础",
        "version": "1.0.0",
        "source": "builtin",
        "tools": ["read_file", "write_file", "edit_file", "list_directory", "grep", "glob"],
        "system_prompt_fragment": "",
        "enabled_by_default": True,
    },
    {
        "id": "builtin-task-mgmt",
        "name": "任务管理",
        "description": "创建任务、分配任务、提交结果、查询任务状态",
        "icon": "📋",
        "icon_bg": "linear-gradient(135deg, #10b981 0%, #059669 100%)",
        "category": "基础",
        "version": "1.0.0",
        "source": "builtin",
        "tools": ["create_task", "submit_task_result", "list_tasks"],
        "system_prompt_fragment": "",
        "enabled_by_default": True,
    },
    {
        "id": "builtin-team-mgmt",
        "name": "团队管理",
        "description": "主智能体管理团队成员：创建、更新、移除、授权",
        "icon": "👥",
        "icon_bg": "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
        "category": "基础",
        "version": "1.0.0",
        "source": "builtin",
        "tools": ["create_team_member", "update_team_member", "remove_team_member", "list_team_members", "grant_path_access"],
        "system_prompt_fragment": "",
        "enabled_by_default": True,
    },
    {
        "id": "builtin-archive",
        "name": "文件归档",
        "description": "移动和复制文件，用于产出归档到 deliverables/",
        "icon": "📦",
        "icon_bg": "linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)",
        "category": "基础",
        "version": "1.0.0",
        "source": "builtin",
        "tools": ["move_file", "copy_file"],
        "system_prompt_fragment": "",
        "enabled_by_default": True,
    },
    {
        "id": "builtin-project-init",
        "name": "项目初始化",
        "description": "初始化项目标准目录结构",
        "icon": "🏗️",
        "icon_bg": "linear-gradient(135deg, #06b6d4 0%, #0891b2 100%)",
        "category": "基础",
        "version": "1.0.0",
        "source": "builtin",
        "tools": ["init_project_structure", "create_directory"],
        "system_prompt_fragment": "",
        "enabled_by_default": True,
    },
    {
        "id": "builtin-meta-team",
        "name": "元团队规划",
        "description": "元团队专用：产出团队蓝图文件（仅元团队主智能体使用）",
        "icon": "🎯",
        "icon_bg": "linear-gradient(135deg, #ec4899 0%, #db2777 100%)",
        "category": "元团队",
        "version": "1.0.0",
        "source": "builtin",
        "tools": [],
        "system_prompt_fragment": "",
        "enabled_by_default": True,
    },
]


def _ensure_builtin_skills() -> None:
    """确保内置技能存在于 skills.json 中。"""
    data = _load_json(SKILLS_FILE, {"skills": []})
    skills = data.get("skills", [])
    existing_ids = {s["id"] for s in skills}

    changed = False
    for builtin in BUILTIN_SKILLS:
        if builtin["id"] not in existing_ids:
            skill = dict(builtin)
            skill["created_at"] = _now()
            skill["updated_at"] = _now()
            skill["use_count"] = 0
            skills.append(skill)
            changed = True

    if changed:
        data["skills"] = skills
        _save_json(SKILLS_FILE, data)


# ============================================================
# 技能 CRUD
# ============================================================

def list_skills() -> list[dict]:
    """列出所有技能（内置 + 自定义）。"""
    _ensure_builtin_skills()
    data = _load_json(SKILLS_FILE, {"skills": []})
    return data.get("skills", [])


def get_skill(skill_id: str) -> dict | None:
    """根据 ID 获取技能。"""
    for s in list_skills():
        if s["id"] == skill_id:
            return s
    return None


def create_skill(payload: dict) -> dict:
    """创建自定义技能。"""
    data = _load_json(SKILLS_FILE, {"skills": []})
    skills = data.get("skills", [])

    skill = {
        "id": _gen_id("skill"),
        "name": payload.get("name", "未命名技能"),
        "description": payload.get("description", ""),
        "icon": payload.get("icon", "🔧"),
        "icon_bg": payload.get("icon_bg", "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)"),
        "category": payload.get("category", "自定义"),
        "version": payload.get("version", "1.0.0"),
        "source": "custom",
        "tools": payload.get("tools", []),
        "system_prompt_fragment": payload.get("system_prompt_fragment", ""),
        "enabled_by_default": payload.get("enabled_by_default", False),
        "created_at": _now(),
        "updated_at": _now(),
        "use_count": 0,
    }
    skills.append(skill)
    data["skills"] = skills
    _save_json(SKILLS_FILE, data)
    return skill


def update_skill(skill_id: str, payload: dict) -> dict | None:
    """更新技能（不允许修改内置技能的 id 和 source）。"""
    data = _load_json(SKILLS_FILE, {"skills": []})
    skills = data.get("skills", [])

    for s in skills:
        if s["id"] == skill_id:
            for k in ["name", "description", "icon", "icon_bg", "category",
                     "version", "tools", "system_prompt_fragment", "enabled_by_default"]:
                if k in payload:
                    s[k] = payload[k]
            s["updated_at"] = _now()
            data["skills"] = skills
            _save_json(SKILLS_FILE, data)
            return s
    return None


def delete_skill(skill_id: str) -> bool:
    """删除技能（内置技能不允许删除）。"""
    data = _load_json(SKILLS_FILE, {"skills": []})
    skills = data.get("skills", [])

    new_skills = [s for s in skills if s["id"] != skill_id]
    if len(new_skills) == len(skills):
        return False

    # 检查是否是内置技能
    for s in skills:
        if s["id"] == skill_id and s.get("source") == "builtin":
            return False

    data["skills"] = new_skills
    _save_json(SKILLS_FILE, data)
    return True


def increment_skill_use_count(skill_ids: list[str]) -> None:
    """增加技能使用次数（用于统计）。"""
    if not skill_ids:
        return
    data = _load_json(SKILLS_FILE, {"skills": []})
    skills = data.get("skills", [])
    for s in skills:
        if s["id"] in skill_ids:
            s["use_count"] = s.get("use_count", 0) + 1
    data["skills"] = skills
    _save_json(SKILLS_FILE, data)


# ============================================================
# 蓝图 CRUD
# ============================================================

def _ensure_blueprints_dir() -> None:
    BLUEPRINTS_DIR.mkdir(parents=True, exist_ok=True)


def list_blueprints() -> list[dict]:
    """列出所有本地蓝图。"""
    data = _load_json(BLUEPRINTS_FILE, {"blueprints": []})
    return data.get("blueprints", [])


def get_blueprint(bp_id: str) -> dict | None:
    """根据 ID 获取蓝图。"""
    for b in list_blueprints():
        if b["id"] == bp_id:
            return b
    return None


def create_blueprint(payload: dict) -> dict:
    """创建本地蓝图。

    payload 字段：
    - name, description, icon, icon_bg, category, version
    - blueprint_data: 实际的 team_blueprint.json 内容
    - source: manual/meta/market/imported
    """
    _ensure_blueprints_dir()
    data = _load_json(BLUEPRINTS_FILE, {"blueprints": []})
    blueprints = data.get("blueprints", [])

    bp_id = _gen_id("bp")
    blueprint_data = payload.get("blueprint_data", {})

    bp = {
        "id": bp_id,
        "name": payload.get("name", "未命名蓝图"),
        "description": payload.get("description", ""),
        "icon": payload.get("icon", "📋"),
        "icon_bg": payload.get("icon_bg", "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)"),
        "category": payload.get("category", "general"),
        "version": payload.get("version", "1.0.0"),
        "source": payload.get("source", "manual"),
        "blueprint_data": blueprint_data,
        "apply_count": 0,
        "created_at": _now(),
        "updated_at": _now(),
    }

    # 同时保存为独立文件，便于导入导出
    bp_file = BLUEPRINTS_DIR / f"{bp_id}.json"
    _save_json(bp_file, blueprint_data)

    blueprints.append(bp)
    data["blueprints"] = blueprints
    _save_json(BLUEPRINTS_FILE, data)
    return bp


def update_blueprint(bp_id: str, payload: dict) -> dict | None:
    """更新蓝图元数据和蓝图数据。"""
    _ensure_blueprints_dir()
    data = _load_json(BLUEPRINTS_FILE, {"blueprints": []})
    blueprints = data.get("blueprints", [])

    for b in blueprints:
        if b["id"] == bp_id:
            for k in ["name", "description", "icon", "icon_bg", "category", "version"]:
                if k in payload:
                    b[k] = payload[k]
            if "blueprint_data" in payload:
                b["blueprint_data"] = payload["blueprint_data"]
                bp_file = BLUEPRINTS_DIR / f"{bp_id}.json"
                _save_json(bp_file, payload["blueprint_data"])
            b["updated_at"] = _now()
            data["blueprints"] = blueprints
            _save_json(BLUEPRINTS_FILE, data)
            return b
    return None


def delete_blueprint(bp_id: str) -> bool:
    """删除蓝图。"""
    data = _load_json(BLUEPRINTS_FILE, {"blueprints": []})
    blueprints = data.get("blueprints", [])

    new_bps = [b for b in blueprints if b["id"] != bp_id]
    if len(new_bps) == len(blueprints):
        return False

    data["blueprints"] = new_bps
    _save_json(BLUEPRINTS_FILE, data)

    # 删除独立文件
    bp_file = BLUEPRINTS_DIR / f"{bp_id}.json"
    if bp_file.exists():
        try:
            bp_file.unlink()
        except Exception:
            pass

    return True


def increment_blueprint_apply_count(bp_id: str) -> None:
    """增加蓝图应用次数。"""
    data = _load_json(BLUEPRINTS_FILE, {"blueprints": []})
    blueprints = data.get("blueprints", [])
    for b in blueprints:
        if b["id"] == bp_id:
            b["apply_count"] = b.get("apply_count", 0) + 1
            b["updated_at"] = _now()
            break
    data["blueprints"] = blueprints
    _save_json(BLUEPRINTS_FILE, data)


def import_blueprint_from_data(blueprint_data: dict, name: str = "", description: str = "") -> dict:
    """从蓝图 JSON 数据导入蓝图（例如从 deliverables/team_blueprint.json 导入）。"""
    if not isinstance(blueprint_data, dict):
        raise ValueError("蓝图数据必须是字典")

    # 导入前校验蓝图数据格式
    is_valid, error = validate_blueprint_data(blueprint_data)
    if not is_valid:
        raise ValueError(f"蓝图数据校验失败：{error}")

    # 从蓝图数据中提取信息
    team_name = blueprint_data.get("team_name", "未命名团队")
    bp_desc = blueprint_data.get("description", "")
    members = blueprint_data.get("members", [])

    payload = {
        "name": name or team_name,
        "description": description or bp_desc,
        "icon": "📋",
        "icon_bg": "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
        "category": "general",
        "version": blueprint_data.get("blueprint_version", "1.0"),
        "source": "imported",
        "blueprint_data": blueprint_data,
    }
    return create_blueprint(payload)


def import_blueprint_from_file(file_path: str, name: str = "", description: str = "") -> dict:
    """从蓝图 JSON 文件导入蓝图。"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"蓝图文件不存在：{file_path}")
    with open(path, "r", encoding="utf-8") as f:
        blueprint_data = json.load(f)
    return import_blueprint_from_data(blueprint_data, name, description)


def validate_blueprint_data(blueprint_data: dict) -> tuple[bool, str]:
    """验证蓝图数据格式是否合法。

    返回 (is_valid, error_message)
    """
    if not isinstance(blueprint_data, dict):
        return False, "蓝图数据必须是字典"

    required_top = ["blueprint_version", "team_name", "members"]
    for field in required_top:
        if field not in blueprint_data:
            return False, f"缺少必需字段：{field}"

    members = blueprint_data.get("members", [])
    if not isinstance(members, list) or len(members) < 2:
        return False, "members 必须是至少 2 个成员的数组"

    for i, m in enumerate(members):
        if not isinstance(m, dict):
            return False, f"members[{i}] 必须是字典"
        for field in ["name", "role", "system_prompt"]:
            if field not in m:
                return False, f"members[{i}] 缺少必需字段：{field}"
        collab = m.get("collaboration", {})
        if not isinstance(collab, dict):
            return False, f"members[{i}].collaboration 必须是字典"
        if "type" not in collab:
            return False, f"members[{i}].collaboration 缺少 type 字段"
        if collab["type"] not in ("star", "direct", "parallel"):
            return False, f"members[{i}].collaboration.type 必须是 star/direct/parallel"

    return True, ""
