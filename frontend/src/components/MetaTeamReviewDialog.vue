<template>
  <el-dialog
    v-model="visible"
    title="元团队评审"
    width="720px"
    :close-on-click-modal="false"
    :close-on-press-escape="!reviewing"
    class="review-dialog"
    @close="handleClose"
  >
    <!-- 步骤 1：评审输入区（未启动评审时显示） -->
    <div v-if="step === 'input'" class="review-input-section">
      <div class="section-header">
        <span class="section-icon">🔍</span>
        <span class="section-title">项目回访评审</span>
      </div>
      <p class="section-desc">
        对当前项目（基于蓝图创建）进行回访评审。系统将采集七维度运行数据，
        交给元团队专家诊断设计问题，产出评审报告。
      </p>

      <!-- 数据预览 -->
      <div class="data-preview" v-if="dataPreview">
        <div class="preview-item">
          <span class="preview-label">团队成员</span>
          <span class="preview-value">{{ dataPreview.member_count }} 个</span>
        </div>
        <div class="preview-item">
          <span class="preview-label">任务总数</span>
          <span class="preview-value">{{ dataPreview.task_total }} 个</span>
        </div>
        <div class="preview-item">
          <span class="preview-label">消息总数</span>
          <span class="preview-value">{{ dataPreview.message_total }} 条</span>
        </div>
        <div class="preview-item">
          <span class="preview-label">异常事件</span>
          <span class="preview-value" :class="{ 'has-anomaly': dataPreview.anomaly_count > 0 }">
            {{ dataPreview.anomaly_count }} 个
          </span>
        </div>
      </div>

      <!-- 用户主观反馈 -->
      <div class="feedback-section">
        <span class="feedback-label">主观反馈（可选）</span>
        <el-input
          v-model="userFeedback"
          type="textarea"
          :rows="4"
          placeholder="可选：描述你在使用这个团队时感受到的问题或满意之处，作为专家评审的参考。&#10;例如：团队成员之间的协作不太顺畅、某个成员的提示词执行效果不好等。"
          resize="none"
          class="feedback-input"
        />
      </div>

      <div class="action-row">
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="handleStartReview">启动评审</el-button>
      </div>
    </div>

    <!-- 步骤 2：评审进行中 -->
    <div v-if="step === 'reviewing'" class="review-progress-section">
      <!-- 进度步骤 -->
      <div class="progress-steps">
        <div class="step-item" :class="getStepClass('collect')">
          <span class="step-icon">{{ getStepIcon('collect') }}</span>
          <span class="step-text">采集数据</span>
        </div>
        <div class="step-connector" :class="{ active: currentPhase !== 'collect' }"></div>
        <div class="step-item" :class="getStepClass('diagnose')">
          <span class="step-icon">{{ getStepIcon('diagnose') }}</span>
          <span class="step-text">专家诊断</span>
        </div>
        <div class="step-connector" :class="{ active: currentPhase === 'summary' }"></div>
        <div class="step-item" :class="getStepClass('summary')">
          <span class="step-icon">{{ getStepIcon('summary') }}</span>
          <span class="step-text">汇总报告</span>
        </div>
      </div>

      <!-- 实时日志 -->
      <div class="progress-log" ref="logRef">
        <div v-for="(log, i) in progressLogs" :key="i" class="log-item" :class="log.type">
          <span class="log-icon">{{ log.icon }}</span>
          <span class="log-text" v-html="renderMarkdown(log.text)"></span>
        </div>
      </div>

      <!-- 中止按钮 -->
      <div class="action-row">
        <el-button type="danger" @click="handleAbort">停止评审</el-button>
      </div>
    </div>

    <!-- 步骤 3：评审报告 -->
    <div v-if="step === 'report'" class="review-report-section">
      <!-- 报告内容 -->
      <div class="report-content markdown-body" v-html="renderMarkdown(reportContent)"></div>

      <!-- 专家诊断对比 -->
      <div v-if="expertDiagnoses.length > 0" class="diagnoses-section">
        <el-collapse>
          <el-collapse-item :title="`📋 各专家原始诊断（${expertDiagnoses.length} 份）`" name="diagnoses">
            <div v-for="diag in expertDiagnoses" :key="diag.expert_id" class="diag-item">
              <div class="diag-header">
                <span class="diag-name">{{ diag.expert_name }}</span>
                <span class="diag-len">{{ diag.content_length }} 字</span>
              </div>
              <div class="diag-content markdown-body" v-html="renderMarkdown(diag.content || diag.content_preview || '')"></div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <!-- 后续动作 -->
      <div class="post-actions">
        <div class="action-hint">基于评审结果，你可以：</div>
        <div class="action-buttons">
          <el-button @click="handleExportReport">📄 导出报告</el-button>
          <el-button @click="handleViewHistory">查看历史评审</el-button>
          <el-button type="primary" @click="handleStartNewDesign">启动新设计任务</el-button>
        </div>
      </div>
    </div>

    <!-- 历史评审列表 -->
    <div v-if="step === 'history'" class="review-history-section">
      <div class="section-header">
        <span class="section-icon">📋</span>
        <span class="section-title">历史评审记录</span>
        <el-button text size="small" @click="step = 'input'">← 返回</el-button>
      </div>
      <div v-if="historyList.length === 0" class="empty-tip">暂无历史评审记录</div>
      <div v-for="item in historyList" :key="item.review_id" class="history-item" @click="handleViewReport(item.review_id)">
        <div class="history-info">
          <span class="history-status" :class="item.status">{{ statusLabel(item.status) }}</span>
          <span class="history-date">{{ item.created_at }}</span>
        </div>
        <span class="history-report-icon" v-if="item.has_report">📄 有报告</span>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/index.js'
import { renderMarkdown } from '../utils/markdown.js'
import { useAgentStore } from '../stores/agent.js'

const store = useAgentStore()

// ===== 响应式状态 =====
const visible = ref(false)
const step = ref('input')          // 'input' | 'reviewing' | 'report' | 'history'
const userFeedback = ref('')
const reviewing = ref(false)
const currentPhase = ref('')       // 'collect' | 'diagnose' | 'summary'
const progressLogs = ref([])
const reportContent = ref('')
const dataPreview = ref(null)
const historyList = ref([])
const expertDiagnoses = ref([])  // 各专家原始诊断
const currentReviewId = ref('')  // 当前评审 ID
const logRef = ref(null)
let abortController = null

// ===== 对外暴露 =====
const props = defineProps({
  conversationId: { type: String, default: '' }
})

// ===== 监听弹窗打开 =====
watch(visible, (val) => {
  if (val) {
    step.value = 'input'
    userFeedback.value = ''
    reviewing.value = false
    currentPhase.value = ''
    progressLogs.value = []
    reportContent.value = ''
    dataPreview.value = null
    // 预加载数据预览（可选，这里不预加载，启动评审时才有）
  }
})

// ===== 工具函数 =====

function statusLabel(status) {
  const map = {
    collecting: '采集中',
    diagnosing: '诊断中',
    summarizing: '汇总中',
    completed: '已完成'
  }
  return map[status] || status
}

function getStepClass(stepName) {
  const phaseOrder = { collect: 0, diagnose: 1, summary: 2 }
  const currentOrder = phaseOrder[currentPhase.value] ?? -1
  const stepOrder = phaseOrder[stepName] ?? 0
  if (stepOrder < currentOrder) return 'done'
  if (stepOrder === currentOrder) return 'active'
  return 'pending'
}

function getStepIcon(stepName) {
  const cls = getStepClass(stepName)
  if (cls === 'done') return '✅'
  if (cls === 'active') return '⏳'
  return '○'
}

function addLog(text, type = 'info', icon = '📋') {
  progressLogs.value.push({ text, type, icon })
  nextTick(() => {
    const el = logRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

// ===== 启动评审 =====
async function handleStartReview() {
  if (!props.conversationId) {
    ElMessage.warning('未找到当前项目 ID')
    return
  }
  step.value = 'reviewing'
  reviewing.value = true
  currentPhase.value = 'collect'
  progressLogs.value = []
  abortController = new AbortController()

  addLog('**评审已启动** — 正在采集七维度运行数据...', 'start', '🚀')

  try {
    const response = await api.metaTeamReviewStream(
      props.conversationId,
      userFeedback.value,
      store.defaultConfigId,
      abortController.signal
    )
    if (!response.ok) throw new Error('请求失败: ' + response.status)
    await readSSEStream(response)
  } catch (e) {
    if (e.name === 'AbortError') {
      addLog('**评审已中止**', 'abort', '⏹️')
    } else {
      console.error('评审失败:', e)
      ElMessage.error('评审失败：' + (e.message || '网络错误'))
      addLog(`**评审失败**：${e.message || '网络错误'}`, 'error', '❌')
    }
  } finally {
    reviewing.value = false
    abortController = null
  }
}

// ===== 读取 SSE 流 =====
async function readSSEStream(response) {
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
          handleSSEEvent(currentEvent, currentData)
        }
        currentEvent = ''
        currentData = ''
      }
    }
  }
  if (currentEvent && currentData) handleSSEEvent(currentEvent, currentData)
}

// ===== 处理 SSE 事件 =====
function handleSSEEvent(event, dataStr) {
  let data
  try { data = JSON.parse(dataStr) } catch (e) { return }

  switch (event) {
    case 'review_start':
      addLog(`评审 ID：\`${data.review_id}\``, 'info', '📝')
      break

    case 'input_collected':
      currentPhase.value = 'diagnose'
      dataPreview.value = data
      addLog(
        `**数据采集完成** — 成员 ${data.member_count} 个、任务 ${data.task_total} 个、消息 ${data.message_total} 条、异常 ${data.anomaly_count} 个`,
        'success', '✅'
      )
      break

    case 'expert_start':
      addLog(`**${data.expert_name}** 开始诊断...`, 'info', '⏳')
      break

    case 'expert_complete':
      if (data.success) {
        addLog(`**${data.expert_name}** 诊断完成（${data.content_length}字）`, 'success', '✅')
      } else {
        addLog(`**${data.expert_name}** 诊断失败：${data.error || '未知错误'}`, 'error', '❌')
      }
      break

    case 'diagnosis_complete':
      addLog(`**诊断阶段完成** — 成功 ${data.success_count}/${data.total}`, 'success', '🎉')
      currentPhase.value = 'summary'
      break

    case 'summary_start':
      addLog('**主智能体正在汇总报告...**', 'info', '🔀')
      reportContent.value = ''
      break

    case 'token':
      reportContent.value += data.content || ''
      break

    case 'review_complete':
      addLog('**评审完成** — 报告已生成', 'success', '🎉')
      currentReviewId.value = data.review_id || ''
      break

    case 'experience_recorded':
      addLog('专家评审经验已记录', 'info', '📝')
      break

    case 'error':
      addLog(`**错误**：${data.message}`, 'error', '❌')
      ElMessage.error(data.message || '评审出错')
      break

    case 'done':
      if (reportContent.value) {
        step.value = 'report'
        // 加载完整诊断数据
        if (currentReviewId.value) {
          loadExpertDiagnoses(currentReviewId.value)
        }
      }
      break
  }
}

// ===== 中止评审 =====
function handleAbort() {
  if (abortController) {
    abortController.abort()
  }
}

// 组件卸载时中止正在进行的 SSE 请求，防止内存泄漏
onBeforeUnmount(() => {
  if (abortController) {
    abortController.abort()
  }
})

// ===== 关闭弹窗 =====
function handleClose() {
  if (reviewing.value) {
    handleAbort()
  }
}

// ===== 加载专家诊断数据 =====
async function loadExpertDiagnoses(reviewId) {
  try {
    const res = await api.getMetaTeamReview(reviewId)
    expertDiagnoses.value = res.data.review?.expert_diagnoses || []
  } catch (e) {
    console.error('加载专家诊断失败:', e)
  }
}

// ===== 导出评审报告 =====
function handleExportReport() {
  if (!reportContent.value) {
    ElMessage.warning('暂无报告可导出')
    return
  }
  // 构建完整的 Markdown 文件内容
  const header = `# 元团队评审报告\n\n> 导出时间：${new Date().toLocaleString('zh-CN')}\n> 项目：${props.conversationId || '未知'}\n\n---\n\n`
  const fullContent = header + reportContent.value
  // 创建 Blob 并触发下载
  const blob = new Blob([fullContent], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `meta_team_review_${new Date().toISOString().slice(0, 10)}.md`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  ElMessage.success('报告已导出')
}

// ===== 查看历史评审 =====
async function handleViewHistory() {
  try {
    const res = await api.listMetaTeamReviews(props.conversationId)
    historyList.value = res.data.reviews || []
    step.value = 'history'
  } catch (e) {
    ElMessage.error('加载历史评审失败：' + (e.response?.data?.detail || e.message))
  }
}

// ===== 查看历史报告 =====
async function handleViewReport(reviewId) {
  try {
    const res = await api.getMetaTeamReview(reviewId)
    const review = res.data.review
    if (review.report) {
      reportContent.value = review.report
      expertDiagnoses.value = review.expert_diagnoses || []
      step.value = 'report'
    } else {
      ElMessage.warning('该评审尚无报告')
    }
  } catch (e) {
    ElMessage.error('加载评审报告失败：' + (e.response?.data?.detail || e.message))
  }
}

// ===== 启动新设计任务 =====
function handleStartNewDesign() {
  visible.value = false
  // 切换到团队设计视图
  store.sidebarView = 'meta-team'
  ElMessage.info('已切换到团队设计模块，请新建设计任务')
}

// ===== 对外暴露方法 =====
defineExpose({
  open() { visible.value = true },
  close() { visible.value = false }
})
</script>

<style scoped>
.review-dialog :deep(.el-dialog__body) {
  padding: 16px 24px;
  max-height: 70vh;
  overflow-y: auto;
}

/* 通用 section header */
.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.section-icon { font-size: 20px; }
.section-title { font-size: 16px; font-weight: 600; }

/* 步骤 1：输入区 */
.review-input-section .section-desc {
  color: var(--text-secondary, #909399);
  font-size: 13px;
  line-height: 1.6;
  margin: 0 0 16px;
}
.data-preview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
  padding: 16px;
  background: var(--bg-hover, #f5f7fa);
  border-radius: 8px;
}
.preview-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: center;
}
.preview-label {
  font-size: 12px;
  color: var(--text-secondary, #909399);
}
.preview-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary, #303133);
}
.preview-value.has-anomaly {
  color: var(--el-color-warning);
}
.feedback-section {
  margin-bottom: 20px;
}
.feedback-label {
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 500;
}
.feedback-input :deep(.el-textarea__inner) {
  font-size: 13px;
}

/* 步骤 2：进度区 */
.progress-steps {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  margin-bottom: 20px;
  padding: 16px;
}
.step-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}
.step-item.pending { color: var(--text-secondary, #c0c4cc); }
.step-item.active { color: var(--el-color-primary); font-weight: 600; }
.step-item.done { color: var(--el-color-success); }
.step-icon { font-size: 16px; }
.step-connector {
  width: 40px;
  height: 2px;
  background: var(--border-light, #e4e7ed);
  margin: 0 8px;
}
.step-connector.active {
  background: var(--el-color-primary);
}
.progress-log {
  max-height: 300px;
  overflow-y: auto;
  padding: 12px;
  background: var(--bg-hover, #f5f7fa);
  border-radius: 8px;
  margin-bottom: 16px;
}
.log-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 4px 0;
  font-size: 13px;
  line-height: 1.6;
}
.log-icon { flex-shrink: 0; }
.log-text { flex: 1; word-break: break-word; }
.log-item.error .log-text { color: var(--el-color-danger); }
.log-item.success .log-text { color: var(--el-color-success); }
.log-text :deep(p) { margin: 0; }
.log-text :deep(strong) { font-weight: 600; }
.log-text :deep(code) {
  background: rgba(0,0,0,0.05);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 12px;
}

/* 步骤 3：报告区 */
.report-content {
  font-size: 14px;
  line-height: 1.8;
  padding: 16px;
  background: var(--bg-hover, #fafafa);
  border-radius: 8px;
  margin-bottom: 16px;
  max-height: 400px;
  overflow-y: auto;
}
.post-actions {
  padding: 16px;
  background: var(--el-color-primary-light-9, #ecf5ff);
  border-radius: 8px;
}
/* 专家诊断对比 */
.diagnoses-section {
  margin-bottom: 16px;
}
.diag-item {
  padding: 12px;
  background: var(--bg-hover, #fafafa);
  border-radius: 6px;
  margin-bottom: 12px;
  border-left: 3px solid var(--el-color-primary);
}
.diag-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.diag-name {
  font-weight: 600;
  font-size: 14px;
}
.diag-len {
  font-size: 12px;
  color: var(--text-secondary, #909399);
}
.diag-content {
  font-size: 13px;
  line-height: 1.6;
}
.action-hint {
  font-size: 13px;
  color: var(--text-secondary, #606266);
  margin-bottom: 8px;
}
.action-buttons {
  display: flex;
  gap: 8px;
}

/* 历史记录 */
.review-history-section .empty-tip {
  text-align: center;
  color: var(--text-secondary, #c0c4cc);
  padding: 40px 0;
}
.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
}
.history-item:hover {
  background: var(--bg-hover, #f5f7fa);
}
.history-info {
  display: flex;
  gap: 8px;
  align-items: center;
}
.history-status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
}
.history-status.completed {
  background: var(--el-color-success-light-9);
  color: var(--el-color-success);
}
.history-status.collecting,
.history-status.diagnosing,
.history-status.summarizing {
  background: var(--el-color-warning-light-9);
  color: var(--el-color-warning);
}
.history-date {
  font-size: 12px;
  color: var(--text-secondary, #909399);
}
.history-report-icon {
  font-size: 12px;
  color: var(--el-color-primary);
}

/* 通用 */
.action-row {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}
</style>
