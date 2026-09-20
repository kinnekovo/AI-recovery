<template>
  <div v-if="open" class="dialog-backdrop" @click.self="$emit('cancel')">
    <section class="confirm-dialog" role="dialog" aria-modal="true" :aria-labelledby="titleId">
      <h2 :id="titleId">{{ title }}</h2><p>{{ message }}</p><slot />
      <div class="dialog-actions"><button class="secondary-button" type="button" @click="$emit('cancel')">取消</button><button class="primary-button" :class="{ danger }" type="button" :disabled="busy" @click="$emit('confirm')">{{ busy ? '处理中…' : confirmLabel }}</button></div>
    </section>
  </div>
</template>
<script setup lang="ts">
const titleId = `confirm-${Math.random().toString(36).slice(2)}`
withDefaults(defineProps<{ open: boolean; title: string; message: string; confirmLabel?: string; danger?: boolean; busy?: boolean }>(), { confirmLabel: '确认', danger: false, busy: false })
defineEmits<{ cancel: []; confirm: [] }>()
</script>
