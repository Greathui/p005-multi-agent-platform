/**
 * 工具图标和名称映射工具（P1-F03 修复：统一 3 处重复定义为单一来源）
 *
 * 提供完整的工具图标和中文标签映射，确保同一工具在所有组件中显示一致的图标和名称。
 * 之前 ChatWindow 有 20+ 工具映射，AgentThread 只有 4 个，导致同一工具在不同位置显示不同名称。
 */

// 工具名称 → emoji 图标映射（完整版，合并所有组件的映射）
const TOOL_ICON_MAP = {
  // 文件操作
  read_file: '📄',
  write_file: '✏️',
  edit_file: '📝',
  move_file: '📦',
  copy_file: '📋',
  list_directory: '📂',
  create_directory: '📁',
  grep: '🔍',
  glob: '🔎',
  read_image_file: '🖼️',
  download_file: '⬇️',
  upload_file: '⬆️',
  // 项目结构
  init_project_structure: '🏗️',
  create_agent_workspace: '🏠',
  // 任务管理
  create_task: '📋',
  create_sub_task: '📤',
  submit_task_result: '✅',
  grant_path_access: '🔓',
  revoke_path_access: '🔒',
  // 团队管理
  list_team_members: '👥',
  create_team_member: '➕',
  update_team_member: '✏️',
  remove_team_member: '➖',
  // 子代理
  invoke_sub_agent: '🤖',
  // 其他
  web_search: '🌐',
  ask_user: '❓',
}

// 工具名称 → 中文标签映射（完整版，合并所有组件的映射）
const TOOL_LABEL_MAP = {
  // 文件操作
  read_file: '读取文件',
  write_file: '写入文件',
  edit_file: '编辑文件',
  move_file: '归档文件',
  copy_file: '复制文件',
  list_directory: '浏览目录',
  create_directory: '创建目录',
  grep: '搜索内容',
  glob: '查找文件',
  read_image_file: '查看图片',
  download_file: '下载文件',
  upload_file: '上传文件',
  // 项目结构
  init_project_structure: '初始化项目',
  create_agent_workspace: '创建工作区',
  // 任务管理
  create_task: '创建任务',
  create_sub_task: '派发子任务',
  submit_task_result: '提交结果',
  grant_path_access: '授权路径',
  revoke_path_access: '撤销权限',
  // 团队管理
  list_team_members: '查看团队',
  create_team_member: '创建成员',
  update_team_member: '更新成员',
  remove_team_member: '移除成员',
  // 子代理
  invoke_sub_agent: '调用子代理',
  // 其他
  web_search: '搜索网页',
  ask_user: '询问用户',
}

/**
 * 获取工具的 emoji 图标
 * @param {string} toolName 工具名称
 * @returns {string} emoji 图标
 */
export function getToolIcon(toolName) {
  return TOOL_ICON_MAP[toolName] || '🔧'
}

/**
 * 获取工具的中文标签
 * @param {string} toolName 工具名称
 * @returns {string} 中文标签
 */
export function getToolLabel(toolName) {
  return TOOL_LABEL_MAP[toolName] || toolName
}

/**
 * 格式化工具调用显示文本
 * @param {Object} toolEvent 工具事件对象 { tool_name, tool_args, tool_result }
 * @returns {string} 格式化后的显示文本
 */
export function formatToolCall(te) {
  const name = te.tool_name
  const args = te.tool_args || {}
  const path = args.path || ''
  const label = getToolLabel(name)

  if (path) {
    // 只显示文件名部分，避免太长
    const parts = path.split(/[/\\]/).filter(Boolean)
    const short = parts.length > 2 ? '.../' + parts.slice(-2).join('/') : path
    return `${label} ${short}`
  }

  // 其他参数显示
  if (name === 'create_task' && args.task_type) {
    return `${label}(${args.task_type})`
  }
  if (name === 'create_team_member' && args.name) {
    return `${label}「${args.name}」`
  }
  if (name === 'create_sub_task' && args.name) {
    return `${label}「${args.name}」`
  }
  if (name === 'invoke_sub_agent' && args.sub_agent_name) {
    return `${label}「${args.sub_agent_name}」`
  }

  return label
}

/**
 * 把工具调用列表压成一行摘要（用于折叠态）
 * 例如：[list_team_members, create_team_member, create_task] → "查看团队 · 创建成员 · 创建任务"
 * @param {Array} toolEvents 工具事件数组
 * @returns {string} 摘要文本
 */
export function formatCollapsedTools(toolEvents) {
  if (!toolEvents || toolEvents.length === 0) return ''

  const labels = toolEvents.map(te => {
    const label = getToolLabel(te.tool_name)
    if (!label || label === te.tool_name) return te.tool_name

    const args = te.tool_args || {}
    if (te.tool_name === 'write_file' && args.path) {
      const shortPath = args.path.split(/[\\/]/).pop()
      return `${label} ${shortPath}`
    }
    if (te.tool_name === 'read_file' && args.path) {
      const shortPath = args.path.split(/[\\/]/).pop()
      return `${label} ${shortPath}`
    }
    if (te.tool_name === 'create_task' && args.task_type) {
      return `${label}(${args.task_type})`
    }
    if (te.tool_name === 'create_team_member' && args.name) {
      return `${label}「${args.name}」`
    }
    if (te.tool_name === 'create_sub_task' && args.name) {
      return `${label}「${args.name}」`
    }
    return label
  })

  // 最多显示 4 个，超过的显示 +N
  if (labels.length > 4) {
    return labels.slice(0, 4).join(' · ') + ` +${labels.length - 4}`
  }
  return labels.join(' · ')
}
