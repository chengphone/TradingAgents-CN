const { api } = require('../../utils/api.js')

Page({
  data: {
    stockCode: '',
    market: 'A股',
    currentDepth: '标准',
    depths: [
      { name: '快速', value: '快速', desc: '1轮辩论', time: '约2-4分钟' },
      { name: '标准', value: '标准', desc: '2轮辩论', time: '约6-10分钟' },
      { name: '深度', value: '深度', desc: '多轮深度', time: '约10-20分钟' }
    ],
    analysts: [
      { name: '市场分析', value: 'market', icon: '📊', selected: true },
      { name: '基本面', value: 'fundamentals', icon: '💼', selected: true },
      { name: '新闻', value: 'news', icon: '📰', selected: false },
      { name: '情绪', value: 'social', icon: '💬', selected: false }
    ],
    submitting: false,
    recentTasks: [],
    quota: { used: 0, total: 10 }
  },

  onLoad() {
    this.loadRecentTasks()
    this.updateQuota()
  },

  onShow() {
    this.updateQuota()
    this.loadRecentTasks()
  },

  updateQuota() {
    const app = getApp()
    const quota = app.getDailyQuota()
    this.setData({ quota })
  },

  onStockChange(e) {
    this.setData({ stockCode: e.detail.code, market: e.detail.market || 'A股' })
  },

  selectDepth(e) {
    this.setData({ currentDepth: e.currentTarget.dataset.value })
  },

  toggleAnalyst(e) {
    const value = e.currentTarget.dataset.value
    const analysts = this.data.analysts.map(a => {
      if (a.value === value) a.selected = !a.selected
      return a
    })
    const selected = analysts.filter(a => a.selected)
    if (selected.length === 0) return // 至少选一个
    this.setData({ analysts })
  },

  async submitAnalysis() {
    if (!this.data.stockCode) {
      wx.showToast({ title: '请输入股票代码', icon: 'none' })
      return
    }
    const selectedAnalysts = this.data.analysts.filter(a => a.selected).map(a => a.value)

    this.setData({ submitting: true })
    try {
      const res = await api.post('/api/analysis/single', {
        symbol: this.data.stockCode,
        stock_code: this.data.stockCode,
        parameters: {
          market_type: this.data.market,
          research_depth: this.data.currentDepth,
          selected_analysts: selectedAnalysts
        }
      })
      if (res.success && res.data) {
        wx.navigateTo({
          url: `/pages/result/result?task_id=${res.data.task_id}&stock=${this.data.stockCode}`
        })
      } else {
        wx.showToast({ title: res.message || '提交失败', icon: 'none' })
      }
    } catch (err) {
      wx.showToast({ title: err.message || '网络错误', icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  },

  async loadRecentTasks() {
    try {
      const res = await api.get('/api/analysis/tasks?limit=5')
      if (res.success && res.data) {
        this.setData({ recentTasks: res.data.tasks || [] })
      }
    } catch (err) {
      console.error('加载最近任务失败:', err)
    }
  },

  goResult(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/result/result?task_id=${id}` })
  }
})
