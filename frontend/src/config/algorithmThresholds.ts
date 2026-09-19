export type VersionedAlgorithmValue<T> = {
  value: T
  unit: string
  domain: string
  maturity: 'E0' | 'E1' | 'E2' | 'E3' | 'E4'
  source: 'engineering heuristic' | 'expert calibrated' | 'pilot validated'
  version: string
}

const version = 'r0-engineering-safety-v1'

export const algorithmThresholds = {
  loudnessReference: {
    value: { min: -35, max: -12 },
    unit: 'dBFS',
    domain: 'repeat.voice_state',
    maturity: 'E1',
    source: 'engineering heuristic',
    version
  },
  speechRateReference: {
    value: { min: 180, max: 240 },
    unit: 'char/min',
    domain: 'repeat.fluency_efficiency',
    maturity: 'E1',
    source: 'engineering heuristic',
    version
  }
} satisfies Record<string, VersionedAlgorithmValue<unknown>>

export function loudnessBand(value: number): 'low' | 'reference' | 'high' {
  const { min, max } = algorithmThresholds.loudnessReference.value
  if (value < min) return 'low'
  if (value > max) return 'high'
  return 'reference'
}

export function speechRateBand(value: number): 'low' | 'reference' | 'high' {
  const { min, max } = algorithmThresholds.speechRateReference.value
  if (value < min) return 'low'
  if (value > max) return 'high'
  return 'reference'
}
