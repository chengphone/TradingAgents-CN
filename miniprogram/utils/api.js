/**
 * HTTP API 封装 - 自动附带 Token + 401 重试
 */
const auth = require('./auth.js')

let _tokenProvider = null

function initApi(tokenProvider) {
  _tokenProvider = tokenProvider
}

function request(method, path, data = null) {
  return new Promise((resolve, reject) => {
    const doRequest = (retry) => {
      const token = typeof _tokenProvider === 'function' ? _tokenProvider() : auth.getToken()
      const header = { 'Content-Type': 'application/json' }
      if (token) header['Authorization'] = `Bearer ${token}`

      wx.request({
        url: auth.API_BASE + path,
        method: method,
        data: data,
        header: header,
        timeout: 120000,
        success: (res) => {
          if (res.statusCode === 401 && !retry) {
            // Token 过期，重新登录后重试
            auth.clearToken()
            auth.login().then(() => doRequest(true)).catch(reject)
            return
          }
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(res.data)
          } else {
            reject(new Error(res.data?.detail || `请求失败 (${res.statusCode})`))
          }
        },
        fail: (err) => {
          reject(new Error(err.errMsg || '网络错误'))
        }
      })
    }
    doRequest(false)
  })
}

const api = {
  get: (path) => request('GET', path),
  post: (path, data) => request('POST', path, data)
}

module.exports = { initApi, api, request }
