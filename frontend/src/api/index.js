import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000  // 流式输出需要更长超时
})

export default {
  // 获取智能体列表
  getAgents() {
    return api.get('/agents')
  },
  // 发送消息（流式）- 返回 fetch Response 对象供调用方处理 SSE
  // direct=true 表示直接对话模式：只调用指定智能体，不触发链式调度
  // signal 可选，用于中止请求
  // defaultConfigId: 会话级默认模型配置ID（智能体未单独配置模型时使用）
  // enableThinking: 会话级思考模式开关（null 表示用配置默认值）
  chatStream(agentId, message, conversationId, direct = false, signal = null, defaultConfigId = '', enableThinking = null) {
    const body = { agent_id: agentId, message, conversation_id: conversationId, direct: direct }
    if (defaultConfigId) body.default_config_id = defaultConfigId
    if (enableThinking !== null) body.enable_thinking = enableThinking
    const opts = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body)
    }
    if (signal) opts.signal = signal
    return fetch('/api/chat/stream', opts)
  },
  // 重新生成消息（流式）- 返回 fetch Response 对象
  // signal 可选，用于中止请求
  // direct=true 表示只重新生成指定智能体的回复，不触发链式调度
  regenerateStream(conversationId, messageId, signal = null, direct = false, targetAgentId = '') {
    const opts = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ 
        conversation_id: conversationId, 
        message_id: messageId,
        direct: direct,
        target_agent_id: targetAgentId
      })
    }
    if (signal) opts.signal = signal
    return fetch('/api/chat/regenerate', opts)
  },
  // 获取预设服务商列表
  getProviders() {
    return api.get('/providers')
  },
  // 测试 API 连接（旧版全局配置测试，仍被部分组件使用）
  testConfig(config) {
    return api.post('/config/test', config)
  },
  // 多模型配置管理
  getModelConfigs() {
    return api.get('/model-configs')
  },
  createModelConfig(data) {
    return api.post('/model-configs', data)
  },
  updateModelConfig(cfgId, data) {
    return api.put(`/model-configs/${cfgId}`, data)
  },
  deleteModelConfig(cfgId) {
    return api.delete(`/model-configs/${cfgId}`)
  },
  testModelConfig(cfgId) {
    return api.post(`/model-configs/${cfgId}/test`)
  },
  // 获取聊天记录
  getMessages(conversationId) {
    return api.get('/messages', { params: { conversation_id: conversationId } })
  },
  // 对话管理
  getConversations() {
    return api.get('/conversations')
  },
  // 创建项目（新建对话）
  createConversation(title = '', rootPath = '', inheritFrom = '', teamId = '') {
    return api.post('/conversations', { title, root_path: rootPath, inherit_from: inheritFrom, team_id: teamId })
  },
  // 导出当前团队为蓝图
  exportBlueprintFromConversation(convId, { blueprint_name, description, category } = {}) {
    return api.post(`/conversations/${convId}/export-blueprint`, { conv_id: convId, blueprint_name, description, category })
  },
  // ========== 团队管理 ==========
  getTeams() {
    return api.get('/teams')
  },
  createTeam(name, rootPath = '', inheritFrom = '') {
    return api.post('/teams', { name, root_path: rootPath, inherit_from: inheritFrom })
  },
  updateTeam(teamId, data) {
    return api.put(`/teams/${teamId}`, data)
  },
  deleteTeam(teamId, deleteProjects = false) {
    return api.delete(`/teams/${teamId}`, { params: { delete_projects: deleteProjects } })
  },
  getTeamAgents(teamId) {
    return api.get(`/teams/${teamId}/agents`)
  },
  addTeamMember(teamId, data) {
    return api.post(`/teams/${teamId}/agents`, data)
  },
  updateTeamAgent(teamId, agentId, data) {
    return api.put(`/teams/${teamId}/agents/${agentId}`, data)
  },
  deleteTeamMember(teamId, agentId) {
    return api.delete(`/teams/${teamId}/agents/${agentId}`)
  },
  // 更新项目根目录
  updateConversationPath(convId, rootPath) {
    return api.put(`/conversations/${convId}/path`, { root_path: rootPath })
  },
  deleteConversation(convId, deleteFiles = false) {
    return api.delete(`/conversations/${convId}`, { params: { delete_files: deleteFiles } })
  },
  resetConversationStructure(convId) {
    return api.post(`/conversations/${convId}/reset-structure`)
  },
  // 清空当前项目的对话消息（保留团队成员和项目文件）
  clearConversationMessages(convId) {
    return api.post(`/conversations/${convId}/clear-messages`)
  },
  renameConversation(convId, title) {
    return api.put(`/conversations/${convId}`, { title })
  },
  getConversationAgents(convId) {
    return api.get(`/conversations/${convId}/agents`)
  },
  updateConversationAgent(convId, agentId, data) {
    return api.put(`/conversations/${convId}/agents/${agentId}`, data)
  },
  // P0-1: 智能体记忆管理
  getAgentMemory(convId, agentId) {
    return api.get(`/conversations/${convId}/agents/${agentId}/memory`)
  },
  clearAgentMemory(convId, agentId) {
    return api.delete(`/conversations/${convId}/agents/${agentId}/memory`)
  },
  addAgentMemory(convId, agentId, data) {
    return api.post(`/conversations/${convId}/agents/${agentId}/memory`, data)
  },
  // P1-5: TODO 列表
  getConversationTodos(convId) {
    return api.get(`/conversations/${convId}/todos`)
  },
  // P1-7: 智能体性能统计
  getAgentStats(convId) {
    return api.get(`/conversations/${convId}/agents/stats`)
  },
  // 文件操作
  listFiles(agentId, path, conversationId = '') {
    return api.post('/files/list', { agent_id: agentId, path, conversation_id: conversationId })
  },
  readFile(agentId, path, conversationId = '') {
    return api.post('/files/read', { agent_id: agentId, path, conversation_id: conversationId })
  },
  // 上传文件到项目目录（默认 shared/）
  uploadFile(file, conversationId, subDir = 'shared') {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('conversation_id', conversationId)
    formData.append('agent_id', 'main')
    formData.append('sub_dir', subDir)
    return api.post('/files/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000,  // 文件上传单独设超时
    })
  },
  // 读取图片（GET请求，需要拼URL参数）
  getImageUrl(path, conversationId = '', agentId = 'main') {
    const params = new URLSearchParams({ path, agent_id: agentId })
    if (conversationId) params.append('conversation_id', conversationId)
    return `/api/files/read-image?${params.toString()}`
  },

  // ========== 技能管理 ==========
  getSkills() {
    return api.get('/skills')
  },
  createSkill(data) {
    return api.post('/skills', data)
  },
  updateSkill(skillId, data) {
    return api.put(`/skills/${skillId}`, data)
  },
  deleteSkill(skillId) {
    return api.delete(`/skills/${skillId}`)
  },

  // ========== 蓝图管理 ==========
  getBlueprints() {
    return api.get('/blueprints')
  },
  getBlueprint(bpId) {
    return api.get(`/blueprints/${bpId}`)
  },
  createBlueprint(data) {
    return api.post('/blueprints', data)
  },
  updateBlueprint(bpId, data) {
    return api.put(`/blueprints/${bpId}`, data)
  },
  deleteBlueprint(bpId) {
    return api.delete(`/blueprints/${bpId}`)
  },
  importBlueprint(data) {
    return api.post('/blueprints/import', data)
  },
  applyBlueprint(bpId, data) {
    return api.post(`/blueprints/${bpId}/apply`, data)
  },

  // ========== 元团队常驻模块 ==========
  // 设计任务管理
  getMetaTeamTasks(status) {
    const params = {}
    if (status) params.status = status
    return api.get('/meta-team/tasks', { params })
  },
  createMetaTeamTask(data) {
    return api.post('/meta-team/tasks', data)
  },
  getMetaTeamTask(taskId) {
    return api.get(`/meta-team/tasks/${taskId}`)
  },
  deleteMetaTeamTask(taskId) {
    return api.delete(`/meta-team/tasks/${taskId}`)
  },
  finalizeMetaTeamTask(taskId) {
    return api.post(`/meta-team/tasks/${taskId}/finalize`)
  },
  // 设计任务对话（SSE 流式）- 返回 fetch Response 对象
  metaTeamChatStream(taskId, message, expertId = null, signal = null, defaultConfigId = '', enableThinking = null) {
    const body = { message }
    if (expertId) body.expert_id = expertId
    if (defaultConfigId) body.default_config_id = defaultConfigId
    if (enableThinking !== null) body.thinking_override = enableThinking
    const opts = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }
    if (signal) opts.signal = signal
    return fetch(`/api/meta-team/tasks/${taskId}/chat`, opts)
  },
  // 专家提示词优化分析（SSE 流式）
  metaTeamOptimizePromptStream(expertId, defaultConfigId = '', signal = null) {
    const body = { message: '请分析并优化提示词' }
    if (defaultConfigId) body.default_config_id = defaultConfigId
    const opts = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }
    if (signal) opts.signal = signal
    return fetch(`/api/meta-team/experts/${expertId}/optimize-prompt`, opts)
  },

  // 深度模式：启动方案并行撰写（SSE 流式）
  metaTeamRunProposalsStream(taskId, defaultConfigId = '', signal = null) {
    const body = {}
    if (defaultConfigId) body.default_config_id = defaultConfigId
    const opts = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }
    if (signal) opts.signal = signal
    return fetch(`/api/meta-team/tasks/${taskId}/run-proposals`, opts)
  },

  // 深度模式：启动专家互相评审（SSE 流式）
  metaTeamRunReviewsStream(taskId, defaultConfigId = '', signal = null) {
    const body = {}
    if (defaultConfigId) body.default_config_id = defaultConfigId
    const opts = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }
    if (signal) opts.signal = signal
    return fetch(`/api/meta-team/tasks/${taskId}/run-reviews`, opts)
  },

  // 深度模式：启动主智能体融合（SSE 流式）
  metaTeamRunFusionStream(taskId, defaultConfigId = '', signal = null) {
    const body = {}
    if (defaultConfigId) body.default_config_id = defaultConfigId
    const opts = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }
    if (signal) opts.signal = signal
    return fetch(`/api/meta-team/tasks/${taskId}/run-fusion`, opts)
  },

  // 深度模式一键全流程
  metaTeamRunAllStream(taskId, defaultConfigId = '', signal = null) {
    const body = {}
    if (defaultConfigId) body.default_config_id = defaultConfigId
    const opts = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }
    if (signal) opts.signal = signal
    return fetch(`/api/meta-team/tasks/${taskId}/run-all`, opts)
  },

  // 专家管理
  getMetaTeamExperts() {
    return api.get('/meta-team/experts')
  },
  getMetaTeamExpert(expertId) {
    return api.get(`/meta-team/experts/${expertId}`)
  },
  createMetaTeamExpert(data) {
    return api.post('/meta-team/experts', data)
  },
  updateMetaTeamExpert(expertId, data) {
    return api.put(`/meta-team/experts/${expertId}`, data)
  },
  deleteMetaTeamExpert(expertId) {
    return api.delete(`/meta-team/experts/${expertId}`)
  },
  upgradeMetaTeamExpertPrompt(expertId, data) {
    return api.post(`/meta-team/experts/${expertId}/upgrade-prompt`, data)
  },
  getMetaTeamExpertPromptHistory(expertId) {
    return api.get(`/meta-team/experts/${expertId}/prompt-history`)
  },
  rollbackMetaTeamExpertPrompt(expertId, targetVersion) {
    return api.post(`/meta-team/experts/${expertId}/rollback-prompt`, { target_version: targetVersion })
  },

  // 全局设置
  getMetaTeamSettings() {
    return api.get('/meta-team/settings')
  },
  updateMetaTeamSettings(data) {
    return api.put('/meta-team/settings', data)
  },

  // 元团队评审（Phase 3）
  metaTeamReviewStream(conversationId, userFeedback = '', defaultConfigId = '', signal = null) {
    const token = localStorage.getItem('token')
    const opts = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {})
      },
      body: JSON.stringify({
        conversation_id: conversationId,
        user_feedback: userFeedback,
        default_config_id: defaultConfigId
      })
    }
    if (signal) opts.signal = signal
    return fetch('/api/meta-team/review', opts)
  },
  getMetaTeamReview(reviewId) {
    return api.get(`/meta-team/review/${reviewId}`)
  },
  listMetaTeamReviews(conversationId = null) {
    const params = conversationId ? { conversation_id: conversationId } : {}
    return api.get('/meta-team/review', { params })
  },
  // 读取专家在设计任务中的方案文件
  getMetaTeamProposal(taskId, expertId) {
    return api.get(`/meta-team/tasks/${taskId}/proposal/${expertId}`)
  },
  // 读取专家在设计任务中的评审文件
  getMetaTeamReviewFile(taskId, expertId) {
    return api.get(`/meta-team/tasks/${taskId}/review/${expertId}`)
  },
  // 读取设计任务的融合决策文件
  getMetaTeamFusionDecision(taskId) {
    return api.get(`/meta-team/tasks/${taskId}/fusion-decision`)
  },
  // 读取设计任务中指定版本的蓝图 JSON
  getMetaTeamBlueprintVersion(taskId, version) {
    return api.get(`/meta-team/tasks/${taskId}/blueprint/${version}`)
  }
}
