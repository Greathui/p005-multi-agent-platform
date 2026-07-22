<template>
  <div class="app-container">
    <!-- 左栏：侧边栏（项目列表 / 团队设计） -->
    <Sidebar ref="sidebarRef" />
    <!-- 右栏：主区域 -->
    <template v-if="store.isMetaTeamView && store.metaTeamTaskId">
      <MetaTeamTask />
    </template>
    <template v-else-if="store.isMetaTeamView">
      <MetaTeamHome ref="metaTeamHomeRef" @new-task="handleNewTask" />
    </template>
    <template v-else-if="store.isTeamHomeView">
      <TeamHome @create-project="handleCreateProjectInTeam" />
    </template>
    <template v-else>
      <ChatWindow @open-api-config="handleOpenApiConfig" />
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAgentStore } from './stores/agent'
import Sidebar from './components/Sidebar.vue'
import ChatWindow from './components/ChatWindow.vue'
import MetaTeamTask from './components/MetaTeamTask.vue'
import MetaTeamHome from './components/MetaTeamHome.vue'
import TeamHome from './components/TeamHome.vue'

const store = useAgentStore()
const sidebarRef = ref(null)
const metaTeamHomeRef = ref(null)

// 在团队主页点击"新建项目"时，调用 Sidebar 的方法打开新建项目弹窗
function handleCreateProjectInTeam(teamId) {
  if (sidebarRef.value) {
    sidebarRef.value.openNewProjectInTeamById(teamId)
  }
}

onMounted(() => {
  store.loadAgents()
  store.loadConversations()
  store.loadTeams()
})

function handleOpenApiConfig() {
  if (sidebarRef.value) {
    sidebarRef.value.openSettings()
  }
}

// 首页点击"新建设计任务"，调用 Sidebar 的方法打开弹窗
function handleNewTask() {
  if (sidebarRef.value) {
    sidebarRef.value.openNewMetaTaskDialog()
  }
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  /* 主色调 - 蓝紫渐变 */
  --primary: #6366f1;
  --primary-light: #818cf8;
  --primary-dark: #4f46e5;
  --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  --primary-gradient-soft: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
  
  /* 背景色 */
  --bg-app: #f8fafc;
  --bg-sidebar: #ffffff;
  --bg-chat: #f8fafc;
  --bg-card: #ffffff;
  --bg-hover: #f1f5f9;
  --bg-active: #eef2ff;
  
  /* 文字色 */
  --text-primary: #0f172a;
  --text-secondary: #475569;
  --text-tertiary: #94a3b8;
  --text-muted: #cbd5e1;
  
  /* 边框 */
  --border-color: #e2e8f0;
  --border-light: #f1f5f9;
  
  /* 阴影 */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.06);
  --shadow-lg: 0 10px 40px rgba(0, 0, 0, 0.08);
  --shadow-xl: 0 20px 60px rgba(0, 0, 0, 0.12);
  --shadow-glow: 0 0 20px rgba(99, 102, 241, 0.3);
  
  /* 圆角 */
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-xl: 20px;
  --radius-full: 9999px;
  
  /* 间距 */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 12px;
  --space-lg: 16px;
  --space-xl: 24px;
  --space-2xl: 32px;
  
  /* 过渡 */
  --transition-fast: 0.15s ease;
  --transition-normal: 0.25s ease;
  --transition-slow: 0.4s ease;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', sans-serif;
  background: var(--bg-app);
  color: var(--text-primary);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* 滚动条美化 */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
  transition: background var(--transition-fast);
}
::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

/* 选中文字颜色 */
::selection {
  background: rgba(99, 102, 241, 0.2);
  color: var(--text-primary);
}

.app-container {
  display: flex;
  height: 100vh;
  background: var(--bg-app);
}

/* 左栏 */
.app-container > :first-child {
  width: 280px;
  flex-shrink: 0;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-color);
}

/* 右栏 */
.app-container > :nth-child(2) {
  flex: 1;
  min-width: 0;
}
</style>
