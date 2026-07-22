<template>
  <div class="local-blueprints-page">
    <!-- 顶部操作栏 -->
    <div class="page-toolbar">
      <div class="toolbar-left">
        <el-button type="primary" size="default" @click="handleCreate">
          + 新建蓝图
        </el-button>
        <el-button size="default" @click="handleImport">
          📥 导入蓝图
        </el-button>
        <el-button size="default" @click="loadData" :loading="loading">
          🔄 刷新
        </el-button>
      </div>
      <div class="toolbar-right">
        <el-input
          v-model="searchText"
          placeholder="搜索本地蓝图"
          size="default"
          prefix-icon="Search"
          clearable
          style="width: 220px"
        />
      </div>
    </div>

    <!-- 统计信息 -->
    <div class="stats-bar">
      <div class="stat-item">
        <span class="stat-num">{{ localBlueprints.length }}</span>
        <span class="stat-label">本地蓝图</span>
      </div>
      <div class="stat-item">
        <span class="stat-num">{{ totalMembers }}</span>
        <span class="stat-label">总成员数</span>
      </div>
      <div class="stat-item">
        <span class="stat-num">{{ appliedCount }}</span>
        <span class="stat-label">已应用次数</span>
      </div>
    </div>

    <!-- 蓝图列表 -->
    <div class="blueprint-list" v-if="filteredBlueprints.length > 0">
      <div
        v-for="bp in filteredBlueprints"
        :key="bp.id"
        class="blueprint-row"
      >
        <div class="bp-cover" :style="{ background: bp.icon_bg || defaultCoverBg }">
          <span class="cover-icon">{{ bp.icon || '📋' }}</span>
        </div>
        <div class="bp-main">
          <div class="bp-header">
            <span class="bp-name">{{ bp.name }}</span>
            <span class="badge" :class="bp.source">{{ sourceLabel(bp.source) }}</span>
            <span class="bp-version">v{{ bp.version }}</span>
            <span class="bp-updated">更新于 {{ formatDate(bp.updated_at) }}</span>
          </div>
          <div class="bp-desc">{{ bp.description }}</div>
          <div class="bp-detail" v-if="bp.blueprint_data">
            <div class="member-list">
              <span class="detail-label">成员 ({{ (bp.blueprint_data.members || []).length }}):</span>
              <span
                v-for="m in (bp.blueprint_data.members || []).slice(0, 6)"
                :key="m.name"
                class="member-chip"
              >{{ m.name }}</span>
              <span v-if="(bp.blueprint_data.members || []).length > 6" class="member-more">
                +{{ (bp.blueprint_data.members || []).length - 6 }}
              </span>
            </div>
            <div class="task-info">
              <span class="detail-label">任务:</span>
              <span class="detail-val">{{ (bp.blueprint_data.tasks || []).length }} 个</span>
              <span class="detail-label" style="margin-left: 12px">协作:</span>
              <span class="detail-val">{{ collaborationSummary(bp) }}</span>
              <span class="detail-label" style="margin-left: 12px">应用:</span>
              <span class="detail-val">{{ bp.apply_count || 0 }} 次</span>
            </div>
          </div>
          <div class="bp-detail" v-else>
            <div class="empty-data-tip">蓝图数据为空，请编辑添加</div>
          </div>
        </div>
        <div class="bp-actions">
          <el-button type="primary" size="small" @click="handleApply(bp)" :disabled="!bp.blueprint_data">
            🚀 应用
          </el-button>
          <el-button text size="small" @click="handleEdit(bp)">编辑</el-button>
          <el-button text size="small" @click="handleExport(bp)">导出</el-button>
          <el-button text size="small" type="danger" @click="handleDelete(bp)">删除</el-button>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!loading" class="empty-state">
      <div class="empty-icon">📋</div>
      <div class="empty-title">还没有本地蓝图</div>
      <div class="empty-desc">
        团队蓝图是可复用的团队配置模板，包含成员清单、提示词、协作模式、任务流程。<br>
        应用蓝图后，系统会一键创建对应的项目团队，无需手动逐个配置。
      </div>
      <div class="empty-actions">
        <el-button type="primary" @click="goToMetaTeam">🎯 让元团队智能生成</el-button>
        <el-button @click="handleCreate">+ 手动新建</el-button>
        <el-button @click="goToMarket">去市场获取</el-button>
      </div>
    </div>

    <div v-else class="loading-state">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载中...</span>
    </div>

    <!-- 新建/编辑蓝图对话框 -->
    <el-dialog
      v-model="editorVisible"
      :title="editingBp.id ? '编辑蓝图' : '新建蓝图'"
      width="780px"
      append-to-body
      :close-on-click-modal="false"
    >
      <el-form :model="editingBp" label-width="100px" size="default">
        <el-form-item label="蓝图名称">
          <el-input v-model="editingBp.name" placeholder="如：科幻长篇小说创作团队" />
        </el-form-item>
        <el-form-item label="蓝图描述">
          <el-input
            v-model="editingBp.description"
            type="textarea"
            :rows="2"
            placeholder="一句话说明蓝图适用场景"
          />
        </el-form-item>
        <el-form-item label="图标">
          <el-input v-model="editingBp.icon" placeholder="emoji，如 🚀" style="width: 80px" />
          <el-input v-model="editingBp.icon_bg" placeholder="CSS background 值" style="flex: 1; margin-left: 8px" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="editingBp.category" allow-create filterable style="width: 100%">
            <el-option label="小说创作" value="novel" />
            <el-option label="代码开发" value="dev" />
            <el-option label="调研分析" value="research" />
            <el-option label="内容运营" value="content" />
            <el-option label="商业服务" value="business" />
            <el-option label="通用" value="general" />
          </el-select>
        </el-form-item>
        <el-form-item label="版本">
          <el-input v-model="editingBp.version" placeholder="1.0.0" style="width: 120px" />
        </el-form-item>
        <el-divider content-position="left">蓝图数据（team_blueprint.json 格式）</el-divider>
        <el-form-item label="蓝图JSON">
          <el-input
            v-model="blueprintJsonInput"
            type="textarea"
            :rows="12"
            placeholder='{"blueprint_version":"1.0","team_name":"...","members":[...],"tasks":[...]}'
            style="font-family: Consolas, Monaco, monospace; font-size: 12px"
          />
          <div class="form-tip">
            粘贴 team_blueprint.json 内容。格式要求：blueprint_version, team_name, members（至少2个，含 name/role/system_prompt/collaboration）
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveBp" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 应用蓝图对话框 -->
    <el-dialog
      v-model="applyVisible"
      :title="`应用蓝图：${applyingBp?.name || ''}`"
      width="520px"
      append-to-body
    >
      <div class="apply-info">
        <div class="apply-summary">
          <span class="summary-label">团队名称：</span>
          <span class="summary-val">{{ applyingBp?.blueprint_data?.team_name || '-' }}</span>
        </div>
        <div class="apply-summary">
          <span class="summary-label">成员数量：</span>
          <span class="summary-val">{{ (applyingBp?.blueprint_data?.members || []).length }} 个</span>
        </div>
        <div class="apply-summary">
          <span class="summary-label">任务数量：</span>
          <span class="summary-val">{{ (applyingBp?.blueprint_data?.tasks || []).length }} 个</span>
        </div>
      </div>
      <el-form label-width="100px" style="margin-top: 16px">
        <el-form-item label="项目名称">
          <el-input v-model="applyForm.project_title" placeholder="留空使用蓝图团队名" />
        </el-form-item>
        <el-form-item label="工作目录">
          <el-input
            v-model="applyForm.root_path"
            placeholder="粘贴文件夹完整路径，如 D:\projects\my-docs"
          />
          <div class="form-tip">将在此目录初始化项目结构，并按蓝图创建团队成员</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="applyVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmApply" :loading="applying">🚀 创建项目团队</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { useAgentStore } from '../../stores/agent'

const emit = defineEmits(['navigate'])
const store = useAgentStore()

const searchText = ref('')
const loading = ref(false)
const saving = ref(false)
const applying = ref(false)
const localBlueprints = ref([])
const editorVisible = ref(false)
const applyVisible = ref(false)
const editingBp = ref({})
const applyingBp = ref(null)
const blueprintJsonInput = ref('')
const applyForm = ref({ project_title: '', root_path: '' })

const defaultCoverBg = 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)'

const filteredBlueprints = computed(() => {
  if (!searchText.value) return localBlueprints.value
  const kw = searchText.value.toLowerCase()
  return localBlueprints.value.filter(b =>
    b.name.toLowerCase().includes(kw) ||
    (b.description || '').toLowerCase().includes(kw)
  )
})

const totalMembers = computed(() =>
  localBlueprints.value.reduce((sum, b) =>
    sum + (b.blueprint_data?.members?.length || 0), 0)
)
const appliedCount = computed(() =>
  localBlueprints.value.reduce((sum, b) => sum + (b.apply_count || 0), 0)
)

function sourceLabel(source) {
  const map = {
    meta: '元团队生成', manual: '手动创建',
    market: '市场获取', imported: '导入'
  }
  return map[source] || source
}

function collaborationSummary(bp) {
  const members = bp.blueprint_data?.members || []
  const types = members.map(m => m.collaboration?.type).filter(Boolean)
  const counts = {}
  types.forEach(t => { counts[t] = (counts[t] || 0) + 1 })
  return Object.entries(counts)
    .map(([t, c]) => `${t}×${c}`)
    .join('、') || '未设置'
}

function formatDate(iso) {
  if (!iso) return '-'
  return iso.replace('T', ' ').substring(0, 16)
}

async function loadData() {
  loading.value = true
  try {
    const res = await api.getBlueprints()
    localBlueprints.value = res.data.blueprints || []
  } catch (e) {
    ElMessage.error('加载蓝图失败：' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

function handleCreate() {
  editingBp.value = {
    name: '', description: '', icon: '📋',
    icon_bg: defaultCoverBg, category: 'general', version: '1.0.0',
    source: 'manual'
  }
  blueprintJsonInput.value = ''
  editorVisible.value = true
}

function handleEdit(bp) {
  editingBp.value = { ...bp }
  blueprintJsonInput.value = bp.blueprint_data
    ? JSON.stringify(bp.blueprint_data, null, 2)
    : ''
  editorVisible.value = true
}

function handleImport() {
  ElMessageBox.prompt('请输入蓝图 JSON 文件路径，或粘贴蓝图 JSON 内容', '导入蓝图', {
    inputType: 'textarea',
    inputPlaceholder: '文件路径如：D:\\projects\\xxx\\deliverables\\team_blueprint.json\n\n或直接粘贴 JSON 内容',
    confirmButtonText: '导入',
    cancelButtonText: '取消',
  }).then(async ({ value }) => {
    if (!value) return
    try {
      let payload
      const trimmed = value.trim()
      if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
        // JSON 内容
        const data = JSON.parse(trimmed)
        payload = { blueprint_data: data, source: 'imported' }
      } else {
        // 文件路径
        payload = { file_path: trimmed, source: 'imported' }
      }
      await api.importBlueprint(payload)
      ElMessage.success('蓝图已导入')
      await loadData()
    } catch (e) {
      ElMessage.error('导入失败：' + (e.response?.data?.detail || e.message))
    }
  }).catch(() => {})
}

async function handleSaveBp() {
  if (!editingBp.value.name) {
    ElMessage.warning('请填写蓝图名称')
    return
  }

  let blueprintData = null
  if (blueprintJsonInput.value.trim()) {
    try {
      blueprintData = JSON.parse(blueprintJsonInput.value)
    } catch (e) {
      ElMessage.error('蓝图 JSON 格式错误：' + e.message)
      return
    }
  }

  saving.value = true
  try {
    const payload = {
      name: editingBp.value.name,
      description: editingBp.value.description,
      icon: editingBp.value.icon,
      icon_bg: editingBp.value.icon_bg,
      category: editingBp.value.category,
      version: editingBp.value.version,
      source: editingBp.value.source || 'manual',
    }
    if (blueprintData) payload.blueprint_data = blueprintData

    if (editingBp.value.id) {
      await api.updateBlueprint(editingBp.value.id, payload)
      ElMessage.success('已更新')
    } else {
      await api.createBlueprint(payload)
      ElMessage.success('已创建')
    }
    editorVisible.value = false
    await loadData()
  } catch (e) {
    ElMessage.error('保存失败：' + (e.response?.data?.detail || e.message))
  } finally {
    saving.value = false
  }
}

async function handleDelete(bp) {
  try {
    await ElMessageBox.confirm(`确定要删除蓝图「${bp.name}」吗？`, '确认删除', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消'
    })
    await api.deleteBlueprint(bp.id)
    ElMessage.success('已删除')
    await loadData()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败：' + (e.response?.data?.detail || e.message))
    }
  }
}

function handleExport(bp) {
  if (!bp.blueprint_data) {
    ElMessage.warning('蓝图数据为空，无法导出')
    return
  }
  const blob = new Blob([JSON.stringify(bp.blueprint_data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${bp.name.replace(/[\\/:*?"<>|]/g, '_')}_blueprint.json`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('已导出')
}

function handleApply(bp) {
  if (!bp.blueprint_data) {
    ElMessage.warning('蓝图数据为空，无法应用')
    return
  }
  applyingBp.value = bp
  applyForm.value = {
    project_title: bp.blueprint_data.team_name || bp.name,
    root_path: ''
  }
  applyVisible.value = true
}

async function confirmApply() {
  if (!applyingBp.value) return
  applying.value = true
  try {
    const res = await api.applyBlueprint(applyingBp.value.id, applyForm.value)
    const conv = res.data.conversation
    // 添加到 store
    store.conversations.unshift(conv)
    store.currentConversationId = conv.id
    store.messages = []
    store.streamingAgents = {}
    await store.loadConversationAgents()
    applyVisible.value = false
    ElMessage.success(res.data.message)
    emit('close-settings')
  } catch (e) {
    ElMessage.error('应用失败：' + (e.response?.data?.detail || e.message))
  } finally {
    applying.value = false
  }
}

function goToMetaTeam() {
  ElMessage.info('请关闭设置面板，点击左侧"+ 新项目"，选择"元团队规划"类型')
}

function goToMarket() {
  emit('navigate', 'blueprint_market')
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.local-blueprints-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.toolbar-left {
  display: flex;
  gap: 8px;
}

.stats-bar {
  display: flex;
  gap: 12px;
  padding: 14px 18px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.06) 0%, rgba(118, 75, 162, 0.06) 100%);
  border-radius: 10px;
  border: 1px solid #e0e7ff;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
}

.stat-num {
  font-size: 22px;
  font-weight: 700;
  color: #4f46e5;
}

.stat-label {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

.blueprint-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.blueprint-row {
  display: flex;
  align-items: stretch;
  gap: 14px;
  padding: 14px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #f1f5f9;
  transition: all 0.2s ease;
}

.blueprint-row:hover {
  border-color: #c7d2fe;
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.12);
}

.bp-cover {
  width: 64px;
  height: 64px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 3px 8px rgba(0, 0, 0, 0.1);
}

.cover-icon {
  font-size: 30px;
}

.bp-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.bp-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.bp-name {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.badge {
  font-size: 10px;
  padding: 1px 7px;
  border-radius: 4px;
  font-weight: 600;
}

.badge.meta { background: #ede9fe; color: #5b21b6; }
.badge.manual { background: #dbeafe; color: #1e40af; }
.badge.market { background: #d1fae5; color: #065f46; }
.badge.imported { background: #fef3c7; color: #92400e; }

.bp-version {
  font-size: 11px;
  color: #94a3b8;
}

.bp-updated {
  font-size: 11px;
  color: #94a3b8;
  margin-left: auto;
}

.bp-desc {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

.bp-detail {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 11px;
  color: #94a3b8;
}

.member-list {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.detail-label {
  color: #94a3b8;
  font-weight: 500;
  margin-right: 4px;
}

.member-chip {
  padding: 1px 7px;
  border-radius: 4px;
  background: #f1f5f9;
  color: #475569;
}

.member-more {
  padding: 1px 7px;
  border-radius: 4px;
  background: #e0e7ff;
  color: #4f46e5;
  font-weight: 600;
}

.detail-val {
  color: #475569;
}

.empty-data-tip {
  color: #f59e0b;
  font-style: italic;
}

.bp-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: stretch;
  justify-content: center;
  min-width: 100px;
}

.empty-state, .loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  color: #94a3b8;
  gap: 14px;
}

.loading-state {
  flex-direction: row;
  gap: 10px;
}

.empty-icon {
  font-size: 48px;
  opacity: 0.6;
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: #475569;
}

.empty-desc {
  font-size: 13px;
  color: #94a3b8;
  line-height: 1.7;
  max-width: 500px;
}

.empty-actions {
  display: flex;
  gap: 10px;
  margin-top: 8px;
  flex-wrap: wrap;
  justify-content: center;
}

.form-tip {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
  line-height: 1.5;
}

/* 应用蓝图对话框 */
.apply-info {
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.apply-summary {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 13px;
}

.summary-label {
  color: #64748b;
}

.summary-val {
  color: #0f172a;
  font-weight: 600;
}
</style>
