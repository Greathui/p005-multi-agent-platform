<template>
  <div class="todo-panel">
    <!-- 头部：标题 + 刷新按钮 -->
    <div class="todo-header">
      <span class="todo-title">TODO 清单</span>
      <el-button
        text
        size="small"
        :loading="loading"
        @click="loadTodos"
        title="刷新"
      >
        <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" v-if="!loading">
          <path d="M8 3a5 5 0 1 0 4.546 2.914.5.5 0 0 1 .908-.417A6 6 0 1 1 8 2v1z"/>
          <path d="M8 4.466V.534a.25.25 0 0 1 .41-.192l2.36 1.966c.12.1.12.284 0 .384L8.41 4.658A.25.25 0 0 1 8 4.466z"/>
        </svg>
      </el-button>
    </div>

    <!-- 加载中 -->
    <div v-if="loading && todos.length === 0" class="todo-loading">
      <el-skeleton :rows="4" animated />
    </div>

    <!-- 空状态 -->
    <div v-else-if="todos.length === 0" class="todo-empty">
      <div class="todo-empty-icon">📝</div>
      <p class="todo-empty-text">暂无TODO清单</p>
    </div>

    <!-- TODO 列表 -->
    <div v-else class="todo-list">
      <div
        v-for="todo in todos"
        :key="todo.todo_id"
        class="todo-card"
      >
        <!-- 卡片头部（可点击折叠） -->
        <div class="todo-card-header" @click="toggleCollapse(todo.todo_id)">
          <span class="todo-collapse-arrow" :class="{ collapsed: isCollapsed(todo.todo_id) }">
            <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
              <path d="M3.22 5.78a.75.75 0 0 1 0-1.06l4.25-4.25a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1-1.06 1.06L8 2.56 4.28 5.78a.75.75 0 0 1-1.06 0z" transform="rotate(180 8 4)"/>
            </svg>
          </span>
          <span class="todo-card-title">{{ todo.title }}</span>
          <span class="todo-item-count">{{ todo.items?.length || 0 }}项</span>
        </div>

        <!-- 卡片内容（可折叠） -->
        <div v-show="!isCollapsed(todo.todo_id)" class="todo-card-body">
          <div
            v-for="item in todo.items"
            :key="item.index"
            class="todo-item"
            :class="'status-' + item.status"
          >
            <span class="todo-item-dot" :style="{ background: statusColor(item.status) }"></span>
            <span class="todo-item-text" :style="{ color: statusColor(item.status) }">
              {{ item.content }}
            </span>
            <span class="todo-item-status">{{ statusLabel(item.status) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import api from '../api'

const props = defineProps({
  convId: {
    type: String,
    required: true
  },
  // 刷新触发器：外部变化时自动重新加载
  refreshTrigger: {
    type: Number,
    default: 0
  }
})

const loading = ref(false)
const todos = ref([])
const collapsedIds = ref(new Set())

// 状态颜色映射
const STATUS_COLORS = {
  pending: '#9ca3af',
  in_progress: '#3b82f6',
  completed: '#10b981'
}

// 状态标签映射
const STATUS_LABELS = {
  pending: '待办',
  in_progress: '进行中',
  completed: '已完成'
}

function statusColor(status) {
  return STATUS_COLORS[status] || STATUS_COLORS.pending
}

function statusLabel(status) {
  return STATUS_LABELS[status] || status
}

// 是否折叠
function isCollapsed(todoId) {
  return collapsedIds.value.has(todoId)
}

// 切换折叠/展开
function toggleCollapse(todoId) {
  if (collapsedIds.value.has(todoId)) {
    collapsedIds.value.delete(todoId)
  } else {
    collapsedIds.value.add(todoId)
  }
  collapsedIds.value = new Set(collapsedIds.value)
}

// 加载 TODO 列表
async function loadTodos() {
  if (!props.convId) {
    todos.value = []
    return
  }
  loading.value = true
  try {
    const res = await api.getConversationTodos(props.convId)
    todos.value = res.data.todos || []
  } catch (e) {
    console.error('加载TODO失败:', e)
    todos.value = []
  } finally {
    loading.value = false
  }
}

// 监听 convId 变化
watch(() => props.convId, (newId) => {
  if (newId) {
    loadTodos()
  } else {
    todos.value = []
  }
}, { immediate: false })

// 监听刷新触发器变化
watch(() => props.refreshTrigger, () => {
  if (props.convId) {
    loadTodos()
  }
})

// 组件挂载时加载
onMounted(() => {
  if (props.convId) {
    loadTodos()
  }
})
</script>

<style scoped>
.todo-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 200px;
  background: #fff;
}

/* 头部 */
.todo-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.todo-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

/* 加载中 */
.todo-loading {
  padding: 12px;
}

/* 空状态 */
.todo-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 16px;
  color: #94a3b8;
}

.todo-empty-icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.todo-empty-text {
  font-size: 13px;
  margin: 0;
}

/* TODO 列表 */
.todo-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

/* 卡片 */
.todo-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 8px;
  overflow: hidden;
}

.todo-card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s;
}

.todo-card-header:hover {
  background: #f8fafc;
}

.todo-collapse-arrow {
  display: flex;
  align-items: center;
  transition: transform 0.2s;
  color: #94a3b8;
}

.todo-collapse-arrow.collapsed {
  transform: rotate(-90deg);
}

.todo-card-title {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.todo-item-count {
  font-size: 11px;
  color: #94a3b8;
  background: #f1f5f9;
  border-radius: 8px;
  padding: 1px 6px;
  flex-shrink: 0;
}

/* 卡片内容 */
.todo-card-body {
  padding: 4px 10px 8px;
}

/* 单个 TODO 项 */
.todo-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  font-size: 12px;
}

.todo-item-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.todo-item-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.todo-item-status {
  font-size: 10px;
  color: #94a3b8;
  flex-shrink: 0;
}

/* 滚动条美化 */
.todo-list::-webkit-scrollbar {
  width: 4px;
}

.todo-list::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 2px;
}

.todo-list::-webkit-scrollbar-track {
  background: transparent;
}
</style>
