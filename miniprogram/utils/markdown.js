/**
 * Markdown 转 WXML 富文本节点
 * 简易转换器，支持标题、加粗、列表、表格等
 */

function parseMarkdown(md) {
  if (!md) return [{ type: 'text', text: '' }]
  const nodes = []
  const lines = md.split('\n')
  let inTable = false
  let tableRows = []

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // 空行
    if (!line.trim()) {
      if (inTable) {
        nodes.push(renderTable(tableRows))
        inTable = false
        tableRows = []
      }
      nodes.push({ type: 'text', text: '\n' })
      continue
    }

    // 标题
    const hMatch = line.match(/^(#{1,6})\s+(.+)/)
    if (hMatch) {
      nodes.push({
        type: 'text',
        text: hMatch[2],
        style: `font-size:${44 - hMatch[1].length * 4}rpx;font-weight:700;margin:${24 - hMatch[1].length * 2}rpx 0 12rpx;color:#e0e0e0;`
      })
      continue
    }

    // 分割线
    if (/^-{3,}$/.test(line.trim())) {
      nodes.push({ type: 'text', text: '━━━━━━━━━━', style: 'color:#555;margin:16rpx 0;' })
      continue
    }

    // 表格
    if (line.includes('|')) {
      inTable = true
      tableRows.push(line.split('|').filter(c => c.trim()))
      continue
    }

    // 列表
    const liMatch = line.match(/^[\s]*[-*+]\s+(.+)/)
    if (liMatch) {
      nodes.push({
        type: 'text',
        text: '  • ' + parseInline(liMatch[1]),
        style: 'color:#c0c0c0;margin:4rpx 0;'
      })
      continue
    }

    // 引用
    const quoteMatch = line.match(/^>\s+(.+)/)
    if (quoteMatch) {
      nodes.push({
        type: 'text',
        text: '▎' + parseInline(quoteMatch[1]),
        style: 'color:#a0a0a0;border-left:4rpx solid #00d4aa;padding-left:16rpx;margin:8rpx 0;'
      })
      continue
    }

    // 普通段落
    nodes.push({
      type: 'text',
      text: parseInline(line),
      style: 'color:#e0e0e0;margin:4rpx 0;'
    })
  }

  // 未闭合表格
  if (inTable && tableRows.length > 0) {
    nodes.push(renderTable(tableRows))
  }

  return nodes
}

function parseInline(text) {
  // 加粗 **text**
  text = text.replace(/\*\*(.+?)\*\*/g, '《$1》')
  // 代码 `code`
  text = text.replace(/`(.+?)`/g, '[$1]')
  return text
}

function renderTable(rows) {
  if (rows.length < 2) return { type: 'text', text: rows.map(r => r.join(' | ')).join('\n') }
  const header = rows[0]
  const body = rows.slice(2) // skip separator
  let tableText = '┌' + '─'.repeat(40) + '┐\n'
  tableText += '│ ' + header.join(' │ ') + ' │\n'
  tableText += '├' + '─'.repeat(40) + '┤\n'
  for (const row of body) {
    tableText += '│ ' + row.join(' │ ') + ' │\n'
  }
  tableText += '└' + '─'.repeat(40) + '┘'
  return {
    type: 'text',
    text: tableText,
    style: 'font-family:monospace;font-size:24rpx;color:#c0c0c0;background:#16213e;padding:16rpx;border-radius:8rpx;margin:8rpx 0;white-space:pre;'
  }
}

module.exports = { parseMarkdown, parseInline }
