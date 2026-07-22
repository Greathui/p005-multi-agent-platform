<template>
  <el-drawer
    v-model="visible"
    :title="null"
    direction="rtl"
    size="480px"
    :with-header="false"
    class="thread-drawer"
    @close="handleClose"
  >
    <div class="thread-panel" v-if="agent">
      <!-- 线程头部 -->
      <div class="thread-header">
        <div class="thread-agent-info">
          <span class="thread-avatar">{{ agent.avatar }}</span>
          <div class="thread-agent-meta">
            <div class="thread-agent-name">{{ agent.name }}</div>
            <div class="thread-agent-role">{{ agent.role }}</div>
          </div>
        </div>
        <el-button text @click="visible = false" class="close-btn">✕</el-button>
      </div>

      <!-- 线程消息区 -->
      <div class="thread-body" ref="threadBodyRef">
        <div v-if="threadMessages.length === 0" class="thread-empty">
          <div class="empty-avatar">{{ agent.avatar }}</div>
          <div class="empty-text">这是你和「{{ agent.name }}」的单独对话</div>
          <div class="empty-tip">你可以直接给它发消息、提出修改意见，它会单独回复你</div>
        </div>

        <div v-for="(msg, i) in threadMessages" :key="msg.id || i" class="thread-msg" :class="msg.role">
          <template v-if="msg.role === 'user'">
            <div class="thread-bubble user-thread-bubble">
              <div class="thread-content">{{ msg.content }}</div>
              <div class="thread-time">{{ msg.time }}</div>
            </div>
          </template>
          <template v-else>
            <div class="thread-agent-row" :class="{ 'main-reply-row': msg.isMainReply }">
              <div class="thread-mini-avatar" :class="{ 'main-avatar': msg.isMainReply }">
                {{ msg.isMainReply ? '👤' : agent.avatar }}
              </div>
              <div class="thread-bubble agent-thread-bubble" :class="{ 'main-reply-bubble': msg.isMainReply }">
                <div v-if="msg.isMainReply" class="main-reply-tag">
                  <span class="main-reply-icon">↩</span>
                  <span>主智能体响应</span>
                </div>
                <div v-if="msg.toolEvents && msg.toolEvents.length > 0" class="tool-events mini">
                  <div v-for="(te, ti) in msg.toolEvents" :key="ti" class="tool-event" :class="te.status">
                    <span class="tool-icon">{{ getToolIcon(te.tool_name) }}</span>
                    <span class="tool-text">{{ formatToolCall(te) }}</span>
                    <span v-if="te.status === 'running'" class="tool-spinner"></span>
                    <span v-else-if="te.status === 'done'" class="tool-check">✓</span>
                  </div>
                </div>
                <div class="thread-content markdown-body" v-html="renderMarkdown(msg.content || '')" :class="{ streaming: msg.streaming }"></div>
                <div class="thread-msg-actions">
                  <span class="thread-time">{{ msg.time }}</span>
                  <el-button text size="small" class="copy-btn" @click="handleCopy(msg.content)" v-if="msg.content">
                    复制
                  </el-button>
                  <el-button
                    text
                    size="small"
                    class="regen-btn"
                    @click="handleRegenerate(msg)"
                    v-if="msg.id && !threadLoading && !msg.isMainReply"
                  >
                    ↻ 重新生成
                  </el-button>
                </div>
              </div>
            </div>
          </template>
        </div>

        <div v-if="threadLoading" class="thread-msg agent">
          <div class="thread-agent-row">
            <div class="thread-mini-avatar thinking-avatar">{{ agent.avatar }}</div>
            <div class="thread-bubble agent-thread-bubble">
              <div class="thread-content typing">
                <span class="typing-dots">
                  <span></span><span></span><span></span>
                </span>
                思考中...
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="thread-input-area">
        <div class="thread-input-wrapper">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="1"
            :autosize="{ minRows: 1, maxRows: 4 }"
            :placeholder="`直接和${agent.name}对话...`"
            resize="none"
            @keydown.enter.ctrl="handleSend"
            :disabled="threadLoading"
          />
          <div class="thread-input-bottom">
            <div class="thread-input-tip">Ctrl+Enter 发送 · 仅{{ agent.name }}可见</div>
            <el-button
              type="primary"
              circle
              size="small"
              @click="handleSend"
              :loading="threadLoading"
            >↑</el-button>
          </div>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { getToolIcon, formatToolCall } from '../utils/toolIcons'
import { useAgentStore } from '../stores/agent'
import api from '../api'
import { ElMessage } from 'element-plus'
import { renderMarkdown } from '../utils/markdown'

const props = defineProps({
  modelValue: Boolean,
  agentId: String
})
const emit = defineEmits(['update:modelValue'])

const store = useAgentStore()
const inputText = ref('')
const threadBodyRef = ref(null)
const threadLoading = ref(false)
const threadMessages = ref([])
const localStreamMsgs = ref([])  // 线程内本地流式消息

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const agent = computed(() => {
  if (!props.agentId) return null
  return store.getAgentById(props.agentId)
})

// 组件卸载时中止正在进行的 SSE 请求，防止内存泄漏
onBeforeUnmount(() => {
  // 不再中止 SSE——项目在后台继续运行
})

// 打开/关闭时加载消息
watch(() => props.modelValue, (val) => {
  if (val && props.agentId) {
    loadThreadMessages()
    inputText.value = ''
    localStreamMsgs.value = []
  }
})

watch(() => props.agentId, () => {
  if (visible.value && props.agentId) {
    loadThreadMessages()
    localStreamMsgs.value = []
  }
})

// 加载该智能体的所有消息
function loadThreadMessages() {
  // 显示与该子智能体直接相关的消息：
  // 1. 用户在本线程里直接发给该智能体的消息（agent_id 匹配）
  // 2. 该智能体的回复（agent_id 匹配）
  // 3. 主智能体对该子智能体汇报的回复（reply_to === agentId，标记为 isMainReply）
  // 注意：主输入框发给主智能体(agent_id='main')的普通消息不显示在这里
  const allMsgs = store.messages
  const result = []
  for (const msg of allMsgs) {
    if (msg.agent_id === props.agentId) {
      result.push({ ...msg })
    } else if (msg.agent_id === 'main' && msg.reply_to === props.agentId) {
      // 主智能体响应子智能体汇报的消息，标记一下用不同样式显示
      result.push({ ...msg, isMainReply: true })
    }
  }
  threadMessages.value = result.concat(localStreamMsgs.value)
  nextTick(scrollToBottom)
}

// 监听主消息变化，实时更新线程
// 只监听 messages.length 变化即可，避免 deep watch 整个 messages 数组的性能问题
watch(() => store.messages.length, loadThreadMessages)
// 监听流式状态变化，流式结束时重新加载
watch(() => store.isStreaming, (streaming) => {
  if (!streaming && visible.value) loadThreadMessages()
})

function scrollToBottom() {
  nextTick(() => {
    if (threadBodyRef.value) {
      threadBodyRef.value.scrollTop = threadBodyRef.value.scrollHeight
    }
  })
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || threadLoading.value || !props.agentId) return
  
  inputText.value = ''
  threadLoading.value = true
  
  const now = new Date().toLocaleTimeString('zh-CN')
  
  // 添加用户消息到本地
  const userMsg = {
    agent_id: props.agentId,
    role: 'user',
    content: text,
    time: now
  }
  localStreamMsgs.value.push(userMsg)
  loadThreadMessages()
  scrollToBottom()
  
  try {
    // 调用流式接口，只调用该智能体（主智能体也可以单独聊）
    const response = await api.chatStream(props.agentId, text, store.currentConversationId, true)
    
    if (!response.ok) {
      throw new Error('请求失败: ' + response.status)
    }
    
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let currentEvent = ''
    let currentData = ''
    let currentMsgContent = ''
    let currentToolEvents = []
    let agentMsgId = null
    
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
            handleThreadSSE(currentEvent, currentData)
          }
          currentEvent = ''
          currentData = ''
        }
      }
    }
    
    if (currentEvent && currentData) {
      handleThreadSSE(currentEvent, currentData)
    }
    
    // 刷新主消息列表
    await store.loadMessages()
    localStreamMsgs.value = []
    loadThreadMessages()
  } catch (e) {
    ElMessage.error('发送失败：' + (e.message || '网络错误'))
    localStreamMsgs.value.push({
      agent_id: props.agentId,
      role: 'agent',
      content: '❌ 出错了：' + (e.message || '网络错误'),
      time: new Date().toLocaleTimeString('zh-CN')
    })
    loadThreadMessages()
  } finally {
    threadLoading.value = false
  }
}

function handleThreadSSE(event, dataStr) {
  try {
    const data = JSON.parse(dataStr)
    const now = new Date().toLocaleTimeString('zh-CN')
    const eventAgentId = data.agent_id

    // 主智能体响应事件（子智能体 @主智能体 触发的回调）
    // 在抽屉里显示一个「主智能体响应」区块
    if (eventAgentId === 'main') {
      switch (event) {
        case 'agent_start': {
          currentMsgContent = ''
          currentToolEvents = []
          const mainMsg = {
            agent_id: 'main',
            role: 'agent',
            content: '',
            time: now,
            streaming: true,
            toolEvents: [],
            isMainReply: true  // 标记为主智能体响应，用不同样式
          }
          localStreamMsgs.value.push(mainMsg)
          agentMsgId = localStreamMsgs.value.length - 1
          loadThreadMessages()
          scrollToBottom()
          break
        }
        case 'token': {
          if (agentMsgId !== null) {
            currentMsgContent += data.content
            localStreamMsgs.value[agentMsgId].content = currentMsgContent
            loadThreadMessages()
            scrollToBottom()
          }
          break
        }
        case 'tool_start': {
          if (agentMsgId !== null) {
            currentToolEvents.push({
              tool_name: data.tool_name,
              tool_args: data.tool_args,
              status: 'running'
            })
            localStreamMsgs.value[agentMsgId].toolEvents = [...currentToolEvents]
            loadThreadMessages()
          }
          break
        }
        case 'tool_end': {
          if (agentMsgId !== null) {
            for (let i = currentToolEvents.length - 1; i >= 0; i--) {
              if (currentToolEvents[i].tool_name === data.tool_name && currentToolEvents[i].status === 'running') {
                currentToolEvents[i].status = 'done'
                currentToolEvents[i].result = data.result
                break
              }
            }
            localStreamMsgs.value[agentMsgId].toolEvents = [...currentToolEvents]
            loadThreadMessages()
          }
          break
        }
        case 'agent_end': {
          if (agentMsgId !== null) {
            localStreamMsgs.value[agentMsgId].content = data.full_content
            localStreamMsgs.value[agentMsgId].streaming = false
            agentMsgId = null
            loadThreadMessages()
            scrollToBottom()
          }
          break
        }
        case 'done': {
          break
        }
      }
      return
    }

    // 原有逻辑：处理当前子智能体的事件
    switch (event) {
      case 'agent_start': {
        if (eventAgentId === props.agentId) {
          currentMsgContent = ''
          currentToolEvents = []
          const agentMsg = {
            agent_id: props.agentId,
            role: 'agent',
            content: '',
            time: now,
            streaming: true,
            toolEvents: []
          }
          localStreamMsgs.value.push(agentMsg)
          agentMsgId = localStreamMsgs.value.length - 1
        }
        break
      }
      case 'token': {
        if (eventAgentId === props.agentId && agentMsgId !== null) {
          currentMsgContent += data.content
          localStreamMsgs.value[agentMsgId].content = currentMsgContent
          loadThreadMessages()
          scrollToBottom()
        }
        break
      }
      case 'tool_start': {
        if (eventAgentId === props.agentId && agentMsgId !== null) {
          const te = {
            tool_name: data.tool_name,
            tool_args: data.tool_args,
            status: 'running'
          }
          currentToolEvents.push(te)
          localStreamMsgs.value[agentMsgId].toolEvents = [...currentToolEvents]
          loadThreadMessages()
        }
        break
      }
      case 'tool_end': {
        if (eventAgentId === props.agentId && agentMsgId !== null) {
          for (let i = currentToolEvents.length - 1; i >= 0; i--) {
            if (currentToolEvents[i].tool_name === data.tool_name && currentToolEvents[i].status === 'running') {
              currentToolEvents[i].status = 'done'
              currentToolEvents[i].result = data.result
              break
            }
          }
          localStreamMsgs.value[agentMsgId].toolEvents = [...currentToolEvents]
          loadThreadMessages()
        }
        break
      }
      case 'agent_end': {
        if (eventAgentId === props.agentId && agentMsgId !== null) {
          localStreamMsgs.value[agentMsgId].content = data.full_content
          localStreamMsgs.value[agentMsgId].streaming = false
          agentMsgId = null
          loadThreadMessages()
          scrollToBottom()
        }
        break
      }
      case 'done': {
        // 完成
        break
      }
    }
  } catch (e) {
    console.error('Thread SSE parse error:', e)
  }
}

async function handleCopy(content) {
  try {
    await navigator.clipboard.writeText(content)
    ElMessage.success('已复制')
  } catch (e) {
    // fallback for older browsers
    const textarea = document.createElement('textarea')
    textarea.value = content
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    ElMessage.success('已复制')
  }
}

// 重新生成子线程中某条智能体回复
async function handleRegenerate(msg) {
  if (!msg.id || threadLoading.value) return
  
  // 在线程消息里找到这条智能体回复前面的最近用户消息
  // 注意：direct模式下的消息，agent_id都是当前线程的智能体id
  const allMsgs = store.messages.filter(m => m.agent_id === props.agentId)
  const msgIdx = allMsgs.findIndex(m => m.id === msg.id)
  if (msgIdx === -1) return
  
  // 向前找用户消息
  let userMsgId = null
  for (let i = msgIdx - 1; i >= 0; i--) {
    if (allMsgs[i].role === 'user') {
      userMsgId = allMsgs[i].id
      break
    }
  }
  if (!userMsgId) {
    ElMessage.warning('找不到对应的用户消息')
    return
  }
  
  threadLoading.value = true
  localStreamMsgs.value = []
  
  try {
    // 使用 direct=true 模式，只重新生成当前智能体的回复，不触发链式调度
    const response = await api.regenerateStream(
      store.currentConversationId, 
      userMsgId, 
      null, 
      true,  // direct
      props.agentId  // target_agent_id
    )
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
            handleThreadSSE(currentEvent, currentData)
          }
          currentEvent = ''
          currentData = ''
        }
      }
    }
    
    if (currentEvent && currentData) {
      handleThreadSSE(currentEvent, currentData)
    }
    
    await store.loadMessages()
    loadThreadMessages()
  } catch (e) {
    ElMessage.error('重新生成失败：' + (e.message || '网络错误'))
  } finally {
    threadLoading.value = false
  }
}

function handleClose() {
  visible.value = false
  localStreamMsgs.value = []
}

// getToolIcon / formatToolCall 已抽取到 utils/toolIcons.js（通过 import 导入）
</script>

<style scoped>
/* 抽屉整体 */
.thread-drawer :deep(.el-drawer) {
  border-radius: 20px 0 0 20px;
  overflow: hidden;
  box-shadow: -8px 0 30px rgba(0, 0, 0, 0.12);
}

.thread-drawer :deep(.el-drawer__body) {
  padding: 0;
  background: #f8fafc;
}

.thread-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f8fafc;
}

/* 头部 - 渐变背景 */
.thread-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-bottom: none;
  position: relative;
}

.thread-header::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: rgba(255, 255, 255, 0.15);
}

.thread-agent-info {
  display: flex;
  align-items: center;
  gap: 14px;
}

.thread-avatar {
  font-size: 36px;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  backdrop-filter: blur(10px);
}

.thread-agent-name {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  letter-spacing: 0.3px;
}

.thread-agent-role {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.75);
  margin-top: 3px;
  letter-spacing: 0.2px;
}

.close-btn {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.85);
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.15);
  transition: all 0.25s ease;
}

.close-btn:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.28);
  transform: translateY(-1px);
}

/* 消息区 */
.thread-body {
  flex: 1;
  overflow-y: auto;
  padding: 18px 16px;
  background: #f8fafc;
}

.thread-body::-webkit-scrollbar {
  width: 6px;
}

.thread-body::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

.thread-body::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

.thread-body::-webkit-scrollbar-track {
  background: transparent;
}

/* 空状态 */
.thread-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.empty-avatar {
  font-size: 52px;
  margin-bottom: 18px;
  opacity: 0.85;
  width: 72px;
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #eef2ff 0%, #f3e8ff 100%);
  border-radius: 20px;
  border: 1px solid #e0e7ff;
}

.empty-text {
  font-size: 15px;
  color: #0f172a;
  margin-bottom: 8px;
  font-weight: 500;
}

.empty-tip {
  font-size: 13px;
  color: #94a3b8;
  max-width: 260px;
  line-height: 1.6;
}

/* 消息行 */
.thread-msg {
  margin-bottom: 18px;
  display: flex;
}

.thread-msg.user {
  justify-content: flex-end;
}

.thread-msg.agent {
  justify-content: flex-start;
}

/* 气泡 */
.thread-bubble {
  max-width: 82%;
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.65;
  transition: all 0.25s ease;
}

.user-thread-bubble {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  border-bottom-right-radius: 4px;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.agent-thread-bubble {
  background: #fff;
  color: #0f172a;
  border: 1px solid #e2e8f0;
  border-bottom-left-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.agent-thread-bubble:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  transform: translateY(-1px);
}

/* 智能体行布局 */
.thread-agent-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.thread-mini-avatar {
  font-size: 20px;
  flex-shrink: 0;
  margin-top: 2px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: linear-gradient(135deg, #eef2ff 0%, #f3e8ff 100%);
  border: 1px solid #e0e7ff;
}

.thinking-avatar {
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

/* 主智能体响应子智能体汇报的特殊样式 */
.main-reply-row {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #d1d5db;
}

.thread-mini-avatar.main-avatar {
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  border: 1px solid #f59e0b;
}

.agent-thread-bubble.main-reply-bubble {
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
  border: 1px solid #f59e0b;
}

.main-reply-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #b45309;
  font-weight: 600;
  background: rgba(245, 158, 11, 0.15);
  padding: 2px 8px;
  border-radius: 6px;
  margin-bottom: 6px;
}

.main-reply-icon {
  font-weight: bold;
}

/* 消息内容 */
.thread-content {
  word-break: break-word;
  color: inherit;
}

.thread-time {
  font-size: 11px;
  opacity: 0.6;
  margin-top: 6px;
  text-align: right;
}

.user-thread-bubble .thread-time {
  color: rgba(255, 255, 255, 0.7);
  opacity: 1;
}

/* 消息操作按钮 */
.thread-msg-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
}

.copy-btn,
.regen-btn {
  font-size: 11px;
  color: #94a3b8;
  padding: 2px 6px;
  opacity: 0;
  transition: all 0.25s ease;
  border-radius: 6px;
}

.agent-thread-bubble:hover .copy-btn,
.agent-thread-bubble:hover .regen-btn {
  opacity: 1;
}

.copy-btn:hover {
  color: #6366f1;
  background: #eef2ff;
}

.regen-btn:hover {
  color: #6366f1;
  background: #eef2ff;
}

/* 工具事件（紧凑版） */
.tool-events.mini {
  margin-bottom: 8px;
  gap: 4px;
  display: flex;
  flex-direction: column;
}

.tool-events.mini .tool-event {
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 6px;
  color: #64748b;
  background: #f8fafc;
  border-left: 2px solid #e2e8f0;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.25s ease;
}

.tool-events.mini .tool-event.running {
  color: #6366f1;
  border-left-color: #6366f1;
  background: #eef2ff;
}

.tool-events.mini .tool-event.done {
  color: #059669;
  border-left-color: #10b981;
  background: #ecfdf5;
}

.tool-events.mini .tool-icon {
  font-size: 12px;
}

.tool-events.mini .tool-text {
  flex: 1;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 11px;
}

.tool-events.mini .tool-spinner {
  width: 10px;
  height: 10px;
  border: 2px solid #6366f1;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.tool-events.mini .tool-check {
  color: #10b981;
  font-weight: bold;
  font-size: 11px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Markdown */
.markdown-body {
  font-size: 14px;
  line-height: 1.7;
  color: #0f172a;
  word-wrap: break-word;
}

.markdown-body :deep(p) {
  margin: 0 0 0.7em 0;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin: 0.8em 0 0.5em 0;
  font-weight: 600;
  line-height: 1.4;
  color: #0f172a;
}

.markdown-body :deep(h1) { font-size: 1.3em; }
.markdown-body :deep(h2) { font-size: 1.2em; }
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
  margin: 0.7em 0;
  padding: 0.7em 1em;
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
  margin: 0.7em 0;
  border-radius: 10px;
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
  padding: 0.9em !important;
  background: #1e293b !important;
  border-radius: 10px;
}

.markdown-body :deep(table) {
  border-collapse: collapse;
  margin: 0.7em 0;
  width: 100%;
  font-size: 0.9em;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #e2e8f0;
  padding: 0.5em 0.8em;
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
  margin: 1em 0;
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

/* 正在输入 */
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

.typing-dots span:nth-child(1) { animation-delay: -0.32s; }
.typing-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes typingBounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* 输入区 */
.thread-input-area {
  padding: 12px 16px 16px;
  background: #fff;
  border-top: 1px solid #f1f5f9;
}

.thread-input-wrapper {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 10px 10px 8px 14px;
  transition: all 0.25s ease;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.thread-input-wrapper:focus-within {
  border-color: #6366f1;
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.2);
  transform: translateY(-1px);
}

.thread-input-wrapper :deep(.el-textarea__inner) {
  background: transparent;
  border: none;
  box-shadow: none;
  padding: 6px 0;
  font-size: 14px;
  color: #0f172a;
  resize: none;
  line-height: 1.6;
}

.thread-input-wrapper :deep(.el-textarea__inner::placeholder) {
  color: #94a3b8;
}

.thread-input-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
  padding-top: 6px;
}

.thread-input-tip {
  font-size: 11px;
  color: #94a3b8;
  letter-spacing: 0.2px;
}

/* 发送按钮 */
.thread-input-bottom :deep(.el-button--primary) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  width: 32px;
  height: 32px;
  font-size: 16px;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
  transition: all 0.25s ease;
}

.thread-input-bottom :deep(.el-button--primary:hover) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
}

.thread-input-bottom :deep(.el-button--primary:active) {
  transform: translateY(0);
}

.thread-input-bottom :deep(.el-button--primary.is-disabled) {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.2);
}
</style>
