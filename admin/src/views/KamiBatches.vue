<template>
  <div class="kami-batches-page">
    <template v-if="viewMode === 'list'">
      <section class="yz-admin-panel">
        <div class="yz-panel-header">
          <div class="yz-panel-title">
            <el-icon><Box /></el-icon>
            <span>批次管理</span>
          </div>
          <div class="panel-actions">
            <el-button :icon="Refresh" @click="loadSpecs">刷新</el-button>
            <el-button type="primary" size="large" @click="showCreateSpecDialog">
              <el-icon><Plus /></el-icon>
              新建规格
            </el-button>
          </div>
        </div>

        <div class="yz-filter-strip">
          <el-select v-model="queryParams.app_id" placeholder="选择应用" class="filter-control" @change="handleAppChange">
            <el-option v-for="app in apps" :key="app.app_id" :label="app.name" :value="app.app_id" />
          </el-select>
          <el-select v-model="queryParams.kami_type" placeholder="全部类型" clearable class="filter-control" @change="handleTypeChange">
            <el-option v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" />
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

        <el-empty v-if="!queryParams.app_id" description="请先选择应用" />
        <template v-else>
          <div class="overview-strip">
            <div class="overview-item">
              <span>规格数</span>
              <strong>{{ specOverview.specs }}</strong>
            </div>
            <div class="overview-item">
              <span>批次数</span>
              <strong>{{ specOverview.batches }}</strong>
            </div>
            <div class="overview-item">
              <span>总卡密</span>
              <strong>{{ specOverview.total }}</strong>
            </div>
            <div class="overview-item">
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
                              <el-button size="small" type="info" plain :icon="View" @click="openSpecDetail(variant)">查看</el-button>
                            </el-tooltip>
                            <el-tooltip content="编辑策略" placement="top">
                              <el-button size="small" plain :icon="EditPen" @click="handleEditSpec(variant)">编辑</el-button>
                            </el-tooltip>
                            <el-tooltip :content="(variant.batch_count || 0) === 0 ? '删除空策略' : '有批次时不可删除'" placement="top">
                              <span class="tooltip-action-wrap">
                                <el-button size="small" type="danger" plain :icon="Delete" :disabled="(variant.batch_count || 0) > 0" @click="handleDeleteSpec(variant)">删除</el-button>
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
                    <el-tooltip content="编辑默认策略" placement="top">
                      <el-button size="small" plain :icon="EditPen" @click="handleEditSpecGroup(row)">编辑</el-button>
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
                              <el-button size="small" type="info" plain :icon="View" @click="openSpecDetail(variant)">查看</el-button>
                            </el-tooltip>
                            <el-tooltip content="编辑策略" placement="top">
                              <el-button size="small" plain :icon="EditPen" @click="handleEditSpec(variant)">编辑</el-button>
                            </el-tooltip>
                            <el-tooltip :content="(variant.batch_count || 0) === 0 ? '删除空策略' : '有批次时不可删除'" placement="top">
                              <span class="tooltip-action-wrap">
                                <el-button size="small" type="danger" plain :icon="Delete" :disabled="(variant.batch_count || 0) > 0" @click="handleDeleteSpec(variant)">删除</el-button>
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
                    <el-tooltip content="编辑默认策略" placement="top">
                      <el-button size="small" plain :icon="EditPen" @click="handleEditSpecGroup(row)">编辑</el-button>
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
              <el-tag v-if="viewMode === 'spec'" type="warning" effect="dark" round>
                {{ getSpecGroupText(currentSpec?.spec_group) }}
              </el-tag>
              <el-tag v-if="userAuthorizationEnabled" type="success" effect="dark" round>
                {{ getAuthorizationOwnerText(currentDetailTarget?.authorization_owner) }}
              </el-tag>
              <el-tag :type="currentDetailTarget?.status === 1 ? 'success' : 'info'" effect="dark" round>
                {{ currentDetailTarget?.status === 1 ? '启用' : '停用' }}
              </el-tag>
            </div>
          </div>
          <div class="hero-actions">
            <el-button :icon="ArrowLeft" @click="backFromDetail">{{ viewMode === 'batch' && currentSpec ? '返回规格' : '返回批次管理' }}</el-button>
            <template v-if="viewMode === 'spec'">
              <el-button :icon="EditPen" @click="handleEditSpec(currentSpec)">编辑规格</el-button>
              <el-button type="danger" plain :icon="Delete" :disabled="(currentSpec?.batch_count || 0) > 0" @click="handleDeleteSpec(currentSpec)">删除规格</el-button>
              <el-button type="primary" :icon="Plus" :disabled="!kamiGenerateEnabled" @click="showGenerateDialog(currentSpec)">生成卡密</el-button>
            </template>
            <template v-else>
              <el-button :icon="EditPen" @click="handleEditBatch(currentBatch)">编辑批次</el-button>
              <el-button type="danger" plain :icon="Delete" @click="handleDeleteBatch(currentBatch)">删除批次</el-button>
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

      <section v-if="viewMode === 'spec'" class="yz-admin-panel batches-panel">
        <div class="yz-panel-header compact">
          <div class="yz-panel-title">
            <el-icon><Box /></el-icon>
            <span>批次记录</span>
          </div>
          <div class="panel-actions">
            <el-button type="primary" :icon="Plus" :disabled="!kamiGenerateEnabled" @click="showGenerateDialog(currentSpec)">生成新批次</el-button>
          </div>
        </div>
        <el-table :data="specBatches" v-loading="batchLoading" class="yz-clean-table" row-key="id">
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
            <template #default="{ row }">{{ getSpecBenefitText(row) }}</template>
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
                  <el-button class="icon-action subtle" :icon="EditPen" @click="handleEditBatch(row)" />
                </el-tooltip>
                <el-tooltip content="删除空批次" placement="top">
                  <el-button class="icon-action danger" :icon="Delete" @click="handleDeleteBatch(row)" />
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
            <el-button type="danger" plain :disabled="selectedDetailKamis.length === 0" @click="handleDeleteSelectedDetail">
              删除选中
            </el-button>
            <el-button v-if="viewMode === 'batch'" type="primary" :icon="Plus" :disabled="!kamiGenerateEnabled" @click="showAppendDialog">追加卡密</el-button>
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
            <el-table-column label="最近验证时间" width="180">
              <template #default="{ row }">{{ formatOptionalTime(row.last_verify_at) }}</template>
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
                {{ getMachineBindModeText(row.machine_bind_mode, row.max_bind_devices) }}
              </template>
            </el-table-column>
            <el-table-column label="绑定设备" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">{{ getBoundDeviceText(row) }}</template>
            </el-table-column>
            <el-table-column label="最近验证时间" width="180">
              <template #default="{ row }">{{ formatOptionalTime(row.last_verify_at) }}</template>
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

    <el-dialog v-model="specDialogVisible" :title="isEditingSpec ? '编辑规格' : '新建规格'" width="720px">
      <el-form :model="specForm" label-width="128px" class="batch-form">
        <el-form-item label="应用" required>
          <el-select v-model="specForm.app_id" placeholder="选择应用" style="width: 100%" :disabled="isEditingSpec">
            <el-option v-for="app in apps" :key="app.app_id" :label="app.name" :value="app.app_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="卡密类型" required>
          <el-select v-model="specForm.kami_type" style="width: 100%" :disabled="isEditingSpec">
            <el-option v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="规格分组" required>
          <el-segmented
            v-model="specForm.spec_group"
            :options="[
              { label: '常用规格', value: 'common' },
              { label: '自定义规格', value: 'custom' }
            ]"
          />
        </el-form-item>
        <el-form-item v-if="isFixedTimeCard(specForm.kami_type)" label="有效期">
          <el-input :model-value="fixedValidityText(specForm.kami_type)" disabled />
        </el-form-item>
        <el-form-item v-if="specForm.kami_type === 'points'" label="积分面额" required>
          <el-input-number v-model="specForm.points_amount" :min="1" :max="100000000" style="width: 100%" :disabled="isEditingSpec" />
        </el-form-item>
        <el-form-item v-if="specForm.kami_type === 'points'" label="积分有效天数">
          <el-input-number v-model="specForm.points_valid_days" :min="1" :max="36500" style="width: 100%" :disabled="isEditingSpec" />
        </el-form-item>
        <el-form-item v-if="specForm.kami_type === 'times'" label="可用次数" required>
          <el-input-number v-model="specForm.times_total" :min="1" :max="1000000" style="width: 100%" :disabled="isEditingSpec" />
        </el-form-item>
        <el-form-item v-if="deviceLimitEnabled" label="机器码绑定" required>
          <el-select v-model="specForm.machine_bind_mode" style="width: 100%" :disabled="isEditingSpec">
            <el-option label="不限制" value="no_limit" />
            <el-option label="一机一码（一个卡密只能绑定一台设备）" value="one_card_one_device" />
            <el-option label="一卡多机（一个卡密可绑定多台设备）" value="one_card_multi_device" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="deviceLimitEnabled && specForm.machine_bind_mode === 'one_card_multi_device'" label="绑定设备数" required>
          <el-input-number v-model="specForm.max_bind_devices" :min="2" :max="1000" style="width: 100%" :disabled="isEditingSpec" />
        </el-form-item>
        <el-form-item v-if="userAuthorizationEnabled" label="授权归属" required>
          <el-select v-model="specForm.authorization_owner" style="width: 100%" :disabled="isEditingSpec">
            <el-option v-for="item in authorizationOwnerOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="userAuthorizationEnabled" label="用户绑定" required>
          <el-select v-model="specForm.user_bind_mode" style="width: 100%" :disabled="isEditingSpec">
            <el-option v-for="item in userBindModeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <div class="form-help">{{ authorizationPolicyHelp }}</div>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="specForm.sort_order" :min="0" :max="999999" style="width: 100%" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="specForm.status" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="停用" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="specForm.remark" type="textarea" :rows="2" />
        </el-form-item>
        <div v-if="!isEditingSpec" class="dialog-tip">
          相同应用、类型、权益和绑定策略会自动归入同一个规格；后续只需要在规格下继续生成批次。
        </div>
      </el-form>
      <template #footer>
        <el-button @click="specDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingSpec" @click="handleSaveSpec">保存规格</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="generateDialogVisible" title="按规格生成卡密" width="620px">
      <el-form :model="generateForm" label-width="110px">
        <el-form-item label="规格">
          <div class="batch-summary">{{ generateSpecSummary }}</div>
        </el-form-item>
        <el-form-item label="生成数量" required>
          <el-input-number v-model="generateForm.count" :min="1" :max="1000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="批次名称" required>
          <el-input v-model="generateForm.batch_no" maxlength="64" placeholder="例如：150积分-20260714" />
        </el-form-item>
        <el-form-item label="卡密前缀">
          <el-input v-model="generateForm.code_prefix" maxlength="32" placeholder="例如：VIP-" />
        </el-form-item>
        <el-form-item label="随机长度" required>
          <el-input-number v-model="generateForm.code_length" :min="4" :max="64" style="width: 100%" />
        </el-form-item>
        <el-form-item label="字符集" required>
          <el-select v-model="generateForm.charset" style="width: 100%">
            <el-option v-for="item in charsetOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="卡密有效期">
          <el-select v-model="generateForm.code_validity_mode" style="width: 100%">
            <el-option label="不限期" value="unlimited" />
            <el-option label="自定义天数" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="generateForm.code_validity_mode === 'custom'" label="有效天数" required>
          <el-input-number v-model="generateForm.code_valid_days" :min="1" :max="36500" style="width: 100%" />
        </el-form-item>
        <el-form-item label="格式预览">
          <div class="code-preview">{{ generateCodePreview }}</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="generateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="generating" @click="handleGenerateForSpec">生成卡密</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="batchDialogVisible" title="编辑批次" width="680px">
      <el-form :model="batchForm" label-width="128px" class="batch-form">
        <el-form-item label="应用" required>
          <el-select v-model="batchForm.app_id" placeholder="选择应用" style="width: 100%" disabled>
            <el-option v-for="app in apps" :key="app.app_id" :label="app.name" :value="app.app_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="批次名称" required>
          <el-input v-model="batchForm.batch_no" maxlength="64" />
        </el-form-item>
        <el-form-item label="卡密类型">
          <el-input :model-value="getTypeText(batchForm.kami_type)" disabled />
        </el-form-item>
        <el-form-item v-if="batchForm.kami_type === 'points'" label="积分面额">
          <el-input-number v-model="batchForm.points_amount" :min="1" :max="100000000" style="width: 100%" :disabled="editingBatchHasCards" />
        </el-form-item>
        <el-form-item v-if="batchForm.kami_type === 'points'" label="积分有效天数">
          <el-input-number v-model="batchForm.points_valid_days" :min="1" :max="36500" style="width: 100%" :disabled="editingBatchHasCards" />
        </el-form-item>
        <el-form-item v-if="batchForm.kami_type === 'times'" label="可用次数">
          <el-input-number v-model="batchForm.times_total" :min="1" :max="1000000" style="width: 100%" :disabled="editingBatchHasCards" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="batchForm.status" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="停用" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="batchForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingBatch" @click="handleSaveBatch">保存批次</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="appendDialogVisible" title="追加卡密" width="620px">
      <el-form :model="appendForm" label-width="110px">
        <el-form-item label="批次">
          <el-input :model-value="currentBatch?.batch_no" disabled />
        </el-form-item>
        <el-form-item label="批次配置">
          <div class="batch-summary">{{ currentBatchSummaryText }}</div>
        </el-form-item>
        <el-form-item label="追加数量" required>
          <el-input-number v-model="appendForm.count" :min="1" :max="1000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="卡密前缀">
          <el-input v-model="appendForm.code_prefix" maxlength="32" placeholder="例如：VIP-" />
        </el-form-item>
        <el-form-item label="随机长度" required>
          <el-input-number v-model="appendForm.code_length" :min="4" :max="64" style="width: 100%" />
        </el-form-item>
        <el-form-item label="字符集" required>
          <el-select v-model="appendForm.charset" style="width: 100%">
            <el-option v-for="item in charsetOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="格式预览">
          <div class="code-preview">{{ appendCodePreview }}</div>
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
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  Box,
  Delete,
  DocumentCopy,
  Download,
  EditPen,
  Key,
  Plus,
  Refresh,
  Search,
  View
} from '@element-plus/icons-vue'
import { getApps } from '../api/admin'
import { getAppInterfaces } from '../api/interfaces'
import {
  batchCreateKamis,
  createKamiSpec,
  deleteKamiBatch,
  deleteKamiSpec,
  deleteKamis,
  exportKamis,
  generateKamisForSpec,
  getKamiBatches,
  getKamiSpecBatches,
  getKamiSpecs,
  getKamis,
  updateKamiBatch,
  updateKamiSpec
} from '../api/kami'
import { formatBeijingTime } from '../utils/datetime'
import {
  AUTHORIZATION_OWNER_OPTIONS,
  TYPE_OPTIONS,
  USER_BIND_MODE_OPTIONS,
  getAuthorizationOwnerText,
  getMachineBindModeText,
  getSpecBenefitText,
  getSpecGroupText,
  getSpecPolicyText,
  getStatusText,
  getStatusType,
  getTypeText,
  getUserBindModeText,
  getValidityText,
  isFixedTimeCard
} from '../utils/kamiDisplay'
import { groupKamiSpecsByBenefit } from '../utils/kamiSpecGrouping'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const batchLoading = ref(false)
const detailLoading = ref(false)
const savingSpec = ref(false)
const savingBatch = ref(false)
const generating = ref(false)
const appending = ref(false)
const apps = ref([])
const specStats = ref([])
const specBatches = ref([])
const batchStats = ref([])
const detailKamis = ref([])
const selectedDetailKamis = ref([])
const detailTotal = ref(0)
const viewMode = ref('list')
const selectedSpec = ref(null)
const selectedBatch = ref(null)
const specDialogVisible = ref(false)
const batchDialogVisible = ref(false)
const generateDialogVisible = ref(false)
const appendDialogVisible = ref(false)
const isEditingSpec = ref(false)
const editingBatchHasCards = ref(false)
const customExpanded = ref(false)
const appInterfaceFlags = ref({})
const appInterfaceConfigs = ref({})

const baseTypeOptions = TYPE_OPTIONS
const authorizationOwnerOptions = AUTHORIZATION_OWNER_OPTIONS
const userBindModeOptions = USER_BIND_MODE_OPTIONS

const charsetOptions = [
  { label: '大写字母 + 数字', value: 'upper_numeric', sample: 'A1B2C3D4E5F6G7H8' },
  { label: '纯数字', value: 'numeric', sample: '1234567890123456' },
  { label: '大写字母', value: 'upper', sample: 'ABCDEFGHJKLMNPQR' },
  { label: '大小写字母 + 数字', value: 'lower_mixed', sample: 'aB3dE5fG7hJ9kLmN' }
]

const fixedValidityMap = {
  hour: '小时卡：1小时',
  day: '天卡：1天',
  week: '周卡：7天',
  month: '月卡：30天',
  quarter: '季卡：90天',
  year: '年卡：365天',
  lifetime: '永久卡：永久'
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
  id: null,
  app_id: '',
  kami_type: 'day',
  spec_group: 'common',
  machine_bind_mode: 'one_card_one_device',
  max_bind_devices: 3,
  points_amount: 100,
  points_valid_days: undefined,
  times_total: 1,
  authorization_owner: 'device',
  user_bind_mode: 'none',
  status: 1,
  sort_order: 0,
  remark: ''
})

const generateForm = reactive({
  spec_id: null,
  count: 10,
  batch_no: '',
  code_prefix: '',
  code_length: 16,
  charset: 'upper_numeric',
  code_validity_mode: 'unlimited',
  code_valid_days: 7
})

const batchForm = reactive({
  id: null,
  app_id: '',
  batch_no: '',
  kami_type: 'day',
  machine_bind_mode: 'one_card_one_device',
  max_bind_devices: 3,
  points_amount: 100,
  points_valid_days: undefined,
  times_total: 1,
  authorization_owner: 'device',
  user_bind_mode: 'none',
  status: 1,
  remark: ''
})

const appendForm = reactive({
  count: 10,
  code_prefix: '',
  code_length: 16,
  charset: 'upper_numeric'
})

const interfaceEnabled = (key, defaultValue = true) => {
  const value = appInterfaceFlags.value[key]
  return typeof value === 'boolean' ? value : defaultValue
}

const deviceLimitEnabled = computed(() => interfaceEnabled('sdk.device_limit', true))
const userAuthorizationEnabled = computed(() => (
  interfaceEnabled('sdk.verify', true) &&
  Boolean(appInterfaceConfigs.value['sdk.verify']?.enable_user_authorization)
))
const pointsFeatureEnabled = computed(() => (
  interfaceEnabled('points.balance', true) ||
  interfaceEnabled('points.redeem', true) ||
  interfaceEnabled('points.consume', true) ||
  interfaceEnabled('points.transactions', true)
))
const kamiGenerateEnabled = computed(() => interfaceEnabled('admin.kamis.batch', true))

const typeOptions = computed(() => (
  baseTypeOptions.filter((item) => item.value !== 'points' || pointsFeatureEnabled.value)
))

const specGroups = computed(() => groupKamiSpecsByBenefit(specStats.value))
const commonSpecs = computed(() => specGroups.value.filter((item) => item.spec_group === 'common'))
const customSpecs = computed(() => specGroups.value.filter((item) => item.spec_group !== 'common'))
const visibleCustomSpecs = computed(() => (
  customExpanded.value || customSpecs.value.length <= 8 ? customSpecs.value : customSpecs.value.slice(0, 8)
))

const specOverview = computed(() => specGroups.value.reduce(
  (acc, item) => {
    acc.specs += 1
    acc.batches += item.batch_count || 0
    acc.total += item.total_count || 0
    acc.unused += item.unused_count || 0
    return acc
  },
  { specs: 0, batches: 0, total: 0, unused: 0 }
))

const currentSpec = computed(() => {
  if (!selectedSpec.value) return null
  return specStats.value.find((item) => item.id === selectedSpec.value.id) || selectedSpec.value
})

const currentBatch = computed(() => {
  if (!selectedBatch.value) return null
  return (
    specBatches.value.find((item) => item.id === selectedBatch.value.id) ||
    specBatches.value.find((item) => item.batch_no === selectedBatch.value.batch_no) ||
    batchStats.value.find((item) => item.id === selectedBatch.value.id) ||
    batchStats.value.find((item) => item.batch_no === selectedBatch.value.batch_no) ||
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
const generateCodePreview = computed(() => codePreview(generateForm))
const appendCodePreview = computed(() => codePreview(appendForm))
const generateSpecSummary = computed(() => {
  const spec = specStats.value.find((item) => item.id === generateForm.spec_id) || currentSpec.value
  if (!spec) return '-'
  return [
    spec.spec_name,
    getTypeText(spec.kami_type),
    getSpecBenefitText(spec),
    getSpecPolicyText(spec)
  ].filter(Boolean).join(' / ')
})
const currentBatchSummaryText = computed(() => {
  const parts = [
    getTypeText(currentBatch.value?.kami_type),
    getValidityText(currentBatch.value)
  ]
  if (deviceLimitEnabled.value) {
    parts.push(getMachineBindModeText(currentBatch.value?.machine_bind_mode, currentBatch.value?.max_bind_devices))
  }
  if (userAuthorizationEnabled.value) {
    parts.push(getAuthorizationOwnerText(currentBatch.value?.authorization_owner))
    parts.push(getUserBindModeText(currentBatch.value?.user_bind_mode))
  }
  return parts.filter(Boolean).join(' / ')
})

const getDefaultVariant = (row) => {
  if (!row) return null
  if (!Array.isArray(row.variants)) return row
  return row.variants.find((item) => item.id === row.default_spec_id) || row.variants[0] || null
}
const authorizationPolicyHelp = computed(() => {
  const owner = specForm.authorization_owner
  const bind = specForm.user_bind_mode
  const ownerHelp = {
    device: '设备授权：权益归属到设备，适合不方便注册账号的软件。',
    user: '用户授权：权益归属到用户，必须传入有效用户信息。',
    auto: '自动识别：SDK 请求带有效 user_id/username 时按用户授权，未传用户时按设备授权。'
  }[owner] || '设备授权：权益归属到设备。'
  const bindHelp = {
    none: '不绑定用户：不读取用户信息。',
    auto: '自动识别绑定：首次使用传入有效用户时绑定用户；未传用户时按设备授权。',
    optional: '自动识别绑定：首次使用传入有效用户时绑定用户；未传用户时按设备授权。',
    required: '必须绑定用户：verify 和 consume 都必须传 user_id 或 username。'
  }[bind] || '不绑定用户：不读取用户信息。'
  return `${ownerHelp} ${bindHelp}`
})

const syncTypeWithInterfaceFlags = () => {
  if (queryParams.kami_type && !typeOptions.value.some((item) => item.value === queryParams.kami_type)) {
    queryParams.kami_type = ''
  }
  if (!typeOptions.value.some((item) => item.value === specForm.kami_type)) {
    specForm.kami_type = typeOptions.value[0]?.value || 'day'
  }
}

const loadAppInterfaceFlags = async () => {
  if (!queryParams.app_id) {
    appInterfaceFlags.value = {}
    appInterfaceConfigs.value = {}
    return
  }
  try {
    const res = await getAppInterfaces(queryParams.app_id)
    const flags = {}
    const configs = {}
    ;(res.data || []).forEach((item) => {
      flags[item.interface_key] = Boolean(item.enabled)
      configs[item.interface_key] = item.config || {}
    })
    appInterfaceFlags.value = flags
    appInterfaceConfigs.value = configs
  } catch (error) {
    console.error('加载应用接口开关失败:', error)
    appInterfaceFlags.value = {}
    appInterfaceConfigs.value = {}
  }
  syncTypeWithInterfaceFlags()
}

const loadApps = async () => {
  const res = await getApps()
  apps.value = res.data || []
  if (route.query.app_id) queryParams.app_id = String(route.query.app_id)
  if (!queryParams.app_id && apps.value.length > 0) queryParams.app_id = apps.value[0].app_id
  specForm.app_id = queryParams.app_id
  await loadAppInterfaceFlags()
  await loadSpecs()
  await hydrateRouteDetail()
}

const hydrateRouteDetail = async () => {
  if (!queryParams.app_id) return
  if (route.query.spec_id) {
    const specId = Number(route.query.spec_id)
    const spec = specStats.value.find((item) => item.id === specId)
    if (spec) await openSpecDetail(spec, false)
    return
  }
  if (route.query.batch_no) {
    const batch = await findBatchByNo(String(route.query.batch_no))
    if (batch) await openBatchDetail(batch, false)
  }
}

const findBatchByNo = async (batchNo) => {
  const res = await getKamiBatches({ app_id: queryParams.app_id })
  batchStats.value = res.data || []
  return batchStats.value.find((item) => item.batch_no === batchNo)
}

const handleAppChange = async () => {
  viewMode.value = 'list'
  selectedSpec.value = null
  selectedBatch.value = null
  specForm.app_id = queryParams.app_id
  await loadAppInterfaceFlags()
  await loadSpecs()
  router.replace({ path: '/kamis/batches', query: { app_id: queryParams.app_id } })
}

const handleTypeChange = async () => {
  customExpanded.value = false
  await loadSpecs()
}

const resetListFilters = async () => {
  queryParams.kami_type = ''
  queryParams.keyword = ''
  customExpanded.value = false
  await loadSpecs()
}

const loadSpecs = async () => {
  if (!queryParams.app_id) {
    specStats.value = []
    return
  }
  loading.value = true
  try {
    const params = { app_id: queryParams.app_id }
    if (queryParams.kami_type) params.kami_type = queryParams.kami_type
    if (queryParams.keyword.trim()) params.keyword = queryParams.keyword.trim()
    const res = await getKamiSpecs(params)
    specStats.value = res.data?.items || []
    if (currentSpec.value) selectedSpec.value = currentSpec.value
  } finally {
    loading.value = false
  }
}

const loadSpecBatches = async () => {
  if (!currentSpec.value?.id) {
    specBatches.value = []
    return
  }
  batchLoading.value = true
  try {
    const res = await getKamiSpecBatches(currentSpec.value.id)
    specBatches.value = res.data || []
  } finally {
    batchLoading.value = false
  }
}

const openSpecGroup = async (row) => {
  const variant = getDefaultVariant(row)
  if (!variant) {
    ElMessage.warning('该权益规格下暂无可查看的绑定策略')
    return
  }
  await openSpecDetail(variant)
}

const openSpecDetail = async (row, updateRoute = true) => {
  if (!row) return
  selectedSpec.value = row
  selectedBatch.value = null
  viewMode.value = 'spec'
  resetDetailState()
  if (updateRoute) {
    router.replace({ path: '/kamis/batches', query: { app_id: queryParams.app_id, spec_id: row.id } })
  }
  await loadSpecBatches()
  await loadDetailKamis()
}

const openBatchDetail = async (row, updateRoute = true) => {
  if (!row) return
  selectedBatch.value = row
  if (row.spec_id) {
    selectedSpec.value = specStats.value.find((item) => item.id === row.spec_id) || selectedSpec.value
  }
  viewMode.value = 'batch'
  resetDetailState()
  if (updateRoute) {
    router.replace({ path: '/kamis/batches', query: { app_id: queryParams.app_id, batch_no: row.batch_no } })
  }
  await loadDetailKamis()
}

const backFromDetail = async () => {
  if (viewMode.value === 'batch' && currentSpec.value) {
    await openSpecDetail(currentSpec.value)
    return
  }
  viewMode.value = 'list'
  selectedSpec.value = null
  selectedBatch.value = null
  selectedDetailKamis.value = []
  router.replace({ path: '/kamis/batches', query: { app_id: queryParams.app_id } })
  await loadSpecs()
}

const resetDetailState = () => {
  detailQuery.batch_no = ''
  detailQuery.status = ''
  detailQuery.keyword = ''
  detailQuery.page = 1
  detailQuery.page_size = 20
  selectedDetailKamis.value = []
}

const loadDetailKamis = async () => {
  if (!currentDetailTarget.value) return
  detailLoading.value = true
  try {
    const params = {
      app_id: currentDetailTarget.value.app_id,
      page: detailQuery.page,
      page_size: detailQuery.page_size
    }
    if (viewMode.value === 'spec') {
      if (detailQuery.batch_no) params.batch_no = detailQuery.batch_no
      else params.spec_id = currentSpec.value.id
    }
    if (viewMode.value === 'batch') params.batch_no = currentBatch.value.batch_no
    if (detailQuery.status) params.status = detailQuery.status
    if (detailQuery.keyword.trim()) params.keyword = detailQuery.keyword.trim()
    const res = await getKamis(params)
    detailKamis.value = res.data.items || []
    detailTotal.value = res.data.total || 0
    selectedDetailKamis.value = []
    await loadSpecs()
    if (viewMode.value === 'spec') await loadSpecBatches()
  } finally {
    detailLoading.value = false
  }
}

const resetDetailFilters = () => {
  detailQuery.batch_no = ''
  detailQuery.status = ''
  detailQuery.keyword = ''
  detailQuery.page = 1
  loadDetailKamis()
}

const resetSpecForm = () => {
  Object.assign(specForm, {
    id: null,
    app_id: queryParams.app_id || apps.value[0]?.app_id || '',
    kami_type: typeOptions.value[0]?.value || 'day',
    spec_group: 'common',
    machine_bind_mode: deviceLimitEnabled.value ? 'one_card_one_device' : 'no_limit',
    max_bind_devices: deviceLimitEnabled.value ? 3 : 0,
    points_amount: 100,
    points_valid_days: undefined,
    times_total: 1,
    authorization_owner: userAuthorizationEnabled.value ? 'auto' : 'device',
    user_bind_mode: userAuthorizationEnabled.value ? 'auto' : 'none',
    status: 1,
    sort_order: 0,
    remark: ''
  })
}

const showCreateSpecDialog = () => {
  isEditingSpec.value = false
  resetSpecForm()
  specDialogVisible.value = true
}

const handleEditSpec = (row) => {
  if (!row) return
  isEditingSpec.value = true
  Object.assign(specForm, {
    id: row.id,
    app_id: row.app_id || queryParams.app_id,
    kami_type: row.kami_type || 'day',
    spec_group: row.spec_group || 'custom',
    machine_bind_mode: row.machine_bind_mode || 'one_card_one_device',
    max_bind_devices: row.max_bind_devices || 1,
    points_amount: row.points_amount || 100,
    points_valid_days: row.points_valid_days || undefined,
    times_total: row.times_total || 1,
    authorization_owner: row.authorization_owner || 'device',
    user_bind_mode: row.user_bind_mode || 'none',
    status: Number(row.status ?? 1),
    sort_order: row.sort_order || 0,
    remark: row.remark || ''
  })
  specDialogVisible.value = true
}

const handleEditSpecGroup = (row) => {
  const variant = getDefaultVariant(row)
  if (!variant) {
    ElMessage.warning('该权益规格下暂无可操作的绑定策略')
    return
  }
  handleEditSpec(variant)
}

const canDeleteSpecGroup = (row) => (row?.batch_count || 0) === 0

const resetDetailAfterSpecDelete = (deletedIds) => {
  if (viewMode.value === 'spec' && deletedIds.includes(currentSpec.value?.id)) {
    viewMode.value = 'list'
    selectedSpec.value = null
    selectedBatch.value = null
    router.replace({ path: '/kamis/batches', query: { app_id: queryParams.app_id } })
  }
}

const handleDeleteSpecGroup = async (row) => {
  if (!row) return
  if (!canDeleteSpecGroup(row)) {
    ElMessage.warning('该规格下已有批次，请先迁移或删除批次后再删除规格')
    return
  }
  const variants = (row.variants?.length ? row.variants : [getDefaultVariant(row)]).filter(Boolean)
  if (variants.length === 0) {
    ElMessage.warning('该权益规格下暂无可删除的绑定策略')
    return
  }
  const deletedIds = variants.map((variant) => variant.id)
  try {
    await ElMessageBox.confirm(
      `确定删除规格「${row.spec_name}」吗？该规格下没有批次，将同时删除 ${variants.length} 个空绑定策略。`,
      '删除空规格',
      { type: 'warning' }
    )
    for (const variant of variants) {
      await deleteKamiSpec(variant.id)
    }
    ElMessage.success('规格已删除')
    resetDetailAfterSpecDelete(deletedIds)
    await loadSpecs()
  } catch (error) {
    if (error !== 'cancel') {
      const detail = error?.response?.data?.detail
      ElMessage.error(detail || error?.message || '删除规格失败')
      console.error('删除规格失败:', error)
    }
  }
}

const normalizeSpecPayload = () => {
  const machineBindMode = deviceLimitEnabled.value ? specForm.machine_bind_mode : 'no_limit'
  const payload = {
    app_id: specForm.app_id,
    kami_type: specForm.kami_type,
    spec_group: specForm.spec_group,
    machine_bind_mode: machineBindMode,
    max_bind_devices:
      machineBindMode === 'one_card_multi_device'
        ? specForm.max_bind_devices || 3
        : machineBindMode === 'no_limit'
          ? 0
          : 1,
    authorization_owner: userAuthorizationEnabled.value ? specForm.authorization_owner : 'device',
    user_bind_mode: userAuthorizationEnabled.value ? specForm.user_bind_mode : 'none',
    status: specForm.status,
    sort_order: specForm.sort_order || 0,
    remark: specForm.remark || null
  }
  if (specForm.kami_type === 'points') {
    payload.points_amount = specForm.points_amount
    payload.points_valid_days = specForm.points_valid_days || null
  }
  if (specForm.kami_type === 'times') {
    payload.times_total = specForm.times_total
  }
  return payload
}

const handleSaveSpec = async () => {
  if (!specForm.app_id) {
    ElMessage.warning('请选择应用')
    return
  }
  if (specForm.kami_type === 'points' && !specForm.points_amount) {
    ElMessage.warning('积分卡必须设置积分面额')
    return
  }
  if (specForm.kami_type === 'times' && !specForm.times_total) {
    ElMessage.warning('次数卡必须设置可用次数')
    return
  }
  if (deviceLimitEnabled.value && specForm.machine_bind_mode === 'one_card_multi_device' && (!specForm.max_bind_devices || specForm.max_bind_devices < 2)) {
    ElMessage.warning('一卡多机至少需要允许 2 台设备')
    return
  }
  if (userAuthorizationEnabled.value && specForm.authorization_owner === 'user' && specForm.user_bind_mode === 'none') {
    ElMessage.warning('用户授权规格必须选择自动识别绑定或必须绑定用户')
    return
  }

  savingSpec.value = true
  try {
    if (isEditingSpec.value) {
      await updateKamiSpec(specForm.id, {
        spec_group: specForm.spec_group,
        status: specForm.status,
        sort_order: specForm.sort_order || 0,
        remark: specForm.remark || null
      })
      ElMessage.success('规格已更新')
    } else {
      const res = await createKamiSpec(normalizeSpecPayload())
      ElMessage.success(res.message || '规格已创建')
      queryParams.app_id = specForm.app_id
    }
    specDialogVisible.value = false
    await loadSpecs()
    if (viewMode.value === 'spec' && currentSpec.value) selectedSpec.value = currentSpec.value
  } finally {
    savingSpec.value = false
  }
}

const handleDeleteSpec = async (row) => {
  if (!row) return
  if ((row.batch_count || 0) > 0) {
    ElMessage.warning('该规格下已有批次，请先迁移或删除批次后再删除规格')
    return
  }
  try {
    await ElMessageBox.confirm(`确定删除规格「${row.spec_name}」吗？只有没有批次和卡密的规格可以删除。`, '删除规格', {
      type: 'warning'
    })
    await deleteKamiSpec(row.id)
    ElMessage.success('规格已删除')
    resetDetailAfterSpecDelete([row.id])
    await loadSpecs()
  } catch (error) {
    if (error !== 'cancel') {
      const detail = error?.response?.data?.detail
      ElMessage.error(detail || error?.message || '删除规格失败')
      console.error('删除规格失败:', error)
    }
  }
}

const showGenerateDialog = (row) => {
  if (!kamiGenerateEnabled.value) {
    ElMessage.warning('卡密生成接口未开通')
    return
  }
  if (!row?.id) {
    ElMessage.warning('请先选择规格')
    return
  }
  const date = new Date().toISOString().slice(0, 10).replaceAll('-', '')
  generateForm.spec_id = row.id
  generateForm.count = 10
  generateForm.batch_no = `${row.spec_name || getSpecBenefitText(row)}-${date}`.slice(0, 64)
  generateForm.code_prefix = ''
  generateForm.code_length = 16
  generateForm.charset = 'upper_numeric'
  generateForm.code_validity_mode = 'unlimited'
  generateForm.code_valid_days = 7
  generateDialogVisible.value = true
}

const showGenerateForGroup = (row) => {
  const variant = getDefaultVariant(row)
  if (!variant) {
    ElMessage.warning('该权益规格下暂无可生成的绑定策略')
    return
  }
  showGenerateDialog(variant)
}

const handleGenerateForSpec = async () => {
  if (!generateForm.spec_id || !generateForm.batch_no.trim()) {
    ElMessage.warning('请选择规格并填写批次名称')
    return
  }
  generating.value = true
  try {
    const res = await generateKamisForSpec(generateForm.spec_id, {
      count: generateForm.count,
      batch_no: generateForm.batch_no.trim(),
      code_prefix: generateForm.code_prefix || null,
      code_length: generateForm.code_length,
      charset: generateForm.charset,
      code_valid_days: generateForm.code_validity_mode === 'custom' ? generateForm.code_valid_days : null
    })
    ElMessage.success(`成功生成 ${res.data.count} 个卡密`)
    generateDialogVisible.value = false
    await loadSpecs()
    const spec = specStats.value.find((item) => item.id === generateForm.spec_id)
    if (spec) {
      selectedSpec.value = spec
      if (viewMode.value === 'list') await openSpecDetail(spec)
      else {
        await loadSpecBatches()
        await loadDetailKamis()
      }
    }
  } finally {
    generating.value = false
  }
}

const handleEditBatch = (row) => {
  if (!row) return
  editingBatchHasCards.value = (row.total_count || 0) > 0
  Object.assign(batchForm, {
    id: row.id,
    app_id: row.app_id || queryParams.app_id,
    batch_no: row.batch_no || '',
    kami_type: row.kami_type || 'day',
    machine_bind_mode: row.machine_bind_mode || 'one_card_one_device',
    max_bind_devices: row.max_bind_devices || 1,
    points_amount: row.points_amount || 100,
    points_valid_days: row.points_valid_days || undefined,
    times_total: row.times_total || 1,
    authorization_owner: row.authorization_owner || 'device',
    user_bind_mode: row.user_bind_mode || 'none',
    status: Number(row.status ?? 1),
    remark: row.remark || ''
  })
  batchDialogVisible.value = true
}

const normalizeBatchPayload = () => {
  const payload = {
    app_id: batchForm.app_id,
    batch_no: batchForm.batch_no.trim(),
    kami_type: batchForm.kami_type,
    machine_bind_mode: batchForm.machine_bind_mode,
    max_bind_devices: batchForm.max_bind_devices,
    authorization_owner: batchForm.authorization_owner,
    user_bind_mode: batchForm.user_bind_mode,
    status: batchForm.status,
    remark: batchForm.remark || null
  }
  if (batchForm.kami_type === 'points') {
    payload.points_amount = batchForm.points_amount
    payload.points_valid_days = batchForm.points_valid_days || null
  }
  if (batchForm.kami_type === 'times') {
    payload.times_total = batchForm.times_total
  }
  return payload
}

const handleSaveBatch = async () => {
  if (!batchForm.id || !batchForm.batch_no.trim()) {
    ElMessage.warning('请填写批次名称')
    return
  }
  savingBatch.value = true
  try {
    await updateKamiBatch(batchForm.id, normalizeBatchPayload())
    ElMessage.success('批次已更新')
    batchDialogVisible.value = false
    await loadSpecs()
    if (viewMode.value === 'spec') await loadSpecBatches()
    if (viewMode.value === 'batch') await loadDetailKamis()
  } finally {
    savingBatch.value = false
  }
}

const handleDeleteBatch = async (row) => {
  if (!row) return
  try {
    await ElMessageBox.confirm(`确定删除批次「${row.batch_no}」吗？只有空批次可以删除。`, '删除批次', {
      type: 'warning'
    })
    await deleteKamiBatch(row.id)
    ElMessage.success('批次已删除')
    if (viewMode.value === 'batch' && currentBatch.value?.id === row.id) {
      if (currentSpec.value) await openSpecDetail(currentSpec.value)
      else await backFromDetail()
      return
    }
    await loadSpecs()
    if (viewMode.value === 'spec') await loadSpecBatches()
  } catch (error) {
    if (error !== 'cancel') {
      const detail = error?.response?.data?.detail
      ElMessage.error(detail || error?.message || '删除批次失败')
      console.error('删除批次失败:', error)
    }
  }
}

const showAppendDialog = () => {
  if (!kamiGenerateEnabled.value) {
    ElMessage.warning('卡密生成接口未开通')
    return
  }
  appendForm.count = 10
  appendForm.code_prefix = ''
  appendForm.code_length = 16
  appendForm.charset = 'upper_numeric'
  appendDialogVisible.value = true
}

const handleAppendKamis = async () => {
  if (!currentBatch.value) return
  appending.value = true
  try {
    const res = await batchCreateKamis({
      app_id: currentBatch.value.app_id,
      batch_no: currentBatch.value.batch_no,
      count: appendForm.count,
      code_prefix: appendForm.code_prefix,
      code_length: appendForm.code_length,
      charset: appendForm.charset
    })
    ElMessage.success(`成功追加 ${res.data.count} 个卡密`)
    appendDialogVisible.value = false
    detailQuery.page = 1
    await loadDetailKamis()
  } finally {
    appending.value = false
  }
}

const handleDeleteSelectedDetail = async () => {
  if (!currentDetailTarget.value || selectedDetailKamis.value.length === 0) return
  const count = selectedDetailKamis.value.length
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${count} 个卡密吗？请先确认这些卡密的授权、积分、次数或使用记录已经迁移，删除后不可恢复。`,
      '确认删除卡密',
      {
        type: 'warning',
        confirmButtonText: '已迁移并确认删除',
        cancelButtonText: '取消'
      }
    )
    const payload = {
      app_id: currentDetailTarget.value.app_id,
      kami_codes: selectedDetailKamis.value.map((item) => item.kami_code)
    }
    if (viewMode.value === 'spec') payload.spec_id = currentSpec.value.id
    if (viewMode.value === 'batch') payload.batch_no = currentBatch.value.batch_no
    const res = await deleteKamis(payload)
    const data = res.data
    ElMessage.success(`已删除 ${data.deleted_count} 个，未处理 ${data.skipped_count} 个`)
    await loadDetailKamis()
  } catch (error) {
    if (error !== 'cancel') console.error('删除卡密失败:', error)
  }
}

const handleDetailExport = async () => {
  if (!currentDetailTarget.value) return
  const params = { app_id: currentDetailTarget.value.app_id }
  if (viewMode.value === 'spec') params.spec_id = currentSpec.value.id
  if (viewMode.value === 'batch') params.batch_no = currentBatch.value.batch_no
  const response = await exportKamis(params)
  const suffix = viewMode.value === 'spec' ? `spec_${currentSpec.value.id}` : currentBatch.value.batch_no
  downloadBlob(response, `kamis_${currentDetailTarget.value.app_id}_${suffix}.csv`)
}

const downloadBlob = (response, filename) => {
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

const usedCount = (row) => {
  if (!row) return 0
  if (typeof row.redeemed_count === 'number' && row.redeemed_count > 0) return row.redeemed_count
  if (typeof row.active_count === 'number' && row.active_count > 0) return row.active_count
  return Math.max((row.total_count || 0) - (row.unused_count || 0) - (row.frozen_count || 0) - (row.expired_count || 0), 0)
}

const getSpecRemainingBenefit = (row) => {
  if (!row) return '-'
  if (row.kami_type === 'points') return `${row.points_remaining_total || 0} 积分`
  if (row.kami_type === 'times') return `${row.times_remaining_total || 0} 次`
  return '-'
}

const getCodeValidityText = (row) => {
  if (!row) return '-'
  if (row.code_validity_text) return row.code_validity_text
  return row.code_valid_days ? `生成后 ${row.code_valid_days} 天` : '不限期'
}

const getSpecRemarkText = (row) => {
  if (!row) return '-'
  const remarks = (row.variants?.length ? row.variants : [row])
    .map((item) => item?.remark)
    .filter(Boolean)
  const uniqueRemarks = [...new Set(remarks)]
  if (uniqueRemarks.length === 0) return '-'
  if (uniqueRemarks.length === 1) return uniqueRemarks[0]
  return '多个备注'
}

const fixedValidityText = (type) => fixedValidityMap[type] || '-'
const formatOptionalTime = (value) => (value ? formatBeijingTime(value) : '-')

const copyToClipboard = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('复制成功')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

const getKamiUserText = (row) => (
  row?.redeemed_user?.username ||
  row?.redeemed_user?.email ||
  row?.redeemed_by_user_id ||
  '-'
)

const getPointsRemaining = (row) => row?.point_remaining_balance ?? row?.points_amount ?? 0
const getPointsRedeemed = (row) => Math.max((row?.points_amount || 0) - getPointsRemaining(row), 0)
const getTimesConsumed = (row) => Math.max((row?.times_total || 0) - (row?.times_remaining ?? 0), 0)
const isKamiExpired = (row) => row?.is_code_expired || row?.display_status === 'expired'
const getKamiStatusText = (row) => (isKamiExpired(row) ? '已过期' : getStatusText(row?.status))
const getKamiStatusType = (row) => (isKamiExpired(row) ? 'warning' : getStatusType(row?.status))

const getBoundDeviceText = (row) => {
  if (row?.bind_uuid) return row.bind_uuid
  if (row?.device_bind_count) return `${row.device_bind_count} 台设备`
  return '-'
}

const getTimeCardValidity = (row) => {
  if (row?.expire_time) return formatBeijingTime(row.expire_time)
  return getValidityText(row)
}

const getTypeBadgeClass = (type) => {
  if (type === 'points') return 'is-points'
  if (type === 'times') return 'is-times'
  if (type === 'lifetime') return 'is-lifetime'
  if (isFixedTimeCard(type)) return 'is-time'
  return 'is-default'
}

const codePreview = (form) => {
  const option = charsetOptions.find((item) => item.value === form.charset) || charsetOptions[0]
  const suffix = option.sample.repeat(Math.ceil(form.code_length / option.sample.length)).slice(0, form.code_length)
  return `${form.code_prefix || ''}${suffix}`
}

onMounted(loadApps)
</script>

<style scoped>
.kami-batches-page {
  min-height: 100%;
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

.overview-strip {
  padding: 18px 28px 6px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.overview-item {
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

.spec-section {
  padding: 20px 28px 10px;
}

.spec-section + .spec-section {
  padding-top: 10px;
  padding-bottom: 28px;
}

.section-title-row {
  min-height: 58px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.section-title-row h3 {
  margin: 0 0 6px;
  color: #0f172a;
  font-size: 18px;
  line-height: 1.2;
}

.section-title-row p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}

.section-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.yz-clean-table {
  width: 100%;
}

.yz-clean-table :deep(.el-table__header th) {
  height: 54px;
  background: #f8fafc;
  color: #58708c;
  font-size: 15px;
  font-weight: 700;
}

.yz-clean-table :deep(.el-table__row) {
  height: 72px;
}

.batch-title-link {
  border: 0;
  background: transparent;
  color: #2563eb;
  font: inherit;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.35;
  padding: 0;
  cursor: pointer;
}

.batch-title-link:hover {
  color: #1d4ed8;
  text-decoration: underline;
}

.type-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  padding: 4px 10px;
  border: 1px solid #dbe4f0;
  border-radius: 6px;
  background: #f8fafc;
  color: #334155;
  font-size: 14px;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
}

.type-badge.is-time {
  border-color: #99f6e4;
  background: #ecfdf5;
  color: #0f766e;
}

.type-badge.is-points {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #15803d;
}

.type-badge.is-times {
  border-color: #fde68a;
  background: #fffbeb;
  color: #b45309;
}

.type-badge.is-lifetime {
  border-color: #fbcfe8;
  background: #fdf2f8;
  color: #be185d;
}

.code-cell,
.count-pills,
.icon-actions,
.compact-actions,
.panel-actions,
.hero-actions,
.hero-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.compact-actions {
  flex-wrap: nowrap;
  gap: 6px;
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

.tooltip-action-wrap {
  display: inline-flex;
}

.code-cell {
  min-width: 0;
}

.count-pill {
  min-width: 30px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: #fff;
  font-weight: 700;
}

.count-pill.is-total {
  background: #64748b;
}

.count-pill.is-used {
  background: #f59e0b;
}

.count-pill.is-left {
  background: #059669;
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

.spec-section :deep(.el-table__header .el-table__cell) {
  padding: 10px 0;
}

.spec-section :deep(.el-table__body .el-table__cell) {
  padding: 8px 0;
}

.spec-section .type-badge {
  min-height: 24px;
  padding: 3px 8px;
  font-size: 13px;
}

.spec-section .count-pill {
  min-width: 28px;
  height: 26px;
  border-radius: 7px;
  font-size: 13px;
}

.spec-section .icon-action {
  width: 32px;
  height: 32px;
}

.variant-panel {
  margin: 0 18px 18px 42px;
  padding: 14px 16px 16px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
}

.variant-title {
  margin-bottom: 10px;
  color: #334155;
  font-size: 14px;
  font-weight: 700;
}

.variant-table :deep(.el-table__row) {
  height: 58px;
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

.summary-metric-card {
  min-height: 150px;
  padding: 30px 34px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  align-items: center;
  text-align: center;
  gap: 10px;
}

.metric-item {
  display: flex;
  flex-direction: column;
  gap: 10px;
  color: #475569;
}

.metric-value {
  font-size: 34px;
  font-weight: 800;
  line-height: 1;
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

.batches-panel {
  margin-bottom: 24px;
}

.cards-panel :deep(.el-empty) {
  min-height: 420px;
}

.detail-table {
  min-height: 360px;
}

.mono-text,
.code-preview {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  word-break: break-all;
}

.code-preview,
.batch-summary,
.dialog-tip {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #dbe4f0;
  border-radius: 8px;
  background: #f8fafc;
  color: #0f172a;
}

.batch-summary,
.dialog-tip {
  color: #475569;
  line-height: 1.5;
}

.dialog-tip {
  margin: 4px 0 0 128px;
  width: calc(100% - 128px);
  color: #64748b;
  font-size: 13px;
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

.batch-form :deep(.el-form-item__label) {
  font-weight: 600;
}

.form-help {
  margin-top: 6px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

html.dark .yz-panel-title,
html.dark .batch-overview-main h2,
html.dark .section-title-row h3,
html.dark .overview-item strong {
  color: #e5e7eb;
}

html.dark .yz-filter-strip,
html.dark .yz-clean-table :deep(.el-table__header th),
html.dark .code-preview,
html.dark .batch-summary,
html.dark .dialog-tip,
html.dark .overview-item {
  background: #111827;
}

@media (max-width: 1180px) {
  .overview-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .batch-detail-shell {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .yz-panel-header,
  .batch-overview-card,
  .table-footer,
  .section-title-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .filter-control,
  .search-control {
    width: 100%;
  }

  .overview-strip {
    grid-template-columns: 1fr;
  }

  .summary-metric-card {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    padding: 24px 16px;
  }

  .dialog-tip {
    margin-left: 0;
    width: 100%;
  }
}
</style>
