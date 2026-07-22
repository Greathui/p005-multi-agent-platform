<template>
  <div class="chat-window">
    <!-- 顶部：智能体团队展示 + 操作按钮 -->
    <div class="chat-topbar" v-if="store.currentAgent">
      <div class="agent-team">
        <el-dropdown
          v-for="agent in store.currentConvAgents"
          :key="agent.id"
          trigger="click"
          @command="(cmd) => handleAgentCommand(agent, cmd)"
          @visible-change="(v) => agentDropdownOpen = v ? agent.id : ''"
        >
          <div class="agent-chip" :class="{ active: agent.id === store.currentAgentId }">
            <span class="chip-avatar">{{ agent.avatar }}</span>
            <span class="chip-name">{{ agent.name }}</span>
            <span v-if="agent.level === 2" class="chip-level-tag" title="L2 执行者">L2</span>
            <span class="chip-model" v-if="getAgentModelName(agent)">· {{ getAgentModelName(agent) }}</span>
            <span class="chip-arrow" :class="{ open: agentDropdownOpen === agent.id }">▸</span>
          </div>
          <template #dropdown>
            <el-dropdown-menu class="agent-dropdown-menu">
              <el-dropdown-item :command="'select'" :disabled="agent.id === store.currentAgentId">
                切换到此智能体
              </el-dropdown-item>
              <el-dropdown-item :command="'thread'">
                💬 打开对话线程
              </el-dropdown-item>
              <el-dropdown-item :command="'edit'" divided>
                编辑智能体
              </el-dropdown-item>
              <!-- 已保存的配置列表 -->
              <el-dropdown-item
                v-for="cfg in configs"
                :key="cfg.id"
                :command="'use_config:' + cfg.id"
                class="model-option"
              >
                <span class="model-name">{{ cfg.name }}</span>
                <span class="model-provider">{{ cfg.model }}</span>
                <span v-if="agent.model_config?.config_id === cfg.id" class="model-check">✓</span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
      <div class="topbar-actions">
        <el-button text size="small" @click="toggleFilePanel" :class="{ active: filePanelOpen }">
          📂 {{ store.currentRootPath ? '文件' : '设置目录' }}
        </el-button>
        <el-button
          v-if="store.currentConversationId"
          text
          size="small"
          @click="todoPanelOpen = !todoPanelOpen"
          :class="{ active: todoPanelOpen }"
          title="查看TODO清单"
        >
          📋 TODO
        </el-button>
        <el-button
          text
          size="small"
          @click="handleClearMessages"
          :disabled="!store.currentConversationId || store.messages.length === 0 || store.loading"
          title="清空当前项目的对话历史，保留团队成员和项目文件"
        >
          ✨ 开启新任务
        </el-button>
        <el-button
          text
          size="small"
          @click="showExportBlueprint = true"
          :disabled="!store.currentConversationId || store.currentConvAgents.length < 2"
          title="将当前团队导出为蓝图，可分享给其他人或在其他项目复用"
        >
          📤 导出蓝图
        </el-button>
        <el-button
          v-if="store.currentConversation?.blueprint_source"
          text
          size="small"
          @click="reviewDialogRef?.open()"
          title="对该项目进行元团队回访评审，诊断团队设计问题"
        >
          🔍 元团队评审
        </el-button>
      </div>
    </div>

    <!-- 主内容区：聊天 + 文件浏览器 -->
    <div class="chat-main" :class="{ 'with-files': filePanelOpen && store.currentRootPath }">
      <!-- 聊天区域 -->
      <div class="chat-area">
        <!-- 项目路径设置栏已移到底部输入框上方，这里不再显示 -->

        <!-- 无工作目录提示 -->
        <div v-if="!store.currentRootPath && store.messages.length === 0" class="no-path-banner">
          <div>
            <strong>提示：</strong>还没有设置工作目录。点击输入框左侧「📁」按钮粘贴一个文件夹路径，
            智能体就可以帮你操作文件了。不设置也能正常聊天。
          </div>
        </div>

        <!-- 聊天内容区 -->
        <div class="chat-body" ref="messagesRef">
          <!-- 欢迎页（无消息时显示） -->
          <div v-if="store.messages.length === 0 && !store.loading" class="welcome-page">
            <h1 class="welcome-title">Hi, 今天从哪里开始</h1>
            <div class="suggestion-bubbles">
              <div
                v-for="s in suggestions"
                :key="s"
                class="suggestion-bubble"
                @click="inputText = s; handleSend()"
              >{{ s }}</div>
            </div>
          </div>

          <!-- 消息列表 -->
          <div v-for="(msg, i) in store.currentMessages" :key="msg.id || i" class="msg-row" :class="msg.role">
        <template v-if="msg.role === 'user'">
          <div class="user-msg-row">
            <div class="user-avatar">👤</div>
            <div class="bubble user-bubble">
              <div class="content markdown-body" v-html="renderMarkdown(msg.content || '')"></div>
              <div class="msg-action-bar user-action-bar">
                <div class="action-icon-group">
                  <button class="action-icon-btn" title="复制" @click="handleCopy(msg.content)" v-if="msg.content">
                    <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25v-7.5z"/><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25v-7.5zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25h-7.5z"/></svg>
                  </button>
                  <button class="action-icon-btn" title="重新生成" @click="handleRegenerate(msg)" v-if="msg.id && store.canRegenerate(msg.id) && !store.loading">
                    <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><path d="M1.5 8a6.5 6.5 0 1 0 3.88-5.95.75.75 0 1 0-.55 1.39A5 5 0 1 1 3 8a.75.75 0 0 0-1.5 0z"/><path d="M3.5 3.5a.75.75 0 0 0 0-1.5H1.75A1.75 1.75 0 0 0 0 3.75v1.75a.75.75 0 0 0 1.5 0V3.5h2z"/></svg>
                  </button>
                </div>
                <span class="action-time">{{ msg.time }}</span>
              </div>
            </div>
          </div>
        </template>
        <template v-else>
          <!-- 统一的调度行渲染：主智能体和子智能体都用同一种结构，默认折叠 -->
          <div class="agent-row" :class="{ 'is-sub-agent': msg.agent_id !== 'main' }">
            <div class="agent-avatar-small" :class="{ 'sub-avatar': msg.agent_id !== 'main' }" @click="msg.agent_id !== 'main' && openThread(msg.agent_id)">{{ getAgent(msg.agent_id)?.avatar || '🤖' }}</div>
            <div class="agent-message-wrap">
              <div class="agent-name-label">
                {{ getAgent(msg.agent_id)?.name || '智能体' }}
                <span class="agent-summary-tag" v-if="!isMsgExpanded(msg)">· {{ getAgentSummary(msg) }}</span>
              </div>

              <!-- 折叠态：紧凑摘要行 -->
              <div v-if="!isMsgExpanded(msg)" class="agent-collapsed-card" @click="toggleExpand(msg)">
                <div class="collapsed-main">
                  <!-- 工具调用摘要（只显示一行代表性摘要） -->
                  <div class="collapsed-tools" v-if="msg.toolEvents && msg.toolEvents.length > 0">
                    <span class="collapsed-tool-icon">🔧</span>
                    <span class="collapsed-tool-text">
                      {{ formatCollapsedTools(msg.toolEvents) }}
                    </span>
                  </div>
                  <!-- 内容摘要（核心结论，最多 80 字） -->
                  <div class="collapsed-summary" v-if="getContentSummary(msg)">
                    <span class="collapsed-quote">{{ getContentSummary(msg) }}</span>
                  </div>
                  <div class="collapsed-summary placeholder" v-else-if="msg.streaming">
                    <span class="collapsed-quote">思考中...</span>
                  </div>
                </div>
                <div class="collapsed-actions">
                  <button class="action-icon-btn" title="展开" @click.stop="toggleExpand(msg)">
                    <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><path d="M12.78 6.22a.75.75 0 0 0-1.06 0L8 9.94 4.28 6.22a.75.75 0 0 0-1.06 1.06l4.25 4.25a.75.75 0 0 0 1.06 0l4.25-4.25a.75.75 0 0 0 0-1.06z"/></svg>
                  </button>
                  <button
                    v-if="msg.agent_id !== 'main'"
                    class="action-icon-btn"
                    title="私聊"
                    @click.stop="openThread(msg.agent_id)"
                  >
                    <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><path d="M1.75 1A1.75 1.75 0 0 0 0 2.75v9.5C0 13.216.784 14 1.75 14h9.5A1.75 1.75 0 0 0 13 12.25v-3.5a.75.75 0 0 0-1.5 0v3.5a.25.25 0 0 1-.25.25h-9.5a.25.25 0 0 1-.25-.25v-9.5a.25.25 0 0 1 .25-.25h3.5a.75.75 0 0 0 0-1.5h-3.5z"/><path d="M8 1.5a.75.75 0 0 0-.75.75v2.5a.75.75 0 0 0 1.5 0V3.36l3.72 3.72a.75.75 0 1 0 1.06-1.06L8.06 1.97A.75.75 0 0 0 8 1.5z"/></svg>
                  </button>
                </div>
              </div>

              <!-- 展开态：完整内容 -->
              <div v-else class="bubble agent-bubble">
                <!-- 工具调用过程（展开态才显示） -->
                <div v-if="msg.toolEvents && msg.toolEvents.length > 0" class="tool-events">
                  <div v-for="(te, ti) in msg.toolEvents" :key="ti" class="tool-event" :class="te.status">
                    <span class="tool-icon">{{ getToolIcon(te.tool_name) }}</span>
                    <span class="tool-text">{{ formatToolCall(te) }}</span>
                    <span v-if="te.status === 'running'" class="tool-spinner"></span>
                    <span v-else-if="te.status === 'done'" class="tool-check">✓</span>
                  </div>
                </div>
                <div class="content markdown-body" v-html="renderMarkdown(msg.content || '')" :class="{ streaming: msg.streaming }"></div>
                <div class="msg-action-bar agent-action-bar">
                  <div class="action-icon-group">
                    <button class="action-icon-btn" title="复制" @click="handleCopy(msg.content)" v-if="msg.content">
                      <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25v-7.5z"/><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25v-7.5zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25h-7.5z"/></svg>
                    </button>
                    <button class="action-icon-btn" title="收起" @click="toggleExpand(msg)" v-if="!msg.streaming">
                      <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><path d="M3.22 9.78a.75.75 0 0 1 0-1.06l4.25-4.25a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 1 1-1.06 1.06L8 6.06 4.28 9.78a.75.75 0 0 1-1.06 0z"/></svg>
                    </button>
                    <button class="action-icon-btn" title="重新生成" @click="handleRegenerate(msg)" v-if="msg.id && !store.loading && msg.agent_id === 'main'">
                      <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><path d="M1.5 8a6.5 6.5 0 1 0 3.88-5.95.75.75 0 1 0-.55 1.39A5 5 0 1 1 3 8a.75.75 0 0 0-1.5 0z"/><path d="M3.5 3.5a.75.75 0 0 0 0-1.5H1.75A1.75 1.75 0 0 0 0 3.75v1.75a.75.75 0 0 0 1.5 0V3.5h2z"/></svg>
                    </button>
                    <button class="action-icon-btn" title="点评" @click="openFeedbackDialog(msg)" v-if="msg.id && !store.loading">
                      <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><path d="M1.75 1A1.75 1.75 0 0 0 0 2.75v9.5C0 13.216.784 14 1.75 14h9.5A1.75 1.75 0 0 0 13 12.25v-3.5a.75.75 0 0 0-1.5 0v3.5a.25.25 0 0 1-.25.25h-9.5a.25.25 0 0 1-.25-.25v-9.5a.25.25 0 0 1 .25-.25h3.5a.75.75 0 0 0 0-1.5h-3.5z"/><path d="M9.78 1.22a.75.75 0 0 0-1.06 0L4.22 5.72a.75.75 0 0 0 0 1.06l4.5 4.5a.75.75 0 0 0 1.06 0l3.5-3.5a.75.75 0 0 0 0-1.06L9.78 1.22z"/></svg>
                    </button>
                  </div>
                  <span class="action-time">{{ msg.time }}</span>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>
      <!-- 阶段3：并行调度批次指示器 -->
      <div v-if="store.activeBatch" class="batch-status-bar">
        <div class="batch-status-content">
          <span class="batch-icon">⚡</span>
          <span class="batch-text">
            第 {{ store.activeBatch.round }} 轮 · {{ store.activeBatch.count }} 个智能体并行执行
            <span class="batch-progress">
              （{{ store.activeBatch.completed || 0 }}/{{ store.activeBatch.count }} 完成）
            </span>
          </span>
          <div class="batch-agents">
            <span
              v-for="a in store.activeBatch.agents"
              :key="a.agent_id"
              class="batch-agent-chip"
            >{{ a.agent_name }}</span>
          </div>
        </div>
      </div>
      <div v-if="store.loading && !store.isStreaming" class="msg-row agent">
        <div class="agent-row">
          <div class="agent-avatar-small">🤔</div>
          <div>
            <div class="bubble agent-bubble">
              <div class="content typing">
                <span class="typing-dots">
                  <span></span><span></span><span></span>
                </span>
                团队思考中...
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

        <!-- 底部输入区 -->
        <div class="input-area">
          <!-- 项目路径设置栏（紧贴输入框上方，由 📁 按钮触发） -->
          <div v-if="showPathBar" class="project-path-bar">
            <div class="path-input-row">
              <el-input
                v-model="projectPathInput"
                placeholder="粘贴项目文件夹的完整路径，如 D:\projects\my-docs"
                size="small"
                @keyup.enter="handleSetProjectPath"
                style="flex: 1"
              />
              <el-button size="small" type="primary" @click="handleSetProjectPath" :loading="pathSetting">
                应用
              </el-button>
              <el-button size="small" @click="showPathBar = false" v-if="store.currentRootPath">
                取消
              </el-button>
            </div>
            <div class="path-info" v-if="store.currentRootPath">
              <span class="path-label">当前工作目录：</span>
              <span class="path-value" :title="store.currentRootPath">{{ store.currentRootPath }}</span>
            </div>
            <div class="path-tip" v-else>
              💡 设置工作目录后，智能体可以自主读写该目录下的文件，帮你完成实际任务。
            </div>
          </div>
          <div class="input-wrapper trae-input-wrapper">
            <div class="mention-container" style="position: relative;">
              <!-- 已选中的文件附件预览条 -->
              <div v-if="attachedFiles.length > 0" class="attached-files-bar">
                <div v-for="(f, idx) in attachedFiles" :key="idx" class="attached-file-chip">
                  <span class="attached-file-icon">{{ getFileIcon(f.name) }}</span>
                  <span class="attached-file-name">{{ f.name }}</span>
                  <span class="attached-file-size">{{ formatFileSize(f.size) }}</span>
                  <button class="attached-file-remove" @click="removeAttachedFile(idx)" title="移除">×</button>
                </div>
              </div>

              <!-- 输入框（上方） -->
              <el-input
                v-model="inputText"
                type="textarea"
                :rows="3"
                :autosize="{ minRows: 3, maxRows: 8 }"
                placeholder="帮你整理文档、编写代码、分析数据等日常工作，输出专业级工作成果... (Ctrl+Enter 发送)"
                resize="none"
                @keydown.enter.ctrl="handleSend"
                @input="handleInputChange"
                @keydown.down.prevent="handleMentionKey('down')"
                @keydown.up.prevent="handleMentionKey('up')"
                @keydown.enter.exact="handleMentionEnter"
                @keydown.esc="mentionVisible = false"
                ref="textareaRef"
              />

              <!-- 下方工具栏 -->
              <div class="input-toolbar">
                <div class="toolbar-left">
                  <button class="toolbar-btn" @click="triggerFileUpload" title="上传文件">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M7.5 11H2.75a.75.75 0 0 1 0-1.5H7.5V5.25a.75.75 0 0 1 1.5 0V9.5h4.75a.75.75 0 0 1 0 1.5H9v4.25a.75.75 0 0 1-1.5 0V11z"/><path d="M3.5 3.75A1.75 1.75 0 0 1 5.25 2h5.5A1.75 1.75 0 0 1 12.5 3.75v5.5a.75.75 0 0 1-1.5 0v-5.5a.25.25 0 0 0-.25-.25h-5.5a.25.25 0 0 0-.25.25v5.5a.75.75 0 0 1-1.5 0v-5.5z"/></svg>
                    <span class="toolbar-btn-label">文件</span>
                  </button>
                  <button class="toolbar-btn" @click="openPathSettings" title="设置工作目录">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M1.75 1A1.75 1.75 0 0 0 0 2.75v10.5C0 14.216.784 15 1.75 15h12.5A1.75 1.75 0 0 0 16 13.25v-7.5A1.75 1.75 0 0 0 14.25 4H7.5L5.72 2.22A.75.75 0 0 0 5.19 2H1.75z"/></svg>
                    <span class="toolbar-btn-label">目录</span>
                  </button>
                  <button class="toolbar-btn" @click="mentionButtonClick" title="@提及智能体">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M5.5 3.5a2 2 0 1 1 4 0v4a.5.5 0 0 1-1 0V3.5a1 1 0 1 0-2 0V9a2.5 2.5 0 0 0 5 0V6a.5.5 0 0 1 1 0v3a3.5 3.5 0 0 1-7 0V3.5z"/><path d="M8 1.5a3.5 3.5 0 0 0-3.5 3.5V9a3.5 3.5 0 0 0 7 0V5a.5.5 0 0 1 1 0v4a4.5 4.5 0 0 1-9 0V5A4.5 4.5 0 0 1 8 .5a.5.5 0 0 1 0 1z"/></svg>
                    <span class="toolbar-btn-label">@</span>
                  </button>
                  <button class="toolbar-btn" @click="openFileFeedbackDialog" title="文件点评">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M11.5 2.5a.75.75 0 0 1 .75.75v6.5a.75.75 0 0 1-1.5 0v-6.5a.75.75 0 0 1 .75-.75zM8 5.25a.75.75 0 0 0-1.5 0v9.5a.75.75 0 0 0 1.5 0v-9.5zM4.75 8a.75.75 0 0 1 .75.75v6a.75.75 0 0 1-1.5 0v-6A.75.75 0 0 1 4.75 8z"/></svg>
                    <span class="toolbar-btn-label">点评</span>
                  </button>
                </div>
                <!-- 中间：会话级模型选择 + 思考模式开关（参考 Trae 布局） -->
                <div class="toolbar-center">
                  <el-select
                    v-model="selectedDefaultConfig"
                    size="small"
                    placeholder="默认模型"
                    class="model-select"
                    @change="handleDefaultConfigChange"
                  >
                    <el-option label="跟随全局配置" value="" />
                    <el-option
                      v-for="cfg in configs"
                      :key="cfg.id"
                      :label="cfg.name + ' · ' + cfg.model"
                      :value="cfg.id"
                    />
                  </el-select>
                  <button
                    class="thinking-toggle"
                    :class="{ active: store.enableThinking === true, inactive: store.enableThinking === false }"
                    @click="toggleThinking"
                    :title="thinkingTooltip"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M9 18h6"/><path d="M10 22h4"/><path d="M2 12a10 10 0 0 1 20 0c0 4-3 6-4 8H6c-1-2-4-4-4-8z"/>
                    </svg>
                    <span class="thinking-label">{{ store.enableThinking === true ? '思考' : (store.enableThinking === false ? '直答' : '自动') }}</span>
                  </button>
                </div>
                <div class="toolbar-right">
                  <button
                    v-if="!store.loading"
                    class="send-btn"
                    @click="handleSend"
                    :disabled="!inputText.trim() && attachedFiles.length === 0"
                    title="发送（Ctrl+Enter）"
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                      <path d="M12 4L12 20M12 4L6 10M12 4L18 10" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    <span class="send-btn-label">发送</span>
                  </button>
                  <button
                    v-else
                    class="stop-btn"
                    @click="handleStopGeneration"
                    title="停止生成"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="white">
                      <rect x="6" y="6" width="12" height="12" rx="2"/>
                    </svg>
                    <span class="send-btn-label">停止</span>
                  </button>
                </div>
              </div>

              <!-- 隐藏的文件上传 input -->
              <input
                ref="fileInputRef"
                type="file"
                multiple
                style="display: none"
                @change="handleFileSelect"
              />

              <!-- @ 智能体选择器 -->
              <div v-if="mentionVisible && filteredAgents.length > 0" class="mention-popover">
                <div class="mention-header">选择要@的智能体</div>
                <div
                  v-for="(agent, idx) in filteredAgents"
                  :key="agent.id"
                  class="mention-item"
                  :class="{ active: mentionIndex === idx }"
                  @click="selectMention(agent)"
                  @mouseenter="mentionIndex = idx"
                >
                  <span class="mention-avatar">{{ agent.avatar }}</span>
                  <div class="mention-info">
                    <span class="mention-name">{{ agent.name }}</span>
                    <span class="mention-role">{{ agent.role }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <!-- /chat-area -->

      <!-- 右侧面板：文件树 / 对话产出（tab 切换） -->
      <div v-if="filePanelOpen && store.currentRootPath" class="file-panel">
        <div class="panel-tabs">
          <div class="panel-tab" :class="{ active: rightPanelTab === 'files' }" @click="rightPanelTab = 'files'">
            📂 文件
          </div>
          <div class="panel-tab" :class="{ active: rightPanelTab === 'outputs' }" @click="rightPanelTab = 'outputs'">
            📦 产出
            <span v-if="outputFiles.length" class="tab-badge">{{ outputFiles.length }}</span>
          </div>
        </div>
        <div class="panel-content">
          <FileExplorer v-show="rightPanelTab === 'files'" @send-feedback="handleFileFeedback" />
          <div v-show="rightPanelTab === 'outputs'" class="outputs-list">
            <div v-if="outputFiles.length === 0" class="outputs-empty">
              <div class="outputs-empty-icon">📦</div>
              <p>暂无产出文件</p>
              <p class="outputs-empty-desc">AI 回复中的代码块会自动收录于此</p>
            </div>
            <div
              v-for="(file, idx) in outputFiles"
              :key="idx"
              class="output-item"
              @click="viewOutputFile(file)"
            >
              <span class="output-icon">{{ getLanguageIcon(file.language) }}</span>
              <div class="output-info">
                <div class="output-name">{{ file.name }}</div>
                <div class="output-meta">
                  <span class="output-lang">{{ file.language || 'text' }}</span>
                  <span class="output-time">{{ file.time }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <!-- TODO 面板（侧边栏，默认折叠） -->
      <div v-if="todoPanelOpen && store.currentConversationId" class="todo-panel-wrapper">
        <TodoPanel :conv-id="store.currentConversationId" :refresh-trigger="store.todoRefreshTrigger" />
      </div>
    </div>
    <!-- /chat-main -->

    <!-- 编辑智能体弹窗 -->
    <el-dialog v-model="editDialogVisible" :title="editingAgentId ? `编辑「${getAgent(editingAgentId)?.name}」` : '编辑智能体'" width="560px" v-if="store.currentAgent">
      <el-form :model="editForm" label-width="90px">
        <el-form-item label="名称">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="角色">
          <el-input v-model="editForm.role" />
        </el-form-item>
        <el-form-item label="头像">
          <el-input v-model="editForm.avatar" style="width: 100px" />
        </el-form-item>
        <el-form-item label="系统提示">
          <el-input v-model="editForm.system_prompt" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="可访问路径">
          <div class="path-input-row">
            <el-input
              v-model="editPathInput"
              placeholder="输入文件夹路径"
              @keyup.enter="addEditPath"
              style="flex: 1"
            />
            <el-button @click="addEditPath" size="small">添加</el-button>
          </div>
          <div class="path-tags">
            <el-tag
              v-for="(p, i) in editForm.allowed_paths"
              :key="i"
              closable
              size="small"
              @close="editForm.allowed_paths.splice(i, 1)"
            >{{ p }}</el-tag>
            <el-tag v-if="editForm.allowed_paths.length === 0" type="info" size="small">留空 = 全部权限</el-tag>
          </div>
        </el-form-item>
        <!-- 模型配置 -->
        <el-form-item label="模型配置">
          <el-select v-model="editForm.model_config_id" placeholder="使用全局默认配置" clearable style="width: 100%">
            <el-option label="使用全局默认配置" value="" />
            <el-option
              v-for="cfg in configs"
              :key="cfg.id"
              :label="`${cfg.name}（${cfg.model || '未知模型'}）`"
              :value="cfg.id"
            />
          </el-select>
          <div class="form-hint">为该智能体单独指定模型配置</div>
        </el-form-item>
        <!-- 技能绑定（非 main 智能体） -->
        <el-form-item v-if="editingAgentId !== 'main'" label="🧩 技能">
          <el-select
            v-model="editForm.enabled_skills"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="不选则无技能"
            style="width: 100%"
          >
            <el-option
              v-for="sk in skillsList"
              :key="sk.id"
              :label="`${sk.emoji || ''} ${sk.name}`"
              :value="sk.id"
            />
          </el-select>
          <div class="form-hint">绑定的技能可作为工具供该智能体调用</div>
        </el-form-item>
        <!-- 子代理开关（非 main 智能体） -->
        <el-form-item v-if="editingAgentId !== 'main'" label="🔧 子代理">
          <el-switch v-model="editForm.can_invoke_sub_agent" />
          <span class="switch-label">{{ editForm.can_invoke_sub_agent ? '已开启' : '已关闭' }}</span>
          <div class="form-hint">开启后该智能体可调用临时子代理协助完成任务</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveEdit" :loading="savingEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 智能体工作线程面板 -->
    <AgentThread v-model="threadVisible" :agent-id="threadAgentId" />

    <!-- 导出蓝图对话框 -->
    <el-dialog v-model="showExportBlueprint" title="导出团队为蓝图" width="480px">
      <el-form label-width="90px">
        <el-form-item label="蓝图名称">
          <el-input v-model="exportBpForm.blueprint_name" :placeholder="`${store.currentConversation?.title || '导出团队'} 的团队蓝图`" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="exportBpForm.description" type="textarea" :rows="3" placeholder="可选，描述这个团队的用途和特点" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="exportBpForm.category" style="width: 100%">
            <el-option label="通用" value="general" />
            <el-option label="小说创作" value="novel" />
            <el-option label="开发编程" value="dev" />
            <el-option label="研究分析" value="research" />
            <el-option label="内容生产" value="content" />
            <el-option label="商业" value="business" />
          </el-select>
        </el-form-item>
        <div class="export-bp-info">
          <p>将把当前项目的 <strong>{{ store.currentConvAgents.length }}</strong> 个智能体导出为蓝图，包含：</p>
          <ul>
            <li>每个智能体的名称、角色、系统提示词</li>
            <li>技能绑定和子代理开关配置</li>
            <li>可访问路径权限设置</li>
          </ul>
          <p class="export-tip">导出后可在「设置 → 本地蓝图」中查看、应用或导出为 JSON 文件分享。</p>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="showExportBlueprint = false">取消</el-button>
        <el-button type="primary" @click="handleExportBlueprint" :loading="exportingBp">导出</el-button>
      </template>
    </el-dialog>

    <!-- 元团队评审弹窗 -->
    <MetaTeamReviewDialog
      ref="reviewDialogRef"
      :conversation-id="store.currentConversationId || ''"
    />

    <!-- 文件点评弹窗（从输入框工具栏触发） -->
    <el-dialog v-model="fileFeedbackVisible" title="📝 文件点评" width="520px">
      <div class="feedback-dialog-body">
        <div class="feedback-field">
          <label class="feedback-label">选择文件</label>
          <el-select v-model="feedbackFilePath" placeholder="选择要点评的文件" filterable style="width: 100%">
            <el-option v-for="f in fileListForFeedback" :key="f.path" :label="f.name" :value="f.path">
              <span style="float: left">{{ f.is_dir ? '📁' : '📄' }} {{ f.name }}</span>
              <span style="float: right; color: var(--el-text-color-secondary); font-size: 12px">{{ f.relPath }}</span>
            </el-option>
          </el-select>
        </div>
        <div class="feedback-field">
          <label class="feedback-label">点评内容</label>
          <el-input v-model="feedbackContent" type="textarea" :rows="4" placeholder="对这个文件有什么意见或建议？点评会发送到项目对话中，智能体能看到你的反馈。" />
        </div>
      </div>
      <template #footer>
        <el-button @click="fileFeedbackVisible = false">取消</el-button>
        <el-button type="primary" @click="submitFileFeedback" :disabled="!feedbackContent.trim()">发送点评</el-button>
      </template>
    </el-dialog>

    <!-- 智能体回复点评弹窗（从智能体回复下方触发） -->
    <el-dialog v-model="agentFeedbackVisible" title="📝 点评智能体回复" width="520px">
      <div class="feedback-dialog-body">
        <div class="feedback-field">
          <label class="feedback-label">点评对象</label>
          <div class="feedback-target">{{ feedbackTargetAgent }}</div>
        </div>
        <div class="feedback-field">
          <label class="feedback-label">点评内容</label>
          <el-input v-model="feedbackContent" type="textarea" :rows="4" placeholder="对智能体的回复有什么意见或建议？点评会发送到项目对话中，智能体能看到你的反馈。" />
        </div>
      </div>
      <template #footer>
        <el-button @click="agentFeedbackVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAgentFeedback" :disabled="!feedbackContent.trim()">发送点评</el-button>
      </template>
    </el-dialog>

    <!-- 产出文件查看对话框 -->
    <el-dialog v-model="outputViewerVisible" :title="outputViewerTitle" width="760px" append-to-body>
      <div class="output-viewer-content">
        <pre class="output-code-block"><code>{{ outputViewerContent }}</code></pre>
      </div>
      <template #footer>
        <el-button @click="outputViewerVisible = false">关闭</el-button>
        <el-button type="primary" @click="copyOutputContent">复制内容</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, nextTick, watch, computed, onBeforeUnmount } from 'vue'
import { useAgentStore } from '../stores/agent'
import api from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { renderMarkdown } from '../utils/markdown'
import { getFileIcon, getLanguageIcon, isImageFile } from '../utils/fileIcons'
import { getToolIcon, formatToolCall, formatCollapsedTools } from '../utils/toolIcons'
import AgentThread from './AgentThread.vue'
import FileExplorer from './FileExplorer.vue'
import TodoPanel from './TodoPanel.vue'
import MetaTeamReviewDialog from './MetaTeamReviewDialog.vue'
import 'highlight.js/styles/github.css'

const store = useAgentStore()
const inputText = ref('')
const messagesRef = ref(null)
const agentDropdownOpen = ref('')
const threadVisible = ref(false)
const threadAgentId = ref('')
const reviewDialogRef = ref(null)  // 元团队评审弹窗引用
const textareaRef = ref(null)
const fileInputRef = ref(null)  // 隐藏的文件上传 input
const attachedFiles = ref([])  // 已选中的待上传文件列表

// 组件卸载时中止正在进行的 SSE 请求，防止内存泄漏
onBeforeUnmount(() => {
  // 不再中止 SSE——项目在后台继续运行，切换回来时自动恢复
})

// 消息展开/收起状态（Trae 风格调度行：默认折叠，只显示操作摘要）
// 存储展开的 msg.id；流式中的消息默认展开
const expandedMsgs = ref(new Set())

function isMsgExpanded(msg) {
  // 流式中的消息自动展开，让用户看到实时输出
  if (msg.streaming) return true
  return expandedMsgs.value.has(msg.id)
}

function toggleExpand(msg) {
  if (msg.streaming) return  // 流式中不允许手动收起
  if (expandedMsgs.value.has(msg.id)) {
    expandedMsgs.value.delete(msg.id)
  } else {
    expandedMsgs.value.add(msg.id)
  }
  // 触发响应式更新
  expandedMsgs.value = new Set(expandedMsgs.value)
}

// 智能体消息的摘要（用于折叠态显示）
function getAgentSummary(msg) {
  const toolCount = msg.toolEvents?.length || 0
  const doneCount = msg.toolEvents?.filter(t => t.status === 'done').length || 0
  const running = msg.toolEvents?.some(t => t.status === 'running')
  
  // 流式中
  if (msg.streaming) {
    if (toolCount === 0 && (!msg.content || msg.content.length < 5)) {
      return '思考中...'
    }
    if (running) {
      return `正在执行第 ${doneCount + 1}/${toolCount} 个操作`
    }
    return `已执行 ${doneCount} 个操作，继续思考中...`
  }
  
  // 完成态
  if (toolCount > 0) {
    return `完成 ${doneCount} 个操作`
  }
  if (msg.content && msg.content.length > 0) {
    return '已回复'
  }
  return '已完成'
}

// 从消息内容提取一句话摘要（用于折叠态展示核心结论）
function getContentSummary(msg) {
  if (!msg.content) return ''
  // 取第一段非空、非标题的文本
  const lines = msg.content.split('\n').map(l => l.trim()).filter(Boolean)
  for (const line of lines) {
    // 跳过纯标题行、工具调用标记
    if (line.startsWith('#') || line.startsWith('```')) continue
    // 去除 markdown 标记
    let text = line
      .replace(/[#*`>_\[\]()~-]/g, '')
      .replace(/\s+/g, ' ')
      .trim()
    if (text.length > 0) {
      if (text.length > 80) {
        return text.slice(0, 80) + '...'
      }
      return text
    }
  }
  return ''
}

// formatCollapsedTools 已抽取到 utils/toolIcons.js（通过 import 导入）

// 文件点评功能
const fileFeedbackVisible = ref(false)
const agentFeedbackVisible = ref(false)
const feedbackContent = ref('')
const feedbackFilePath = ref('')
const feedbackTargetAgent = ref('')
const feedbackTargetMsgId = ref('')
const fileListForFeedback = ref([])

// @ 智能体提及功能
const mentionVisible = ref(false)
const mentionIndex = ref(0)
const mentionStartPos = ref(-1)
const mentionSearch = ref('')

const filteredAgents = computed(() => {
  if (!store.currentConvAgents) return []
  const search = mentionSearch.value.toLowerCase()
  return store.currentConvAgents.filter(a => {
    if (!search) return true
    return a.name.toLowerCase().includes(search) || a.role?.toLowerCase().includes(search)
  })
})

function handleInputChange() {
  const text = inputText.value
  // 简单检测：找到最后一个 @ 符号
  const lastAtIndex = text.lastIndexOf('@')
  if (lastAtIndex === -1) {
    mentionVisible.value = false
    return
  }
  // 检查 @ 后面是否有空格（还没输入完）
  const afterAt = text.substring(lastAtIndex + 1)
  if (afterAt.includes(' ') || afterAt.includes('\n')) {
    mentionVisible.value = false
    return
  }
  // 显示选择器
  mentionStartPos.value = lastAtIndex
  mentionSearch.value = afterAt
  mentionVisible.value = true
  mentionIndex.value = 0
}

function selectMention(agent) {
  const text = inputText.value
  const before = text.substring(0, mentionStartPos.value)
  const after = text.substring(mentionStartPos.value + mentionSearch.value.length + 1)
  inputText.value = before + '@' + agent.name + ' ' + after
  mentionVisible.value = false
  nextTick(() => {
    // 聚焦输入框
    const textarea = textareaRef.value?.$el?.querySelector('textarea')
    if (textarea) textarea.focus()
  })
}

function handleMentionKey(dir) {
  if (!mentionVisible.value) return
  if (dir === 'down') {
    mentionIndex.value = Math.min(mentionIndex.value + 1, filteredAgents.value.length - 1)
  } else {
    mentionIndex.value = Math.max(mentionIndex.value - 1, 0)
  }
}

function handleMentionEnter(e) {
  if (mentionVisible.value && filteredAgents.value.length > 0) {
    e.preventDefault()
    selectMention(filteredAgents.value[mentionIndex.value])
  }
  // 否则不阻止，让 textarea 正常换行
}

function mentionButtonClick() {
  // 点击@按钮，手动触发选择器
  if (!inputText.value || inputText.value.endsWith(' ') || inputText.value.endsWith('\n') || inputText.value === '') {
    inputText.value += '@'
  } else {
    inputText.value += ' @'
  }
  handleInputChange()
  nextTick(() => {
    const textarea = textareaRef.value?.$el?.querySelector('textarea')
    if (textarea) textarea.focus()
  })
}

const emit = defineEmits(['open-api-config'])

// 建议气泡
const suggestions = [
  '帮我写个项目介绍文档',
  '检查代码有没有bug',
  '分析一下这个需求是否合理',
  '帮我整理会议纪要',
]

// 工作目录面板
const filePanelOpen = ref(false)
const todoPanelOpen = ref(false)  // TODO 面板开关（默认折叠）
const showPathBar = ref(false)
const pathSetting = ref(false)
const projectPathInput = ref('')
const rightPanelTab = ref('files')  // 右侧面板当前 tab：files / outputs

// 产出文件查看
const outputViewerVisible = ref(false)
const outputViewerTitle = ref('')
const outputViewerContent = ref('')

// 从对话消息中提取代码块作为产出文件
const outputFiles = computed(() => {
  const files = []
  for (const msg of store.messages) {
    // 兼容 assistant 和 agent 两种 role
    if ((msg.role !== 'assistant' && msg.role !== 'agent') || !msg.content) continue
    const blocks = extractCodeBlocks(msg.content)
    for (const block of blocks) {
      files.push({
        ...block,
        time: msg.time || '',
        agent: msg.agent_id || ''
      })
    }
  }
  return files
})

// 从 Markdown 内容中提取代码块
function extractCodeBlocks(content) {
  const blocks = []
  const regex = /```(\w*)(?::([^\n]+))?\n([\s\S]*?)```/g
  let match
  while ((match = regex.exec(content)) !== null) {
    const language = match[1] || ''
    const filename = match[2]?.trim() || ''
    const code = match[3].trim()
    if (!code) continue
    const name = filename || `代码片段 ${blocks.length + 1}.${language || 'txt'}`
    blocks.push({ name, language, code })
  }
  return blocks
}

// 获取产出文件图标
// 文件图标函数已抽取到 utils/fileIcons.js
// getFileIcon / getLanguageIcon / isImageFile 从该模块导入

// 查看产出文件
function viewOutputFile(file) {
  outputViewerTitle.value = file.name
  outputViewerContent.value = file.code
  outputViewerVisible.value = true
}

// 复制产出内容
async function copyOutputContent() {
  try {
    await navigator.clipboard.writeText(outputViewerContent.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

// 编辑智能体
const editDialogVisible = ref(false)
const editingAgentId = ref('')
const savingEdit = ref(false)
const editPathInput = ref('')

// 导出蓝图
const showExportBlueprint = ref(false)
const exportingBp = ref(false)
const exportBpForm = ref({
  blueprint_name: '',
  description: '',
  category: 'general'
})

async function handleExportBlueprint() {
  if (!store.currentConversationId) {
    ElMessage.warning('请先选择一个项目')
    return
  }
  exportingBp.value = true
  try {
    const res = await api.exportBlueprintFromConversation(store.currentConversationId, exportBpForm.value)
    ElMessage.success(res.data.message || '团队已导出为蓝图')
    showExportBlueprint.value = false
    exportBpForm.value = { blueprint_name: '', description: '', category: 'general' }
  } catch (e) {
    ElMessage.error('导出失败：' + (e.response?.data?.detail || e.message))
  } finally {
    exportingBp.value = false
  }
}
const editForm = ref({
  name: '',
  role: '',
  avatar: '',
  system_prompt: '',
  allowed_paths: [],
  model_config_id: '',
  enabled_skills: [],
  can_invoke_sub_agent: false
})

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
loadSkills()

function getAgent(id) {
  return store.getAgentById(id)
}

// 加载配置列表
const configs = ref([])
async function loadConfigs() {
  try {
    const res = await api.getModelConfigs()
    configs.value = res.data.configs || []
    // 初始化 selectedDefaultConfig（从 store 同步）
    if (store.defaultConfigId && !configs.value.find(c => c.id === store.defaultConfigId)) {
      // 存的配置已删除，重置
      store.setDefaultConfig('')
    }
  } catch (e) {}
}
loadConfigs()

// 会话级默认模型选择（双向绑定 store）
const selectedDefaultConfig = ref(store.defaultConfigId)
function handleDefaultConfigChange(val) {
  store.setDefaultConfig(val)
}

// 思考模式开关：三态循环 自动(null) → 思考(true) → 直答(false) → 自动(null)
const thinkingTooltip = computed(() => {
  if (store.enableThinking === true) return '思考模式：已开启（LLM 会先推理再行动）'
  if (store.enableThinking === false) return '思考模式：已关闭（LLM 直接回复）'
  return '思考模式：跟随配置（点击开启/关闭）'
})
function toggleThinking() {
  if (store.enableThinking === null) {
    store.setEnableThinking(true)
  } else if (store.enableThinking === true) {
    store.setEnableThinking(false)
  } else {
    store.setEnableThinking(null)
  }
}

// 获取智能体当前配置名称
function getAgentModelName(agent) {
  const mc = agent?.model_config
  if (!mc?.model && !mc?.config_id) return ''
  // 优先从配置列表匹配
  const cfg = configs.value.find(c => c.id === mc.config_id)
  if (cfg) return cfg.name
  return mc.model || ''
}

// 智能体芯片下拉命令处理
async function handleAgentCommand(agent, cmd) {
  if (cmd === 'select') {
    store.selectAgent(agent.id)
  } else if (cmd === 'thread') {
    openThread(agent.id)
  } else if (cmd === 'edit') {
    editForm.value = {
      name: agent.name,
      role: agent.role,
      avatar: agent.avatar,
      system_prompt: agent.system_prompt || '',
      allowed_paths: [...(agent.allowed_paths || [])],
      model_config_id: agent.model_config?.config_id || '',
      enabled_skills: Array.isArray(agent.enabled_skills) ? [...agent.enabled_skills] : [],
      can_invoke_sub_agent: !!agent.can_invoke_sub_agent
    }
    editingAgentId.value = agent.id
    editDialogVisible.value = true
  } else if (cmd.startsWith('use_config:')) {
    const cfgId = cmd.slice(11)
    const cfg = configs.value.find(c => c.id === cfgId)
    if (cfg) {
      await store.updateConversationAgent(agent.id, {
        name: agent.name,
        role: agent.role,
        avatar: agent.avatar,
        system_prompt: agent.system_prompt || '',
        allowed_paths: agent.allowed_paths || ['*'],
        model_cfg: {
          config_id: cfg.id,
        }
      })
      ElMessage.success(`${agent.name} 已切换到「${cfg.name}」`)
      await loadConfigs()
    }
  }
}

async function handleSend() {
  if ((!inputText.value.trim() && attachedFiles.value.length === 0) || store.loading) return
  
  const text = inputText.value
  inputText.value = ''
  
  // 如果有附件，先上传到项目目录，再把文件信息附加到消息里
  let finalText = text
  if (attachedFiles.value.length > 0) {
    if (!store.currentConversationId) {
      ElMessage.warning('请先选择一个项目')
      attachedFiles.value = []
      return
    }
    if (!store.currentRootPath) {
      ElMessage.warning('请先设置项目工作目录')
      return
    }
    
    const uploadedFiles = []
    for (const f of attachedFiles.value) {
      try {
        const res = await api.uploadFile(f.file, store.currentConversationId)
        uploadedFiles.push({
          name: res.data.filename,
          path: res.data.relative_path,
          size: res.data.size,
        })
      } catch (e) {
        ElMessage.error(`文件「${f.name}」上传失败：${e.response?.data?.detail || e.message}`)
      }
    }
    
    if (uploadedFiles.length > 0) {
      // 把文件信息附加到消息文本，让智能体知道有哪些文件
      const fileList = uploadedFiles.map(f => `- ${f.name}（路径：${f.path}，大小：${formatFileSize(f.size)}）`).join('\n')
      finalText = `${text}\n\n📎 已上传文件：\n${fileList}\n\n请读取上述文件并处理。`
    }
    
    attachedFiles.value = []  // 清空附件列表
  }
  
  await store.sendMessage(finalText)
  scrollToBottom()
}

// 停止生成
function handleStopGeneration() {
  store.stopGeneration()
}

async function handleCopy(content) {
  await store.copyMessage(content)
  ElMessage.success('已复制到剪贴板')
}

async function handleRegenerate(msg) {
  if (!msg.id || store.loading) return
  await store.regenerateMessage(msg.id)
  scrollToBottom()
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

// 流式输出时持续滚动到底部
// 监听 messages.length 变化（新消息加入时滚动）
watch(() => store.messages.length, scrollToBottom)
// 监听流式状态变化，开始/结束流式时滚动
watch(() => store.isStreaming, (streaming) => {
  if (streaming) scrollToBottom()
})
// 监听流式内容变化（token 追加时滚动）- 用 streamingAgents 的 values 拼接长度作为轻量触发
watch(() => Object.values(store.streamingAgents).join('').length, () => {
  if (store.isStreaming) scrollToBottom()
})

watch(() => store.currentConversationId, () => {
  projectPathInput.value = store.currentRootPath || ''
  // 不在这里调 loadMessages——selectConversation 已处理消息加载
})

watch(() => store.currentRootPath, (val) => {
  projectPathInput.value = val || ''
})

// 初始化路径输入
projectPathInput.value = store.currentRootPath || ''

watch(() => store.currentAgentId, () => {
  populateEditForm()
})

watch(editDialogVisible, (val) => {
  if (val) {
    nextTick(() => populateEditForm())
  }
})

watch(() => store.currentAgent, (agent) => {
  if (agent && editDialogVisible.value) {
    populateEditForm()
  }
})

function populateEditForm() {
  // 优先使用 editingAgentId 对应的智能体，否则用当前选中的智能体
  const targetId = editingAgentId.value || store.currentAgentId
  const agent = store.getAgentById(targetId) || store.currentAgent
  if (agent) {
    editForm.value = {
      name: agent.name,
      role: agent.role,
      avatar: agent.avatar,
      system_prompt: agent.system_prompt || '',
      allowed_paths: [...(agent.allowed_paths || [])],
      model_config_id: agent.model_config?.config_id || '',
      enabled_skills: [...(agent.enabled_skills || [])],
      can_invoke_sub_agent: agent.can_invoke_sub_agent ?? false
    }
  }
}

// 设置项目工作目录
async function handleSetProjectPath() {
  const p = projectPathInput.value.trim()
  pathSetting.value = true
  try {
    await store.updateConversationRootPath(p)
    ElMessage.success(p ? '工作目录已设置' : '已清除工作目录')
    showPathBar.value = false
    if (p) {
      filePanelOpen.value = true
    } else {
      filePanelOpen.value = false
    }
  } catch (e) {
    ElMessage.error('设置失败：' + (e.response?.data?.detail || e.message))
  } finally {
    pathSetting.value = false
  }
}

// 切换文件面板显示
// 开启新任务：清空当前项目的对话消息，保留团队成员和项目文件
async function handleClearMessages() {
  if (!store.currentConversationId) {
    ElMessage.warning('请先选择一个项目')
    return
  }
  try {
    await ElMessageBox.confirm(
      '将清空当前项目的对话历史，开始新任务。\n\n保留的内容：\n• 团队成员（智能体配置）\n• 项目文件和任务产出\n\n清除的内容：\n• 所有对话消息（主智能体不再记得之前的任务）',
      '开启新任务',
      {
        confirmButtonText: '确认清空',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      }
    )
  } catch (e) {
    return  // 用户取消
  }
  try {
    const res = await store.clearConversationMessages(store.currentConversationId)
    ElMessage.success(res.message || '已开启新任务')
  } catch (e) {
    ElMessage.error('清空失败：' + (e.response?.data?.detail || e.message))
  }
}

function toggleFilePanel() {
  if (!store.currentRootPath) {
    // 没有设置目录，打开设置栏
    showPathBar.value = true
    filePanelOpen.value = false
  } else {
    filePanelOpen.value = !filePanelOpen.value
    if (filePanelOpen.value) {
      showPathBar.value = false
    }
  }
}

// 打开路径设置
function openPathSettings() {
  showPathBar.value = true
  projectPathInput.value = store.currentRootPath
}

// ===== 文件上传功能 =====
// 触发文件选择对话框
function triggerFileUpload() {
  if (!fileInputRef.value) return
  fileInputRef.value.value = ''  // 清空，允许重复选同一文件
  fileInputRef.value.click()
}

// 处理文件选择
function handleFileSelect(event) {
  const files = Array.from(event.target.files || [])
  if (files.length === 0) return
  for (const file of files) {
    // 限制单个文件 10MB
    if (file.size > 10 * 1024 * 1024) {
      ElMessage.warning(`文件「${file.name}」超过 10MB，请减小后再上传`)
      continue
    }
    attachedFiles.value.push({
      file,
      name: file.name,
      size: file.size,
      type: file.type,
    })
  }
  // 焦点回到输入框
  focusTextarea()
}

// 移除已选中的文件
function removeAttachedFile(idx) {
  attachedFiles.value.splice(idx, 1)
}

// 格式化文件大小
function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

// 根据文件类型返回图标
// getFileIcon / isImageFile 已抽取到 utils/fileIcons.js（通过 import 导入）

// 焦点回到输入框
function focusTextarea() {
  nextTick(() => {
    const textarea = textareaRef.value?.$el?.querySelector('textarea')
    if (textarea) textarea.focus()
  })
}

// 处理文件点评反馈，直接发送给主智能体
async function handleFileFeedback(text) {
  inputText.value = text
  await handleSend()
}

// ===== 文件点评功能 =====
// 打开文件点评弹窗（从输入框工具栏触发）
async function openFileFeedbackDialog() {
  feedbackContent.value = ''
  feedbackFilePath.value = ''
  // 加载文件列表供选择
  if (store.currentRootPath) {
    try {
      const res = await api.listFiles('main', store.currentRootPath)
      const items = res.data.items || []
      // 构建文件列表（只显示文件，不显示目录；包含相对路径）
      fileListForFeedback.value = items
        .filter(f => !f.is_dir)
        .map(f => ({
          name: f.name,
          path: f.path,
          relPath: f.path.replace(store.currentRootPath, '').replace(/^\//, ''),
          is_dir: false
        }))
      // 如果没有文件，也加载子目录的文件
      if (fileListForFeedback.value.length === 0) {
        for (const dir of items.filter(f => f.is_dir)) {
          try {
            const subRes = await api.listFiles('main', dir.path)
            const subItems = (subRes.data.items || []).filter(f => !f.is_dir)
            subItems.forEach(f => {
              fileListForFeedback.value.push({
                name: f.name,
                path: f.path,
                relPath: f.path.replace(store.currentRootPath, '').replace(/^\//, ''),
                is_dir: false
              })
            })
          } catch (e) { /* 忽略子目录加载错误 */ }
        }
      }
    } catch (e) {
      ElMessage.error('加载文件列表失败：' + (e.response?.data?.detail || e.message))
    }
  }
  fileFeedbackVisible.value = true
}

// 提交文件点评
async function submitFileFeedback() {
  const text = feedbackContent.value.trim()
  if (!text) return
  const filePath = feedbackFilePath.value || '(未指定文件)'
  const feedbackMsg = `【文件点评】文件：${filePath}\n\n${text}`
  fileFeedbackVisible.value = false
  inputText.value = feedbackMsg
  await handleSend()
}

// 打开智能体回复点评弹窗（从智能体回复下方触发）
function openFeedbackDialog(msg) {
  feedbackContent.value = ''
  feedbackTargetMsgId.value = msg.id
  const agent = store.currentConvAgents?.find(a => a.id === msg.agent_id) || store.agents?.find(a => a.id === msg.agent_id)
  feedbackTargetAgent.value = agent ? `${agent.avatar} ${agent.name}（${agent.role}）` : '智能体'
  agentFeedbackVisible.value = true
}

// 提交智能体回复点评
async function submitAgentFeedback() {
  const text = feedbackContent.value.trim()
  if (!text) return
  const feedbackMsg = `【回复点评】给 ${feedbackTargetAgent.value} 的反馈：\n\n${text}`
  agentFeedbackVisible.value = false
  inputText.value = feedbackMsg
  await handleSend()
}

// getToolIcon / formatToolCall 已抽取到 utils/toolIcons.js（通过 import 导入）

// 打开智能体工作线程面板
function openThread(agentId) {
  threadAgentId.value = agentId
  threadVisible.value = true
}

// 获取子智能体工具调用摘要
function getSubAgentSummary(msg) {
  if (!msg.toolEvents || msg.toolEvents.length === 0) return ''
  const doneCount = msg.toolEvents.filter(t => t.status === 'done').length
  const running = msg.toolEvents.some(t => t.status === 'running')
  if (running) {
    return `正在执行 ${doneCount + 1}/${msg.toolEvents.length} 个操作`
  }
  return `完成 ${doneCount} 个操作`
}

// 获取子智能体回复预览（去除markdown，取前40字）
function getSubAgentPreview(msg) {
  if (msg.streaming && (!msg.content || msg.content.length < 5)) {
    return '工作中...'
  }
  if (!msg.content) return '等待回复...'
  // 简单去除markdown标记
  let text = msg.content
    .replace(/[#*`>_\[\]()~-]/g, '')
    .replace(/\n+/g, ' ')
    .trim()
  if (text.length > 40) {
    text = text.slice(0, 40) + '...'
  }
  return text || '已完成'
}

function addEditPath() {
  const p = editPathInput.value.trim()
  if (p && !editForm.value.allowed_paths.includes(p)) {
    editForm.value.allowed_paths.push(p)
  }
  editPathInput.value = ''
}

async function handleSaveEdit() {
  if (!editForm.value.name || !editForm.value.role) {
    ElMessage.warning('请填写名称和角色')
    return
  }
  savingEdit.value = true
  try {
    const targetId = editingAgentId.value || store.currentAgentId
    const payload = {
      name: editForm.value.name,
      role: editForm.value.role,
      avatar: editForm.value.avatar,
      system_prompt: editForm.value.system_prompt,
      allowed_paths: editForm.value.allowed_paths.length > 0 ? editForm.value.allowed_paths : ['*'],
      enabled_skills: editForm.value.enabled_skills,
      can_invoke_sub_agent: editForm.value.can_invoke_sub_agent
    }
    // 模型配置：空字符串表示使用全局默认（清除绑定）
    if (editForm.value.model_config_id) {
      payload.model_cfg = { config_id: editForm.value.model_config_id }
    } else {
      payload.model_cfg = {}
    }
    await store.updateConversationAgent(targetId, payload)
    ElMessage.success('保存成功（仅当前对话）')
    editDialogVisible.value = false
    editingAgentId.value = ''
  } catch (e) {
    ElMessage.error('保存失败：' + (e.response?.data?.detail || e.message))
  } finally {
    savingEdit.value = false
  }
}
</script>

<style scoped>
.chat-window {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f8fafc;
}

/* 主内容区：聊天 + 文件浏览器 */
.chat-main {
  flex: 1;
  display: flex;
  min-height: 0;
}

.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.file-panel {
  width: 300px;
  flex-shrink: 0;
  border-left: 1px solid #e2e8f0;
  background: #fff;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* TODO 面板包装（侧边栏样式） */
.todo-panel-wrapper {
  width: 260px;
  flex-shrink: 0;
  border-left: 1px solid #e2e8f0;
  background: #fff;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 面板 tab 切换 */
.panel-tabs {
  display: flex;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.panel-tab {
  flex: 1;
  padding: 10px 8px;
  text-align: center;
  font-size: 13px;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s;
  border-bottom: 2px solid transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.panel-tab:hover {
  color: #475569;
  background: #f8fafc;
}

.panel-tab.active {
  color: #6366f1;
  border-bottom-color: #6366f1;
  font-weight: 600;
}

.tab-badge {
  font-size: 10px;
  background: #6366f1;
  color: #fff;
  border-radius: 10px;
  padding: 0 5px;
  min-width: 16px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.panel-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 产出文件列表 */
.outputs-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.outputs-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 16px;
  color: #94a3b8;
  text-align: center;
}

.outputs-empty-icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.outputs-empty p {
  margin: 2px 0;
  font-size: 13px;
}

.outputs-empty-desc {
  font-size: 12px !important;
  color: #cbd5e1;
}

.output-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.output-item:hover {
  background: #f1f5f9;
}

.output-icon {
  font-size: 20px;
  flex-shrink: 0;
}

.output-info {
  flex: 1;
  min-width: 0;
}

.output-name {
  font-size: 13px;
  font-weight: 500;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.output-meta {
  display: flex;
  gap: 8px;
  margin-top: 2px;
}

.output-lang {
  font-size: 11px;
  color: #6366f1;
  background: #eef2ff;
  padding: 0 6px;
  border-radius: 4px;
}

.output-time {
  font-size: 11px;
  color: #94a3b8;
}

/* 产出文件查看对话框 */
.output-viewer-content {
  max-height: 60vh;
  overflow: auto;
}

.output-code-block {
  background: #1e293b;
  color: #e2e8f0;
  padding: 16px;
  border-radius: 8px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
  overflow-x: auto;
  margin: 0;
}

.output-code-block code {
  font-family: inherit;
}

/* 顶部栏 */
.chat-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 28px;
  background: #fff;
  border-bottom: 1px solid #f1f5f9;
  backdrop-filter: blur(10px);
}

.agent-team {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.agent-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 9999px;
  cursor: pointer;
  transition: all 0.25s ease;
  font-size: 13px;
  color: #475569;
  background: #f1f5f9;
  border: 1px solid transparent;
}

.agent-chip:hover {
  background: #eef2ff;
  border-color: #818cf8;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.15);
}

.agent-chip.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-color: transparent;
  color: #fff;
  font-weight: 500;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.agent-chip.active .chip-model {
  color: rgba(255, 255, 255, 0.75);
}

.agent-chip.active .chip-arrow {
  color: rgba(255, 255, 255, 0.7);
}

.chip-avatar {
  font-size: 16px;
}

.chip-name {
  white-space: nowrap;
}

.chip-level-tag {
  font-size: 9px;
  font-weight: 600;
  padding: 1px 4px;
  border-radius: 3px;
  background: #ede9fe;
  color: #5b21b6;
  margin-left: -2px;
}

.chip-model {
  font-size: 11px;
  opacity: 0.7;
}

.chip-arrow {
  font-size: 10px;
  color: #94a3b8;
  transition: transform 0.15s ease;
}

.chip-arrow.open {
  transform: rotate(90deg);
}

.topbar-actions {
  display: flex;
  gap: 4px;
}

.topbar-actions .el-button {
  border-radius: 12px;
  padding: 8px 14px !important;
  height: auto !important;
  font-size: 13px !important;
  transition: all 0.25s ease !important;
}

.topbar-actions .el-button.active {
  color: #6366f1;
  background: #eef2ff;
  font-weight: 500;
}

/* 项目工作目录栏（位于输入框上方，紧贴输入框） */
.project-path-bar {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-bottom: none;
  border-radius: 12px 12px 0 0;
  padding: 12px 16px 10px;
  margin-bottom: -2px;  /* 让路径栏和输入框无缝衔接 */
  animation: slideDown 0.2s ease;
}

@keyframes slideDown {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

.path-input-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.path-info {
  margin-top: 8px;
  font-size: 12px;
  color: #475569;
  display: flex;
  align-items: center;
  gap: 6px;
}

.path-label {
  color: #94a3b8;
}

.path-value {
  color: #6366f1;
  font-family: monospace;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.path-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.5;
}

/* 无目录提示横幅 */
.no-path-banner {
  background: #fef3c7;
  border-bottom: 1px solid #fde68a;
  padding: 10px 28px;
  font-size: 13px;
  color: #b45309;
  line-height: 1.5;
}

/* 工具调用事件 */
.tool-events {
  margin-bottom: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tool-event {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #64748b;
  padding: 6px 12px;
  background: #f8fafc;
  border-radius: 8px;
  border-left: 3px solid #e2e8f0;
  transition: all 0.25s ease;
}

.tool-event.done {
  color: #059669;
  border-left-color: #10b981;
  background: #ecfdf5;
}

.tool-event.running {
  color: #6366f1;
  border-left-color: #6366f1;
  background: #eef2ff;
}

.tool-icon {
  font-size: 14px;
}

.tool-text {
  flex: 1;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
}

.tool-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid #6366f1;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.tool-check {
  color: #10b981;
  font-weight: bold;
  font-size: 12px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 聊天主体 */
.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 28px;
}

/* 欢迎页 */
.welcome-page {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  padding: 40px 0;
}

.welcome-title {
  font-size: 32px;
  font-weight: 700;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 32px;
}

.suggestion-bubbles {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
  max-width: 700px;
}

.suggestion-bubble {
  padding: 12px 22px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 9999px;
  font-size: 14px;
  color: #475569;
  cursor: pointer;
  transition: all 0.25s ease;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.suggestion-bubble:hover {
  background: #eef2ff;
  border-color: #818cf8;
  color: #6366f1;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.2);
}

/* 消息 */
/* 阶段3：并行调度批次指示器 */
.batch-status-bar {
  margin: 4px 0 12px;
  padding: 0 12px;
}
.batch-status-content {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 14px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(168, 85, 247, 0.08));
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 10px;
  font-size: 13px;
  color: #6366f1;
}
.batch-icon {
  font-size: 15px;
  animation: batch-pulse 1.5s ease-in-out infinite;
}
@keyframes batch-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.batch-text {
  font-weight: 500;
}
.batch-progress {
  color: #9ca3af;
  font-weight: 400;
  font-size: 12px;
}
.batch-agents {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.batch-agent-chip {
  padding: 2px 8px;
  background: rgba(99, 102, 241, 0.1);
  border-radius: 8px;
  font-size: 11px;
  color: #4f46e5;
  white-space: nowrap;
}

.msg-row {
  display: flex;
  margin-bottom: 20px;
  padding: 8px 0;
}

.msg-row.user {
  justify-content: flex-end;
}

.msg-row.agent {
  justify-content: flex-start;
}

/* 用户消息行：气泡在左，头像在右（整体右对齐） */
.user-msg-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  max-width: 75%;
  margin-left: auto;
}

.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
  order: 2;  /* 头像在右 */
}

.user-msg-row .bubble {
  flex: 1;
  min-width: 0;
  order: 1;  /* 气泡在左 */
}

/* 子智能体行 */
.agent-row.is-sub-agent {
  margin-bottom: 8px;
  padding: 4px 0;
}

/* 子智能体折叠卡片 */
.sub-agent-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.25s ease;
  max-width: 70%;
  flex: 1;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.sub-agent-card:hover {
  background: #fafbff;
  border-color: #818cf8;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.15);
}

.sub-agent-card.thinking-card {
  background: #eef2ff;
  border-color: #818cf8;
  cursor: default;
}

.sub-card-left {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: hidden;
  flex: 1;
}

.sub-card-right {
  flex-shrink: 0;
  color: #6366f1;
  font-size: 12px;
  font-weight: 500;
}

.sub-agent-name {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  flex-shrink: 0;
}

.sub-agent-status {
  font-size: 12px;
  color: #6366f1;
  flex-shrink: 0;
}

.sub-agent-preview {
  font-size: 12px;
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sub-agent-preview.streaming {
  color: #6366f1;
}

.thread-hint {
  font-size: 11px;
  opacity: 0.8;
}

.sub-avatar {
  font-size: 22px;
  margin-top: 0;
  cursor: pointer;
  opacity: 0.9;
  transition: all 0.25s ease;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #f1f5f9;
}

.sub-avatar:hover {
  opacity: 1;
  background: #eef2ff;
  transform: translateY(-1px);
}

.thinking-avatar {
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

.bubble {
  max-width: 75%;
  padding: 14px 18px;
  border-radius: 16px;
}

.user-bubble {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  border-bottom-right-radius: 4px;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

/* 用户消息里的 markdown 渲染样式适配深色背景 */
.user-bubble .markdown-body {
  color: #fff;
}

.user-bubble .markdown-body code {
  background: rgba(255, 255, 255, 0.15);
  color: #fef3c7;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}

.user-bubble .markdown-body pre {
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.user-bubble .markdown-body pre code {
  background: transparent;
  color: #fff;
  padding: 0;
}

.user-bubble .markdown-body a {
  color: #fef3c7;
  text-decoration: underline;
}

.user-bubble .markdown-body blockquote {
  border-left-color: rgba(255, 255, 255, 0.4);
  color: rgba(255, 255, 255, 0.85);
  background: rgba(255, 255, 255, 0.05);
}

.user-bubble .markdown-body strong {
  color: #fff;
}

.agent-bubble {
  background: #fff;
  color: #0f172a;
  border: 1px solid #e2e8f0;
  border-bottom-left-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.agent-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.agent-avatar-small {
  font-size: 22px;
  margin-top: 2px;
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: linear-gradient(135deg, #eef2ff 0%, #f3e8ff 100%);
  border: 1px solid #e0e7ff;
}

.agent-message-wrap {
  max-width: 75%;
}

.agent-name-label {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 6px;
  margin-left: 4px;
  font-weight: 500;
}

.agent-summary-tag {
  color: #94a3b8;
  font-weight: 400;
  margin-left: 4px;
}

/* 折叠态调度行卡片（Trae 风格） */
.agent-collapsed-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  border-left: 3px solid #cbd5e1;
}

.agent-collapsed-card:hover {
  background: #f1f5f9;
  border-color: #94a3b8;
  border-left-color: #64748b;
}

.is-sub-agent .agent-collapsed-card {
  background: #faf5ff;
  border-color: #e9d5ff;
  border-left-color: #a78bfa;
}

.is-sub-agent .agent-collapsed-card:hover {
  background: #f5f0ff;
  border-color: #c4b5fd;
  border-left-color: #8b5cf6;
}

.collapsed-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.collapsed-tools {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #6366f1;
  font-weight: 500;
}

.collapsed-tool-icon {
  font-size: 12px;
}

.collapsed-tool-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.collapsed-summary {
  font-size: 13px;
  color: #475569;
  line-height: 1.5;
}

.collapsed-summary.placeholder {
  color: #94a3b8;
  font-style: italic;
}

.collapsed-quote {
  display: inline-block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.collapsed-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.expand-btn {
  color: #6366f1 !important;
  font-size: 12px !important;
  padding: 2px 8px !important;
}

.expand-icon {
  display: inline-block;
  transition: transform 0.2s;
  font-size: 10px;
}

.thread-btn {
  padding: 2px 6px !important;
}

.collapse-btn {
  color: #94a3b8 !important;
  font-size: 12px !important;
}

.content {
  font-size: 15px;
  line-height: 1.7;
  word-break: break-word;
  color: #0f172a;
}

/* ===== 统一的消息操作栏（Trae 风格：图标按钮组） ===== */
.msg-action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
  gap: 8px;
  min-height: 24px;
}

.action-icon-group {
  display: flex;
  align-items: center;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.2s ease;
}

/* 悬停消息时才显示操作按钮（更清爽） */
.agent-bubble:hover .action-icon-group,
.user-bubble:hover .action-icon-group,
.agent-collapsed-card:hover .action-icon-group {
  opacity: 1;
}

/* 流式输出时强制显示（避免看不到操作） */
.agent-bubble .action-icon-group:has(.streaming),
.bubble:has(.content.streaming) ~ .msg-action-bar .action-icon-group {
  opacity: 1;
}

.action-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.15s ease;
}

.action-icon-btn:hover {
  background: #f1f5f9;
  color: #475569;
}

.action-icon-btn:active {
  transform: scale(0.92);
}

.action-icon-btn svg {
  display: block;
  pointer-events: none;
}

.action-time {
  font-size: 11px;
  color: #cbd5e1;
  font-variant-numeric: tabular-nums;
  user-select: none;
}

/* 用户消息的操作栏（深色背景，白色图标） */
.user-action-bar .action-icon-btn {
  color: rgba(255, 255, 255, 0.6);
}

.user-action-bar .action-icon-btn:hover {
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
}

.user-action-bar .action-time {
  color: rgba(255, 255, 255, 0.5);
}

/* 折叠态卡片里的操作按钮（常驻显示，因为卡片本身就是悬停态才点） */
.agent-collapsed-card .action-icon-group {
  opacity: 1;
}

.agent-collapsed-card .action-icon-btn {
  width: 24px;
  height: 24px;
}

/* 点评弹窗 */
.feedback-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.feedback-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.feedback-label {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}
.feedback-target {
  padding: 10px 14px;
  background: #f8fafc;
  border-radius: 8px;
  font-size: 13px;
  color: #475569;
  border: 1px solid #f1f5f9;
}

.typing {
  color: #94a3b8;
  display: flex;
  align-items: center;
  gap: 8px;
}

.typing-dots {
  display: inline-flex;
  gap: 3px;
}

.typing-dots span {
  width: 6px;
  height: 6px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 50%;
  animation: typingBounce 1.4s infinite ease-in-out both;
}

.typing-dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.typing-dots span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes typingBounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* Markdown 样式 */
.markdown-body {
  font-size: 15px;
  line-height: 1.7;
  word-wrap: break-word;
  color: #0f172a;
}

.markdown-body :deep(p) {
  margin: 0 0 0.8em 0;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin: 1em 0 0.6em 0;
  font-weight: 600;
  line-height: 1.4;
  color: #0f172a;
}

.markdown-body :deep(h1) { font-size: 1.4em; }
.markdown-body :deep(h2) { font-size: 1.25em; }
.markdown-body :deep(h3) { font-size: 1.1em; }
.markdown-body :deep(h4) { font-size: 1em; }

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 1.5em;
  margin: 0.5em 0;
}

.markdown-body :deep(li) {
  margin: 0.2em 0;
}

.markdown-body :deep(blockquote) {
  margin: 0.8em 0;
  padding: 0.8em 1em;
  border-left: 4px solid #6366f1;
  color: #475569;
  background: #eef2ff;
  border-radius: 0 8px 8px 0;
}

.markdown-body :deep(code) {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  background: #f1f5f9;
  color: #4f46e5;
  padding: 0.15em 0.4em;
  border-radius: 4px;
  font-size: 0.9em;
}

.markdown-body :deep(pre) {
  margin: 0.8em 0;
  border-radius: 12px;
  overflow-x: auto;
  background: #1e293b !important;
}

.markdown-body :deep(pre code) {
  background: none !important;
  color: #e2e8f0;
  padding: 0;
  font-size: 0.88em;
  line-height: 1.6;
}

.markdown-body :deep(.hljs) {
  padding: 1em !important;
  background: #1e293b !important;
  border-radius: 12px;
}

.markdown-body :deep(table) {
  border-collapse: collapse;
  margin: 0.8em 0;
  width: 100%;
  font-size: 0.9em;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #e2e8f0;
  padding: 0.6em 0.9em;
  text-align: left;
}

.markdown-body :deep(th) {
  background: #f8fafc;
  font-weight: 600;
  color: #0f172a;
}

.markdown-body :deep(a) {
  color: #6366f1;
  text-decoration: none;
}

.markdown-body :deep(a:hover) {
  color: #4f46e5;
  text-decoration: underline;
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid #e2e8f0;
  margin: 1.2em 0;
}

.markdown-body :deep(img) {
  max-width: 100%;
  border-radius: 8px;
}

/* 流式输出光标 */
.markdown-body.streaming::after {
  content: '▋';
  display: inline-block;
  color: #6366f1;
  animation: blink 1s step-end infinite;
  margin-left: 2px;
  font-weight: 100;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* 输入区 */
.input-area {
  padding: 12px 28px 20px;
}

/* Trae Work 风格输入框 */
.trae-input-wrapper {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 14px 16px 10px;
  transition: all 0.25s ease;
  display: flex;
  flex-direction: column;  /* 垂直堆叠：附件栏 / 输入框 / 工具栏 */
  gap: 0;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.06);
}

.trae-input-wrapper:focus-within {
  border-color: #6366f1;
  background: #fff;
  box-shadow: 0 4px 24px rgba(99, 102, 241, 0.18);
  transform: translateY(-1px);
}

.trae-input-wrapper .el-textarea__inner {
  border: none;
  box-shadow: none;
  padding: 6px 4px;
  font-size: 14px;
  resize: none;
  background: transparent;
  width: 100%;
  color: #0f172a;
  line-height: 1.7;
  min-height: 72px;  /* 至少 3 行 */
}

.trae-input-wrapper .el-textarea__inner::placeholder {
  color: #94a3b8;
}

/* 已选中的文件附件预览条 */
.attached-files-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 6px 8px 0;
  background: transparent;
}

.attached-file-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: #eef2ff;
  border: 1px solid #c7d2fe;
  border-radius: 6px;
  font-size: 12px;
  color: #4338ca;
  max-width: 200px;
  animation: slideDown 0.15s ease;
}

.attached-file-icon {
  font-size: 14px;
}

.attached-file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 120px;
}

.attached-file-size {
  color: #94a3b8;
  font-size: 11px;
}

.attached-file-remove {
  border: none;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  padding: 0 2px;
  border-radius: 3px;
}

.attached-file-remove:hover {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

/* 下方工具栏 */
.input-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 4px 2px;
  margin-top: 6px;
  border-top: 1px solid #f1f5f9;
  gap: 8px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 2px;
}

.toolbar-right {
  display: flex;
  align-items: center;
}

/* 中间：模型选择 + 思考开关（参考 Trae 布局） */
.toolbar-center {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
}

.model-select {
  width: 180px;
}
.model-select :deep(.el-select__wrapper) {
  min-height: 30px;
  font-size: 12px;
  border-radius: 8px;
  background: #f8fafc;
  box-shadow: none;
  border: 1px solid #e2e8f0;
}
.model-select :deep(.el-select__wrapper:hover) {
  border-color: #cbd5e1;
}

/* 思考模式三态开关 */
.thinking-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #64748b;
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.15s ease;
  min-height: 30px;
}
.thinking-toggle:hover {
  border-color: #cbd5e1;
  background: #f1f5f9;
}
.thinking-toggle.active {
  color: #6366f1;
  background: #eef2ff;
  border-color: #c7d2fe;
}
.thinking-toggle.inactive {
  color: #94a3b8;
  background: #f8fafc;
  border-color: #e2e8f0;
}
.thinking-label {
  font-weight: 500;
}

.toolbar-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 10px;
  border: none;
  background: transparent;
  color: #64748b;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.15s ease;
}

.toolbar-btn:hover {
  background: #f1f5f9;
  color: #475569;
}

.toolbar-btn:active {
  transform: scale(0.95);
}

.toolbar-btn-label {
  font-size: 12px;
  font-weight: 500;
}

/* 发送/停止按钮（工具栏右侧） */
.send-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 16px;
  border-radius: 10px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  box-shadow: 0 3px 10px rgba(99, 102, 241, 0.35);
}

.send-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 5px 14px rgba(99, 102, 241, 0.45);
}

.send-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
  box-shadow: none;
}

.send-btn-label {
  font-size: 13px;
}

.stop-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 16px;
  border-radius: 10px;
  background: #ef4444;
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  box-shadow: 0 3px 10px rgba(239, 68, 68, 0.35);
}

.stop-btn:hover {
  background: #dc2626;
  transform: translateY(-1px);
  box-shadow: 0 5px 14px rgba(239, 68, 68, 0.45);
}

/* 编辑弹窗 */
.path-input-row {
  display: flex;
  gap: 8px;
}

.path-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

/* 编辑智能体表单提示 */
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

/* 导出蓝图信息区 */
.export-bp-info {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 16px;
  margin-top: 8px;
}

.export-bp-info p {
  margin: 0 0 6px 0;
  font-size: 13px;
  color: #475569;
  line-height: 1.5;
}

.export-bp-info ul {
  margin: 0 0 8px 0;
  padding-left: 20px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.6;
}

.export-bp-info .export-tip {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
}

/* @ 智能体提及选择器 */
.mention-container {
  position: relative;
  width: 100%;
  display: flex;
  flex-direction: column;  /* 垂直堆叠：附件栏 / 输入框 / 工具栏 */
  gap: 0;
}
.mention-popover {
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  margin-bottom: 8px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  z-index: 1000;
  max-height: 260px;
  overflow-y: auto;
  overflow-x: hidden;
}
.mention-header {
  padding: 10px 14px;
  font-size: 12px;
  color: #64748b;
  border-bottom: 1px solid #f1f5f9;
  font-weight: 500;
}
.mention-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  cursor: pointer;
  transition: all 0.25s ease;
}
.mention-item:hover,
.mention-item.active {
  background: #eef2ff;
}
.mention-avatar {
  font-size: 22px;
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: linear-gradient(135deg, #eef2ff 0%, #f3e8ff 100%);
  border: 1px solid #e0e7ff;
}
.mention-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 2px;
}
.mention-name {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}
.mention-role {
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
