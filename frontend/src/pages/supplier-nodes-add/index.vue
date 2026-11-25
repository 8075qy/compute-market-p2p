<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSupplierStore } from '@/stores/supplier'
import { Button, Input, Card, Badge, Icon } from '@/components/ui'
import { useToast } from '@/composables/useToast'
import { detectGpu } from '@/composables/useGpuDetect'
import type { GpuSpec } from '@/types'

const router = useRouter()
const supplierStore = useSupplierStore()
const { success, danger } = useToast()

const form = reactive({
  name: '',
  gpu_model: '',
  vram_gb: 0,
  peak_tflops: 0,
  gpu_count: 1,
  docker_image: '',
})

const isSubmitting = ref(false)
const detectingGpu = ref(false)

const gpuPresets = ref<GpuSpec[]>([])

const nameError = computed(() => {
  if (!form.name.trim()) return '请输入节点名称'
  if (form.name.length > 64) return '名称不能超过 64 字符'
  return ''
})

const gpuError = computed(() => {
  if (!form.gpu_model.trim()) return '请输入 GPU 型号'
  return ''
})

const vramError = computed(() => {
  if (form.vram_gb < 1) return '显存需大于 0'
  if (form.vram_gb > 512) return '显存不能超过 512GB'
  return ''
})

const vramHint = ref('')

const tflopsError = computed(() => {
  if (form.peak_tflops <= 0) return '峰值算力需大于 0'
  if (form.peak_tflops > 10000) return '峰值算力不能超过 10000 TFLOPS'
  return ''
})

const gpuCountError = computed(() => {
  if (form.gpu_count < 1) return '卡数需大于 0'
  if (form.gpu_count > 16) return '卡数不能超过 16'
  return ''
})

const canSubmit = computed(() => {
  return form.name.trim() &&
    form.gpu_model.trim() &&
    form.vram_gb >= 1 &&
    form.peak_tflops > 0 &&
    form.gpu_count >= 1 &&
    !nameError.value &&
    !gpuError.value &&
    !vramError.value &&
    !tflopsError.value &&
    !gpuCountError.value
})

function shortLabel(gpuModel: string) {
  return gpuModel
    .replace(/^NVIDIA GeForce /, '')
    .replace(/^NVIDIA /, '')
    .replace(/^Apple /, '')
    .replace(/^AMD Radeon /, '')
    .replace(/^AMD Instinct /, '')
    .replace(/^Intel Arc /, '')
}

function applyGpuSpec(spec: GpuSpec) {
  form.gpu_model = spec.gpu_model
  fillVram(spec)
  form.peak_tflops = spec.peak_tflops
}

// 显存填充：Apple 统一内存与消费级显卡均用规格库默认值（浏览器无法精确读取真实内存），
// 实际值由 Agent 端 system_profiler / nvidia-smi 实测后自动校准
function fillVram(spec: GpuSpec) {
  form.vram_gb = spec.vram_gb
  vramHint.value = spec.vendor === 'apple'
    ? '统一内存为常见配置默认值，请确认实际大小（如 32/64/128GB）'
    : ''
}

async function autoDetectGpu(silent = false) {
  if (detectingGpu.value) return
  detectingGpu.value = true
  try {
    const result = detectGpu()
    if (!result) {
      if (!silent) danger('无法自动探测 GPU，请手动填写或选择预设型号')
      return
    }
    form.gpu_model = result.gpu_model
    const spec = await supplierStore.matchGpuSpec(result.gpu_model)
    if (spec) {
      form.gpu_model = spec.gpu_model
      fillVram(spec)
      form.peak_tflops = spec.peak_tflops
      if (!silent) success(`已识别 GPU：${spec.gpu_model}，并自动填充显存与算力`)
    } else if (!silent) {
      success(`已识别 GPU：${result.gpu_model}，请手动补充显存与算力`)
    }
  } catch {
    if (!silent) danger('GPU 规格查询失败，请手动填写')
  } finally {
    detectingGpu.value = false
  }
}

onMounted(async () => {
  try {
    gpuPresets.value = await supplierStore.fetchGpuSpecs()
  } catch {
    // 预设列表加载失败不阻塞表单填写
  }
  if (!form.gpu_model.trim()) {
    autoDetectGpu(true)
  }
})

async function submitNode() {
  if (!canSubmit.value || isSubmitting.value) return
  isSubmitting.value = true
  try {
    await supplierStore.createNode({
      name: form.name.trim(),
      gpu_model: form.gpu_model.trim(),
      vram_gb: Math.round(form.vram_gb),
      peak_tflops: form.peak_tflops,
      gpu_count: form.gpu_count,
      docker_image: form.docker_image.trim() || undefined,
    })
    success('节点添加成功')
    router.replace('/supplier/nodes')
  } catch (error: any) {
    danger(error.response?.data?.message || '添加失败')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="page-layout">
    <div class="page-content">
      <form @submit.prevent="submitNode">
        <!-- 接入说明 -->
        <Card style="margin-bottom: var(--space-16); background: var(--color-primary-hover); border-color: var(--color-primary);">
          <div style="display: flex; gap: var(--space-12);">
            <Icon name="info" class="icon-md" style="color: var(--color-primary); flex-shrink: 0; margin-top: 2px;" />
            <div style="font-size: var(--text-sm); color: var(--color-primary-ink); line-height: 1.6;">
              <p style="margin: 0; font-weight: 600;">设备如何接入中心？</p>
              <p style="margin: var(--space-4) 0 0;">
                在此登记节点基础信息后，节点以「离线」状态入库。设备真实执行算力，请在设备上运行
                <span style="font-weight: 600;">供给方 Agent</span>，节点上线后即可被调度派单。
              </p>
              <p style="margin: var(--space-4) 0 0; opacity: 0.8;">
                点击「自动探测」读取本机 GPU 型号，或手动填写以下参数；显存与算力请按设备实际规格补充。
              </p>
            </div>
          </div>
        </Card>

        <!-- 基本信息 -->
        <Card style="margin-bottom: var(--space-16);">
          <h2 style="font-size: var(--text-lg); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">基本信息</h2>
          <div style="display: flex; flex-direction: column; gap: var(--space-16);">
            <Input
              v-model="form.name"
              label="节点名称"
              placeholder="例如：我的 RTX 4090 工作站"
              :error="nameError"
              clearable
              :maxlength="64"
            />
            <Input
              v-model="form.gpu_model"
              label="GPU 型号"
              placeholder="例如：NVIDIA GeForce RTX 4090"
              :error="gpuError"
              clearable
            />
            <button
              type="button"
              class="btn btn-outline btn-sm"
              style="align-self: flex-start;"
              :disabled="detectingGpu"
              @click="autoDetectGpu()"
            >
              <Icon name="gpu" class="icon-sm" /> {{ detectingGpu ? '探测中…' : '自动探测本机 GPU' }}
            </button>
          </div>
        </Card>

        <!-- 算力规格 -->
        <Card style="margin-bottom: var(--space-16);">
          <h2 style="font-size: var(--text-lg); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">算力规格</h2>
          <div style="display: flex; flex-direction: column; gap: var(--space-16);">
            <div>
              <label class="input-label">快速选择 GPU 型号</label>
              <div style="display: flex; flex-wrap: wrap; gap: var(--space-8); margin-bottom: var(--space-12);">
                <button
                  v-for="spec in gpuPresets"
                  :key="spec.gpu_model"
                  type="button"
                  class="btn btn-outline btn-sm"
                  :class="{ 'btn-primary': form.gpu_model === spec.gpu_model }"
                  @click="applyGpuSpec(spec)"
                >
                  {{ shortLabel(spec.gpu_model) }}
                </button>
              </div>
            </div>
            <div style="display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-12);">
              <Input
                v-model.number="form.vram_gb"
                type="number"
                label="显存（单卡）"
                placeholder="GB"
                :error="vramError"
              />
              <span style="color: var(--color-text-muted); margin-top: 20px;">GB</span>
              <Input
                v-model.number="form.gpu_count"
                type="number"
                label="GPU 卡数"
                placeholder="1"
                :error="gpuCountError"
              />
              <span style="color: var(--color-text-muted); margin-top: 20px;">卡</span>
              <Input
                v-model.number="form.peak_tflops"
                type="number"
                label="峰值算力（单卡）"
                placeholder="TFLOPS"
                :error="tflopsError"
              />
              <span style="color: var(--color-text-muted); margin-top: 20px;">TFLOPS</span>
            </div>
            <p v-if="form.gpu_count > 1" style="font-size: var(--text-sm); color: var(--color-text-muted);">
              整机总显存 {{ form.vram_gb * form.gpu_count }} GB · 总算力 {{ (form.peak_tflops * form.gpu_count).toFixed(2) }} TFLOPS
            </p>
            <p v-if="vramHint" style="font-size: var(--text-sm); color: var(--color-text-muted);">{{ vramHint }}</p>
          </div>
        </Card>

        <!-- 运行环境（可选） -->
        <Card style="margin-bottom: var(--space-16);">
          <h2 style="font-size: var(--text-lg); font-weight: 600; color: var(--color-text); margin-bottom: var(--space-16);">运行环境（可选）</h2>
          <Input
            v-model="form.docker_image"
            label="Docker 镜像"
            placeholder="例如：pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime"
            clearable
          />
        </Card>

        <!-- 提交 -->
        <Button variant="primary" block :loading="isSubmitting" type="submit" :disabled="!canSubmit" style="margin-bottom: var(--space-32);">
          <Icon name="check" class="icon-md" /> 添加节点
        </Button>
      </form>
    </div>
  </div>
</template>

<style scoped>
/* 额外样式 */
</style>