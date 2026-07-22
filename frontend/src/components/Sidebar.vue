<template>
  <div class="sidebar">
    <!-- 顶部：应用 Logo + 名称 -->
    <div class="sidebar-header">
      <div class="app-brand">
        <div class="brand-logo">
          <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="16" cy="16" r="14" stroke="white" stroke-width="2" stroke-opacity="0.3"/>
            <circle cx="16" cy="8" r="3" fill="white"/>
            <circle cx="8" cy="20" r="3" fill="white" fill-opacity="0.8"/>
            <circle cx="24" cy="20" r="3" fill="white" fill-opacity="0.8"/>
            <path d="M16 11 L8 17 M16 11 L24 17 M8 20 L24 20" stroke="white" stroke-width="1.5" stroke-opacity="0.5"/>
          </svg>
        </div>
        <div class="brand-text">
          <span class="brand-name">多智能体团队</span>
          <span class="brand-sub">Multi-Agent Studio</span>
        </div>
      </div>
    </div>

    <!-- 视图切换标签栏 -->
    <div class="view-tabs">
      <div class="view-tab" :class="{ active: store.sidebarView === 'projects' }" @click="store.showProjectsPanel()">
        <span>📁 团队</span>
      </div>
      <div class="view-tab" :class="{ active: store.sidebarView === 'meta-team' }" @click="store.showMetaTeamPanel()">
        <span>🎯 团队设计</span>
      </div>
    </div>

    <!-- ===== 项目视图 ===== -->
    <template v-if="store.sidebarView === 'projects'">
    <!-- 搜索框 -->
    <div class="search-box">
      <el-input
        v-model="searchText"
        placeholder="搜索团队或项目"
        size="small"
        prefix-icon="Search"
        clearable
      />
    </div>

    <!-- 新建团队按钮 -->
    <div class="new-conv-btn">
      <el-button type="primary" plain class="full-btn" @click="openNewTeamDialog">
        + 新团队
      </el-button>
    </div>

    <!-- 团队列表（两级树：团队 > 项目） -->
    <div class="conv-section">
      <div class="section-label">团队</div>
      <div class="team-list">
        <div
          v-for="team in filteredTeams"
          :key="team.id"
          class="team-group"
        >
          <!-- 团队头部 -->
          <div class="team-header" @click="handleSelectTeam(team)">
            <span class="team-arrow" :class="{ collapsed: collapsedTeams[team.id] }" @click.stop="toggleTeamCollapse(team.id)">▾</span>
            <span class="team-icon">👥</span>
            <span class="team-name" :title="team.name">{{ team.name }}</span>
            <span class="team-count">{{ team.projects?.length || 0 }}</span>
            <div class="team-actions">
              <button class="team-action-btn" title="新建项目" @click.stop="openNewProjectInTeam(team)">＋</button>
              <button class="team-action-btn team-delete-btn" title="删除团队" @click.stop="handleDeleteTeam(team)">×</button>
            </div>
          </div>
          <!-- 团队下项目列表 -->
          <div v-show="!collapsedTeams[team.id]" class="team-projects">
            <div
              v-for="conv in team.projects"
              :key="conv.id"
              class="conv-item"
              :class="{ active: conv.id === store.currentConversationId }"
              @click="handleSelectConv(conv)"
            >
              <template v-if="editingConvId === conv.id">
                <el-input
                  v-model="editingTitle"
                  size="small"
                  @keyup.enter="handleSaveRename(conv)"
                  @blur="handleSaveRename(conv)"
                  @click.stop
                  ref="renameInputRef"
                />
              </template>
              <template v-else>
                <div class="conv-title-wrap">
                  <span class="running-dot" v-if="store.runningConvIds.includes(conv.id)" title="运行中"></span>
                  <div class="conv-title" @dblclick.stop="startRename(conv)">{{ conv.title }}</div>
                  <div class="conv-path" v-if="conv.root_path" :title="conv.root_path">{{ formatPath(conv.root_path) }}</div>
                </div>
              </template>
              <div class="conv-actions" v-if="editingConvId !== conv.id">
                <el-button
                  text
                  size="small"
                  class="action-btn"
                  :title="conv.root_path ? '重置项目目录结构' : '请先设置项目目录'"
                  :disabled="!conv.root_path"
                  @click.stop="handleResetStructure(conv)"
                >🔄</el-button>
                <el-button
                  text
                  size="small"
                  class="action-btn"
                  title="重命名"
                  @click.stop="startRename(conv)"
                >✎</el-button>
                <el-button
                  text
                  size="small"
                  class="delete-btn"
                  title="删除项目"
                  @click.stop="handleDelete(conv)"
                >×</el-button>
              </div>
            </div>
            <div v-if="!team.projects?.length" class="empty-tip-small">暂无项目，点击＋创建</div>
          </div>
        </div>
        <div v-if="filteredTeams.length === 0" class="empty-tip">暂无团队，点击「+ 新团队」创建</div>
      </div>
    </div>
    </template>

    <!-- ===== 团队设计视图 ===== -->
    <template v-if="store.sidebarView === 'meta-team'">
    <!-- 搜索框 -->
    <div class="search-box">
      <el-input
        v-model="metaTaskSearchText"
        placeholder="搜索设计任务"
        size="small"
        prefix-icon="Search"
        clearable
      />
    </div>

    <!-- 新建设计任务按钮 -->
    <div class="new-conv-btn">
      <el-button type="primary" plain class="full-btn" @click="openNewMetaTaskDialog">
        + 新建设计任务
      </el-button>
    </div>

    <!-- 设计任务列表 -->
    <div class="conv-section">
      <div class="section-label" v-if="store.metaTeamStats">
        设计任务 ({{ store.metaTeamStats.total }})
      </div>
      <div class="section-label" v-else>设计任务</div>
      <div class="conv-list" v-loading="store.metaTeamLoading">
        <!-- 进行中 -->
        <template v-if="activeMetaTeamTasks.length > 0">
          <div class="task-group-label">进行中</div>
          <div
            v-for="task in activeMetaTeamTasks"
            :key="task.id"
            class="conv-item meta-task-item"
            :class="{ active: task.id === store.metaTeamTaskId }"
            @click="handleSelectMetaTask(task)"
          >
            <div class="conv-title-wrap">
              <div class="conv-title">{{ task.title }}</div>
              <div class="meta-task-meta">
                <span class="task-mode-tag">{{ task.mode === 'fast' ? '快速' : '深度' }}</span>
                <span class="task-status-tag" :class="'status-' + task.status">{{ metaTaskStatusText(task.status) }}</span>
                <span class="task-time">{{ formatTaskTime(task.updated_at) }}</span>
              </div>
            </div>
            <div class="conv-actions">
              <el-button text size="small" class="delete-btn" title="删除" @click.stop="handleDeleteMetaTask(task)">×</el-button>
            </div>
          </div>
        </template>
        <!-- 已完成 -->
        <template v-if="completedMetaTeamTasks.length > 0">
          <div class="task-group-label">已完成</div>
          <div
            v-for="task in completedMetaTeamTasks"
            :key="task.id"
            class="conv-item meta-task-item"
            :class="{ active: task.id === store.metaTeamTaskId }"
            @click="handleSelectMetaTask(task)"
          >
            <div class="conv-title-wrap">
              <div class="conv-title">{{ task.title }}</div>
              <div class="meta-task-meta">
                <span class="task-status-tag" :class="'status-' + task.status">{{ metaTaskStatusText(task.status) }}</span>
                <span class="task-time">{{ formatTaskTime(task.updated_at) }}</span>
              </div>
            </div>
            <div class="conv-actions">
              <el-button text size="small" class="delete-btn" title="删除" @click.stop="handleDeleteMetaTask(task)">×</el-button>
            </div>
          </div>
        </template>
        <div v-if="!store.metaTeamLoading && store.metaTeamTasks.length === 0" class="empty-tip">
          暂无设计任务<br>点击上方按钮创建
        </div>
      </div>
    </div>
    </template>

    <!-- 底部：设置入口（移到左下角） -->
    <div class="sidebar-footer">
      <el-button text size="small" class="footer-btn" @click="settingsVisible = true">
        <span class="settings-icon">⚙</span>
        <span>设置</span>
      </el-button>
    </div>

    <!-- 统一设置面板（模型配置 / 技能 / 蓝图） -->
    <SettingsPanel v-model="settingsVisible" />

    <!-- 智能体管理弹窗 -->
    <el-dialog v-model="agentDialogVisible" title="项目智能体管理" width="560px">
      <div class="agent-manage-header">
        <span class="agent-manage-tip" v-if="store.currentConversation">
          当前项目：{{ store.currentConversation.title }}
        </span>
        <span class="agent-manage-tip" v-else>请先选择一个项目</span>
      </div>
      <div class="agent-manage-list">
        <div v-for="agent in projectAgents" :key="agent.id" class="agent-manage-item" :class="'agent-level-' + (agent.level || (agent.id === 'main' ? 0 : 1))">
          <span class="agent-avatar">{{ agent.avatar }}</span>
          <div class="agent-info">
            <div class="agent-name">
              <span class="level-badge" :class="'level-' + (agent.level || (agent.id === 'main' ? 0 : 1))">L{{ agent.level || (agent.id === 'main' ? 0 : 1) }}</span>
              {{ agent.name }}
              <span v-if="agent.template" class="template-tag">{{ agent.template }}</span>
            </div>
            <div class="agent-role">{{ agent.role }}</div>
            <div class="agent-config">
              <el-select
                v-model="agentConfigMap[agent.id]"
                placeholder="选择模型配置"
                size="small"
                style="width: 100%; margin-top: 4px"
                @change="(val) => handleAgentConfigChange(agent, val)"
                :disabled="agent.id === 'main'"
              >
                <el-option label="使用全局配置" value="" />
                <el-option
                  v-for="cfg in configs"
                  :key="cfg.id"
                  :label="cfg.name + '（' + cfg.model + '）'"
                  :value="cfg.id"
                />
              </el-select>
            </div>
            <!-- Phase 3: 技能绑定 + 子代理开关（仅非 main 智能体） -->
            <div class="agent-extensions" v-if="agent.id !== 'main'">
              <div class="extension-row">
                <span class="extension-label">🧩 技能</span>
                <el-select
                  v-model="agentSkillsMap[agent.id]"
                  multiple
                  collapse-tags
                  collapse-tags-tooltip
                  placeholder="选择技能"
                  size="small"
                  style="flex: 1"
                  @change="(val) => handleAgentSkillsChange(agent, val)"
                >
                  <el-option
                    v-for="sk in skillsList"
                    :key="sk.id"
                    :label="sk.name + (sk.is_builtin ? ' (内置)' : '')"
                    :value="sk.id"
                  />
                </el-select>
              </div>
              <div class="extension-row">
                <span class="extension-label">🔧 子代理</span>
                <el-switch
                  v-model="agentSubAgentMap[agent.id]"
                  size="small"
                  @change="(val) => handleAgentSubAgentChange(agent, val)"
                />
                <span class="extension-hint">{{ agentSubAgentMap[agent.id] ? '可调用临时子代理' : '未开启' }}</span>
              </div>
            </div>
            <!-- 记忆与统计 -->
            <el-collapse v-model="activeMemoryCollapse" class="agent-memory-collapse">
              <el-collapse-item :name="agent.id">
                <template #title>
                  <span class="collapse-title">记忆与统计</span>
                </template>
                <div class="memory-stats-content" v-loading="loadingMemoryStats">
                  <div class="stat-row">
                    <span class="stat-label">记忆条数</span>
                    <span class="stat-value stat-blue">{{ agentMemoryMap[agent.id]?.count ?? 0 }} 条</span>
                  </div>
                  <div class="stat-row">
                    <span class="stat-label">已完成任务</span>
                    <span class="stat-value stat-blue">{{ agentStatsMap[agent.id]?.completed_tasks ?? 0 }} 个</span>
                  </div>
                  <div class="stat-row">
                    <span class="stat-label">最后活跃</span>
                    <span class="stat-value">{{ formatLastActive(agentStatsMap[agent.id]?.last_active_at) }}</span>
                  </div>
                  <div class="memory-action-row">
                    <el-button
                      text
                      size="small"
                      class="clear-memory-btn"
                      :disabled="(agentMemoryMap[agent.id]?.count ?? 0) === 0"
                      @click="handleClearMemory(agent)"
                    >清空记忆</el-button>
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>
          <el-button
            v-if="agent.id !== 'main'"
            text
            type="danger"
            size="small"
            @click="handleDeleteAgent(agent)"
          >删除</el-button>
          <span v-else class="main-badge">内置</span>
        </div>
        <div v-if="projectAgents.length === 0" class="empty-agents-tip">
          团队为空，请在主聊天框让主智能体创建成员
        </div>
      </div>
      <el-divider />
      <div class="agent-manage-footer">
        <el-button text size="small" @click="goToChatForCreate">
          💬 让主智能体创建新成员
        </el-button>
        <el-button text size="small" @click="refreshAgents">
          ↻ 刷新
        </el-button>
      </div>
    </el-dialog>

    <!-- 新建项目弹窗 -->
    <el-dialog v-model="newProjectVisible" title="新建项目" width="560px">
      <el-form label-width="100px" style="margin-top: 18px">
        <el-form-item label="所属团队">
          <el-tag type="primary" effect="light">{{ getTeamName(newProjectForm.teamId) }}</el-tag>
        </el-form-item>
        <el-form-item label="项目名称">
          <el-input v-model="newProjectForm.title" placeholder="例如：我的文档整理项目" />
        </el-form-item>
        <el-form-item label="工作目录">
          <el-input
            v-model="newProjectForm.rootPath"
            placeholder="粘贴文件夹的完整路径，如 D:\projects\my-docs"
          >
            <template #append>
              <el-button @click="pickFolder">选择</el-button>
            </template>
          </el-input>
          <div class="form-tip">
            设置工作目录后，智能体可以自主读写该目录下的文件，帮你完成实际任务。
            不设置则只能聊天，不能操作文件。
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="newProjectVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreateProject" :loading="creatingProject">
          创建项目
        </el-button>
      </template>
    </el-dialog>

    <!-- 新建团队弹窗 -->
    <el-dialog v-model="newTeamVisible" title="新建团队" width="520px">
      <el-form label-width="100px" style="margin-top: 18px">
        <el-form-item label="团队名称" required>
          <el-input v-model="newTeamForm.name" placeholder="例如：小说创作团队" />
        </el-form-item>
        <el-form-item label="工作目录">
          <el-input
            v-model="newTeamForm.rootPath"
            placeholder="可选，团队默认工作目录"
          >
            <template #append>
              <el-button @click="pickFolder">选择</el-button>
            </template>
          </el-input>
          <div class="form-tip">
            团队下的项目会继承此目录作为默认工作目录，也可在创建项目时单独指定。
          </div>
        </el-form-item>
        <el-form-item v-if="store.currentConvAgents.length > 1" label="继承配置">
          <el-switch v-model="newTeamForm.inheritFrom" :active-value="store.currentConversationId" inactive-value="" />
          <span class="switch-desc">{{ newTeamForm.inheritFrom ? '从当前项目复制智能体配置' : '使用默认智能体（仅主智能体）' }}</span>
        </el-form-item>
      </el-form>
      <div class="team-create-tip">
        💡 团队创建后，可在团队下创建多个项目，项目间共享智能体配置。通过编辑智能体可调整团队配置，变更会同步到该团队所有项目。
      </div>
      <template #footer>
        <el-button @click="newTeamVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreateTeam" :loading="creatingTeam">
          创建团队
        </el-button>
      </template>
    </el-dialog>

    <!-- 新建设计任务弹窗 -->
    <el-dialog v-model="newMetaTaskVisible" title="新建设计任务" width="520px" @open="handleNewTaskDialogOpen">
      <el-form label-position="top">
        <el-form-item label="任务标题">
          <el-input v-model="newMetaTaskForm.title" placeholder="如：科幻小说创作团队设计" />
        </el-form-item>
        <el-form-item label="需求描述">
          <el-input
            v-model="newMetaTaskForm.requirement"
            type="textarea"
            :rows="4"
            placeholder="描述你想要的团队：要做什么任务、需要什么角色、有什么特殊要求..."
          />
        </el-form-item>
        <el-form-item label="工作模式">
          <el-radio-group v-model="newMetaTaskForm.mode">
            <el-radio value="deep">深度模式（多专家并行 + 评审融合）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="参与专家">
          <el-select
            v-model="newMetaTaskForm.expert_ids"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="不选则使用全部专家"
            style="width: 100%"
          >
            <el-option
              v-for="exp in store.metaTeamExperts"
              :key="exp.id"
              :label="exp.name"
              :value="exp.id"
            />
          </el-select>
          <div class="form-hint">选择参与本次设计任务的专家，深度模式建议选 3 个</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="newMetaTaskVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreateMetaTask" :loading="creatingMetaTask">
          创建任务
        </el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useAgentStore } from '../stores/agent'
import { ElMessage, ElMessageBox } from 'element-plus'
import SettingsPanel from './SettingsPanel.vue'
import api from '../api'

const store = useAgentStore()
const searchText = ref('')
const agentDropdownOpen = ref(false)
const settingsVisible = ref(false)
// 智能体管理弹窗：绑定到 store，允许 ChatWindow 跨组件触发
const agentDialogVisible = computed({
  get: () => store.agentManageDialogVisible,
  set: (v) => { store.agentManageDialogVisible = v }
})
const configs = ref([])
const agentConfigMap = ref({})
// Phase 3: 技能绑定 + 子代理开关
const skillsList = ref([])
const agentSkillsMap = ref({})    // { agentId: [skillId, ...] }
const agentSubAgentMap = ref({})  // { agentId: boolean }
// 记忆与统计
const agentMemoryMap = ref({})    // { agentId: { count: number, log: [] } }
const agentStatsMap = ref({})     // { agentId: { completed_tasks, last_active_at, ... } }
const activeMemoryCollapse = ref([])  // el-collapse 展开状态，存储 agentId
const loadingMemoryStats = ref(false)

// 新建项目相关
const newProjectVisible = ref(false)
const creatingProject = ref(false)
const newProjectForm = ref({
  type: 'normal',  // 'normal' | 'meta'
  title: '',
  rootPath: '',
  teamId: ''  // 所属团队
})

// 新建团队相关
const newTeamVisible = ref(false)
const creatingTeam = ref(false)
const newTeamForm = ref({
  name: '',
  rootPath: '',
  inheritFrom: ''  // 可选：从当前项目继承团队
})

// 团队折叠状态
const collapsedTeams = ref({})  // { teamId: true/false }

// 元团队设计任务相关
const newMetaTaskVisible = ref(false)
const creatingMetaTask = ref(false)
const newMetaTaskForm = ref({
  title: '',
  requirement: '',
  mode: 'deep',
  expert_ids: []
})
const metaTaskSearchText = ref('')  // 设计任务搜索关键词

// 元团队任务分组（带搜索过滤）
const activeMetaTeamTasks = computed(() => {
  const kw = metaTaskSearchText.value.trim().toLowerCase()
  return store.metaTeamTasks.filter(t =>
    !['completed', 'archived'].includes(t.status) &&
    (!kw || (t.title || '').toLowerCase().includes(kw))
  )
})
const completedMetaTeamTasks = computed(() => {
  const kw = metaTaskSearchText.value.trim().toLowerCase()
  return store.metaTeamTasks.filter(t =>
    ['completed', 'archived'].includes(t.status) &&
    (!kw || (t.title || '').toLowerCase().includes(kw))
  )
})

// 元团队任务状态文字
function metaTaskStatusText(status) {
  const map = {
    drafting: '设计中',
    reviewing: '评审中',
    fusing: '融合中',
    completed: '已完成',
    archived: '已归档'
  }
  return map[status] || status
}

// 格式化任务时间
function formatTaskTime(timeStr) {
  if (!timeStr) return ''
  try {
    const d = new Date(timeStr)
    const now = new Date()
    const diff = (now - d) / 1000
    if (diff < 60) return '刚刚'
    if (diff < 3600) return Math.floor(diff / 60) + '分钟前'
    if (diff < 86400) return Math.floor(diff / 3600) + '小时前'
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  } catch {
    return ''
  }
}

// 打开新建设计任务弹窗
function openNewMetaTaskDialog() {
  newMetaTaskForm.value = { title: '', requirement: '', mode: 'deep', expert_ids: [] }
  newMetaTaskVisible.value = true
}

// 弹窗打开时加载专家列表
function handleNewTaskDialogOpen() {
  store.loadMetaTeamExperts()
}

// 创建设计任务
async function handleCreateMetaTask() {
  if (!newMetaTaskForm.value.title.trim()) {
    ElMessage.warning('请输入任务标题')
    return
  }
  if (!newMetaTaskForm.value.requirement.trim()) {
    ElMessage.warning('请输入需求描述')
    return
  }
  creatingMetaTask.value = true
  try {
    const task = await store.createMetaTeamTask({
      title: newMetaTaskForm.value.title,
      requirement: newMetaTaskForm.value.requirement,
      mode: newMetaTaskForm.value.mode,
      expert_ids: newMetaTaskForm.value.expert_ids.length > 0 ? newMetaTaskForm.value.expert_ids : null
    })
    ElMessage.success('设计任务已创建')
    newMetaTaskVisible.value = false
    store.selectMetaTeamTask(task.id)
  } catch (e) {
    ElMessage.error('创建失败：' + (e.response?.data?.detail || e.message))
  } finally {
    creatingMetaTask.value = false
  }
}

// 选中设计任务
function handleSelectMetaTask(task) {
  store.selectMetaTeamTask(task.id)
}

// 删除设计任务
async function handleDeleteMetaTask(task) {
  try {
    await ElMessageBox.confirm(`确定删除设计任务「${task.title}」？`, '提示', { type: 'warning' })
    await store.deleteMetaTeamTask(task.id)
    ElMessage.success('已删除')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

// 重命名相关
const editingConvId = ref('')
const editingTitle = ref('')
const renameInputRef = ref(null)

// 加载配置列表
async function loadConfigs() {
  try {
    const res = await api.getModelConfigs()
    configs.value = res.data.configs || []
  } catch (e) {}
}

// 加载技能列表（用于智能体管理弹窗的技能下拉）
async function loadSkills() {
  try {
    const res = await api.getSkills()
    skillsList.value = res.data.skills || []
  } catch (e) {
    skillsList.value = []
  }
}

// 初始化智能体扩展属性映射（技能 + 子代理开关）
function initExtensionMaps() {
  const skMap = {}
  const subMap = {}
  projectAgents.value.forEach(a => {
    skMap[a.id] = Array.isArray(a.enabled_skills) ? [...a.enabled_skills] : []
    subMap[a.id] = !!a.can_invoke_sub_agent
  })
  agentSkillsMap.value = skMap
  agentSubAgentMap.value = subMap
}

// 加载所有智能体的记忆和统计
async function loadAgentMemoryAndStats() {
  const convId = store.currentConversationId
  if (!convId) return
  loadingMemoryStats.value = true
  try {
    // 先获取整体统计（一次请求拿到所有智能体的统计）
    const statsRes = await api.getAgentStats(convId)
    const agentsStats = statsRes.data.agents_stats || []
    const statsMap = {}
    agentsStats.forEach(s => {
      statsMap[s.agent_id] = s
    })
    agentStatsMap.value = statsMap
    // 再逐个获取记忆条数（并行请求）
    const memPromises = projectAgents.value.map(async a => {
      try {
        const memRes = await api.getAgentMemory(convId, a.id)
        const log = memRes.data.memory_log || []
        return { agentId: a.id, count: log.length, log }
      } catch {
        return { agentId: a.id, count: 0, log: [] }
      }
    })
    const memResults = await Promise.all(memPromises)
    const memMap = {}
    memResults.forEach(m => {
      memMap[m.agentId] = { count: m.count, log: m.log }
    })
    agentMemoryMap.value = memMap
  } catch {
    // 静默失败，不影响弹窗正常使用
  } finally {
    loadingMemoryStats.value = false
  }
}

// 清空指定智能体的记忆
async function handleClearMemory(agent) {
  const convId = store.currentConversationId
  if (!convId) return
  try {
    await ElMessageBox.confirm(
      `确定清空「${agent.name}」的记忆吗？清空后该智能体将不再记住之前的交互内容。`,
      '清空记忆',
      { type: 'warning', confirmButtonText: '确定清空', cancelButtonText: '取消' }
    )
    await api.clearAgentMemory(convId, agent.id)
    ElMessage.success(`${agent.name} 的记忆已清空`)
    // 刷新该智能体的记忆数据
    try {
      const memRes = await api.getAgentMemory(convId, agent.id)
      const log = memRes.data.memory_log || []
      agentMemoryMap.value = {
        ...agentMemoryMap.value,
        [agent.id]: { count: log.length, log }
      }
    } catch {
      agentMemoryMap.value = {
        ...agentMemoryMap.value,
        [agent.id]: { count: 0, log: [] }
      }
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('清空记忆失败：' + (e.response?.data?.detail || e.message))
    }
  }
}

// 格式化最后活跃时间
function formatLastActive(timeStr) {
  if (!timeStr) return '暂无'
  try {
    const d = new Date(timeStr)
    const now = new Date()
    const diff = (now - d) / 1000
    if (diff < 60) return '刚刚'
    if (diff < 3600) return Math.floor(diff / 60) + '分钟前'
    if (diff < 86400) return Math.floor(diff / 3600) + '小时前'
    return d.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch {
    return timeStr
  }
}

// 项目级智能体列表（实时读取当前项目的智能体）
const projectAgents = computed(() => {
  if (store.currentConvAgents && store.currentConvAgents.length > 0) {
    return store.currentConvAgents
  }
  // 没有项目级智能体时，回退到全局模板（至少能显示 main）
  return store.agents
})

// 监听弹窗打开，加载配置和项目级智能体
watch(agentDialogVisible, async (val) => {
  if (val) {
    await Promise.all([loadConfigs(), loadSkills()])
    // 重新加载当前项目的智能体列表（确保看到最新状态）
    if (store.currentConversationId) {
      await store.loadConversationAgents()
    }
    // 初始化每个智能体的配置选择
    const map = {}
    projectAgents.value.forEach(a => {
      map[a.id] = a.model_config?.config_id || ''
    })
    agentConfigMap.value = map
    // 初始化技能 + 子代理开关映射
    initExtensionMaps()
    // 加载记忆与统计
    loadAgentMemoryAndStats()
  }
})

// 刷新项目级智能体列表
async function refreshAgents() {
  if (store.currentConversationId) {
    await store.loadConversationAgents()
    // 重新初始化配置映射
    const map = {}
    projectAgents.value.forEach(a => {
      map[a.id] = a.model_config?.config_id || ''
    })
    agentConfigMap.value = map
    initExtensionMaps()
    // 刷新记忆与统计
    loadAgentMemoryAndStats()
    ElMessage.success('已刷新')
  }
}

// 跳到主聊天框让主智能体创建新成员
function goToChatForCreate() {
  agentDialogVisible.value = false
  ElMessage.info('请在主聊天框对主智能体说：「创建一个新成员：角色=翻译员，职责=...」')
}

async function handleAgentConfigChange(agent, cfgId) {
  if (!store.currentConversationId) {
    ElMessage.warning('请先选择一个项目')
    return
  }
  const payload = {
    name: agent.name,
    role: agent.role,
    avatar: agent.avatar,
    system_prompt: agent.system_prompt || '',
    allowed_paths: agent.allowed_paths || ['*'],
  }
  if (!cfgId) {
    // 使用全局配置，清除 model_config
    payload.model_cfg = {}
  } else {
    const cfg = configs.value.find(c => c.id === cfgId)
    if (!cfg) return
    // 只传 config_id，后端通过 config_id 从 configs.json 取真实配置
    payload.model_cfg = { config_id: cfg.id }
  }
  try {
    // 走项目级 API：PUT /api/conversations/{convId}/agents/{agentId}
    await api.updateConversationAgent(store.currentConversationId, agent.id, payload)
    // 更新本地 store
    await store.loadConversationAgents()
    ElMessage.success(`${agent.name} 模型配置已更新`)
  } catch (e) {
    ElMessage.error('更新失败：' + (e.response?.data?.detail || e.message))
  }
}

// Phase 3: 技能绑定变更
async function handleAgentSkillsChange(agent, skillIds) {
  if (!store.currentConversationId) {
    ElMessage.warning('请先选择一个项目')
    return
  }
  const payload = {
    name: agent.name,
    role: agent.role,
    avatar: agent.avatar,
    system_prompt: agent.system_prompt || '',
    allowed_paths: agent.allowed_paths || ['*'],
    enabled_skills: skillIds,
  }
  try {
    await api.updateConversationAgent(store.currentConversationId, agent.id, payload)
    await store.loadConversationAgents()
    const names = (skillIds || []).map(id => {
      const sk = skillsList.value.find(s => s.id === id)
      return sk ? sk.name : id
    })
    ElMessage.success(`${agent.name} 技能已更新：${names.length ? names.join('、') : '无'}`)
  } catch (e) {
    ElMessage.error('更新技能失败：' + (e.response?.data?.detail || e.message))
    // 回滚 UI 状态
    await store.loadConversationAgents()
    initExtensionMaps()
  }
}

// Phase 3: 子代理开关变更
async function handleAgentSubAgentChange(agent, enabled) {
  if (!store.currentConversationId) {
    ElMessage.warning('请先选择一个项目')
    return
  }
  const payload = {
    name: agent.name,
    role: agent.role,
    avatar: agent.avatar,
    system_prompt: agent.system_prompt || '',
    allowed_paths: agent.allowed_paths || ['*'],
    can_invoke_sub_agent: !!enabled,
  }
  try {
    await api.updateConversationAgent(store.currentConversationId, agent.id, payload)
    await store.loadConversationAgents()
    ElMessage.success(`${agent.name} 子代理调用已${enabled ? '开启' : '关闭'}`)
  } catch (e) {
    ElMessage.error('更新子代理开关失败：' + (e.response?.data?.detail || e.message))
    // 回滚 UI 状态
    await store.loadConversationAgents()
    initExtensionMaps()
  }
}

const filteredConversations = computed(() => {
  if (!searchText.value) return store.conversations
  const kw = searchText.value.toLowerCase()
  return store.conversations.filter(c => c.title.toLowerCase().includes(kw))
})

// 团队列表（带搜索过滤）
const filteredTeams = computed(() => {
  if (!searchText.value) return store.teams
  const kw = searchText.value.toLowerCase()
  return store.teams.map(t => ({
    ...t,
    projects: (t.projects || []).filter(p => p.title.toLowerCase().includes(kw) || t.name.toLowerCase().includes(kw))
  })).filter(t => t.projects.length > 0 || t.name.toLowerCase().includes(kw))
})

// 切换团队折叠
function toggleTeamCollapse(teamId) {
  collapsedTeams.value[teamId] = !collapsedTeams.value[teamId]
}

// 打开新建团队弹窗
function openNewTeamDialog() {
  newTeamForm.value = { name: '', rootPath: '', inheritFrom: '' }
  newTeamVisible.value = true
}

// 在指定团队下新建项目
function openNewProjectInTeam(team) {
  newProjectForm.value = { type: 'normal', title: '', rootPath: team.root_path || '', teamId: team.id }
  newProjectVisible.value = true
}

// 通过 teamId 新建项目（供 App.vue 调用）
function openNewProjectInTeamById(teamId) {
  const team = store.teams.find(t => t.id === teamId)
  openNewProjectInTeam(team || { id: teamId, root_path: '' })
}

// 点击团队进入团队主页
function handleSelectTeam(team) {
  store.selectTeam(team.id)
}

// 创建团队
async function handleCreateTeam() {
  if (!newTeamForm.value.name.trim()) {
    ElMessage.warning('请输入团队名称')
    return
  }
  creatingTeam.value = true
  try {
    await store.createTeam(newTeamForm.value.name.trim(), newTeamForm.value.rootPath.trim(), newTeamForm.value.inheritFrom)
    newTeamVisible.value = false
    ElMessage.success('团队已创建')
  } catch (e) {
    ElMessage.error('创建失败：' + (e.message || '未知错误'))
  } finally {
    creatingTeam.value = false
  }
}

// 删除团队
async function handleDeleteTeam(team) {
  try {
    const action = await ElMessageBox.confirm(
      `确定要删除团队「${team.name}」吗？该团队下的 ${team.projects?.length || 0} 个项目也会被删除。`,
      '删除团队',
      { confirmButtonText: '删除团队和项目', cancelButtonText: '取消', type: 'warning' }
    )
    await store.deleteTeam(team.id, true)
    ElMessage.success('团队已删除')
  } catch (e) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error('删除失败：' + (e.message || '未知错误'))
    }
  }
}

function handleSelectAgent(id) {
  // 合并管理入口：选择 'manage' 时打开智能体管理弹窗
  if (id === 'manage') {
    agentDialogVisible.value = true
    return
  }
  store.selectAgent(id)
}

function handleSelectConv(conv) {
  if (editingConvId.value === conv.id) return
  store.exitTeamHome()  // 退出团队主页，确保切回 ChatWindow
  store.selectConversation(conv.id)
}

function openNewProjectDialog() {
  newProjectForm.value = { type: 'normal', title: '', rootPath: '', teamId: '', inheritTeam: false }
  newProjectVisible.value = true
}

async function pickFolder() {
  // 浏览器安全限制下无法直接选择文件夹，提示用户手动粘贴路径
  // 未来桌面端（Electron/Tauri）可替换为原生文件夹选择器
  ElMessage.info('请直接在输入框中粘贴文件夹的完整路径，例如：D:\\projects\\my-docs')
}

async function handleCreateProject() {
  creatingProject.value = true
  try {
    const rootPath = newProjectForm.value.rootPath.trim()
    const title = newProjectForm.value.title.trim()

    // 创建普通项目（元团队已重构为常驻功能模块，通过侧边栏「团队设计」入口使用）
    const inheritFrom = newProjectForm.value.inheritTeam ? store.currentConversationId : ''
    const teamId = newProjectForm.value.teamId || ''
    await store.createConversation(rootPath, inheritFrom, teamId)
    if (title) {
      await store.renameConversation(store.currentConversationId, title)
    }
    newProjectVisible.value = false
    ElMessage.success('项目已创建')
  } catch (e) {
    ElMessage.error('创建失败：' + (e.message || '未知错误'))
  } finally {
    creatingProject.value = false
  }
}

// 格式化路径显示：只显示最后两级
function formatPath(fullPath) {
  if (!fullPath) return ''
  const parts = fullPath.split(/[/\\]/).filter(Boolean)
  if (parts.length <= 2) return fullPath
  return '.../' + parts.slice(-2).join('/')
}

// 获取团队名称
function getTeamName(teamId) {
  const team = store.teams.find(t => t.id === teamId)
  return team ? team.name : '未指定团队'
}

function startRename(conv) {
  editingConvId.value = conv.id
  editingTitle.value = conv.title
  nextTick(() => {
    if (renameInputRef.value) {
      // 聚焦输入框
      const inputs = document.querySelectorAll('.conv-item input')
      inputs.forEach(input => input.focus())
    }
  })
}

async function handleSaveRename(conv) {
  if (editingConvId.value !== conv.id) return
  const newTitle = editingTitle.value.trim()
  editingConvId.value = ''
  if (newTitle && newTitle !== conv.title) {
    await store.renameConversation(conv.id, newTitle)
    ElMessage.success('已重命名')
  }
}

async function handleDelete(conv) {
  try {
    await ElMessageBox.confirm(
      `确定要删除对话「${conv.title}」吗？`,
      '删除对话',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
    // 如果项目设置了工作目录，追问是否同时删除项目文件（含隐藏的 .agent 文件夹）
    let deleteFiles = false
    if (conv.root_path) {
      try {
        await ElMessageBox.confirm(
          `是否同时删除项目目录下的标准结构文件？\n\n将删除：.agent/、agent_work/、shared/、deliverables/\n（你自己的其他文件不会动）\n\n建议：如果之后还要用这个目录，选「取消」改用「🔄重置结构」更合适。`,
          '是否清理项目文件',
          { type: 'warning', confirmButtonText: '同时删除文件', cancelButtonText: '仅删除对话记录' }
        )
        deleteFiles = true
      } catch (e) {
        // 用户选了「仅删除对话记录」
        deleteFiles = false
      }
    }
    await store.deleteConversation(conv.id, deleteFiles)
    ElMessage.success(deleteFiles ? '已删除对话和项目文件' : '已删除')
  } catch (e) {}
}

async function handleResetStructure(conv) {
  try {
    await ElMessageBox.confirm(
      `将重置「${conv.title}」的项目目录结构：\n\n1. 清理 .agent/ 下的所有旧任务\n2. 重建标准目录（shared/、agent_work/、deliverables/）\n3. 重建助手工作区并恢复权限\n\n你自己的其他文件不受影响。确定继续？`,
      '重置项目结构',
      { type: 'warning', confirmButtonText: '确定重置', cancelButtonText: '取消' }
    )
    const data = await store.resetConversationStructure(conv.id)
    ElMessage.success(data.message || '项目结构已重置')
  } catch (e) {
    if (e.response?.data?.detail) {
      ElMessage.error('重置失败：' + e.response.data.detail)
    }
  }
}

async function handleDeleteAgent(agent) {
  try {
    await ElMessageBox.confirm(
      `确定要移除智能体「${agent.name}」吗？\n\n注意：已产出的文件会保留。建议在主聊天框让主智能体用 remove_team_member 工具移除，这样主智能体能同步更新团队状态。`,
      '确认移除',
      { type: 'warning', confirmButtonText: '我知道了', cancelButtonText: '取消' }
    )
    agentDialogVisible.value = false
    ElMessage.info('请在主聊天框对主智能体说：「请移除成员 ' + agent.name + '」')
  } catch (e) {}
}

function openSettings() {
  settingsVisible.value = true
}

defineExpose({ openSettings, openNewProjectInTeamById, openNewProjectDialog })
</script>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-sidebar);
}

/* 顶部栏 */
.sidebar-header {
  padding: var(--space-lg);
  background: var(--primary-gradient);
  position: relative;
  overflow: hidden;
}

.sidebar-header::before {
  content: '';
  position: absolute;
  top: -50%;
  right: -30%;
  width: 200px;
  height: 200px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 50%;
}

.sidebar-header::after {
  content: '';
  position: absolute;
  bottom: -30%;
  left: -20%;
  width: 150px;
  height: 150px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 50%;
}

.app-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  position: relative;
  z-index: 1;
}

.brand-logo {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
}

.brand-logo svg {
  width: 100%;
  height: 100%;
}

.brand-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.brand-name {
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  letter-spacing: 0.5px;
}

.brand-sub {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.6);
  letter-spacing: 1px;
  text-transform: uppercase;
}

.search-box {
  padding: var(--space-md) var(--space-lg);
}

.search-box :deep(.el-input__wrapper) {
  border-radius: var(--radius-lg);
  box-shadow: 0 0 0 1px var(--border-color) inset;
  transition: all var(--transition-fast);
}

.search-box :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px var(--primary-light) inset;
}

.search-box :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--primary) inset, 0 0 0 4px rgba(99, 102, 241, 0.1);
}

/* 设置按钮样式（已移至左下角 footer） */
.settings-icon {
  font-size: 14px;
  flex-shrink: 0;
  margin-right: 4px;
}

.new-conv-btn {
  padding: 0 var(--space-lg) var(--space-md);
}

.full-btn {
  width: 100%;
}

.new-conv-btn :deep(.el-button) {
  border-radius: var(--radius-lg);
  height: 40px;
  font-weight: 600;
  background: var(--primary-gradient);
  border: none;
  color: #fff;
  transition: all var(--transition-normal);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.new-conv-btn :deep(.el-button:hover) {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4);
  background: var(--primary-gradient);
  color: #fff;
}

.new-conv-btn :deep(.el-button:active) {
  transform: translateY(0);
}

.form-hint {
  font-size: 12px;
  color: var(--text-tertiary, #94a3b8);
  margin-top: 4px;
  line-height: 1.4;
}

.conv-section {
  flex: 1;
  overflow-y: auto;
  padding: 0 var(--space-md);
}

.section-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-tertiary);
  margin-bottom: 8px;
  padding: 0 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.conv-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.conv-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  gap: 8px;
  position: relative;
}

.conv-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 0;
  background: var(--primary);
  border-radius: 0 2px 2px 0;
  transition: height var(--transition-fast);
}

.conv-item:hover {
  background: var(--bg-hover);
}

.conv-item:hover .delete-btn,
.conv-item:hover .action-btn {
  opacity: 1;
}

.conv-item.active {
  background: var(--bg-active);
}

.conv-item.active::before {
  height: 20px;
}

.conv-item.active .conv-title {
  color: var(--primary-dark);
  font-weight: 600;
}

.conv-title {
  font-size: 14px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color var(--transition-fast);
}

.conv-title-wrap {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.running-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  flex-shrink: 0;
  animation: pulse-dot 1.2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.75); }
}

.conv-path {
  font-size: 11px;
  color: var(--text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
}

.conv-item.active .conv-path {
  color: var(--primary);
}

.form-tip {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 4px;
  line-height: 1.5;
}

.form-tip code {
  background: rgba(99, 102, 241, 0.1);
  color: #4f46e5;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 11px;
  font-family: 'Consolas', 'Monaco', monospace;
}

.switch-desc {
  margin-left: 10px;
  font-size: 12px;
  color: var(--text-tertiary);
}

.team-create-tip {
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 8px;
  padding: 10px 14px;
  margin-top: 12px;
  font-size: 12px;
  color: #475569;
  line-height: 1.6;
}

/* 团队树结构 */
.team-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.team-group {
  border-radius: 10px;
  overflow: hidden;
  background: #e0e7ff;
  border: 1px solid #a5b4fc;
  box-shadow: 0 1px 3px rgba(99, 102, 241, 0.1);
}

.team-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 12px;
  cursor: pointer;
  border-radius: 10px;
  transition: all 0.2s;
  position: relative;
  user-select: none;
  border-left: 3px solid #6366f1;
}

.team-header:hover {
  background: #c7d2fe;
}

.team-arrow {
  font-size: 12px;
  color: #6366f1;
  transition: transform 0.2s;
  flex-shrink: 0;
  width: 14px;
  text-align: center;
  cursor: pointer;
  font-weight: bold;
}

.team-arrow.collapsed {
  transform: rotate(-90deg);
}

.team-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.team-name {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.team-count {
  font-size: 11px;
  color: #ffffff;
  background: #6366f1;
  border-radius: 10px;
  padding: 1px 8px;
  min-width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-weight: 600;
}

.team-actions {
  display: flex;
  gap: 4px;
  margin-left: 4px;
}

.team-header:hover .team-actions {
  display: flex;
}

.team-actions .team-action-btn {
  padding: 2px 6px;
  font-size: 15px;
  min-height: auto;
  color: #6366f1;
  border: none;
  border-radius: 6px;
  background: transparent;
  line-height: 1.4;
  cursor: pointer;
  transition: all 0.2s;
}

.team-actions .team-action-btn:hover {
  background: rgba(99, 102, 241, 0.15);
  color: #4f46e5;
}

.team-actions .team-delete-btn {
  color: #9ca3af;
}

.team-actions .team-delete-btn:hover {
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}

.team-projects {
  padding: 4px 12px 8px 34px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.team-projects .conv-item {
  padding: 8px 10px;
  border-radius: 8px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
}

.team-projects .conv-item:hover {
  background: #f8fafc;
}

.team-projects .conv-item.active {
  background: #eef2ff;
  border-color: #6366f1;
}

.empty-tip-small {
  font-size: 12px;
  color: #64748b;
  padding: 8px 10px;
  font-style: italic;
}

/* 项目类型选择 */
.project-type-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.type-tab {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px;
  border-radius: 10px;
  border: 2px solid #e2e8f0;
  background: #f8fafc;
  cursor: pointer;
  transition: all 0.25s ease;
  position: relative;
  overflow: hidden;
}

.type-tab::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 0;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.08) 0%, rgba(118, 75, 162, 0.08) 100%);
  transition: height 0.25s ease;
}

.type-tab:hover {
  border-color: #c7d2fe;
  transform: translateY(-1px);
}

.type-tab.active {
  border-color: #6366f1;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.06) 0%, rgba(118, 75, 162, 0.06) 100%);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.15);
}

.type-tab.active::before {
  height: 100%;
}

.type-icon {
  font-size: 24px;
  flex-shrink: 0;
  position: relative;
  z-index: 1;
}

.type-info {
  position: relative;
  z-index: 1;
  flex: 1;
  min-width: 0;
}

.type-name {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 3px;
}

.type-desc {
  font-size: 11px;
  color: #64748b;
  line-height: 1.4;
}

/* 元团队说明卡片 */
.meta-team-info {
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
  border: 1px solid #e0e7ff;
}

.info-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px dashed #c7d2fe;
}

.info-icon {
  font-size: 16px;
}

.info-title {
  font-size: 13px;
  font-weight: 600;
  color: #4f46e5;
}

.info-steps {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.info-step {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: #475569;
  padding: 4px 0;
}

.step-num {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #fff;
  border: 1.5px solid #6366f1;
  color: #6366f1;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.info-step.final {
  color: #059669;
  font-weight: 600;
  margin-top: 4px;
  padding-top: 8px;
  border-top: 1px dashed #c7d2fe;
}

.info-step.final .step-num {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  border-color: #059669;
  color: #fff;
}

.conv-actions {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}

.action-btn,
.delete-btn {
  opacity: 0;
  font-size: 14px;
  color: var(--text-tertiary);
  padding: 0 4px;
  transition: all var(--transition-fast);
}

.action-btn:hover {
  color: var(--primary);
}

.delete-btn:hover {
  color: #ef4444;
}

.empty-tip {
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  padding: 30px 0;
}

/* ===== 视图切换标签栏 ===== */
.view-tabs {
  display: flex;
  gap: 4px;
  padding: 0 var(--space-md);
  margin-top: 8px;
}
.view-tab {
  flex: 1;
  text-align: center;
  padding: 6px 8px;
  font-size: 13px;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
  user-select: none;
}
.view-tab:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
.view-tab.active {
  background: var(--bg-active);
  color: var(--primary-color);
  font-weight: 600;
}

/* ===== 元团队任务列表 ===== */
.meta-task-item {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
}
.meta-task-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  font-size: 11px;
}
.task-mode-tag {
  background: var(--bg-tag);
  color: var(--text-secondary);
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
}
.task-status-tag {
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 500;
}
.task-status-tag.status-drafting { background: #e0e7ff; color: #4338ca; }
.task-status-tag.status-reviewing { background: #fef3c7; color: #92400e; }
.task-status-tag.status-fusing { background: #f3e8ff; color: #6b21a8; }
.task-status-tag.status-completed { background: #d1fae5; color: #065f46; }
.task-status-tag.status-archived { background: #e5e7eb; color: #4b5563; }
.task-time {
  color: var(--text-muted);
  font-size: 10px;
}
.task-group-label {
  font-size: 11px;
  color: var(--text-muted);
  padding: 8px 4px 4px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.meta-team-experts-entry {
  padding: 0 var(--space-md) var(--space-sm);
}

.sidebar-footer {
  padding: var(--space-md);
  border-top: 1px solid var(--border-light);
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: var(--bg-card);
}

.footer-btn {
  width: 100%;
  text-align: left;
  justify-content: flex-start;
  color: var(--text-secondary);
  border-radius: var(--radius-md) !important;
  padding: 10px 12px !important;
  transition: all var(--transition-fast) !important;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.footer-btn:hover {
  background: var(--bg-hover) !important;
  color: var(--primary) !important;
}

.agent-manage-header {
  margin-bottom: 12px;
  padding: 8px 12px;
  background: #f1f5f9;
  border-radius: 6px;
}

.agent-manage-tip {
  font-size: 12px;
  color: #64748b;
}

.agent-manage-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}

.empty-agents-tip {
  padding: 24px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
  background: #f8fafc;
  border: 1px dashed #e2e8f0;
  border-radius: 8px;
}

.main-badge {
  font-size: 11px;
  color: #94a3b8;
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 4px;
}

.agent-manage-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.agent-manage-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border-radius: var(--radius-md);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  transition: all var(--transition-fast);
}

/* 阶段4：L2 执行者缩进显示层级关系 */
.agent-manage-item.agent-level-2 {
  margin-left: 28px;
  border-left: 3px solid #a78bfa;
}

.agent-manage-item:hover {
  border-color: var(--primary-light);
  box-shadow: var(--shadow-sm);
}

/* 层级徽章 */
.level-badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  margin-right: 6px;
  vertical-align: middle;
}
.level-badge.level-0 {
  background: #dbeafe;
  color: #1e40af;
}
.level-badge.level-1 {
  background: #d1fae5;
  color: #065f46;
}
.level-badge.level-2 {
  background: #ede9fe;
  color: #5b21b6;
}
.template-tag {
  display: inline-block;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 10px;
  background: var(--bg-hover);
  color: var(--text-secondary);
  margin-left: 4px;
  vertical-align: middle;
}

.agent-manage-item .agent-avatar {
  font-size: 28px;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-hover);
  border-radius: var(--radius-md);
}

.agent-manage-item .agent-info {
  flex: 1;
  min-width: 0;
}

.agent-manage-item .agent-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.agent-manage-item .agent-role {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 2px;
}

/* Phase 3: 技能 + 子代理扩展区 */
.agent-extensions {
  margin-top: 8px;
  padding: 8px 10px;
  background: var(--bg-secondary, rgba(0,0,0,0.03));
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.agent-extensions .extension-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.agent-extensions .extension-label {
  font-size: 12px;
  color: var(--text-tertiary);
  min-width: 48px;
  flex-shrink: 0;
}

.agent-extensions .extension-hint {
  font-size: 11px;
  color: var(--text-tertiary);
}

/* ===== 记忆与统计折叠区 ===== */
.agent-memory-collapse {
  margin-top: 8px;
  border: none;
}

.agent-memory-collapse :deep(.el-collapse-item__header) {
  height: 32px;
  line-height: 32px;
  font-size: 12px;
  color: var(--text-tertiary);
  background: #f1f5f9;
  border-radius: 6px;
  padding: 0 10px;
  border: none;
}

.agent-memory-collapse :deep(.el-collapse-item__header:hover) {
  background: #e2e8f0;
}

.agent-memory-collapse :deep(.el-collapse-item__wrap) {
  border: none;
}

.agent-memory-collapse :deep(.el-collapse-item__content) {
  padding: 8px 0 0;
}

.collapse-title {
  font-size: 12px;
  font-weight: 500;
  color: #475569;
}

.memory-stats-content {
  background: #f8fafc;
  border-radius: 6px;
  padding: 8px 10px;
}

.stat-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 3px 0;
  font-size: 12px;
}

.stat-label {
  color: var(--text-tertiary);
}

.stat-value {
  color: var(--text-secondary);
  font-weight: 500;
}

.stat-blue {
  color: #2563eb;
  font-weight: 600;
}

.memory-action-row {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed #e2e8f0;
  display: flex;
  justify-content: flex-end;
}

.clear-memory-btn {
  color: #ef4444 !important;
  font-size: 12px;
  padding: 2px 6px !important;
}

.clear-memory-btn:hover {
  color: #dc2626 !important;
  background: rgba(239, 68, 68, 0.08) !important;
}

.clear-memory-btn.is-disabled {
  color: #cbd5e1 !important;
}

/* 弹窗整体美化 */
:deep(.el-dialog) {
  border-radius: var(--radius-lg) !important;
  overflow: hidden;
}

:deep(.el-dialog__header) {
  padding: 20px 24px 16px !important;
  border-bottom: 1px solid var(--border-light);
  margin-right: 0 !important;
}

:deep(.el-dialog__title) {
  font-size: 17px !important;
  font-weight: 600 !important;
  color: var(--text-primary) !important;
}

:deep(.el-dialog__body) {
  padding: 20px 24px !important;
}

:deep(.el-dialog__footer) {
  padding: 16px 24px 20px !important;
  border-top: 1px solid var(--border-light);
}

:deep(.el-button--primary) {
  background: var(--primary-gradient);
  border: none;
  border-radius: var(--radius-md);
  font-weight: 500;
  transition: all var(--transition-normal);
}

:deep(.el-button--primary:hover) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

:deep(.el-button) {
  border-radius: var(--radius-md);
}

:deep(.el-input__wrapper) {
  border-radius: var(--radius-md);
}

:deep(.el-textarea__inner) {
  border-radius: var(--radius-md);
}
</style>
