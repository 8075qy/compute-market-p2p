export interface GpuDetectResult {
  gpu_model: string
  vendor: 'apple' | 'nvidia' | 'amd' | 'intel' | 'mobile' | 'unknown'
  raw: string
}

/**
 * 通过 WebGL 扩展探测当前设备的 GPU 渲染器名称。
 * 兼容 iOS Safari / Android Chrome / 桌面浏览器（WebGL 2 优先，回退 WebGL 1）。
 */
export function detectGpuRenderer(): string | null {
  try {
    const canvas = document.createElement('canvas')
    const gl = (canvas.getContext('webgl2') || canvas.getContext('webgl')) as
      | WebGL2RenderingContext
      | WebGLRenderingContext
      | null
    if (!gl) return null
    const ext = gl.getExtension('WEBGL_debug_renderer_info')
    if (!ext) return null
    const renderer = gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) as unknown
    return typeof renderer === 'string' && renderer.trim() ? renderer.trim() : null
  } catch {
    return null
  }
}

/**
 * 将原始渲染器字符串解析为友好的 GPU 型号。
 * 处理 Chrome 的 `ANGLE (Vendor, Renderer, ...)` 格式与各平台的图形 API 版本后缀。
 */
export function parseGpuRenderer(renderer: string): GpuDetectResult {
  let model = renderer.trim()

  const angle = model.match(/^ANGLE\s*\(([^,]+),\s*([^,]+)/i)
  if (angle) {
    model = angle[2].trim()
  }

  model = model
    .replace(/\s*(?:Direct3D|D3D|OpenGL|Vulkan|Metal)[\w.\s]*$/i, '')
    .replace(/\s*vs_\d+_\d+\s*ps_\d+_\d+/i, '')
    .replace(/\s*\(R\)\s*/g, ' ')
    .replace(/\s{2,}/g, ' ')
    .trim()

  const lower = model.toLowerCase()
  let vendor: GpuDetectResult['vendor'] = 'unknown'
  if (lower.includes('apple')) vendor = 'apple'
  else if (/nvidia|geforce|rtx|gtx|quadro|tesla|titan/.test(lower)) vendor = 'nvidia'
  else if (/amd|radeon|firepro/.test(lower)) vendor = 'amd'
  else if (/intel|iris|uhd|hd graphics/.test(lower)) vendor = 'intel'
  else if (/adreno|mali|powervr|imgtech/.test(lower)) vendor = 'mobile'

  return { gpu_model: model, vendor, raw: renderer.trim() }
}

export function detectGpu(): GpuDetectResult | null {
  const renderer = detectGpuRenderer()
  if (!renderer) return null
  return parseGpuRenderer(renderer)
}