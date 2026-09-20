<template><div class="loading-skeleton" role="status" aria-live="polite"><span></span><span></span><span></span><p>{{ label }}</p></div></template>
<script setup lang="ts">
withDefaults(defineProps<{ label?: string }>(), { label: '正在加载…' })
</script>
