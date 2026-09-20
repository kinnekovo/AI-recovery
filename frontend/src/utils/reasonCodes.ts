const dictionary: Record<string, string> = {
  EVIDENCE_INSUFFICIENT: '当前证据不足，暂不改变训练安排',
  QUALITY_RECENTLY_UNSTABLE: '近期证据质量不稳定，需要复核',
  MAINTAIN_DURING_COOLDOWN: '处于观察期，保持当前设置',
  THERAPIST_OVERRIDE_ACTIVE: '治疗师人工设置正在生效',
  unexpected_decision_instability: '决策稳定性需要复核',
  state_conflict: '训练状态已发生变化',
  suspended: '当前操作类型已暂停'
}

export function explainReasonCode(code: string): string {
  return dictionary[code] ?? code.replace(/_/g, ' ').toLowerCase()
}
