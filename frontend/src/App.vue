<script setup lang="ts">
import { computed } from 'vue'
import { RouterView } from 'vue-router'
import en from 'element-plus/es/locale/lang/en'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import AppLayout from '@/layouts/AppLayout.vue'
import { useUiStore } from '@/stores/ui'

const uiStore = useUiStore()

// Element Plus 内置文案（分页/日期选择/空态等）跟随界面语言；
// 此前未接 config-provider，组件内部文案恒为英文而界面是中文。
const epLocale = computed(() => (uiStore.lang === 'en-US' ? en : zhCn))
</script>

<template>
  <el-config-provider :locale="epLocale">
    <AppLayout>
      <RouterView />
    </AppLayout>
  </el-config-provider>
</template>
