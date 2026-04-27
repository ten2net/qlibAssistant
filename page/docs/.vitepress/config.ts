import { defineConfig } from 'vitepress'
import { pagesSidebar } from './sidebar-pages.generated'

export default defineConfig({
  base: '/qlibAssistant/',
  metaChunk: true,
  title: 'qlib csi300 score',
  description: 'qlib 量化选股评分数据展示',
  lang: 'zh-CN',
  themeConfig: {
    socialLinks: [
      { icon: 'github', link: 'https://github.com/touhoufan2024/qlibAssistant' },
    ],
    nav: [
      { text: '首页', link: '/' },
      { text: '文档', link: '/pages/docs/' },
      { text: '随笔', link: '/pages/essays/' },
      { text: '马后炮', link: '/pages/mahoupao/' },
      { text: '路线图与更新', link: '/pages/changelog/' },
      { text: '帮助', link: '/pages/about/' },
    ],
    sidebar: {
      ...pagesSidebar,
      '/': [
        {
          text: '数据目录',
          link: '/',
          items: [{ text: 'selection_20260427_074819', link: '/score/selection_20260427_074819/' }],
        },
      ],
    },
    outline: {
      level: [2, 4], // 显示 H2～H4，包含 top10/top30 等四级标题
    },
    footer: {
      message: (() => {
        const now = new Date()
        const dateTime = now.toLocaleString('zh-CN', {
          timeZone: 'UTC',
          year: 'numeric',
          month: 'numeric',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
        }) + ' UTC'
        const parts = [`生成日期: ${dateTime}`]
        const os =
          process.env.RUNNER_OS ||
          process.env.OS ||
          { win32: 'Windows', darwin: 'macOS', linux: 'Linux' }[process.platform] ||
          process.platform
        const runId = process.env.GITHUB_RUN_ID
        parts.push(`运行环境: ${os}`)
        if (runId) parts.push(`构建 ID: ${runId}`)
        parts.push(`Node: ${process.version}`)
        return parts.join(' · ')
      })(),
    },
  },
  markdown: {
    theme: {
      light: 'github-light',
      dark: 'github-dark',
    },
  },
})
