<template><div class="timeline"><article v-for="item in items" :key="item.id"><span></span><div><strong>{{ item.title }}</strong><p>{{ item.time }}</p><small v-if="item.detail">{{ item.detail }}</small></div></article></div></template>
<script setup lang="ts">
defineProps<{ items: Array<{ id: string; title: string; time: string; detail?: string }> }>()
</script>
