<template>
  <iframe
    v-if="body.type === 'html' && body.html"
    title="邮件正文"
    class="mail-frame"
    sandbox=""
    :srcdoc="documentHtml"
  />
  <pre v-else-if="body.type === 'text' && body.text" class="text-body">{{ body.text }}</pre>
  <el-empty v-else description="邮件正文为空" />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { MessageBody } from '../types/message'
import { buildMailDocument } from '../utils/mailHtml'

const props = defineProps<{ body: MessageBody }>()
const documentHtml = computed(() => buildMailDocument(props.body.html ?? ''))
</script>
