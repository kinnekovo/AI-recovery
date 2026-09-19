import { algorithmThresholds, loudnessBand, speechRateBand } from '@/config/algorithmThresholds'

export type ProcessMetricKey = 'script_accuracy' | 'error_count' | 'speech_rate' | 'loudness'
export type MetricTone = 'good' | 'watch' | 'neutral'

export const processMetricCatalog: Record<
  ProcessMetricKey,
  {
    label: string
    patientLabel: string
    unit: string
    polarity: 'positive' | 'negative' | 'neutral'
    reference: string
    patientHint: string
  }
> = {
  script_accuracy: {
    label: '表达完整度',
    patientLabel: '表达完整度',
    unit: '%',
    polarity: 'positive',
    reference: '目标 90% 以上',
    patientHint: '越完整越好'
  },
  error_count: {
    label: '错误次数',
    patientLabel: '需要留意',
    unit: '次',
    polarity: 'negative',
    reference: '目标 0-1 次',
    patientHint: '越少越好'
  },
  speech_rate: {
    label: '言语速率',
    patientLabel: '说话节奏',
    unit: '字/min',
    polarity: 'neutral',
    reference: `工程参考 ${algorithmThresholds.speechRateReference.value.min}-${algorithmThresholds.speechRateReference.value.max} 字/min`,
    patientHint: '保持自然节奏'
  },
  loudness: {
    label: '声音响度',
    patientLabel: '声音响度',
    unit: 'dBFS',
    polarity: 'neutral',
    reference: `工程参考 ${algorithmThresholds.loudnessReference.value.min} 至 ${algorithmThresholds.loudnessReference.value.max} dBFS`,
    patientHint: '声音清楚舒适'
  }
}

export function isProcessMetricKey(key: string): key is ProcessMetricKey {
  return key in processMetricCatalog
}

export function processMetricTone(key: string, value: number): MetricTone {
  if (key === 'script_accuracy') return value >= 90 ? 'good' : 'watch'
  if (key === 'error_count') return value <= 1 ? 'good' : 'watch'
  if (key === 'speech_rate') return speechRateBand(value) === 'reference' ? 'good' : 'watch'
  if (key === 'loudness') return loudnessBand(value) === 'reference' ? 'good' : 'watch'
  return 'neutral'
}

export function processMetricBrief(key: string, value: number) {
  if (key === 'script_accuracy') return value >= 90 ? '表达完整度较好' : '表达完整度需关注'
  if (key === 'error_count') return value <= 1 ? '错误较少' : '错误偏多'
  if (key === 'speech_rate') {
    if (speechRateBand(value) === 'low') return '节奏偏慢'
    if (speechRateBand(value) === 'high') return '节奏偏快'
    return '节奏稳定'
  }
  if (key === 'loudness') {
    if (loudnessBand(value) === 'low') return '声音偏轻'
    if (loudnessBand(value) === 'high') return '声音偏响'
    return '音量稳定'
  }
  return '可作为阶段参考'
}

export function formatMetricValue(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

export function formatMetricWithUnit(key: string, value: number) {
  const unit = isProcessMetricKey(key) ? processMetricCatalog[key].unit : ''
  return `${formatMetricValue(value)}${unit ? ` ${unit}` : ''}`
}

export function formatPatientMetricValue(key: ProcessMetricKey, value: number) {
  if (key === 'script_accuracy') return `${formatMetricValue(value)}%`
  if (key === 'error_count') return `${formatMetricValue(value)}处`
  if (key === 'speech_rate') {
    if (speechRateBand(value) === 'low') return '偏慢'
    if (speechRateBand(value) === 'high') return '偏快'
    return '合适'
  }
  if (key === 'loudness') {
    if (loudnessBand(value) === 'low') return '偏轻'
    if (loudnessBand(value) === 'high') return '偏响'
    return '稳定'
  }
  return formatMetricValue(value)
}
