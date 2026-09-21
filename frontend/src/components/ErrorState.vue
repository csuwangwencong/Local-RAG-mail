<template>
  <div class="state-block">
    <el-alert :title="message" type="error" show-icon :closable="false" />
    <el-button class="retry-button" @click="$emit('retry')">重试</el-button>
  </div>
</template>

<script setup lang="ts">
defineProps<{ message: string }>()
defineEmits<{ retry: [] }>()
</script>
