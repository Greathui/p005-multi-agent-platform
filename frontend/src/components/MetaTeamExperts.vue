<template>
  <!-- 专家详情对话框 -->
  <el-dialog
    v-model="detailVisible"
    :title="`专家详情：${detailExpert?.name || ''}`"
    width="720px"
    append-to-body
    :close-on-click-modal="false"
    class="detail-dialog"
    @close="handleDetailClose"
  >
      <div v-if="detailLoading" class="state-box">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span class="state-text">加载专家详情...</span>
      </div>

      <div v-else-if="detailExpert" class="detail-content">
        <!-- 基本信息 -->
        <div class="detail-section">
          <div class="section-title">基本信息</div>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">专家名称</span>
              <span class="info-val">{{ detailExpert.name }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">提示词版本</span>
              <span class="info-val">v{{ detailExpert.prompt_version }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">经验次数</span>
              <span class="info-val">{{ detailExpert.experience_count || 0 }} 次</span>
            </div>
            <div class="info-item">
              <span class="info-label">平均得分</span>
              <span class="info-val" :class="scoreClass(detailExpert.avg_score)">
                {{ detailExpert.avg_score != null ? Number(detailExpert.avg_score).toFixed(1) : '-' }}
              </span>
            </div>
          </div>
        </div>

        <!-- 当前 System Prompt -->
        <div class="detail-section">
          <div class="section-title">当前 System Prompt（v{{ detailExpert.prompt_version }}）</div>
          <el-collapse>
            <el-collapse-item title="点击展开 / 折叠提示词内容" name="prompt">
              <pre class="prompt-preview">{{ detailExpert.system_prompt || '（无提示词内容）' }}</pre>
            </el-collapse-item>
          </el-collapse>
        </div>

        <!-- 提示词版本历史 -->
        <div class="detail-section">
          <div class="section-title">
            提示词版本历史
            <el-button text size="small" @click="loadPromptHistory" :loading="historyLoading">
              {{ historyLoading ? '加载中...' : '刷新' }}
            </el-button>
          </div>
          <div v-if="promptHistory.length === 0 && !historyLoading" class="empty-records">
            暂无版本历史（点击"刷新"加载）
          </div>
          <div v-else class="version-timeline">
            <div
              v-for="item in promptHistory"
              :key="item.version"
              class="version-item"
              :class="{ current: item.is_current }"
            >
              <div class="version-header">
                <span class="version-tag" :class="{ current: item.is_current }">
                  v{{ item.version }}{{ item.is_current ? '（当前）' : '' }}
                </span>
                <span class="version-date">{{ item.upgraded_at || '未知时间' }}</span>
                <el-button
                  v-if="!item.is_current"
                  text
                  size="small"
                  type="warning"
                  @click="handleRollback(item.version)"
                >
                  回退到此版本
                </el-button>
              </div>
              <div class="version-reason">{{ item.upgrade_reason || '无说明' }}</div>
              <el-collapse>
                <el-collapse-item title="查看提示词内容" :name="`v${item.version}`">
                  <pre class="prompt-preview">{{ item.system_prompt || '（无内容）' }}</pre>
                </el-collapse-item>
              </el-collapse>
            </div>
          </div>
        </div>

        <!-- 经验记录 -->
        <div class="detail-section">
          <div class="section-title">经验记录（{{ experienceRecords.length }} 条）</div>
          <div v-if="experienceRecords.length === 0" class="empty-records">暂无经验记录</div>
          <div v-else class="record-list">
            <div v-for="record in experienceRecords" :key="record.record_id" class="record-card">
              <div class="record-header">
                <span class="record-title">{{ record.task_title || '未命名任务' }}</span>
                <el-tag size="small" :type="scoreTagType(record.score_received)" effect="light">
                  {{ record.score_received != null ? Number(record.score_received).toFixed(1) : '-' }} 分
                </el-tag>
              </div>
              <div class="record-time">{{ formatDate(record.created_at) }}</div>

              <!-- 评分明细 -->
              <div class="record-breakdown" v-if="record.score_breakdown && Object.keys(record.score_breakdown).length > 0">
                <span class="sub-label">评分明细</span>
                <div class="breakdown-chips">
                  <span v-for="(val, key) in record.score_breakdown" :key="key" class="breakdown-chip" :class="scoreClass(val)">
                    {{ key }} <strong>{{ val }}</strong>
                  </span>
                </div>
              </div>

              <!-- 评审意见 -->
              <div class="record-feedback" v-if="record.feedback_summary">
                <span class="sub-label">评审意见</span>
                <p class="feedback-text">{{ record.feedback_summary }}</p>
              </div>

              <!-- 采纳情况 -->
              <div class="record-adoption" v-if="(record.fusion_adopted && record.fusion_adopted.length > 0) || (record.fusion_not_adopted && record.fusion_not_adopted.length > 0)">
                <div v-if="record.fusion_adopted && record.fusion_adopted.length > 0" class="adopt-line">
                  <span class="sub-label adopted-label">已采纳</span>
                  <span v-for="(item, i) in record.fusion_adopted" :key="'a'+i" class="adopt-chip adopted">{{ item }}</span>
                </div>
                <div v-if="record.fusion_not_adopted && record.fusion_not_adopted.length > 0" class="adopt-line">
                  <span class="sub-label not-adopted-label">未采纳</span>
                  <span v-for="(item, i) in record.fusion_not_adopted" :key="'n'+i" class="adopt-chip not-adopted">{{ item }}</span>
                </div>
              </div>

              <!-- 产出文件查看 -->
              <div class="record-output-actions" v-if="record.task_id">
                <span class="sub-label">产出文件</span>
                <div class="output-btns">
                  <el-button text size="small" @click="viewOutput(record, 'proposal')" :loading="outputLoading === record.record_id + '-proposal'">
                    📄 查看方案
                  </el-button>
                  <el-button text size="small" @click="viewOutput(record, 'review')" :loading="outputLoading === record.record_id + '-review'">
                    📝 查看评审
                  </el-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="detail-footer">
          <el-button type="danger" plain @click="handleDeleteExpert" :loading="deleting">
            删除专家
          </el-button>
          <el-button @click="detailVisible = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 产出文件查看对话框 -->
    <el-dialog
      v-model="outputVisible"
      :title="outputTitle"
      width="760px"
      append-to-body
      :close-on-click-modal="true"
      class="output-dialog"
    >
      <div v-if="outputLoading" class="output-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在加载文件内容...</span>
      </div>
      <div v-else-if="outputContent" class="output-content markdown-body" v-html="renderMarkdown(outputContent)"></div>
      <div v-else class="output-empty">
        <div class="empty-icon-small">📄</div>
        <p>文件内容为空或不存在</p>
      </div>
      <template #footer>
        <el-button @click="outputVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 提示词优化对话框 -->
    <el-dialog
      v-model="optimizeVisible"
      :title="`优化提示词：${optimizeExpert?.name || ''}`"
      width="760px"
      append-to-body
      :close-on-click-modal="false"
      class="optimize-dialog"
      @close="handleOptimizeClose"
    >
      <div class="optimize-content">
        <!-- 当前版本信息 -->
        <div class="optimize-meta">
          <span class="meta-item">当前版本：<strong>v{{ optimizeExpert?.prompt_version || 0 }}</strong></span>
          <span class="meta-item" v-if="optimizeExpert?.avg_score != null">
            平均得分：<strong :class="scoreClass(optimizeExpert.avg_score)">{{ Number(optimizeExpert.avg_score).toFixed(1) }}</strong>
          </span>
          <span class="meta-item" v-if="optimizeExpert?.experience_count">
            经验记录：<strong>{{ optimizeExpert.experience_count }} 次</strong>
          </span>
        </div>

        <!-- 分析区域 -->
        <div class="optimize-section">
          <div class="section-header">
            <span class="section-title">优化分析</span>
            <div class="section-actions">
              <el-button
                v-if="!optimizing && !optimizeAnalysis"
                size="small"
                type="primary"
                @click="startOptimize"
              >开始分析</el-button>
              <el-button
                v-if="optimizing"
                size="small"
                type="danger"
                @click="cancelOptimize"
              >停止</el-button>
              <el-button
                v-if="!optimizing && optimizeAnalysis"
                size="small"
                @click="startOptimize"
              >重新分析</el-button>
            </div>
          </div>

          <div v-if="optimizeAnalysis || optimizing" class="analysis-box">
            <div class="analysis markdown-body" v-html="renderMarkdown(optimizeAnalysis)"></div>
            <div v-if="optimizing" class="analyzing-indicator">
              <span class="typing-dots"><span></span><span></span><span></span></span>
              <span>分析中...</span>
            </div>
          </div>
          <div v-else class="analysis-empty">
            <div class="empty-icon-small">🔍</div>
            <p>点击「开始分析」，AI 将结合当前提示词与历史经验记录，生成优化建议和新的提示词</p>
          </div>
        </div>

        <!-- 新提示词编辑区域 -->
        <div class="optimize-section" v-if="extractedPrompt !== null">
          <div class="section-header">
            <span class="section-title">优化后的提示词（可编辑）</span>
            <el-button
              v-if="optimizeExpert?.system_prompt"
              size="small"
              text
              @click="extractedPrompt = optimizeExpert.system_prompt"
            >填入当前提示词</el-button>
          </div>
          <el-input
            v-model="extractedPrompt"
            type="textarea"
            :rows="10"
            placeholder="优化后的提示词内容，可在此编辑修改"
            style="font-family: Consolas, Monaco, monospace; font-size: 12px"
          />
          <div class="optimize-reason">
            <span class="reason-label">升级原因（将记录到版本历史）</span>
            <el-input
              v-model="optimizationReason"
              type="textarea"
              :rows="3"
              placeholder="说明本次优化的原因和改进点，如：根据低分项加强需求匹配约束"
            />
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="optimizeVisible = false">关闭</el-button>
        <el-button
          v-if="extractedPrompt !== null"
          type="primary"
          @click="confirmUpgrade"
          :loading="upgrading"
        >确认升级到 v{{ (optimizeExpert?.prompt_version || 0) + 1 }}</el-button>
      </template>
    </el-dialog>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import api from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { useAgentStore } from '../stores/agent'
import { renderMarkdown } from '../utils/markdown'

const props = defineProps({
  modelValue: Boolean,
  focusExpertId: { type: String, default: '' },
  openOptimize: { type: Boolean, default: false }  // true 时直接打开优化弹窗
})
const emit = defineEmits(['update:modelValue', 'expert-deleted'])

const store = useAgentStore()

// 弹窗显隐双向绑定
const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

// 专家列表状态
const experts = ref([])
const loading = ref(false)
const modelConfigs = ref([])

// 详情对话框状态
const detailVisible = ref(false)
const detailExpert = ref(null)
const detailLoading = ref(false)

// 版本历史状态
const promptHistory = ref([])
const historyLoading = ref(false)

// 产出文件查看状态
const outputVisible = ref(false)
const outputContent = ref('')
const outputTitle = ref('')
const outputLoading = ref('')  // 格式：record_id + '-proposal' / '-review'，空字符串表示未加载

// 优化对话框状态
const optimizeVisible = ref(false)
const optimizeExpert = ref(null)
const optimizing = ref(false)
const optimizeAnalysis = ref('')
const extractedPrompt = ref(null)
const optimizationReason = ref('')
const upgrading = ref(false)
let abortController = null

// 经验记录列表（兼容 experience_log / experiences 两种字段名）
const experienceRecords = computed(() => {
  if (!detailExpert.value) return []
  return detailExpert.value.experience_log || detailExpert.value.experiences || []
})

// 弹窗打开时自动加载
watch(() => props.modelValue, async (val) => {
  if (val) {
    await loadModelConfigs()
    // 如果指定了 focusExpertId，直接打开该专家的详情
    if (props.focusExpertId) {
      await nextTick()
      await openDetail({ id: props.focusExpertId, name: '' })
      // 如果 openOptimize=true，详情加载完成后自动打开优化弹窗
      if (props.openOptimize && detailExpert.value) {
        openOptimize(detailExpert.value)
      }
    }
  }
})

// 加载专家列表
async function loadExperts() {
  loading.value = true
  try {
    await store.loadMetaTeamExperts()
    // 复制到本地并附加下拉框绑定字段，避免直接修改 store
    experts.value = (store.metaTeamExperts || []).map(e => ({
      ...e,
      _modelConfigId: e.model_config?.config_id || ''
    }))
  } catch (e) {
    ElMessage.error('加载专家列表失败：' + (e.response?.data?.detail || e.message || '网络错误'))
  } finally {
    loading.value = false
  }
}

// 加载模型配置列表（用于下拉框）
async function loadModelConfigs() {
  try {
    const res = await api.getModelConfigs()
    modelConfigs.value = res.data.configs || []
  } catch (e) {
    console.error('加载模型配置失败:', e)
  }
}

// 更新专家绑定的模型配置
async function handleModelChange(expert, configId) {
  const oldConfigId = expert.model_config?.config_id || ''
  try {
    await api.updateMetaTeamExpert(expert.id, {
      name: expert.name,
      model_config_id: configId || null
    })
    // 同步本地状态
    expert.model_config = configId ? { config_id: configId } : null
    ElMessage.success(configId ? '模型配置已绑定' : '已解除模型绑定')
  } catch (e) {
    // 回滚下拉框选中值
    expert._modelConfigId = oldConfigId
    ElMessage.error('更新失败：' + (e.response?.data?.detail || e.message || '网络错误'))
  }
}

// 详情弹窗关闭时，同时关闭外层弹窗
function handleDetailClose() {
  visible.value = false
}

// 删除专家
const deleting = ref(false)
async function handleDeleteExpert() {
  if (!detailExpert.value) return
  const expert = detailExpert.value
  try {
    await ElMessageBox.confirm(
      `确定删除专家「${expert.name}」吗？该操作不可恢复，专家的经验记录和提示词版本历史将一并删除。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
  } catch {
    return  // 用户取消
  }
  deleting.value = true
  try {
    await api.deleteMetaTeamExpert(expert.id)
    ElMessage.success('专家已删除')
    detailVisible.value = false
    visible.value = false
    // 通知父组件（首页）刷新卡片
    emit('expert-deleted', expert.id)
  } catch (e) {
    ElMessage.error('删除失败：' + (e.response?.data?.detail || e.message || '网络错误'))
  } finally {
    deleting.value = false
  }
}

// 打开详情对话框
async function openDetail(expert) {
  detailVisible.value = true
  detailLoading.value = true
  detailExpert.value = null
  promptHistory.value = []
  try {
    const res = await api.getMetaTeamExpert(expert.id)
    detailExpert.value = res.data.expert || res.data
    // 自动加载版本历史
    await loadPromptHistory()
  } catch (e) {
    ElMessage.error('加载详情失败：' + (e.response?.data?.detail || e.message || '网络错误'))
  } finally {
    detailLoading.value = false
  }
}

// 加载提示词版本历史
async function loadPromptHistory() {
  if (!detailExpert.value) return
  historyLoading.value = true
  try {
    const res = await api.getMetaTeamExpertPromptHistory(detailExpert.value.id)
    promptHistory.value = res.data.history || []
  } catch (e) {
    console.error('加载版本历史失败:', e)
  } finally {
    historyLoading.value = false
  }
}

// 回退到指定版本
async function handleRollback(targetVersion) {
  try {
    await ElMessageBox.confirm(
      `确定要回退到 v${targetVersion} 版本吗？当前版本将被保存到历史记录中。`,
      '确认回退',
      { type: 'warning' }
    )
  } catch (_) {
    return  // 用户取消
  }
  try {
    const res = await api.rollbackMetaTeamExpertPrompt(detailExpert.value.id, targetVersion)
    ElMessage.success(res.data.message || '回退成功')
    // 刷新详情和历史
    await openDetail(detailExpert.value)
  } catch (e) {
    ElMessage.error('回退失败：' + (e.response?.data?.detail || e.message || '网络错误'))
  }
}

// 查看专家在设计任务中的产出文件（方案或评审）
async function viewOutput(record, type) {
  // type: 'proposal' 方案 | 'review' 评审
  const loadingKey = record.record_id + '-' + type
  outputLoading.value = loadingKey
  outputContent.value = ''
  outputTitle.value = ''

  try {
    const expertId = detailExpert.value?.id
    if (!expertId) {
      ElMessage.warning('未找到当前专家 ID')
      return
    }
    let res
    if (type === 'proposal') {
      res = await api.getMetaTeamProposal(record.task_id, expertId)
      outputTitle.value = `📄 方案文件 — ${res.data.expert_name}（${record.task_title || '未命名任务'}）`
    } else {
      res = await api.getMetaTeamReviewFile(record.task_id, expertId)
      outputTitle.value = `📝 评审文件 — ${res.data.expert_name}（${record.task_title || '未命名任务'}）`
    }
    outputContent.value = res.data.content || ''
    outputVisible.value = true
  } catch (e) {
    if (e.response?.status === 404) {
      ElMessage.info('该任务中未找到此专家的' + (type === 'proposal' ? '方案' : '评审') + '文件')
    } else {
      ElMessage.error('加载失败：' + (e.response?.data?.detail || e.message || '网络错误'))
    }
  } finally {
    outputLoading.value = ''
  }
}

// 打开优化对话框
function openOptimize(expert) {
  optimizeVisible.value = true
  optimizeExpert.value = { ...expert }
  optimizeAnalysis.value = ''
  extractedPrompt.value = null
  optimizationReason.value = ''
  optimizing.value = false
}

// 开始 SSE 流式优化分析
async function startOptimize() {
  if (!optimizeExpert.value) return
  optimizing.value = true
  optimizeAnalysis.value = ''
  extractedPrompt.value = null
  optimizationReason.value = ''

  abortController = new AbortController()

  try {
    const response = await api.metaTeamOptimizePromptStream(
      optimizeExpert.value.id,
      store.defaultConfigId,
      abortController.signal
    )

    if (!response.ok) {
      throw new Error('请求失败: ' + response.status)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let currentEvent = null
    let currentData = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim()
          currentData = ''
        } else if (line.startsWith('data: ')) {
          currentData += line.slice(6)
        } else if (line === '' && currentEvent) {
          try {
            const data = JSON.parse(currentData)
            handleOptimizeSSE(currentEvent, data)
          } catch (e) {
            console.error('SSE 解析错误:', e)
          }
          currentEvent = null
          currentData = ''
        }
      }
    }
  } catch (e) {
    if (e.name !== 'AbortError') {
      ElMessage.error('优化分析失败：' + (e.message || '网络错误'))
    }
  } finally {
    optimizing.value = false
    abortController = null
  }
}

// 取消优化分析
function cancelOptimize() {
  if (abortController) {
    abortController.abort()
  }
  optimizing.value = false
}

// 处理 SSE 事件
function handleOptimizeSSE(event, data) {
  switch (event) {
    case 'agent_start':
      // 分析开始，清空内容
      optimizeAnalysis.value = ''
      break
    case 'token':
      if (data.content) {
        optimizeAnalysis.value += data.content
      }
      break
    case 'agent_end': {
      // 分析完成，用完整内容替换并提取提示词
      if (data.full_content) {
        optimizeAnalysis.value = data.full_content
      }
      // 从 markdown 代码块中提取优化后的提示词
      const prompt = extractPromptFromAnalysis(optimizeAnalysis.value)
      if (prompt) {
        extractedPrompt.value = prompt
      } else {
        // 未能自动提取，给空值让用户手动编辑
        extractedPrompt.value = ''
        ElMessage.warning('未能自动提取提示词，请手动粘贴或编辑')
      }
      break
    }
    case 'done':
      // 全部完成
      break
    case 'error':
      ElMessage.error(data.message || '分析过程出错')
      break
  }
}

// 从分析结果的 markdown 代码块中提取优化后的提示词
function extractPromptFromAnalysis(text) {
  if (!text) return ''
  // 匹配所有 ``` 代码块（含可选语言标记）
  const codeBlockRegex = /```(?:[a-zA-Z]*)\n?([\s\S]*?)```/g
  const matches = []
  let match
  while ((match = codeBlockRegex.exec(text)) !== null) {
    const content = match[1].trim()
    if (content) matches.push(content)
  }
  if (matches.length === 0) return ''
  // 返回最长的代码块内容（通常是完整的提示词）
  return matches.reduce((longest, current) =>
    current.length > longest.length ? current : longest, '')
}

// 确认升级提示词版本
async function confirmUpgrade() {
  if (!optimizeExpert.value || !extractedPrompt.value) {
    ElMessage.warning('请先完成优化分析并填写新提示词')
    return
  }

  const currentVersion = optimizeExpert.value.prompt_version || 0
  const nextVersion = currentVersion + 1

  try {
    await ElMessageBox.confirm(
      `确认将「${optimizeExpert.value.name}」的提示词从 v${currentVersion} 升级到 v${nextVersion}？\n\n升级后新任务将使用新版本提示词，历史经验记录保留。`,
      '升级确认',
      {
        type: 'warning',
        confirmButtonText: '确认升级',
        cancelButtonText: '取消',
        dangerouslyUseHTMLString: false
      }
    )
  } catch {
    return // 用户取消
  }

  upgrading.value = true
  try {
    await api.upgradeMetaTeamExpertPrompt(optimizeExpert.value.id, {
      new_prompt: extractedPrompt.value,
      optimization_reason: optimizationReason.value || '基于历史经验自动优化'
    })
    ElMessage.success(`提示词已升级到 v${nextVersion}`)
    optimizeVisible.value = false
    // 刷新专家列表
    await loadExperts()
  } catch (e) {
    ElMessage.error('升级失败：' + (e.response?.data?.detail || e.message || '网络错误'))
  } finally {
    upgrading.value = false
  }
}

// 关闭优化对话框时清理
function handleOptimizeClose() {
  if (optimizing.value && abortController) {
    abortController.abort()
  }
  optimizing.value = false
  optimizeAnalysis.value = ''
  extractedPrompt.value = null
  optimizationReason.value = ''
}

// 根据得分返回样式类名
function scoreClass(score) {
  if (score == null) return 'score-none'
  if (score >= 8) return 'score-high'
  if (score >= 6) return 'score-mid'
  return 'score-low'
}

// 根据得分返回 el-tag 类型
function scoreTagType(score) {
  if (score == null) return 'info'
  if (score >= 8) return 'success'
  if (score >= 6) return 'warning'
  return 'danger'
}

// 格式化日期
function formatDate(iso) {
  if (!iso) return '-'
  return iso.replace('T', ' ').substring(0, 16)
}

// 根据专家名称生成头像 emoji
const avatarPool = ['🧠', '🎨', '📐', '🔧', '📊', '💡', '🎯', '🏗️']
function getExpertAvatar(expert) {
  if (!expert || !expert.id) return '👤'
  // 根据 id 哈希到头像池
  let hash = 0
  const str = expert.id + (expert.name || '')
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash)
  }
  return avatarPool[Math.abs(hash) % avatarPool.length]
}
</script>

<style scoped>
/* 主弹窗 */
.experts-dialog :deep(.el-dialog__body) {
  padding: 0 20px 20px;
  max-height: 70vh;
  overflow-y: auto;
}

.experts-dialog :deep(.el-dialog__body::-webkit-scrollbar) {
  width: 6px;
}

.experts-dialog :deep(.el-dialog__body::-webkit-scrollbar-thumb) {
  background: var(--border-color);
  border-radius: 3px;
}

/* 工具栏 */
.experts-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0 16px;
  border-bottom: 1px solid var(--border-light);
  margin-bottom: 16px;
}

.toolbar-tip {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

/* 状态盒子（加载/空） */
.state-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: var(--text-tertiary);
  gap: 12px;
}

.state-box .is-loading {
  font-size: 28px;
  color: var(--primary);
}

.state-text {
  font-size: 14px;
}

.state-box.empty .empty-icon {
  font-size: 48px;
  opacity: 0.6;
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.empty-desc {
  font-size: 13px;
  color: var(--text-tertiary);
  text-align: center;
  max-width: 420px;
  line-height: 1.6;
}

/* 专家卡片列表 */
.expert-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.expert-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--space-lg);
  transition: all var(--transition-fast);
  box-shadow: var(--shadow-sm);
}

.expert-card:hover {
  border-color: var(--primary-light);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

/* 卡片头部 */
.card-header {
  display: flex;
  align-items: flex-start;
  gap: var(--space-md);
}

.expert-avatar {
  font-size: 28px;
  width: 48px;
  height: 48px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--bg-active) 0%, #f3e8ff 100%);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.expert-main {
  flex: 1;
  min-width: 0;
}

.expert-name-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: 6px;
  flex-wrap: wrap;
}

.expert-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.expert-stats {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}

.stat-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.stat-label {
  color: var(--text-tertiary);
}

.stat-val {
  font-weight: 600;
  color: var(--text-primary);
}

.stat-sep {
  color: var(--text-muted);
}

.card-actions {
  display: flex;
  gap: var(--space-sm);
  flex-shrink: 0;
}

/* 得分趋势 */
.card-trend {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  margin-top: var(--space-md);
  padding-top: var(--space-md);
  border-top: 1px dashed var(--border-light);
}

.trend-label {
  font-size: 12px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.trend-scores {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.score-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 38px;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 600;
  font-family: 'Consolas', 'Monaco', monospace;
}

.score-chip.score-high {
  background: #dcfce7;
  color: #15803d;
}

.score-chip.score-mid {
  background: #fef3c7;
  color: #b45309;
}

.score-chip.score-low {
  background: #fee2e2;
  color: #b91c1c;
}

.score-chip.score-none {
  background: var(--bg-hover);
  color: var(--text-tertiary);
}

.trend-arrow {
  color: var(--text-muted);
  font-size: 12px;
}

/* 模型配置 */
.card-model {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  margin-top: var(--space-md);
}

.model-label {
  font-size: 12px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

/* 得分颜色（文本） */
.score-high {
  color: #15803d;
}

.score-mid {
  color: #b45309;
}

.score-low {
  color: #b91c1c;
}

.score-none {
  color: var(--text-tertiary);
}

/* ========== 详情对话框 ========== */
.detail-dialog :deep(.el-dialog__body) {
  max-height: 72vh;
  overflow-y: auto;
}

.detail-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-xl);
}

.detail-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  padding-left: 10px;
  border-left: 3px solid var(--primary);
}

/* 基本信息网格 */
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-md);
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: var(--space-md);
  background: var(--bg-app);
  border-radius: var(--radius-sm);
}

.info-label {
  font-size: 12px;
  color: var(--text-tertiary);
}

.info-val {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

/* 提示词预览 */
.prompt-preview {
  background: #1e293b;
  color: #e2e8f0;
  padding: var(--space-lg);
  border-radius: var(--radius-sm);
  font-size: 12px;
  line-height: 1.7;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 400px;
  overflow-y: auto;
  margin: 0;
}

/* 经验记录 */
.empty-records {
  padding: var(--space-xl);
  text-align: center;
  color: var(--text-tertiary);
  font-size: 13px;
  background: var(--bg-app);
  border-radius: var(--radius-sm);
}

/* 版本历史时间线 */
.version-timeline {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}
.version-item {
  background: var(--bg-app);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  padding: var(--space-md);
  position: relative;
}
.version-item.current {
  border-color: var(--el-color-success);
  background: var(--el-color-success-light-9, #f0f9eb);
}
.version-item:not(.current)::before {
  content: '';
  position: absolute;
  left: 12px;
  top: -8px;
  width: 2px;
  height: 8px;
  background: var(--border-light);
}
.version-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-xs);
}
.version-tag {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--bg-hover, #f0f0f0);
  color: var(--text-secondary);
}
.version-tag.current {
  background: var(--el-color-success);
  color: white;
}
.version-date {
  font-size: 11px;
  color: var(--text-tertiary);
}
.version-reason {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: var(--space-xs);
  padding-left: var(--space-xs);
}

.record-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.record-card {
  background: var(--bg-app);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  padding: var(--space-md);
}

.record-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
  margin-bottom: 4px;
}

.record-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.record-time {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: var(--space-sm);
}

.record-breakdown,
.record-feedback,
.record-adoption {
  margin-top: var(--space-sm);
}

.sub-label {
  display: inline-block;
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 4px;
}

.breakdown-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.breakdown-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
}

.breakdown-chip strong {
  font-family: 'Consolas', 'Monaco', monospace;
}

.feedback-text {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 4px 0 0;
  padding: var(--space-sm) var(--space-md);
  background: var(--bg-card);
  border-left: 3px solid var(--primary-light);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.adopt-line {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 4px;
}

.adopted-label {
  color: #15803d;
  font-weight: 600;
}

.not-adopted-label {
  color: #b91c1c;
  font-weight: 600;
}

.adopt-chip {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 12px;
}

.adopt-chip.adopted {
  background: #dcfce7;
  color: #15803d;
}

.adopt-chip.not-adopted {
  background: #fee2e2;
  color: #b91c1c;
}

/* ========== 优化对话框 ========== */
.optimize-dialog :deep(.el-dialog__body) {
  max-height: 72vh;
  overflow-y: auto;
}

.optimize-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-xl);
}

.optimize-meta {
  display: flex;
  gap: var(--space-xl);
  padding: var(--space-md) var(--space-lg);
  background: var(--bg-active);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text-secondary);
  flex-wrap: wrap;
}

.meta-item strong {
  color: var(--text-primary);
}

.optimize-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-actions {
  display: flex;
  gap: var(--space-sm);
}

/* 分析结果展示 */
.analysis-box {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: var(--space-lg);
  max-height: 360px;
  overflow-y: auto;
}

.analysis-box::-webkit-scrollbar {
  width: 6px;
}

.analysis-box::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

.analysis-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-xl) var(--space-lg);
  text-align: center;
  background: var(--bg-app);
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-sm);
}

.empty-icon-small {
  font-size: 32px;
  opacity: 0.5;
}

.analysis-empty p {
  font-size: 13px;
  color: var(--text-tertiary);
  line-height: 1.6;
  margin: 0;
  max-width: 440px;
}

.analyzing-indicator {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding-top: var(--space-sm);
  font-size: 13px;
  color: var(--primary);
}

.typing-dots {
  display: inline-flex;
  gap: 3px;
}

.typing-dots span {
  width: 6px;
  height: 6px;
  background: var(--primary);
  border-radius: 50%;
  animation: typingBounce 1.4s infinite ease-in-out both;
}

.typing-dots span:nth-child(1) { animation-delay: -0.32s; }
.typing-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes typingBounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* 新提示词编辑 */
.optimize-reason {
  margin-top: var(--space-md);
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.reason-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}

/* Markdown 渲染样式 */
.analysis.markdown-body {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-primary);
  word-wrap: break-word;
}

.analysis.markdown-body :deep(p) {
  margin: 0 0 0.6em 0;
}

.analysis.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.analysis.markdown-body :deep(h1),
.analysis.markdown-body :deep(h2),
.analysis.markdown-body :deep(h3),
.analysis.markdown-body :deep(h4) {
  margin: 0.8em 0 0.4em 0;
  font-weight: 600;
  color: var(--text-primary);
}

.analysis.markdown-body :deep(h1) { font-size: 1.2em; }
.analysis.markdown-body :deep(h2) { font-size: 1.1em; }
.analysis.markdown-body :deep(h3) { font-size: 1.05em; }

.analysis.markdown-body :deep(ul),
.analysis.markdown-body :deep(ol) {
  padding-left: 1.4em;
  margin: 0.4em 0;
}

.analysis.markdown-body :deep(li) {
  margin: 0.2em 0;
}

.analysis.markdown-body :deep(blockquote) {
  margin: 0.6em 0;
  padding: 0.5em 0.8em;
  border-left: 3px solid var(--primary);
  color: var(--text-secondary);
  background: var(--bg-active);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.analysis.markdown-body :deep(code) {
  font-family: 'Consolas', 'Monaco', monospace;
  background: var(--bg-hover);
  color: var(--primary-dark);
  padding: 0.1em 0.35em;
  border-radius: 4px;
  font-size: 0.88em;
}

.analysis.markdown-body :deep(pre) {
  margin: 0.6em 0;
  border-radius: var(--radius-sm);
  overflow-x: auto;
  background: #1e293b !important;
}

.analysis.markdown-body :deep(pre code) {
  background: none !important;
  color: #e2e8f0;
  padding: 0;
}

.analysis.markdown-body :deep(.hljs) {
  padding: 0.8em !important;
  background: #1e293b !important;
  border-radius: var(--radius-sm);
}

.analysis.markdown-body :deep(table) {
  border-collapse: collapse;
  margin: 0.6em 0;
  width: 100%;
  font-size: 0.9em;
}

.analysis.markdown-body :deep(th),
.analysis.markdown-body :deep(td) {
  border: 1px solid var(--border-color);
  padding: 0.4em 0.7em;
  text-align: left;
}

.analysis.markdown-body :deep(th) {
  background: var(--bg-app);
  font-weight: 600;
}

.analysis.markdown-body :deep(a) {
  color: var(--primary);
  text-decoration: none;
}

.analysis.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid var(--border-color);
  margin: 0.8em 0;
}

/* 折叠面板样式 */
.detail-section :deep(.el-collapse) {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.detail-section :deep(.el-collapse-item__header) {
  padding: 0 var(--space-md);
  font-size: 13px;
  color: var(--text-secondary);
  background: var(--bg-app);
}

.detail-section :deep(.el-collapse-item__content) {
  padding: 0;
}

/* ===== 产出文件查看 ===== */
.record-output-actions {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.output-btns {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

/* 产出文件查看对话框 */
.output-dialog :deep(.el-dialog__body) {
  max-height: 65vh;
  overflow-y: auto;
  padding: 16px 20px;
}

.output-content {
  font-size: 14px;
  line-height: 1.7;
  color: #334155;
}

.output-content :deep(h1),
.output-content :deep(h2),
.output-content :deep(h3) {
  margin-top: 16px;
  margin-bottom: 8px;
  color: #1e293b;
}

.output-content :deep(pre) {
  background: #f8fafc;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 13px;
}

.output-content :deep(code) {
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 13px;
}

.output-content :deep(pre code) {
  background: none;
  padding: 0;
}

.output-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px 0;
  color: #64748b;
}

.output-empty {
  text-align: center;
  padding: 40px 0;
  color: #94a3b8;
}
</style>
