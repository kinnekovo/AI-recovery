export type StatusTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'

export interface StatusPresentation { label: string; tone: StatusTone; description: string }

const statuses: Record<string, StatusPresentation> = {
  formal: { label: '正式结果', tone: 'success', description: '已形成正式结果，仍应结合专业判断。' },
  review_required: { label: '需要复核', tone: 'warning', description: '存在需要专业人员确认的信息。' },
  unscorable: { label: '无法计分', tone: 'neutral', description: '当前证据不足以形成结果。' },
  unavailable: { label: '不可用', tone: 'neutral', description: '当前结果不可用。' },
  fresh: { label: '最新', tone: 'success', description: '画像已基于近期证据生成。' },
  stale: { label: '需要刷新', tone: 'warning', description: '画像可能未包含近期证据。' },
  failed: { label: '处理失败', tone: 'danger', description: '处理未完成，请检查错误后重试。' },
  shadow: { label: '影子模式', tone: 'info', description: '仅供专业人员查看，不会自动改变患者训练。' },
  experimental: { label: '实验性', tone: 'neutral', description: '工程验证阶段，不能作为临床结论。' },
  provisional: { label: '暂定', tone: 'warning', description: '已有部分证据，仍需持续验证。' },
  promoted: { label: '已晋级', tone: 'success', description: '已满足当前工程晋级规则，不代表临床有效性。' },
  suspended: { label: '已暂停', tone: 'danger', description: '当前流程被阻断，不能继续执行。' },
  eligible_for_controlled_activation: { label: '可进入受控启用', tone: 'success', description: '满足受控流程的工程条件，仍需治疗师审批。' },
  eligible_for_streamlined_evaluation: { label: '可进入简化评估', tone: 'success', description: '具备后续流程简化评估的工程条件，当前仍需治疗师审批。' },
  manual_only: { label: '仅人工流程', tone: 'info', description: '建议持续保留人工审批。' },
  controlled: { label: '受控运行', tone: 'info', description: '当前操作仍受审批、范围和冲突门控。' },
  insufficient_evidence: { label: '证据不足', tone: 'neutral', description: '尚无足够证据支持进一步判断。' },
  insufficient: { label: '记录形成中', tone: 'neutral', description: '完成更多训练或评估后将逐步形成记录。' },
  pending_review: { label: '待审批', tone: 'warning', description: '等待治疗师审批。' },
  approved: { label: '已批准', tone: 'info', description: '已批准，但尚未执行。' },
  rejected: { label: '已拒绝', tone: 'neutral', description: '提案已被拒绝。' },
  applied: { label: '已应用', tone: 'success', description: '后端已确认应用。' },
  rolled_back: { label: '已回滚', tone: 'warning', description: '已恢复执行前状态。' },
  expired: { label: '已过期', tone: 'neutral', description: '该提案已超过有效期，不能再执行。' },
  frozen: { label: '已冻结', tone: 'info', description: '数据集已冻结，不能继续编辑。' },
  draft: { label: '草稿', tone: 'neutral', description: '数据集仍可编辑。' }
}

export function presentStatus(status?: string | null): StatusPresentation {
  if (!status) return { label: '未提供', tone: 'neutral', description: '后端未提供状态。' }
  return statuses[status] ?? { label: status.replace(/_/g, ' '), tone: 'neutral', description: '后端返回的状态。' }
}
