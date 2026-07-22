import { defineStore } from 'pinia'
import api from '../api'

export const useAgentStore = defineStore('agent', {
  state: () => ({
    agents: [],  // 全局智能体模板
    teams: [],  // 团队列表（每个团队含 agents 配置和 projects 列表）
    conversations: [],
    currentAgentId: 'main',
    currentConversationId: '',
    currentConvAgents: [],  // 当前对话的智能体配置
    messages: [],
    loading: false,
    streamingAgents: {},  // 当前正在流式输出的智能体 { agentId: partialContent }
    streamMsgCounter: 0,  // 流式消息计数器，用于生成唯一临时ID
    activeBatch: null,  // 阶段3：当前并行执行的批次信息 { round, count, parallel, agents }
    _abortControllers: {},  // 按对话 ID 隔离的 AbortController Map
    _convBuffers: {},  // 后台运行缓冲：{ convId: { messages, streamingAgents, _streamMsgMap } }
    _activeStreamConvId: '',  // 当前 SSE 流所属的对话 ID
    runningConvIds: [],  // 有活跃 SSE 流的对话 ID 列表（侧边栏显示运行状态）
    _isSwitching: false,  // 切换对话中标志：为 true 时 SSE 事件全部走缓存路径，防止竞态
    // 会话级默认模型配置（输入框上方的模型选择）
    defaultConfigId: localStorage.getItem('p005_default_config_id') || '',
    // 会话级思考模式开关（null 表示用配置默认值，true/false 表示用户显式开关）
    enableThinking: localStorage.getItem('p005_enable_thinking') === 'true' ? true : (localStorage.getItem('p005_enable_thinking') === 'false' ? false : null),
    // 智能体管理弹窗可见性（跨组件控制：ChatWindow 触发，Sidebar 渲染弹窗）
    agentManageDialogVisible: false,
    // ===== 团队主页视图 =====
    currentTeamId: '',  // 当前查看的团队 ID（非空时主区域显示团队主页）
    // ===== 元团队常驻模块 =====
    sidebarView: 'projects',  // 侧边栏视图：'projects'（项目列表）| 'meta-team'（团队设计）
    metaTeamTaskId: '',  // 当前查看的设计任务 ID（非空时主区域显示任务详情）
    metaTeamTasks: [],  // 设计任务列表
    metaTeamExperts: [],  // 常驻专家列表
    metaTeamStats: null,  // 设计任务统计
    metaTeamLoading: false,  // 元团队数据加载中
    _metaTeamAbortController: null,  // 用于中止元团队对话流式请求
    // ===== TODO 刷新机制 =====
    todoRefreshTrigger: 0  // TODO 刷新触发器：每次 +1 通知 TodoPanel 重新加载
  }),
  getters: {
    currentMessages(state) {
      return state.messages
    },
    currentConversation(state) {
      return state.conversations.find(c => c.id === state.currentConversationId) || null
    },
    currentRootPath(state) {
      const conv = state.conversations.find(c => c.id === state.currentConversationId)
      return conv?.root_path || ''
    },
    currentAgent(state) {
      // 优先从对话级配置查找
      const convAgent = state.currentConvAgents.find(a => a.id === state.currentAgentId)
      if (convAgent) return convAgent
      return state.agents.find(a => a.id === state.currentAgentId) || null
    },
    currentAgentsList(state) {
      // 获取当前对话可用的智能体列表（优先对话级配置，没有则用全局）
      if (state.currentConvAgents && state.currentConvAgents.length > 0) {
        return state.currentConvAgents
      }
      return state.agents
    },
    getAgentById(state) {
      return (id) => {
        // 优先从对话级配置查找
        const convAgent = state.currentConvAgents.find(a => a.id === id)
        if (convAgent) return convAgent
        return state.agents.find(a => a.id === id) || null
      }
    },
    isStreaming(state) {
      // 当前项目有活跃 SSE 流时才算 streaming（不受 streamingAgents 清空影响）
      return state.runningConvIds.includes(state.currentConversationId)
    },
    // 当前查看的元团队设计任务
    currentMetaTeamTask(state) {
      if (!state.metaTeamTaskId) return null
      return state.metaTeamTasks.find(t => t.id === state.metaTeamTaskId) || null
    },
    // 是否在元团队视图
    isMetaTeamView(state) {
      return state.sidebarView === 'meta-team'
    },
    // 当前查看的团队
    currentTeam(state) {
      if (!state.currentTeamId) return null
      return state.teams.find(t => t.id === state.currentTeamId) || null
    },
    // 是否在团队主页视图
    isTeamHomeView(state) {
      return state.sidebarView === 'projects' && !!state.currentTeamId
    }
  },
  actions: {
    async loadAgents() {
      const res = await api.getAgents()
      this.agents = res.data.agents
    },
    async loadConversations() {
      try {
        const res = await api.getConversations()
        this.conversations = res.data.conversations || []
        // 如果没有对话，自动创建一个
        if (this.conversations.length === 0) {
          await this.createConversation()
        } else if (!this.currentConversationId) {
          // 选中最新的对话，并加载智能体配置和消息
          this.currentConversationId = this.conversations[0].id
          await this.loadConversationAgents()
          await this.loadMessages()
        }
      } catch (e) {
        // 忽略
      }
    },
    async loadConversationAgents() {
      if (!this.currentConversationId) return
      try {
        const res = await api.getConversationAgents(this.currentConversationId)
        this.currentConvAgents = res.data.agents || []
      } catch (e) {
        // 忽略
      }
    },
    async loadMessages(convId) {
      // 支持显式传入 convId，避免异步过程中 currentConversationId 变化导致加载错误对话的消息
      const id = convId || this.currentConversationId
      if (!id) return
      try {
        const res = await api.getMessages(id)
        // 只有当前仍在看这个对话时才更新 this.messages
        // 防止后台异步完成后覆盖了用户已切换到的新对话
        if (this.currentConversationId === id) {
          this.messages = res.data.messages || []
        }
      } catch (e) {
        // 忽略
      }
    },
    selectAgent(id) {
      this.currentAgentId = id
    },
    // 设置会话级默认模型配置
    setDefaultConfig(configId) {
      this.defaultConfigId = configId
      if (configId) {
        localStorage.setItem('p005_default_config_id', configId)
      } else {
        localStorage.removeItem('p005_default_config_id')
      }
    },
    // 设置会话级思考模式开关（传 null 表示用配置默认值）
    setEnableThinking(value) {
      this.enableThinking = value
      if (value === null) {
        localStorage.removeItem('p005_enable_thinking')
      } else {
        localStorage.setItem('p005_enable_thinking', String(value))
      }
    },
    async selectConversation(id) {
      // 如果离开的对话有活跃 SSE，保存当前消息和流式状态为快照
      // （避免切走时丢失前台已接收的消息——sendMessage 拍的快照只有用户消息）
      if (this.currentConversationId && this.currentConversationId !== id && this.runningConvIds.includes(this.currentConversationId)) {
        if (!this._convBuffers[this.currentConversationId]) {
          this._convBuffers[this.currentConversationId] = {}
        }
        this._convBuffers[this.currentConversationId].messagesSnapshot = this.messages.map(m => ({ ...m }))
        this._convBuffers[this.currentConversationId].streamMsgMap = { ...this._streamMsgMap }
      }
      // 设置切换标志：切换完成前，所有 SSE 事件走缓存路径，防止竞态
      // （否则 await 期间事件会 push 到被清空的 this.messages，随后被快照覆盖丢失）
      this._isSwitching = true
      this.currentConversationId = id
      // loading 反映当前项目是否有 SSE 在运行
      this.loading = this.runningConvIds.includes(id)
      this.messages = []
      this.streamingAgents = {}
      this._streamMsgMap = {}
      await this.loadConversationAgents()
      
      // 检查是否有后台 SSE 的缓存事件
      const buf = this._convBuffers[id]
      if (buf && buf.messagesSnapshot) {
        // 恢复快照和流式状态
        this.messages = buf.messagesSnapshot.map(m => ({ ...m }))
        if (buf.streamMsgMap) {
          this._streamMsgMap = { ...buf.streamMsgMap }
        }
        // 重放缓存的事件（如果有）
        if (buf.pendingEvents && buf.pendingEvents.length > 0) {
          const events = buf.pendingEvents
          buf.pendingEvents = []
          let hasDone = false
          for (const e of events) {
            if (e.event === 'done') {
              hasDone = true
              this._streamMsgMap = {}
              this.activeBatch = null
            } else {
              this.handleSSEEvent(e.event, e.data)
            }
          }
          // 更新快照
          buf.messagesSnapshot = this.messages.map(m => ({ ...m }))
          // 如果 SSE 已结束，从后端刷新（确保拿到最终持久化的消息）
          if (hasDone) {
            await this.loadMessages(id)
            buf.messagesSnapshot = this.messages.map(m => ({ ...m }))
          }
        } else if (!this.runningConvIds.includes(id)) {
          // 没有后台 SSE 在运行，从后端刷新
          await this.loadMessages(id)
        }
      } else {
        // 没有快照，正常从后端加载
        await this.loadMessages(id)
      }
      // 清理快照（避免内存泄漏，下次进入时从后端加载最新）
      if (!this.runningConvIds.includes(id)) {
        delete this._convBuffers[id]
      }
      // 切换完成，恢复 SSE 事件直通
      this._isSwitching = false
    },
    async createConversation(rootPath = '', inheritFrom = '', teamId = '') {
      const res = await api.createConversation('', rootPath, inheritFrom, teamId)
      this.conversations.unshift(res.data.conversation)
      this.currentConversationId = res.data.conversation.id
      this.messages = []
      this.streamingAgents = {}
      await this.loadConversationAgents()
      await this.loadTeams()  // 刷新团队的项目列表
      return res.data.conversation
    },

    // ========== 团队管理 ==========
    async loadTeams() {
      try {
        const res = await api.getTeams()
        this.teams = res.data.teams || []
      } catch (e) {
        this.teams = []
      }
    },
    async createTeam(name, rootPath = '', inheritFrom = '') {
      const res = await api.createTeam(name, rootPath, inheritFrom)
      this.teams.unshift(res.data.team)
      return res.data.team
    },
    async deleteTeam(teamId, deleteProjects = false) {
      await api.deleteTeam(teamId, deleteProjects)
      this.teams = this.teams.filter(t => t.id !== teamId)
      if (deleteProjects) {
        this.conversations = this.conversations.filter(c => c.team_id !== teamId)
      }
    },
    // 进入团队主页
    selectTeam(teamId) {
      // 保存当前项目快照（如果有后台 SSE），让事件走缓存路径
      if (this.currentConversationId && this.runningConvIds.includes(this.currentConversationId)) {
        if (!this._convBuffers[this.currentConversationId]) {
          this._convBuffers[this.currentConversationId] = {}
        }
        this._convBuffers[this.currentConversationId].messagesSnapshot = this.messages.map(m => ({ ...m }))
      }
      this.currentTeamId = teamId
      this.currentConversationId = ''  // 清空当前项目，让 SSE 走缓存路径
    },
    // 退出团队主页
    exitTeamHome() {
      this.currentTeamId = ''
    },
    // 添加团队成员
    async addTeamMember(teamId, data) {
      const res = await api.addTeamMember(teamId, data)
      await this.loadTeams()  // 刷新团队数据
      return res.data
    },
    // 更新团队成员
    async updateTeamAgent(teamId, agentId, data) {
      const res = await api.updateTeamAgent(teamId, agentId, data)
      await this.loadTeams()
      // 如果当前项目属于该团队，刷新项目 agents
      if (this.currentConversationId) {
        const conv = this.conversations.find(c => c.id === this.currentConversationId)
        if (conv && conv.team_id === teamId) {
          await this.loadConversationAgents()
        }
      }
      return res.data
    },
    // 删除团队成员
    async deleteTeamMember(teamId, agentId) {
      const res = await api.deleteTeamMember(teamId, agentId)
      await this.loadTeams()
      if (this.currentConversationId) {
        const conv = this.conversations.find(c => c.id === this.currentConversationId)
        if (conv && conv.team_id === teamId) {
          await this.loadConversationAgents()
        }
      }
      return res.data
    },
    async updateConversationRootPath(rootPath) {
      if (!this.currentConversationId) return
      const res = await api.updateConversationPath(this.currentConversationId, rootPath)
      const idx = this.conversations.findIndex(c => c.id === this.currentConversationId)
      if (idx !== -1) {
        // 用 splice 替代直接索引赋值，确保 Vue 响应式更新
        this.conversations.splice(idx, 1, res.data.conversation)
      }
      return res.data.conversation
    },
    async deleteConversation(id, deleteFiles = false) {
      // 先中止该项目的 SSE 流（如果有）
      this.stopGeneration(id)
      // 清理缓冲区和运行状态
      delete this._convBuffers[id]
      this.runningConvIds = this.runningConvIds.filter(rid => rid !== id)
      
      await api.deleteConversation(id, deleteFiles)
      this.conversations = this.conversations.filter(c => c.id !== id)
      // 刷新团队数据（团队主页的项目列表来自 teams）
      this.loadTeams()
      if (this.currentConversationId === id) {
        if (this.conversations.length > 0) {
          this.currentConversationId = this.conversations[0].id
          await this.loadConversationAgents()
          await this.loadMessages()
        } else {
          await this.createConversation()
        }
      } else {
        this.messages = []
        await this.loadMessages()
      }
    },
    async resetConversationStructure(id) {
      // 重置项目目录结构：清理旧任务、重建目录、重建助手工作区
      const res = await api.resetConversationStructure(id)
      // 重新加载对话级智能体配置（权限可能已更新）
      if (this.currentConversationId === id) {
        await this.loadConversationAgents()
      }
      return res.data
    },
    async clearConversationMessages(id) {
      // 先停止该对话的 SSE 流（如果有），防止清空后新事件继续追加
      this.stopGeneration(id)
      // 清空当前项目的对话消息，保留团队成员和项目文件
      const res = await api.clearConversationMessages(id)
      // 如果清的是当前项目，立即清空前端消息列表
      if (this.currentConversationId === id) {
        this.messages = []
        this.streamingAgents = {}
        this._streamMsgMap = {}
      }
      // 清理缓冲区
      delete this._convBuffers[id]
      return res.data
    },
    async renameConversation(id, title) {
      const res = await api.renameConversation(id, title)
      const idx = this.conversations.findIndex(c => c.id === id)
      if (idx !== -1) {
        // 用 splice 替代直接索引赋值，确保 Vue 响应式更新
        this.conversations.splice(idx, 1, res.data.conversation)
      }
      return res.data.conversation
    },
    async sendMessage(text) {
      if (!text.trim() || this.loading) return
      this.loading = true
      
      const convId = this.currentConversationId
      this._activeStreamConvId = convId
      
      // 标记为运行中（侧边栏显示指示器）
      if (!this.runningConvIds.includes(convId)) {
        this.runningConvIds.push(convId)
      }
      
      this.streamingAgents = {}
      this._streamMsgMap = {}
      this._abortControllers[convId] = new AbortController()
      
      const userMsgTime = new Date().toLocaleTimeString('zh-CN')
      // 先添加用户消息到本地
      this.messages.push({
        agent_id: this.currentAgentId,
        role: 'user',
        content: text,
        time: userMsgTime
      })

      // 拍快照（用于切走后切回来时恢复）
      if (!this._convBuffers[convId]) {
        this._convBuffers[convId] = {}
      }
      this._convBuffers[convId].messagesSnapshot = this.messages.map(m => ({ ...m }))
      this._convBuffers[convId].pendingEvents = []

      try {
        const response = await api.chatStream(this.currentAgentId, text, convId, false, this._abortControllers[convId].signal, this.defaultConfigId, this.enableThinking)
        
        if (!response.ok) {
          throw new Error('请求失败: ' + response.status)
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let currentEvent = ''
        let currentData = ''
        
        // 持续读取流
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
              const dataContent = line.slice(5)
              currentData += dataContent.startsWith(' ') ? dataContent.slice(1) : dataContent
            } else if (line === '') {
              if (currentEvent && currentData) {
                // 用户在看 且 不在切换过程中，正常处理；否则缓存事件
                // _isSwitching 防止 selectConversation 的 await 期间事件 push 到被清空的 messages
                if (this.currentConversationId === convId && !this._isSwitching) {
                  this.handleSSEEvent(currentEvent, currentData)
                } else {
                  this._convBuffers[convId].pendingEvents.push({ event: currentEvent, data: currentData })
                }
              }
              currentEvent = ''
              currentData = ''
            }
          }
        }
        
        // 处理剩余事件
        if (currentEvent && currentData) {
          if (this.currentConversationId === convId && !this._isSwitching) {
            this.handleSSEEvent(currentEvent, currentData)
          } else {
            this._convBuffers[convId].pendingEvents.push({ event: currentEvent, data: currentData })
          }
        }

        // 如果用户不在看，重放缓存的事件到快照上（更新快照供下次切回使用）
        if (this.currentConversationId !== convId && this._convBuffers[convId].pendingEvents.length > 0) {
          this._replayPendingEvents(convId)
        }

        await this.loadConversations()
        await this.loadConversationAgents()
      } catch (e) {
        if (e.name === 'AbortError') {
          // 用户主动中止
          if (this.currentConversationId === convId) {
            for (const key in this.streamingAgents) {
              const msgId = this._streamMsgMap?.[key]
              if (msgId) {
                const msg = this.messages.find(m => m.id === msgId)
                if (msg && msg.streaming) {
                  msg.streaming = false
                  msg.content += '\n\n_[已停止生成]_'
                }
              }
            }
          }
        } else {
          if (this.currentConversationId === convId) {
            this.messages.push({
              agent_id: this.currentAgentId,
              role: 'agent',
              content: '出错了：' + (e.message || '网络错误'),
              time: new Date().toLocaleTimeString('zh-CN')
            })
          }
        }
      } finally {
        // 只有当前还在看这个对话时才重置 loading 和 streamingAgents
        // 否则会把另一个正在运行 SSE 的对话的 loading 状态误置为 false
        if (this.currentConversationId === convId) {
          this.loading = false
          this.streamingAgents = {}
        }
        delete this._abortControllers[convId]
        this.runningConvIds = this.runningConvIds.filter(id => id !== convId)
        this._activeStreamConvId = ''
        this.loadTeams()
        this.loadConversationAgents()
      }
    },
    // 停止生成（可指定对话 ID，不指定则停止当前对话）
    stopGeneration(convId) {
      const targetConvId = convId || this.currentConversationId
      if (this._abortControllers[targetConvId]) {
        this._abortControllers[targetConvId].abort()
      }
    },
    // 重放缓存的事件到快照上（SSE 后台运行期间用户切走时，事件被缓存）
    // 此方法在后台静默执行，不更新 this.messages（因为用户在看其他页面）
    _replayPendingEvents(convId) {
      const buf = this._convBuffers[convId]
      if (!buf || !buf.pendingEvents || buf.pendingEvents.length === 0) return
      
      // 临时切换到快照上下文
      const savedMessages = this.messages
      const savedStreaming = this.streamingAgents
      const savedStreamMsgMap = this._streamMsgMap
      const savedConvId = this.currentConversationId
      const savedLoading = this.loading
      
      this.messages = (buf.messagesSnapshot || []).map(m => ({ ...m }))
      this.streamingAgents = {}
      this._streamMsgMap = {}
      this.currentConversationId = convId
      this.loading = false  // 防止 done 事件中的 loadMessages 重复加载
      
      // 重放（跳过 done 事件中的 loadMessages 调用）
      let hasDone = false
      for (const e of buf.pendingEvents) {
        if (e.event === 'done') {
          hasDone = true
          // 手动处理 done：清空状态
          this._streamMsgMap = {}
          this.activeBatch = null
        } else {
          this.handleSSEEvent(e.event, e.data)
        }
      }
      
      // 更新快照（供下次切回使用）
      buf.messagesSnapshot = this.messages.map(m => ({ ...m }))
      buf.pendingEvents = []
      
      // 恢复
      this.messages = savedMessages
      this.streamingAgents = savedStreaming
      this._streamMsgMap = savedStreamMsgMap
      this.currentConversationId = savedConvId
      this.loading = savedLoading
    },
    handleSSEEvent(event, dataStr) {
      try {
        const data = JSON.parse(dataStr)
        const now = new Date().toLocaleTimeString('zh-CN')
        
        // 维护 agent_id -> 当前流式消息ID 的映射，支持同一智能体多轮回复
        if (!this._streamMsgMap) this._streamMsgMap = {}
        
        switch (event) {
          case 'batch_start': {
            // 阶段3：本批并行执行开始，记录批次信息供 UI 展示
            this.activeBatch = {
              round: data.round,
              count: data.count,
              parallel: data.parallel,
              agents: data.agents || [],
              completed: 0
            }
            break
          }
          case 'batch_end': {
            // 阶段3：本批并行执行完成
            this.activeBatch = null
            break
          }
          case 'hallucination_warning': {
            // 防幻觉：主智能体引用了不存在的 task_id，后端已把警告追加到回复末尾
            // 这里只做控制台记录，UI 上通过回复内容里的警告文本即可见
            console.warn('[防幻觉检测]', data.warning || `检测到 ${data.fake_tasks?.length || 0} 个不存在的任务 ID`, data.fake_tasks)
            break
          }
          case 'agent_start': {
            // 某个智能体开始回复，添加一个占位消息（唯一ID）
            this.streamMsgCounter++
            const msgId = 'stream_' + this.streamMsgCounter
            this._streamMsgMap[data.agent_id] = msgId
            this.streamingAgents[data.agent_id] = ''
            this.messages.push({
              id: msgId,
              agent_id: data.agent_id,
              role: 'agent',
              content: '',
              time: now,
              streaming: true,
              toolEvents: []
            })
            break
          }
          case 'token': {
            // 收到流式 token，追加到对应智能体的内容
            const msgId = this._streamMsgMap[data.agent_id]
            if (msgId && this.streamingAgents[data.agent_id] !== undefined) {
              this.streamingAgents[data.agent_id] += data.content
              const msgIdx = this.messages.findIndex(m => m.id === msgId)
              if (msgIdx !== -1) {
                this.messages[msgIdx].content = this.streamingAgents[data.agent_id]
              }
            }
            break
          }
          case 'tool_start': {
            // 智能体开始调用工具，添加工具事件到当前流式消息
            const msgId = this._streamMsgMap[data.agent_id]
            if (msgId) {
              const msgIdx = this.messages.findIndex(m => m.id === msgId)
              if (msgIdx !== -1) {
                if (!this.messages[msgIdx].toolEvents) {
                  this.messages[msgIdx].toolEvents = []
                }
                this.messages[msgIdx].toolEvents.push({
                  type: 'start',
                  tool_name: data.tool_name,
                  tool_args: data.tool_args,
                  status: 'running'
                })
              }
            }
            break
          }
          case 'tool_end': {
            // 工具调用完成，更新状态
            const msgId = this._streamMsgMap[data.agent_id]
            if (msgId) {
              const msgIdx = this.messages.findIndex(m => m.id === msgId)
              if (msgIdx !== -1 && this.messages[msgIdx].toolEvents) {
                const events = this.messages[msgIdx].toolEvents
                for (let i = events.length - 1; i >= 0; i--) {
                  if (events[i].tool_name === data.tool_name && events[i].status === 'running') {
                    events[i].status = 'done'
                    events[i].result = data.result
                    break
                  }
                }
              }
            }
            // 如果是会改变团队成员的工具，立即刷新团队列表（不用等整个流结束）
            if (data.tool_name === 'create_team_member' || data.tool_name === 'remove_team_member' || data.tool_name === 'update_team_member' || data.tool_name === 'create_sub_task') {
              this.loadConversationAgents()
            }
            // 如果是 TODO 相关工具，触发 TodoPanel 刷新
            if (data.tool_name === 'create_todo_list' || data.tool_name === 'update_todo_status') {
              this.todoRefreshTrigger++
            }
            break
          }
          case 'agent_end': {
            // 某个智能体回复完成，更新为最终内容
            const msgId = this._streamMsgMap[data.agent_id]
            delete this.streamingAgents[data.agent_id]
            delete this._streamMsgMap[data.agent_id]
            if (msgId) {
              const msgIdx = this.messages.findIndex(m => m.id === msgId)
              if (msgIdx !== -1) {
                // 只有当 full_content 非空时才覆盖，避免覆盖错误信息或流式累积的内容
                const finalContent = data.full_content || ''
                if (finalContent) {
                  this.messages[msgIdx].content = finalContent
                }
                this.messages[msgIdx].streaming = false
                // 保留临时 id 用于 UI 状态（如展开/折叠），loadMessages 刷新时会被替换
                // delete this.messages[msgIdx].id
              }
            }
            // 阶段3：累加本批并行完成数
            if (this.activeBatch) {
              this.activeBatch.completed = (this.activeBatch.completed || 0) + 1
            }
            break
          }
          case 'error': {
            const errMsg = '❌ ' + (data.message || '出错了')
            const errAgentId = data.agent_id || this.currentAgentId
            const errMsgId = this._streamMsgMap?.[errAgentId]
            if (errMsgId) {
              // 更新当前流式消息为错误内容
              const errIdx = this.messages.findIndex(m => m.id === errMsgId)
              if (errIdx !== -1) {
                this.messages[errIdx].content = errMsg
                this.messages[errIdx].streaming = false
              }
            } else {
              // 没有对应的流式消息，新建一条
              this.messages.push({
                agent_id: errAgentId,
                role: 'agent',
                content: errMsg,
                time: now
              })
            }
            break
          }
          case 'done': {
            // 所有智能体都回复完成了，最终从后端刷新消息列表确保一致
            this._streamMsgMap = {}
            this.activeBatch = null
            // 用 _activeStreamConvId 而非 currentConversationId，防止异步覆盖错误对话
            // loadMessages 内部会校验 currentConversationId 是否仍然匹配
            if (this._activeStreamConvId) {
              this.loadMessages(this._activeStreamConvId)
            }
            break
          }
        }
      } catch (e) {
        console.error('SSE parse error:', e, dataStr)
      }
    },
    async updateConversationAgent(agentId, data) {
      // 更新对话级智能体配置
      const res = await api.updateConversationAgent(this.currentConversationId, agentId, data)
      const idx = this.currentConvAgents.findIndex(a => a.id === agentId)
      if (idx !== -1) {
        // 用 splice 替代直接索引赋值，确保 Vue 响应式更新
        this.currentConvAgents.splice(idx, 1, res.data.agent)
      }
      return res.data.agent
    },
    async copyMessage(content) {
      try {
        await navigator.clipboard.writeText(content)
        return true
      } catch (e) {
        // 降级方案
        const textarea = document.createElement('textarea')
        textarea.value = content
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
        return true
      }
    },
    async regenerateMessage(messageId) {
      // 重新生成某条消息之后的回复（支持用户消息和智能体回复）
      if (this.loading || !this.currentConversationId) return
      
      // 找到这条消息在本地的位置
      const msgIdx = this.messages.findIndex(m => m.id === messageId)
      if (msgIdx === -1) return
      const targetMsg = this.messages[msgIdx]
      
      // 如果是智能体回复，找到它前面的最近用户消息作为重新生成的起点
      let userMsgIdx = msgIdx
      if (targetMsg.role !== 'user') {
        for (let i = msgIdx - 1; i >= 0; i--) {
          if (this.messages[i].role === 'user') {
            userMsgIdx = i
            break
          }
        }
        if (this.messages[userMsgIdx].role !== 'user') return
      }
      // 后端会根据 messageId 找到对应消息并处理，这里传原始 messageId
      const userMessageId = this.messages[userMsgIdx].id
      
      const convId = this.currentConversationId
      this._activeStreamConvId = convId
      if (!this.runningConvIds.includes(convId)) {
        this.runningConvIds.push(convId)
      }
      
      this.loading = true
      this.streamingAgents = {}
      this._streamMsgMap = {}
      this._abortControllers[convId] = new AbortController()
      
      // 先从本地删除用户消息之后的所有消息（保留用户消息本身）
      this.messages = this.messages.slice(0, userMsgIdx + 1)

      // 拍快照
      if (!this._convBuffers[convId]) {
        this._convBuffers[convId] = {}
      }
      this._convBuffers[convId].messagesSnapshot = this.messages.map(m => ({ ...m }))
      this._convBuffers[convId].pendingEvents = []

      try {
        const response = await api.regenerateStream(convId, userMessageId, this._abortControllers[convId].signal)
        
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
              const dataContent = line.slice(5)
              currentData += dataContent.startsWith(' ') ? dataContent.slice(1) : dataContent
            } else if (line === '') {
              if (currentEvent && currentData) {
                if (this.currentConversationId === convId && !this._isSwitching) {
                  this.handleSSEEvent(currentEvent, currentData)
                } else {
                  this._convBuffers[convId].pendingEvents.push({ event: currentEvent, data: currentData })
                }
              }
              currentEvent = ''
              currentData = ''
            }
          }
        }
        
        if (currentEvent && currentData) {
          if (this.currentConversationId === convId && !this._isSwitching) {
            this.handleSSEEvent(currentEvent, currentData)
          } else {
            this._convBuffers[convId].pendingEvents.push({ event: currentEvent, data: currentData })
          }
        }

        // 如果用户不在看，重放到快照
        if (this.currentConversationId !== convId && this._convBuffers[convId].pendingEvents.length > 0) {
          this._replayPendingEvents(convId)
        }

        await this.loadConversations()
        await this.loadConversationAgents()
      } catch (e) {
        if (e.name === 'AbortError') {
          if (this.currentConversationId === convId) {
            for (const key in this.streamingAgents) {
              const msgId = this._streamMsgMap?.[key]
              if (msgId) {
                const msg = this.messages.find(m => m.id === msgId)
                if (msg) {
                  msg.streaming = false
                  msg.stopped = true
                  if (!msg.content) msg.content = '（已停止）'
                }
              }
            }
          }
        } else {
          if (this.currentConversationId === convId) {
            this.messages.push({
              agent_id: this.currentAgentId,
              role: 'agent',
              content: '出错了：' + (e.message || '网络错误'),
              time: new Date().toLocaleTimeString('zh-CN')
            })
          }
        }
      } finally {
        // 只有当前还在看这个对话时才重置 loading 和 streamingAgents
        if (this.currentConversationId === convId) {
          this.loading = false
          this.streamingAgents = {}
        }
        delete this._abortControllers[convId]
        this.runningConvIds = this.runningConvIds.filter(id => id !== convId)
        this._activeStreamConvId = ''
      }
    },
    // 检查某条用户消息是否是最后一条用户消息（可以重新生成）
    canRegenerate(messageId) {
      // 从后往前找最后一条用户消息
      for (let i = this.messages.length - 1; i >= 0; i--) {
        if (this.messages[i].role === 'user') {
          return this.messages[i].id === messageId
        }
      }
      return false
    },

    // ===== 元团队常驻模块 =====

    // 切换侧边栏视图
    showProjectsPanel() {
      this.sidebarView = 'projects'
      this.metaTeamTaskId = ''
    },
    showMetaTeamPanel() {
      // 保存当前项目快照（如果有后台 SSE），让事件走缓存路径
      if (this.currentConversationId && this.runningConvIds.includes(this.currentConversationId)) {
        if (!this._convBuffers[this.currentConversationId]) {
          this._convBuffers[this.currentConversationId] = {}
        }
        this._convBuffers[this.currentConversationId].messagesSnapshot = this.messages.map(m => ({ ...m }))
      }
      this.sidebarView = 'meta-team'
      this.metaTeamTaskId = ''
      this.currentConversationId = ''  // 清空当前项目，让 SSE 走缓存路径
      this.loadMetaTeamTasks()
    },

    // 加载设计任务列表
    async loadMetaTeamTasks(status = null) {
      this.metaTeamLoading = true
      try {
        const res = await api.getMetaTeamTasks(status)
        this.metaTeamTasks = res.data.tasks || []
        this.metaTeamStats = res.data.stats || null
      } catch (e) {
        console.error('加载设计任务失败:', e)
      } finally {
        this.metaTeamLoading = false
      }
    },

    // 创建设计任务
    async createMetaTeamTask(data) {
      const res = await api.createMetaTeamTask(data)
      await this.loadMetaTeamTasks()
      return res.data.task
    },

    // 选中设计任务（查看详情）
    selectMetaTeamTask(taskId) {
      this.metaTeamTaskId = taskId
    },

    // 删除设计任务
    async deleteMetaTeamTask(taskId) {
      await api.deleteMetaTeamTask(taskId)
      if (this.metaTeamTaskId === taskId) {
        this.metaTeamTaskId = ''
      }
      await this.loadMetaTeamTasks()
    },

    // 确认产出蓝图
    async finalizeMetaTeamTask(taskId) {
      const res = await api.finalizeMetaTeamTask(taskId)
      await this.loadMetaTeamTasks()
      return res.data
    },

    // 加载专家列表
    async loadMetaTeamExperts() {
      try {
        const res = await api.getMetaTeamExperts()
        this.metaTeamExperts = res.data.experts || []
      } catch (e) {
        console.error('加载专家列表失败:', e)
      }
    }
  }
})
