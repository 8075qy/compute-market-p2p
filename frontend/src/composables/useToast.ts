let toastInstance: {
  success: (msg: string, duration?: number) => void
  warning: (msg: string, duration?: number) => void
  danger: (msg: string, duration?: number) => void
  info: (msg: string, duration?: number) => void
} | null = null

export function provideToast(instance: typeof toastInstance) {
  toastInstance = instance
}

export function useToast() {
  return {
    success: (msg: string, duration?: number) => {
      if (toastInstance) toastInstance.success(msg, duration)
      else console.log('[SUCCESS]', msg)
    },
    warning: (msg: string, duration?: number) => {
      if (toastInstance) toastInstance.warning(msg, duration)
      else console.log('[WARNING]', msg)
    },
    danger: (msg: string, duration?: number) => {
      if (toastInstance) toastInstance.danger(msg, duration)
      else console.log('[ERROR]', msg)
    },
    info: (msg: string, duration?: number) => {
      if (toastInstance) toastInstance.info(msg, duration)
      else console.log('[INFO]', msg)
    },
  }
}