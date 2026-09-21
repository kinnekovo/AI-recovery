<template>
  <section class="v2-page therapist-v2-page assessment-entry-page">
    <header class="v2-page-header">
      <RouterLink :to="`/therapist/patients/${patientId}#assessment`" class="v2-text-link">← 返回患者工作区</RouterLink>
      <p class="v2-context">正式专业评估</p>
      <h1>记录量表施测</h1>
      <p>这里只记录治疗师实际完成的正式施测。新版暂不接入 WAB、CADL 和接受度指标。</p>
    </header>
    <form class="assessment-form workspace-band" @submit.prevent="submit">
      <div class="assessment-form-grid">
        <label>量表名称<input v-model="form.instrument_name" required placeholder="例如 CADL 或 WAB" /></label>
        <label>量表版本<input v-model="form.instrument_version" required placeholder="例如 中文版 1.0" /></label>
        <label>计分单位<input v-model="form.score_unit" required placeholder="分" /></label>
        <label>施测方式<select v-model="form.administration_mode" required><option value="in_person">面对面</option><option value="remote">远程</option><option value="hybrid">混合</option></select></label>
      </div>
      <fieldset>
        <legend>正式量表指标</legend>
        <p class="v2-quiet-copy">WAB、CADL 和接受度暂不在新版指标面板中展示或录入；历史正式评估数据仍保留。</p>
      </fieldset>
      <label>专业备注<textarea v-model="form.notes" placeholder="记录施测条件、偏差或解释边界"></textarea></label>
      <p v-if="error" class="v2-inline-error" role="alert">{{ error }}</p>
      <div class="assessment-actions"><button class="v2-button primary" :disabled="busy">{{ busy ? '正在保存…' : '保存正式评估' }}</button></div>
    </form>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { v2Api } from '@/api/v2'
import { toUserMessage } from '@/utils/errors'

const route = useRoute()
const router = useRouter()
const patientId = computed(() => String(route.params.patientId))
const busy = ref(false)
const error = ref('')
const form = reactive({ instrument_name: '', instrument_version: '', score_unit: '分', administration_mode: 'in_person', notes: '' })
async function submit() {
  busy.value = true
  error.value = ''
  try {
    await v2Api.createFormalAssessment(patientId.value, {
      ...form,
      language_locale: 'zh-CN',
      raw_item_results: {},
      subscale_results: {},
      total_result: {},
      metrics: {},
      missing_items: [],
      protocol_deviations: {},
      protocol_deviation_reasons: []
    })
    await router.push(`/therapist/patients/${patientId.value}#assessment`)
  } catch (err) {
    error.value = toUserMessage(err, '正式评估保存失败，尚未写入。')
  } finally {
    busy.value = false
  }
}
</script>
