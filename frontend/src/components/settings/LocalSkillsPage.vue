<template>
  <div class="local-skills-page">
    <!-- 顶部操作栏 -->
    <div class="page-toolbar">
      <div class="toolbar-left">
        <el-button type="primary" size="default" @click="handleCreate">
          + 新建技能
        </el-button>
        <el-button size="default" @click="handleImport">
          📥 导入技能
        </el-button>
        <el-button size="default" @click="loadData" :loading="loading">
          🔄 刷新
        </el-button>
      </div>
      <div class="toolbar-right">
        <el-input
          v-model="searchText"
          placeholder="搜索本地技能"
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
        <span class="stat-num">{{ localSkills.length }}</span>
        <span class="stat-label">已安装技能</span>
      </div>
      <div class="stat-item">
        <span class="stat-num">{{ enabledCount }}</span>
        <span class="stat-label">默认启用</span>
      </div>
      <div class="stat-item">
        <span class="stat-num">{{ builtinCount }}</span>
        <span class="stat-label">内置技能</span>
      </div>
    </div>

    <!-- 技能列表 -->
    <div class="skill-list" v-if="filteredSkills.length > 0">
      <div
        v-for="skill in filteredSkills"
        :key="skill.id"
        class="skill-row"
        :class="{ disabled: !skill.enabled_by_default }"
      >
        <div class="skill-icon" :style="{ background: skill.icon_bg }">
          {{ skill.icon }}
        </div>
        <div class="skill-main">
          <div class="skill-header">
            <span class="skill-name">{{ skill.name }}</span>
            <span v-if="skill.source === 'builtin'" class="badge builtin">内置</span>
            <span v-else-if="skill.source === 'custom'" class="badge custom">自定义</span>
            <span v-else-if="skill.source === 'imported'" class="badge imported">导入</span>
            <span v-else-if="skill.source === 'market'" class="badge market">市场</span>
            <span class="skill-version">v{{ skill.version }}</span>
          </div>
          <div class="skill-desc">{{ skill.description }}</div>
          <div class="skill-detail">
            <span class="detail-item">🔧 工具: {{ (skill.tools || []).length }} 个</span>
            <span class="detail-item">📂 分类: {{ skill.category }}</span>
            <span class="detail-item">📊 使用: {{ skill.use_count || 0 }} 次</span>
          </div>
          <div class="skill-tools" v-if="skill.tools && skill.tools.length > 0">
            <span v-for="t in skill.tools.slice(0, 6)" :key="t" class="tool-chip">{{ t }}</span>
            <span v-if="skill.tools.length > 6" class="tool-more">+{{ skill.tools.length - 6 }}</span>
          </div>
        </div>
        <div class="skill-actions">
          <el-switch
            v-model="skill.enabled_by_default"
            @change="(val) => handleToggle(skill, val)"
          />
          <el-button text size="small" @click="handleEdit(skill)">编辑</el-button>
          <el-button text size="small" type="danger" @click="handleDelete(skill)" v-if="skill.source !== 'builtin'">删除</el-button>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!loading" class="empty-state">
      <div class="empty-icon">📦</div>
      <div class="empty-title">还没有本地技能</div>
      <div class="empty-desc">
        本地技能是可插拔的智能体能力模块，由「工具组合 + 提示词片段」构成。<br>
        您可以新建技能、从市场安装，或导入他人分享的技能文件。
      </div>
      <div class="empty-actions">
        <el-button type="primary" @click="handleCreate">+ 新建第一个技能</el-button>
        <el-button @click="goToMarket">去市场看看</el-button>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-else class="loading-state">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载中...</span>
    </div>

    <!-- 新建/编辑技能对话框 -->
    <el-dialog
      v-model="editorVisible"
      :title="editingSkill.id ? '编辑技能' : '新建技能'"
      width="640px"
      append-to-body
    >
      <el-form :model="editingSkill" label-width="120px" size="default">
        <el-form-item label="技能名称">
          <el-input v-model="editingSkill.name" placeholder="如：代码审查专家" />
        </el-form-item>
        <el-form-item label="技能描述">
          <el-input
            v-model="editingSkill.description"
            type="textarea"
            :rows="2"
            placeholder="一句话说明技能的作用"
          />
        </el-form-item>
        <el-form-item label="图标">
          <el-input v-model="editingSkill.icon" placeholder="emoji，如 🔍" style="width: 80px" />
          <el-input v-model="editingSkill.icon_bg" placeholder="CSS background 值" style="flex: 1; margin-left: 8px" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="editingSkill.category" placeholder="选择分类" allow-create filterable style="width: 100%">
            <el-option label="基础" value="基础" />
            <el-option label="创作" value="创作" />
            <el-option label="开发" value="开发" />
            <el-option label="分析" value="分析" />
            <el-option label="效率" value="效率" />
            <el-option label="自定义" value="自定义" />
          </el-select>
        </el-form-item>
        <el-form-item label="版本">
          <el-input v-model="editingSkill.version" placeholder="1.0.0" style="width: 120px" />
        </el-form-item>
        <el-form-item label="包含工具">
          <el-input
            v-model="toolsInput"
            placeholder="逗号分隔的工具名，如：read_file,write_file,grep"
          />
          <div class="form-tip">每个工具名对应智能体可调用的工具函数</div>
        </el-form-item>
        <el-form-item label="提示词片段">
          <el-input
            v-model="editingSkill.system_prompt_fragment"
            type="textarea"
            :rows="4"
            placeholder="附加到智能体 system_prompt 的内容，如特定工作流程、产出规范等"
          />
        </el-form-item>
        <el-form-item label="默认启用">
          <el-switch v-model="editingSkill.enabled_by_default" />
          <span class="form-tip" style="margin-left: 8px">新建智能体时是否自动启用此技能</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveSkill" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'

const emit = defineEmits(['navigate'])

const searchText = ref('')
const loading = ref(false)
const saving = ref(false)
const localSkills = ref([])
const editorVisible = ref(false)
const editingSkill = ref({})
const toolsInput = ref('')

const filteredSkills = computed(() => {
  if (!searchText.value) return localSkills.value
  const kw = searchText.value.toLowerCase()
  return localSkills.value.filter(s =>
    s.name.toLowerCase().includes(kw) ||
    (s.description || '').toLowerCase().includes(kw)
  )
})

const enabledCount = computed(() => localSkills.value.filter(s => s.enabled_by_default).length)
const builtinCount = computed(() => localSkills.value.filter(s => s.source === 'builtin').length)

async function loadData() {
  loading.value = true
  try {
    const res = await api.getSkills()
    localSkills.value = res.data.skills || []
  } catch (e) {
    ElMessage.error('加载技能失败：' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

function handleCreate() {
  editingSkill.value = {
    name: '', description: '', icon: '🔧',
    icon_bg: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
    category: '自定义', version: '1.0.0',
    tools: [], system_prompt_fragment: '', enabled_by_default: false
  }
  toolsInput.value = ''
  editorVisible.value = true
}

function handleEdit(skill) {
  editingSkill.value = { ...skill }
  toolsInput.value = (skill.tools || []).join(', ')
  editorVisible.value = true
}

function handleImport() {
  ElMessage.info('技能导入功能即将上线，支持从 .skill.json 文件导入')
}

async function handleSaveSkill() {
  if (!editingSkill.value.name) {
    ElMessage.warning('请填写技能名称')
    return
  }
  saving.value = true
  try {
    const payload = { ...editingSkill.value }
    payload.tools = toolsInput.value.split(',').map(t => t.trim()).filter(Boolean)

    if (editingSkill.value.id) {
      await api.updateSkill(editingSkill.value.id, payload)
      ElMessage.success('已更新')
    } else {
      await api.createSkill(payload)
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

async function handleDelete(skill) {
  try {
    await ElMessageBox.confirm(`确定要删除技能「${skill.name}」吗？`, '确认删除', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消'
    })
    await api.deleteSkill(skill.id)
    ElMessage.success('已删除')
    await loadData()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败：' + (e.response?.data?.detail || e.message))
    }
  }
}

async function handleToggle(skill, val) {
  try {
    await api.updateSkill(skill.id, { enabled_by_default: val })
    ElMessage.success(`「${skill.name}」已${val ? '启用' : '关闭'}`)
  } catch (e) {
    skill.enabled_by_default = !val  // 回滚
    ElMessage.error('更新失败：' + (e.response?.data?.detail || e.message))
  }
}

function goToMarket() {
  emit('navigate', 'skill_market')
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.local-skills-page {
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

.skill-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skill-row {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #f1f5f9;
  transition: all 0.2s ease;
}

.skill-row:hover {
  border-color: #c7d2fe;
  box-shadow: 0 3px 10px rgba(99, 102, 241, 0.1);
}

.skill-row.disabled {
  opacity: 0.6;
}

.skill-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  color: #fff;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
}

.skill-main {
  flex: 1;
  min-width: 0;
}

.skill-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}

.skill-name {
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

.badge.builtin { background: #dbeafe; color: #1e40af; }
.badge.custom { background: #d1fae5; color: #065f46; }
.badge.imported { background: #fef3c7; color: #92400e; }
.badge.market { background: #ede9fe; color: #5b21b6; }

.skill-version {
  font-size: 11px;
  color: #94a3b8;
}

.skill-desc {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
  margin-bottom: 6px;
}

.skill-detail {
  display: flex;
  gap: 14px;
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 6px;
  flex-wrap: wrap;
}

.skill-tools {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.tool-chip {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  background: #f1f5f9;
  color: #475569;
  font-family: 'Consolas', monospace;
}

.tool-more {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  background: #e0e7ff;
  color: #4f46e5;
  font-weight: 600;
}

.skill-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
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
  max-width: 460px;
}

.empty-actions {
  display: flex;
  gap: 10px;
  margin-top: 8px;
}

.form-tip {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
  line-height: 1.5;
}

:deep(.el-switch.is-checked .el-switch__core) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-color: transparent;
}
</style>
