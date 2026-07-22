<template>
  <div class="meta-team-home">
    <!-- 顶部标题区 -->
    <div class="home-header">
      <div class="header-left">
        <div class="header-icon">🎯</div>
        <div>
          <div class="header-title">团队设计</div>
          <div class="header-desc">管理设计专家，创建设计任务，产出团队蓝图</div>
        </div>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="$emit('new-task')">
          + 新建设计任务
        </el-button>
      </div>
    </div>

    <!-- 专家卡片列表 -->
    <div class="experts-section">
      <div class="section-header">
        <span class="section-title">设计专家（{{ experts.length }}）</span>
        <el-button text type="primary" size="small" @click="showCreateExpert = true">
          + 新增专家
        </el-button>
      </div>

      <div v-if="expertsLoading" class="experts-loading">
        <span class="loading-spinner">⏳</span>
        <span>加载专家列表...</span>
      </div>

      <div v-else-if="experts.length === 0" class="experts-empty">
        <div class="empty-icon-small">👥</div>
        <p>还没有专家，点击「新增专家」创建</p>
      </div>

      <div v-else class="experts-grid">
        <div
          v-for="exp in experts"
          :key="exp.id"
          class="expert-card"
          @click="handleEditExpert(exp)"
        >
          <!-- 卡片头部：头像 + 名称 + 标签 -->
          <div class="card-header">
            <span class="card-avatar">{{ getExpertAvatar(exp) }}</span>
            <div class="card-info">
              <div class="card-name-row">
                <span class="card-name">{{ exp.name }}</span>
                <el-tag size="small" type="primary" effect="light" round>v{{ exp.prompt_version }}</el-tag>
                <el-tag v-if="exp.model_config" size="small" type="success" effect="plain">模型已绑定</el-tag>
                <el-tag v-else size="small" type="info" effect="plain">模型未绑定</el-tag>
              </div>
              <div class="card-id">{{ exp.id }}</div>
            </div>
          </div>

          <!-- 统计信息：平均得分 + 经验次数 -->
          <div class="card-stats">
            <span class="stat-item">
              <span class="stat-label">平均得分</span>
              <span class="stat-val" :class="scoreClass(exp.avg_score)">
                {{ exp.avg_score != null ? Number(exp.avg_score).toFixed(1) : '-' }}
              </span>
            </span>
            <span class="stat-sep">·</span>
            <span class="stat-item">
              <span class="stat-label">经验</span>
              <span class="stat-val">{{ exp.experience_count || exp.experience_log?.length || 0 }} 次</span>
            </span>
          </div>

          <!-- 得分趋势 -->
          <div class="card-trend" v-if="exp.recent_scores && exp.recent_scores.length > 0">
            <span class="trend-label">得分趋势</span>
            <div class="trend-scores">
              <template v-for="(s, i) in exp.recent_scores" :key="i">
                <span class="score-chip" :class="scoreClass(s)">{{ Number(s).toFixed(1) }}</span>
                <span v-if="i < exp.recent_scores.length - 1" class="trend-arrow">→</span>
              </template>
            </div>
          </div>

          <!-- 提示词预览 -->
          <div class="card-prompt">
            {{ truncatePrompt(exp.system_prompt) }}
          </div>

          <!-- 模型配置绑定 + 操作按钮 -->
          <div class="card-footer" @click.stop>
            <div class="card-model-row">
              <span class="model-label">模型</span>
              <el-select
                v-model="exp._modelConfigId"
                placeholder="默认配置"
                size="small"
                style="width: 100%"
                @change="(val) => handleModelChange(exp, val)"
              >
                <el-option label="未绑定（默认）" value="" />
                <el-option
                  v-for="cfg in modelConfigs"
                  :key="cfg.config_id"
                  :label="`${cfg.name}（${cfg.model || '未知'}）`"
                  :value="cfg.config_id"
                />
              </el-select>
            </div>
          </div>

          <div class="card-actions" @click.stop>
            <el-button size="small" @click="handleEditExpert(exp)">查看详情</el-button>
            <el-button size="small" type="primary" @click="handleOptimize(exp)">优化提示词</el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 新增专家对话框 -->
    <el-dialog v-model="showCreateExpert" title="新增专家" width="560px">
      <el-form label-position="top" :model="newExpertForm">
        <el-form-item label="专家名称" required>
          <el-input v-model="newExpertForm.name" placeholder="如：团队架构师" />
        </el-form-item>
        <el-form-item label="系统提示词" required>
          <el-input
            v-model="newExpertForm.system_prompt"
            type="textarea"
            :rows="8"
            placeholder="详细描述专家的角色定位、专业能力、工作方式、输出要求等..."
          />
          <div class="form-hint">提示词越详细，专家产出质量越高。可参考已有专家的提示词。</div>
        </el-form-item>
        <el-form-item label="绑定模型配置">
          <el-select
            v-model="newExpertForm.model_config_id"
            placeholder="不选则使用默认模型"
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="cfg in modelConfigs"
              :key="cfg.config_id"
              :label="`${cfg.name}（${cfg.model || '未知'}）`"
              :value="cfg.config_id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateExpert = false">取消</el-button>
        <el-button type="primary" @click="handleCreateExpert" :loading="creatingExpert">
          创建专家
        </el-button>
      </template>
    </el-dialog>

    <!-- 专家详情/优化弹窗 -->
    <MetaTeamExperts
      v-model="expertsDialogVisible"
      :focus-expert-id="focusExpertId"
      :open-optimize="openOptimizeFlag"
      @expert-deleted="handleExpertDeleted"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/index.js'
import { useAgentStore } from '../stores/agent.js'
import MetaTeamExperts from './MetaTeamExperts.vue'

const store = useAgentStore()

defineEmits(['new-task'])

// 专家列表
const experts = ref([])
const expertsLoading = ref(false)
const modelConfigs = ref([])

// 新增专家
const showCreateExpert = ref(false)
const creatingExpert = ref(false)
const newExpertForm = ref({
  name: '',
  system_prompt: '',
  model_config_id: ''
})

// 专家详情弹窗
const expertsDialogVisible = ref(false)
const focusExpertId = ref('')
const openOptimizeFlag = ref(false)  // 是否直接打开优化弹窗

// 头像生成
const avatarPool = ['🧠', '🎨', '📐', '🔧', '📊', '💡', '🎯', '🏗️']
function getExpertAvatar(expert) {
  if (!expert || !expert.id) return '👤'
  let hash = 0
  const str = expert.id + (expert.name || '')
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash)
  }
  return avatarPool[Math.abs(hash) % avatarPool.length]
}

// 截断提示词预览
function truncatePrompt(prompt) {
  if (!prompt) return '暂无提示词'
  const text = prompt.replace(/\n/g, ' ').trim()
  return text.length > 100 ? text.slice(0, 100) + '...' : text
}

// 得分样式
function scoreClass(score) {
  if (score == null) return 'score-none'
  if (score >= 8) return 'score-high'
  if (score >= 6) return 'score-mid'
  return 'score-low'
}

// 加载模型配置列表
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
    expert.model_config = configId ? { config_id: configId } : null
    ElMessage.success(configId ? '模型配置已绑定' : '已解除模型绑定')
  } catch (e) {
    expert._modelConfigId = oldConfigId
    ElMessage.error('更新失败：' + (e.response?.data?.detail || e.message || '网络错误'))
  }
}

// 加载专家列表（附加 _modelConfigId 字段供下拉框绑定）
async function loadExperts() {
  expertsLoading.value = true
  try {
    const res = await api.getMetaTeamExperts()
    experts.value = (res.data.experts || []).map(e => ({
      ...e,
      _modelConfigId: e.model_config?.config_id || ''
    }))
  } catch (e) {
    console.error('加载专家列表失败:', e)
  } finally {
    expertsLoading.value = false
  }
}

// 点击专家卡片，打开详情编辑
function handleEditExpert(exp) {
  focusExpertId.value = exp.id
  openOptimizeFlag.value = false
  expertsDialogVisible.value = true
}

// 点击优化提示词按钮
function handleOptimize(exp) {
  focusExpertId.value = exp.id
  openOptimizeFlag.value = true
  expertsDialogVisible.value = true
}

// 专家被删除后刷新卡片列表
function handleExpertDeleted() {
  loadExperts()
}

// 创建专家
async function handleCreateExpert() {
  if (!newExpertForm.value.name.trim()) {
    ElMessage.warning('请输入专家名称')
    return
  }
  if (!newExpertForm.value.system_prompt.trim()) {
    ElMessage.warning('请输入系统提示词')
    return
  }
  creatingExpert.value = true
  try {
    await api.createMetaTeamExpert({
      name: newExpertForm.value.name.trim(),
      system_prompt: newExpertForm.value.system_prompt.trim(),
      model_config_id: newExpertForm.value.model_config_id || null
    })
    ElMessage.success('专家创建成功')
    showCreateExpert.value = false
    newExpertForm.value = { name: '', system_prompt: '', model_config_id: '' }
    await loadExperts()
    store.loadMetaTeamExperts()
  } catch (e) {
    ElMessage.error('创建失败：' + (e.response?.data?.detail || e.message))
  } finally {
    creatingExpert.value = false
  }
}

// 暴露给父组件调用
defineExpose({ loadExperts })

onMounted(() => {
  loadExperts()
  loadModelConfigs()
})
</script>

<style scoped>
.meta-team-home {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-chat, #f8fafc);
  overflow-y: auto;
  padding: 24px 32px;
}

/* 顶部标题区 */
.home-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-icon {
  font-size: 32px;
}

.header-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary, #0f172a);
}

.header-desc {
  font-size: 13px;
  color: var(--text-tertiary, #94a3b8);
  margin-top: 2px;
}

/* 专家列表区 */
.experts-section {
  flex: 1;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-secondary, #475569);
}

.experts-loading,
.experts-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 60px 0;
  color: var(--text-tertiary, #94a3b8);
  font-size: 14px;
}

.empty-icon-small {
  font-size: 32px;
  margin-bottom: 8px;
}

.experts-empty {
  flex-direction: column;
}

/* 专家卡片网格 */
.experts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}

.expert-card {
  background: var(--bg-card, #fff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: var(--radius-md, 12px);
  padding: 16px;
  cursor: pointer;
  transition: all 0.25s ease;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.expert-card:hover {
  border-color: var(--primary-light, #818cf8);
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.12);
  transform: translateY(-2px);
}

/* 卡片头部 */
.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.card-avatar {
  font-size: 28px;
  flex-shrink: 0;
}

.card-info {
  flex: 1;
  min-width: 0;
}

.card-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary, #0f172a);
}

.card-id {
  font-size: 12px;
  color: var(--text-tertiary, #94a3b8);
  margin-top: 2px;
}

/* 统计信息 */
.card-stats {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.stat-label {
  color: var(--text-tertiary, #94a3b8);
  font-size: 12px;
}

.stat-val {
  font-weight: 600;
  color: var(--text-secondary, #475569);
}

.stat-sep {
  color: var(--text-tertiary, #94a3b8);
}

/* 得分样式 */
.score-high { color: #16a34a; }
.score-mid { color: #d97706; }
.score-low { color: #dc2626; }
.score-none { color: var(--text-tertiary, #94a3b8); }

/* 得分趋势 */
.card-trend {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.trend-label {
  font-size: 12px;
  color: var(--text-tertiary, #94a3b8);
}

.trend-scores {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.score-chip {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--bg-active, #f1f5f9);
}

.score-chip.score-high { background: #dcfce7; color: #16a34a; }
.score-chip.score-mid { background: #fef3c7; color: #d97706; }
.score-chip.score-low { background: #fee2e2; color: #dc2626; }

.trend-arrow {
  font-size: 10px;
  color: var(--text-tertiary, #94a3b8);
}

/* 提示词预览 */
.card-prompt {
  font-size: 13px;
  color: var(--text-secondary, #475569);
  line-height: 1.5;
  min-height: 36px;
}

/* 卡片底部：模型配置 */
.card-footer {
  padding-top: 8px;
  border-top: 1px solid var(--border-light, #f1f5f9);
}

.card-model-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.model-label {
  font-size: 12px;
  color: var(--text-tertiary, #94a3b8);
  flex-shrink: 0;
}

/* 操作按钮 */
.card-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

/* 表单提示 */
.form-hint {
  font-size: 12px;
  color: var(--text-tertiary, #94a3b8);
  margin-top: 4px;
  line-height: 1.4;
}

/* 加载动画 */
.loading-spinner {
  font-size: 20px;
  animation: spin 1s linear infinite;
  display: inline-block;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
