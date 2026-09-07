<template>
  <section class="page-stack">
    <div class="page-heading">
      <span class="kicker">单题反馈</span>
      <h1>这次训练已经保存</h1>
      <p>以下是本次练习表现和下一步建议，只用于训练参考，不代表临床诊断。</p>
    </div>
    <ProcessFeedbackPanel v-if="feedback" :result="feedback" />
    <section v-if="feedback?.audio_url" class="recording-playback-panel patient-playback">
      <div>
        <strong>本次录音已保存</strong>
        <p>你可以先听一遍，再对照下面的反馈看下一次怎么练。</p>
      </div>
      <AudioPlayback :src="feedback.audio_url" />
    </section>
    <div v-if="!feedback" class="empty-state">
      <p>还没有训练反馈。</p>
      <RouterLink to="/training">开始一次训练</RouterLink>
    </div>
    <section v-if="usedRecommendation" class="recommendation-complete">
      <strong>已完成建议训练</strong>
      <p>这次训练会和建议记录放在一起，方便治疗师查看后续表现。</p>
    </section>
    <div class="action-row">
      <RouterLink class="secondary-link" to="/training">再练一题</RouterLink>
      <RouterLink class="primary-link" to="/report">查看记录</RouterLink>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AudioPlayback from '@/components/common/AudioPlayback.vue'
import ProcessFeedbackPanel from '@/components/report/ProcessFeedbackPanel.vue'
import { useTrainingStore } from '@/stores/training'

const store = useTrainingStore()
const feedback = computed(() => store.latestFeedback)
const usedRecommendation = computed(() => Boolean(store.currentSession?.recommendation_source))
</script>
