<template>
  <div class="meta-team-task">
    <!-- 顶部栏：标题 + 状态标签 + 工作模式标签 + 返回按钮 + 确认产出按钮 -->
    <div class="task-topbar">
      <div class="topbar-left">
        <el-button text class="back-btn" @click="goBack">← 返回列表</el-button>
        <div class="task-title" :title="task ? task.title : ''">
          {{ task ? task.title : '加载中…' }}
        </div>
        <el-tag v-if="task" :type="statusTagType" size="small" effect="light">{{ statusLabel }}</el-tag>
        <el-tag v-if="task" type="info" size="small" effect="plain">{{ modeLabel }}</el-tag>
      </div>
      <div class="topbar-right">
        <!-- 深度模式：阶段控制按钮 -->
        <template v-if="task && task.mode === 'deep' && !phaseLoading">
          <!-- 一键全流程按钮（仅在初始状态显示） -->
          <el-button
            v-if="task.status === 'drafting' && proposalCount === 0"
            type="success"
            size="small"
            @click="handleRunAll"
          >
            🚀 一键全流程
          </el-button>
          <el-button
            v-if="task.status === 'drafting' && proposalCount === 0"
            type="primary"
            size="small"
            @click="handleRunProposals"
          >
            启动方案撰写
          </el-button>
          <el-button
            v-if="proposalCount > 0 && reviewCount === 0 && task.status !== 'completed'"
            type="primary"
            size="small"
            @click="handleRunReviews"
          >
            启动评审
          </el-button>
          <el-button
            v-if="reviewCount > 0 && task.status !== 'completed' && !task.has_fusion_decision"
            type="primary"
            size="small"
            @click="handleRunFusion"
          >
            启动融合
          </el-button>
        </template>
        <!-- 阶段进行中的加载指示 -->
        <el-tag v-if="phaseLoading" type="warning" size="small" effect="light">
          {{ phaseLoadingText }}
        </el-tag>
        <!-- 确认产出蓝图 -->
        <el-button
          v-if="task && task.status === 'completed'"
          type="primary"
          size="small"
          @click="handleFinalize"
        >
          确认产出蓝图
        </el-button>
      </div>
    </div>

    <!-- 专家胶囊栏：展示参与本任务的专家，点击切换对话对象 -->
    <div class="expert-team-bar" v-if="task && taskExperts.length > 0">
      <div class="bar-label">设计专家</div>
      <div class="expert-chips">
        <div
          v-for="exp in taskExperts"
          :key="exp.id"
          class="expert-chip"
          :class="{ active: selectedExpertId === exp.id }"
          @click="selectedExpertId = exp.id"
          :title="`点击切换到 ${exp.name} 对话`"
        >
          <span class="chip-avatar">{{ getExpertAvatar(exp.id) }}</span>
          <span class="chip-name">{{ exp.name }}</span>
          <span v-if="exp.prompt_version" class="chip-ver">v{{ exp.prompt_version }}</span>
        </div>
      </div>
    </div>

    <!-- 主体：对话区 + 产出文件面板 -->
    <div class="task-main" :class="{ 'panel-collapsed': !panelOpen }">
      <!-- 对话区 -->
      <div class="chat-area">
        <!-- 消息列表 -->
        <div class="msg-list" ref="msgListRef">
          <!-- 空状态提示 -->
          <div v-if="messages.length === 0 && !loading" class="empty-tip">
            <div class="empty-icon">💬</div>
            <div class="empty-text">还没有对话</div>
            <div class="empty-sub">在下方输入你的需求，与专家一起设计团队方案</div>
          </div>

          <!-- 消息条目（用户消息靠右、专家回复靠左、系统消息居中） -->
          <div
            v-for="(msg, i) in messages"
            :key="i"
            class="msg-row"
            :class="msg.role === 'user' ? 'msg-user' : (msg.role === 'system' ? 'msg-system-row' : 'msg-expert')"
          >
            <!-- 系统消息：居中展示阶段进度 -->
            <div v-if="msg.role === 'system'" class="msg-system">
              <span class="system-icon">{{ msg.icon || '📋' }}</span>
              <span class="system-text markdown-body" v-html="renderMarkdown(msg.content || '')"></span>
            </div>
            <!-- 普通消息：带头像 -->
            <template v-else>
              <div class="msg-avatar">{{ getMsgAvatar(msg) }}</div>
              <div class="msg-body">
                <div class="msg-meta">
                  <span class="msg-name">{{ getMsgName(msg) }}</span>
                  <span v-if="msg.streaming" class="streaming-tip">正在输入…</span>
                </div>
                <div class="msg-bubble markdown-body" v-html="renderMarkdown(msg.content || '')"></div>
              </div>
            </template>
          </div>
        </div>

        <!-- 输入区 -->
        <div class="input-area">
          <!-- 专家选择行 -->
          <div class="expert-row">
            <span class="expert-label">对话专家</span>
            <el-select
              v-model="selectedExpertId"
              size="small"
              :disabled="loading || taskExperts.length === 0"
              placeholder="选择专家"
              class="expert-select"
            >
              <el-option
                v-for="exp in taskExperts"
                :key="exp.id"
                :label="exp.name"
                :value="exp.id"
              />
            </el-select>
            <span v-if="task" class="requirement-hint" :title="task.requirement">
              需求：{{ truncate(task.requirement, 40) }}
            </span>
          </div>

          <!-- 输入框 + 发送按钮 -->
          <div class="input-row">
            <el-input
              v-model="inputText"
              type="textarea"
              :rows="3"
              :disabled="loading"
              placeholder="输入你的想法或需求…（Ctrl+Enter 发送）"
              resize="none"
              class="input-box"
              @keydown.ctrl.enter.prevent="handleSend"
              @keydown.meta.enter.prevent="handleSend"
            />
            <el-button
              v-if="!loading"
              type="primary"
              :disabled="!inputText.trim() || !selectedExpertId"
              @click="handleSend"
            >
              发送
            </el-button>
            <el-button v-else type="danger" @click="stopGeneration">停止</el-button>
          </div>
        </div>
      </div>

      <!-- 产出文件面板（可折叠） -->
      <div class="output-panel">
        <div class="panel-header" @click="panelOpen = !panelOpen">
          <span class="panel-title">产出文件</span>
          <span class="panel-toggle">{{ panelOpen ? '›' : '‹' }}</span>
        </div>
        <div v-show="panelOpen" class="panel-body">
          <!-- 专家方案 -->
          <div class="panel-section">
            <div class="section-title">专家方案</div>
            <div v-if="proposalCount === 0" class="section-empty">暂无</div>
            <div v-for="item in proposalList" :key="item.key" class="file-item clickable" @click="viewPanelFile('proposal', item.key, item.label)">
              <span class="file-icon">📄</span>
              <span class="file-name">{{ item.label }}</span>
            </div>
          </div>

          <!-- 评审记录 -->
          <div class="panel-section">
            <div class="section-title">评审记录</div>
            <div v-if="reviewCount === 0" class="section-empty">暂无</div>
            <div v-for="item in reviewList" :key="item.key" class="file-item clickable" @click="viewPanelFile('review', item.key, item.label)">
              <span class="file-icon">📝</span>
              <span class="file-name">{{ item.label }}</span>
            </div>
          </div>

          <!-- 蓝图版本 -->
          <div class="panel-section">
            <div class="section-title">蓝图版本</div>
            <div v-if="blueprintCount === 0" class="section-empty">暂无</div>
            <div v-for="name in blueprintList" :key="name" class="file-item clickable" @click="viewPanelFile('blueprint', name, name)">
              <span class="file-icon">📋</span>
              <span class="file-name">{{ name }}</span>
            </div>
          </div>

          <!-- 融合决策标记 -->
          <div v-if="task && task.has_fusion_decision" class="panel-section">
            <div class="section-title">融合决策</div>
            <div class="file-item clickable" @click="viewPanelFile('fusion', '', 'fusion_decision.md')">
              <span class="file-icon">🔀</span>
              <span class="file-name">fusion_decision.md</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧文件查看对话框 -->
    <el-dialog
      v-model="fileViewerVisible"
      :title="fileViewerTitle"
      width="760px"
      append-to-body
      :close-on-click-modal="true"
      class="file-viewer-dialog"
    >
      <div v-if="fileViewerLoading" class="file-viewer-loading">
        <span class="loading-spinner">⏳</span>
        <span>正在加载文件内容...</span>
      </div>
      <div v-else-if="fileViewerContent" class="file-viewer-content markdown-body" v-html="renderMarkdown(fileViewerContent)"></div>
      <div v-else class="file-viewer-empty">
        <div class="empty-icon">📄</div>
        <p>文件内容为空或不存在</p>
      </div>
      <template #footer>
        <el-button @click="fileViewerVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api/index.js'
import { renderMarkdown } from '../utils/markdown.js'
import { useAgentStore } from '../stores/agent.js'

const store = useAgentStore()

// ===== 响应式状态 =====
const task = ref(null)              // 任务完整详情（含 messages、proposals 等）
const experts = ref([])             // 全部专家列表
const messages = ref([])            // 当前展示的消息列表（历史 + 流式）
const inputText = ref('')           // 输入框文本
const loading = ref(false)          // 是否正在流式请求
const selectedExpertId = ref('')    // 当前选中的对话专家
const panelOpen = ref(true)         // 产出面板是否展开
const msgListRef = ref(null)        // 消息列表 DOM 引用（用于自动滚动）
let abortController = null          // 中止流式请求的控制器
let streamingMsgIndex = -1          // 当前流式输出消息在 messages 中的索引

// ===== 深度模式多阶段流程状态 =====
const phaseLoading = ref(null)      // null | 'proposals' | 'reviews' | 'fusion'
const expertProgress = ref({})      // {expert_id: {status, content_length, error}}

// ===== 右侧文件查看器状态 =====
const fileViewerVisible = ref(false)
const fileViewerLoading = ref(false)
const fileViewerTitle = ref('')
const fileViewerContent = ref('')

// ===== 计算属性 =====

// 当前任务 ID（从 store 读取）
const taskId = computed(() => store.metaTeamTaskId)

// 参与本任务的专家列表（按 task.expert_ids 过滤）
const taskExperts = computed(() => {
  if (!task.value || !task.value.expert_ids) return []
  return task.value.expert_ids
    .map(id => experts.value.find(e => e.id === id))
    .filter(Boolean)
})

// 状态标签文案
const statusLabel = computed(() => {
  const map = {
    drafting: '设计中',
    reviewing: '评审中',
    fusing: '融合中',
    completed: '已完成',
    archived: '已归档'
  }
  return map[task.value?.status] || task.value?.status || ''
})

// 状态标签颜色
const statusTagType = computed(() => {
  const map = {
    drafting: 'warning',
    reviewing: 'warning',
    fusing: 'warning',
    completed: 'success',
    archived: 'info'
  }
  return map[task.value?.status] || 'info'
})

// 工作模式标签文案
const modeLabel = computed(() => {
  if (!task.value) return ''
  return task.value.mode === 'fast' ? '快速模式' : '深度模式'
})

// 阶段进行中的提示文字
const phaseLoadingText = computed(() => {
  const map = {
    proposals: '专家撰写方案中…',
    reviews: '专家评审中…',
    fusion: '融合主智能体产出中…'
  }
  return map[phaseLoading.value] || ''
})

// 产出文件列表（将 dict 转为可遍历的数组）
const proposalList = computed(() => {
  const p = task.value?.proposals || {}
  return Object.keys(p).map(expertId => ({
    key: expertId,
    label: `${getExpertName(expertId)} 的方案`
  }))
})
const proposalCount = computed(() => proposalList.value.length)

const reviewList = computed(() => {
  const r = task.value?.reviews || {}
  return Object.keys(r).map(expertId => ({
    key: expertId,
    label: `${getExpertName(expertId)} 的评审`
  }))
})
const reviewCount = computed(() => reviewList.value.length)

const blueprintList = computed(() => task.value?.blueprint_versions || [])
const blueprintCount = computed(() => blueprintList.value.length)

// ===== 工具函数 =====

// 根据专家 ID 获取专家名称
function getExpertName(expertId) {
  if (!expertId) return '专家'
  const exp = experts.value.find(e => e.id === expertId)
  return exp ? exp.name : '专家'
}

// 获取消息头像
function getMsgAvatar(msg) {
  if (msg.role === 'user') return '👤'
  return '🧑‍💼'
}

// 根据专家 ID 生成头像 emoji（与 MetaTeamExperts 保持一致）
const avatarPool = ['🧠', '🎨', '📐', '🔧', '📊', '💡', '🎯', '🏗️']
function getExpertAvatar(expertId) {
  if (!expertId) return '👤'
  let hash = 0
  for (let i = 0; i < expertId.length; i++) {
    hash = expertId.charCodeAt(i) + ((hash << 5) - hash)
  }
  return avatarPool[Math.abs(hash) % avatarPool.length]
}

// 查看右侧面板中的产出文件
async function viewPanelFile(type, key, label) {
  if (!taskId.value) return
  fileViewerVisible.value = true
  fileViewerLoading.value = true
  fileViewerTitle.value = label || '文件查看'
  fileViewerContent.value = ''

  try {
    if (type === 'proposal') {
      // 专家方案
      const res = await api.getMetaTeamProposal(taskId.value, key)
      fileViewerContent.value = res.data.content || ''
      fileViewerTitle.value = `📄 ${label}`
    } else if (type === 'review') {
      // 专家评审
      const res = await api.getMetaTeamReviewFile(taskId.value, key)
      fileViewerContent.value = res.data.content || ''
      fileViewerTitle.value = `📝 ${label}`
    } else if (type === 'fusion') {
      // 融合决策
      const res = await api.getMetaTeamFusionDecision(taskId.value)
      fileViewerContent.value = res.data.content || ''
      fileViewerTitle.value = `🔀 融合决策 — ${res.data.task_title || ''}`
    } else if (type === 'blueprint') {
      // 蓝图版本（JSON 数据，格式化展示）
      // key 是文件名如 "team_blueprint_v1.json"，提取版本号
      const versionMatch = key.match(/v(\d+)/)
      const version = versionMatch ? parseInt(versionMatch[1]) : 1
      const res = await api.getMetaTeamBlueprintVersion(taskId.value, version)
      const bpData = res.data.blueprint_data
      // 将蓝图 JSON 格式化为可读的 Markdown
      let md = `# 蓝图 v${version}\n\n`
      md += `**团队名称**: ${bpData.team_name || '未命名'}\n\n`
      md += `**团队描述**: ${bpData.description || '无'}\n\n`
      md += `## 成员列表（${bpData.members?.length || 0} 个）\n\n`
      if (bpData.members) {
        for (const m of bpData.members) {
          md += `### ${m.name || '未命名'}\n`
          md += `- **角色**: ${m.role || '无'}\n`
          md += `- **模板**: ${m.template || 'worker'}\n`
          md += `- **权限路径**: ${m.allowed_paths?.length || 0} 个\n`
          if (m.enabled_skills && m.enabled_skills.length > 0) {
            md += `- **技能**: ${m.enabled_skills.join(', ')}\n`
          }
          if (m.system_prompt) {
            md += `- **提示词**: \n\`\`\`\n${m.system_prompt}\n\`\`\`\n`
          }
          md += '\n'
        }
      }
      if (bpData.tasks && bpData.tasks.length > 0) {
        md += `## 任务列表（${bpData.tasks.length} 个）\n\n`
        for (const t of bpData.tasks) {
          md += `- ${t.description || t.title || '未命名任务'} → ${t.assignee || '未指定'}\n`
        }
        md += '\n'
      }
      if (bpData.execution_tips) {
        md += `## 执行建议\n\n${bpData.execution_tips}\n`
      }
      fileViewerContent.value = md
      fileViewerTitle.value = `📋 蓝图 v${version} — ${bpData.team_name || ''}`
    }
  } catch (e) {
    if (e.response?.status === 404) {
      ElMessage.info('文件不存在或已被删除')
    } else {
      ElMessage.error('加载失败：' + (e.response?.data?.detail || e.message || '网络错误'))
    }
    fileViewerContent.value = ''
  } finally {
    fileViewerLoading.value = false
  }
}

// 获取消息发送者名称
function getMsgName(msg) {
  if (msg.role === 'user') return '我'
  return getExpertName(msg.expert_id)
}

// 截断文本
function truncate(text, len) {
  if (!text) return ''
  return text.length > len ? text.slice(0, len) + '…' : text
}

// 滚动消息列表到底部
function scrollToBottom() {
  nextTick(() => {
    const el = msgListRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

// ===== 数据加载 =====

// 加载任务详情
async function loadTask() {
  if (!taskId.value) return
  try {
    const res = await api.getMetaTeamTask(taskId.value)
    task.value = res.data.task
    // 保留前端已有的系统消息（阶段进度），合并后端消息
    const systemMsgs = messages.value.filter(m => m.role === 'system')
    const backendMsgs = (res.data.task.messages || []).map(m => ({ ...m, streaming: false }))
    messages.value = [...backendMsgs, ...systemMsgs]
    // 默认选中第一个专家
    if (!selectedExpertId.value && task.value.expert_ids && task.value.expert_ids.length > 0) {
      selectedExpertId.value = task.value.expert_ids[0]
    }
    scrollToBottom()
  } catch (e) {
    console.error('加载任务详情失败:', e)
    ElMessage.error('加载任务详情失败：' + (e.response?.data?.detail || e.message))
  }
}

// 加载专家列表
async function loadExperts() {
  try {
    const res = await api.getMetaTeamExperts()
    experts.value = res.data.experts || []
  } catch (e) {
    console.error('加载专家列表失败:', e)
  }
}

// ===== 发送消息（SSE 流式） =====
async function handleSend() {
  const text = inputText.value.trim()
  if (!text || loading.value) return
  if (!selectedExpertId.value) {
    ElMessage.warning('请先选择对话专家')
    return
  }
  if (!taskId.value) return

  loading.value = true
  inputText.value = ''
  abortController = new AbortController()

  // 先把用户消息追加到本地列表
  messages.value.push({
    role: 'user',
    content: text,
    created_at: new Date().toISOString(),
    streaming: false
  })
  scrollToBottom()

  try {
    const response = await api.metaTeamChatStream(
      taskId.value,
      text,
      selectedExpertId.value,
      abortController.signal,
      store.defaultConfigId,
      store.enableThinking
    )

    if (!response.ok) {
      throw new Error('请求失败: ' + response.status)
    }

    // 读取 SSE 流
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let currentEvent = ''
    let currentData = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('event:')) {
          currentEvent = line.slice(6).trim()
          currentData = ''
        } else if (line.startsWith('data:')) {
          currentData += line.slice(6)
        } else if (line === '') {
          // 空行表示一个事件结束
          if (currentEvent && currentData) {
            handleSSEEvent(currentEvent, currentData)
          }
          currentEvent = ''
          currentData = ''
        }
      }
    }

    // 处理缓冲区中剩余的事件
    if (currentEvent && currentData) {
      handleSSEEvent(currentEvent, currentData)
    }

    // 流式完成后重新加载任务，同步产出文件和状态
    await loadTask()
  } catch (e) {
    // 用户主动中止时不报错
    if (e.name === 'AbortError') {
      if (streamingMsgIndex >= 0 && messages.value[streamingMsgIndex]) {
        messages.value[streamingMsgIndex].streaming = false
        if (messages.value[streamingMsgIndex].content) {
          messages.value[streamingMsgIndex].content += '\n\n_[已停止生成]_'
        }
      }
    } else {
      console.error('对话失败:', e)
      ElMessage.error('对话失败：' + (e.message || '网络错误'))
    }
  } finally {
    loading.value = false
    abortController = null
    streamingMsgIndex = -1
  }
}

// 处理单个 SSE 事件
function handleSSEEvent(event, dataStr) {
  let data
  try {
    data = JSON.parse(dataStr)
  } catch (e) {
    console.warn('SSE 数据解析失败:', dataStr)
    return
  }

  switch (event) {
    case 'agent_start': {
      // 专家开始回复，追加一个占位消息
      messages.value.push({
        role: 'expert',
        expert_id: data.expert_id,
        content: '',
        created_at: new Date().toISOString(),
        streaming: true
      })
      streamingMsgIndex = messages.value.length - 1
      scrollToBottom()
      break
    }
    case 'token': {
      // 追加 token 到当前流式消息
      if (streamingMsgIndex >= 0 && messages.value[streamingMsgIndex]) {
        messages.value[streamingMsgIndex].content += data.content || ''
        scrollToBottom()
      }
      break
    }
    case 'agent_end': {
      // 流式结束，标记完成（用 full_content 兜底补全）
      if (streamingMsgIndex >= 0 && messages.value[streamingMsgIndex]) {
        messages.value[streamingMsgIndex].streaming = false
        if (data.full_content && !messages.value[streamingMsgIndex].content) {
          messages.value[streamingMsgIndex].content = data.full_content
        }
      }
      break
    }
    case 'done': {
      // 全部完成
      if (streamingMsgIndex >= 0 && messages.value[streamingMsgIndex]) {
        messages.value[streamingMsgIndex].streaming = false
      }
      break
    }
    case 'error': {
      ElMessage.error('专家回复出错：' + (data.message || '未知错误'))
      if (streamingMsgIndex >= 0 && messages.value[streamingMsgIndex]) {
        messages.value[streamingMsgIndex].streaming = false
      }
      break
    }
  }
}

// 中止生成
function stopGeneration() {
  if (abortController) abortController.abort()
}

// 组件卸载时中止正在进行的 SSE 请求，防止内存泄漏
onBeforeUnmount(() => {
  if (abortController) abortController.abort()
})

// ===== 深度模式：多阶段流程控制 =====

// 添加系统消息（居中展示的阶段进度提示）
function addSystemMessage(content, icon = '📋') {
  messages.value.push({
    role: 'system',
    content: content,
    icon: icon,
    created_at: new Date().toISOString(),
    streaming: false
  })
  scrollToBottom()
}

// 启动方案撰写阶段
// 一键全流程（自动流转方案撰写→评审→融合）
async function handleRunAll() {
  if (!taskId.value || phaseLoading.value) return
  phaseLoading.value = 'proposals'  // 初始显示"方案撰写中"
  loading.value = true
  expertProgress.value = {}
  abortController = new AbortController()

  addSystemMessage('**🚀 一键全流程启动** — 将自动执行方案撰写、评审、融合三个阶段', '🚀')

  try {
    const response = await api.metaTeamRunAllStream(
      taskId.value,
      store.defaultConfigId,
      abortController.signal
    )
    await readPhaseSSEStream(response, 'all')
    await loadTask()
  } catch (e) {
    handlePhaseError(e, '全流程')
  } finally {
    try { await loadTask() } catch (_) {}
    phaseLoading.value = null
    loading.value = false
    abortController = null
  }
}

async function handleRunProposals() {
  if (!taskId.value || phaseLoading.value) return
  phaseLoading.value = 'proposals'
  loading.value = true
  expertProgress.value = {}
  abortController = new AbortController()

  addSystemMessage('**启动方案撰写阶段** — 3 位专家将并行撰写各自的团队蓝图方案', '🚀')

  try {
    const response = await api.metaTeamRunProposalsStream(
      taskId.value,
      store.defaultConfigId,
      abortController.signal
    )
    await readPhaseSSEStream(response, 'proposals')
    // 流式完成后重新加载任务，同步产出文件和状态
    await loadTask()
  } catch (e) {
    handlePhaseError(e, '方案撰写')
  } finally {
    // 无论成功或失败，都重新加载任务数据以同步产出文件和状态
    try { await loadTask() } catch (_) {}
    phaseLoading.value = null
    loading.value = false
    abortController = null
  }
}

// 启动评审阶段
async function handleRunReviews() {
  if (!taskId.value || phaseLoading.value) return
  phaseLoading.value = 'reviews'
  loading.value = true
  expertProgress.value = {}
  abortController = new AbortController()

  addSystemMessage('**启动评审阶段** — 每位专家将评审其他专家的方案并打分', '📝')

  try {
    const response = await api.metaTeamRunReviewsStream(
      taskId.value,
      store.defaultConfigId,
      abortController.signal
    )
    await readPhaseSSEStream(response, 'reviews')
    await loadTask()
  } catch (e) {
    handlePhaseError(e, '评审')
  } finally {
    try { await loadTask() } catch (_) {}
    phaseLoading.value = null
    loading.value = false
    abortController = null
  }
}

// 启动融合阶段
async function handleRunFusion() {
  if (!taskId.value || phaseLoading.value) return
  phaseLoading.value = 'fusion'
  loading.value = true
  abortController = new AbortController()

  addSystemMessage('**启动融合阶段** — 主智能体将融合所有方案和评审，产出最终蓝图', '🔀')

  // 为融合结果创建一个流式消息（以专家消息形式展示）
  messages.value.push({
    role: 'expert',
    expert_id: 'fusion',
    content: '',
    created_at: new Date().toISOString(),
    streaming: true
  })
  streamingMsgIndex = messages.value.length - 1
  scrollToBottom()

  try {
    const response = await api.metaTeamRunFusionStream(
      taskId.value,
      store.defaultConfigId,
      abortController.signal
    )
    await readPhaseSSEStream(response, 'fusion')
    await loadTask()
  } catch (e) {
    handlePhaseError(e, '融合')
  } finally {
    try { await loadTask() } catch (_) {}
    phaseLoading.value = null
    loading.value = false
    abortController = null
    streamingMsgIndex = -1
  }
}

// 读取阶段 SSE 流（通用）
async function readPhaseSSEStream(response, phase) {
  if (!response.ok) {
    throw new Error('请求失败: ' + response.status)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let currentEvent = ''
  let currentData = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (line.startsWith('event:')) {
        currentEvent = line.slice(6).trim()
        currentData = ''
      } else if (line.startsWith('data:')) {
        currentData += line.slice(6)
      } else if (line === '') {
        if (currentEvent && currentData) {
          handlePhaseSSEEvent(currentEvent, currentData, phase)
        }
        currentEvent = ''
        currentData = ''
      }
    }
  }
  // 处理缓冲区中剩余的事件
  if (currentEvent && currentData) {
    handlePhaseSSEEvent(currentEvent, currentData, phase)
  }
}

// 处理阶段 SSE 事件
function handlePhaseSSEEvent(event, dataStr, phase) {
  let data
  try {
    data = JSON.parse(dataStr)
  } catch (e) {
    console.warn('SSE 数据解析失败:', dataStr)
    return
  }

  switch (event) {
    case 'all_start': {
      // 一键全流程启动
      phaseLoading.value = 'proposals'
      break
    }
    case 'expert_start': {
      expertProgress.value[data.expert_id] = { status: 'working' }
      // all 模式下根据 phaseLoading 判断当前阶段
      const currentPhase = phase === 'all' ? phaseLoading.value : phase
      const action = currentPhase === 'reviews' ? '评审' : '撰写方案'
      addSystemMessage(`**${data.expert_name}** 开始${action}…`, '⏳')
      break
    }
    case 'expert_complete': {
      if (data.success) {
        expertProgress.value[data.expert_id] = {
          status: 'done',
          content_length: data.content_length || 0
        }
        const currentPhase = phase === 'all' ? phaseLoading.value : phase
        const action = currentPhase === 'reviews' ? '评审' : '方案撰写'
        const lenStr = data.content_length ? `（${data.content_length}字）` : ''
        addSystemMessage(`**${data.expert_name}** 完成${action}${lenStr}`, '✅')
      } else {
        expertProgress.value[data.expert_id] = {
          status: 'failed',
          error: data.error
        }
        const currentPhase = phase === 'all' ? phaseLoading.value : phase
        const action = currentPhase === 'reviews' ? '评审' : '方案撰写'
        addSystemMessage(`**${data.expert_name}** ${action}失败：${data.error || '未知错误'}`, '❌')
      }
      break
    }
    case 'phase_complete': {
      if (phase === 'fusion') break  // 融合阶段由 fusion_complete 处理

      // all 模式下根据 data.phase 判断刚完成的是哪个阶段
      if (phase === 'all') {
        const completedPhase = data.phase  // 'proposing'、'reviewing' 或 'fusing'
        // 融合阶段的完成由 fusion_complete 和 all_complete 事件处理，跳过
        if (completedPhase === 'fusing') break
        const phaseNames = { proposing: '方案撰写', reviewing: '评审' }
        addSystemMessage(
          `**${phaseNames[completedPhase] || completedPhase}阶段完成** — 成功 ${data.success_count}/${data.total}`,
          '🎉'
        )
        // 自动切换到下一阶段
        if (completedPhase === 'proposing') {
          phaseLoading.value = 'reviews'
          addSystemMessage('**自动进入评审阶段** — 专家将互相评审方案', '📝')
        } else if (completedPhase === 'reviewing') {
          phaseLoading.value = 'fusion'
          addSystemMessage('**自动进入融合阶段** — 主智能体将融合所有方案和评审', '🔀')
          // 为融合结果创建流式消息
          messages.value.push({
            role: 'expert',
            expert_id: 'fusion',
            content: '',
            created_at: new Date().toISOString(),
            streaming: true
          })
          streamingMsgIndex = messages.value.length - 1
          scrollToBottom()
        }
      } else {
        const phaseNames = { proposals: '方案撰写', reviews: '评审' }
        addSystemMessage(
          `**${phaseNames[phase] || phase}阶段完成** — 成功 ${data.success_count}/${data.total}`,
          '🎉'
        )
      }
      break
    }
    case 'fusion_start': {
      // 融合开始，清空流式消息内容
      if (streamingMsgIndex >= 0 && messages.value[streamingMsgIndex]) {
        messages.value[streamingMsgIndex].content = ''
      }
      break
    }
    case 'token': {
      // 融合阶段的流式 token
      if (streamingMsgIndex >= 0 && messages.value[streamingMsgIndex]) {
        messages.value[streamingMsgIndex].content += data.content || ''
        scrollToBottom()
      }
      break
    }
    case 'fusion_complete': {
      if (streamingMsgIndex >= 0 && messages.value[streamingMsgIndex]) {
        messages.value[streamingMsgIndex].streaming = false
      }
      addSystemMessage('**融合阶段完成** — 最终蓝图已产出，可确认入库', '🎉')
      break
    }
    case 'all_complete': {
      if (streamingMsgIndex >= 0 && messages.value[streamingMsgIndex]) {
        messages.value[streamingMsgIndex].streaming = false
      }
      if (data.success) {
        addSystemMessage('**🚀 全流程完成** — 方案撰写→评审→融合全部完成，可确认产出蓝图', '🎉')
      } else {
        addSystemMessage(`**全流程中止** — ${data.message || '某阶段失败'}`, '⚠️')
      }
      break
    }
    case 'experience_recorded': {
      console.log('专家经验已记录:', data.expert_name || data.expert_id)
      break
    }
    case 'error': {
      ElMessage.error('阶段执行出错：' + (data.message || '未知错误'))
      if (streamingMsgIndex >= 0 && messages.value[streamingMsgIndex]) {
        messages.value[streamingMsgIndex].streaming = false
      }
      break
    }
    case 'done': {
      if (streamingMsgIndex >= 0 && messages.value[streamingMsgIndex]) {
        messages.value[streamingMsgIndex].streaming = false
      }
      break
    }
  }
}

// 阶段错误处理
function handlePhaseError(e, phaseName) {
  if (e.name === 'AbortError') {
    addSystemMessage(`**${phaseName}阶段已中止**`, '⏹️')
    if (streamingMsgIndex >= 0 && messages.value[streamingMsgIndex]) {
      messages.value[streamingMsgIndex].streaming = false
      if (messages.value[streamingMsgIndex].content) {
        messages.value[streamingMsgIndex].content += '\n\n_[已停止生成]_'
      }
    }
  } else {
    console.error(`${phaseName}失败:`, e)
    ElMessage.error(`${phaseName}失败：` + (e.message || '网络错误'))
  }
}

// ===== 确认产出蓝图 =====
async function handleFinalize() {
  if (!taskId.value) return
  try {
    await ElMessageBox.confirm(
      '确认将本任务产出的最新蓝图写入蓝图库？确认后任务将转为「已归档」状态。',
      '确认产出蓝图',
      { confirmButtonText: '确认入库', cancelButtonText: '取消', type: 'warning' }
    )
  } catch (e) {
    return // 用户取消
  }

  try {
    const res = await store.finalizeMetaTeamTask(taskId.value)
    ElMessage.success(res.message || '蓝图已入库')
    // 重新加载任务详情，刷新状态和产出
    await loadTask()
  } catch (e) {
    console.error('确认产出失败:', e)
    ElMessage.error('确认产出失败：' + (e.response?.data?.detail || e.message))
  }
}

// ===== 返回列表 =====
function goBack() {
  store.selectMetaTeamTask('')
}

// ===== 生命周期 =====
onMounted(() => {
  loadExperts()
  loadTask()
})

// 当 store 中的 taskId 变化时重新加载（例如侧边栏切换任务）
watch(taskId, (newId) => {
  if (newId) {
    selectedExpertId.value = ''
    loadTask()
  }
})
</script>

<style scoped>
.meta-team-task {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-app);
  overflow: hidden;
}

/* ===== 顶部栏 ===== */
.task-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-md) var(--space-lg);
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}
.topbar-left {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  min-width: 0;
  flex: 1;
}
.topbar-right {
  flex-shrink: 0;
}
.back-btn {
  padding: 4px 8px;
  color: var(--text-secondary);
  font-size: 13px;
}
.back-btn:hover {
  color: var(--primary);
}
.task-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 360px;
}

/* ===== 专家胶囊栏 ===== */
.expert-team-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.bar-label {
  font-size: 12px;
  color: #64748b;
  flex-shrink: 0;
  font-weight: 500;
}

.expert-chips {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.expert-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 9999px;
  cursor: pointer;
  transition: all 0.25s ease;
  font-size: 13px;
  color: #475569;
  background: #f1f5f9;
  border: 1px solid transparent;
}

.expert-chip:hover {
  background: #eef2ff;
  border-color: #818cf8;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.15);
}

.expert-chip.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-color: transparent;
  color: #fff;
  font-weight: 500;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.chip-avatar {
  font-size: 16px;
}

.chip-ver {
  font-size: 11px;
  opacity: 0.7;
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.2);
}

.expert-chip:not(.active) .chip-ver {
  background: #e0e7ff;
  color: #4f46e5;
}

/* ===== 主体布局 ===== */
.task-main {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.task-main.panel-collapsed .chat-area {
  flex: 1;
}

/* ===== 对话区 ===== */
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--bg-chat);
}

/* 消息列表 */
.msg-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-lg) var(--space-xl);
}
.empty-tip {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-tertiary);
  text-align: center;
}
.empty-icon {
  font-size: 48px;
  margin-bottom: var(--space-md);
}
.empty-text {
  font-size: 16px;
  color: var(--text-secondary);
  margin-bottom: var(--space-xs);
}
.empty-sub {
  font-size: 13px;
  color: var(--text-tertiary);
}

/* 消息条目 */
.msg-row {
  display: flex;
  gap: var(--space-md);
  margin-bottom: var(--space-lg);
  max-width: 880px;
}
.msg-user {
  flex-direction: row-reverse;
  margin-left: auto;
}
.msg-expert {
  margin-right: auto;
}
.msg-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--bg-active);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}
.msg-user .msg-avatar {
  background: var(--primary);
}
.msg-body {
  display: flex;
  flex-direction: column;
  min-width: 0;
  max-width: calc(100% - 52px);
}
.msg-user .msg-body {
  align-items: flex-end;
}
.msg-meta {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: 4px;
  font-size: 12px;
  color: var(--text-tertiary);
}
.msg-user .msg-meta {
  flex-direction: row-reverse;
}
.msg-name {
  font-weight: 500;
  color: var(--text-secondary);
}
.streaming-tip {
  color: var(--primary);
}
.streaming-tip::before {
  content: '';
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary);
  margin-right: 4px;
  animation: blink 1s infinite;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
.msg-bubble {
  padding: var(--space-md) var(--space-lg);
  border-radius: var(--radius-md);
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}
.msg-expert .msg-bubble {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-top-left-radius: 4px;
  color: var(--text-primary);
}
.msg-user .msg-bubble {
  background: var(--primary);
  color: #fff;
  border-top-right-radius: 4px;
}

/* ===== 系统消息（阶段进度） ===== */
.msg-system-row {
  justify-content: center;
  margin-left: auto;
  margin-right: auto;
  max-width: 600px;
}
.msg-system {
  display: flex;
  align-items: flex-start;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-secondary);
  border: 1px solid var(--border-light);
}
.system-icon {
  flex-shrink: 0;
  font-size: 14px;
  line-height: 1.6;
}
.system-text {
  flex: 1;
  line-height: 1.6;
  word-break: break-word;
}
.system-text :deep(p) {
  margin: 0;
}

/* ===== 输入区 ===== */
.input-area {
  flex-shrink: 0;
  padding: var(--space-md) var(--space-xl) var(--space-lg);
  background: var(--bg-card);
  border-top: 1px solid var(--border-color);
}
.expert-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-sm);
  font-size: 13px;
  color: var(--text-secondary);
}
.expert-label {
  flex-shrink: 0;
}
.expert-select {
  width: 180px;
}
.requirement-hint {
  margin-left: auto;
  color: var(--text-tertiary);
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 320px;
}
.input-row {
  display: flex;
  gap: var(--space-md);
  align-items: flex-end;
}
.input-box {
  flex: 1;
}

/* ===== 产出文件面板 ===== */
.output-panel {
  width: 300px;
  flex-shrink: 0;
  background: var(--bg-card);
  border-left: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  transition: width var(--transition-fast);
  overflow: hidden;
}
.task-main.panel-collapsed .output-panel {
  width: 44px;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-md) var(--space-lg);
  border-bottom: 1px solid var(--border-color);
  cursor: pointer;
  user-select: none;
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}
.panel-header:hover {
  background: var(--bg-hover);
}
.panel-toggle {
  font-size: 20px;
  color: var(--text-tertiary);
  line-height: 1;
}
.task-main.panel-collapsed .panel-header {
  flex-direction: column;
  gap: var(--space-sm);
  border-bottom: none;
  padding: var(--space-md) var(--space-xs);
}
.task-main.panel-collapsed .panel-title {
  writing-mode: vertical-rl;
  font-size: 12px;
}
.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-md) var(--space-lg);
}
.panel-section {
  margin-bottom: var(--space-xl);
}
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--space-sm);
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border-light);
}
.section-empty {
  font-size: 12px;
  color: var(--text-muted);
  padding: var(--space-xs) 0;
}
.file-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: 6px var(--space-sm);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text-secondary);
  cursor: default;
  transition: background var(--transition-fast);
}
.file-item:hover {
  background: var(--bg-hover);
}
.file-item.clickable {
  cursor: pointer;
}
.file-item.clickable:hover {
  background: #eef2ff;
  color: #4f46e5;
}
.file-icon {
  flex-shrink: 0;
  font-size: 14px;
}
.file-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ===== 文件查看对话框 ===== */
.file-viewer-dialog :deep(.el-dialog__body) {
  max-height: 65vh;
  overflow-y: auto;
  padding: 16px 20px;
}

.file-viewer-content {
  font-size: 14px;
  line-height: 1.7;
  color: #334155;
}

.file-viewer-content :deep(h1),
.file-viewer-content :deep(h2),
.file-viewer-content :deep(h3) {
  margin-top: 16px;
  margin-bottom: 8px;
  color: #1e293b;
}

.file-viewer-content :deep(pre) {
  background: #f8fafc;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 13px;
}

.file-viewer-content :deep(code) {
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 13px;
}

.file-viewer-content :deep(pre code) {
  background: none;
  padding: 0;
}

.file-viewer-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px 0;
  color: #64748b;
}

.loading-spinner {
  font-size: 20px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.file-viewer-empty {
  text-align: center;
  padding: 40px 0;
  color: #94a3b8;
}

.file-viewer-empty .empty-icon {
  font-size: 32px;
  margin-bottom: 8px;
}
</style>
