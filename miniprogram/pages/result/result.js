const { api } = require('../../utils/api.js')

Page({
  data: {
    taskId: '',
    stockCode: '',
    stockName: '',
    status: 'pending',
    progress: 0,
    message: '',
    current_step_name: '',
    elapsed_time: 0,
    remaining_time: 0,
    steps: [],
    decision: null,
    summary: '',
    recommendation: '',
    reportModules: [],
    errorMessage: ''
  },

  _pollTimer: null,
  _pollCount: 0,
  _maxPolls: 400, // 最多轮询约20分钟

  onLoad(options) {
    const taskId = options.task_id || ''
    const stockCode = options.stock || ''
    this.setData({ taskId, stockCode })
    if (taskId) this.startPolling()
  },

  onUnload() {
    this.stopPolling()
  },

  startPolling() {
    this.poll()
    this._pollTimer = setInterval(() => this.poll(), 3000)
  },

  stopPolling() {
    if (this._pollTimer) {
      clearInterval(this._pollTimer)
      this._pollTimer = null
    }
  },

  async poll() {
    if (this._pollCount >= this._maxPolls) {
      this.stopPolling()
      return
    }
    this._pollCount++

    try {
      const res = await api.get(`/api/analysis/tasks/${this.data.taskId}/status`)
      if (!res.success || !res.data) return

      const d = res.data
      const status = d.status

      this.setData({
        status: status,
        progress: d.progress || 0,
        message: d.message || '',
        current_step_name: d.current_step_name || '',
        elapsed_time: d.elapsed_time || 0,
        remaining_time: d.remaining_time || 0,
        steps: d.steps || []
      })

      // 完成或失败时停止轮询并拉取完整结果
      if (status === 'completed') {
        this.stopPolling()
        await this.loadResult()
      } else if (status === 'failed') {
        this.stopPolling()
        this.setData({ errorMessage: d.error_message || '分析失败' })
      }
    } catch (err) {
      console.error('轮询状态失败:', err)
    }
  },

  async loadResult() {
    try {
      const res = await api.get(`/api/analysis/tasks/${this.data.taskId}/result`)
      if (!res.success || !res.data) return

      const d = res.data
      const reports = d.reports || {}

      // 构建报告模块列表
      const moduleMap = {
        market_report: { name: '市场分析', icon: '📊', key: 'market_report' },
        fundamentals_report: { name: '基本面分析', icon: '💼', key: 'fundamentals_report' },
        news_report: { name: '新闻分析', icon: '📰', key: 'news_report' },
        sentiment_report: { name: '情绪分析', icon: '💬', key: 'sentiment_report' },
        investment_plan: { name: '投资计划', icon: '📋', key: 'investment_plan' },
        final_trade_decision: { name: '最终决策', icon: '🎯', key: 'final_trade_decision' }
      }
      const reportModules = Object.keys(reports)
        .filter(k => reports[k])
        .map(k => ({
          ...moduleMap[k],
          preview: (reports[k] || '').substring(0, 50) + '...'
        }))
        .filter(m => m.name)

      this.setData({
        decision: d.decision || { action: '持有', confidence: 0.5 },
        summary: d.summary || '',
        recommendation: d.recommendation || '',
        reportModules: reportModules,
        stockName: d.stock_name || this.data.stockName
      })
    } catch (err) {
      console.error('加载结果失败:', err)
    }
  },

  goModule(e) {
    const module = e.currentTarget.dataset.module
    wx.navigateTo({
      url: `/pages/detail/detail?task_id=${this.data.taskId}&module=${module}&stock=${this.data.stockCode}`
    })
  }
})
