<template>
  <div class="file-explorer">
    <!-- 文件树 -->
    <div class="file-tree" v-if="rootPath">
      <div class="tree-header">
        <span class="tree-title">📂 项目文件</span>
        <el-button text size="small" @click="refreshFileTree" :loading="loadingTree">
          🔄 刷新
        </el-button>
      </div>
      
      <!-- 目录结构说明（折叠） -->
      <el-collapse class="dir-legend" v-model="legendActive">
        <el-collapse-item title="📖 目录说明" name="legend">
          <div class="legend-content">
            <div class="legend-item"><span class="legend-icon">🔧</span><code>.agent/tasks/</code> 任务文件夹（自动生成，每个任务独立input/output）</div>
            <div class="legend-item"><span class="legend-icon">📤</span><code>shared/</code> 共享区（智能体间交换非任务文件）</div>
            <div class="legend-item"><span class="legend-icon">📁</span><code>agent_work/</code> 私有工作区（每个智能体自己的目录）</div>
            <div class="legend-item"><span class="legend-icon">✅</span><code>deliverables/</code> 最终交付物（整理后的成果）</div>
          </div>
        </el-collapse-item>
      </el-collapse>
      
      <div class="tree-body">
        <div v-if="loadingTree" class="tree-loading">
          加载中...
        </div>
        <template v-else-if="fileTree">
          <FileTreeNode 
            v-for="item in fileTree" 
            :key="item.path" 
            :item="item" 
            :level="0"
            @select="handleFileSelect"
            @toggle-dir="toggleDirectory"
            :expanded-dirs="expandedDirs"
          />
        </template>
        <div v-else class="tree-empty" @click="refreshFileTree">
          点击加载文件列表
        </div>
      </div>
    </div>

    <!-- 无目录提示 -->
    <div v-else class="no-path-tip">
      <div class="no-path-icon">📁</div>
      <div class="no-path-text">还没设置工作目录</div>
      <div class="no-path-desc">点击顶部「📂 工作目录」设置一个文件夹，就能在这里浏览文件了</div>
    </div>

    <!-- 文件预览抽屉 -->
    <el-drawer
      v-model="previewVisible"
      :title="null"
      direction="rtl"
      size="560px"
      :with-header="false"
      class="file-preview-drawer"
    >
      <div class="file-preview-panel" v-if="selectedFile">
        <!-- 文件头部 -->
        <div class="preview-header">
          <div class="file-info">
            <span class="file-icon">{{ getFileIcon(selectedFile.name) }}</span>
            <div class="file-meta">
              <div class="file-name">{{ selectedFile.name }}</div>
              <div class="file-path">{{ selectedFile.path }}</div>
            </div>
          </div>
          <div class="preview-actions">
            <el-button text size="small" @click="copyFilePath">
              📋 复制路径
            </el-button>
            <el-button text @click="previewVisible = false" class="close-btn">✕</el-button>
          </div>
        </div>

        <!-- 文件内容 -->
        <div class="preview-body">
          <div v-if="previewLoading" class="preview-loading">加载中...</div>
          <div v-else-if="previewError" class="preview-error">
            {{ previewError }}
          </div>
          <template v-else>
            <!-- 文本/代码文件 -->
            <div v-if="isTextFile(selectedFile.name)" class="code-preview">
              <pre><code :class="getLangClass(selectedFile.name)">{{ fileContent }}</code></pre>
            </div>
            <!-- Markdown 文件 -->
            <div v-else-if="isMarkdownFile(selectedFile.name)" class="markdown-preview markdown-body" v-html="renderMarkdown(fileContent)"></div>
            <!-- 图片文件 -->
            <div v-else-if="isImageFile(selectedFile.name)" class="image-preview">
              <img :src="api.getImageUrl(selectedFile.path, currentConvId)" :alt="selectedFile.name" @error="handleImageError" />
              <div v-if="imageError" class="image-error">图片加载失败</div>
            </div>
            <!-- 其他文件 -->
            <div v-else class="binary-preview">
              <div class="binary-icon">📄</div>
              <div class="binary-text">这是二进制文件或暂不支持预览的格式</div>
              <div class="binary-path">{{ selectedFile.path }}</div>
            </div>
          </template>
        </div>

        <!-- 点评区域 -->
        <div class="feedback-section">
          <div class="feedback-title">
            <span>💬 添加点评反馈</span>
          </div>
          <el-input
            v-model="feedbackText"
            type="textarea"
            :rows="3"
            placeholder="写下你对这个文件的修改意见、建议，或者直接@智能体让它修改..."
          />
          <div class="feedback-actions">
            <div class="feedback-tip">点评会发送到项目对话中，智能体能看到你的意见</div>
            <el-button type="primary" size="small" @click="submitFeedback" :loading="submittingFeedback">
              发送反馈
            </el-button>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { useAgentStore } from '../stores/agent'
import api from '../api'
import { ElMessage } from 'element-plus'
import { renderMarkdown } from '../utils/markdown'
import { getFileIcon, isTextFile, isImageFile, isMarkdownFile } from '../utils/fileIcons'
import 'highlight.js/styles/github.css'
import FileTreeNode from './FileTreeNode.vue'

const props = defineProps({
  modelValue: Boolean
})
const emit = defineEmits(['update:modelValue', 'send-feedback'])

const store = useAgentStore()

const rootPath = computed(() => store.currentRootPath)
const currentConvId = computed(() => store.currentConversationId)
const loadingTree = ref(false)
const fileTree = ref(null)
const expandedDirs = ref(new Set([rootPath.value]))
const legendActive = ref([])  // 目录说明默认折叠

// 文件预览
const previewVisible = ref(false)
const selectedFile = ref(null)
const fileContent = ref('')
const previewLoading = ref(false)
const previewError = ref('')
const imageError = ref(false)

// 点评反馈
const feedbackText = ref('')
const submittingFeedback = ref(false)

// 监听路径变化，自动刷新
watch(rootPath, (newPath) => {
  if (newPath) {
    refreshFileTree()
    expandedDirs.value = new Set([newPath])
  } else {
    fileTree.value = null
  }
}, { immediate: true })

// 刷新文件树
async function refreshFileTree() {
  if (!rootPath.value) return
  loadingTree.value = true
  try {
    const res = await api.listFiles('main', rootPath.value, currentConvId.value)
    // 后端返回 {items: [{name, is_dir, path}], path}，无 success 字段
    const items = res.data.items || []
    fileTree.value = buildFileTree(items, rootPath.value)
  } catch (e) {
    ElMessage.error('加载文件失败：' + (e.response?.data?.detail || e.message))
  } finally {
    loadingTree.value = false
  }
}

// 构建文件树结构
function buildFileTree(files, basePath) {
  // 后端返回 is_dir 字段（bool），转换为前端统一的 type 字段
  const dirs = files.filter(f => f.is_dir).sort((a, b) => a.name.localeCompare(b.name))
  const regularFiles = files.filter(f => !f.is_dir).sort((a, b) => a.name.localeCompare(b.name))
  
  const result = []
  
  for (const dir of dirs) {
    result.push({
      name: dir.name,
      path: dir.path,
      type: 'directory',
      children: null  // 懒加载
    })
  }
  
  for (const file of regularFiles) {
    result.push({
      name: file.name,
      path: file.path,
      type: 'file',
      size: file.size
    })
  }
  
  return result
}

// 展开/收起目录（懒加载子目录）
async function toggleDirectory(item) {
  if (expandedDirs.value.has(item.path)) {
    expandedDirs.value.delete(item.path)
    expandedDirs.value = new Set(expandedDirs.value)
  } else {
    expandedDirs.value.add(item.path)
    expandedDirs.value = new Set(expandedDirs.value)
    
    // 懒加载子目录内容
    if (!item.children) {
      try {
        const res = await api.listFiles('main', item.path, currentConvId.value)
        const items = res.data.items || []
        item.children = buildFileTree(items, item.path)
      } catch (e) {
        console.error('加载子目录失败:', e)
        ElMessage.error('加载子目录失败：' + (e.response?.data?.detail || e.message))
      }
    }
  }
}

// 选择文件，打开预览
async function handleFileSelect(item) {
  if (item.type === 'directory') return
  
  selectedFile.value = item
  previewVisible.value = true
  previewLoading.value = true
  previewError.value = ''
  imageError.value = false
  fileContent.value = ''
  feedbackText.value = ''
  
  try {
    const res = await api.readFile('main', item.path, currentConvId.value)
    // 后端返回 {content: str, path: str}，无 success 字段
    fileContent.value = res.data.content
  } catch (e) {
    previewError.value = '读取失败：' + (e.response?.data?.detail || e.message)
  } finally {
    previewLoading.value = false
  }
}

// 复制文件路径
async function copyFilePath() {
  if (!selectedFile.value) return
  try {
    await navigator.clipboard.writeText(selectedFile.value.path)
    ElMessage.success('路径已复制')
  } catch (e) {
    ElMessage.error('复制失败')
  }
}

// 提交点评反馈
function submitFeedback() {
  const text = feedbackText.value.trim()
  if (!text || !selectedFile.value) return
  
  const feedbackMsg = `【文件点评】文件：${selectedFile.value.path}\n\n${text}`
  emit('send-feedback', feedbackMsg)
  feedbackText.value = ''
  previewVisible.value = false
  ElMessage.success('反馈已发送')
}

// 文件类型判断
// 文件图标/类型判断函数已抽取到 utils/fileIcons.js
// getFileIcon / isTextFile / isImageFile / isMarkdownFile 从该模块导入

function getLangClass(filename) {
  const ext = filename.split('.').pop().toLowerCase()
  const langMap = {
    js: 'javascript',
    ts: 'typescript',
    py: 'python',
    html: 'html',
    css: 'css',
    json: 'json',
    md: 'markdown',
    vue: 'vue',
    java: 'java',
    go: 'go',
    rs: 'rust',
    cpp: 'cpp',
    c: 'c',
    sh: 'bash',
    yaml: 'yaml',
    yml: 'yaml'
  }
  return 'language-' + (langMap[ext] || 'plaintext')
}

function handleImageError() {
  imageError.value = true
}
</script>

<style scoped>
.file-explorer {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
}

/* 无目录提示 */
.no-path-tip {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
  text-align: center;
}

.no-path-icon {
  font-size: 56px;
  margin-bottom: 20px;
  opacity: 0.6;
  filter: grayscale(0.2);
}

.no-path-text {
  font-size: 15px;
  color: #0f172a;
  margin-bottom: 10px;
  font-weight: 500;
}

.no-path-desc {
  font-size: 13px;
  color: #94a3b8;
  line-height: 1.6;
  max-width: 220px;
}

/* 文件树 */
.tree-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #f1f5f9;
  background: linear-gradient(180deg, #fafbff 0%, #ffffff 100%);
}

.tree-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  letter-spacing: 0.2px;
}

/* 目录说明 */
.dir-legend {
  border-bottom: 1px solid #f1f5f9;
  --el-collapse-header-height: 38px;
}
.dir-legend :deep(.el-collapse-item__header) {
  font-size: 12px;
  color: #6366f1;
  height: 38px;
  line-height: 38px;
  padding: 0 20px;
  font-weight: 500;
  background: #f8fafc;
  transition: all 0.25s ease;
}
.dir-legend :deep(.el-collapse-item__header:hover) {
  color: #4f46e5;
  background: #f1f5f9;
}
.dir-legend :deep(.el-collapse-item__wrap) {
  border-bottom: none;
  background: #fff;
}
.dir-legend :deep(.el-collapse-item__content) {
  padding: 12px 20px 16px;
}
.legend-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.legend-item {
  font-size: 12px;
  color: #475569;
  line-height: 1.6;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 8px;
  background: #f8fafc;
  transition: all 0.25s ease;
}
.legend-item:hover {
  background: #eef2ff;
  transform: translateX(2px);
}
.legend-icon {
  flex-shrink: 0;
  font-size: 13px;
  margin-top: 1px;
}
.legend-item code {
  background: #fff;
  padding: 2px 6px;
  border-radius: 6px;
  font-size: 11px;
  color: #6366f1;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  flex-shrink: 0;
  font-weight: 500;
  border: 1px solid #e2e8f0;
}

.tree-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 8px;
}

.tree-loading, .tree-empty {
  padding: 24px;
  text-align: center;
  font-size: 13px;
  color: #94a3b8;
}

.tree-empty {
  cursor: pointer;
  transition: all 0.25s ease;
  border-radius: 12px;
  margin: 0 12px;
}

.tree-empty:hover {
  color: #6366f1;
  background: #eef2ff;
}

/* 文件预览抽屉 */
.file-preview-drawer :deep(.el-drawer__body) {
  padding: 0;
  background: #f8fafc;
}

.file-preview-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.file-info {
  display: flex;
  align-items: center;
  gap: 14px;
  flex: 1;
  min-width: 0;
}

.file-icon {
  font-size: 32px;
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%);
  border-radius: 12px;
}

.file-meta {
  min-width: 0;
}

.file-name {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-path {
  font-size: 12px;
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 4px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
}

.preview-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.close-btn {
  font-size: 18px;
  color: #94a3b8;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  transition: all 0.25s ease;
}
.close-btn:hover {
  background: #f1f5f9;
  color: #6366f1;
  transform: rotate(90deg);
}

.preview-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.preview-loading, .preview-error {
  padding: 48px;
  text-align: center;
  font-size: 14px;
  color: #94a3b8;
}

.preview-error {
  color: #ef4444;
  background: #fef2f2;
  border-radius: 12px;
  margin: 0 auto;
  max-width: 400px;
}

/* 代码预览 */
.code-preview {
  background: #1e293b;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
}

.code-preview pre {
  margin: 0;
  padding: 20px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.7;
}

.code-preview code {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  color: #e2e8f0;
}

/* Markdown 预览 */
.markdown-preview {
  background: #fff;
  padding: 28px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  font-size: 14px;
  line-height: 1.8;
  color: #0f172a;
  transition: all 0.25s ease;
}
.markdown-preview:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,0.08);
}

/* 图片预览 */
.image-preview {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  transition: all 0.25s ease;
}
.image-preview:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,0.08);
  transform: translateY(-1px);
}

.image-preview img {
  max-width: 100%;
  max-height: 500px;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.1);
}

.image-error {
  padding: 40px;
  color: #ef4444;
  font-size: 14px;
}

/* 二进制文件 */
.binary-preview {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 64px 24px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  text-align: center;
  transition: all 0.25s ease;
}
.binary-preview:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,0.08);
  transform: translateY(-1px);
}

.binary-icon {
  font-size: 64px;
  margin-bottom: 20px;
  opacity: 0.7;
  filter: grayscale(0.3);
}

.binary-text {
  font-size: 14px;
  color: #475569;
  margin-bottom: 10px;
  font-weight: 500;
}

.binary-path {
  font-size: 12px;
  color: #94a3b8;
  word-break: break-all;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  background: #f8fafc;
  padding: 6px 10px;
  border-radius: 6px;
  max-width: 100%;
}

/* 点评反馈区域 */
.feedback-section {
  padding: 20px 24px;
  background: #fff;
  border-top: 1px solid #e2e8f0;
  box-shadow: 0 -2px 8px rgba(0,0,0,0.04);
}

.feedback-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.feedback-title::before {
  content: '';
  display: inline-block;
  width: 4px;
  height: 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 2px;
}

.feedback-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
}

.feedback-tip {
  font-size: 12px;
  color: #94a3b8;
}

.feedback-actions :deep(.el-button--primary) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
  border: none !important;
  border-radius: 8px !important;
  padding: 0 20px !important;
  font-weight: 500 !important;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3) !important;
  transition: all 0.25s ease !important;
}
.feedback-actions :deep(.el-button--primary:hover) {
  transform: translateY(-1px) !important;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4) !important;
}
</style>
