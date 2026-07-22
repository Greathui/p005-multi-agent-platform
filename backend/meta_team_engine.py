# -*- coding: utf-8 -*-
"""
元团队工作模式引擎（Phase 2）

实现 Plan B 工作模式：全栈专家并行 + 互相评审打分 + 主智能体融合。

三阶段流程：
  1. 方案撰写（proposing）：3 个专家独立并行撰写完整蓝图方案
  2. 评审打分（reviewing）：每个专家读取其他专家方案，按五项标准打分 + 文字意见
  3. 融合产出（fusing）：主智能体读取所有方案和评审，产出最终蓝图 + 融合决策说明

经验自动积累：融合完成后，为每个专家追加经验记录（得分、评审意见、采纳情况）。
"""

import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import meta_team_config as mtc
import meta_team_task as mtt

# 注意：main 模块的函数通过延迟导入获取，避免循环导入
# （main.py 在初始化时导入本模块，本模块又需要 main 的 LLM 调用函数）

# 最大并行专家数
MAX_EXPERT_PARALLEL = 5

# 融合阶段的系统提示词
FUSION_SYSTEM_PROMPT = """你是「元团队融合主智能体」，负责将多个专家的团队设计方案融合成一份最优蓝图。

## 你的任务
你将看到 3 位专家各自独立设计的团队方案，以及他们互相评审的打分和意见。你的任务是融合这些方案的精华，产出一份最优的 team_blueprint.json。

## 融合原则
1. **不是拼接**：不要简单地把三个方案拼在一起，而是提取每个方案的精华，重新设计一份
2. **采纳高分要点**：参考评审打分，优先采纳得分高的方案中的设计要点
3. **补齐短板**：如果某个方案在某项得分低，看看其他方案在这方面是否更好
4. **保持完整**：最终蓝图必须包含完整的 members、tasks、recommended_config 字段
5. **说明决策**：在融合决策说明中，说清楚你采纳了哪些专家的哪些要点，为什么

## 输出格式
你必须输出两部分内容：

### 第一部分：融合决策说明
用 Markdown 格式说明你的融合决策：
- 采纳了专家 A 的哪些要点（理由）
- 采纳了专家 B 的哪些要点（理由）
- 采纳了专家 C 的哪些要点（理由）
- 未采纳的要点及原因
- 最终方案的整体设计思路

### 第二部分：最终蓝图
用 JSON 代码块输出完整的 team_blueprint.json：

```json
{
  "blueprint_version": "1.0",
  "team_name": "团队名称",
  "description": "团队适用场景描述",
  "members": [...],
  "tasks": [...],
  "recommended_config": {
    "context_window": 131072,
    "enable_thinking": true,
    "max_tokens": 8000
  },
  "execution_tips": "执行建议"
}
```
"""


# =========================================================================
# 模型自动选择
# =========================================================================

def auto_select_models(expert_count: int = 3, default_config_id: str = "") -> list[dict]:
    """
    从用户已配置的模型中，选择差异最大的 N 个配置分配给专家。

    选择策略：
    1. 按 provider 分组，优先选不同服务商的模型（保证多样性）
    2. 同一 provider 内选 model 名称不同的
    3. 不足 N 个时用全局默认配置补充
    4. 返回的每个元素是 {"config_id": "cfg_xxx"} 格式，可直接赋给 expert.model_config

    Args:
        expert_count: 需要的模型数量
        default_config_id: 用户在界面上选择的默认配置 ID（优先使用）

    Returns:
        长度为 expert_count 的列表，每个元素是 {"config_id": "cfg_xxx"} 或 None
    """
    # 延迟导入避免循环依赖
    from main import load_model_configs
    configs = load_model_configs()
    selected_ids = []
    used_providers = set()
    used_models = set()

    # 如果用户选了默认配置，优先使用
    if default_config_id:
        default_cfg = next((c for c in configs if c["id"] == default_config_id), None)
        if default_cfg:
            selected_ids.append(default_config_id)
            used_providers.add(default_cfg.get("provider", ""))
            used_models.add(default_cfg.get("model", ""))

    # 按 provider 分组
    provider_groups = {}
    for cfg in configs:
        provider = cfg.get("provider", "unknown")
        if provider not in provider_groups:
            provider_groups[provider] = []
        provider_groups[provider].append(cfg)

    # 第一轮：每个 provider 选一个（优先选未用过的 provider）
    for provider, cfgs in provider_groups.items():
        if len(selected_ids) >= expert_count:
            break
        if provider in used_providers:
            continue
        # 选该 provider 下第一个未用过的 model
        for cfg in cfgs:
            model = cfg.get("model", "")
            if model not in used_models:
                selected_ids.append(cfg["id"])
                used_providers.add(provider)
                used_models.add(model)
                break

    # 第二轮：如果还不够，从剩余配置中补充（允许同 provider）
    if len(selected_ids) < expert_count:
        for cfg in configs:
            if len(selected_ids) >= expert_count:
                break
            if cfg["id"] in selected_ids:
                continue
            selected_ids.append(cfg["id"])

    # 第三轮：如果还不够，用 None 填充（表示用全局默认）
    while len(selected_ids) < expert_count:
        selected_ids.append(None)

    # 转换为 model_config 格式
    result = []
    for cid in selected_ids[:expert_count]:
        if cid:
            result.append({"config_id": cid})
        else:
            result.append(None)
    return result


# =========================================================================
# 非流式 LLM 调用
# =========================================================================

def call_llm_complete(system_prompt: str, messages: list, agent: dict = None,
                      default_config_id: str = "", thinking_override: bool = None) -> str:
    """
    非流式调用大模型，收集完整回复并返回。

    内部复用 call_llm_stream 的流式接口，收集所有 token 拼接为完整文本。
    如果 LLM 调用失败（如 API 额度用完、认证失败等），call_llm_stream 会 yield 错误消息，
    本函数检测到错误消息后抛出 RuntimeError，让调用方正确处理失败。
    """
    # 延迟导入避免循环依赖
    from main import call_llm_stream
    full_text = ""
    for token in call_llm_stream(
        system_prompt=system_prompt,
        messages=messages,
        agent=agent,
        default_config_id=default_config_id,
        thinking_override=thinking_override
    ):
        full_text += token
    # call_llm_stream 在遇到错误时会 yield "❌ ..." 格式的错误消息
    # 检测到错误消息时抛出异常，避免把错误消息当作正常内容保存
    if full_text.startswith("❌"):
        raise RuntimeError(full_text)
    return full_text


# 单专家调用超时（秒）
EXPERT_TIMEOUT = 90
# 超时后重试次数
EXPERT_RETRY_COUNT = 1


def _call_with_retry(system_prompt: str, messages: list, agent: dict,
                     default_config_id: str, timeout: int = EXPERT_TIMEOUT,
                     retry_count: int = EXPERT_RETRY_COUNT) -> str:
    """
    带超时和重试的 LLM 调用。

    在子线程中执行 call_llm_complete，主线程等待 timeout 秒。
    超时后重试 retry_count 次，仍失败则抛出 TimeoutError。

    Returns:
        LLM 回复的完整文本

    Raises:
        TimeoutError: 所有重试都超时
        RuntimeError: LLM 返回错误消息
    """
    last_error = None
    for attempt in range(retry_count + 1):
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    call_llm_complete,
                    system_prompt=system_prompt,
                    messages=messages,
                    agent=agent,
                    default_config_id=default_config_id
                )
                result = future.result(timeout=timeout)
                return result
        except TimeoutError:
            last_error = f"调用超时（{timeout}s）"
            continue
        except Exception as e:
            last_error = str(e)
            # 非超时错误不重试（如认证失败、额度用完）
            raise
    raise TimeoutError(last_error)


# =========================================================================
# 阶段 1：方案并行撰写
# =========================================================================

def _build_proposal_prompt(expert: dict, task: dict) -> str:
    """构建专家撰写方案的系统提示词"""
    prompt = expert["system_prompt"]
    # 追加历史经验
    prompt += mtc.get_expert_context_for_task(expert["id"])
    # 追加当前任务信息
    prompt += f"\n\n## 当前设计任务\n任务标题：{task['title']}\n用户需求：{task.get('requirement', '')}\n\n请基于以上信息，设计一份完整的团队蓝图方案。直接输出 team_blueprint.json 方案，不要多余的寒暄。"
    return prompt


def _run_single_proposal(expert: dict, task: dict, model_config: dict | None,
                         default_config_id: str) -> dict:
    """
    单个专家撰写方案（在工作线程中执行，带超时和重试）

    Returns:
        {"expert_id": "...", "expert_name": "...", "success": bool, "content": "...", "error": "..."}
    """
    try:
        system_prompt = _build_proposal_prompt(expert, task)
        messages = [{"role": "user", "content": f"请为「{task['title']}」设计团队蓝图方案。"}]
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


def run_proposals(task_id: str, default_config_id: str = ""):
    """
    并行启动所有专家撰写方案（generator，产出 SSE 事件）

    产出的事件格式：
        ("expert_start", {"expert_id": "...", "expert_name": "..."})
        ("expert_complete", {"expert_id": "...", "expert_name": "...", "success": bool, "content_length": int})
        ("phase_complete", {"phase": "proposing", "success_count": int, "total": int})
        ("error", {"message": "..."})
    """
    task = mtt.get_task(task_id)
    if not task:
        yield ("error", {"message": "设计任务不存在"})
        return

    # 更新任务状态
    mtt.update_task_status(task_id, mtt.STATUS_DRAFTING)

    expert_ids = task.get("expert_ids", [])
    experts = mtc.get_experts_by_ids(expert_ids)
    if not experts:
        yield ("error", {"message": "没有可用的专家"})
        return

    # 自动选择模型配置（如果专家未绑定模型）
    model_configs = auto_select_models(len(experts), default_config_id)
    # 保存用户消息
    mtt.add_message(task_id, mtt.ROLE_ASSISTANT, f"已启动 {len(experts)} 位专家并行撰写方案...", None)

    # 并行执行
    results = []
    with ThreadPoolExecutor(max_workers=min(len(experts), MAX_EXPERT_PARALLEL)) as executor:
        future_to_expert = {}
        for i, expert in enumerate(experts):
            # 专家自己的 model_config 优先，否则用自动选择的
            mc = expert.get("model_config") or model_configs[i] if i < len(model_configs) else None
            future = executor.submit(_run_single_proposal, expert, task, mc, default_config_id)
            future_to_expert[future] = expert
            yield ("expert_start", {"expert_id": expert["id"], "expert_name": expert["name"]})

        for future in as_completed(future_to_expert):
            expert = future_to_expert[future]
            try:
                result = future.result()
                results.append(result)
                if result["success"]:
                    # 保存方案到文件
                    mtt.save_proposal(task_id, result["expert_id"], result["content"])
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

    success_count = sum(1 for r in results if r["success"])
    yield ("phase_complete", {
        "phase": "proposing",
        "success_count": success_count,
        "total": len(experts)
    })


# =========================================================================
# 阶段 2：专家互相评审
# =========================================================================

REVIEW_SYSTEM_PROMPT_TEMPLATE = """你正在评审其他专家的团队设计方案。

## 评审标准（五项，每项 1-10 分）
1. **团队结构**：成员配置是否合理、分工是否清晰、有无冗余或缺失
2. **提示词质量**：成员 system_prompt 的清晰度、可执行性、角色边界
3. **协作机制**：谁向谁汇报、并行还是串行、协作模式是否匹配任务
4. **需求匹配**：团队设计是否覆盖需求全部要点、有无偏离
5. **成本效率**：有无过度设计、成员数量是否最优

## 评审要求
- 打分客观公正，先肯定亮点再指出问题
- 意见要具体，引用方案中的具体设计点
- 每项打分后附 1-2 句说明

## 输出格式（必须严格遵守）
请输出 JSON 格式的评审结果：

```json
{{
  "scores": {{
    "团队结构": 8,
    "提示词质量": 7,
    "协作机制": 8,
    "需求匹配": 7,
    "成本效率": 7.5
  }},
  "average_score": 7.5,
  "highlights": ["亮点1", "亮点2"],
  "issues": ["问题1", "问题2"],
  "suggestions": ["建议1", "建议2"]
}}
```
"""


def _build_review_prompt(expert: dict, task: dict, other_proposals: list[dict]) -> str:
    """构建评审的系统提示词"""
    prompt = expert["system_prompt"]
    prompt += f"\n\n## 当前设计任务\n任务标题：{task['title']}\n用户需求：{task.get('requirement', '')}\n"
    prompt += "\n\n## 你需要评审的方案\n"
    for p in other_proposals:
        prompt += f"\n--- 专家「{p['expert_name']}」的方案 ---\n{p['content']}\n"
    prompt += "\n\n请按照评审标准对以上方案进行评审，输出 JSON 格式的评审结果。"
    return prompt


def _run_single_review(expert: dict, task: dict, proposals_to_review: list[dict],
                       model_config: dict | None, default_config_id: str) -> dict:
    """单个专家执行评审（在工作线程中执行，带超时和重试）"""
    try:
        system_prompt = _build_review_prompt(expert, task, proposals_to_review)
        messages = [{"role": "user", "content": "请评审以上方案并输出 JSON 评审结果。"}]
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
        # 尝试解析 JSON
        review_data = _extract_review_json(content)
        return {
            "expert_id": expert["id"],
            "expert_name": expert["name"],
            "success": True,
            "content": content,
            "review_data": review_data
        }
    except Exception as e:
        return {
            "expert_id": expert["id"],
            "expert_name": expert["name"],
            "success": False,
            "content": "",
            "error": str(e)
        }


def _extract_review_json(content: str) -> dict | None:
    """从 LLM 回复中提取评审 JSON"""
    # 尝试直接解析
    try:
        return json.loads(content)
    except Exception:
        pass
    # 尝试提取 JSON 代码块
    import re
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    # 尝试提取第一个 {...} 块
    match = re.search(r'\{[^{}]*"scores"[^{}]*\}', content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return None


def run_reviews(task_id: str, default_config_id: str = ""):
    """
    并行启动专家互相评审（generator，产出 SSE 事件）
    """
    task = mtt.get_task(task_id)
    if not task:
        yield ("error", {"message": "设计任务不存在"})
        return

    mtt.update_task_status(task_id, mtt.STATUS_REVIEWING)

    expert_ids = task.get("expert_ids", [])
    experts = mtc.get_experts_by_ids(expert_ids)
    if not experts:
        yield ("error", {"message": "没有可用的专家"})
        return

    # 收集所有方案
    proposals = []
    for eid in expert_ids:
        content = mtt.get_proposal(task_id, eid)
        if content:
            expert = next((e for e in experts if e["id"] == eid), None)
            proposals.append({
                "expert_id": eid,
                "expert_name": expert["name"] if expert else eid,
                "content": content
            })

    if len(proposals) < 2:
        yield ("error", {"message": "方案数量不足，至少需要 2 个方案才能进行评审"})
        return

    # 自动选择模型
    model_configs = auto_select_models(len(experts), default_config_id)

    # 每个专家评审其他所有人的方案
    results = []
    with ThreadPoolExecutor(max_workers=min(len(experts), MAX_EXPERT_PARALLEL)) as executor:
        future_to_expert = {}
        for i, expert in enumerate(experts):
            # 该专家要评审的方案 = 所有方案减去自己的
            other_proposals = [p for p in proposals if p["expert_id"] != expert["id"]]
            mc = expert.get("model_config") or model_configs[i] if i < len(model_configs) else None
            future = executor.submit(_run_single_review, expert, task, other_proposals, mc, default_config_id)
            future_to_expert[future] = expert
            yield ("expert_start", {"expert_id": expert["id"], "expert_name": expert["name"]})

        for future in as_completed(future_to_expert):
            expert = future_to_expert[future]
            try:
                result = future.result()
                results.append(result)
                if result["success"]:
                    mtt.save_review(task_id, result["expert_id"], result["content"])
                    yield ("expert_complete", {
                        "expert_id": result["expert_id"],
                        "expert_name": result["expert_name"],
                        "success": True,
                        "review_data": result.get("review_data")
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

    success_count = sum(1 for r in results if r["success"])
    yield ("phase_complete", {
        "phase": "reviewing",
        "success_count": success_count,
        "total": len(experts)
    })


# =========================================================================
# 阶段 3：主智能体融合
# =========================================================================

def _build_fusion_context(task: dict, proposals: list, reviews: list) -> str:
    """构建融合阶段的上下文（所有方案 + 评审）"""
    context = f"## 设计任务\n标题：{task['title']}\n需求：{task.get('requirement', '')}\n"

    context += "\n\n## 专家方案\n"
    for p in proposals:
        context += f"\n### 专家「{p['expert_name']}」的方案\n{p['content']}\n"

    context += "\n\n## 评审结果\n"
    for r in reviews:
        content = r.get("content", "")
        context += f"\n### 专家「{r['expert_name']}」的评审\n{content}\n"

    return context


def _extract_blueprint_json(content: str) -> dict | None:
    """从融合结果中提取蓝图 JSON"""
    import re
    # 尝试提取 JSON 代码块
    matches = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
    for match in reversed(matches):  # 从后往前（最后的代码块通常是最终蓝图）
        try:
            data = json.loads(match)
            if "members" in data:  # 验证是蓝图格式
                return data
        except Exception:
            continue
    # 尝试直接解析
    try:
        data = json.loads(content)
        if "members" in data:
            return data
    except Exception:
        pass
    return None


def _extract_fusion_decision(content: str) -> str:
    """从融合结果中提取融合决策说明（JSON 代码块之前的文本）"""
    import re
    # 找到第一个 JSON 代码块的位置
    match = re.search(r'```(?:json)?\s*\{', content)
    if match:
        return content[:match.start()].strip()
    return content.strip()


def _record_expert_experience(task: dict, proposals: list, reviews: list,
                              fusion_content: str, blueprint_data: dict | None):
    """为每个专家追加经验记录（融合完成后调用）"""
    for proposal in proposals:
        expert_id = proposal["expert_id"]
        expert_name = proposal["expert_name"]

        # 找到其他专家对该方案的评审
        other_reviews = [r for r in reviews if r["expert_id"] != expert_id]

        # 计算该方案收到的平均分
        scores = []
        score_breakdown = {}
        feedback_parts = []
        for r in other_reviews:
            rd = r.get("review_data")
            if rd and isinstance(rd, dict):
                r_scores = rd.get("scores", {})
                avg = rd.get("average_score")
                if avg:
                    scores.append(avg)
                # 合并评分明细
                for k, v in r_scores.items():
                    if k not in score_breakdown:
                        score_breakdown[k] = []
                    score_breakdown[k].append(v)
                # 收集意见
                highlights = rd.get("highlights", [])
                issues = rd.get("issues", [])
                suggestions = rd.get("suggestions", [])
                if highlights:
                    feedback_parts.append(f"亮点：{', '.join(highlights)}")
                if issues:
                    feedback_parts.append(f"问题：{', '.join(issues)}")
                if suggestions:
                    feedback_parts.append(f"建议：{', '.join(suggestions)}")

        # 计算平均得分
        avg_score = round(sum(scores) / len(scores), 2) if scores else None

        # 合并评分明细（取平均）
        avg_breakdown = {}
        for k, v_list in score_breakdown.items():
            if v_list:
                avg_breakdown[k] = round(sum(v_list) / len(v_list), 2)

        # 分析采纳情况（简单实现：检查蓝图 JSON 中是否包含该专家方案的某些关键词）
        adopted = []
        not_adopted = []
        if blueprint_data:
            bp_json = json.dumps(blueprint_data, ensure_ascii=False)
            # 简单检查：如果蓝图中的成员名与该专家方案中的成员名相同，则认为采纳了
            proposal_text = proposal.get("content", "")
            if "team_name" in blueprint_data:
                # 这里只是简单实现，实际可以更复杂
                pass

        # 追加经验记录
        mtc.add_experience_record(
            expert_id=expert_id,
            task_id=task["id"],
            task_title=task.get("title", ""),
            score_received=avg_score,
            score_breakdown=avg_breakdown,
            feedback_summary="；".join(feedback_parts) if feedback_parts else "无评审意见",
            fusion_adopted=adopted,
            fusion_not_adopted=not_adopted
        )


def run_fusion(task_id: str, default_config_id: str = ""):
    """
    主智能体融合（generator，产出 SSE 事件）

    流式输出融合过程，完成后自动积累经验。
    """
    task = mtt.get_task(task_id)
    if not task:
        yield ("error", {"message": "设计任务不存在"})
        return

    mtt.update_task_status(task_id, mtt.STATUS_FUSING)

    expert_ids = task.get("expert_ids", [])
    experts = mtc.get_experts_by_ids(expert_ids)

    # 收集所有方案和评审
    proposals = []
    for eid in expert_ids:
        content = mtt.get_proposal(task_id, eid)
        if content:
            expert = next((e for e in experts if e["id"] == eid), None)
            proposals.append({
                "expert_id": eid,
                "expert_name": expert["name"] if expert else eid,
                "content": content
            })

    reviews = []
    for eid in expert_ids:
        content = mtt.get_review(task_id, eid)
        if content:
            expert = next((e for e in experts if e["id"] == eid), None)
            # 尝试解析评审 JSON
            review_data = _extract_review_json(content)
            reviews.append({
                "expert_id": eid,
                "expert_name": expert["name"] if expert else eid,
                "content": content,
                "review_data": review_data
            })

    if not proposals:
        yield ("error", {"message": "没有方案可融合"})
        return

    # 构建融合上下文
    fusion_context = _build_fusion_context(task, proposals, reviews)
    system_prompt = FUSION_SYSTEM_PROMPT
    messages = [{"role": "user", "content": fusion_context + "\n\n请开始融合，输出融合决策说明和最终蓝图 JSON。"}]

    # 使用全局默认配置（主智能体融合不绑定特定专家的模型）
    agent = {"id": "fusion_main", "model_config": None, "can_use_tools": False}

    yield ("fusion_start", {"message": "主智能体开始融合方案..."})

    # 流式输出融合过程
    from main import call_llm_stream as _call_llm_stream
    full_content = ""
    for token in _call_llm_stream(
        system_prompt=system_prompt,
        messages=messages,
        agent=agent,
        default_config_id=default_config_id
    ):
        full_content += token
        yield ("token", {"content": token})

    # 保存融合决策说明
    fusion_decision = _extract_fusion_decision(full_content)
    mtt.save_fusion_decision(task_id, fusion_decision)

    # 提取蓝图 JSON
    blueprint_data = _extract_blueprint_json(full_content)
    if blueprint_data:
        version = mtt.save_blueprint_version(task_id, blueprint_data)
        mtt.update_task_status(task_id, mtt.STATUS_COMPLETED)
        yield ("fusion_complete", {
            "success": True,
            "blueprint_version": version,
            "message": f"融合完成，蓝图已保存为 v{version}"
        })
    else:
        # 蓝图提取失败，保存原始内容作为参考
        mtt.save_fusion_decision(task_id, full_content)
        mtt.update_task_status(task_id, mtt.STATUS_COMPLETED)
        yield ("fusion_complete", {
            "success": False,
            "message": "融合完成但蓝图 JSON 提取失败，请查看融合决策说明手动整理"
        })

    # 自动积累经验
    try:
        _record_expert_experience(task, proposals, reviews, full_content, blueprint_data)
        yield ("experience_recorded", {"message": "专家经验已自动积累"})
    except Exception as e:
        yield ("error", {"message": f"经验记录保存失败：{str(e)}"})

    yield ("phase_complete", {"phase": "fusing", "success": blueprint_data is not None})


# =========================================================================
# 深度模式一键全流程（Phase 4：自动流转）
# =========================================================================

def run_all_phases(task_id: str, default_config_id: str = ""):
    """
    深度模式一键全流程（generator，产出 SSE 事件）

    依次自动执行三个阶段：方案撰写 → 评审 → 融合。
    前一阶段完成后自动进入下一阶段，无需用户手动点击。
    如果某阶段成功数量不足（方案 < 2 或评审 < 1），中止流程并产出 error 事件。

    事件格式：
        ("all_start", {"message": "..."})
        各阶段的 expert_start/expert_complete/phase_complete/token/fusion_complete 事件
        ("all_complete", {"success": bool, "message": "..."})
        ("error", {"message": "..."})
    """
    yield ("all_start", {"message": "深度模式全流程启动，将依次执行方案撰写、评审、融合三个阶段"})

    # ===== 阶段 1：方案撰写 =====
    proposal_success = 0
    proposal_total = 0
    for event_type, event_data in run_proposals(task_id, default_config_id):
        yield (event_type, event_data)
        if event_type == "phase_complete":
            proposal_success = event_data.get("success_count", 0)
            proposal_total = event_data.get("total", 0)

    # 检查方案数量是否足够
    if proposal_success < 2:
        yield ("error", {
            "message": f"方案撰写阶段成功数不足（{proposal_success}/{proposal_total}），至少需要 2 个方案才能进行评审，全流程中止"
        })
        yield ("all_complete", {"success": False, "message": "方案撰写阶段失败"})
        return

    # ===== 阶段 2：评审 =====
    review_success = 0
    review_total = 0
    for event_type, event_data in run_reviews(task_id, default_config_id):
        yield (event_type, event_data)
        if event_type == "phase_complete":
            review_success = event_data.get("success_count", 0)
            review_total = event_data.get("total", 0)

    # 检查评审数量
    if review_success < 1:
        yield ("error", {
            "message": f"评审阶段全部失败（{review_success}/{review_total}），无法进行融合，全流程中止"
        })
        yield ("all_complete", {"success": False, "message": "评审阶段失败"})
        return

    # ===== 阶段 3：融合 =====
    fusion_success = False
    for event_type, event_data in run_fusion(task_id, default_config_id):
        yield (event_type, event_data)
        if event_type == "fusion_complete":
            fusion_success = event_data.get("success", False)

    yield ("all_complete", {
        "success": fusion_success,
        "message": "全流程完成" if fusion_success else "融合阶段失败，请查看融合决策说明"
    })
