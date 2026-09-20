<template><div class="state-panel empty-state"><strong>{{ title }}</strong><p>{{ text }}</p><slot /></div></template>
<script setup lang="ts">
withDefaults(defineProps<{ title?: string; text?: string }>(), { title: '暂无数据', text: '这里还没有可显示的记录。' })
</script>
