/**
 * 微信静默登录 + Token 管理
 */
const { api } = require('./api.js')

const TOKEN_KEY = 'auth_token'
const API_BASE = 'https://your-env-id.api.tcloudbasegateway.com' // 云托管地址

let _token = null

function getToken() {
  if (_token) return _token
  try {
    _token = wx.getStorageSync(TOKEN_KEY)
  } catch (e) {
    _token = null
  }
  return _token
}

function saveToken(token) {
  _token = token
  try {
    wx.setStorageSync(TOKEN_KEY, token)
  } catch (e) {
    console.error('保存token失败:', e)
  }
}

function clearToken() {
  _token = null
  try {
    wx.removeStorageSync(TOKEN_KEY)
  } catch (e) { /* ignore */ }
}

/**
 * 静默登录：wx.login → 后端 code2session → JWT
 */
function login() {
  return new Promise((resolve, reject) => {
    wx.login({
      success: (loginRes) => {
        if (!loginRes.code) {
          reject(new Error('wx.login 失败'))
          return
        }
        wx.request({
          url: API_BASE + '/api/auth/login',
          method: 'POST',
          data: { code: loginRes.code },
          success: (res) => {
            // 修复：后端返回结构为 { success: true, data: { token, openid, daily_quota } }
            const token = res.data?.data?.token
            if (res.statusCode === 200 && token) {
              saveToken(token)
              resolve(token)
            } else {
              reject(new Error(res.data?.detail || res.data?.message || '登录失败'))
            }
          },
          fail: reject
        })
      },
      fail: reject
    })
  })
}

/**
 * 初始化认证：有 token 就用，没有就登录
 */
async function initAuth() {
  let token = getToken()
  if (token) return token
  return await login()
}

module.exports = { getToken, saveToken, clearToken, login, initAuth, API_BASE }
