const { api } = require('../../utils/api.js')
const { parseMarkdown } = require('../../utils/markdown.js')

const ALL_MODULES = [
  { name: '市场分析', key: 'market_report' },
  { name: '基本面分析', key: 'fundamentals_report' },
  { name: '新闻分析', key: 'news_report' },
  { name: '情绪分析', key: 'sentiment_report' },
  { name: '投资计划', key: 'investment_plan' },
  { name: '最终决策', key: 'final_trade_decision' }
]

Page({
  data: {
    taskId: '',
    reportId: '',
    singleModule: false,
    currentModule: '',
    modules: ALL_MODULES,
    content: '',
    richNodes: [],
    loading: true
  },

  onLoad(options) {
    const taskId = options.task_id || ''
    const reportId = options.report_id || ''
    const module = options.module || ''

    if (module) {
      // 从结果页跳转，直接显示特定模块
      this.setData({
        taskId: taskId,
        singleModule: true,
        currentModule: module
      })
      this.loadModuleContent(taskId || reportId, module)
    } else if (reportId) {
      // 从历史页跳转，加载完整报告
      this.setData({ reportId: reportId, currentModule: 'final_trade_decision' })
      this.loadReportDetail(reportId)
    }
  },

  async loadModuleContent(id, module) {
    try {
      const res = await api.get(`/api/reports/${id}/content/${module}`)
      if (res.success && res.data) {
        this.renderMarkdown(res.data.content || '')
      } else {
        this.setData({ content: '暂无内容' })
      }
    } catch (err) {
      this.setData({ content: '加载失败: ' + err.message })
    } finally {
      this.setData({ loading: false })
    }
  },

  async loadReportDetail(id) {
    try {
      const res = await api.get(`/api/reports/${id}/detail`)
      if (res.success && res.data) {
        const reports = res.data.reports || {}
        // 先显示最终决策，其他模块通过 tab 切换
        const content = reports[this.data.currentModule] || ''
        this.renderMarkdown(content)
      }
    } catch (err) {
      this.setData({ content: '加载失败: ' + err.message })
    } finally {
      this.setData({ loading: false })
    }
  },

  async switchModule(e) {
    const key = e.currentTarget.dataset.key
    this.setData({ currentModule: key, loading: true })
    const id = this.data.taskId || this.data.reportId

    if (this.data.singleModule) {
      await this.loadModuleContent(id, key)
    } else {
      try {
        const res = await api.get(`/api/reports/${id}/detail`)
        if (res.success && res.data) {
          const reports = res.data.reports || {}
          this.renderMarkdown(reports[key] || '暂无内容')
        }
      } catch (err) {
        this.setData({ content: '加载失败' })
      } finally {
        this.setData({ loading: false })
      }
    }
  },

  renderMarkdown(md) {
    const nodes = parseMarkdown(md)
    this.setData({
      content: md,
      richNodes: nodes
    })
  }
})
