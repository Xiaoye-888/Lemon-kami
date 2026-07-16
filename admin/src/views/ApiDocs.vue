<template>
  <div class="api-docs-page">
    <aside class="doc-sidebar">
      <div class="sidebar-title">
        <strong>小柠檬网络验证 API 文档</strong>
        <span>Lemon Kami API</span>
      </div>
      <nav class="doc-nav">
        <a
          href="#basic-info"
          :class="{ active: activeAnchor === 'basic-info' }"
          @click.prevent="scrollToAnchor('basic-info')"
        >
          基础信息
        </a>
        <div v-for="section in categorySections" :key="section.category" class="nav-group">
          <a
            class="nav-group-title"
            :href="`#${section.anchor}`"
            :class="{ active: activeAnchor === section.anchor }"
            @click.prevent="scrollToAnchor(section.anchor)"
          >
            {{ section.title }}
          </a>
          <a
            v-for="item in section.items"
            :key="item.interface_key"
            :href="`#${interfaceAnchor(item)}`"
            :class="{ active: activeAnchor === interfaceAnchor(item) }"
            @click.prevent="scrollToInterface(item)"
          >
            {{ item.name }}
          </a>
        </div>
      </nav>
    </aside>

    <main class="doc-content" v-loading="loading">
      <header class="doc-hero">
        <h1>小柠檬网络验证 API 文档</h1>
        <div class="doc-meta">
          <span>小柠檬网络验证</span>
          <span>接口目录自动生成</span>
          <span>JSON 响应格式</span>
        </div>
        <div class="doc-intro">
          本文档根据当前系统已有接口生成，覆盖用户注册登录、积分充值消费、SDK 卡密验证、卡密管理与批次管理等接口。业务系统可按接口地址、请求参数和响应示例进行对接。
        </div>
      </header>

      <section id="basic-info" class="doc-section">
        <h2>基础信息</h2>
        <ul class="basic-list">
          <li>
            <span>基础 URL：</span>
            <code>{{ origin }}</code>
          </li>
          <li>
            <span>认证方式：</span>
            <code>Authorization: Bearer &lt;token&gt;</code>
          </li>
          <li>
            <span>请求格式：</span>
            <code>application/json</code>
          </li>
          <li>
            <span>响应格式：</span>
            <code>JSON</code>
          </li>
        </ul>
      </section>

      <template v-for="section in categorySections" :key="section.category">
        <section :id="section.anchor" class="category-heading">
          <h2>{{ section.title }}</h2>
          <p>{{ section.description }}</p>
        </section>

        <section
          v-for="item in section.items"
          :id="interfaceAnchor(item)"
          :key="item.interface_key"
          class="endpoint"
        >
          <div class="endpoint-title">
            <div>
              <h3>{{ item.name }}</h3>
              <p>{{ item.description || item.doc_markdown || '暂无接口说明' }}</p>
            </div>
            <el-tag :type="item.is_builtin ? 'warning' : 'primary'" effect="plain">
              {{ item.is_builtin ? '内置接口' : '自定义接口' }}
            </el-tag>
          </div>

          <div class="code-block request-line">
            <span :class="['method-badge', methodClass(item.method)]">{{ item.method }}</span>
            <code>{{ item.path }}</code>
          </div>

          <div class="endpoint-meta">
            <div>
              <span>接口标识</span>
              <code>{{ item.interface_key }}</code>
            </div>
            <div>
              <span>归属分类</span>
              <code>{{ categoryLabel(item.category) }}</code>
            </div>
            <div>
              <span>Content-Type</span>
              <code>{{ item.content_type || 'application/json' }}</code>
            </div>
            <div>
              <span>认证方式</span>
              <code>{{ item.auth_mode || 'bearer' }}</code>
            </div>
          </div>

          <ParamTable title="请求头" :rows="normalizeParams(item.request_headers)" />
          <ParamTable title="请求参数" :rows="normalizeParams(item.request_params)" />
          <ParamTable title="返回参数" :rows="normalizeParams(item.response_params)" />

          <div class="examples">
            <div>
              <h4>成功响应示例</h4>
              <pre>{{ formatJson(item.success_example || item.response_example) }}</pre>
            </div>
            <div>
              <h4>错误响应示例</h4>
              <pre>{{ formatJson(item.error_example) }}</pre>
            </div>
          </div>

          <div v-if="item.remark" class="remark-box">
            {{ item.remark }}
          </div>
        </section>
      </template>

      <el-empty v-if="!loading && interfaces.length === 0" description="暂无接口文档数据" />
    </main>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getPublicInterfaceDocs } from '../api/interfaces'
import { interfaceKeyToAnchor } from '../utils/interfaceDocs'

const route = useRoute()
const loading = ref(false)
const interfaces = ref([])
const activeAnchor = ref('basic-info')
const origin = window.location.origin

const categoryMeta = {
  user: {
    title: '用户接口',
    description: '用于业务侧普通用户注册、登录和查询当前用户资料。'
  },
  points: {
    title: '积分接口',
    description: '用于查询积分余额、卡密兑换积分、扣除积分和查询积分流水。'
  },
  sdk: {
    title: 'SDK 接口',
    description: '用于客户端获取公钥、卡密验证、解绑机器码、读取应用配置和上报行为。'
  },
  admin: {
    title: '管理端接口',
    description: '用于后台管理卡密、批次、应用接口等数据。'
  },
  core: {
    title: '核心接口',
    description: '系统核心能力接口。'
  },
  other: {
    title: '其他接口',
    description: '未归入固定模块的接口。'
  }
}

const categoryOrder = ['user', 'points', 'sdk', 'admin', 'core', 'other']

const categoryLabel = (category) => categoryMeta[category]?.title || category || '未分类'

const categoryAnchor = (category) => `category-${interfaceKeyToAnchor(category || 'other')}`

const categorySections = computed(() => {
  const groups = interfaces.value.reduce((result, item) => {
    const category = item.category || 'other'
    if (!result[category]) result[category] = []
    result[category].push(item)
    return result
  }, {})

  return Object.keys(groups)
    .sort((left, right) => {
      const leftIndex = categoryOrder.indexOf(left)
      const rightIndex = categoryOrder.indexOf(right)
      return (leftIndex === -1 ? 999 : leftIndex) - (rightIndex === -1 ? 999 : rightIndex)
    })
    .map((category) => ({
      category,
      anchor: categoryAnchor(category),
      title: categoryLabel(category),
      description: categoryMeta[category]?.description || `${categoryLabel(category)}相关接口。`,
      items: groups[category]
    }))
})

const ParamTable = {
  props: {
    title: { type: String, required: true },
    rows: { type: Array, required: true }
  },
  template: `
    <div class="param-table">
      <h4>{{ title }}</h4>
      <el-table v-if="rows.length" :data="rows" border>
        <el-table-column prop="name" label="参数" min-width="150" show-overflow-tooltip />
        <el-table-column prop="type" label="类型" width="120" />
        <el-table-column label="必填" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.required ? 'danger' : 'info'" effect="plain">
              {{ row.required ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="260" show-overflow-tooltip />
        <el-table-column prop="example" label="示例" min-width="160" show-overflow-tooltip />
      </el-table>
      <div v-else class="empty-param">无参数</div>
    </div>
  `
}

const interfaceAnchor = (item) => interfaceKeyToAnchor(item.interface_key)

const methodClass = (method = '') => `method-${String(method).toLowerCase()}`

const normalizeRequired = (value) => value === true || value === 1 || value === '1' || value === '是'

const normalizeParams = (value) => {
  if (Array.isArray(value)) {
    return value.map((item) => ({
      name: item.name || item.key || item.field || '-',
      type: item.type || item.data_type || '-',
      required: normalizeRequired(item.required),
      description: item.description || item.desc || item.remark || '',
      example: item.example ?? item.default ?? ''
    }))
  }

  if (value && typeof value === 'object') {
    return Object.entries(value).map(([name, type]) => ({
      name,
      type: typeof type === 'string' ? type : typeof type,
      required: false,
      description: '',
      example: ''
    }))
  }

  return []
}

const formatJson = (value) => {
  if (value === null || value === undefined || value === '') return '{}'
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch (error) {
    return String(value)
  }
}

const currentRequestedAnchor = () => {
  const hash = decodeURIComponent(window.location.hash.replace(/^#/, ''))
  if (hash) return hash
  if (route.query.interface_key) return interfaceKeyToAnchor(route.query.interface_key)
  return 'basic-info'
}

const scrollToAnchor = (anchor) => {
  activeAnchor.value = anchor
  const target = document.getElementById(anchor)
  if (target) {
    target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  if (window.location.hash !== `#${anchor}`) {
    window.history.replaceState(null, '', `${window.location.pathname}#${anchor}`)
  }
}

const scrollToInterface = (item) => scrollToAnchor(interfaceAnchor(item))

const syncActiveFromHash = () => {
  activeAnchor.value = currentRequestedAnchor()
}

const loadDocs = async () => {
  loading.value = true
  try {
    const res = await getPublicInterfaceDocs({ page: 1, page_size: 100 })
    interfaces.value = res.data.items || []
    await nextTick()
    scrollToAnchor(currentRequestedAnchor())
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  window.addEventListener('hashchange', syncActiveFromHash)
  loadDocs()
})

onUnmounted(() => {
  window.removeEventListener('hashchange', syncActiveFromHash)
})
</script>

<style scoped>
.api-docs-page {
  display: grid;
  grid-template-columns: 292px minmax(0, 1fr);
  min-height: 100vh;
  background: #fff;
  color: #1f2937;
}

.doc-sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  padding: 28px 22px;
  border-right: 1px solid #e5e7eb;
  background: rgba(255, 255, 255, 0.96);
  overflow: auto;
}

.sidebar-title {
  display: grid;
  gap: 5px;
  margin-bottom: 22px;
}

.sidebar-title strong {
  color: #0f172a;
  font-size: 17px;
}

.sidebar-title span {
  color: #64748b;
  font-size: 12px;
}

.doc-nav,
.nav-group {
  display: grid;
  gap: 2px;
}

.nav-group {
  margin-top: 10px;
}

.doc-nav a {
  display: block;
  padding: 7px 8px;
  border-radius: 6px;
  color: #475569;
  font-size: 14px;
  line-height: 1.45;
  text-decoration: none;
}

.doc-nav a:hover,
.doc-nav a.active {
  color: #0f62fe;
  background: #eff6ff;
}

.doc-nav .nav-group-title {
  color: #0f172a;
  font-weight: 700;
}

.nav-group .nav-group-title ~ a {
  padding-left: 22px;
}

.doc-content {
  width: min(1180px, calc(100vw - 340px));
  padding: 72px 42px 96px;
}

.doc-hero {
  margin-bottom: 44px;
}

.doc-hero h1 {
  margin: 0;
  color: #111827;
  font-size: 42px;
  font-weight: 800;
  line-height: 1.15;
  letter-spacing: 0;
}

.doc-meta {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  margin-top: 18px;
  color: #6b7280;
  font-size: 14px;
}

.doc-meta span + span {
  padding-left: 14px;
  border-left: 1px solid #d1d5db;
}

.doc-intro {
  margin-top: 24px;
  padding: 18px 20px;
  border: 1px solid #d9dee8;
  border-radius: 8px;
  color: #4b5563;
  background: #fbfdff;
  line-height: 1.8;
}

.doc-section,
.category-heading,
.endpoint {
  scroll-margin-top: 24px;
}

.doc-section,
.category-heading {
  margin: 42px 0 28px;
  padding-bottom: 26px;
  border-bottom: 1px solid #e5e7eb;
}

.doc-section h2,
.category-heading h2 {
  margin: 0 0 18px;
  color: #111827;
  font-size: 28px;
  line-height: 1.2;
}

.category-heading p {
  margin: 0;
  color: #64748b;
  line-height: 1.7;
}

.basic-list {
  display: grid;
  gap: 14px;
  padding-left: 22px;
}

.basic-list li {
  line-height: 1.8;
}

.basic-list span {
  color: #374151;
}

.endpoint {
  margin: 34px 0 54px;
}

.endpoint-title {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 16px;
}

.endpoint-title h3 {
  margin: 0;
  color: #111827;
  font-size: 25px;
  line-height: 1.25;
}

.endpoint-title p {
  margin: 10px 0 0;
  color: #4b5563;
  line-height: 1.75;
}

.code-block {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f6f8fa;
}

.request-line {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  overflow-x: auto;
}

.method-badge {
  flex: 0 0 auto;
  min-width: 54px;
  padding: 4px 8px;
  border-radius: 5px;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  text-align: center;
}

.method-get {
  background: #16a34a;
}

.method-post {
  background: #0ea5e9;
}

.method-put {
  background: #2563eb;
}

.method-delete {
  background: #dc2626;
}

.endpoint-meta {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin: 18px 0;
}

.endpoint-meta > div {
  min-width: 0;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.endpoint-meta span {
  display: block;
  margin-bottom: 6px;
  color: #64748b;
  font-size: 12px;
}

code,
pre {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

code {
  color: #2563eb;
  word-break: break-all;
}

.param-table {
  margin-top: 22px;
}

.param-table h4,
.examples h4 {
  margin: 0 0 10px;
  color: #1f2937;
  font-size: 16px;
}

.empty-param {
  padding: 14px 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  color: #94a3b8;
  background: #f8fafc;
}

.examples {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 22px;
}

pre {
  min-height: 180px;
  margin: 0;
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  color: #1f2937;
  background: #f6f8fa;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}

.remark-box {
  margin-top: 18px;
  padding: 14px 16px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  color: #1e3a8a;
  background: #eff6ff;
}

@media (max-width: 980px) {
  .api-docs-page {
    grid-template-columns: 1fr;
  }

  .doc-sidebar {
    position: static;
    height: auto;
    max-height: 360px;
  }

  .doc-content {
    width: 100%;
    padding: 40px 18px 64px;
  }

  .doc-hero h1 {
    font-size: 32px;
  }

  .endpoint-meta,
  .examples {
    grid-template-columns: 1fr;
  }
}
</style>
