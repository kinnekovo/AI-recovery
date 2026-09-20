<template><div class="state-panel error-state" role="alert"><strong>暂时无法加载</strong><p>{{ message }}</p><button class="secondary-button" type="button" @click="$emit('retry')">重新加载</button></div></template>
<script setup lang="ts">
defineProps<{ message: string }>()
defineEmits<{ retry: [] }>()
</script>
