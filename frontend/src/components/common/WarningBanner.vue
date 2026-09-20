<template><aside class="warning-banner" :class="tone" role="note"><strong>{{ title }}</strong><p v-if="message">{{ message }}</p><slot /></aside></template>
<script setup lang="ts">
withDefaults(defineProps<{ title: string; message?: string; tone?: 'info' | 'warning' | 'danger' }>(), { message: '', tone: 'warning' })
</script>
