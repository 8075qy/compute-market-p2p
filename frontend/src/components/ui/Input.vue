<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  modelValue: string | number | undefined
  type?: 'text' | 'password' | 'number' | 'tel' | 'email' | 'date'
  placeholder?: string
  label?: string
  error?: string
  disabled?: boolean
  readonly?: boolean
  suffix?: string
  clearable?: boolean
  maxlength?: number
}

const props = withDefaults(defineProps<Props>(), {
  type: 'text',
  placeholder: '',
  label: '',
  error: '',
  disabled: false,
  readonly: false,
  suffix: '',
  clearable: false,
  maxlength: undefined,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  blur: [event: FocusEvent]
  focus: [event: FocusEvent]
}>()

const showPassword = ref(false)
const inputRef = ref<HTMLInputElement>()

const inputType = computed(() => {
  if (props.type === 'password') {
    return showPassword.value ? 'text' : 'password'
  }
  return props.type
})

const wrapperClasses = computed(() => [
  'input-wrapper',
  { 'input-with-suffix': props.suffix || props.clearable || props.type === 'password' },
])

const inputClasses = computed(() => [
  'input',
  { 'input-error': props.error },
])
</script>

<template>
  <div :class="wrapperClasses">
    <label v-if="label" class="input-label">{{ label }}</label>
    <div class="input-inner" style="position: relative;">
      <input
        ref="inputRef"
        :type="inputType"
        :class="inputClasses"
        :placeholder="placeholder"
        :value="modelValue"
        :disabled="disabled"
        :readonly="readonly"
        :maxlength="maxlength"
        @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
        @blur="emit('blur', $event)"
        @focus="emit('focus', $event)"
        class="input"
      />
      <template v-if="props.type === 'password'">
        <button
          type="button"
          class="input-suffix"
          @click="showPassword = !showPassword"
          aria-label="切换密码可见性"
        >
          <svg v-if="showPassword" class="icon icon-sm" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" /></svg>
          <svg v-else class="icon icon-sm" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
        </button>
      </template>
      <template v-else-if="clearable && modelValue">
        <button
          type="button"
          class="input-suffix"
          @click="emit('update:modelValue', '')"
          aria-label="清除输入"
        >
          <svg class="icon icon-sm" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
        </button>
      </template>
      <template v-else-if="suffix">
        <span class="input-suffix">{{ suffix }}</span>
      </template>
    </div>
    <p v-if="error" class="input-error-message">{{ error }}</p>
  </div>
</template>

<style scoped>
/* 样式在 app.css 中定义 */
</style>