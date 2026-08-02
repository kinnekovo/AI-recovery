<template>
  <button class="app-button" :class="variant" :disabled="disabled || loading">
    <slot />
    <span v-if="loading" class="button-spinner" />
  </button>
</template>

<script setup lang="ts">
defineProps<{
  variant?: 'primary' | 'secondary' | 'quiet'
  loading?: boolean
  disabled?: boolean
}>()
</script>
