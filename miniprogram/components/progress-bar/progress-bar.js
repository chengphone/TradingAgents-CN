Component({
  properties: {
    progress: { type: Number, value: 0 },
    currentStep: { type: String, value: '' },
    elapsed: { type: Number, value: 0 },
    remaining: { type: Number, value: 0 },
    steps: { type: Array, value: [] }
  },

  methods: {
    formatTime(seconds) {
      if (!seconds || seconds <= 0) return '--'
      const m = Math.floor(seconds / 60)
      const s = Math.floor(seconds % 60)
      if (m > 0) return `${m}分${s}秒`
      return `${s}秒`
    }
  }
})
