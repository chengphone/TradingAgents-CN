const { api } = require('../../utils/api.js')

Component({
  data: {
    configs: [],
    providers: [],
    modified: false
  },

  lifetimes: {
    attached() {
      this.loadConfigs()
    }
  },

  methods: {
    async loadConfigs() {
      try {
        const res = await api.get('/api/config/llm')
        if (res.success && res.data) {
          this.setData({ configs: res.data, modified: false })
        }
      } catch (err) {
        console.error('加载配置失败:', err)
      }
    },

    onFieldChange(e) {
      const { index, field } = e.currentTarget.dataset
      const value = e.detail.value
      const configs = this.data.configs
      configs[index][field] = value
      this.setData({ configs, modified: true })
    },

    toggleEnabled(e) {
      const index = e.currentTarget.dataset.index
      const configs = this.data.configs
      configs[index].enabled = !configs[index].enabled
      this.setData({ configs, modified: true })
    },

    addConfig() {
      const configs = this.data.configs
      const provider = 'custom-' + Date.now()
      configs.push({
        provider: provider,
        model_name: '',
        api_key: '',
        api_base: '',
        enabled: true,
        input_price_per_1k: 0,
        output_price_per_1k: 0
      })
      this.setData({ configs, modified: true })
    },

    async saveConfigs() {
      try {
        for (const cfg of this.data.configs) {
          await api.post('/api/config/llm', cfg)
        }
        wx.showToast({ title: '保存成功', icon: 'success' })
        this.setData({ modified: false })
        this.loadConfigs()
      } catch (err) {
        wx.showToast({ title: '保存失败: ' + err.message, icon: 'none' })
      }
    }
  }
})
