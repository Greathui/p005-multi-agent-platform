<template>
  <div class="skill-market-page">
    <!-- 顶部操作栏 -->
    <div class="page-toolbar">
      <div class="search-box">
        <el-input
          v-model="searchText"
          placeholder="搜索技能名称或关键词"
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

    <!-- 技能卡片网格 -->
    <div class="skill-grid" v-if="filteredSkills.length > 0">
      <div
        v-for="skill in filteredSkills"
        :key="skill.id"
        class="skill-card"
      >
        <div class="card-header">
          <div class="skill-icon" :style="{ background: skill.iconBg }">
            {{ skill.icon }}
          </div>
          <div class="skill-meta">
            <div class="skill-name">{{ skill.name }}</div>
            <div class="skill-author">{{ skill.author }}</div>
          </div>
          <el-button
            type="primary"
            size="small"
            plain
            :disabled="skill.installed"
            @click="handleInstall(skill)"
          >
            {{ skill.installed ? '✓ 已安装' : '+ 添加' }}
          </el-button>
        </div>
        <div class="skill-desc">{{ skill.description }}</div>
        <div class="skill-tags">
          <span v-for="tag in skill.tags" :key="tag" class="skill-tag">{{ tag }}</span>
        </div>
        <div class="skill-stats">
          <span class="stat">⭐ {{ skill.stars }}</span>
          <span class="stat">📥 {{ skill.downloads }}</span>
          <span class="stat">v{{ skill.version }}</span>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <div class="empty-icon">🛒</div>
      <div class="empty-title">技能市场即将上线</div>
      <div class="empty-desc">
        这里将提供社区共享的智能体技能，包括专业提示词模板、工具组合包、工作流等。<br>
        您可以一键安装到本地，为智能体扩展能力。
      </div>
      <div class="empty-tags">
        <span class="empty-tag">📝 提示词技能</span>
        <span class="empty-tag">🔧 工具组合</span>
        <span class="empty-tag">⚙️ 工作流</span>
        <span class="empty-tag">🎨 创作辅助</span>
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
  { key: 'writing', label: '内容创作' },
  { key: 'dev', label: '开发工具' },
  { key: 'analysis', label: '数据分析' },
  { key: 'design', label: '界面设计' },
  { key: 'efficiency', label: '效率提升' },
])

// 预设技能示例（市场功能上线后替换为真实数据）
const skills = ref([
  {
    id: 'novel-outline',
    name: '小说大纲规划',
    author: '社区 · 作者A',
    icon: '📖',
    iconBg: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    description: '为长篇小说生成结构化大纲，包含人物、情节、章节拆分。',
    tags: ['创作', '小说', '大纲'],
    stars: 128,
    downloads: 342,
    version: '1.2.0',
    category: 'writing',
    installed: false,
  },
  {
    id: 'code-review',
    name: '代码审查专家',
    author: '社区 · 作者B',
    icon: '🔍',
    iconBg: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
    description: '自动审查代码质量，发现潜在bug、安全漏洞和性能问题。',
    tags: ['开发', '审查', '质量'],
    stars: 256,
    downloads: 892,
    version: '2.0.1',
    category: 'dev',
    installed: false,
  },
])

const filteredSkills = computed(() => {
  let list = skills.value
  if (activeCategory.value !== 'all') {
    list = list.filter(s => s.category === activeCategory.value)
  }
  if (searchText.value) {
    const kw = searchText.value.toLowerCase()
    list = list.filter(s =>
      s.name.toLowerCase().includes(kw) ||
      s.description.toLowerCase().includes(kw) ||
      s.tags.some(t => t.toLowerCase().includes(kw))
    )
  }
  return list
})

function handleInstall(skill) {
  ElMessage.info(`「${skill.name}」安装功能即将上线，敬请期待`)
}
</script>

<style scoped>
.skill-market-page {
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
  transition: all 0.2s ease;
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
  user-select: none;
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

.skill-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px;
}

.skill-card {
  padding: 16px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #f1f5f9;
  transition: all 0.25s ease;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.skill-card:hover {
  border-color: #c7d2fe;
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.12);
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.skill-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
  color: #fff;
  box-shadow: 0 3px 8px rgba(0, 0, 0, 0.1);
}

.skill-meta {
  flex: 1;
  min-width: 0;
}

.skill-name {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.skill-author {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

.skill-desc {
  font-size: 12px;
  color: #475569;
  line-height: 1.6;
  min-height: 38px;
}

.skill-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.skill-tag {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 4px;
  background: #f1f5f9;
  color: #64748b;
}

.skill-stats {
  display: flex;
  gap: 14px;
  font-size: 11px;
  color: #94a3b8;
  padding-top: 8px;
  border-top: 1px dashed #f1f5f9;
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
  max-width: 460px;
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
