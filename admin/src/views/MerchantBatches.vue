<template>
  <div class="kami-batches-page batch-page" data-contract="admin-isomorphic-batch-workbench">
    <template v-if="viewMode === 'list'">
      <section class="yz-admin-panel">
        <div class="yz-panel-header">
          <div class="yz-panel-title">
            <el-icon><Box /></el-icon>
            <span>批次管理</span>
          </div>
          <div class="panel-actions">
            <el-button :icon="Refresh" @click="loadAll">刷新</el-button>
            <el-button v-if="canManageSelectedApp" type="primary" size="large" @click="openSpecDialog()">
              <el-icon><Plus /></el-icon>
              新建规格
            </el-button>
          </div>
        </div>

        <div class="yz-filter-strip">
          <el-select v-model="queryParams.app_id" placeholder="选择应用" class="filter-control" @change="handleAppChange">
            <el-option
              v-for="app in apps"
              :key="app.app_id"
              :label="`${app.name} / ${app.is_owned ? '自建应用' : '授权应用'}`"
              :value="app.app_id"
            />
          </el-select>
          <el-tag v-if="selectedApp" :type="selectedApp.is_owned ? 'success' : 'info'" effect="plain">
            {{ selectedApp.is_owned ? '自建应用可管理' : '授权应用只读' }}
          </el-tag>
          <el-select v-model="queryParams.kami_type" placeholder="全部类型" clearable class="filter-control" @change="handleTypeChange">
            <el-option v-for="item in TYPE_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-input
            v-model="queryParams.keyword"
            placeholder="搜索规格"
            clearable
            class="search-control"
            @keyup.enter="loadSpecs"
            @clear="loadSpecs"
          />
          <el-button type="primary" :icon="Search" @click="loadSpecs">查询</el-button>
          <el-button :icon="Refresh" @click="resetListFilters">重置</el-button>
        </div>

        <el-alert
          v-if="lowBalanceWarning"
          class="quota-warning"
          type="warning"
          :closable="false"
          show-icon
          title="低额度提醒"
          :description="`当前发卡额度 ${issueCardQuota.balance}，低于预警值 ${issueCardQuota.warning_threshold}`"
        />

        <el-empty v-if="!queryParams.app_id" description="请先选择应用" />
        <template v-else>
          <div class="overview-strip">
            <div class="overview-item summary-metric-card">
              <span>规格数</span>
              <strong>{{ specOverview.specs }}</strong>
            </div>
            <div class="overview-item summary-metric-card">
              <span>批次数</span>
              <strong>{{ specOverview.batches }}</strong>
            </div>
            <div class="overview-item summary-metric-card">
              <span>总卡密</span>
              <strong>{{ specOverview.total }}</strong>
            </div>
            <div class="overview-item summary-metric-card">
              <span>可发放</span>
              <strong>{{ specOverview.unused }}</strong>
            </div>
          </div>

          <section class="spec-section">
            <div class="section-title-row">
              <div>
                <h3>常用规格</h3>
                <p>推荐沉淀为常用面额或常用时长，适合高频生成。</p>
              </div>
              <el-tag round>{{ commonSpecs.length }} 个</el-tag>
            </div>
            <el-table :data="commonSpecs" v-loading="loading" class="yz-clean-table" row-key="id">
              <el-table-column type="expand" width="42">
                <template #default="{ row }">
                  <div class="variant-panel">
                    <div class="variant-title">绑定策略版本</div>
                    <el-table :data="row.variants" class="yz-clean-table variant-table" row-key="id">
                      <el-table-column label="绑定策略" min-width="260" show-overflow-tooltip>
                        <template #default="{ row: variant }">{{ getSpecPolicyText(variant) }}</template>
                      </el-table-column>
                      <el-table-column label="批次" width="90">
                        <template #default="{ row: variant }">{{ variant.batch_count || 0 }}</template>
                      </el-table-column>
                      <el-table-column label="卡密有效期" width="140">
                        <template #default="{ row: variant }">{{ getCodeValidityText(variant) }}</template>
                      </el-table-column>
                      <el-table-column label="总数/已用/剩余" min-width="180">
                        <template #default="{ row: variant }">
                          <div class="count-pills">
                            <span class="count-pill is-total">{{ variant.total_count || 0 }}</span>
                            <span>/</span>
                            <span class="count-pill is-used">{{ usedCount(variant) }}</span>
                            <span>/</span>
                            <span class="count-pill is-left">{{ variant.unused_count || 0 }}</span>
                          </div>
                        </template>
                      </el-table-column>
                      <el-table-column label="状态" width="100">
                        <template #default="{ row: variant }">
                          <el-tag :type="variant.status === 1 ? 'success' : 'info'" effect="dark" round>
                            {{ variant.status === 1 ? '启用' : '停用' }}
                          </el-tag>
                        </template>
                      </el-table-column>
                      <el-table-column label="操作" width="300">
                        <template #default="{ row: variant }">
                          <div class="row-actions">
                            <el-tooltip content="生成卡密" placement="top">
                              <el-button size="small" type="primary" plain :icon="Plus" @click="showGenerateDialog(variant)">生成</el-button>
                            </el-tooltip>
                            <el-tooltip content="查看规格" placement="top">
                              <el-button size="small" type="info" plain :icon="View" @click="openSpecGroup(variant)">查看</el-button>
                            </el-tooltip>
                            <el-tooltip :content="variant.is_editable ? '编辑策略' : '授权规格只读'" placement="top">
                              <span class="tooltip-action-wrap">
                                <el-button size="small" plain :icon="EditPen" :disabled="!variant.is_editable" @click="handleEditSpecGroup(variant)">编辑</el-button>
                              </span>
                            </el-tooltip>
                            <el-tooltip :content="canDeleteSpecGroup(variant) ? '删除空规格' : '有批次时不可删除'" placement="top">
                              <span class="tooltip-action-wrap">
                                <el-button size="small" type="danger" plain :icon="Delete" :disabled="!canDeleteSpecGroup(variant)" @click="handleDeleteSpecGroup(variant)">删除</el-button>
                              </span>
                            </el-tooltip>
                          </div>
                        </template>
                      </el-table-column>
                    </el-table>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="规格" min-width="180">
                <template #default="{ row }">
                  <button type="button" class="batch-title-link" @click="openSpecGroup(row)">
                    {{ row.spec_name }}
                  </button>
                </template>
              </el-table-column>
              <el-table-column label="类型" width="130">
                <template #default="{ row }">
                  <span :class="['type-badge', getTypeBadgeClass(row.kami_type)]">
                    {{ getTypeText(row.kami_type) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="策略数" width="90">
                <template #default="{ row }">{{ row.variant_count || 0 }}</template>
              </el-table-column>
              <el-table-column label="批次" width="100">
                <template #default="{ row }">{{ row.batch_count || 0 }}</template>
              </el-table-column>
              <el-table-column label="总数/已用/剩余" min-width="190">
                <template #default="{ row }">
                  <div class="count-pills">
                    <span class="count-pill is-total">{{ row.total_count || 0 }}</span>
                    <span>/</span>
                    <span class="count-pill is-used">{{ usedCount(row) }}</span>
                    <span>/</span>
                    <span class="count-pill is-left">{{ row.unused_count || 0 }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="110">
                <template #default="{ row }">
                  <el-tag :type="row.status === 1 ? 'success' : 'info'" effect="dark" round>
                    {{ row.has_disabled_variants ? '部分启用' : (row.status === 1 ? '启用' : '停用') }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="用途备注" min-width="180" show-overflow-tooltip>
                <template #default="{ row }">{{ getSpecRemarkText(row) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="300" fixed="right">
                <template #default="{ row }">
                  <div class="row-actions">
                    <el-tooltip content="生成卡密" placement="top">
                      <el-button size="small" type="primary" plain :icon="Plus" @click="showGenerateForGroup(row)">生成</el-button>
                    </el-tooltip>
                    <el-tooltip content="查看规格" placement="top">
                      <el-button size="small" type="info" plain :icon="View" @click="openSpecGroup(row)">查看</el-button>
                    </el-tooltip>
                    <el-tooltip :content="canEditSpecGroup(row) ? '编辑默认策略' : '授权规格只读'" placement="top">
                      <span class="tooltip-action-wrap">
                        <el-button size="small" plain :icon="EditPen" :disabled="!canEditSpecGroup(row)" @click="handleEditSpecGroup(row)">编辑</el-button>
                      </span>
                    </el-tooltip>
                    <el-tooltip :content="canDeleteSpecGroup(row) ? '删除空规格' : '有批次时不可删除'" placement="top">
                      <span class="tooltip-action-wrap">
                        <el-button size="small" type="danger" plain :icon="Delete" :disabled="!canDeleteSpecGroup(row)" @click="handleDeleteSpecGroup(row)">删除</el-button>
                      </span>
                    </el-tooltip>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </section>

          <section class="spec-section">
            <div class="section-title-row">
              <div>
                <h3>自定义规格</h3>
                <p>68、143、150 等非固定面额会自动归入这里，同权益和同绑定策略会合并管理。</p>
              </div>
              <div class="section-actions">
                <el-tag round>{{ customSpecs.length }} 个</el-tag>
                <el-button v-if="customSpecs.length > 8" link type="primary" @click="customExpanded = !customExpanded">
                  {{ customExpanded ? '收起' : '展开全部' }}
                </el-button>
              </div>
            </div>
            <el-table :data="visibleCustomSpecs" v-loading="loading" class="yz-clean-table" row-key="id">
              <el-table-column type="expand" width="42">
                <template #default="{ row }">
                  <div class="variant-panel">
                    <div class="variant-title">绑定策略版本</div>
                    <el-table :data="row.variants" class="yz-clean-table variant-table" row-key="id">
                      <el-table-column label="绑定策略" min-width="260" show-overflow-tooltip>
                        <template #default="{ row: variant }">{{ getSpecPolicyText(variant) }}</template>
                      </el-table-column>
                      <el-table-column label="批次" width="90">
                        <template #default="{ row: variant }">{{ variant.batch_count || 0 }}</template>
                      </el-table-column>
                      <el-table-column label="卡密有效期" width="140">
                        <template #default="{ row: variant }">{{ getCodeValidityText(variant) }}</template>
                      </el-table-column>
                      <el-table-column label="总数/已用/剩余" min-width="180">
                        <template #default="{ row: variant }">
                          <div class="count-pills">
                            <span class="count-pill is-total">{{ variant.total_count || 0 }}</span>
                            <span>/</span>
                            <span class="count-pill is-used">{{ usedCount(variant) }}</span>
                            <span>/</span>
                            <span class="count-pill is-left">{{ variant.unused_count || 0 }}</span>
                          </div>
                        </template>
                      </el-table-column>
                      <el-table-column label="状态" width="100">
                        <template #default="{ row: variant }">
                          <el-tag :type="variant.status === 1 ? 'success' : 'info'" effect="dark" round>
                            {{ variant.status === 1 ? '启用' : '停用' }}
                          </el-tag>
                        </template>
                      </el-table-column>
                      <el-table-column label="操作" width="300">
                        <template #default="{ row: variant }">
                          <div class="row-actions">
                            <el-tooltip content="生成卡密" placement="top">
                              <el-button size="small" type="primary" plain :icon="Plus" @click="showGenerateDialog(variant)">生成</el-button>
                            </el-tooltip>
                            <el-tooltip content="查看规格" placement="top">
                              <el-button size="small" type="info" plain :icon="View" @click="openSpecGroup(variant)">查看</el-button>
                            </el-tooltip>
                            <el-tooltip :content="variant.is_editable ? '编辑策略' : '授权规格只读'" placement="top">
                              <span class="tooltip-action-wrap">
                                <el-button size="small" plain :icon="EditPen" :disabled="!variant.is_editable" @click="handleEditSpecGroup(variant)">编辑</el-button>
                              </span>
                            </el-tooltip>
                            <el-tooltip :content="canDeleteSpecGroup(variant) ? '删除空规格' : '有批次时不可删除'" placement="top">
                              <span class="tooltip-action-wrap">
                                <el-button size="small" type="danger" plain :icon="Delete" :disabled="!canDeleteSpecGroup(variant)" @click="handleDeleteSpecGroup(variant)">删除</el-button>
                              </span>
                            </el-tooltip>
                          </div>
                        </template>
                      </el-table-column>
                    </el-table>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="规格" min-width="180">
                <template #default="{ row }">
                  <button type="button" class="batch-title-link" @click="openSpecGroup(row)">
                    {{ row.spec_name }}
                  </button>
                </template>
              </el-table-column>
              <el-table-column label="类型" width="130">
                <template #default="{ row }">
                  <span :class="['type-badge', getTypeBadgeClass(row.kami_type)]">
                    {{ getTypeText(row.kami_type) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="策略数" width="90">
                <template #default="{ row }">{{ row.variant_count || 0 }}</template>
              </el-table-column>
              <el-table-column label="批次" width="100">
                <template #default="{ row }">{{ row.batch_count || 0 }}</template>
              </el-table-column>
              <el-table-column label="总数/已用/剩余" min-width="190">
                <template #default="{ row }">
                  <div class="count-pills">
                    <span class="count-pill is-total">{{ row.total_count || 0 }}</span>
                    <span>/</span>
                    <span class="count-pill is-used">{{ usedCount(row) }}</span>
                    <span>/</span>
                    <span class="count-pill is-left">{{ row.unused_count || 0 }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="110">
                <template #default="{ row }">
                  <el-tag :type="row.status === 1 ? 'success' : 'info'" effect="dark" round>
                    {{ row.has_disabled_variants ? '部分启用' : (row.status === 1 ? '启用' : '停用') }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="用途备注" min-width="180" show-overflow-tooltip>
                <template #default="{ row }">{{ getSpecRemarkText(row) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="300" fixed="right">
                <template #default="{ row }">
                  <div class="row-actions">
                    <el-tooltip content="生成卡密" placement="top">
                      <el-button size="small" type="primary" plain :icon="Plus" @click="showGenerateForGroup(row)">生成</el-button>
                    </el-tooltip>
                    <el-tooltip content="查看规格" placement="top">
                      <el-button size="small" type="info" plain :icon="View" @click="openSpecGroup(row)">查看</el-button>
                    </el-tooltip>
                    <el-tooltip :content="canEditSpecGroup(row) ? '编辑默认策略' : '授权规格只读'" placement="top">
                      <span class="tooltip-action-wrap">
                        <el-button size="small" plain :icon="EditPen" :disabled="!canEditSpecGroup(row)" @click="handleEditSpecGroup(row)">编辑</el-button>
                      </span>
                    </el-tooltip>
                    <el-tooltip :content="canDeleteSpecGroup(row) ? '删除空规格' : '有批次时不可删除'" placement="top">
                      <span class="tooltip-action-wrap">
                        <el-button size="small" type="danger" plain :icon="Delete" :disabled="!canDeleteSpecGroup(row)" @click="handleDeleteSpecGroup(row)">删除</el-button>
                      </span>
                    </el-tooltip>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </section>
        </template>
      </section>
    </template>

    <template v-else>
      <div class="batch-detail-shell">
        <section class="batch-overview-card">
          <div class="batch-overview-main">
            <h2>{{ currentDetailTitle }}</h2>
            <div class="hero-tags">
              <el-tag type="primary" effect="dark" round>{{ getTypeText(currentDetailType) }}</el-tag>
              <el-tag type="info" effect="dark" round>{{ getValidityText(currentDetailTarget) }}</el-tag>
              <el-tag v-if="viewMode === 'spec' && selectedSpec?.is_editable" type="success" effect="dark" round>自建规格可编辑</el-tag>
              <el-tag v-else-if="viewMode === 'spec'" type="info" effect="dark" round>授权规格只读</el-tag>
              <el-tag effect="dark" round>{{ currentDetailTarget?.source === 'self_owned' ? '自建应用' : '授权应用' }}</el-tag>
            </div>
          </div>
          <div class="hero-actions">
            <el-button :icon="ArrowLeft" @click="backFromDetail">{{ viewMode === 'batch' && currentSpec ? '返回规格' : '返回批次管理' }}</el-button>
            <template v-if="viewMode === 'spec'">
              <el-button :icon="EditPen" :disabled="!selectedSpec?.is_editable" @click="handleEditSpecGroup(selectedSpec)">编辑规格</el-button>
              <el-button type="danger" plain :icon="Delete" :disabled="!canDeleteSpecGroup(selectedSpec)" @click="handleDeleteSpecGroup(selectedSpec)">删除规格</el-button>
              <el-button type="primary" :icon="Plus" :disabled="!merchantBatchPermissions.generateBatch" @click="showGenerateForGroup(selectedSpec)">生成卡密</el-button>
            </template>
            <template v-else>
              <el-button :icon="EditPen" :disabled="!currentBatch?.can_edit" @click="showBatchDialog(currentBatch)">编辑批次</el-button>
              <el-button type="danger" plain :icon="Delete" :disabled="!currentBatch?.can_delete" @click="deleteBatch(currentBatch)">删除批次</el-button>
            </template>
          </div>
        </section>

        <section class="summary-metric-card">
          <div class="metric-item">
            <strong class="metric-value is-primary">{{ currentDetailTarget?.total_count || 0 }}</strong>
            <span>总数</span>
          </div>
          <div class="metric-item">
            <strong class="metric-value is-green">{{ currentDetailTarget?.unused_count || 0 }}</strong>
            <span>未使用</span>
          </div>
          <div class="metric-item">
            <strong class="metric-value is-amber">{{ usedCount(currentDetailTarget) }}</strong>
            <span>已使用</span>
          </div>
        </section>
      </div>

      <section class="yz-admin-panel batches-panel">
        <div class="yz-panel-header compact">
          <div class="yz-panel-title">
            <el-icon><Box /></el-icon>
            <span>批次列表</span>
          </div>
          <div class="panel-actions">
            <el-button type="primary" :icon="Plus" :disabled="!merchantBatchPermissions.generateBatch" @click="showGenerateForGroup(selectedSpec)">
              生成新批次
            </el-button>
          </div>
        </div>
        <el-table :data="specBatches" v-loading="loading" class="yz-clean-table" row-key="id">
          <el-table-column label="批次名称" min-width="180">
            <template #default="{ row }">
              <button type="button" class="batch-title-link" @click="openBatchDetail(row)">
                {{ row.batch_no }}
              </button>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="130">
            <template #default="{ row }">
              <span :class="['type-badge', getTypeBadgeClass(row.kami_type)]">{{ getTypeText(row.kami_type) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="权益" width="150">
            <template #default="{ row }">{{ getValidityText(row) }}</template>
          </el-table-column>
          <el-table-column label="剩余权益" min-width="140">
            <template #default="{ row }">{{ getSpecRemainingBenefit(row) }}</template>
          </el-table-column>
          <el-table-column label="卡密有效期" width="140">
            <template #default="{ row }">{{ getCodeValidityText(row) }}</template>
          </el-table-column>
          <el-table-column label="机器码限制" width="180">
            <template #default="{ row }">{{ getMachineBindModeText(row.machine_bind_mode, row.max_bind_devices) }}</template>
          </el-table-column>
          <el-table-column label="总数/已用/剩余" min-width="190">
            <template #default="{ row }">
              <div class="count-pills">
                <span class="count-pill is-total">{{ row.total_count || 0 }}</span>
                <span>/</span>
                <span class="count-pill is-used">{{ usedCount(row) }}</span>
                <span>/</span>
                <span class="count-pill is-left">{{ row.unused_count || 0 }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="row.status === 1 ? 'success' : 'info'" effect="dark" round>
                {{ row.status === 1 ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" width="180">
            <template #default="{ row }">{{ row.created_at ? formatBeijingTime(row.created_at) : '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <div class="icon-actions">
                <el-tooltip content="查看卡密" placement="top">
                  <el-button class="icon-action info" :icon="View" @click="openBatchDetail(row)" />
                </el-tooltip>
                <el-tooltip content="编辑批次" placement="top">
                  <el-button class="icon-action subtle" :icon="EditPen" :disabled="!row.can_edit" @click="showBatchDialog(row)" />
                </el-tooltip>
                <el-tooltip content="删除空批次" placement="top">
                  <el-button class="icon-action danger" :icon="Delete" :disabled="!row.can_delete" @click="deleteBatch(row)" />
                </el-tooltip>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <section class="yz-admin-panel cards-panel">
        <div class="yz-panel-header compact">
          <div class="yz-panel-title">
            <el-icon><Key /></el-icon>
            <span>{{ viewMode === 'spec' ? '规格卡密列表' : '批次卡密列表' }}</span>
          </div>
          <div class="panel-actions">
            <el-button :icon="Download" @click="handleDetailExport">导出</el-button>
            <el-button
              type="danger"
              plain
              :disabled="!merchantBatchPermissions.deleteDetailKamis || selectedDetailKamis.length === 0"
              :title="merchantBatchPermissions.deleteDetailKamis ? '' : '发卡用户无批量删除卡密权限'"
              @click="handleDeleteSelectedDetail"
            >
              删除选中
            </el-button>
            <el-button
              v-if="viewMode === 'batch'"
              type="primary"
              :icon="Plus"
              :disabled="!currentBatch?.can_append"
              @click="showAppendDialog(currentBatch)"
            >
              追加卡密
            </el-button>
          </div>
        </div>

        <div class="yz-filter-strip">
          <el-select
            v-if="viewMode === 'spec'"
            v-model="detailQuery.batch_no"
            placeholder="全部批次"
            clearable
            class="filter-control"
            @change="loadDetailKamis"
          >
            <el-option v-for="batch in specBatches" :key="batch.batch_no" :label="batch.batch_no" :value="batch.batch_no" />
          </el-select>
          <el-select v-model="detailQuery.status" placeholder="全部状态" clearable class="filter-control" @change="loadDetailKamis">
            <el-option label="未使用" value="unused" />
            <el-option label="已使用" value="active" />
            <el-option label="已过期" value="expired" />
            <el-option label="已冻结" value="frozen" />
          </el-select>
          <el-input v-model="detailQuery.keyword" placeholder="搜索卡密/用户" clearable class="search-control" @keyup.enter="loadDetailKamis" />
          <el-button type="primary" :icon="Search" @click="loadDetailKamis" />
          <el-button :icon="Refresh" @click="resetDetailFilters">重置</el-button>
        </div>

        <el-table
          :data="detailKamis"
          v-loading="detailLoading"
          row-key="kami_code"
          class="yz-clean-table detail-table"
          @selection-change="selectedDetailKamis = $event"
        >
          <el-table-column type="selection" width="48" />
          <el-table-column label="卡密" min-width="220">
            <template #default="{ row }">
              <div class="code-cell">
                <span class="mono-text">{{ row.kami_code }}</span>
                <el-tooltip content="复制卡密" placement="top">
                  <el-button :icon="DocumentCopy" size="small" circle @click="copyToClipboard(row.kami_code)" />
                </el-tooltip>
              </div>
            </template>
          </el-table-column>
          <el-table-column v-if="viewMode === 'spec'" label="批次" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">{{ row.batch_no || '-' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="getKamiStatusType(row)" round>{{ getKamiStatusText(row) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="绑定关系" width="120">
            <template #default="{ row }">{{ row.binding_relation || '-' }}</template>
          </el-table-column>
          <el-table-column label="设备策略" width="130">
            <template #default="{ row }">
              {{ row.machine_bind_mode_text || getMachineBindModeText(row.machine_bind_mode, row.max_bind_devices) }}
            </template>
          </el-table-column>
          <el-table-column label="创建时间" width="180">
            <template #default="{ row }">{{ row.created_at ? formatBeijingTime(row.created_at) : '-' }}</template>
          </el-table-column>
          <template v-if="currentDetailType === 'points'">
            <el-table-column label="使用用户" min-width="130">
              <template #default="{ row }">{{ getKamiUserText(row) }}</template>
            </el-table-column>
            <el-table-column label="积分面额" width="120">
              <template #default="{ row }">{{ row.points_amount || 0 }}</template>
            </el-table-column>
            <el-table-column label="已兑换积分" width="130">
              <template #default="{ row }">{{ getPointsRedeemed(row) }}</template>
            </el-table-column>
            <el-table-column label="剩余积分" width="120">
              <template #default="{ row }">{{ getPointsRemaining(row) }}</template>
            </el-table-column>
            <el-table-column label="兑换时间" width="180">
              <template #default="{ row }">{{ formatOptionalTime(row.redeemed_at) }}</template>
            </el-table-column>
            <el-table-column label="有效期" width="120">
              <template #default="{ row }">{{ row.points_valid_days ? `${row.points_valid_days}天` : '永久' }}</template>
            </el-table-column>
          </template>
          <template v-else-if="currentDetailType === 'times'">
            <el-table-column label="使用用户" min-width="130">
              <template #default="{ row }">{{ getKamiUserText(row) }}</template>
            </el-table-column>
            <el-table-column label="绑定设备" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">{{ getBoundDeviceText(row) }}</template>
            </el-table-column>
            <el-table-column label="每卡次数" width="120">
              <template #default="{ row }">{{ row.times_total || 0 }}</template>
            </el-table-column>
            <el-table-column label="已核销次数" width="130">
              <template #default="{ row }">{{ getTimesConsumed(row) }}</template>
            </el-table-column>
            <el-table-column label="剩余次数" width="120">
              <template #default="{ row }">{{ row.times_remaining ?? 0 }}</template>
            </el-table-column>
            <el-table-column label="最近核销时间" width="180">
              <template #default="{ row }">{{ formatOptionalTime(row.last_consume_at) }}</template>
            </el-table-column>
            <el-table-column label="兑换时间" width="180">
              <template #default="{ row }">{{ formatOptionalTime(row.redeemed_at) }}</template>
            </el-table-column>
          </template>
          <template v-else>
            <el-table-column label="使用用户" min-width="130">
              <template #default="{ row }">{{ getKamiUserText(row) }}</template>
            </el-table-column>
            <el-table-column label="有效期" width="180">
              <template #default="{ row }">{{ getTimeCardValidity(row) }}</template>
            </el-table-column>
            <el-table-column label="机器码限制" width="170">
              <template #default="{ row }">
                {{ row.machine_bind_mode_text || getMachineBindModeText(row.machine_bind_mode, row.max_bind_devices) }}
              </template>
            </el-table-column>
            <el-table-column label="绑定设备" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">{{ getBoundDeviceText(row) }}</template>
            </el-table-column>
            <el-table-column label="兑换时间" width="180">
              <template #default="{ row }">{{ formatOptionalTime(row.redeemed_at) }}</template>
            </el-table-column>
          </template>
          <el-table-column label="备注" min-width="160">
            <template #default="{ row }">{{ row.remark || '-' }}</template>
          </el-table-column>
        </el-table>

        <div class="table-footer">
          <span>共 {{ detailTotal }} 条</span>
          <el-pagination
            v-model:current-page="detailQuery.page"
            v-model:page-size="detailQuery.page_size"
            :total="detailTotal"
            :page-sizes="[10, 20, 50, 100]"
            layout="sizes, prev, pager, next"
            @size-change="loadDetailKamis"
            @current-change="loadDetailKamis"
          />
        </div>
      </section>
    </template>

    <el-dialog v-model="specDialogVisible" :title="editingSpec ? '编辑规格' : '新建规格'" width="760px">
      <el-alert
        v-if="editingSpec"
        type="info"
        :closable="false"
        show-icon
        title="编辑模式仅允许调整规格分组、状态、排序和备注；卡密类型、权益规则和绑定策略保持不变。"
      />
      <el-form :model="specForm" label-width="104px" class="spec-form">
        <el-row :gutter="16">
          <el-col :xs="24" :sm="12">
            <el-form-item label="规格分组" required>
              <el-select v-model="specForm.spec_group" :disabled="Boolean(editingSpec)" style="width: 100%">
                <el-option v-for="option in SPEC_GROUP_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="卡密类型" required>
              <el-select v-model="specForm.kami_type" :disabled="Boolean(editingSpec)" style="width: 100%">
                <el-option v-for="option in TYPE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col v-if="specForm.kami_type === 'points'" :xs="24" :sm="12">
            <el-form-item label="积分面额" required>
              <el-input-number
                v-model="specForm.points_amount"
                :min="1"
                :max="100000000"
                :disabled="Boolean(editingSpec)"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col v-if="specForm.kami_type === 'points'" :xs="24" :sm="12">
            <el-form-item label="有效天数">
              <el-input-number
                v-model="specForm.points_valid_days"
                :min="1"
                :max="36500"
                :disabled="Boolean(editingSpec)"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col v-if="specForm.kami_type === 'times'" :xs="24" :sm="12">
            <el-form-item label="次数" required>
              <el-input-number
                v-model="specForm.times_total"
                :min="1"
                :max="100000000"
                :disabled="Boolean(editingSpec)"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col v-if="isTimeCardType(specForm.kami_type) && specForm.kami_type !== 'lifetime'" :xs="24" :sm="12">
            <el-form-item label="时长数值" required>
              <el-input-number
                v-model="specForm.time_value"
                :min="1"
                :max="100000000"
                :disabled="Boolean(editingSpec)"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col v-if="isTimeCardType(specForm.kami_type) && specForm.kami_type !== 'lifetime'" :xs="24" :sm="12">
            <el-form-item label="时长单位" required>
              <el-select v-model="specForm.time_unit" :disabled="Boolean(editingSpec)" style="width: 100%">
                <el-option v-for="option in TIME_UNIT_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="specForm.kami_type === 'lifetime'" :xs="24" :sm="12">
            <el-form-item label="有效期">
              <el-input model-value="永久" disabled />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :xs="24" :sm="12">
            <el-form-item label="绑定策略">
              <el-select v-model="specForm.machine_bind_mode" :disabled="Boolean(editingSpec)" style="width: 100%">
                <el-option v-for="option in MACHINE_BIND_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="specForm.machine_bind_mode === 'one_card_multi_device'" :xs="24" :sm="12">
            <el-form-item label="设备数量">
              <el-input-number
                v-model="specForm.max_bind_devices"
                :min="2"
                :max="1000"
                :disabled="Boolean(editingSpec)"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="授权归属">
              <el-select v-model="specForm.authorization_owner" :disabled="Boolean(editingSpec)" style="width: 100%">
                <el-option
                  v-for="option in AUTHORIZATION_OWNER_OPTIONS"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="用户绑定">
              <el-select v-model="specForm.user_bind_mode" :disabled="Boolean(editingSpec)" style="width: 100%">
                <el-option v-for="option in USER_BIND_MODE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="排序">
              <el-input-number v-model="specForm.sort_order" :min="0" :max="999999" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="状态">
          <el-switch v-model="specForm.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="specForm.remark" type="textarea" :rows="2" maxlength="200" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="specDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingSpec" @click="saveSpec">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="generateDialogVisible" title="按规格生成卡密" width="680px">
      <div v-if="selectedSpec" class="issue-preview">
        <div class="issue-preview__meta">
          <div>本次预计消耗 {{ issuePreview?.total_cost || 0 }} 发卡额度，生成后余额 {{ issuePreview?.balance_after ?? '-' }}</div>
          <div>单张消耗 {{ issuePreview?.unit_cost || '-' }}，规则 {{ pricingLabel(issuePreview?.pricing_source) }}</div>
          <div>单张卡密格式 {{ generateCodePreview }}</div>
        </div>
        <el-tag :type="issuePreview?.can_issue ? 'success' : 'danger'">
          {{ issuePreview?.can_issue ? '额度充足' : '额度不足' }}
        </el-tag>
      </div>
      <el-form :model="generateForm" label-width="96px" class="batch-form">
        <el-form-item label="规格">
          <el-input :model-value="selectedSpec ? `${selectedSpec.spec_name} · ${getValidityText(selectedSpec)}` : '-'" disabled />
        </el-form-item>
        <el-form-item label="批次号">
          <el-input v-model="generateForm.batch_no" placeholder="可留空自动生成" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12">
            <el-form-item label="生成数量">
              <el-input-number v-model="generateForm.count" :min="1" :max="1000" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="卡密前缀">
              <el-input v-model="generateForm.code_prefix" maxlength="32" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12">
            <el-form-item label="随机长度">
              <el-input-number v-model="generateForm.code_length" :min="4" :max="64" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="字符集">
              <el-select v-model="generateForm.charset" style="width: 100%">
                <el-option v-for="option in charsetOptions" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12">
            <el-form-item label="卡密有效期">
              <el-select v-model="generateForm.code_validity_mode" style="width: 100%">
                <el-option label="不限期" value="unlimited" />
                <el-option label="自定义天数" value="custom" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="generateForm.code_validity_mode === 'custom'" :xs="24" :sm="12">
            <el-form-item label="有效天数">
              <el-input-number v-model="generateForm.code_valid_days" :min="1" :max="36500" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="格式预览">
          <el-input :model-value="generateCodePreview" disabled />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="generateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="issuing" :disabled="!canIssue" @click="handleIssue">生成卡密</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="batchDialogVisible" :title="editingBatch ? `编辑批次 - ${editingBatch.batch_no}` : '编辑批次'" width="760px">
      <el-alert
        v-if="editingBatchHasCards"
        type="info"
        :closable="false"
        show-icon
        title="该批次已存在卡密，建议只调整批次编号、状态和备注；权益、生成策略和绑定策略会影响后续追加。"
      />
      <el-form :model="batchForm" label-width="96px" class="batch-form">
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12">
            <el-form-item label="批次号">
              <el-input v-model="batchForm.batch_no" maxlength="64" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="卡密类型">
              <el-select v-model="batchForm.kami_type" :disabled="editingBatchHasCards" style="width: 100%">
                <el-option v-for="option in TYPE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col v-if="batchForm.kami_type === 'points'" :xs="24" :sm="12">
            <el-form-item label="积分面额">
              <el-input-number v-model="batchForm.points_amount" :min="1" :max="100000000" :disabled="editingBatchHasCards" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="batchForm.kami_type === 'points'" :xs="24" :sm="12">
            <el-form-item label="有效天数">
              <el-input-number v-model="batchForm.points_valid_days" :min="1" :max="36500" :disabled="editingBatchHasCards" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="batchForm.kami_type === 'times'" :xs="24" :sm="12">
            <el-form-item label="次数">
              <el-input-number v-model="batchForm.times_total" :min="1" :max="100000000" :disabled="editingBatchHasCards" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="batchForm.kami_type !== 'points' && batchForm.kami_type !== 'times'" :xs="24" :sm="12">
            <el-form-item label="时长数值">
              <el-input-number v-model="batchForm.time_value" :min="1" :max="100000000" :disabled="editingBatchHasCards" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="batchForm.kami_type !== 'points' && batchForm.kami_type !== 'times'" :xs="24" :sm="12">
            <el-form-item label="时长单位">
              <el-select v-model="batchForm.time_unit" :disabled="editingBatchHasCards" style="width: 100%">
                <el-option v-for="option in TIME_UNIT_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12">
            <el-form-item label="卡密前缀">
              <el-input v-model="batchForm.code_prefix" maxlength="32" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="随机长度">
              <el-input-number v-model="batchForm.code_length" :min="4" :max="64" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12">
            <el-form-item label="字符集">
              <el-select v-model="batchForm.charset" style="width: 100%">
                <el-option v-for="option in charsetOptions" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="卡密有效期">
              <el-input-number v-model="batchForm.code_valid_days" :min="1" :max="36500" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12">
            <el-form-item label="绑定策略">
              <el-select v-model="batchForm.machine_bind_mode" :disabled="editingBatchHasCards" style="width: 100%">
                <el-option v-for="option in MACHINE_BIND_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="batchForm.machine_bind_mode === 'one_card_multi_device'" :xs="24" :sm="12">
            <el-form-item label="设备数量">
              <el-input-number v-model="batchForm.max_bind_devices" :min="2" :max="1000" :disabled="editingBatchHasCards" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="授权归属">
              <el-select v-model="batchForm.authorization_owner" :disabled="editingBatchHasCards" style="width: 100%">
                <el-option v-for="option in AUTHORIZATION_OWNER_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="用户绑定">
              <el-select v-model="batchForm.user_bind_mode" :disabled="editingBatchHasCards" style="width: 100%">
                <el-option v-for="option in USER_BIND_MODE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="状态">
          <el-switch v-model="batchForm.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="batchForm.remark" type="textarea" :rows="2" maxlength="200" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingBatch" @click="handleSaveBatch">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="appendDialogVisible" :title="selectedBatch ? `追加卡密 - ${selectedBatch.batch_no}` : '追加卡密'" width="560px">
      <div v-if="selectedBatch" class="issue-preview">
        <div class="issue-preview__meta">
          <div>批次 {{ selectedBatch.batch_no }} · {{ selectedBatch.spec_name || '未绑定规格' }}</div>
          <div>单张消耗发卡额度 {{ issuePreview?.unit_cost || '-' }}，当前批次余额 {{ issueCardQuota.balance }}</div>
          <div>追加后格式预览 {{ appendCodePreview }}</div>
        </div>
      </div>
      <el-form :model="appendForm" label-width="96px" class="batch-form">
        <el-form-item label="追加数量">
          <el-input-number v-model="appendForm.count" :min="1" :max="1000" style="width: 100%" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12">
            <el-form-item label="卡密前缀">
              <el-input v-model="appendForm.code_prefix" maxlength="32" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="随机长度">
              <el-input-number v-model="appendForm.code_length" :min="4" :max="64" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12">
            <el-form-item label="字符集">
              <el-select v-model="appendForm.charset" style="width: 100%">
                <el-option v-for="option in charsetOptions" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="卡密有效期">
              <el-select v-model="appendForm.code_validity_mode" style="width: 100%">
                <el-option label="不限期" value="unlimited" />
                <el-option label="自定义天数" value="custom" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item v-if="appendForm.code_validity_mode === 'custom'" label="有效天数">
          <el-input-number v-model="appendForm.code_valid_days" :min="1" :max="36500" style="width: 100%" />
        </el-form-item>
        <el-form-item label="格式预览">
          <el-input :model-value="appendCodePreview" disabled />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="appendDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="appending" @click="handleAppendKamis">追加卡密</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Box, Delete, DocumentCopy, Download, EditPen, Key, Plus, Refresh, Search, View } from '@element-plus/icons-vue'
import { formatBeijingTime } from '../utils/datetime'
import {
  AUTHORIZATION_OWNER_OPTIONS,
  TYPE_OPTIONS,
  USER_BIND_MODE_OPTIONS,
  getAuthorizationOwnerText,
  getMachineBindModeText,
  getSpecGroupText,
  getStatusText,
  getStatusType,
  getTypeText,
  getUserBindModeText,
  getValidityText,
  isFixedTimeCard
} from '../utils/kamiDisplay'
import { copyTextToClipboard } from '../utils/clipboard'
import {
  createMerchantAppSpec,
  deleteMerchantAppSpec,
  getMerchantAppSpecs,
  getMerchantApps,
  exportMerchantKamis,
  getMerchantBatchKamis,
  getMerchantBatches,
  getMerchantQuotas,
  getMerchantSpecBatches,
  getMerchantSpecKamis,
  issueMerchantKamis,
  previewMerchantKamis,
  appendMerchantBatchKamis,
  deleteMerchantBatch,
  updateMerchantBatch,
  updateMerchantAppSpec
} from '../api/merchant'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const savingSpec = ref(false)
const issuing = ref(false)
const previewLoading = ref(false)
const detailLoading = ref(false)
const apps = ref([])
const specRows = ref([])
const selectedSpec = ref(null)
const specBatches = ref([])
const specKamis = ref({ items: [], total: 0 })
const detailKamis = ref([])
const selectedDetailKamis = ref([])
const detailTotal = ref(0)
const selectedBatch = ref(null)
const viewMode = ref('list')
const activeTab = ref('batches')
const specGroupTab = ref('common')
const customExpanded = ref(false)
const specDialogVisible = ref(false)
const generateDialogVisible = ref(false)
const batchDialogVisible = ref(false)
const appendDialogVisible = ref(false)
const editingSpec = ref(null)
const editingBatch = ref(null)
const savingBatch = ref(false)
const appending = ref(false)
const issuePreview = ref(null)
const issueCardQuota = ref({
  balance: 0,
  warning_threshold: 0,
  low_balance_warning: false
})

const SPEC_GROUP_OPTIONS = [
  { label: '常用规格', value: 'common' },
  { label: '自定义规格', value: 'custom' }
]
const MACHINE_BIND_OPTIONS = [
  { label: '一卡一机', value: 'one_card_one_device' },
  { label: '一卡多机', value: 'one_card_multi_device' },
  { label: '不限制设备', value: 'no_limit' }
]
const TIME_UNIT_OPTIONS = [
  { label: '小时', value: 'hour' },
  { label: '天', value: 'day' },
  { label: '周', value: 'week' },
  { label: '月', value: 'month' },
  { label: '季度', value: 'quarter' },
  { label: '年', value: 'year' }
]
const TIME_CARD_DEFAULTS = {
  hour: { value: 1, unit: 'hour' },
  day: { value: 1, unit: 'day' },
  week: { value: 1, unit: 'week' },
  month: { value: 1, unit: 'month' },
  quarter: { value: 1, unit: 'quarter' },
  year: { value: 1, unit: 'year' },
  lifetime: { value: null, unit: 'lifetime' }
}

const queryParams = reactive({
  app_id: '',
  kami_type: '',
  keyword: ''
})

const detailQuery = reactive({
  batch_no: '',
  status: '',
  keyword: '',
  page: 1,
  page_size: 20
})

const specForm = reactive({
  spec_group: 'custom',
  kami_type: 'points',
  points_amount: 100,
  points_valid_days: null,
  times_total: 10,
  time_value: 1,
  time_unit: 'day',
  machine_bind_mode: 'one_card_one_device',
  max_bind_devices: 2,
  authorization_owner: 'device',
  user_bind_mode: 'none',
  status: 1,
  sort_order: 0,
  remark: ''
})

const generateForm = reactive({
  batch_no: '',
  count: 10,
  code_prefix: '',
  code_length: 16,
  charset: 'upper_numeric',
  code_validity_mode: 'unlimited',
  code_valid_days: 30
})

const batchForm = reactive({
  id: null,
  batch_no: '',
  kami_type: 'points',
  points_amount: null,
  points_valid_days: null,
  times_total: null,
  time_value: null,
  time_unit: 'day',
  code_prefix: '',
  code_length: 16,
  charset: 'upper_numeric',
  code_valid_days: null,
  machine_bind_mode: 'one_card_one_device',
  max_bind_devices: 1,
  authorization_owner: 'device',
  user_bind_mode: 'none',
  status: 1,
  remark: ''
})

const appendForm = reactive({
  count: 10,
  code_prefix: '',
  code_length: 16,
  charset: 'upper_numeric',
  code_validity_mode: 'unlimited',
  code_valid_days: 30
})

const selectedApp = computed(() => apps.value.find((item) => item.app_id === queryParams.app_id))
const canManageSelectedApp = computed(() => selectedApp.value?.is_owned === true)
const lowBalanceWarning = computed(() => issueCardQuota.value.low_balance_warning)
const canIssueInputs = computed(() => Boolean(selectedApp.value?.app_id && selectedSpec.value?.id && generateForm.count > 0))
const canIssue = computed(() => canIssueInputs.value && issuePreview.value?.can_issue !== false)
const specGroups = computed(() => groupMerchantSpecs(specRows.value))
const commonSpecs = computed(() => specGroups.value.filter((row) => row.spec_group === 'common'))
const customSpecs = computed(() => specGroups.value.filter((row) => row.spec_group !== 'common'))
const visibleCustomSpecs = computed(() => (
  customExpanded.value || customSpecs.value.length <= 8 ? customSpecs.value : customSpecs.value.slice(0, 8)
))
const specOverview = computed(() => ({
  specs: specGroups.value.length,
  batches: specGroups.value.reduce((sum, row) => sum + (row.batch_count || 0), 0),
  total: specGroups.value.reduce((sum, row) => sum + (row.total_count || 0), 0),
  unused: specGroups.value.reduce((sum, row) => sum + (row.unused_count || 0), 0)
}))
const currentSpec = computed(() => {
  if (!selectedSpec.value) return null
  return specRows.value.find((item) => item.id === selectedSpec.value.id) || selectedSpec.value
})
const currentBatch = computed(() => {
  if (!selectedBatch.value) return null
  return (
    specBatches.value.find((item) => item.id === selectedBatch.value.id) ||
    specBatches.value.find((item) => item.batch_no === selectedBatch.value.batch_no) ||
    selectedBatch.value
  )
})
const currentDetailTarget = computed(() => (viewMode.value === 'spec' ? currentSpec.value : currentBatch.value))
const currentDetailType = computed(() => currentDetailTarget.value?.kami_type || '')
const currentDetailTitle = computed(() => (
  viewMode.value === 'spec'
    ? currentSpec.value?.spec_name || '-'
    : currentBatch.value?.batch_no || '-'
))
const merchantBatchPermissions = computed(() => ({
  createSpec: canManageSelectedApp.value,
  editSpec: canManageSelectedApp.value,
  deleteSpec: canManageSelectedApp.value,
  editBatch: canManageSelectedApp.value,
  appendBatch: canManageSelectedApp.value,
  deleteBatch: canManageSelectedApp.value,
  generateBatch: Boolean(selectedApp.value?.app_id && selectedSpec.value?.id),
  deleteDetailKamis: false
}))
const editingBatchHasCards = computed(() => (editingBatch.value?.count || 0) > 0)
const charsetOptions = [
  { label: '大写字母 + 数字', value: 'upper_numeric', sample: 'A1' },
  { label: '纯数字', value: 'numeric', sample: '1' },
  { label: '大写字母', value: 'upper', sample: 'A' },
  { label: '字母 + 数字', value: 'lower_mixed', sample: 'a1' }
]
const generateCodePreview = computed(() => buildCodePreview(generateForm))
const appendCodePreview = computed(() => buildCodePreview(appendForm))

function isTimeCardType(type) {
  return Object.prototype.hasOwnProperty.call(TIME_CARD_DEFAULTS, type)
}

function applyTypeDefaults(type) {
  const defaults = TIME_CARD_DEFAULTS[type]
  if (!defaults) return
  specForm.time_value = defaults.value
  specForm.time_unit = defaults.unit
}

function responseItems(res) {
  if (Array.isArray(res.data)) return res.data
  return res.data?.items || res.items || []
}

function responsePayload(res) {
  return res.data?.items ? res.data : { items: res.items || [], total: res.total || 0 }
}

function specValueText(row) {
  if (!row) return '-'
  return getValidityText(row)
}

function getSpecVariants(row) {
  if (!row) return []
  if (Array.isArray(row.variants) && row.variants.length) return row.variants
  return [row]
}

function buildSpecGroupKey(row) {
  return [
    row.app_id || '',
    row.spec_group || '',
    row.kami_type || '',
    row.spec_name || '',
    row.points_amount ?? '',
    row.points_valid_days ?? '',
    row.times_total ?? '',
    row.time_value ?? '',
    row.time_unit ?? '',
    row.source || ''
  ].join('|')
}

function mergeSpecGroupStats(group, row) {
  group.variant_count += 1
  group.batch_count += row.batch_count || 0
  group.total_count += row.total_count || 0
  group.unused_count += row.unused_count || 0
  group.active_count += row.active_count || 0
  group.frozen_count += row.frozen_count || 0
  group.device_bound_count += row.device_bound_count || 0
  group.has_disabled_variants = group.has_disabled_variants || row.status !== 1
  group.status = group.variants.some((variant) => variant.status === 1) ? 1 : 0
  group.is_editable = group.variants.every((variant) => variant.is_editable !== false)
}

function normalizeMerchantSpecRow(row) {
  const variants = getSpecVariants(row).slice().sort((left, right) => {
    const leftSort = Number(left.sort_order || 0)
    const rightSort = Number(right.sort_order || 0)
    if (leftSort !== rightSort) return leftSort - rightSort
    return Number(left.id || 0) - Number(right.id || 0)
  })
  const first = variants[0] || row
  const group = {
    ...first,
    variants,
    variant_count: 0,
    batch_count: 0,
    total_count: 0,
    unused_count: 0,
    active_count: 0,
    frozen_count: 0,
    device_bound_count: 0,
    has_disabled_variants: false,
    is_editable: variants.every((variant) => variant.is_editable !== false),
    source: first?.source || row.source,
    spec_name: first?.spec_name || row.spec_name,
    spec_group: first?.spec_group || row.spec_group,
    kami_type: first?.kami_type || row.kami_type,
  }
  variants.forEach((variant) => mergeSpecGroupStats(group, variant))
  return group
}

function groupMerchantSpecs(rows) {
  const groups = new Map()
  for (const row of rows || []) {
    const normalized = normalizeMerchantSpecRow(row)
    const key = buildSpecGroupKey(normalized)
    if (!groups.has(key)) {
      groups.set(key, normalized)
      continue
    }
    const existing = groups.get(key)
    existing.variants = [...existing.variants, ...normalized.variants]
    existing.variants.sort((left, right) => {
      const leftSort = Number(left.sort_order || 0)
      const rightSort = Number(right.sort_order || 0)
      if (leftSort !== rightSort) return leftSort - rightSort
      return Number(left.id || 0) - Number(right.id || 0)
    })
    mergeSpecGroupStats(existing, normalized.variants[0] || normalized)
  }
  return [...groups.values()].sort((left, right) => {
    const leftSort = Number(left.sort_order || 0)
    const rightSort = Number(right.sort_order || 0)
    if (leftSort !== rightSort) return leftSort - rightSort
    return Number(left.id || 0) - Number(right.id || 0)
  })
}

function getDefaultVariant(row) {
  const variants = getSpecVariants(row)
  if (!variants.length) return null
  if (row?.default_spec_id) {
    return variants.find((item) => item.id === row.default_spec_id) || variants[0] || null
  }
  return variants[0] || null
}

function getSpecPolicyText(row) {
  if (!row) return '-'
  return [
    getMachineBindModeText(row.machine_bind_mode, row.max_bind_devices),
    getAuthorizationOwnerText(row.authorization_owner),
    getUserBindModeText(row.user_bind_mode)
  ].filter(Boolean).join(' / ')
}

function getCodeValidityText(row) {
  if (!row) return '-'
  if (row.code_validity_text) return row.code_validity_text
  return row.code_valid_days ? `生成后 ${row.code_valid_days} 天` : '不限期'
}

function getSpecRemainingBenefit(row) {
  if (!row) return '-'
  if (row.kami_type === 'points') return `${row.points_remaining_total || 0} 积分`
  if (row.kami_type === 'times') return `${row.times_remaining_total || 0} 次`
  return '-'
}

function getSpecRemarkText(row) {
  if (!row) return '-'
  const variants = getSpecVariants(row)
  const remarks = variants.map((item) => item?.remark).filter(Boolean)
  const uniqueRemarks = [...new Set(remarks)]
  if (uniqueRemarks.length === 0) return '-'
  if (uniqueRemarks.length === 1) return uniqueRemarks[0]
  return '多个备注'
}

function getTypeBadgeClass(type) {
  if (type === 'points') return 'is-points'
  if (type === 'times') return 'is-times'
  if (type === 'lifetime') return 'is-lifetime'
  if (isTimeCardType(type)) return 'is-time'
  return 'is-default'
}

function usedCount(row) {
  if (!row) return 0
  if (typeof row.redeemed_count === 'number' && row.redeemed_count > 0) return row.redeemed_count
  if (typeof row.active_count === 'number' && row.active_count > 0) return row.active_count
  return Math.max((row.total_count || 0) - (row.unused_count || 0) - (row.frozen_count || 0) - (row.expired_count || 0), 0)
}

function canEditSpecGroup(row) {
  const variant = getDefaultVariant(row)
  return Boolean(variant?.is_editable)
}

function canDeleteSpecGroup(row) {
  const variants = getSpecVariants(row)
  return variants.length > 0 && variants.every((variant) => variant.is_editable !== false && (variant.batch_count || 0) === 0)
}

function pricingLabel(value) {
  return {
    user_self_app: '用户自建专属',
    global_self_app: '自建应用默认',
    user_authorized_spec: '用户授权规格专属',
    authorized_spec: '授权规格默认',
    global_authorized_app: '授权应用默认',
    default: '系统默认'
  }[value] || value || '系统默认'
}

function buildCodePreview(form) {
  const charset = charsetOptions.find((item) => item.value === form.charset) || charsetOptions[0]
  const length = Number(form.code_length || 0)
  const prefix = form.code_prefix || ''
  const body = charset.sample.repeat(Math.max(Math.ceil(length / charset.sample.length), 1)).slice(0, length)
  return `${prefix}${body || 'A1B2'}`.trim()
}

function batchValidityModeText(row) {
  if (!row) return '-'
  if (row.code_valid_days) return `有效 ${row.code_valid_days} 天`
  return '不限期'
}

function resetBatchForm(row = null) {
  editingBatch.value = row
  batchForm.id = row?.id ?? null
  batchForm.batch_no = row?.batch_no || ''
  batchForm.kami_type = row?.kami_type || selectedSpec.value?.kami_type || 'points'
  batchForm.points_amount = row?.points_amount ?? selectedSpec.value?.points_amount ?? null
  batchForm.points_valid_days = row?.points_valid_days ?? selectedSpec.value?.points_valid_days ?? null
  batchForm.times_total = row?.times_total ?? selectedSpec.value?.times_total ?? null
  batchForm.time_value = row?.time_value ?? selectedSpec.value?.time_value ?? null
  batchForm.time_unit = row?.time_unit || selectedSpec.value?.time_unit || 'day'
  batchForm.code_prefix = row?.code_prefix || ''
  batchForm.code_length = row?.code_length || 16
  batchForm.charset = row?.charset || 'upper_numeric'
  batchForm.code_valid_days = row?.code_valid_days ?? null
  batchForm.machine_bind_mode = row?.machine_bind_mode || selectedSpec.value?.machine_bind_mode || 'one_card_one_device'
  batchForm.max_bind_devices = row?.max_bind_devices ?? selectedSpec.value?.max_bind_devices ?? 1
  batchForm.authorization_owner = row?.authorization_owner || selectedSpec.value?.authorization_owner || 'device'
  batchForm.user_bind_mode = row?.user_bind_mode || selectedSpec.value?.user_bind_mode || 'none'
  batchForm.status = row?.status ?? 1
  batchForm.remark = row?.remark || ''
}

function resetAppendForm(row = null) {
  appendForm.count = 10
  appendForm.code_prefix = row?.code_prefix || ''
  appendForm.code_length = row?.code_length || 16
  appendForm.charset = row?.charset || 'upper_numeric'
  appendForm.code_validity_mode = row?.code_valid_days ? 'custom' : 'unlimited'
  appendForm.code_valid_days = row?.code_valid_days || 30
}

function batchPayloadFromForm() {
  return {
    batch_no: batchForm.batch_no || null,
    kami_type: batchForm.kami_type,
    points_amount: batchForm.kami_type === 'points' ? batchForm.points_amount : null,
    points_valid_days: batchForm.kami_type === 'points' ? batchForm.points_valid_days || null : null,
    times_total: batchForm.kami_type === 'times' ? batchForm.times_total : null,
    time_value: isTimeCardType(batchForm.kami_type) ? batchForm.time_value : null,
    time_unit: isTimeCardType(batchForm.kami_type) ? batchForm.time_unit : null,
    code_prefix: batchForm.code_prefix || null,
    code_length: batchForm.code_length,
    charset: batchForm.charset,
    code_valid_days: batchForm.code_valid_days || null,
    machine_bind_mode: batchForm.machine_bind_mode,
    max_bind_devices: batchForm.max_bind_devices,
    authorization_owner: batchForm.authorization_owner,
    user_bind_mode: batchForm.user_bind_mode,
    status: batchForm.status,
    remark: batchForm.remark || null
  }
}

function appendPayloadFromForm() {
  return {
    count: appendForm.count,
    code_prefix: appendForm.code_prefix || null,
    code_length: appendForm.code_length,
    charset: appendForm.charset,
    code_valid_days: appendForm.code_validity_mode === 'custom' ? appendForm.code_valid_days : null
  }
}

function resetSpecForm(row = null) {
  editingSpec.value = row
  specForm.spec_group = row?.spec_group || 'custom'
  specForm.kami_type = row?.kami_type || 'points'
  specForm.points_amount = row?.points_amount || 100
  specForm.points_valid_days = row?.points_valid_days || null
  specForm.times_total = row?.times_total || 10
  specForm.time_value = row?.time_value || 1
  specForm.time_unit = row?.time_unit || 'day'
  specForm.machine_bind_mode = row?.machine_bind_mode || 'one_card_one_device'
  specForm.max_bind_devices = row?.max_bind_devices || 2
  specForm.authorization_owner = row?.authorization_owner || 'device'
  specForm.user_bind_mode = row?.user_bind_mode || 'none'
  specForm.status = row?.status ?? 1
  specForm.sort_order = row?.sort_order || 0
  specForm.remark = row?.remark || ''
  if (!row) {
    applyTypeDefaults(specForm.kami_type)
  }
}

function specPayload() {
  const payload = {
    spec_group: specForm.spec_group,
    kami_type: specForm.kami_type,
    machine_bind_mode: specForm.machine_bind_mode,
    max_bind_devices: specForm.max_bind_devices,
    authorization_owner: specForm.authorization_owner,
    user_bind_mode: specForm.user_bind_mode,
    status: specForm.status,
    sort_order: specForm.sort_order,
    remark: specForm.remark || null
  }
  if (specForm.kami_type === 'points') {
    payload.points_amount = specForm.points_amount
    payload.points_valid_days = specForm.points_valid_days || null
  }
  if (specForm.kami_type === 'times') {
    payload.times_total = specForm.times_total
  }
  if (isTimeCardType(specForm.kami_type)) {
    payload.time_value = specForm.time_value
    payload.time_unit = specForm.time_unit
  }
  return payload
}

function buildIssuePayload() {
  return {
    spec_id: selectedSpec.value?.id,
    count: generateForm.count,
    batch_no: generateForm.batch_no || null,
    code_prefix: generateForm.code_prefix || null,
    code_length: generateForm.code_length,
    charset: generateForm.charset,
    code_valid_days: generateForm.code_validity_mode === 'custom' ? generateForm.code_valid_days : null
  }
}

async function loadApps() {
  const res = await getMerchantApps()
  apps.value = responseItems(res)
  const routeAppId = route.query.app_id ? String(route.query.app_id) : ''
  if (routeAppId) {
    queryParams.app_id = routeAppId
  } else if (!queryParams.app_id && apps.value.length) {
    queryParams.app_id = apps.value[0].app_id
  }
}

async function hydrateRouteDetail() {
  if (!queryParams.app_id || viewMode.value !== 'list') return
  const routeSpecId = route.query.spec_id ? Number(route.query.spec_id) : null
  if (routeSpecId) {
    const spec = specRows.value.find((item) => item.id === routeSpecId)
    if (spec) {
      await openSpecGroup(spec, false)
    }
    return
  }
  if (route.query.batch_no) {
    const batch = await findBatchByNo(String(route.query.batch_no))
    if (batch) await openBatchDetail(batch, false)
  }
}

function findRouteGenerateTarget() {
  const routeSpecId = route.query.spec_id ? Number(route.query.spec_id) : null
  const groups = [...commonSpecs.value, ...customSpecs.value]
  if (routeSpecId) {
    return groups.find((group) => getSpecVariants(group).some((variant) => variant.id === routeSpecId)) || null
  }
  return groups.find((group) => Boolean(getDefaultVariant(group))) || null
}

async function hydrateRouteAction() {
  if (route.query.action !== 'generate' || !queryParams.app_id || viewMode.value !== 'list') return
  const target = findRouteGenerateTarget()
  if (!target) {
    ElMessage.warning('当前应用暂无可生成卡密的规格')
  } else {
    await showGenerateForGroup(target)
  }
  const { action, ...nextQuery } = route.query
  router.replace({ path: '/merchant/batches', query: { ...nextQuery, app_id: queryParams.app_id } })
}

async function findBatchByNo(batchNo) {
  const res = await getMerchantBatches(queryParams.app_id)
  const batches = responseItems(res)
  const batch = batches.find((item) => item.batch_no === batchNo)
  const spec = batch?.spec_id ? specRows.value.find((item) => item.id === batch.spec_id) : null
  if (spec) {
    selectedSpec.value = spec
    await loadSpecBatches()
  }
  return batch
}

async function loadQuota() {
  const res = await getMerchantQuotas()
  issueCardQuota.value = res.data?.issue_card || {
    balance: res.data?.kami_issue_balance || 0,
    warning_threshold: 0,
    low_balance_warning: false
  }
}

async function loadSpecs() {
  specRows.value = []
  if (!queryParams.app_id) return
  const params = {}
  if (queryParams.kami_type) params.kami_type = queryParams.kami_type
  if (queryParams.keyword.trim()) params.keyword = queryParams.keyword.trim()
  const res = await getMerchantAppSpecs(queryParams.app_id, params)
  specRows.value = responseItems(res)
  if (viewMode.value === 'list') {
    selectedSpec.value = null
    specBatches.value = []
    specKamis.value = { items: [], total: 0 }
    detailKamis.value = []
    detailTotal.value = 0
    selectedDetailKamis.value = []
  } else if (selectedSpec.value) {
    const next = specRows.value.find((item) => item.id === selectedSpec.value.id)
    if (next) {
      selectedSpec.value = next
      await Promise.all([loadSpecBatches(), loadDetailKamis(), loadIssuePreview()])
    }
  }
}

async function loadSpecBatches() {
  if (!selectedSpec.value?.id) {
    specBatches.value = []
    return
  }
  const res = await getMerchantSpecBatches(selectedSpec.value.id)
  specBatches.value = responseItems(res)
}

function resetDetailState() {
  detailQuery.batch_no = ''
  detailQuery.status = ''
  detailQuery.keyword = ''
  detailQuery.page = 1
  detailQuery.page_size = 20
  selectedDetailKamis.value = []
}

async function loadDetailKamis() {
  if (!currentDetailTarget.value) {
    detailKamis.value = []
    detailTotal.value = 0
    return
  }
  detailLoading.value = true
  try {
    const params = {
      page: detailQuery.page,
      page_size: detailQuery.page_size
    }
    if (detailQuery.batch_no) params.batch_no = detailQuery.batch_no
    if (detailQuery.status) params.status = detailQuery.status
    if (detailQuery.keyword.trim()) params.keyword = detailQuery.keyword.trim()
    const res = viewMode.value === 'batch'
      ? await getMerchantBatchKamis(selectedBatch.value.id, params)
      : await getMerchantSpecKamis(selectedSpec.value.id, params)
    const payload = responsePayload(res)
    detailKamis.value = payload.items || []
    detailTotal.value = payload.total || 0
    selectedDetailKamis.value = []
  } finally {
    detailLoading.value = false
  }
}

async function loadSpecKamis() {
  return loadDetailKamis()
}

async function resetDetailFilters() {
  resetDetailState()
  await loadDetailKamis()
}

async function loadIssuePreview() {
  if (!canIssueInputs.value) {
    issuePreview.value = null
    return
  }
  previewLoading.value = true
  try {
    const res = await previewMerchantKamis(queryParams.app_id, buildIssuePayload())
    issuePreview.value = res.data || null
  } catch (error) {
    issuePreview.value = null
  } finally {
    previewLoading.value = false
  }
}

async function loadQuotaSafely() {
  try {
    await loadQuota()
  } catch (error) {
    issueCardQuota.value = {
      balance: 0,
      warning_threshold: 0,
      low_balance_warning: false
    }
  }
}

async function loadAll() {
  loading.value = true
  try {
    const routeAppId = route.query.app_id ? String(route.query.app_id) : ''
    if (routeAppId) {
      queryParams.app_id = routeAppId
    }
    await Promise.all([loadQuotaSafely(), loadApps()])
    if (routeAppId) {
      queryParams.app_id = routeAppId
    }
    await loadSpecs()
    await hydrateRouteAction()
    await hydrateRouteDetail()
  } finally {
    loading.value = false
  }
}

async function handleAppChange() {
  viewMode.value = 'list'
  selectedSpec.value = null
  selectedBatch.value = null
  customExpanded.value = false
  specBatches.value = []
  specKamis.value = { items: [], total: 0 }
  detailKamis.value = []
  detailTotal.value = 0
  selectedDetailKamis.value = []
  resetDetailState()
  router.replace({ path: '/merchant/batches', query: queryParams.app_id ? { app_id: queryParams.app_id } : {} })
  await loadSpecs()
}

async function handleTypeChange() {
  customExpanded.value = false
  await loadSpecs()
}

async function resetListFilters() {
  queryParams.kami_type = ''
  queryParams.keyword = ''
  customExpanded.value = false
  if (viewMode.value === 'spec') {
    await backFromDetail()
    return
  }
  await loadSpecs()
}

async function selectSpec(row) {
  selectedSpec.value = row
  specGroupTab.value = row?.spec_group === 'common' ? 'common' : 'custom'
  activeTab.value = 'batches'
  await Promise.all([loadSpecBatches(), loadDetailKamis(), loadIssuePreview()])
}

async function openSpecGroup(row, updateRoute = true) {
  const variant = getDefaultVariant(row)
  if (!variant) {
    ElMessage.warning('该规格暂无可查看的绑定策略')
    return
  }
  viewMode.value = 'spec'
  resetDetailState()
  await selectSpec(variant)
  if (updateRoute) {
    router.replace({ path: '/merchant/batches', query: { app_id: queryParams.app_id, spec_id: variant.id } })
  }
}

function openSpecDialog(row = null) {
  if (!selectedApp.value?.is_owned) return
  resetSpecForm(row)
  specDialogVisible.value = true
}

function handleEditSpecGroup(row) {
  const variant = getDefaultVariant(row)
  if (!variant) {
    ElMessage.warning('该规格暂无可编辑的绑定策略')
    return
  }
  if (!variant.is_editable) {
    ElMessage.warning('授权规格只读')
    return
  }
  openSpecDialog(variant)
}

async function handleDeleteSpecGroup(row) {
  const variants = getSpecVariants(row)
  if (!variants.length) {
    ElMessage.warning('该规格暂无可删除的绑定策略')
    return
  }
  if (!canDeleteSpecGroup(row)) {
    ElMessage.warning('有批次时不可删除')
    return
  }
  await ElMessageBox.confirm(`确认删除规格「${row.spec_name}」吗？该规格下没有批次，将同时删除 ${variants.length} 个空绑定策略。`, '删除规格', {
    type: 'warning'
  })
  for (const variant of variants) {
    await deleteMerchantAppSpec(variant.app_id, variant.id)
  }
  ElMessage.success('规格已删除')
  if (viewMode.value === 'spec' && selectedSpec.value && variants.some((variant) => variant.id === selectedSpec.value.id)) {
    await backFromDetail()
    return
  }
  await loadSpecs()
}

async function saveSpec() {
  if (!selectedApp.value?.app_id) return
  savingSpec.value = true
  try {
    if (editingSpec.value?.id) {
      await updateMerchantAppSpec(selectedApp.value.app_id, editingSpec.value.id, specPayload())
      ElMessage.success('规格已更新')
    } else {
      await createMerchantAppSpec(selectedApp.value.app_id, specPayload())
      ElMessage.success('规格已创建')
    }
    specDialogVisible.value = false
    await loadSpecs()
  } finally {
    savingSpec.value = false
  }
}

async function deleteSpec(row) {
  await ElMessageBox.confirm('确认删除该空规格？', '删除规格', { type: 'warning' })
  await deleteMerchantAppSpec(row.app_id, row.id)
  ElMessage.success('规格已删除')
  await loadSpecs()
}

async function openGenerateDialog(row) {
  const variant = getDefaultVariant(row)
  if (!variant) {
    ElMessage.warning('该规格暂无可生成的绑定策略')
    return
  }
  await selectSpec(variant)
  generateForm.batch_no = ''
  generateForm.count = 10
  generateForm.code_prefix = ''
  generateForm.code_length = 16
  generateForm.charset = 'upper_numeric'
  generateForm.code_validity_mode = 'unlimited'
  generateForm.code_valid_days = 30
  generateDialogVisible.value = true
  await loadIssuePreview()
}

function showGenerateDialog(row) {
  return openGenerateDialog(row)
}

async function showGenerateForGroup(row) {
  const variant = getDefaultVariant(row)
  if (!variant) {
    ElMessage.warning('该规格暂无可生成的绑定策略')
    return
  }
  await openGenerateDialog(variant)
}

const handleDetailExport = async () => {
  if (!currentDetailTarget.value?.app_id) return
  const params = {
    app_id: currentDetailTarget.value.app_id
  }
  if (viewMode.value === 'batch') {
    params.batch_no = currentBatch.value?.batch_no
  } else {
    params.spec_id = selectedSpec.value.id
    if (detailQuery.batch_no) params.batch_no = detailQuery.batch_no
  }
  if (detailQuery.status) params.status = detailQuery.status
  if (detailQuery.keyword.trim()) params.keyword = detailQuery.keyword.trim()
  const response = await exportMerchantKamis(params)
  const suffix = viewMode.value === 'batch' ? `batch-${currentBatch.value?.batch_no || 'detail'}` : `spec-${selectedSpec.value.id}`
  downloadBlob(response, `merchant-kamis-${currentDetailTarget.value.app_id}-${suffix}.csv`)
}

const handleDeleteSelectedDetail = async () => {
  if (!merchantBatchPermissions.value.deleteDetailKamis) {
    ElMessage.warning('发卡用户无批量删除卡密权限')
    return
  }
  if (selectedDetailKamis.value.length === 0) return
}

function downloadBlob(response, filename) {
  const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

async function copyToClipboard(text) {
  try {
    await copyTextToClipboard(text)
    ElMessage.success('复制成功')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

function formatOptionalTime(value) {
  return value ? formatBeijingTime(value) : '-'
}

function isKamiExpired(row) {
  return row?.is_code_expired || row?.display_status === 'expired'
}

function getKamiStatusText(row) {
  return isKamiExpired(row) ? '已过期' : getStatusText(row?.status)
}

function getKamiStatusType(row) {
  return isKamiExpired(row) ? 'warning' : getStatusType(row?.status)
}

function getKamiUserText(row) {
  return (
    row?.redeemed_user?.username ||
    row?.redeemed_user?.email ||
    row?.redeemed_by_user_id ||
    '-'
  )
}

function getPointsRemaining(row) {
  return row?.point_source_remaining ?? row?.points_remaining ?? row?.point_remaining_balance ?? row?.points_amount ?? 0
}

function getPointsRedeemed(row) {
  return row?.point_source_redeemed ?? row?.points_redeemed ?? Math.max((row?.points_amount || 0) - getPointsRemaining(row), 0)
}

function getTimesConsumed(row) {
  return Math.max((row?.times_total || 0) - (row?.times_remaining ?? 0), 0)
}

function isUserIdentityBindValue(value) {
  if (!value || typeof value !== 'string') return false
  const normalized = value.trim().toLowerCase()
  return normalized.startsWith('user:') || normalized.startsWith('username:')
}

function getBoundDeviceText(row) {
  const devices = Array.isArray(row?.bound_device_uuids) ? row.bound_device_uuids.filter(Boolean) : []
  if (devices.length === 1) return devices[0]
  if (devices.length > 1) return `${devices.length}台设备`
  if (row?.bind_uuid && !isUserIdentityBindValue(row.bind_uuid)) return row.bind_uuid
  if (row?.device_bind_count) return `${row.device_bind_count}台设备`
  return '-'
}

function getTimeCardValidity(row) {
  if (row?.expire_time) return formatBeijingTime(row.expire_time)
  if (row?.code_expire_time) return formatBeijingTime(row.code_expire_time)
  if (row?.code_valid_days) return `有效期 ${row.code_valid_days} 天`
  if (isFixedTimeCard(row?.kami_type)) return getValidityText(row)
  return getValidityText(row)
}

async function backFromDetail() {
  if (viewMode.value === 'batch' && currentSpec.value) {
    await openSpecGroup(currentSpec.value)
    return
  }
  viewMode.value = 'list'
  selectedSpec.value = null
  selectedBatch.value = null
  specBatches.value = []
  specKamis.value = { items: [], total: 0 }
  detailKamis.value = []
  detailTotal.value = 0
  selectedDetailKamis.value = []
  resetDetailState()
  activeTab.value = 'batches'
  router.replace({ path: '/merchant/batches', query: queryParams.app_id ? { app_id: queryParams.app_id } : {} })
  await loadSpecs()
}

async function handleIssue() {
  if (issuePreview.value?.can_issue === false) {
    ElMessage.error('发卡额度不足')
    return
  }
  issuing.value = true
  try {
    const res = await issueMerchantKamis(queryParams.app_id, buildIssuePayload())
    ElMessage.success(`已生成 ${res.data.count} 个卡密`)
    generateDialogVisible.value = false
    await Promise.all([loadQuota(), loadSpecs()])
  } finally {
    issuing.value = false
  }
}

async function openBatchDetail(row, updateRoute = true) {
  if (!row) return
  selectedBatch.value = row
  const spec = row.spec_id ? specRows.value.find((item) => item.id === row.spec_id) : null
  if (spec) {
    selectedSpec.value = spec
    if (!specBatches.value.some((item) => item.id === row.id || item.batch_no === row.batch_no)) {
      await loadSpecBatches()
    }
  }
  viewMode.value = 'batch'
  resetDetailState()
  if (updateRoute) {
    router.replace({ path: '/merchant/batches', query: { app_id: queryParams.app_id, batch_no: row.batch_no } })
  }
  await loadDetailKamis()
}

function showBatchDialog(row) {
  if (!row?.can_manage) return
  selectedBatch.value = row
  resetBatchForm(row)
  batchDialogVisible.value = true
}

async function handleSaveBatch() {
  if (!selectedBatch.value?.id) return
  const specId = selectedSpec.value?.id
  savingBatch.value = true
  try {
    await updateMerchantBatch(selectedBatch.value.id, batchPayloadFromForm())
    ElMessage.success('批次已保存')
    batchDialogVisible.value = false
    await loadSpecs()
    const nextSpec = specId ? specRows.value.find((item) => item.id === specId) : null
    if (nextSpec) {
      await selectSpec(nextSpec)
    }
  } finally {
    savingBatch.value = false
  }
}

function showAppendDialog(row) {
  if (!row?.can_append) return
  selectedBatch.value = row
  resetAppendForm(row)
  appendDialogVisible.value = true
}

async function handleAppendKamis() {
  if (!selectedBatch.value?.id) return
  const specId = selectedSpec.value?.id
  appending.value = true
  try {
    await appendMerchantBatchKamis(selectedBatch.value.id, appendPayloadFromForm())
    ElMessage.success('卡密已追加')
    appendDialogVisible.value = false
    await Promise.all([loadQuota(), loadSpecs()])
    const nextSpec = specId ? specRows.value.find((item) => item.id === specId) : null
    if (nextSpec) {
      await selectSpec(nextSpec)
    }
  } finally {
    appending.value = false
  }
}

async function deleteBatch(row) {
  if (!row?.can_manage) return
  if ((row.count || 0) > 0) {
    ElMessage.warning('请先清空批次中的卡密后再删除')
    return
  }
  const specId = selectedSpec.value?.id
  await ElMessageBox.confirm('确认删除该批次？', '删除批次', { type: 'warning' })
  await deleteMerchantBatch(row.id)
  ElMessage.success('批次已删除')
  await loadSpecs()
  const nextSpec = specId ? specRows.value.find((item) => item.id === specId) : null
  if (nextSpec) {
    await selectSpec(nextSpec)
  }
}

watch(
  () => specForm.kami_type,
  (value) => {
    applyTypeDefaults(value)
  }
)

watch(
  () => [
    generateForm.count,
    generateForm.code_prefix,
    generateForm.code_length,
    generateForm.charset,
    generateForm.code_validity_mode,
    generateForm.code_valid_days,
    selectedSpec.value?.id
  ],
  loadIssuePreview
)

onMounted(loadAll)
</script>

<style scoped>
.kami-batches-page {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.kami-batches-page :deep(.el-button--primary:not(.is-plain)) {
  background: #2f80ed !important;
  border-color: #2f80ed !important;
}

.kami-batches-page :deep(.el-button--primary:not(.is-plain):hover) {
  background: #1d4ed8 !important;
  border-color: #1d4ed8 !important;
}

.yz-admin-panel,
.batch-overview-card,
.summary-metric-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
}

.yz-panel-header {
  min-height: 84px;
  padding: 22px 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.yz-panel-header.compact {
  min-height: 70px;
  padding: 18px 22px;
}

.yz-panel-title {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: #0f172a;
  font-size: 24px;
  font-weight: 700;
}

.yz-panel-header.compact .yz-panel-title {
  font-size: 20px;
}

.panel-actions,
.section-actions,
.hero-actions,
.hero-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.icon-actions {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  flex-wrap: nowrap;
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: nowrap;
}

.row-actions :deep(.el-button) {
  margin-left: 0;
  border-radius: 8px;
  font-weight: 600;
}

.icon-action {
  width: 36px;
  height: 36px;
  padding: 0;
  border-color: #2563eb;
  color: #2563eb;
}

.icon-action.info {
  border-color: #06b6d4;
  color: #0891b2;
}

.icon-action.subtle {
  border-color: #94a3b8;
  color: #475569;
}

.icon-action.danger {
  border-color: #ef4444;
  color: #ef4444;
}

.yz-filter-strip {
  padding: 18px 28px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  background: #f8fafc;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.filter-control {
  width: 210px;
}

.search-control {
  width: 280px;
}

.quota-warning {
  border-radius: 8px;
}

.overview-strip {
  padding: 18px 28px 6px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.overview-item.summary-metric-card {
  min-height: 88px;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: linear-gradient(135deg, #f8fbff 0%, #ffffff 100%);
}

.overview-item span {
  color: #64748b;
  font-size: 14px;
}

.overview-item strong {
  color: #0f172a;
  font-size: 28px;
  line-height: 1;
}

.summary-metric-card {
  min-height: 150px;
  padding: 30px 34px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  align-items: center;
  text-align: center;
  gap: 10px;
}

.summary-metric-card .metric-item {
  display: flex;
  flex-direction: column;
  gap: 10px;
  color: #475569;
}

.metric-item span {
  display: block;
}

.metric-value {
  display: block;
  font-size: 34px;
  font-weight: 800;
  line-height: 1;
  color: #0f172a;
}

.metric-value.is-primary {
  color: #2563eb;
}

.metric-value.is-green {
  color: #059669;
}

.metric-value.is-amber {
  color: #f59e0b;
}

.spec-section {
  padding: 20px 28px 10px;
}

.spec-section + .spec-section {
  padding-top: 10px;
  padding-bottom: 28px;
}

.section-title-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.section-title-row h3 {
  margin: 0;
  color: #0f172a;
  font-size: 20px;
}

.section-title-row p {
  margin: 6px 0 0;
  color: #64748b;
}

.variant-panel {
  padding: 10px 0;
}

.variant-title {
  margin-bottom: 8px;
  color: #334155;
  font-weight: 600;
}

.stat-inline {
  margin-left: 10px;
}

.subtext {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.4;
}

.count-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.count-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: #eef2ff;
  color: #334155;
  font-size: 12px;
}

.count-pill.is-total {
  background: #dbeafe;
  color: #1d4ed8;
}

.count-pill.is-used {
  background: #fef3c7;
  color: #b45309;
}

.count-pill.is-left {
  background: #dcfce7;
  color: #15803d;
}

.batch-title-link {
  padding: 0;
  border: 0;
  background: transparent;
  color: #2563eb;
  font: inherit;
  cursor: pointer;
}

.type-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 999px;
  border: 1px solid transparent;
  font-size: 12px;
}

.type-badge.is-points {
  background: #fff7ed;
  border-color: #fdba74;
  color: #c2410c;
}

.type-badge.is-times {
  background: #eff6ff;
  border-color: #93c5fd;
  color: #1d4ed8;
}

.type-badge.is-time {
  background: #f0fdf4;
  border-color: #86efac;
  color: #15803d;
}

.type-badge.is-lifetime,
.type-badge.is-default {
  background: #f8fafc;
  border-color: #cbd5e1;
  color: #334155;
}

.tooltip-action-wrap {
  display: inline-flex;
}

.code-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.mono-text {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  word-break: break-all;
}

.detail-table {
  min-height: 360px;
}

.table-footer {
  min-height: 72px;
  padding: 16px 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
  color: #475569;
}

.spec-form,
.batch-form {
  margin-top: 12px;
}

.issue-preview {
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fafc;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: #334155;
  font-size: 13px;
}

.issue-preview__meta {
  display: grid;
  gap: 4px;
}

.batch-detail-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: 24px;
  margin-bottom: 24px;
}

.batch-overview-card {
  min-height: 150px;
  padding: 30px 36px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.batch-overview-main h2 {
  margin: 8px 0 14px;
  color: #0f172a;
  font-size: 30px;
  line-height: 1.2;
}

.hero-tags {
  margin-top: 10px;
}

.hero-actions {
  justify-content: flex-end;
  flex-wrap: nowrap;
}

.hero-actions :deep(.el-button) {
  white-space: nowrap;
}

.batches-panel,
.cards-panel {
  overflow: hidden;
}

.cards-panel :deep(.el-empty) {
  min-height: 420px;
}

.el-table :deep(.cell) {
  line-height: 1.45;
}

@media (max-width: 1180px) {
  .overview-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .batch-detail-shell {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 960px) {
  .hero-actions,
  .panel-actions {
    justify-content: flex-start;
  }

  .hero-actions {
    flex-wrap: wrap;
  }
}

@media (max-width: 720px) {
  .overview-strip {
    grid-template-columns: 1fr;
  }

  .batch-overview-card {
    flex-direction: column;
    align-items: flex-start;
  }

  .summary-metric-card {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    padding: 24px 16px;
  }

  .issue-preview {
    flex-direction: column;
    align-items: flex-start;
  }

  .table-footer {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
