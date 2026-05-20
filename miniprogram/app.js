/**
 * TradingAgents-CN 微信小程序
 * AI驱动的股票分析工具
 */
const { initAuth, getToken } = require('./utils/auth.js')
const { initApi } = require('./utils/api.js')

App({
  globalData: {
    userInfo: null,
    token: null,
    openid: null,
    dailyQuota: { used: 0, total: 10 }
  },

  onLaunch() {
    // 云开发初始化（如已开通）
    if (wx.cloud) {
      wx.cloud.init({
        env: 'your-env-id',
        traceUser: true
      })
    }

    // 自动登录
    this.autoLogin()
  },

  async autoLogin() {
    try {
      const token = await initAuth()
      if (token) {
        this.globalData.token = token
        initApi(token)
        await this.loadUserInfo()
      }
    } catch (err) {
      console.error('自动登录失败:', err)
    }
  },

  async loadUserInfo() {
    try {
      const api = require('./utils/api.js').api
      const res = await api.get('/api/auth/me')
      if (res.success) {
        this.globalData.userInfo = res.data
        this.globalData.openid = res.data.openid
        this.globalData.dailyQuota = {
          used: res.data.daily_used || 0,
          total: res.data.daily_quota || 10
        }
      }
    } catch (err) {
      console.error('获取用户信息失败:', err)
    }
  },

  getDailyQuota() {
    return this.globalData.dailyQuota
  }
})
