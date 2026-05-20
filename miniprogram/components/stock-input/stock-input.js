Component({
  data: {
    code: '',
    marketIndex: 0,
    markets: ['A股', '港股', '美股'],
    stockName: ''
  },

  methods: {
    onInput(e) {
      const code = e.detail.value
      this.setData({ code })
      this.triggerEvent('change', {
        code: code,
        market: this.data.markets[this.data.marketIndex]
      })
    },

    onMarketChange(e) {
      const idx = parseInt(e.detail.value)
      this.setData({ marketIndex: idx })
      this.triggerEvent('change', {
        code: this.data.code,
        market: this.data.markets[idx]
      })
    }
  }
})
