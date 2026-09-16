import type { Messages } from './index'

/**
 * common —— 跨视图通用的极小词表（确定/取消/刷新/空态等）。
 * 只放「与业务无关、任何视图都可能用到」的词；带业务语义的文案一律留在各自的视图模块。
 */

export const zh: Messages = {
  confirm: '确定',
  cancel: '取消',
  close: '关闭',
  refresh: '刷新',
  loading: '加载中…',
  noData: '暂无数据',
  search: '搜索',
  reset: '重置',
  save: '保存',
  edit: '编辑',
  copy: '复制',
  copied: '已复制',
  retry: '重试',
  back: '返回',
  more: '更多',
  all: '全部',
}

export const en: Messages = {
  confirm: 'OK',
  cancel: 'Cancel',
  close: 'Close',
  refresh: 'Refresh',
  loading: 'Loading…',
  noData: 'No data',
  search: 'Search',
  reset: 'Reset',
  save: 'Save',
  edit: 'Edit',
  copy: 'Copy',
  copied: 'Copied',
  retry: 'Retry',
  back: 'Back',
  more: 'More',
  all: 'All',
}
