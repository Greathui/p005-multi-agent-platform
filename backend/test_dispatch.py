"""测试调度逻辑"""
from main import extract_mentioned_agents, extract_task_for_agent

agents = [
    {"id": "main", "name": "我（主智能体）"},
    {"id": "assistant_a", "name": "助手A"},
    {"id": "assistant_b", "name": "助手B"},
]

text = """好的，我来安排一下。

@助手A 请帮我整理这段内容，提炼出3个核心要点，用简洁的语言总结。

@助手B 请检查一下这段内容有没有逻辑问题和表述不清的地方。"""

mentioned = extract_mentioned_agents(text, agents)
print("提到的智能体：", [a["name"] for a in mentioned])
for a in mentioned:
    task = extract_task_for_agent(text, a["name"])
    print("  给" + a["name"] + "的任务：" + task[:50] + "...")
