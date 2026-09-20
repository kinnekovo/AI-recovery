<template>
  <LoadingSkeleton v-if="loading" />
  <ErrorState v-else-if="error" :message="error" @retry="$emit('retry')" />
  <EmptyState v-else-if="empty" :title="emptyTitle" :text="emptyText"><slot name="empty-action" /></EmptyState>
  <slot v-else />
</template>
<script setup lang="ts">
import LoadingSkeleton from './LoadingSkeleton.vue'
import ErrorState from './ErrorState.vue'
import EmptyState from './EmptyState.vue'
defineProps<{ loading?: boolean; error?: string; empty?: boolean; emptyTitle?: string; emptyText?: string }>()
defineEmits<{ retry: [] }>()
</script>
