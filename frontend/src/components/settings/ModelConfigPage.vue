<template>
  <div class="model-config-page">
    <div class="config-layout">
      <!-- 左侧：配置列表 -->
      <div class="config-list-panel">
        <div class="list-header">
          <span>已保存的配置</span>
          <el-button type="primary" size="small" @click="handleAdd">+ 新建</el-button>
        </div>
        <div class="config-list">
          <div
            v-for="cfg in configs"
            :key="cfg.id"
            class="config-item"
            :class="{ active: editingId === cfg.id, disabled: cfg.enabled === false }"
            @click="handleSelect(cfg)"
          >
            <div class="config-item-header">
              <span class="config-provider-badge" :style="{ background: getProviderColor(cfg.provider) }">
                {{ getProviderLabel(cfg.provider) }}
              </span>
              <span class="config-name">{{ cfg.name }}</span>
              <el-switch
                :model-value="cfg.enabled !== false"
                size="small"
                class="config-item-switch"
                @update:model-value="(val) => toggleEnabled(cfg, val)"
                @click.stop
              />
            </div>
            <div class="config-item-model">{{ cfg.model }}</div>
            <div class="config-item-provider">{{ getProviderName(cfg.provider) }}</div>
          </div>
          <div v-if="configs.length === 0" class="empty-tip">
            暂无配置，点击「新建」添加
          </div>
        </div>
      </div>

      <!-- 右侧：编辑表单 -->
      <div class="config-form-panel">
        <div v-if="editingId" class="form-content">
          <div class="form-header">
            <h3>{{ isEditing ? '编辑配置' : '新建配置' }}</h3>
            <div class="form-actions">
              <el-button size="small" @click="handleTest" :loading="testing">测试</el-button>
              <el-button size="small" type="danger" text @click="handleDelete" v-if="isEditing">删除</el-button>
            </div>
          </div>

          <el-form :model="form" label-width="80px" size="default">
            <el-form-item label="名称">
              <el-input v-model="form.name" placeholder="如：通义千问-主力" />
            </el-form-item>

            <el-form-item label="服务商">
              <el-select
                v-model="form.provider"
                placeholder="选择服务商"
                style="width: 100%"
                @change="onProviderChange"
              >
                <el-option
                  v-for="p in providers"
                  :key="p.code"
                  :label="p.name"
                  :value="p.code"
                >
                  <span>{{ p.icon }} {{ p.name }}</span>
                </el-option>
              </el-select>
            </el-form-item>

            <el-form-item label="模型">
              <el-select
                v-model="form.model"
                placeholder="选择或输入模型"
                filterable
                allow-create
                default-first-option
                style="width: 100%"
              >
                <el-option
                  v-for="m in currentModels"
                  :key="m"
                  :label="m"
                  :value="m"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="API 密钥">
              <el-input
                v-model="form.api_key"
                type="password"
                show-password
                placeholder="sk-xxxxxxxx"
              >
                <template #append v-if="isKeyMasked">
                  <el-tooltip content="点击清除脱敏值，粘贴新的 API Key" placement="top">
                    <el-button @click="form.api_key = ''">重置</el-button>
                  </el-tooltip>
                </template>
              </el-input>
              <div class="key-tip" v-if="isKeyMasked">
                💡 当前显示的是脱敏值。无需修改可直接保存（不会覆盖原 Key）；如要更换 Key，点「重置」后粘贴新值。
              </div>
            </el-form-item>

            <el-form-item label="API 地址">
              <el-input v-model="form.base_url" placeholder="https://..." />
            </el-form-item>

            <el-divider content-position="left" style="margin: 16px 0">高级设置</el-divider>

            <el-form-item label="温度">
              <el-slider v-model="form.temperature" :min="0" :max="2" :step="0.1" show-input :input-size="'small'" style="flex: 1" />
            </el-form-item>

            <el-form-item label="最大长度">
              <el-slider v-model="form.max_tokens" :min="100" :max="16000" :step="100" show-input :input-size="'small'" style="flex: 1" />
            </el-form-item>

            <el-form-item label="思考模式">
              <el-switch v-model="form.enable_thinking" active-text="开启" inactive-text="关闭" />
            </el-form-item>

            <el-form-item label="上下文窗口">
              <el-input-number v-model="form.context_window" :min="4096" :max="1048576" :step="4096" size="small" controls-position="right" style="width: 180px" />
              <span class="form-hint" style="margin-left: 8px; color: #94a3b8; font-size: 12px">token（影响历史消息保留量）</span>
            </el-form-item>
          </el-form>

          <div class="form-footer">
            <el-button @click="handleCancel">取消</el-button>
            <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
          </div>
        </div>

        <div v-else class="empty-form">
          <div class="empty-icon"></div>
          <div class="empty-text">选择一个配置进行编辑，或点击「新建」创建新配置</div>
        </div>
      </div>
    </div>

    <!-- 测试结果 -->
    <div v-if="testResult.message" class="test-result-bar" :class="{ ok: testResult.ok, fail: !testResult.ok }">
      <span>{{ testResult.ok ? '✅' : '❌' }}</span>
      <span>{{ testResult.message }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const configs = ref([])
const providers = ref([])
const editingId = ref('')
const saving = ref(false)
const testing = ref(false)
const testResult = ref({ ok: false, message: '' })
const modelHistory = ref([])

const form = ref({
  name: '',
  provider: '',
  base_url: '',
  api_key: '',
  model: '',
  temperature: 0.7,
  max_tokens: 2000,
  enable_thinking: false,
  context_window: 131072,
  enabled: true
})

const isEditing = computed(() => configs.value.some(c => c.id === editingId.value))
const isKeyMasked = computed(() => typeof form.value.api_key === 'string' && form.value.api_key.includes('***'))

const currentProvider = computed(() =>
  providers.value.find(p => p.code === form.value.provider) || null
)

const currentModels = computed(() => {
  const providerModels = currentProvider.value?.models || []
  const allModels = [...providerModels.map(m => m.id), ...modelHistory.value]
  return [...new Set(allModels)]
})

const PROVIDER_STYLES = {
  openai:      { color: '#10a37f', label: 'AI', name: 'OpenAI' },
  deepseek:    { color: '#4d6bfe', label: 'DS', name: '深度求索' },
  qwen:        { color: '#615ced', label: 'QW', name: '通义千问' },
  moonshot:    { color: '#1d1d1f', label: 'MS', name: '月之暗面' },
  zhipu:      { color: '#3859ff', label: 'ZP', name: '智谱清言' },
  siliconflow: { color: '#ff6b35', label: 'SF', name: '硅基流动' },
  ollama:      { color: '#000000', label: 'OL', name: '本地 Ollama' },
}

function getProviderColor(provider) {
  return (PROVIDER_STYLES[provider] || { color: '#94a3b8' }).color
}
function getProviderLabel(provider) {
  return (PROVIDER_STYLES[provider] || { label: '?' }).label
}
function getProviderName(provider) {
  if (!provider) return '自定义'
  return (PROVIDER_STYLES[provider] || { name: provider }).name
}

async function loadData() {
  testResult.value = { ok: false, message: '' }
  try {
    const [configsRes, providersRes] = await Promise.all([
      api.getModelConfigs(),
      api.getProviders()
    ])
    configs.value = configsRes.data.configs || []
    providers.value = providersRes.data.providers || []
    loadModelHistory()
  } catch (e) {
    ElMessage.error('加载失败')
  }
}

function loadModelHistory() {
  try {
    const saved = localStorage.getItem('model_history')
    modelHistory.value = saved ? JSON.parse(saved) : []
  } catch (e) {
    modelHistory.value = []
  }
}

function saveModelToHistory(model) {
  if (!model) return
  const history = modelHistory.value
  const filtered = history.filter(m => m !== model)
  filtered.unshift(model)
  modelHistory.value = filtered.slice(0, 20)
  localStorage.setItem('model_history', JSON.stringify(modelHistory.value))
}

function handleSelect(cfg) {
  editingId.value = cfg.id
  form.value = {
    name: cfg.name,
    provider: cfg.provider || '',
    base_url: cfg.base_url,
    api_key: cfg.api_key,
    model: cfg.model,
    temperature: cfg.temperature ?? 0.7,
    max_tokens: cfg.max_tokens ?? 2000,
    enable_thinking: cfg.enable_thinking ?? false,
    context_window: cfg.context_window ?? 131072,
    enabled: cfg.enabled !== false  // 旧数据没有 enabled 字段时默认为 true
  }
  testResult.value = { ok: false, message: '' }
}

function handleAdd() {
  editingId.value = 'new'
  form.value = {
    name: '', provider: '', base_url: '', api_key: '', model: '',
    temperature: 0.7, max_tokens: 2000, enable_thinking: false, context_window: 131072,
    enabled: true
  }
  testResult.value = { ok: false, message: '' }
}

function handleCancel() {
  editingId.value = ''
  testResult.value = { ok: false, message: '' }
}

function onProviderChange(code) {
  const provider = providers.value.find(p => p.code === code)
  if (provider) {
    if (provider.base_url) form.value.base_url = provider.base_url
    if (provider.default_model) form.value.model = provider.default_model
  }
}

async function handleSave() {
  if (!form.value.name || !form.value.base_url || !form.value.api_key || !form.value.model) {
    ElMessage.warning('请填写名称、API 地址、密钥和模型')
    return
  }
  saving.value = true
  try {
    const payload = { ...form.value }
    if (isEditing.value && typeof payload.api_key === 'string' && payload.api_key.includes('***')) {
      delete payload.api_key
    }
    if (isEditing.value) {
      await api.updateModelConfig(editingId.value, payload)
      ElMessage.success('配置已更新')
    } else {
      const res = await api.createModelConfig(payload)
      ElMessage.success('配置已创建')
      editingId.value = res.data.config.id
    }
    saveModelToHistory(form.value.model)
    await loadData()
  } catch (e) {
    ElMessage.error('保存失败：' + (e.response?.data?.detail || e.message))
  } finally {
    saving.value = false
  }
}

async function handleDelete() {
  try {
    await ElMessageBox.confirm('确定要删除这个配置吗？', '确认删除', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消'
    })
    await api.deleteModelConfig(editingId.value)
    ElMessage.success('已删除')
    editingId.value = ''
    await loadData()
  } catch (e) {}
}

// 卡片上的开关：直接调 API 切换启用状态，不需要进编辑模式
async function toggleEnabled(cfg, val) {
  try {
    await api.updateModelConfig(cfg.id, { enabled: val })
    // 更新本地列表状态（避免整页刷新）
    cfg.enabled = val
    // 如果正在编辑这个配置，同步表单
    if (editingId.value === cfg.id) {
      form.value.enabled = val
    }
    ElMessage.success(val ? '已启用' : '已禁用')
  } catch (e) {
    ElMessage.error('切换失败：' + (e.response?.data?.detail || e.message))
  }
}

async function handleTest() {
  if (!form.value.base_url || !form.value.api_key || !form.value.model) {
    ElMessage.warning('请先填写 API 地址、密钥和模型')
    return
  }
  testing.value = true
  testResult.value = { ok: false, message: '' }
  try {
    if (isEditing.value) {
      const res = await api.testModelConfig(editingId.value)
      testResult.value = { ok: res.data.ok, message: res.data.message }
    } else {
      const res = await api.testConfig({
        base_url: form.value.base_url,
        api_key: form.value.api_key,
        model: form.value.model
      })
      testResult.value = { ok: res.data.ok, message: res.data.message }
    }
  } catch (e) {
    testResult.value = { ok: false, message: '测试失败：' + (e.response?.data?.detail || e.message) }
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.model-config-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.config-layout {
  display: flex;
  gap: 0;
  min-height: 420px;
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid #f1f5f9;
}

.key-tip {
  margin-top: 6px;
  font-size: 12px;
  color: #6366f1;
  line-height: 1.5;
  background: #eef2ff;
  padding: 6px 10px;
  border-radius: 6px;
}

.config-list-panel {
  width: 240px;
  flex-shrink: 0;
  border-right: 1px solid #f1f5f9;
  display: flex;
  flex-direction: column;
  background: #f8fafc;
}

.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  border-bottom: 1px solid #f1f5f9;
  background: #fff;
}

.config-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.config-item {
  padding: 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.25s ease;
  margin-bottom: 8px;
  border: 1px solid transparent;
  background: #fff;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  position: relative;
  overflow: hidden;
}

.config-item::before {
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 3px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  opacity: 0;
  transition: opacity 0.25s ease;
}

.config-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.15);
  border-color: #e0e7ff;
}
.config-item:hover::before { opacity: 0.5; }

.config-item.active {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.08) 0%, rgba(118, 75, 162, 0.08) 100%);
  border-color: #c7d2fe;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.2);
  transform: translateY(-1px);
}
.config-item.active::before { opacity: 1; }

.config-item-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.config-provider-badge {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}

.config-name {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.config-item-model {
  font-size: 11px;
  color: #6366f1;
  margin-bottom: 4px;
  font-weight: 500;
  padding: 2px 8px;
  background: rgba(99, 102, 241, 0.08);
  border-radius: 9999px;
  display: inline-block;
}

.config-item-provider {
  font-size: 11px;
  color: #94a3b8;
}

.config-item.disabled {
  opacity: 0.55;
}

.config-item.disabled .config-item-model {
  background: rgba(148, 163, 184, 0.12);
  color: #94a3b8;
}

/* 卡片上的开关：定位到右上角 */
.config-item-switch {
  margin-left: auto;
  flex-shrink: 0;
}

/* 禁用状态下开关更低调 */
.config-item.disabled :deep(.el-switch.is-checked .el-switch__core) {
  opacity: 0.7;
}

.empty-tip {
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
  padding: 40px 16px;
  line-height: 1.6;
}

.config-form-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.form-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid #f1f5f9;
}

.form-header h3 {
  margin: 0;
  font-size: 15px;
  color: #0f172a;
  font-weight: 600;
  position: relative;
  padding-left: 12px;
}

.form-header h3::before {
  content: '';
  position: absolute;
  left: 0; top: 50%;
  transform: translateY(-50%);
  width: 4px; height: 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 2px;
}

.form-actions {
  display: flex;
  gap: 8px;
}

.form-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 4px 4px 0;
}

.form-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid #f1f5f9;
}

.empty-form {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #94a3b8;
  gap: 16px;
  padding: 40px 20px;
}

.empty-icon {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}
.empty-icon::before {
  content: '⚙️';
  font-size: 32px;
  opacity: 0.7;
}

.empty-text {
  font-size: 13px;
  text-align: center;
  line-height: 1.6;
  color: #64748b;
}

.test-result-bar {
  margin-top: 12px;
  padding: 10px 16px;
  border-radius: 10px;
  display: flex;
  gap: 10px;
  align-items: center;
  font-size: 13px;
  font-weight: 500;
}

.test-result-bar.ok {
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(5, 150, 105, 0.1) 100%);
  color: #059669;
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.test-result-bar.fail {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(220, 38, 38, 0.1) 100%);
  color: #dc2626;
  border: 1px solid rgba(239, 68, 68, 0.2);
}

:deep(.el-select .el-select__caret) {
  transition: transform 0.25s ease;
  transform: rotate(-90deg);
  color: #94a3b8;
}
:deep(.el-select .el-select__caret.is-reverse) {
  transform: rotate(0deg);
  color: #6366f1;
}

:deep(.el-slider__runway) { background-color: #e2e8f0; height: 6px; }
:deep(.el-slider__bar) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  height: 6px;
}
:deep(.el-slider__button) {
  border: 2px solid #6366f1;
  width: 16px; height: 16px;
}
:deep(.el-slider__button:hover) { box-shadow: 0 0 0 6px rgba(99, 102, 241, 0.15); }

:deep(.el-switch.is-checked .el-switch__core) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-color: transparent;
}

:deep(.el-form-item__label) {
  color: #475569;
  font-weight: 500;
  font-size: 13px;
}

:deep(.el-divider__text) {
  color: #64748b;
  font-weight: 500;
  font-size: 12px;
  background: #fff;
}
</style>
