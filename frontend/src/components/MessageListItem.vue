<template>
  <button class="message-item" :class="{ 'is-active': active, 'is-unread': !message.is_read }" type="button" @click="$emit('select')">
    <span class="unread-dot" />
    <span class="sender">{{ displaySender }}</span>
    <span class="date">{{ formatMailDate(message.received_at) }}</span>
    <span class="subject">{{ message.subject || '无主题' }}</span>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { MessageSummary } from '../types/message'
import { formatMailDate } from '../utils/date'

const props = defineProps<{
  message: MessageSummary
  active: boolean
}>()

defineEmits<{ select: [] }>()

const displaySender = computed(() => props.message.sender.name || props.message.sender.address || '未知发件人')
</script>
