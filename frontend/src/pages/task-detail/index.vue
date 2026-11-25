<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDemanderStore } from '@/stores/demander'
import { Card, Button, Icon, Badge, Progress, StatusDot, Skeleton, EmptyState } from '@/components/ui'
import { useToast } from '@/composables/useToast'
import { onRealtime } from '@/composables/useRealtimeEvents'

const route = useRoute()
const router = useRouter()
const demanderStore = useDemanderStore()
const { success, danger, info } = useToast()

const taskId = route.params.id as string
const activeTab = ref<'overview' | 'logs' | 'result'>(route.query.tab as any || 'overview')

const tabs = [
  { key: 'overview', label: '概览', icon: 'activity' },
  { key: 'logs', label: '日志', icon: 'terminal' },
  { key: 'result', label: '结果', icon: 'file-text' },
]

const task = computed(() => demanderStore.currentTask)
const executions = computed(() => task.value?.executions || [])
const completedSlices = computed(() => executions.value.filter(e => e.status === 'completed').length)
const totalSlices = computed(() => executions.value.length)
const progressPercent = computed(() => totalSlices.value > 0 ? Math.round((completedSlices.value / totalSlices.value) * 100) : 0)
const isBatch = computed(() => task.value?.type === 'batch')
const completedWorkUnits = computed(() => task.value?.completed_work_units || 0)
const totalWorkUnits = computed(() => task.value?.total_work_units || 0)
const logs = ref<string>('')
const resultUrl = ref<string>('')
const isLoadingLogs = ref(false)
const isLoadingResult = ref(false)
let logPollTimer: number | null = null

function getStatusBadgeVariant(status: string) {
  switch (status) {
    case 'running': return 'success'
    case 'completed': return 'primary'
    case 'failed': return 'danger'
    case 'cancelled': return 'muted'
    default: return 'warning'
  }
}

function getStatusLabel(status: string) {
  switch (status) {
    case 'pending': return '待调度'
    case 'scheduling': return '调度中'
    case 'assigned': return '已分配'
    case 'running': return '运行中'
    case 'completed': return '已完成'
    case 'failed': return '失败'
    case 'cancelled': return '已取消'
    default: return status
  }
}

function formatDuration(minutes: number) {
  if (!minutes) return '0 分钟'
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h > 0 && m > 0) return `${h} 小时 ${m} 分钟`
  if (h > 0) return `${h} 小时`
  return `${m} 分钟`
}

async function loadTask() {
  await demanderStore.getTask(taskId)
}

async function loadLogs(attemptNo?: number) {
  if (isLoadingLogs.value) return
  isLoadingLogs.value = true
  try {
    const data = await demanderStore.fetchTaskLogs(taskId, attemptNo)
    logs.value = data.logs
  } catch (error: any) {
    danger(error.response?.data?.message || '加载日志失败')
  } finally {
    isLoadingLogs.value = false
  }
}

async function loadResult() {
  if (isLoadingResult.value) return
  isLoadingResult.value = true
  try {
    const data = await demanderStore.fetchTaskResult(taskId)
    resultUrl.value = data.result_url
  } catch (error: any) {
    danger(error.response?.data?.message || '加载结果失败')
  } finally {
    isLoadingResult.value = false
  }
}

async function handleRetry() {
  if (!task.value) return
  try {
    await demanderStore.retryTask(taskId)
    success('重试已提交')
    loadTask()
  } catch (error: any) {
    danger(error.response?.data?.message || '重试失败')
  }
}

async function handleCancel() {
  if (!task.value) return
  const confirmed = confirm('确定要取消该任务吗？已执行部分将按实际用量结算。')
  if (confirmed) {
    try {
      await demanderStore.cancelTask(taskId)
      success('任务已取消')
      loadTask()
    } catch (error: any) {
      danger(error.response?.data?.message || '取消失败')
    }
  }
}

function startLogPolling() {
  if (logPollTimer) return
  loadLogs()
  logPollTimer = window.setInterval(() => {
    if (task.value && (task.value.status === 'running' || task.value.status === 'scheduling' || task.value.status === 'assigned')) {
      loadLogs()
    } else {
      stopLogPolling()
    }
  }, 5000)
}

function stopLogPolling() {
  if (logPollTimer) {
    clearInterval(logPollTimer)
    logPollTimer = null
  }
}

const unsubscribeRealtime = onRealtime(({ event, data }) => {
  if (event !== 'task_status' || !data?.task_id || data.task_id !== taskId) return
  loadTask()
  if (data.status === 'completed' && activeTab.value === 'result') {
    loadResult()
  }
})

onMounted(() => {
  loadTask()
})

onBeforeUnmount(() => {
  unsubscribeRealtime()
  stopLogPolling()
})

watch(() => activeTab.value, (newTab) => {
  if (newTab === 'logs') {
    startLogPolling()
  } else {
    stopLogPolling()
  }
  if (newTab === 'result') {
    loadResult()
  }
}, { immediate: true })

// 清理定时器
import { onUnmounted } from 'vue'
onUnmounted(() => {
  stopLogPolling()
})
</script>

<template>
  <div class="page-layout">
    <div class="page-content">
      <Card v-if="demanderStore.isLoading && !task" style="padding: var(--space-32); text-align: center;">
        <Skeleton type="card" v-for="i in 3" :key="i" />
      </Card>

      <div v-else-if="task">
        <!-- 任务头部状态 -->
        <Card style="margin-bottom: var(--space-16);">
          <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-16); flex-wrap: wrap;">
            <div style="flex: 1; min-width: 200px;">
              <div style="display: flex; align-items: center; gap: var(--space-8); flex-wrap: wrap; margin-bottom: var(--space-8);">
                <h2 style="font-size: var(--text-xl); font-weight: 700; color: var(--color-text);">{{ task.title }}</h2>
                <Badge :variant="task.type === 'training' ? 'warning' : 'primary'">
                  {{ task.type === 'training' ? '训练' : task.type === 'batch' ? '批处理' : '推理' }}
                </Badge>
                <Badge :variant="getStatusBadgeVariant(task.status)">
                  {{ getStatusLabel(task.status) }}
                </Badge>
              </div>
              <p style="font-size: var(--text-sm); color: var(--color-text-muted); margin-bottom: var(--space-12);">{{ task.description }}</p>
              <div style="display: flex; flex-wrap: wrap; gap: var(--space-16); font-size: var(--text-sm); color: var(--color-text-muted);">
                <span><strong>ID:</strong> {{ task.id.slice(0, 8) }}...</span>
                <span v-if="task.assigned_node_id"><strong>节点:</strong> {{ task.assigned_node_id.slice(0, 8) }}...</span>
                <span><strong>预算:</strong> {{ task.budget_points }} 分</span>
                <span><strong>最大时长:</strong> {{ formatDuration(task.timeout_minutes) }}</span>
              </div>
            </div>
            <div style="display: flex; gap: var(--space-8); flex-wrap: wrap;">
              <Button v-if="task.status === 'pending' || task.status === 'scheduling' || task.status === 'assigned' || task.status === 'running'" variant="danger" @click="handleCancel">
                <Icon name="x-circle" class="icon-md" /> 取消
              </Button>
              <Button v-if="task.status === 'failed' && task.retry_count < task.max_retries" variant="primary" @click="handleRetry">
                <Icon name="refresh-cw" class="icon-md" /> 重试 ({{ task.max_retries - task.retry_count }}次)
              </Button>
              <Button v-if="task.status === 'completed'" variant="outline" @click="activeTab = 'result'">
                <Icon name="download" class="icon-md" /> 下载结果
              </Button>
            </div>
          </div>
        </Card>

        <!-- 标签页导航 -->
        <div class="top-tabbar" style="margin: calc(var(--space-16) * -1) calc(var(--space-16) * -1) var(--space-16); padding-top: var(--space-8);">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            class="top-tabbar-item"
            :class="{ active: activeTab === tab.key }"
            @click="activeTab = tab.key as any"
          >
            <Icon :name="tab.icon" class="icon-md" style="margin-right: var(--space-4);" />
            {{ tab.label }}
          </button>
        </div>

        <!-- 概览标签页 -->
        <div v-if="activeTab === 'overview'">
          <Card style="margin-bottom: var(--space-16);">
            <h3 style="font-size: var(--text-base); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">运行环境</h3>
            <div style="display: flex; flex-direction: column; gap: var(--space-12);">
              <div>
                <label style="font-size: var(--text-xs); color: var(--color-text-muted);">Docker 镜像</label>
                <p style="font-family: var(--font-mono); font-size: var(--text-sm); color: var(--color-text); word-break: break-all;">{{ task.docker_image }}</p>
              </div>
              <div>
                <label style="font-size: var(--text-xs); color: var(--color-text-muted);">启动命令</label>
                <p style="font-family: var(--font-mono); font-size: var(--text-sm); color: var(--color-text); word-break: break-all;">{{ task.command }}</p>
              </div>
              <div v-if="Object.keys(task.env_vars || {}).length > 0">
                <label style="font-size: var(--text-xs); color: var(--color-text-muted);">环境变量</label>
                <div style="font-family: var(--font-mono); font-size: var(--text-sm); color: var(--color-text);">
                  <span v-for="(value, key) in task.env_vars" :key="key" style="display: block;">{{ key }}={{ value }}</span>
                </div>
              </div>
            </div>
          </Card>

          <Card style="margin-bottom: var(--space-16);">
            <h3 style="font-size: var(--text-base); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">算力需求</h3>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-12);">
              <div>
                <label style="font-size: var(--text-xs); color: var(--color-text-muted);">显存需求</label>
                <p style="font-size: var(--text-base); font-weight: 600; color: var(--color-text); font-family: var(--font-mono); font-variant-numeric: tabular-nums;">{{ task.required_vram_gb }} GB</p>
              </div>
              <div v-if="task.required_tflops">
                <label style="font-size: var(--text-xs); color: var(--color-text-muted);">算力需求</label>
                <p style="font-size: var(--text-base); font-weight: 600; color: var(--color-text); font-family: var(--font-mono); font-variant-numeric: tabular-nums;">{{ task.required_tflops }} TFLOPS</p>
              </div>
            </div>
          </Card>

          <Card style="margin-bottom: var(--space-16);">
            <h3 style="font-size: var(--text-base); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">执行进度</h3>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-12); margin-bottom: var(--space-16);">
              <div>
                <label style="font-size: var(--text-xs); color: var(--color-text-muted);">初始并发</label>
                <p style="font-size: var(--text-base); font-weight: 600; color: var(--color-text); font-family: var(--font-mono); font-variant-numeric: tabular-nums;">{{ task.concurrency }}</p>
              </div>
              <div>
                <label style="font-size: var(--text-xs); color: var(--color-text-muted);">最小并发</label>
                <p style="font-size: var(--text-base); font-weight: 600; color: var(--color-text); font-family: var(--font-mono); font-variant-numeric: tabular-nums;">{{ task.min_concurrency ?? task.concurrency }}</p>
              </div>
              <div>
                <label style="font-size: var(--text-xs); color: var(--color-text-muted);">最大并发</label>
                <p style="font-size: var(--text-base); font-weight: 600; color: var(--color-text); font-family: var(--font-mono); font-variant-numeric: tabular-nums;">{{ task.max_concurrency ?? task.concurrency }}</p>
              </div>
            </div>
            <div v-if="isBatch">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-8);">
                <span style="font-size: var(--text-sm); color: var(--color-text);">处理进度</span>
                <span style="font-size: var(--text-sm); color: var(--color-text-muted); font-family: var(--font-mono); font-variant-numeric: tabular-nums;">{{ completedWorkUnits }} / {{ totalWorkUnits }} 个文件</span>
              </div>
              <Progress :value="completedWorkUnits" :max="totalWorkUnits" variant="success" />
            </div>
            <div v-else-if="totalSlices > 0">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-8);">
                <span style="font-size: var(--text-sm); color: var(--color-text);">分片完成进度</span>
                <span style="font-size: var(--text-sm); color: var(--color-text-muted); font-family: var(--font-mono); font-variant-numeric: tabular-nums;">{{ completedSlices }} / {{ totalSlices }} 分片</span>
              </div>
              <Progress :value="completedSlices" :max="totalSlices" variant="success" />
            </div>
            <p v-else style="font-size: var(--text-sm); color: var(--color-text-muted); margin: 0;">任务尚未拆分分片，等待调度中...</p>
          </Card>

          <Card style="margin-bottom: var(--space-16);">
            <h3 style="font-size: var(--text-base); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">时间线</h3>
            <div style="display: flex; flex-direction: column; gap: var(--space-12);">
              <div class="timeline-item">
                <div style="font-size: var(--text-xs); color: var(--color-text-muted);">创建</div>
                <div style="font-size: var(--text-sm); color: var(--color-text); font-family: var(--font-mono); font-variant-numeric: tabular-nums;">{{ new Date(task.created_at).toLocaleString() }}</div>
              </div>
              <div v-if="task.scheduled_at" class="timeline-item">
                <div style="font-size: var(--text-xs); color: var(--color-text-muted);">调度完成</div>
                <div style="font-size: var(--text-sm); color: var(--color-text); font-family: var(--font-mono); font-variant-numeric: tabular-nums;">{{ new Date(task.scheduled_at).toLocaleString() }}</div>
              </div>
              <div v-if="task.started_at" class="timeline-item">
                <div style="font-size: var(--text-xs); color: var(--color-text-muted);">开始执行</div>
                <div style="font-size: var(--text-sm); color: var(--color-text); font-family: var(--font-mono); font-variant-numeric: tabular-nums;">{{ new Date(task.started_at).toLocaleString() }}</div>
              </div>
              <div v-if="task.completed_at" class="timeline-item">
                <div style="font-size: var(--text-xs); color: var(--color-text-muted);">{{ task.status === 'completed' ? '完成' : '失败/取消' }}</div>
                <div style="font-size: var(--text-sm); color: var(--color-text); font-family: var(--font-mono); font-variant-numeric: tabular-nums;">{{ new Date(task.completed_at).toLocaleString() }}</div>
              </div>
            </div>
          </Card>

          <Card v-if="task.error_message" style="margin-bottom: var(--space-16); background: var(--color-danger-bg); border-color: var(--color-danger);">
            <h3 style="font-size: var(--text-base); font-weight: 600; color: var(--color-danger); margin-bottom: var(--space-8);">错误信息</h3>
            <pre style="font-family: var(--font-mono); font-size: var(--text-sm); color: var(--color-danger-ink); white-space: pre-wrap; word-break: break-word;">{{ task.error_message }}</pre>
          </Card>
        </div>

        <!-- 日志标签页 -->
        <Card v-else-if="activeTab === 'logs'" style="padding: 0; min-height: 300px;">
          <div v-if="isLoadingLogs && !logs" style="padding: var(--space-32); text-align: center;">
            <Skeleton type="text" v-for="i in 10" :key="i" />
          </div>
          <pre v-else style="padding: var(--space-16); font-family: var(--font-mono); font-size: var(--text-xs); line-height: var(--leading-relaxed); color: var(--color-text); overflow-x: auto; white-space: pre-wrap; word-break: break-word; min-height: 300px;">
            {{ logs || '暂无日志' }}
          </pre>
          <div v-if="task.status === 'running' || task.status === 'scheduling' || task.status === 'assigned'" style="padding: var(--space-12) var(--space-16); border-top: 1px solid var(--color-line); font-size: var(--text-xs); color: var(--color-text-muted); text-align: center;">
            自动刷新中... (每 5 秒)
          </div>
        </Card>

        <!-- 结果标签页 -->
        <Card v-else-if="activeTab === 'result'" style="padding: var(--space-24); text-align: center;">
          <div v-if="isLoadingResult" style="padding: var(--space-32);">
            <Skeleton type="text" v-for="i in 3" :key="i" />
          </div>
          <div v-else-if="resultUrl">
            <Icon name="file-text" class="icon" style="font-size: 48px; color: var(--color-primary); margin-bottom: var(--space-16);" />
            <h3 style="font-size: var(--text-lg); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-8);">结果已就绪</h3>
            <p style="font-size: var(--text-sm); color: var(--color-text-muted); margin-bottom: var(--space-16);">点击下载任务执行结果文件</p>
            <a :href="resultUrl" target="_blank" class="btn btn-primary" style="display: inline-flex; align-items: center; gap: var(--space-8);">
              <Icon name="download" class="icon-md" /> 下载结果
            </a>
          </div>
          <div v-else style="padding: var(--space-32);">
            <EmptyState
              icon="file-text"
              title="暂无结果"
              description="任务完成后将显示结果下载链接"
            />
          </div>
        </Card>
      </div>

      <div v-else style="text-align: center; padding: var(--space-32);">
        <EmptyState
          icon="alert-circle"
          title="任务不存在"
          description="该任务可能已被删除或不属于您"
          actionLabel="返回任务列表"
          :action="() => router.push('/demand/tasks')"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.timeline-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-8) 0;
  border-bottom: 1px solid var(--color-line);
}

.timeline-item:last-child {
  border-bottom: none;
}
</style>