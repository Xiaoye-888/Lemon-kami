<template>
  <div class="interface-create">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>新增接口</span>
          <el-button @click="router.push('/interfaces/list')">返回列表</el-button>
        </div>
      </template>

      <el-form :model="form" label-width="120px" class="interface-form">
        <div class="form-grid">
          <el-form-item label="接口名称" required>
            <el-input v-model="form.name" placeholder="例如：查询积分" />
          </el-form-item>
          <el-form-item label="接口标识" required>
            <el-input v-model="form.interface_key" placeholder="例如：points.query" />
          </el-form-item>
          <el-form-item label="请求方法" required>
            <el-select v-model="form.method" style="width: 100%">
              <el-option label="GET" value="GET" />
              <el-option label="POST" value="POST" />
              <el-option label="PUT" value="PUT" />
              <el-option label="DELETE" value="DELETE" />
            </el-select>
          </el-form-item>
          <el-form-item label="接口分类">
            <el-input v-model="form.category" placeholder="user / points / sdk / admin" />
          </el-form-item>
          <el-form-item label="认证方式">
            <el-select v-model="form.auth_mode" style="width: 100%">
              <el-option label="无需认证" value="none" />
              <el-option label="Bearer Token" value="bearer" />
              <el-option label="管理员 Token" value="admin-bearer" />
              <el-option label="SDK 签名" value="sdk-signature" />
              <el-option label="App ID" value="app_id" />
            </el-select>
          </el-form-item>
          <el-form-item label="Content-Type">
            <el-input v-model="form.content_type" />
          </el-form-item>
        </div>

        <el-form-item label="接口地址" required>
          <el-input v-model="form.path" placeholder="/api/v1/user/points/consume" />
        </el-form-item>
        <el-form-item label="接口说明">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="说明接口用途、调用场景和业务影响" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.enabled" active-text="启用" inactive-text="停用" />
        </el-form-item>

        <param-editor title="请求头参数" :rows="form.request_headers" @add="addParam('request_headers')" @remove="removeParam('request_headers', $event)" />
        <param-editor title="请求参数" :rows="form.request_params" @add="addParam('request_params')" @remove="removeParam('request_params', $event)" />
        <param-editor title="返回参数" :rows="form.response_params" @add="addParam('response_params')" @remove="removeParam('response_params', $event)" />

        <div class="example-grid">
          <el-form-item label="成功示例 JSON">
            <el-input v-model="form.success_example_text" type="textarea" :rows="10" />
          </el-form-item>
          <el-form-item label="错误示例 JSON">
            <el-input v-model="form.error_example_text" type="textarea" :rows="10" />
          </el-form-item>
        </div>

        <el-form-item label="接口文档">
          <el-input
            v-model="form.doc_markdown"
            type="textarea"
            :rows="6"
            placeholder="补充调用说明、状态码、注意事项"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="3" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleSubmit">保存接口</el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createInterface } from '../api/interfaces'

const router = useRouter()
const saving = ref(false)

const emptyParam = () => ({
  name: '',
  type: 'string',
  required: false,
  description: '',
  example: ''
})

const initialForm = () => ({
  name: '',
  interface_key: '',
  method: 'POST',
  path: '',
  category: 'core',
  description: '',
  auth_mode: 'bearer',
  content_type: 'application/json',
  enabled: true,
  request_headers: [emptyParam()],
  request_params: [emptyParam()],
  response_params: [emptyParam()],
  success_example_text: '{\n  "success": true,\n  "data": {}\n}',
  error_example_text: '{\n  "success": false,\n  "detail": "请求失败"\n}',
  doc_markdown: '',
  remark: ''
})

const form = reactive(initialForm())

const resetForm = () => {
  Object.assign(form, initialForm())
}

const addParam = (field) => {
  form[field].push(emptyParam())
}

const removeParam = (field, index) => {
  form[field].splice(index, 1)
  if (form[field].length === 0) {
    form[field].push(emptyParam())
  }
}

const cleanRows = (rows) =>
  rows
    .filter((row) => row.name || row.description || row.example)
    .map((row) => ({
      name: row.name,
      type: row.type || 'string',
      required: Boolean(row.required),
      description: row.description || '',
      example: row.example || ''
    }))

const parseJsonField = (text, fieldName) => {
  if (!text || !text.trim()) return null
  try {
    return JSON.parse(text)
  } catch (error) {
    throw new Error(`${fieldName} 格式错误：${error.message}`)
  }
}

const handleSubmit = async () => {
  if (!form.name || !form.interface_key || !form.path) {
    ElMessage.warning('请填写接口名称、接口标识和接口地址')
    return
  }

  let successExample
  let errorExample
  try {
    successExample = parseJsonField(form.success_example_text, '成功示例')
    errorExample = parseJsonField(form.error_example_text, '错误示例')
  } catch (error) {
    ElMessage.error(error.message)
    return
  }

  saving.value = true
  try {
    await createInterface({
      name: form.name,
      interface_key: form.interface_key,
      method: form.method,
      path: form.path,
      category: form.category || 'core',
      description: form.description || null,
      auth_mode: form.auth_mode,
      content_type: form.content_type || 'application/json',
      status: form.enabled ? 1 : 0,
      request_headers: cleanRows(form.request_headers),
      request_params: cleanRows(form.request_params),
      response_params: cleanRows(form.response_params),
      success_example: successExample,
      error_example: errorExample,
      response_example: successExample,
      doc_markdown: form.doc_markdown || null,
      remark: form.remark || null
    })
    ElMessage.success('接口已新增')
    router.push('/interfaces/list')
  } catch (error) {
    console.error('新增接口失败:', error)
  } finally {
    saving.value = false
  }
}
</script>

<script>
export default {
  components: {
    ParamEditor: {
      props: {
        title: { type: String, required: true },
        rows: { type: Array, required: true }
      },
      emits: ['add', 'remove'],
      template: `
        <section class="param-section">
          <div class="section-header">
            <span>{{ title }}</span>
            <el-button size="small" @click="$emit('add')">添加参数</el-button>
          </div>
          <el-table :data="rows" border>
            <el-table-column label="参数名" min-width="150">
              <template #default="{ row }">
                <el-input v-model="row.name" placeholder="name" />
              </template>
            </el-table-column>
            <el-table-column label="类型" width="130">
              <template #default="{ row }">
                <el-select v-model="row.type">
                  <el-option label="string" value="string" />
                  <el-option label="integer" value="integer" />
                  <el-option label="boolean" value="boolean" />
                  <el-option label="object" value="object" />
                  <el-option label="array" value="array" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="必填" width="86" align="center">
              <template #default="{ row }">
                <el-checkbox v-model="row.required" />
              </template>
            </el-table-column>
            <el-table-column label="说明" min-width="220">
              <template #default="{ row }">
                <el-input v-model="row.description" placeholder="字段说明" />
              </template>
            </el-table-column>
            <el-table-column label="示例" min-width="150">
              <template #default="{ row }">
                <el-input v-model="row.example" placeholder="示例值" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="86" align="center">
              <template #default="{ $index }">
                <el-button size="small" type="danger" link @click="$emit('remove', $index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </section>
      `
    }
  }
}
</script>

<style scoped>
.interface-create {
  height: 100%;
}

.card-header,
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.interface-form {
  max-width: 1120px;
}

.form-grid,
.example-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 20px;
}

.param-section {
  margin: 18px 0 24px;
}

.section-header {
  margin-bottom: 10px;
  font-weight: 600;
  color: #334155;
}

@media (max-width: 900px) {
  .form-grid,
  .example-grid {
    grid-template-columns: 1fr;
  }
}
</style>
