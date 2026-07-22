<template>
  <div class="team-home">
    <!-- 顶部栏 -->
    <div class="team-topbar">
      <el-button text @click="goBack" class="back-btn">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
      <div class="team-title-area">
        <span class="team-emoji">👥</span>
        <span class="team-title-text">{{ team?.name || '团队主页' }}</span>
      </div>
      <div class="topbar-actions">
        <el-button type="primary" plain size="small" @click="handleCreateProject">
          ＋ 新建项目
        </el-button>
        <el-button size="small" @click="showEditTeam = true">编辑团队</el-button>
        <el-button type="danger" plain size="small" @click="handleDeleteTeam">删除团队</el-button>
      </div>
    </div>

    <div class="team-content" v-if="team">
      <!-- 团队信息卡 -->
      <div class="team-info-card">
        <div class="info-row">
          <span class="info-label">团队名称</span>
          <span class="info-value">{{ team.name }}</span>
        </div>
        <div class="info-row" v-if="team.root_path">
          <span class="info-label">工作目录</span>
          <span class="info-value path">{{ team.root_path }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">创建时间</span>
          <span class="info-value">{{ team.created_at }}</span>
        </div>
        <div class="info-stats">
          <div class="stat-item">
            <span class="stat-num">{{ team.agents?.length || 0 }}</span>
            <span class="stat-label">成员</span>
          </div>
          <div class="stat-item">
            <span class="stat-num">{{ team.projects?.length || 0 }}</span>
            <span class="stat-label">项目</span>
          </div>
        </div>
      </div>

      <!-- 团队成员区 -->
      <div class="members-section">
        <div class="section-header">
          <h3>团队成员</h3>
          <el-button text size="small" @click="showAddMember = true">＋ 添加成员</el-button>
        </div>
        <div class="members-grid">
          <div v-for="agent in teamAgents" :key="agent.id" class="member-card">
            <div class="member-avatar">{{ agent.avatar || '🤖' }}</div>
            <div class="member-info">
              <div class="member-name">
                {{ agent.name }}
                <el-tag v-if="agent.id === 'main'" size="small" type="primary" effect="plain">主</el-tag>
              </div>
              <div class="member-role">{{ agent.role }}</div>
              <div class="member-tags">
                <el-tag v-if="agent.model_config?.config_id" size="small" type="success">模型已绑定</el-tag>
                <el-tag v-if="agent.enabled_skills?.length" size="small" type="warning">技能 {{ agent.enabled_skills.length }}</el-tag>
                <el-tag v-if="agent.can_invoke_sub_agent" size="small" type="info">子代理</el-tag>
              </div>
            </div>
            <div class="member-actions">
              <el-button text size="small" @click="handleEditMember(agent)">编辑</el-button>
              <el-button v-if="agent.id !== 'main'" text size="small" class="delete-btn" @click="handleDeleteMember(agent)">删除</el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 项目列表区 -->
      <div class="projects-section">
        <div class="section-header">
          <h3>团队项目</h3>
        </div>
        <div class="projects-list">
          <div
            v-for="proj in team.projects"
            :key="proj.id"
            class="project-card"
            @click="handleSelectProject(proj)"
          >
            <div class="project-icon">📄</div>
            <div class="project-info">
              <div class="project-title">{{ proj.title }}</div>
              <div class="project-path" v-if="proj.root_path">{{ formatPath(proj.root_path) }}</div>
              <div class="project-time">{{ proj.updated_at || proj.created_at }}</div>
            </div>
          </div>
          <div v-if="!team.projects?.length" class="empty-projects">
            <p>暂无项目</p>
            <el-button type="primary" plain size="small" @click="handleCreateProject">创建第一个项目</el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 添加成员弹窗 -->
    <el-dialog v-model="showAddMember" title="添加团队成员" width="540px">
      <el-form label-width="90px">
        <el-form-item label="名称" required>
          <el-input v-model="addMemberForm.name" placeholder="例如：小说创作者" />
        </el-form-item>
        <el-form-item label="头像">
          <el-input v-model="addMemberForm.avatar" placeholder="一个 emoji，如 📝" style="width: 100px" />
        </el-form-item>
        <el-form-item label="角色" required>
          <el-input v-model="addMemberForm.role" placeholder="如：creator / reviewer / worker" />
        </el-form-item>
        <el-form-item label="模板">
          <el-select v-model="addMemberForm.template" placeholder="选择角色模板（可选）" style="width: 100%">
            <el-option label="自定义（手写提示词）" value="" />
            <el-option label="creator（创作者）" value="creator" />
            <el-option label="reviewer（审阅者）" value="reviewer" />
            <el-option label="analyst（分析师）" value="analyst" />
            <el-option label="worker（通用执行者）" value="worker" />
          </el-select>
          <div class="form-hint">选择模板后系统会自动生成高质量提示词，无需手写</div>
        </el-form-item>
        <el-form-item v-if="!addMemberForm.template" label="系统提示">
          <el-input v-model="addMemberForm.system_prompt" type="textarea" :rows="4" placeholder="该智能体的系统提示词（选了模板则可留空）" />
        </el-form-item>
        <el-form-item label="🧩 技能">
          <el-select
            v-model="addMemberForm.enabled_skills"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="不选则无技能"
            style="width: 100%"
          >
            <el-option
              v-for="sk in skillsList"
              :key="sk.id"
              :label="`${sk.icon || ''} ${sk.name}`"
              :value="sk.id"
            />
          </el-select>
          <div class="form-hint">绑定的技能可作为工具供该智能体调用</div>
        </el-form-item>
        <el-form-item label="🔧 子代理">
          <el-switch v-model="addMemberForm.can_invoke_sub_agent" />
          <span class="switch-label">开启后可调用临时子代理</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddMember = false">取消</el-button>
        <el-button type="primary" @click="handleAddMember" :loading="addingMember">添加</el-button>
      </template>
    </el-dialog>

    <!-- 编辑成员弹窗 -->
    <el-dialog v-model="showEditMember" title="编辑成员" width="520px">
      <el-form label-width="90px">
        <el-form-item label="名称">
          <el-input v-model="editMemberForm.name" />
        </el-form-item>
        <el-form-item label="头像">
          <el-input v-model="editMemberForm.avatar" style="width: 100px" />
        </el-form-item>
        <el-form-item label="角色">
          <el-input v-model="editMemberForm.role" />
        </el-form-item>
        <el-form-item label="系统提示">
          <el-input v-model="editMemberForm.system_prompt" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item v-if="editingAgentId !== 'main'" label="🧩 技能">
          <el-select
            v-model="editMemberForm.enabled_skills"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="不选则无技能"
            style="width: 100%"
          >
            <el-option
              v-for="sk in skillsList"
              :key="sk.id"
              :label="`${sk.icon || ''} ${sk.name}`"
              :value="sk.id"
            />
          </el-select>
          <div class="form-hint">绑定的技能可作为工具供该智能体调用</div>
        </el-form-item>
        <el-form-item v-if="editingAgentId !== 'main'" label="🔧 子代理">
          <el-switch v-model="editMemberForm.can_invoke_sub_agent" />
          <span class="switch-label">开启后可调用临时子代理</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditMember = false">取消</el-button>
        <el-button type="primary" @click="handleSaveMember" :loading="savingMember">保存</el-button>
      </template>
    </el-dialog>

    <!-- 编辑团队弹窗 -->
    <el-dialog v-model="showEditTeam" title="编辑团队" width="480px">
      <el-form label-width="90px">
        <el-form-item label="团队名称">
          <el-input v-model="editTeamForm.name" />
        </el-form-item>
        <el-form-item label="工作目录">
          <el-input v-model="editTeamForm.root_path" placeholder="团队默认工作目录" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditTeam = false">取消</el-button>
        <el-button type="primary" @click="handleSaveTeam" :loading="savingTeam">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useAgentStore } from '../stores/agent'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import api from '../api'

const store = useAgentStore()

const team = computed(() => store.currentTeam)
const teamAgents = computed(() => team.value?.agents || [])

// 技能列表
const skillsList = ref([])
async function loadSkills() {
  try {
    const res = await api.getSkills()
    skillsList.value = res.data.skills || []
  } catch (e) {
    skillsList.value = []
  }
}
onMounted(() => { loadSkills() })

// 返回
function goBack() {
  store.exitTeamHome()
}

// 格式化路径
function formatPath(fullPath) {
  if (!fullPath) return ''
  const parts = fullPath.split(/[/\\]/).filter(Boolean)
  if (parts.length <= 2) return fullPath
  return '.../' + parts.slice(-2).join('/')
}

// 选择项目
async function handleSelectProject(proj) {
  store.exitTeamHome()  // 先退出团队主页，触发视图切换到 ChatWindow
  await store.selectConversation(proj.id)  // 再加载项目数据
}

// 创建项目
function handleCreateProject() {
  // 通过 emit 通知父组件打开新建项目弹窗
  emit('create-project', team.value?.id)
}

const emit = defineEmits(['create-project'])

// ===== 添加成员 =====
const showAddMember = ref(false)
const addingMember = ref(false)
const addMemberForm = ref({
  name: '', avatar: '🤖', role: '', template: '', system_prompt: '', enabled_skills: [], can_invoke_sub_agent: false
})

async function handleAddMember() {
  if (!addMemberForm.value.name.trim()) {
    ElMessage.warning('请输入成员名称')
    return
  }
  if (!addMemberForm.value.role.trim()) {
    ElMessage.warning('请输入成员角色')
    return
  }
  if (!addMemberForm.value.template && !addMemberForm.value.system_prompt.trim()) {
    ElMessage.warning('请选择模板或填写系统提示词')
    return
  }
  addingMember.value = true
  try {
    const res = await store.addTeamMember(team.value.id, addMemberForm.value)
    ElMessage.success(res.message || '成员已添加')
    showAddMember.value = false
    addMemberForm.value = { name: '', avatar: '🤖', role: '', template: '', system_prompt: '', enabled_skills: [], can_invoke_sub_agent: false }
  } catch (e) {
    ElMessage.error('添加失败：' + (e.response?.data?.detail || e.message))
  } finally {
    addingMember.value = false
  }
}

// ===== 编辑成员 =====
const showEditMember = ref(false)
const savingMember = ref(false)
const editingAgentId = ref('')
const editMemberForm = ref({
  name: '', avatar: '', role: '', system_prompt: '', can_invoke_sub_agent: false, enabled_skills: []
})

function handleEditMember(agent) {
  editingAgentId.value = agent.id
  editMemberForm.value = {
    name: agent.name,
    avatar: agent.avatar,
    role: agent.role,
    system_prompt: agent.system_prompt || '',
    can_invoke_sub_agent: !!agent.can_invoke_sub_agent,
    enabled_skills: Array.isArray(agent.enabled_skills) ? [...agent.enabled_skills] : []
  }
  showEditMember.value = true
}

async function handleSaveMember() {
  savingMember.value = true
  try {
    const res = await store.updateTeamAgent(team.value.id, editingAgentId.value, editMemberForm.value)
    ElMessage.success('已保存')
    showEditMember.value = false
  } catch (e) {
    ElMessage.error('保存失败：' + (e.response?.data?.detail || e.message))
  } finally {
    savingMember.value = false
  }
}

// ===== 删除成员 =====
async function handleDeleteMember(agent) {
  try {
    await ElMessageBox.confirm(
      `确定要删除成员「${agent.name}」吗？该操作会同步到团队下所有项目。`,
      '删除成员',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await store.deleteTeamMember(team.value.id, agent.id)
    ElMessage.success('成员已删除')
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败：' + (e.response?.data?.detail || e.message))
    }
  }
}

// ===== 删除团队 =====
async function handleDeleteTeam() {
  try {
    const projectCount = team.value.projects?.length || 0
    await ElMessageBox.confirm(
      `确定要删除团队「${team.value.name}」吗？${projectCount > 0 ? `该团队下的 ${projectCount} 个项目也会被删除。` : ''}`,
      '删除团队',
      { confirmButtonText: '删除团队和项目', cancelButtonText: '取消', type: 'warning' }
    )
    await store.deleteTeam(team.value.id, true)
    store.exitTeamHome()
    ElMessage.success('团队已删除')
  } catch (e) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error('删除失败：' + (e.response?.data?.detail || e.message))
    }
  }
}

// ===== 编辑团队 =====
const showEditTeam = ref(false)
const savingTeam = ref(false)
const editTeamForm = ref({ name: '', root_path: '' })

watch(showEditTeam, (v) => {
  if (v && team.value) {
    editTeamForm.value = {
      name: team.value.name,
      root_path: team.value.root_path || ''
    }
  }
})

async function handleSaveTeam() {
  savingTeam.value = true
  try {
    await api.updateTeam(team.value.id, editTeamForm.value)
    await store.loadTeams()
    ElMessage.success('团队信息已更新')
    showEditTeam.value = false
  } catch (e) {
    ElMessage.error('保存失败：' + (e.response?.data?.detail || e.message))
  } finally {
    savingTeam.value = false
  }
}
</script>

<style scoped>
.team-home {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-main, #f8fafc);
  overflow: hidden;
}

.team-topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  background: var(--bg-card, #ffffff);
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  flex-shrink: 0;
}

.back-btn {
  color: var(--text-tertiary, #94a3b8);
}

.team-title-area {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
}

.team-emoji {
  font-size: 20px;
}

.team-title-text {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary, #1e293b);
}

.topbar-actions {
  display: flex;
  gap: 8px;
}

.team-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
}

/* 团队信息卡 */
.team-info-card {
  background: var(--bg-card, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
}

.info-row {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
  font-size: 14px;
}

.info-label {
  width: 80px;
  color: var(--text-tertiary, #94a3b8);
  flex-shrink: 0;
}

.info-value {
  color: var(--text-primary, #1e293b);
}

.info-value.path {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  color: var(--text-secondary, #475569);
}

.info-stats {
  display: flex;
  gap: 32px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color, #e2e8f0);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-num {
  font-size: 24px;
  font-weight: 700;
  color: #6366f1;
}

.stat-label {
  font-size: 12px;
  color: var(--text-tertiary, #94a3b8);
  margin-top: 2px;
}

/* 区块标题 */
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.section-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #1e293b);
  margin: 0;
}

/* 成员网格 */
.members-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.member-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  background: var(--bg-card, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 10px;
  padding: 14px;
  transition: box-shadow 0.2s;
}

.member-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.member-avatar {
  font-size: 28px;
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f1f5f9;
  border-radius: 10px;
}

.member-info {
  flex: 1;
  min-width: 0;
}

.member-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #1e293b);
  display: flex;
  align-items: center;
  gap: 6px;
}

.member-role {
  font-size: 12px;
  color: var(--text-tertiary, #94a3b8);
  margin-top: 2px;
}

.member-tags {
  display: flex;
  gap: 4px;
  margin-top: 6px;
  flex-wrap: wrap;
}

.member-actions {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex-shrink: 0;
}

.delete-btn {
  color: #ef4444;
}

/* 项目列表 */
.projects-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 10px;
}

.project-card {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--bg-card, #ffffff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 10px;
  padding: 12px 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.project-card:hover {
  border-color: #6366f1;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.1);
}

.project-icon {
  font-size: 20px;
  flex-shrink: 0;
}

.project-info {
  flex: 1;
  min-width: 0;
}

.project-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary, #1e293b);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-path {
  font-size: 11px;
  color: var(--text-tertiary, #94a3b8);
  font-family: 'Consolas', 'Monaco', monospace;
  margin-top: 2px;
}

.project-time {
  font-size: 11px;
  color: var(--text-tertiary, #94a3b8);
  margin-top: 2px;
}

.empty-projects {
  grid-column: 1 / -1;
  text-align: center;
  padding: 40px 20px;
  color: var(--text-tertiary, #94a3b8);
}

.empty-projects p {
  margin-bottom: 12px;
  font-size: 14px;
}

.form-hint {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.4;
  margin-top: 4px;
}

.switch-label {
  margin-left: 8px;
  font-size: 13px;
  color: #64748b;
}
</style>
