<template>
  <div class="interface-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>接口列表</span>
          <el-button type="primary" @click="router.push('/interfaces/new')">添加接口</el-button>
        </div>
      </template>

      <el-form :inline="true" :model="queryParams" class="filter-form">
        <el-form-item label="关键词">
          <el-input
            v-model="queryParams.keyword"
            clearable
            placeholder="搜索接口名称、标识、说明或地址"
            style="width: 260px"
            @keyup.enter="loadInterfaces"
          />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="queryParams.category" clearable placeholder="user / points / sdk" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryParams.status" clearable placeholder="全部" style="width: 120px">
            <el-option label="启用" :value="1" />
            <el-option label="停用" :value="0" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadInterfaces">搜索</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="interfaces" v-loading="loading" border stripe>
        <el-table-column type="selection" width="48" />
        <el-table-column prop="id" label="接口ID" width="86" />
        <el-table-column prop="category" label="归属分类" width="110" show-overflow-tooltip />
        <el-table-column prop="name" label="接口名称" min-width="130" show-overflow-tooltip />
        <el-table-column prop="description" label="接口说明" min-width="260" show-overflow-tooltip />
        <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip />
        <el-table-column label="请求地址" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.method }}</el-tag>
            <span class="path-text">{{ row.path }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="92">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'">
              {{ row.status === 1 ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="96">
          <template #default="{ row }">
            <el-tag :type="row.is_builtin ? 'warning' : 'primary'" effect="plain">
              {{ row.is_builtin ? '内置' : '自定义' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="warning" @click="goDocs(row)">开发文档</el-button>
            <el-button size="small" type="primary" @click="showEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.page_size"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        class="pagination"
        @size-change="loadInterfaces"
        @current-change="loadInterfaces"
      />
    </el-card>

    <el-dialog v-model="editDialogVisible" title="编辑接口" width="860px">
      <el-form :model="editForm" label-width="118px">
        <div class="form-grid">
          <el-form-item label="接口名称" required>
            <el-input v-model="editForm.name" />
          </el-form-item>
          <el-form-item label="接口标识" required>
            <el-input v-model="editForm.interface_key" />
          </el-form-item>
          <el-form-item label="请求方法" required>
            <el-select v-model="editForm.method" style="width: 100%">
              <el-option label="GET" value="GET" />
              <el-option label="POST" value="POST" />
              <el-option label="PUT" value="PUT" />
              <el-option label="DELETE" value="DELETE" />
            </el-select>
          </el-form-item>
          <el-form-item label="分类">
            <el-input v-model="editForm.category" />
          </el-form-item>
          <el-form-item label="认证方式">
            <el-input v-model="editForm.auth_mode" />
          </el-form-item>
          <el-form-item label="Content-Type">
            <el-input v-model="editForm.content_type" />
          </el-form-item>
        </div>
        <el-form-item label="接口地址" required>
          <el-input v-model="editForm.path" />
        </el-form-item>
        <el-form-item label="接口说明">
          <el-input v-model="editForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="editForm.enabled" active-text="启用" inactive-text="停用" />
        </el-form-item>
        <el-form-item label="请求头 JSON">
          <el-input v-model="editForm.request_headers_text" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="请求参数 JSON">
          <el-input v-model="editForm.request_params_text" type="textarea" :rows="5" />
        </el-form-item>
        <el-form-item label="返回参数 JSON">
          <el-input v-model="editForm.response_params_text" type="textarea" :rows="5" />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="成功示例 JSON">
            <el-input v-model="editForm.success_example_text" type="textarea" :rows="7" />
          </el-form-item>
          <el-form-item label="错误示例 JSON">
            <el-input v-model="editForm.error_example_text" type="textarea" :rows="7" />
          </el-form-item>
        </div>
        <el-form-item label="接口文档">
          <el-input v-model="editForm.doc_markdown" type="textarea" :rows="5" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.remark" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleUpdate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getInterfaces, updateInterface } from '../api/interfaces'
import { openInterfaceDoc } from '../utils/interfaceDocs'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const interfaces = ref([])
const total = ref(0)
const editDialogVisible = ref(false)

const queryParams = reactive({
  keyword: '',
  category: '',
  status: '',
  page: 1,
  page_size: 20
})

const editForm = reactive({
  id: null,
  name: '',
  interface_key: '',
  method: 'POST',
  path: '',
  category: '',
  description: '',
  auth_mode: 'bearer',
  content_type: 'application/json',
  enabled: true,
  request_headers_text: '[]',
  request_params_text: '[]',
  response_params_text: '[]',
  success_example_text: '{}',
  error_example_text: '{}',
  doc_markdown: '',
  remark: ''
})

const formatJson = (value, fallback = null) => JSON.stringify(value ?? fallback, null, 2)

const parseJsonField = (text, fieldName) => {
  if (!text || !text.trim()) return null
  try {
    return JSON.parse(text)
  } catch (error) {
    throw new Error(`${fieldName} 格式错误：${error.message}`)
  }
}

const normalizedParams = () => {
  const params = { ...queryParams }
  if (params.status === '') delete params.status
  if (!params.category) delete params.category
  if (!params.keyword) delete params.keyword
  return params
}

const loadInterfaces = async () => {
  loading.value = true
  try {
    const res = await getInterfaces(normalizedParams())
    interfaces.value = res.data.items
    total.value = res.data.total
  } catch (error) {
    console.error('加载接口列表失败:', error)
  } finally {
    loading.value = false
  }
}

const goDocs = (row) => {
  openInterfaceDoc(row.interface_key)
}

const showEdit = (row) => {
  Object.assign(editForm, {
    id: row.id,
    name: row.name,
    interface_key: row.interface_key,
    method: row.method,
    path: row.path,
    category: row.category || 'core',
    description: row.description || '',
    auth_mode: row.auth_mode || 'bearer',
    content_type: row.content_type || 'application/json',
    enabled: row.status === 1,
    request_headers_text: formatJson(row.request_headers, []),
    request_params_text: formatJson(row.request_params, []),
    response_params_text: formatJson(row.response_params, []),
    success_example_text: formatJson(row.success_example, {}),
    error_example_text: formatJson(row.error_example, {}),
    doc_markdown: row.doc_markdown || '',
    remark: row.remark || ''
  })
  editDialogVisible.value = true
}

const handleUpdate = async () => {
  let requestHeaders
  let requestParams
  let responseParams
  let successExample
  let errorExample
  try {
    requestHeaders = parseJsonField(editForm.request_headers_text, '请求头')
    requestParams = parseJsonField(editForm.request_params_text, '请求参数')
    responseParams = parseJsonField(editForm.response_params_text, '返回参数')
    successExample = parseJsonField(editForm.success_example_text, '成功示例')
    errorExample = parseJsonField(editForm.error_example_text, '错误示例')
  } catch (error) {
    ElMessage.error(error.message)
    return
  }

  saving.value = true
  try {
    await updateInterface(editForm.id, {
      name: editForm.name,
      interface_key: editForm.interface_key,
      method: editForm.method,
      path: editForm.path,
      category: editForm.category || 'core',
      description: editForm.description || null,
      auth_mode: editForm.auth_mode || 'bearer',
      content_type: editForm.content_type || 'application/json',
      status: editForm.enabled ? 1 : 0,
      request_headers: requestHeaders || [],
      request_params: requestParams || [],
      response_params: responseParams || [],
      success_example: successExample,
      error_example: errorExample,
      response_example: successExample,
      doc_markdown: editForm.doc_markdown || null,
      remark: editForm.remark || null
    })
    ElMessage.success('接口已更新')
    editDialogVisible.value = false
    await loadInterfaces()
  } catch (error) {
    console.error('更新接口失败:', error)
  } finally {
    saving.value = false
  }
}

onMounted(loadInterfaces)
</script>

<style scoped>
.interface-list {
  height: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.filter-form {
  margin-bottom: 16px;
}

.path-text {
  margin-left: 8px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
}

.pagination {
  margin-top: 20px;
  justify-content: flex-end;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 18px;
}

@media (max-width: 900px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
