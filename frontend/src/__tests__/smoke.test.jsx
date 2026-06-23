import { describe, it, expect } from 'vitest'

describe('Project structure', () => {
  it('package.json has correct version', () => {
    const pkg = require('../../package.json')
    expect(pkg.version).toBe('0.4.0')
    expect(pkg.name).toBe('rca-analyzer-frontend')
  })
})
