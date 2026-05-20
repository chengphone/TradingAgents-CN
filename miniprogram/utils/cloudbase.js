/**
 * 云数据库 / 云存储 操作封装（可选，用于直接访问云数据库）
 * 主要数据操作通过云托管 API，这里仅提供云存储上传下载等辅助功能
 */

const db = wx.cloud ? wx.cloud.database() : null

function getCollection(name) {
  return db ? db.collection(name) : null
}

/** 上传报告截图到云存储 */
function uploadReportImage(filePath, taskId) {
  return wx.cloud.uploadFile({
    cloudPath: `reports/${taskId}/${Date.now()}.png`,
    filePath: filePath
  })
}

/** 获取云存储临时链接 */
function getTempFileURL(fileID) {
  return wx.cloud.getTempFileURL({
    fileList: [fileID]
  })
}

module.exports = { getCollection, uploadReportImage, getTempFileURL }
