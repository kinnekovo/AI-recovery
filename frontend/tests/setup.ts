import { afterEach } from 'vitest'
import { config } from '@vue/test-utils'

config.global.stubs = { RouterLink: { template: '<a><slot /></a>' } }
afterEach(() => { localStorage.clear(); document.body.innerHTML = '' })
