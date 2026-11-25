<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDemanderStore } from '@/stores/demander'
import { usePlatformStore } from '@/stores/platform'
import { Button, Input, Card, Radio, Badge, Icon, Progress, Switch } from '@/components/ui'
import { useToast } from '@/composables/useToast'

const router = useRouter()
const demanderStore = useDemanderStore()
const platformStore = usePlatformStore()
const { success, danger, warning } = useToast()

const form = reactive({
  type: 'inference' as 'inference' | 'training' | 'batch',
  title: '',
  description: '',
  model_source: 'platform' as 'platform' | 'upload',
  model_id: '',
  model_file_key: '',
  model_file_size: undefined as number | undefined,
  input_file_key: '',
  input_file_size: undefined as number | undefined,
  batch_size: 0,
  docker_image: '',
  command: '',
  env_vars: {} as Record<string, string>,
  required_vram_gb: 8,
  required_tflops: undefined as number | undefined,
  concurrency: 1,
  min_concurrency: 1,
  max_concurrency: undefined as number | undefined,
  budget_points: 100,
  timeout_minutes: 120,
})

const envVarsText = ref('')
const isSubmitting = ref(false)
const selectedFile = ref<File | null>(null)
const isUploading = ref(false)
const uploadedFileName = ref('')
const uploadedFileSize = ref(0)
const modelsLoading = ref(false)
const inputFile = ref<File | null>(null)
const isUploadingInput = ref(false)
const inputFileCount = ref(0)
const inputFileSize = ref(0)
const inputFileName = ref('')
const showAdvanced = ref(false)

const MIN_BUDGET = 10
const MIN_TIMEOUT_MINUTES = 5
const MAX_TIMEOUT_MINUTES = 10080
const MIN_CONCURRENCY = 1
const MAX_CONCURRENCY = 10

const durationHours = computed({
  get: () => form.timeout_minutes / 60,
  set: (hours: number) => {
    form.timeout_minutes = Math.round(hours * 60)
  },
})

function formatDuration(minutes: number) {
  if (!minutes) return '0 分钟'
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h > 0 && m > 0) return `${h} 小时 ${m} 分钟`
  if (h > 0) return `${h} 小时`
  return `${m} 分钟`
}

function formatSize(bytes: number) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  selectedFile.value = file
  uploadModel()
  input.value = ''
}

async function uploadModel() {
  const file = selectedFile.value
  if (!file || isUploading.value) return
  isUploading.value = true
  try {
    const result = await demanderStore.uploadModelFile(file)
    form.model_source = 'upload'
    form.model_file_key = result.object_key
    form.model_file_size = result.size
    uploadedFileName.value = file.name
    uploadedFileSize.value = result.size
    success('模型上传成功')
  } catch (error: any) {
    danger(error.response?.data?.message || error.message || '模型上传失败')
  } finally {
    isUploading.value = false
  }
}

function onInputFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  inputFile.value = file
  uploadInput()
  input.value = ''
}

async function uploadInput() {
  const file = inputFile.value
  if (!file || isUploadingInput.value) return
  isUploadingInput.value = true
  try {
    const result = await demanderStore.uploadInputFile(file)
    form.input_file_key = result.object_key
    form.input_file_size = result.file_size
    inputFileCount.value = result.file_count
    inputFileSize.value = result.file_size
    inputFileName.value = file.name
    success(`数据包上传成功，检测到 ${result.file_count} 个文件`)
  } catch (error: any) {
    danger(error.response?.data?.message || error.message || '数据包上传失败')
  } finally {
    isUploadingInput.value = false
  }
}

async function loadModels() {
  modelsLoading.value = true
  try {
    await platformStore.fetchModels()
  } catch (error: any) {
    danger(error.response?.data?.message || '加载模型列表失败')
  } finally {
    modelsLoading.value = false
  }
}

function selectModel(modelId: string) {
  form.model_id = modelId
}

onMounted(loadModels)

const budgetError = computed(() => {
  if (form.budget_points < MIN_BUDGET) return `预算不能低于 ${MIN_BUDGET} 分`
  if (form.budget_points > (platformStore.account?.balance_points || 0)) return '预算超过账户可用余额'
  return ''
})

const dockerImageError = computed(() => {
  if (!form.docker_image.trim()) return '请输入 Docker 镜像地址'
  return ''
})

const titleError = computed(() => {
  if (!form.title.trim()) return '请输入任务标题'
  if (form.title.length > 50) return '标题不能超过 50 字符'
  return ''
})

const concurrencyError = computed(() => {
  const concurrency = form.concurrency
  const minConcurrency = form.min_concurrency
  const maxConcurrency = form.max_concurrency || undefined
  if (!Number.isInteger(concurrency) || concurrency < MIN_CONCURRENCY || concurrency > MAX_CONCURRENCY) {
    return `初始并发需为 ${MIN_CONCURRENCY}-${MAX_CONCURRENCY} 的整数`
  }
  if (!Number.isInteger(minConcurrency) || minConcurrency < MIN_CONCURRENCY || minConcurrency > MAX_CONCURRENCY) {
    return `最小并发需为 ${MIN_CONCURRENCY}-${MAX_CONCURRENCY} 的整数`
  }
  if (maxConcurrency != null && (!Number.isInteger(maxConcurrency) || maxConcurrency < MIN_CONCURRENCY || maxConcurrency > MAX_CONCURRENCY)) {
    return `最大并发需为 ${MIN_CONCURRENCY}-${MAX_CONCURRENCY} 的整数`
  }
  if (concurrency < minConcurrency) return '初始并发不能低于最小并发'
  if (maxConcurrency != null && concurrency > maxConcurrency) return '初始并发不能超过最大并发'
  if (maxConcurrency != null && minConcurrency > maxConcurrency) return '最小并发不能超过最大并发'
  return ''
})

const canSubmit = computed(() => {
  const baseOk = form.title.trim() &&
         form.budget_points >= MIN_BUDGET &&
         !budgetError.value &&
         !titleError.value

  if (form.type === 'batch') {
    return baseOk &&
           form.input_file_key !== '' &&
           form.docker_image.trim() !== '' &&
           !dockerImageError.value
  }

  return baseOk &&
         form.docker_image.trim() &&
         form.command.trim() &&
         form.required_vram_gb > 0 &&
         form.timeout_minutes >= MIN_TIMEOUT_MINUTES &&
         !dockerImageError.value &&
         !concurrencyError.value
})

const taskTypes = [
  { value: 'inference', label: '推理任务', desc: '模型推理、批量预测、实时服务', icon: 'activity' },
  { value: 'training', label: '训练任务', desc: '模型训练、微调、分布式训练', icon: 'trending-up' },
  { value: 'batch', label: '批处理任务', desc: '批量处理文件、图片、音频等数据', icon: 'file-text' },
]

const gpuPresets = [
  { label: 'RTX 3080 (10GB)', vram: 10, tflops: 30 },
  { label: 'RTX 3090 (24GB)', vram: 24, tflops: 36 },
  { label: 'RTX 4090 (24GB)', vram: 24, tflops: 83 },
  { label: 'A100 (40GB)', vram: 40, tflops: 156 },
  { label: 'A100 (80GB)', vram: 80, tflops: 156 },
  { label: 'H100 (80GB)', vram: 80, tflops: 300 },
]

async function submitTask() {
  if (!canSubmit.value || isSubmitting.value) return
  if (form.type === 'batch' && !form.input_file_key) {
    danger('请先上传数据包')
    return
  }
  if (form.model_source === 'upload' && !form.model_file_key) {
    danger('请先上传模型文件')
    return
  }
  if (form.model_source === 'platform' && !form.model_id) {
    danger('请先选择平台模型')
    return
  }

  isSubmitting.value = true
  try {
    // 解析环境变量
    const envVars: Record<string, string> = {}
    envVarsText.value.split('\n').forEach(line => {
      const [key, ...valueParts] = line.split('=')
      if (key && valueParts.length) {
        envVars[key.trim()] = valueParts.join('=').trim()
      }
    })

    await demanderStore.createTask({
      type: form.type,
      title: form.title.trim(),
      description: form.description.trim(),
      docker_image: form.docker_image.trim(),
      command: form.command.trim(),
      env_vars: envVars,
      required_vram_gb: form.required_vram_gb,
      required_tflops: form.required_tflops,
      concurrency: form.concurrency,
      min_concurrency: form.min_concurrency,
      max_concurrency: form.max_concurrency || undefined,
      model_source: form.model_source,
      model_id: form.model_id || undefined,
      model_file_key: form.model_file_key || undefined,
      model_file_size: form.model_file_size,
      input_file_key: form.type === 'batch' ? form.input_file_key : undefined,
      input_file_size: form.type === 'batch' ? form.input_file_size : undefined,
      batch_size: form.type === 'batch' ? form.batch_size : undefined,
      budget_points: form.budget_points,
      timeout_minutes: form.timeout_minutes,
    })

    success('任务发布成功，等待调度中...')
    router.replace('/demand/tasks')
  } catch (error: any) {
    danger(error.response?.data?.message || '发布失败')
  } finally {
    isSubmitting.value = false
  }
}

function applyPreset(preset: { vram: number; tflops: number }) {
  form.required_vram_gb = preset.vram
  form.required_tflops = preset.tflops
}
</script>

<template>
  <div class="page-layout">
    <div class="page-content">
      <form @submit.prevent="submitTask">
        <!-- 任务类型选择 -->
        <Card style="margin-bottom: var(--space-16);">
          <h2 style="font-size: var(--text-lg); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">任务类型</h2>
          <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-12);">
            <label
              v-for="type in taskTypes"
              :key="type.value"
              class="radio-item"
              :class="{ checked: form.type === type.value }"
              @click="form.type = type.value as any"
            >
              <input
                type="radio"
                class="radio-input"
                :checked="form.type === type.value"
                @change.stop
              />
              <div style="display: flex; align-items: center; gap: var(--space-12);">
                <div :style="{ width: '40px', height: '40px', borderRadius: 'var(--radius-card)', background: type.value === 'training' ? 'var(--color-warning-bg)' : 'var(--color-primary-hover)', display: 'flex', alignItems: 'center', justifyContent: 'center' }">
                  <Icon :name="type.icon" class="icon-md" :style="{ color: type.value === 'training' ? 'var(--color-warning)' : 'var(--color-primary)' }" />
                </div>
                <div>
                  <div style="font-weight: 600; color: var(--color-text);">{{ type.label }}</div>
                  <div style="font-size: var(--text-xs); color: var(--color-text-muted);">{{ type.desc }}</div>
                </div>
              </div>
            </label>
          </div>
        </Card>

        <!-- 数据包上传（批处理） -->
        <Card v-if="form.type === 'batch'" style="margin-bottom: var(--space-16);">
          <h2 style="font-size: var(--text-lg); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">数据包</h2>
          <label
            :style="{
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              gap: 'var(--space-8)', padding: 'var(--space-24)',
              border: '1px dashed var(--color-line)', borderRadius: 'var(--radius-card)',
              background: 'var(--color-surface)', cursor: isUploadingInput ? 'not-allowed' : 'pointer',
              opacity: isUploadingInput ? 0.6 : 1,
            }"
          >
            <input
              type="file"
              class="radio-input"
              :disabled="isUploadingInput"
              accept=".zip"
              @change="onInputFileChange"
            />
            <Icon name="upload" class="icon-lg" style="color: var(--color-primary);" />
            <span style="font-weight: 500; color: var(--color-text);">{{ isUploadingInput ? '上传中...' : '点击上传数据包' }}</span>
            <span style="font-size: var(--text-xs); color: var(--color-text-muted);">zip 格式，系统会自动识别包内文件数量</span>
          </label>

          <div v-if="inputFileCount > 0" style="display: flex; align-items: center; gap: var(--space-8); font-size: var(--text-sm); margin-top: var(--space-12);">
            <Icon name="check-circle" class="icon-md" style="color: var(--color-success);" />
            <span style="color: var(--color-text);">检测到 {{ inputFileCount }} 个文件（{{ formatSize(inputFileSize) }}）</span>
          </div>
        </Card>

        <!-- 模型来源 -->
        <Card style="margin-bottom: var(--space-16);">
          <h2 style="font-size: var(--text-lg); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">模型来源</h2>
          <div style="display: flex; flex-direction: column; gap: var(--space-12);">
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-12);">
              <label
                class="radio-item"
                :class="{ checked: form.model_source === 'platform' }"
                @click="form.model_source = 'platform'"
              >
                <input type="radio" class="radio-input" :checked="form.model_source === 'platform'" @change.stop />
                <div style="display: flex; align-items: center; gap: var(--space-12);">
                  <div :style="{ width: '40px', height: '40px', borderRadius: 'var(--radius-card)', background: 'var(--color-primary-hover)', display: 'flex', alignItems: 'center', justifyContent: 'center' }">
                    <Icon name="cpu" class="icon-md" style="color: var(--color-primary);" />
                  </div>
                  <div>
                    <div style="font-weight: 600; color: var(--color-text);">平台模型</div>
                    <div style="font-size: var(--text-xs); color: var(--color-text-muted);">使用平台模型库</div>
                  </div>
                </div>
              </label>
              <label
                class="radio-item"
                :class="{ checked: form.model_source === 'upload' }"
                @click="form.model_source = 'upload'"
              >
                <input type="radio" class="radio-input" :checked="form.model_source === 'upload'" @change.stop />
                <div style="display: flex; align-items: center; gap: var(--space-12);">
                  <div :style="{ width: '40px', height: '40px', borderRadius: 'var(--radius-card)', background: 'var(--color-warning-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center' }">
                    <Icon name="upload" class="icon-md" style="color: var(--color-warning);" />
                  </div>
                  <div>
                    <div style="font-weight: 600; color: var(--color-text);">上传模型</div>
                    <div style="font-size: var(--text-xs); color: var(--color-text-muted);">上传自有模型文件</div>
                  </div>
                </div>
              </label>
            </div>

            <div v-if="form.model_source === 'platform'" style="display: flex; flex-direction: column; gap: var(--space-8);">
              <p v-if="modelsLoading" style="font-size: var(--text-sm); color: var(--color-text-muted); margin: 0;">正在加载平台模型...</p>
              <p v-else-if="platformStore.models.length === 0" style="font-size: var(--text-sm); color: var(--color-text-muted); margin: 0;">暂无可选平台模型，可改用「上传模型」。</p>
              <template v-else>
                <label
                  v-for="model in platformStore.models"
                  :key="model.id"
                  class="radio-item"
                  :class="{ checked: form.model_id === model.id }"
                  @click="selectModel(model.id)"
                >
                  <input type="radio" class="radio-input" :checked="form.model_id === model.id" @change.stop />
                  <div class="radio-content">
                    <div style="display: flex; align-items: center; justify-content: space-between; gap: var(--space-8);">
                      <span class="radio-label">{{ model.name }}</span>
                      <Badge>{{ model.framework }}</Badge>
                    </div>
                    <span class="radio-desc">{{ formatSize(model.size_bytes) }} · 推荐显存 {{ model.required_vram_gb }}GB</span>
                  </div>
                </label>
              </template>
            </div>

            <div v-else style="display: flex; flex-direction: column; gap: var(--space-8);">
              <label
                :style="{
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                  gap: 'var(--space-8)', padding: 'var(--space-24)',
                  border: '1px dashed var(--color-line)', borderRadius: 'var(--radius-card)',
                  background: 'var(--color-surface)', cursor: isUploading ? 'not-allowed' : 'pointer',
                  opacity: isUploading ? 0.6 : 1,
                }"
              >
                <input
                  type="file"
                  class="radio-input"
                  :disabled="isUploading"
                  accept=".pt,.pth,.bin,.safetensors,.onnx,.gguf,.zip,.tar,.gz"
                  @change="onFileChange"
                />
                <Icon name="upload" class="icon-lg" style="color: var(--color-primary);" />
                <span style="font-weight: 500; color: var(--color-text);">{{ isUploading ? '上传中...' : '点击选择模型文件' }}</span>
                <span style="font-size: var(--text-xs); color: var(--color-text-muted);">支持模型权重、ONNX、GGUF、压缩包等格式</span>
              </label>

              <div v-if="uploadedFileName" style="display: flex; align-items: center; gap: var(--space-8); font-size: var(--text-sm);">
                <Icon name="check-circle" class="icon-md" style="color: var(--color-success);" />
                <span style="color: var(--color-text);">已上传：{{ uploadedFileName }}（{{ formatSize(uploadedFileSize) }}）</span>
              </div>
            </div>
          </div>
        </Card>

        <!-- 基本信息 -->
        <Card style="margin-bottom: var(--space-16);">
          <h2 style="font-size: var(--text-lg); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">基本信息</h2>
          <div style="display: flex; flex-direction: column; gap: var(--space-16);">
            <Input
              v-model="form.title"
              label="任务标题"
              placeholder="例如：Llama-2-7B 推理服务"
              :error="titleError"
              clearable
              :maxlength="50"
            />
            <Input
              v-if="form.type !== 'batch'"
              v-model="form.description"
              type="text"
              label="任务描述（可选）"
              placeholder="描述任务的具体用途、数据规模等"
            />
          </div>
        </Card>

        <!-- 运行环境 -->
        <Card style="margin-bottom: var(--space-16);">
          <h2 style="font-size: var(--text-lg); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">运行环境</h2>
          <div style="display: flex; flex-direction: column; gap: var(--space-16);">
            <Input
              v-model="form.docker_image"
              label="Docker 镜像"
              placeholder="例如：pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime"
              :error="dockerImageError"
              clearable
            />
            <Input
              v-model="form.command"
              label="启动命令"
              placeholder="例如：python train.py --epochs 10"
              clearable
            />
            <div v-if="form.type !== 'batch'">
              <label class="input-label">环境变量（每行一个 KEY=VALUE）</label>
              <textarea
                v-model="envVarsText"
                class="input"
                style="min-height: 100px; resize: vertical; font-family: var(--font-mono); font-size: var(--text-sm);"
                placeholder="CUDA_VISIBLE_DEVICES=0&#10;BATCH_SIZE=32"
              />
            </div>
          </div>
        </Card>

        <!-- 高级选项（批处理） -->
        <Card v-if="form.type === 'batch'" style="margin-bottom: var(--space-16);">
          <button
            type="button"
            @click="showAdvanced = !showAdvanced"
            style="display: flex; align-items: center; justify-content: space-between; width: 100%; background: none; border: none; padding: 0; cursor: pointer;"
          >
            <span style="font-weight: 600; color: var(--color-text);">高级选项</span>
            <Icon :name="showAdvanced ? 'chevron-up' : 'chevron-down'" class="icon-md" style="color: var(--color-text-muted);" />
          </button>
          <div v-if="showAdvanced" style="display: flex; flex-direction: column; gap: var(--space-16); margin-top: var(--space-16);">
            <Input
              v-model="form.description"
              type="text"
              label="任务描述（可选）"
              placeholder="描述任务的具体用途、数据规模等"
            />
            <div>
              <label class="input-label">环境变量（每行一个 KEY=VALUE）</label>
              <textarea
                v-model="envVarsText"
                class="input"
                style="min-height: 100px; resize: vertical; font-family: var(--font-mono); font-size: var(--text-sm);"
                placeholder="CUDA_VISIBLE_DEVICES=0&#10;BATCH_SIZE=32"
              />
            </div>
            <Input
              v-model.number="form.batch_size"
              type="number"
              label="每批处理文件数（0 表示系统自动）"
              placeholder="0"
            />
            <div>
              <label class="input-label">显存需求</label>
              <div style="display: flex; align-items: center; gap: var(--space-12);">
                <Input v-model.number="form.required_vram_gb" type="number" placeholder="GB" style="width: 100px;" />
                <span style="color: var(--color-text-muted);">GB</span>
              </div>
            </div>
            <div>
              <label class="input-label">并发</label>
              <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-12);">
                <div>
                  <span style="font-size: var(--text-xs); color: var(--color-text-muted);">初始</span>
                  <Input v-model.number="form.concurrency" type="number" placeholder="1" />
                </div>
                <div>
                  <span style="font-size: var(--text-xs); color: var(--color-text-muted);">最小</span>
                  <Input v-model.number="form.min_concurrency" type="number" placeholder="1" />
                </div>
                <div>
                  <span style="font-size: var(--text-xs); color: var(--color-text-muted);">最大</span>
                  <Input v-model.number="form.max_concurrency" type="number" placeholder="可选" />
                </div>
              </div>
              <p v-if="concurrencyError" class="input-error-message" style="margin-top: var(--space-8);">{{ concurrencyError }}</p>
            </div>
            <div>
              <label class="input-label">最大运行时长</label>
              <div style="display: flex; align-items: center; gap: var(--space-8);">
                <Input v-model.number="durationHours" type="number" placeholder="小时" style="width: 100px;" />
                <span style="color: var(--color-text-muted);">小时</span>
              </div>
            </div>
          </div>
        </Card>

        <!-- 算力需求 -->
        <Card v-if="form.type !== 'batch'" style="margin-bottom: var(--space-16);">
          <h2 style="font-size: var(--text-lg); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">算力需求</h2>
          <div style="display: flex; flex-direction: column; gap: var(--space-16);">
            <div>
              <label class="input-label">显存需求</label>
              <div style="display: flex; flex-wrap: wrap; gap: var(--space-8); margin-bottom: var(--space-8);">
                <button
                  v-for="preset in gpuPresets"
                  :key="preset.vram"
                  type="button"
                  class="btn btn-outline btn-sm"
                  :class="{ 'btn-primary': form.required_vram_gb === preset.vram && form.required_tflops === preset.tflops }"
                  @click="applyPreset(preset)"
                >
                  {{ preset.label }}
                </button>
              </div>
              <div style="display: flex; align-items: center; gap: var(--space-12);">
                <Input
                  v-model.number="form.required_vram_gb"
                  type="number"
                  placeholder="GB"
                  style="width: 100px;"
                />
                <span style="color: var(--color-text-muted);">GB</span>
                <Input
                  v-model.number="form.required_tflops"
                  type="number"
                  placeholder="TFLOPS（可选）"
                  style="flex: 1;"
                />
              </div>
            </div>
          </div>
        </Card>

        <!-- 弹性并发 -->
        <Card v-if="form.type !== 'batch'" style="margin-bottom: var(--space-16);">
          <h2 style="font-size: var(--text-lg); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-8);">弹性并发</h2>
          <p style="font-size: var(--text-xs); color: var(--color-text-muted); margin-bottom: var(--space-16);">
            任务会拆分为多个分片并行执行，系统会在 {{ MIN_CONCURRENCY }}-{{ MAX_CONCURRENCY }} 个分片间，根据可用节点与预算动态伸缩。
          </p>
          <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-12);">
            <div>
              <label class="input-label">初始并发</label>
              <Input v-model.number="form.concurrency" type="number" placeholder="1" />
            </div>
            <div>
              <label class="input-label">最小并发</label>
              <Input v-model.number="form.min_concurrency" type="number" placeholder="1" />
            </div>
            <div>
              <label class="input-label">最大并发</label>
              <Input v-model.number="form.max_concurrency" type="number" placeholder="可选" />
            </div>
          </div>
          <p v-if="concurrencyError" class="input-error-message" style="margin-top: var(--space-8);">{{ concurrencyError }}</p>
        </Card>

        <!-- 预算与时长 -->
        <Card style="margin-bottom: var(--space-16);">
          <h2 style="font-size: var(--text-lg); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">{{ form.type === 'batch' ? '预算上限' : '预算与时长' }}</h2>
          <div style="display: flex; flex-direction: column; gap: var(--space-16);">
            <div>
              <label class="input-label">预算上限</label>
              <div style="display: flex; align-items: center; gap: var(--space-8);">
                <Input
                  v-model.number="form.budget_points"
                  type="number"
                  placeholder="分"
                  style="flex: 1;"
                />
                <span style="color: var(--color-text-muted); font-size: var(--text-lg); font-weight: 600;">分</span>
              </div>
              <p v-if="budgetError" class="input-error-message">{{ budgetError }}</p>
              <p style="font-size: var(--text-xs); color: var(--color-text-muted); margin-top: var(--space-4);">
                可用余额：{{ platformStore.account?.balance_points || 0 }} 分（冻结：{{ platformStore.account?.frozen_points || 0 }} 分） · 最低 {{ MIN_BUDGET }} 分
              </p>
            </div>

            <div v-if="form.type !== 'batch'">
              <label class="input-label">最大运行时长</label>
              <div style="display: flex; align-items: center; gap: var(--space-8);">
                <Input
                  v-model.number="durationHours"
                  type="number"
                  placeholder="小时"
                  style="width: 100px;"
                />
                <span style="color: var(--color-text-muted);">小时</span>
                <div style="flex: 1; height: 4px; background: var(--color-line); border-radius: var(--radius-pill);">
                  <div
                    class="progress-bar"
                    :style="{ width: `${Math.min(form.timeout_minutes / MAX_TIMEOUT_MINUTES, 1) * 100}%` }"
                  />
                </div>
              </div>
              <p style="font-size: var(--text-xs); color: var(--color-text-muted); margin-top: var(--space-4);">
                范围：{{ formatDuration(MIN_TIMEOUT_MINUTES) }} - {{ formatDuration(MAX_TIMEOUT_MINUTES) }}（超时自动终止并结算已用时长）
              </p>
            </div>
          </div>
        </Card>

        <!-- 预估费用 -->
        <Card v-if="form.type !== 'batch'" style="margin-bottom: var(--space-16); background: var(--color-primary-hover); border-color: var(--color-primary);">
          <h2 style="font-size: var(--text-lg); font-weight: 600; color: var(--color-primary-ink); margin-bottom: var(--space-12);">预估费用</h2>
          <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-12);">
            <div>
              <div style="font-size: var(--text-xs); color: var(--color-primary-ink); opacity: 0.8;">预估总费用</div>
              <div style="font-size: var(--text-2xl); font-weight: 700; color: var(--color-primary-ink); font-family: var(--font-mono); font-variant-numeric: tabular-nums;">
                {{ (form.budget_points * (durationHours / Math.max(durationHours, 1))).toFixed(0) }} 分
              </div>
            </div>
            <div>
              <div style="font-size: var(--text-xs); color: var(--color-primary-ink); opacity: 0.8;">平台抽成 (10%)</div>
              <div style="font-size: var(--text-xl); font-weight: 700; color: var(--color-primary-ink); font-family: var(--font-mono); font-variant-numeric: tabular-nums;">
                {{ (form.budget_points * 0.1).toFixed(0) }} 分
              </div>
            </div>
            <div>
              <div style="font-size: var(--text-xs); color: var(--color-primary-ink); opacity: 0.8;">供给方到账</div>
              <div style="font-size: var(--text-xl); font-weight: 700; color: var(--color-primary-ink); font-family: var(--font-mono); font-variant-numeric: tabular-nums;">
                {{ (form.budget_points * 0.9).toFixed(0) }} 分
              </div>
            </div>
            <div>
              <div style="font-size: var(--text-xs); color: var(--color-primary-ink); opacity: 0.8;">剩余预算退回</div>
              <div style="font-size: var(--text-xl); font-weight: 700; color: var(--color-primary-ink); font-family: var(--font-mono); font-variant-numeric: tabular-nums;">
                实时退回
              </div>
            </div>
          </div>
        </Card>

        <!-- 提交按钮 -->
        <Button variant="primary" block :loading="isSubmitting" type="submit" :disabled="!canSubmit" style="margin-bottom: var(--space-32);">
          <Icon name="send" class="icon-md" /> 发布任务
        </Button>
      </form>
    </div>
  </div>
</template>

<style scoped>
/* 额外样式 */
</style>