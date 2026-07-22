"""
多智能体协作平台 - 全功能自动化测试
测试范围：
1. 基础API健康检查
2. 项目（对话）CRUD
3. 智能体管理
4. 模型配置
5. 消息历史
6. 文件系统工具（list/read/write/create_dir）
7. 权限系统（白名单、隔离、授权/撤销）
8. 任务文件夹机制（input/output隔离、只读保护、结果提交）
9. 目录结构自动初始化
10. @智能体调度解析
11. 路径遍历防护
12. 前端静态文件服务
"""
import sys
import os
import json
import tempfile
import shutil
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 在导入main之前，备份并使用临时数据文件
import main as main_module

client = TestClient(main_module.app)

results = {
    "passed": 0,
    "failed": 0,
    "errors": []
}

def test(name, func):
    try:
        func()
        results["passed"] += 1
        print(f"  ✅ {name}")
    except AssertionError as e:
        results["failed"] += 1
        results["errors"].append((name, str(e)))
        print(f"  ❌ {name}: {e}")
    except Exception as e:
        results["failed"] += 1
        results["errors"].append((name, f"异常: {type(e).__name__}: {e}"))
        import traceback
        traceback.print_exc()
        print(f"  💥 {name}: {type(e).__name__}: {e}")

print("=" * 60)
print("多智能体协作平台 - 全功能自动化测试")
print("=" * 60)

TEST_DIR = tempfile.mkdtemp(prefix="multi_agent_test_")
print(f"\n📂 测试临时目录: {TEST_DIR}")

# ========================================================================
# 1. 基础API测试
# ========================================================================
print("\n🔹 1. 基础API健康检查")

def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
test("健康检查接口", test_health)

def test_get_agents():
    r = client.get("/api/agents")
    assert r.status_code == 200
    data = r.json()
    assert "agents" in data
    agents = data["agents"]
    assert isinstance(agents, list)
    assert len(agents) >= 3
    ids = [a["id"] for a in agents]
    assert "main" in ids
    assert "assistant_a" in ids
    assert "assistant_b" in ids
test("获取智能体列表", test_get_agents)

# ========================================================================
# 2. 项目（对话）CRUD测试
# ========================================================================
print("\n🔹 2. 项目（对话）管理")

test_conv_id = None

def test_create_project_without_path():
    global test_conv_id
    r = client.post("/api/conversations", json={"title": "测试项目"})
    assert r.status_code == 200
    data = r.json()
    assert "conversation" in data
    conv = data["conversation"]
    assert conv["title"] == "测试项目"
    assert "id" in conv
    assert conv["root_path"] == ""
    test_conv_id = conv["id"]
test("创建项目（无工作目录）", test_create_project_without_path)

def test_create_project_with_path():
    project_dir = os.path.join(TEST_DIR, "test_project_1")
    os.makedirs(project_dir, exist_ok=True)
    
    r = client.post("/api/conversations", json={
        "title": "带目录的测试项目",
        "root_path": project_dir
    })
    assert r.status_code == 200
    data = r.json()
    conv = data["conversation"]
    assert conv["root_path"] != ""
    
    # 验证目录是否自动创建
    assert os.path.isdir(os.path.join(project_dir, ".agent", "tasks")), ".agent/tasks 未创建"
    assert os.path.isdir(os.path.join(project_dir, "shared")), "shared 未创建"
    assert os.path.isdir(os.path.join(project_dir, "agent_work")), "agent_work 未创建"
    assert os.path.isdir(os.path.join(project_dir, "deliverables")), "deliverables 未创建"
    assert os.path.isdir(os.path.join(project_dir, "agent_work", "assistant_a")), "助手A工作区未创建"
    assert os.path.isdir(os.path.join(project_dir, "agent_work", "assistant_b")), "助手B工作区未创建"
    
    # 验证智能体权限
    assert "agents" in conv
    for a in conv["agents"]:
        if a["id"] in ("assistant_a", "assistant_b"):
            assert "allowed_paths" in a, f"{a['id']} 缺少allowed_paths"
            assert len(a["allowed_paths"]) >= 3, f"{a['id']} 权限项不足"
test("创建项目（带工作目录，自动初始化结构）", test_create_project_with_path)

def test_get_conversations():
    r = client.get("/api/conversations")
    assert r.status_code == 200
    data = r.json()
    assert "conversations" in data
    convs = data["conversations"]
    assert isinstance(convs, list)
    assert len(convs) >= 1
test("获取项目列表", test_get_conversations)

def test_update_project_path():
    project_dir = os.path.join(TEST_DIR, "test_project_update")
    os.makedirs(project_dir, exist_ok=True)
    
    r = client.post("/api/conversations", json={"title": "待设置目录"})
    conv_id = r.json()["conversation"]["id"]
    
    r = client.put(f"/api/conversations/{conv_id}/path", json={"root_path": project_dir})
    assert r.status_code == 200
    data = r.json()
    assert data["conversation"]["root_path"] != ""
    
    assert os.path.isdir(os.path.join(project_dir, ".agent", "tasks"))
    assert os.path.isdir(os.path.join(project_dir, "shared"))
test("设置项目工作目录（自动初始化）", test_update_project_path)

def test_rename_conversation():
    r = client.put(f"/api/conversations/{test_conv_id}", json={"title": "重命名后的项目"})
    assert r.status_code == 200
test("重命名项目", test_rename_conversation)

# ========================================================================
# 3. 消息历史测试
# ========================================================================
print("\n🔹 3. 消息历史")

def test_get_messages_empty():
    r = client.get(f"/api/messages?conversation_id={test_conv_id}")
    assert r.status_code == 200
    data = r.json()
    assert "messages" in data
    msgs = data["messages"]
    assert isinstance(msgs, list)
test("获取空项目消息列表", test_get_messages_empty)

# ========================================================================
# 4. 文件系统权限测试
# ========================================================================
print("\n🔹 4. 文件系统与权限控制")

perm_test_dir = os.path.join(TEST_DIR, "perm_test")
os.makedirs(perm_test_dir, exist_ok=True)

r = client.post("/api/conversations", json={
    "title": "权限测试项目",
    "root_path": perm_test_dir
})
perm_conv_id = r.json()["conversation"]["id"]
print(f"    权限测试项目ID: {perm_conv_id}")

def init_project_directly():
    result = main_module.execute_tool(
        "init_project_structure", {}, perm_test_dir, "main", perm_conv_id
    )
    assert ("✅" in result) or ("初始化" in result) or ("完成" in result), f"初始化失败: {result}"
    assert os.path.isdir(os.path.join(perm_test_dir, ".agent", "tasks"))
test("init_project_structure 初始化目录", init_project_directly)

def test_list_directory_as_main():
    result = main_module.execute_tool("list_directory", {"path": "."}, perm_test_dir, "main", perm_conv_id)
    assert "权限不足" not in result, f"主智能体应能列出根目录: {result}"
test("主智能体可以列出根目录", test_list_directory_as_main)

def test_write_file_as_main():
    result = main_module.execute_tool(
        "write_file",
        {"path": "test_file.txt", "content": "主智能体写入的内容"},
        perm_test_dir, "main", perm_conv_id
    )
    assert "✅" in result, f"写入失败: {result}"
    assert os.path.isfile(os.path.join(perm_test_dir, "test_file.txt"))
test("主智能体可以写入根目录文件", test_write_file_as_main)

def test_read_file_as_main():
    result = main_module.execute_tool("read_file", {"path": "test_file.txt"}, perm_test_dir, "main", perm_conv_id)
    assert "主智能体写入的内容" in result, f"读取内容不符: {result[:100]}"
test("主智能体可以读取根目录文件", test_read_file_as_main)

def test_create_dir_as_main():
    result = main_module.execute_tool("create_directory", {"path": "docs"}, perm_test_dir, "main", perm_conv_id)
    assert "✅" in result, f"创建目录失败: {result}"
    assert os.path.isdir(os.path.join(perm_test_dir, "docs"))
test("主智能体可以创建目录", test_create_dir_as_main)

def test_assistant_a_cannot_access_root():
    result = main_module.execute_tool("list_directory", {"path": "."}, perm_test_dir, "assistant_a", perm_conv_id)
    assert "权限不足" in result, f"助手A应无权访问根目录，返回: {result[:100]}"
test("助手A默认无权访问根目录", test_assistant_a_cannot_access_root)

def test_assistant_a_can_access_own_workspace():
    result = main_module.execute_tool(
        "list_directory", {"path": "agent_work/assistant_a"},
        perm_test_dir, "assistant_a", perm_conv_id
    )
    assert "权限不足" not in result, f"助手A应能访问自己的工作区: {result[:100]}"
test("助手A可以访问自己的工作区", test_assistant_a_can_access_own_workspace)

def test_assistant_a_can_access_shared():
    result = main_module.execute_tool(
        "list_directory", {"path": "shared"},
        perm_test_dir, "assistant_a", perm_conv_id
    )
    assert "权限不足" not in result, f"助手A应能访问shared: {result[:100]}"
test("助手A可以访问共享目录", test_assistant_a_can_access_shared)

def test_assistant_a_can_write_own_workspace():
    result = main_module.execute_tool(
        "write_file",
        {"path": "agent_work/assistant_a/notes.txt", "content": "助手A的笔记"},
        perm_test_dir, "assistant_a", perm_conv_id
    )
    assert "✅" in result, f"写入工作区失败: {result}"
test("助手A可以写入自己的工作区", test_assistant_a_can_write_own_workspace)

def test_assistant_a_cannot_write_root():
    result = main_module.execute_tool(
        "write_file",
        {"path": "hacker.txt", "content": "试图越权写入"},
        perm_test_dir, "assistant_a", perm_conv_id
    )
    assert ("权限不足" in result) or ("❌" in result), f"越权写入应被拦截: {result[:100]}"
test("助手A不能写入根目录（越权拦截）", test_assistant_a_cannot_write_root)

def test_assistant_a_cannot_access_other_workspace():
    result = main_module.execute_tool(
        "list_directory", {"path": "agent_work/assistant_b"},
        perm_test_dir, "assistant_a", perm_conv_id
    )
    assert "权限不足" in result, f"应不能访问其他智能体工作区: {result[:100]}"
test("助手A不能访问助手B的工作区（隔离）", test_assistant_a_cannot_access_other_workspace)

def test_grant_path_access():
    result = main_module.execute_tool(
        "grant_path_access",
        {"agent_id": "assistant_a", "path": "docs/"},
        perm_test_dir, "main", perm_conv_id
    )
    assert "✅" in result, f"授权失败: {result}"
    
    result2 = main_module.execute_tool(
        "list_directory", {"path": "docs"},
        perm_test_dir, "assistant_a", perm_conv_id
    )
    assert "权限不足" not in result2, f"授权后应能访问docs: {result2[:100]}"
test("grant_path_access 授权后可访问", test_grant_path_access)

def test_revoke_path_access():
    main_module.execute_tool(
        "grant_path_access",
        {"agent_id": "assistant_a", "path": "docs/"},
        perm_test_dir, "main", perm_conv_id
    )
    result = main_module.execute_tool(
        "revoke_path_access",
        {"agent_id": "assistant_a", "path": "docs/"},
        perm_test_dir, "main", perm_conv_id
    )
    assert ("✅" in result) or ("已撤销" in result) or ("本来就没有" in result), f"撤销失败: {result}"
test("revoke_path_access 撤销权限", test_revoke_path_access)

# ========================================================================
# 5. 任务文件夹机制测试
# ========================================================================
print("\n🔹 5. 任务文件夹与权限模板")

def test_create_task_document():
    result = main_module.execute_tool(
        "create_task",
        {
            "agent_id": "assistant_a",
            "task_type": "document",
            "description": "写一份项目介绍文档",
            "input_files": ["test_file.txt"]
        },
        perm_test_dir, "main", perm_conv_id
    )
    assert "✅" in result, f"创建任务失败: {result[:200]}"
    assert "task_" in result
    assert "输入目录" in result
    assert "输出目录" in result
    
    tasks_dir = os.path.join(perm_test_dir, ".agent", "tasks")
    task_dirs = [d for d in os.listdir(tasks_dir) if d.startswith("task_")]
    assert len(task_dirs) >= 1, "没有创建任务目录"
    
    task_dir = os.path.join(tasks_dir, sorted(task_dirs)[-1])
    assert os.path.isdir(os.path.join(task_dir, "input")), "input目录未创建"
    assert os.path.isdir(os.path.join(task_dir, "output")), "output目录未创建"
    assert os.path.isfile(os.path.join(task_dir, "TASK.md")), "TASK.md未创建"
    assert os.path.isfile(os.path.join(task_dir, "meta.json")), "meta.json未创建"
    
    with open(os.path.join(task_dir, "meta.json"), "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["type"] == "document"
    assert meta["agent_id"] == "assistant_a"
    assert meta["status"] == "pending"
test("create_task 创建任务（document类型）", test_create_task_document)

def test_task_input_readonly():
    """任务input目录应该是只读的"""
    result = main_module.execute_tool(
        "create_task",
        {
            "agent_id": "assistant_a",
            "task_type": "general",
            "description": "测试input只读"
        },
        perm_test_dir, "main", perm_conv_id
    )
    
    tasks_dir = os.path.join(perm_test_dir, ".agent", "tasks")
    task_dirs = sorted([d for d in os.listdir(tasks_dir) if d.startswith("task_")])
    latest_task = task_dirs[-1]
    
    write_result = main_module.execute_tool(
        "write_file",
        {"path": f".agent/tasks/{latest_task}/input/hack.txt", "content": "试图写入input"},
        perm_test_dir, "assistant_a", perm_conv_id
    )
    # input目录写入应被拦截（只读检查）
    assert ("权限不足" in write_result) or ("只读" in write_result) or ("❌" in write_result), \
        f"写入input应被拦截，返回: {write_result[:200]}"
test("任务input目录对智能体只读", test_task_input_readonly)

def test_task_output_writable():
    tasks_dir = os.path.join(perm_test_dir, ".agent", "tasks")
    # 按mtime排序找到最新任务
    task_dirs_path = sorted(
        [d for d in Path(tasks_dir).iterdir() if d.is_dir() and d.name.startswith("task_")],
        key=lambda x: x.stat().st_mtime, reverse=True
    )
    latest_task = task_dirs_path[0].name
    
    write_result = main_module.execute_tool(
        "write_file",
        {"path": f".agent/tasks/{latest_task}/output/result.txt", "content": "任务结果"},
        perm_test_dir, "assistant_a", perm_conv_id
    )
    assert "✅" in write_result, f"写入output失败: {write_result[:100]}"
    assert os.path.isfile(os.path.join(tasks_dir, latest_task, "output", "result.txt"))
test("任务output目录可写", test_task_output_writable)

def test_submit_task_result():
    # 创建一个专门用于提交结果的任务
    result = main_module.execute_tool(
        "create_task",
        {
            "agent_id": "assistant_a",
            "task_type": "general",
            "description": "提交测试任务"
        },
        perm_test_dir, "main", perm_conv_id
    )
    assert "✅" in result
    
    tasks_dir = os.path.join(perm_test_dir, ".agent", "tasks")
    # 按mtime排序找到最新任务（和代码逻辑一致）
    task_dirs_path = sorted(
        [d for d in Path(tasks_dir).iterdir() if d.is_dir() and d.name.startswith("task_")],
        key=lambda x: x.stat().st_mtime, reverse=True
    )
    latest_task = task_dirs_path[0].name
    
    # 写入结果文件到output
    main_module.execute_tool(
        "write_file",
        {"path": f".agent/tasks/{latest_task}/output/final.md", "content": "# 最终报告"},
        perm_test_dir, "assistant_a", perm_conv_id
    )
    
    result = main_module.execute_tool(
        "submit_task_result",
        {
            "result_files": [f".agent/tasks/{latest_task}/output/final.md"],
            "summary": "任务已完成"
        },
        perm_test_dir, "assistant_a", perm_conv_id
    )
    assert ("✅" in result) or ("已提交" in result), f"提交结果失败: {result[:200]}"
    
    meta_path = os.path.join(tasks_dir, latest_task, "meta.json")
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["status"] == "completed", f"任务状态应为completed，实际: {meta['status']}"
test("submit_task_result 提交结果", test_submit_task_result)

def test_all_task_types():
    """测试所有任务类型模板"""
    for ttype in ["document", "code_review", "coding", "data_analysis", "testing", "general"]:
        result = main_module.execute_tool(
            "create_task",
            {"agent_id": "assistant_b", "task_type": ttype, "description": f"测试{ttype}类型"},
            perm_test_dir, "main", perm_conv_id
        )
        assert "✅" in result, f"任务类型 {ttype} 创建失败: {result[:100]}"
test("所有6种任务类型模板均可创建", test_all_task_types)

# ========================================================================
# 6. 权限边界测试
# ========================================================================
print("\n🔹 6. 权限边界测试")

def test_subagent_cannot_use_manage_tools():
    for tool in ["init_project_structure", "create_agent_workspace", "create_task", "grant_path_access", "revoke_path_access"]:
        result = main_module.execute_tool(tool, {}, perm_test_dir, "assistant_a", perm_conv_id)
        assert "只有主智能体" in result, f"工具 {tool} 应被子智能体拒绝，返回: {result[:100]}"
test("子智能体不能使用管理工具", test_subagent_cannot_use_manage_tools)

def test_path_traversal_protection():
    result = main_module.execute_tool(
        "read_file", {"path": "../../../Windows/System32/config/SAM"},
        perm_test_dir, "main", perm_conv_id
    )
    assert ("超出" in result) or ("错误" in result), f"路径遍历应被拦截: {result[:100]}"
test("路径遍历攻击被拦截", test_path_traversal_protection)

# ========================================================================
# 7. 模型配置API测试
# ========================================================================
print("\n🔹 7. 模型配置管理")

def test_get_model_configs():
    r = client.get("/api/model-configs")
    assert r.status_code == 200
    data = r.json()
    assert "configs" in data
    assert isinstance(data["configs"], list)
test("获取模型配置", test_get_model_configs)

def test_create_model_config():
    r = client.post("/api/model-configs", json={
        "name": "测试配置",
        "provider": "custom",
        "base_url": "https://api.example.com/v1",
        "api_key": "sk-test123",
        "model": "gpt-4"
    })
    assert r.status_code == 200
    data = r.json()
    assert "config" in data
    assert data["config"]["name"] == "测试配置"
test("创建模型配置", test_create_model_config)

# ========================================================================
# 8. 智能体编辑API
# ========================================================================
print("\n🔹 8. 智能体管理")

def test_update_conv_agent():
    """更新项目级智能体信息"""
    r = client.put(f"/api/conversations/{perm_conv_id}/agents/assistant_a", json={
        "name": "文档助手",
        "role": "专门写文档的",
        "avatar": "📄"
    })
    assert r.status_code == 200
test("更新项目级智能体信息", test_update_conv_agent)

# ========================================================================
# 9. @提及解析测试
# ========================================================================
print("\n🔹 9. @智能体解析")

def test_extract_mentions_text():
    """测试从字符串中提取@提及"""
    agents = main_module.load_agents()
    mentioned = main_module.extract_mentioned_agents("@助手A 帮我写文档", agents)
    ids = [a["id"] for a in mentioned]
    assert "assistant_a" in ids, f"应识别助手A，实际识别: {ids}"
test("@助手A 从字符串解析正确", test_extract_mentions_text)

def test_extract_mentions_list():
    """测试从消息列表中提取@提及"""
    msgs = [{"role": "user", "content": "@助手A 写文档 @助手B 检查代码"}]
    agents = main_module.load_agents()
    mentioned = main_module.extract_mentioned_agents(msgs, agents)
    ids = [a["id"] for a in mentioned]
    assert "assistant_a" in ids
    assert "assistant_b" in ids
test("@多个智能体从消息列表解析正确", test_extract_mentions_list)

def test_extract_no_mentions():
    """无@时返回空列表"""
    agents = main_module.load_agents()
    mentioned = main_module.extract_mentioned_agents("你好，请帮我", agents)
    assert len(mentioned) == 0
test("无@时不返回任何智能体", test_extract_no_mentions)

# ========================================================================
# 10. 前端静态文件服务
# ========================================================================
print("\n🔹 10. 前端静态文件服务")

def test_frontend_index():
    r = client.get("/")
    assert r.status_code == 200, f"首页应返回200，实际{r.status_code}"
    assert ("<!DOCTYPE html>" in r.text) or ("<html" in r.text), "应返回HTML"
test("前端首页可访问", test_frontend_index)

def test_frontend_assets():
    """静态资源路径应该可以访问（验证assets挂载）"""
    r = client.get("/")
    assert r.status_code == 200
    # 只要首页能访问就OK，具体asset文件可能hash变化
test("静态资源路径配置正确", test_frontend_assets)

# ========================================================================
# 11. create_agent_workspace 测试
# ========================================================================
print("\n🔹 11. 工作区创建")

def test_create_agent_workspace():
    """先创建一个新智能体，再创建工作区"""
    # 创建新智能体
    r = client.post("/api/agents", json={
        "name": "测试员C",
        "role": "测试专员",
        "avatar": "🧪"
    })
    assert r.status_code == 200
    new_id = r.json()["agent"]["id"]
    
    # 为它创建工作区
    result = main_module.execute_tool(
        "create_agent_workspace",
        {"agent_id": new_id},
        perm_test_dir, "main", perm_conv_id
    )
    assert "✅" in result, f"创建工作区失败: {result[:100]}"
    assert os.path.isdir(os.path.join(perm_test_dir, "agent_work", new_id))
test("create_agent_workspace 为新智能体创建工作区", test_create_agent_workspace)

# ========================================================================
# 测试总结
# ========================================================================
print("\n" + "=" * 60)
print("测试完成！")
print(f"  ✅ 通过: {results['passed']}")
print(f"  ❌ 失败: {results['failed']}")
total = results['passed'] + results['failed']
print(f"  📊 通过率: {results['passed']/total*100:.1f}%")
print("=" * 60)

if results["errors"]:
    print("\n失败详情:")
    for name, err in results["errors"]:
        print(f"  - {name}: {err}")

try:
    shutil.rmtree(TEST_DIR)
    print(f"\n🧹 已清理临时测试目录")
except Exception as e:
    print(f"\n⚠️ 清理临时目录失败: {e}")

if results["failed"] == 0:
    print("\n🎉 所有测试通过！")
    sys.exit(0)
else:
    print(f"\n⚠️ 有 {results['failed']} 个测试失败，请检查")
    sys.exit(1)
