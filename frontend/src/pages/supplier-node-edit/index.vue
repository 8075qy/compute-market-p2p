<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSupplierStore } from '@/stores/supplier'
import { Button, Input, Card, Icon } from '@/components/ui'
import { useToast } from '@/composables/useToast'
import type { GpuSpec } from '@/types'

const route = useRoute()
const router = useRouter()
const supplierStore = useSupplierStore()
const { success, danger } = useToast()

const nodeId = route.params.id as string

const form = reactive({
  name: '',
  gpu_model: '',
  vram_gb: 0,
  peak_tflops: 0,
  gpu_count: 1,
})

const isSubmitting = ref(false)
const isLoading = ref(false)
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
  form.vram_gb = spec.vram_gb
  form.peak_tflops = spec.peak_tflops
}

async function loadNode() {
  isLoading.value = true
  try {
    const node = await supplierStore.getNode(nodeId)
    form.name = node.name
    form.gpu_model = node.gpu_model
    form.vram_gb = node.vram_gb
    form.peak_tflops = node.peak_tflops
    form.gpu_count = node.gpu_count || 1
  } catch (error: any) {
    danger(error.response?.data?.message || '加载节点失败')
  } finally {
    isLoading.value = false
  }
}

async function submitNode() {
  if (!canSubmit.value || isSubmitting.value) return
  isSubmitting.value = true
  try {
    await supplierStore.updateNode(nodeId, {
      name: form.name.trim(),
      gpu_model: form.gpu_model.trim(),
      vram_gb: Math.round(form.vram_gb),
      peak_tflops: form.peak_tflops,
      gpu_count: form.gpu_count,
    })
    success('节点已更新')
    router.replace(`/supplier/nodes/${nodeId}`)
  } catch (error: any) {
    danger(error.response?.data?.message || '更新失败')
  } finally {
    isSubmitting.value = false
  }
}

onMounted(async () => {
  loadNode()
  try {
    gpuPresets.value = await supplierStore.fetchGpuSpecs()
  } catch {
    // 预设列表加载失败不阻塞表单编辑
  }
})
</script>

<template>
  <div class="page-layout">
    <div class="page-content">
      <div class="detail-header">
        <div class="detail-header-left">
          <button type="button" class="back-btn" aria-label="返回" @click="router.back()">
            <Icon name="chevron-left" class="icon-md" />
          </button>
          <div>
            <h2 class="detail-title">编辑节点</h2>
            <p class="detail-subtitle">{{ form.name || '加载中...' }}</p>
          </div>
        </div>
      </div>

      <form @submit.prevent="submitNode">
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
          </div>
        </Card>

        <!-- 提交 -->
        <Button variant="primary" block :loading="isSubmitting" type="submit" :disabled="!canSubmit || isLoading" style="margin-bottom: var(--space-32);">
          <Icon name="check" class="icon-md" /> 保存修改
        </Button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-12);
  margin-bottom: var(--space-16);
}

.detail-header-left {
  display: flex;
  align-items: center;
  gap: var(--space-8);
}

.back-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  color: var(--color-text-secondary);
  background: var(--color-surface);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-md);
  flex-shrink: 0;
}

.detail-title {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--color-text);
}

.detail-subtitle {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  margin-top: var(--space-4);
}
</style>