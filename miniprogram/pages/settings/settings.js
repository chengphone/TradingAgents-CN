const { api } = require('../../utils/api.js')

Page({
  data: {
    openid: '',
    quota: { used: 0, total: 10 }
  },

  onShow() {
    this.loadUserInfo()
    this.updateQuota()
  },

  updateQuota() {
    const app = getApp()
    this.setData({ quota: app.getDailyQuota() })
  },

  async loadUserInfo() {
    try {
      const res = await api.get('/auth/me')
      if (res.success && res.data) {
        this.setData({
          openid: res.data.openid ? res.data.openid.substring(0, 12) + '...' : '未知'
        })
      }
    } catch (err) {
      console.error('获取用户信息失败:', err)
    }
  }
})
