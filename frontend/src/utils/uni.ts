declare global {
  var uni: {
    setStorageSync(key: string, data: string): void
    getStorageSync(key: string): string | null
    removeStorageSync(key: string): void
  }
}

globalThis.uni = {
  setStorageSync(key, data) {
    localStorage.setItem(key, data)
  },
  getStorageSync(key) {
    return localStorage.getItem(key)
  },
  removeStorageSync(key) {
    localStorage.removeItem(key)
  },
}

export {}