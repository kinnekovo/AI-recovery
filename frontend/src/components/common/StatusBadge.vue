<template><span class="status-badge" :class="`status-${view.tone}`" :title="view.description"><span aria-hidden="true">●</span>{{ view.label }}</span></template>
<script setup lang="ts">
import { computed } from 'vue'
import { presentStatus } from '@/utils/status'
const props = defineProps<{ status?: string | null }>()
const view = computed(() => presentStatus(props.status))
</script>
