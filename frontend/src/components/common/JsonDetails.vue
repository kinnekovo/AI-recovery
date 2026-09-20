<template><dl class="key-value-list"><div v-for="([key,value]) in entries" :key="key"><dt>{{ humanize(key) }}</dt><dd><span v-if="isPrimitive(value)">{{ display(value) }}</span><pre v-else>{{ JSON.stringify(value,null,2) }}</pre></dd></div></dl></template>
<script setup lang="ts">
import { computed } from 'vue'; import type { JsonObject, JsonValue } from '@/types/professional'
const props=defineProps<{ value?: JsonObject|null }>(); const entries=computed(()=>Object.entries(props.value||{}).filter(([,v])=>v!==null&&v!==undefined))
function humanize(v:string){return v.replace(/_/g,' ')} function isPrimitive(v:JsonValue){return typeof v!=='object'||v===null} function display(v:JsonValue){return typeof v==='boolean'?(v?'是':'否'):String(v)}
</script>
