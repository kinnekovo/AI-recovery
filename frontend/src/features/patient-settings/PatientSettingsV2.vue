<template>
  <section class="v2-page patient-readable">
    <header class="v2-page-header"><p class="v2-context">我的</p><h1>让训练更适合你</h1><p>陪伴形象是表达和练习的呈现方式，不会替你做医疗决定。</p></header>
    <section class="settings-lines">
      <RouterLink to="/legacy/agent/list"><span><strong>陪伴设置</strong><small>形象、声音与自动播放</small></span><ChevronRight aria-hidden="true"/></RouterLink>
      <div><span><strong>字体大小</strong><small>标准；浏览器缩放也会保留</small></span><select aria-label="字体大小" v-model="fontSize" @change="applyFont()"><option value="standard">标准</option><option value="large">大</option><option value="xlarge">特大</option></select></div>
      <div><span><strong>患者时区</strong><small>决定“今天训练”的自然日边界</small></span><select aria-label="患者时区" v-model="timezone" @change="saveTimezone"><option>Asia/Shanghai</option><option>Asia/Hong_Kong</option><option>Asia/Tokyo</option><option>UTC</option></select></div>
      <label class="toggle-line"><span><strong>简化页面</strong><small>减少训练时的非必要信息</small></span><input type="checkbox" v-model="simpleMode" @change="applySimpleMode()"></label>
      <label class="toggle-line"><span><strong>文字朗读</strong><small>支持系统朗读重要提示</small></span><input type="checkbox" v-model="readAloud" @change="saveLocalPreferences"></label>
      <div><span><strong>回答等待时间</strong><small>开始录音前留出更充足的准备时间</small></span><select aria-label="回答等待时间" v-model="waitTime" @change="saveLocalPreferences"><option value="3">3 秒</option><option value="5">5 秒</option><option value="8">8 秒</option></select></div>
      <label class="toggle-line"><span><strong>自动播放示范</strong><small>进入复述练习时自动播放示范音频</small></span><input type="checkbox" v-model="autoPlay" @change="saveLocalPreferences"></label>
    </section>
    <p v-if="saved" class="v2-inline-success" role="status">设置已保存。</p>
    <section class="v2-section-block"><h2>当前康复计划</h2><p>正式目标、训练重点和计划版本由治疗师发布。你可以在首页查看今天要完成的内容。</p><RouterLink class="v2-button secondary" to="/home">查看今天的计划</RouterLink></section>
  </section>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'; import { ChevronRight } from 'lucide-vue-next'; import { v2Api } from '@/api/v2'
const timezone=ref('Asia/Shanghai');const fontSize=ref(localStorage.getItem('patient_font_size')||'standard');const simpleMode=ref(localStorage.getItem('patient_simple_mode')==='true');const readAloud=ref(localStorage.getItem('patient_read_aloud')==='true');const waitTime=ref(localStorage.getItem('patient_wait_time')||'5');const autoPlay=ref(localStorage.getItem('patient_auto_play')==='true');const saved=ref(false)
function flash(){saved.value=true;window.setTimeout(()=>saved.value=false,1600)}function applyFont(notify=true){localStorage.setItem('patient_font_size',fontSize.value);document.documentElement.dataset.patientFont=fontSize.value;if(notify)flash()}function applySimpleMode(notify=true){localStorage.setItem('patient_simple_mode',String(simpleMode.value));document.documentElement.dataset.simpleMode=String(simpleMode.value);if(notify)flash()}function saveLocalPreferences(){localStorage.setItem('patient_wait_time',waitTime.value);localStorage.setItem('patient_auto_play',String(autoPlay.value));localStorage.setItem('patient_read_aloud',String(readAloud.value));flash()}async function saveTimezone(){await v2Api.updatePatientSettings(timezone.value);flash()}onMounted(async()=>{const result=await v2Api.patientSettings();timezone.value=result.timezone;if(!localStorage.getItem('patient_wait_time'))localStorage.setItem('patient_wait_time',waitTime.value);applyFont(false);applySimpleMode(false)})
</script>
