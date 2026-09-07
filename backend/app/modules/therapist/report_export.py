from html import escape

from app.modules.therapist.schema import TherapistStageReportRead


def render_stage_report_html(report: TherapistStageReportRead) -> str:
    summary = report.process_summary
    assessment_rows = "\n".join(
        f"""
        <tr>
          <td>{escape(item.assessment_type)}</td>
          <td>{escape(item.review_status)}</td>
          <td>{escape(_date(item.assessed_at))}</td>
          <td>{escape(item.therapist_notes or "-")}</td>
        </tr>
        """
        for item in report.assessments
    ) or "<tr><td colspan=\"4\">暂无阶段评估。</td></tr>"
    notes = "".join(f"<li>{escape(note)}</li>" for note in report.therapist_notes) or "<li>暂无治疗师备注。</li>"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>{escape(report.username)} - 阶段训练报告</title>
  <style>
    @page {{ margin: 18mm; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: #1f322a;
      font-family: "Microsoft YaHei", "Noto Sans CJK SC", Arial, sans-serif;
      line-height: 1.6;
    }}
    header {{ border-bottom: 2px solid #2f9e73; padding-bottom: 14px; margin-bottom: 22px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    h2 {{ margin: 24px 0 10px; font-size: 18px; }}
    p {{ margin: 0; color: #40524b; }}
    .meta {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 22px; margin-top: 12px; }}
    .cards {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }}
    .card {{ border: 1px solid #dce7e1; border-radius: 8px; padding: 12px; }}
    .card strong {{ display: block; color: #1f4fb8; font-size: 22px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
    th, td {{ border: 1px solid #dce7e1; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #eef6f2; }}
    ul {{ margin: 8px 0 0; padding-left: 20px; }}
    .print-actions {{ margin: 18px 0; }}
    .print-actions button {{ padding: 9px 14px; border: 0; border-radius: 8px; background: #2f9e73; color: white; font-weight: 700; }}
    @media print {{ .print-actions {{ display: none; }} }}
  </style>
</head>
<body>
  <header>
    <h1>阶段训练报告</h1>
    <p>{escape(report.username)} 的训练、过程指标与复核备注汇总。本报告用于治疗师复盘，不代表临床诊断。</p>
    <div class="meta">
      <span>患者 ID：{escape(str(report.patient_user_id))}</span>
      <span>报告范围：{escape(_range_label(report))}</span>
      <span>训练次数：{report.training_count}</span>
      <span>已分析次数：{report.analyzed_attempt_count}</span>
    </div>
  </header>
  <div class="print-actions"><button onclick="window.print()">打印或另存为 PDF</button></div>
  <section>
    <h2>质控概览</h2>
    <div class="cards">
      <div class="card"><strong>{report.failed_analysis_count}</strong><span>分析失败</span></div>
      <div class="card"><strong>{report.low_quality_attempt_count}</strong><span>低质量录音</span></div>
      <div class="card"><strong>{round(report.low_quality_rate * 100, 1)}%</strong><span>低质量比例</span></div>
      <div class="card"><strong>{report.provider_failure_count}</strong><span>外部服务失败</span></div>
    </div>
  </section>
  <section>
    <h2>过程指标</h2>
    <div class="cards">
      <div class="card"><strong>{_metric(summary.avg_script_accuracy, "%")}</strong><span>表达完整度</span></div>
      <div class="card"><strong>{_metric(summary.avg_error_count, "次")}</strong><span>错误次数</span></div>
      <div class="card"><strong>{_metric(summary.avg_speech_rate, "字/min")}</strong><span>言语速率</span></div>
      <div class="card"><strong>{_metric(summary.avg_loudness, "dBA")}</strong><span>声音响度</span></div>
    </div>
    <p>{escape(summary.summary)}</p>
  </section>
  <section>
    <h2>阶段评估</h2>
    <table>
      <thead><tr><th>类型</th><th>状态</th><th>时间</th><th>治疗师备注</th></tr></thead>
      <tbody>{assessment_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>治疗师备注</h2>
    <ul>{notes}</ul>
  </section>
</body>
</html>"""


def _metric(value: float | None, unit: str) -> str:
    if value is None:
        return "--"
    text = str(int(value)) if float(value).is_integer() else f"{value:.1f}"
    return f"{text}{unit}"


def _date(value) -> str:
    return value.strftime("%Y-%m-%d %H:%M")


def _range_label(report: TherapistStageReportRead) -> str:
    if report.date_from and report.date_to:
        return f"{_date(report.date_from)} 至 {_date(report.date_to)}"
    if report.date_from:
        return f"{_date(report.date_from)} 至今"
    if report.date_to:
        return f"截至 {_date(report.date_to)}"
    return "全部记录"
