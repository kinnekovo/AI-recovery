<template><article class="surface-card metric-card"><small>{{ label }}</small><strong>{{ value }}</strong><p v-if="hint">{{ hint }}</p></article></template>
<script setup lang="ts">
withDefaults(defineProps<{ label: string; value: string | number; hint?: string }>(), { hint: '' })
</script>
