<template>
  <el-dialog
    v-model="visible"
    :show-close="false"
    width="960px"
    top="5vh"
    :close-on-click-modal="false"
    class="settings-panel-dialog"
    append-to-body
  >
    <div class="settings-panel">
      <!-- 左侧导航 -->
      <aside class="settings-nav">
        <div class="nav-header">
          <span class="nav-title">⚙ 设置</span>
        </div>

        <div class="nav-group">
          <div class="nav-group-label">模型与能力</div>
          <div
            v-for="item in navItems"
            :key="item.key"
            class="nav-item"
            :class="{ active: activeKey === item.key }"
            @click="activeKey = item.key"
          >
            <span class="nav-icon">{{ item.icon }}</span>
            <span class="nav-label">{{ item.label }}</span>
            <span v-if="item.badge" class="nav-badge">{{ item.badge }}</span>
          </div>
        </div>

        <div class="nav-footer">
          <div class="version-info">P005 多智能体协作系统 v1.0</div>
        </div>
      </aside>

      <!-- 右侧内容区 -->
      <section class="settings-content">
        <header class="content-header">
          <h2 class="content-title">
            <span class="title-icon">{{ currentNav?.icon }}</span>
            {{ currentNav?.label }}
          </h2>
          <p class="content-desc">{{ currentNav?.desc }}</p>
          <el-button text class="close-btn" @click="visible = false">× 关闭</el-button>
        </header>

        <div class="content-body">
          <!-- 模型配置 -->
          <ModelConfigPage v-if="activeKey === 'model'" />

          <!-- 技能市场 -->
          <SkillMarketPage
            v-else-if="activeKey === 'skill_market'"
            @navigate="handleNavigate"
          />

          <!-- 本地技能 -->
          <LocalSkillsPage
            v-else-if="activeKey === 'local_skills'"
            @navigate="handleNavigate"
          />

          <!-- 蓝图市场 -->
          <BlueprintMarketPage
            v-else-if="activeKey === 'blueprint_market'"
            @navigate="handleNavigate"
          />

          <!-- 本地蓝图 -->
          <LocalBlueprintsPage
            v-else-if="activeKey === 'local_blueprints'"
            @navigate="handleNavigate"
            @close-settings="visible = false"
          />

          <!-- 关于与捐赠 -->
          <AboutPage v-else-if="activeKey === 'about'" />
        </div>
      </section>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import ModelConfigPage from './settings/ModelConfigPage.vue'
import SkillMarketPage from './settings/SkillMarketPage.vue'
import LocalSkillsPage from './settings/LocalSkillsPage.vue'
import BlueprintMarketPage from './settings/BlueprintMarketPage.vue'
import LocalBlueprintsPage from './settings/LocalBlueprintsPage.vue'
import AboutPage from './settings/AboutPage.vue'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue'])

const visible = ref(props.modelValue)
const activeKey = ref('model')

const navItems = ref([
  { key: 'model', label: '模型配置', icon: '🤖', desc: '管理大语言模型的 API 配置，支持多服务商和独立模型设置' },
  { key: 'skill_market', label: '技能市场', icon: '🛒', desc: '浏览和获取社区共享的智能体技能' },
  { key: 'local_skills', label: '本地技能', icon: '📦', desc: '管理已安装的技能，为智能体启用或关闭技能' },
  { key: 'blueprint_market', label: '蓝图市场', icon: '🏪', desc: '浏览和获取社区共享的团队蓝图' },
  { key: 'local_blueprints', label: '本地蓝图', icon: '📋', desc: '管理已保存的团队蓝图，一键创建项目团队' },
  { key: 'about', label: '关于与支持', icon: '💖', desc: '了解软件功能，支持开发者持续迭代' },
])

const currentNav = computed(() => navItems.value.find(n => n.key === activeKey.value))

function handleNavigate(key) {
  if (key) activeKey.value = key
}

watch(() => props.modelValue, v => visible.value = v)
watch(visible, v => emit('update:modelValue', v))
</script>

<style scoped>
.settings-panel {
  display: flex;
  height: 82vh;
  min-height: 540px;
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
}

/* 左侧导航 */
.settings-nav {
  width: 220px;
  flex-shrink: 0;
  background: #f8fafc;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  padding: 0;
}

.nav-header {
  padding: 20px 18px 16px;
  border-bottom: 1px solid #e2e8f0;
  background: #fff;
}

.nav-title {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: 0.3px;
}

.nav-group {
  flex: 1;
  padding: 12px 10px;
  overflow-y: auto;
}

.nav-group-label {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  padding: 8px 10px 6px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  color: #475569;
  font-size: 14px;
  margin-bottom: 2px;
  position: relative;
}

.nav-item:hover {
  background: #e2e8f0;
  color: #0f172a;
}

.nav-item.active {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.12) 0%, rgba(118, 75, 162, 0.12) 100%);
  color: #4f46e5;
  font-weight: 600;
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 18px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 0 2px 2px 0;
}

.nav-icon {
  font-size: 16px;
  flex-shrink: 0;
  width: 20px;
  text-align: center;
}

.nav-label {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nav-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 9999px;
  background: #6366f1;
  color: #fff;
  font-weight: 600;
}

.nav-footer {
  padding: 12px 18px;
  border-top: 1px solid #e2e8f0;
  background: #fff;
}

.version-info {
  font-size: 11px;
  color: #94a3b8;
  text-align: center;
}

/* 右侧内容区 */
.settings-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.content-header {
  padding: 20px 28px 16px;
  border-bottom: 1px solid #f1f5f9;
  position: relative;
}

.content-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
  display: flex;
  align-items: center;
  gap: 10px;
}

.title-icon {
  font-size: 20px;
}

.content-desc {
  margin: 6px 0 0;
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
}

.close-btn {
  position: absolute;
  top: 18px;
  right: 20px;
  font-size: 13px;
  color: #94a3b8;
  padding: 4px 10px;
}

.close-btn:hover {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.08);
}

.content-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 28px 28px;
}

/* 隐藏 dialog 默认 header */
:deep(.el-dialog__header) {
  display: none;
}

:deep(.el-dialog__body) {
  padding: 0;
}

:deep(.el-dialog) {
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}
</style>
