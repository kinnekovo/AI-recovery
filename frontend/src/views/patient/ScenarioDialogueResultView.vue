<template>
  <section class="page-stack scenario-result-page">
    <div class="page-heading">
      <span class="kicker">场景表达小结</span>
      <h1>{{ goalHeading }}</h1>
      <p>这是对整段交流的训练观察，不是诊断。重点是对方最终能否理解并回应你的需要。</p>
    </div>
    <section v-if="loading" class="primary-panel">正在整理这段对话…</section>
    <p v-else-if="error" class="error-text">{{ error }}</p>
    <template v-else-if="evaluation">
      <section class="scenario-summary-panel">
        <h2>对方最终理解了什么</h2>
        <p>{{ goalDescription }}</p>
        <p v-if="evaluation.review_status === 'pending_semantic_review'" class="scenario-review-note">本次转写或语义证据仍需复核，因此没有生成正式总分。</p>
      </section>
      <section class="scenario-evidence-grid" aria-label="本次沟通观察">
        <article><h2>已经说清的信息</h2><p>{{ informationDescription }}</p></article>
        <article><h2>回应追问</h2><p>{{ Math.round(evaluation.response_score) }}% 的本轮表达与当前对话有关。</p></article>
        <article><h2>独立完成</h2><p>{{ independenceDescription }}</p></article>
      </section>
      <section class="scenario-next-step">
        <h2>下一次最值得练的一件事</h2>
        <p>{{ nextStep }}</p>
      </section>
      <details class="scenario-secondary-observation">
        <summary>查看附属训练数据</summary>
        <p>本次没有把语速、响度或“错误次数”作为场景表达的主结论；它们会作为逐轮音频观察，供治疗师结合原始录音复核。</p>
      </details>
    </template>
    <div class="action-row"><RouterLink class="secondary-link" to="/training">再练一个场景</RouterLink><RouterLink class="primary-link" to="/report">查看训练记录</RouterLink></div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { scenarioDialoguesApi } from '@/api/scenarioDialogues'
import type { ScenarioDialogueEvaluation } from '@/types/api'
import { toUserMessage } from '@/utils/errors'

const route = useRoute()
const evaluation = ref<ScenarioDialogueEvaluation | null>(null)
const loading = ref(true)
const error = ref('')
const goalHeading = computed(() => ({ achieved: '对方已经理解你的主要需要', partly_achieved: '对方理解了部分需要', not_achieved: '这次还没有把主要需要说清' })[evaluation.value?.goal_status || 'not_achieved'])
const goalDescription = computed(() => ({ achieved: '你提供的信息已经足够让对方采取下一步行动。', partly_achieved: '对方已经获得一部分关键信息；下次可以补充最重要但还没说到的内容。', not_achieved: '这次对方还缺少完成下一步所需的信息。' })[evaluation.value?.goal_status || 'not_achieved'])
const informationDescription = computed(() => {
  const collected = evaluation.value?.evidence_snapshot.collected_information_unit_ids || []
  return collected.length ? `本次已从整段对话中识别到 ${collected.length} 项关键沟通信息。` : '这次还没有稳定识别到关键沟通信息。'
})
const independenceDescription = computed(() => ((evaluation.value?.independence_score ?? 0) >= 85 ? '你基本独立完成了表达。' : '下次可以先自己组织一句，再在需要时使用提示。'))
const nextStep = computed(() => ((evaluation.value?.information_score ?? 0) < 100 ? '围绕数字人的下一句提问，补充一个还没有说清的关键信息。' : '保持现在的方式，练习在新的生活场景中主动说明需要。'))

onMounted(async () => {
  try { evaluation.value = await scenarioDialoguesApi.evaluation(String(route.params.dialogueId)) }
  catch (err) { error.value = toUserMessage(err, '暂时无法读取本次小结') }
  finally { loading.value = false }
})
</script>
