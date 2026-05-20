const { api } = require('../../utils/api.js')

Page({
  data: {
    reports: [],
    searchCode: '',
    page: 1,
    pageSize: 20,
    total: 0,
    loading: false,
    loadingMore: false,
    hasMore: false
  },

  onShow() {
    this.setData({ page: 1, reports: [] })
    this.loadReports()
  },

  onSearchInput(e) {
    this.setData({ searchCode: e.detail.value })
  },

  doSearch() {
    this.setData({ page: 1, reports: [] })
    this.loadReports()
  },

  async loadReports() {
    this.setData({ loading: true })
    try {
      let url = `/api/reports/list?page=${this.data.page}&page_size=${this.data.pageSize}`
      if (this.data.searchCode) url += `&stock_code=${this.data.searchCode}`

      const res = await api.get(url)
      if (res.success && res.data) {
        const newReports = res.data.reports || []
        const reports = this.data.page === 1 ? newReports : this.data.reports.concat(newReports)
        this.setData({
          reports: reports,
          total: res.data.total || 0,
          hasMore: reports.length < (res.data.total || 0)
        })
      }
    } catch (err) {
      console.error('加载历史失败:', err)
    } finally {
      this.setData({ loading: false, loadingMore: false })
    }
  },

  loadMore() {
    if (this.data.loadingMore) return
    this.setData({ page: this.data.page + 1, loadingMore: true }, () => {
      this.loadReports()
    })
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/detail/detail?report_id=${id}` })
  }
})
