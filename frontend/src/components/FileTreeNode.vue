<template>
  <div class="file-tree-node">
    <div 
      class="tree-node" 
      :class="{ 
        directory: item.type === 'directory', 
        file: item.type === 'file',
        expanded: isExpanded
      }"
      :style="{ paddingLeft: (level * 16 + 12) + 'px' }"
      @click="handleClick"
    >
      <span v-if="item.type === 'directory'" class="expand-icon">
        {{ isExpanded ? '▾' : '▸' }}
      </span>
      <span v-else class="expand-icon placeholder"></span>
      <span class="node-icon">{{ getIcon() }}</span>
      <span class="node-name" :title="item.path">{{ item.name }}</span>
    </div>
    
    <!-- 子目录（懒加载） -->
    <div v-if="item.type === 'directory' && isExpanded && item.children" class="children">
      <FileTreeNode
        v-for="child in item.children"
        :key="child.path"
        :item="child"
        :level="level + 1"
        :expanded-dirs="expandedDirs"
        @select="$emit('select', $event)"
        @toggle-dir="$emit('toggle-dir', $event)"
      />
    </div>
    
    <!-- 加载中 -->
    <div v-if="item.type === 'directory' && isExpanded && !item.children" class="children">
      <div class="loading-child" :style="{ paddingLeft: ((level + 1) * 16 + 28) + 'px' }">
        加载中...
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { getFileIcon, getDirectoryIcon } from '../utils/fileIcons'

const props = defineProps({
  item: Object,
  level: Number,
  expandedDirs: Set
})

const emit = defineEmits(['select', 'toggle-dir'])

const isExpanded = computed(() => {
  return props.expandedDirs.has(props.item.path)
})

function handleClick() {
  if (props.item.type === 'directory') {
    emit('toggle-dir', props.item)
  } else {
    emit('select', props.item)
  }
}

// 文件图标函数已抽取到 utils/fileIcons.js
function getIcon() {
  if (props.item.type === 'directory') {
    return getDirectoryIcon(isExpanded.value)
  }
  return getFileIcon(props.item.name)
}
</script>

<style scoped>
.tree-node {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  cursor: pointer;
  font-size: 13px;
  user-select: none;
  transition: background 0.15s;
}

.tree-node:hover {
  background: #f5f7fa;
}

.tree-node.file:hover {
  background: #ecf5ff;
}

.expand-icon {
  width: 14px;
  text-align: center;
  font-size: 10px;
  color: #909399;
  flex-shrink: 0;
}

.expand-icon.placeholder {
  opacity: 0;
}

.node-icon {
  font-size: 15px;
  flex-shrink: 0;
}

.node-name {
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.children {
  /* 子节点自动缩进通过 paddingLeft 控制 */
}

.loading-child {
  padding: 4px 12px;
  font-size: 12px;
  color: #c0c4cc;
}
</style>
