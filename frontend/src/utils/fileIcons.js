/**
 * 文件图标映射工具（P1-F02 修复：统一 4 处重复定义为单一来源）
 *
 * 提供两个主要函数：
 * - getFileIcon(fileName): 根据文件名返回 emoji 图标
 * - getLanguageIcon(language): 根据编程语言名称返回 emoji 图标（用于代码产出展示）
 * - isImageFile(fileName): 判断是否是图片文件
 * - isTextFile(fileName): 判断是否是文本文件
 */

// 文件扩展名 → emoji 图标映射（合并自 ChatWindow / FileTreeNode / FileExplorer）
const FILE_ICON_MAP = {
  // 文本
  txt: '📄', md: '📝', markdown: '📝', log: '📃',
  // 数据格式
  json: '📋', csv: '📊', yaml: '⚙️', yml: '⚙️', toml: '⚙️', ini: '⚙️', conf: '⚙️', xml: '📄',
  // 编程语言
  js: '📜', mjs: '📜', cjs: '📜', ts: '📜', vue: '💚', py: '🐍',
  java: '☕', kt: '☕', scala: '☕',
  c: '🔧', h: '🔧', cpp: '🔧', hpp: '🔧', cc: '🔧',
  go: '🐹', rs: '🦀', rb: '💎', php: '🐘', swift: '🦅',
  sh: '⚙️', bash: '⚙️', zsh: '⚙️', bat: '⚙️', ps1: '⚙️',
  sql: '🗄️', r: '📊', lua: '🌙',
  // 标记/样式
  html: '🌐', htm: '🌐', css: '🎨', scss: '🎨', less: '🎨',
  jsx: '⚛️', tsx: '⚛️',
  // 图片
  jpg: '🖼️', jpeg: '🖼️', png: '🖼️', gif: '🖼️', webp: '🖼️', svg: '🖼️', bmp: '🖼️', ico: '🖼️',
  // 文档
  pdf: '📕', doc: '📘', docx: '📘', xls: '📗', xlsx: '📗', ppt: '📙', pptx: '📙',
  // 压缩包
  zip: '📦', rar: '📦', '7z': '📦', tar: '📦', gz: '📦',
  // 可执行/系统
  exe: '⚙️', msi: '⚙️', dmg: '⚙️', deb: '⚙️', rpm: '⚙️',
}

// 编程语言名称 → emoji 图标映射（用于产出文件按语言展示图标）
const LANGUAGE_ICON_MAP = {
  python: '🐍', py: '🐍',
  javascript: '📜', js: '📜',
  typescript: '📘', ts: '📘',
  vue: '💚',
  html: '🌐',
  css: '🎨',
  json: '📋',
  markdown: '📝', md: '📝',
  bash: '⚙️', sh: '⚙️', shell: '⚙️',
  sql: '🗄️',
  java: '☕',
  cpp: '🔧', 'c++': '🔧', c: '🔧',
  go: '🐹',
  rust: '🦀', rs: '🦀',
  ruby: '💎', rb: '💎',
  php: '🐘',
  r: '📊',
  yaml: '⚙️', toml: '⚙️', ini: '⚙️',
}

// 图片扩展名集合
const IMAGE_EXTENSIONS = new Set(['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'ico'])

// 文本文件扩展名集合
const TEXT_EXTENSIONS = new Set([
  'txt', 'md', 'markdown', 'log',
  'js', 'mjs', 'cjs', 'ts', 'vue', 'jsx', 'tsx',
  'py', 'java', 'kt', 'scala', 'c', 'h', 'cpp', 'hpp', 'cc',
  'go', 'rs', 'rb', 'php', 'swift',
  'json', 'html', 'htm', 'css', 'scss', 'less',
  'yaml', 'yml', 'toml', 'ini', 'conf', 'xml', 'csv',
  'sh', 'bash', 'zsh', 'bat', 'ps1',
  'sql', 'r', 'lua',
])

/**
 * 根据文件名返回 emoji 图标
 * @param {string} fileName 文件名（含扩展名）
 * @returns {string} emoji 图标
 */
export function getFileIcon(fileName) {
  if (!fileName) return '📄'
  const ext = fileName.split('.').pop()?.toLowerCase()
  return FILE_ICON_MAP[ext] || '📄'
}

/**
 * 根据编程语言名称返回 emoji 图标（用于代码产出展示）
 * @param {string} language 编程语言名称（如 python, javascript）
 * @returns {string} emoji 图标
 */
export function getLanguageIcon(language) {
  if (!language) return '📄'
  return LANGUAGE_ICON_MAP[language?.toLowerCase()] || '📄'
}

/**
 * 判断文件是否是图片
 * @param {string} fileName 文件名
 * @returns {boolean}
 */
export function isImageFile(fileName) {
  if (!fileName) return false
  const ext = fileName.split('.').pop()?.toLowerCase()
  return IMAGE_EXTENSIONS.has(ext)
}

/**
 * 判断文件是否是文本文件
 * @param {string} fileName 文件名
 * @returns {boolean}
 */
export function isTextFile(fileName) {
  if (!fileName) return false
  const ext = fileName.split('.').pop()?.toLowerCase()
  return TEXT_EXTENSIONS.has(ext)
}

/**
 * 判断文件是否是 Markdown
 * @param {string} fileName 文件名
 * @returns {boolean}
 */
export function isMarkdownFile(fileName) {
  if (!fileName) return false
  const ext = fileName.split('.').pop()?.toLowerCase()
  return ext === 'md' || ext === 'markdown'
}

/**
 * 获取目录图标（展开/收起状态）
 * @param {boolean} isExpanded 是否展开
 * @returns {string} emoji 图标
 */
export function getDirectoryIcon(isExpanded) {
  return isExpanded ? '📂' : '📁'
}
