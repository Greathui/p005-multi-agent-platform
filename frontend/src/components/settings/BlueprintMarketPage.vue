<template>
  <div class="blueprint-market-page">
    <!-- 顶部操作栏 -->
    <div class="page-toolbar">
      <div class="search-box">
        <el-input
          v-model="searchText"
          placeholder="搜索团队蓝图"
          size="default"
          prefix-icon="Search"
          clearable
        />
      </div>
      <div class="category-tabs">
        <div
          v-for="cat in categories"
          :key="cat.key"
          class="category-tab"
          :class="{ active: activeCategory === cat.key }"
          @click="activeCategory = cat.key"
        >
          {{ cat.label }}
        </div>
      </div>
    </div>

    <!-- 蓝图卡片网格 -->
    <div class="blueprint-grid" v-if="filteredBlueprints.length > 0">
      <div
        v-for="bp in filteredBlueprints"
        :key="bp.id"
        class="blueprint-card"
      >
        <div class="card-header" :style="{ background: bp.coverBg }">
          <div class="card-cover">
            <span class="cover-icon">{{ bp.icon }}</span>
          </div>
          <div class="card-badge">{{ bp.teamSize }}人团队</div>
        </div>
        <div class="card-body">
          <div class="bp-name">{{ bp.name }}</div>
          <div class="bp-desc">{{ bp.description }}</div>
          <div class="bp-members">
            <div class="member-chips">
              <span v-for="m in bp.members.slice(0, 4)" :key="m" class="member-chip">{{ m }}</span>
              <span v-if="bp.members.length > 4" class="member-more">+{{ bp.members.length - 4 }}</span>
            </div>
          </div>
          <div class="bp-stats">
            <span class="stat">⭐ {{ bp.stars }}</span>
            <span class="stat">📥 {{ bp.downloads }}</span>
            <span class="stat">v{{ bp.version }}</span>
          </div>
        </div>
        <div class="card-footer">
          <el-button size="small" @click="handlePreview(bp)">预览</el-button>
          <el-button type="primary" size="small" plain @click="handleInstall(bp)">获取</el-button>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <div class="empty-icon">🏪</div>
      <div class="empty-title">蓝图市场即将上线</div>
      <div class="empty-desc">
        这里将提供社区共享的团队蓝图模板，覆盖小说创作、代码开发、市场调研、内容运营等场景。<br>
        一键获取蓝图后，可在「本地蓝图」中应用，快速创建专业团队。
      </div>
      <div class="empty-tags">
        <span class="empty-tag">📖 小说创作团队</span>
        <span class="empty-tag">💻 代码开发团队</span>
        <span class="empty-tag">📊 市场调研团队</span>
        <span class="empty-tag">📝 内容运营团队</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'

const searchText = ref('')
const activeCategory = ref('all')

const categories = ref([
  { key: 'all', label: '全部' },
  { key: 'novel', label: '小说创作' },
  { key: 'dev', label: '代码开发' },
  { key: 'research', label: '调研分析' },
  { key: 'content', label: '内容运营' },
  { key: 'business', label: '商业服务' },
])

// 预设蓝图示例（市场上线后替换为真实数据）
const blueprints = ref([
  {
    id: 'bp-novel-scifi',
    name: '科幻长篇小说创作团队',
    description: '专攻50章+长篇科幻小说，含世界观、大纲、正文、审阅全流程',
    icon: '🚀',
    coverBg: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    members: ['世界观设计师', '大纲规划师', '正文作者', '审阅编辑'],
    teamSize: 5,
    stars: 89,
    downloads: 156,
    version: '1.2.0',
    category: 'novel',
  },
  {
    id: 'bp-dev-fullstack',
    name: '全栈应用开发团队',
    description: '前后端分离开发，含需求分析、架构设计、编码、测试、文档',
    icon: '💻',
    coverBg: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
    members: ['产品经理', '架构师', '前端工程师', '后端工程师', '测试工程师'],
    teamSize: 6,
    stars: 142,
    downloads: 268,
    version: '2.0.1',
    category: 'dev',
  },
  {
    id: 'bp-research-market',
    name: '市场调研分析团队',
    description: '行业调研、竞品分析、用户访谈、数据汇总、报告撰写',
    icon: '📊',
    coverBg: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
    members: ['调研员', '数据分析师', '报告撰写员'],
    teamSize: 4,
    stars: 67,
    downloads: 98,
    version: '1.0.3',
    category: 'research',
  },
])

const filteredBlueprints = computed(() => {
  let list = blueprints.value
  if (activeCategory.value !== 'all') {
    list = list.filter(b => b.category === activeCategory.value)
  }
  if (searchText.value) {
    const kw = searchText.value.toLowerCase()
    list = list.filter(b =>
      b.name.toLowerCase().includes(kw) ||
      b.description.toLowerCase().includes(kw)
    )
  }
  return list
})

function handlePreview(bp) {
  ElMessage.info(`「${bp.name}」预览功能即将上线`)
}

function handleInstall(bp) {
  ElMessage.success(`「${bp.name}」已获取，可在「本地蓝图」中查看和应用`)
}
</script>

<style scoped>
.blueprint-market-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.page-toolbar {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.search-box :deep(.el-input__wrapper) {
  border-radius: 10px;
  box-shadow: 0 0 0 1px #e2e8f0 inset;
}
.search-box :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #818cf8 inset;
}
.search-box :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #6366f1 inset, 0 0 0 4px rgba(99, 102, 241, 0.1);
}

.category-tabs {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.category-tab {
  padding: 5px 14px;
  border-radius: 9999px;
  font-size: 12px;
  color: #64748b;
  background: #f1f5f9;
  cursor: pointer;
  transition: all 0.2s ease;
}

.category-tab:hover {
  background: #e2e8f0;
  color: #0f172a;
}

.category-tab.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  font-weight: 600;
}

.blueprint-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
}

.blueprint-card {
  border-radius: 12px;
  background: #fff;
  border: 1px solid #f1f5f9;
  overflow: hidden;
  transition: all 0.25s ease;
  display: flex;
  flex-direction: column;
}

.blueprint-card:hover {
  border-color: #c7d2fe;
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.15);
  transform: translateY(-3px);
}

.card-header {
  height: 90px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.card-cover {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.cover-icon {
  font-size: 28px;
}

.card-badge {
  position: absolute;
  top: 10px;
  right: 10px;
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 9999px;
  background: rgba(255, 255, 255, 0.9);
  color: #0f172a;
  font-weight: 600;
}

.card-body {
  padding: 14px 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bp-name {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.bp-desc {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
  min-height: 36px;
}

.bp-members {
  margin-top: 2px;
}

.member-chips {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.member-chip {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 4px;
  background: #f1f5f9;
  color: #475569;
}

.member-more {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 4px;
  background: #e0e7ff;
  color: #4f46e5;
  font-weight: 600;
}

.bp-stats {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #94a3b8;
  padding-top: 8px;
  border-top: 1px dashed #f1f5f9;
}

.card-footer {
  padding: 10px 16px 14px;
  display: flex;
  gap: 8px;
  border-top: 1px solid #f1f5f9;
}

.card-footer .el-button {
  flex: 1;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  color: #94a3b8;
  gap: 14px;
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
  max-width: 480px;
}

.empty-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
  margin-top: 8px;
}

.empty-tag {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 9999px;
  background: #f1f5f9;
  color: #64748b;
}
</style>
