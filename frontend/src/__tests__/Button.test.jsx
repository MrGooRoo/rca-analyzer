import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Button } from '../components/ui/Button'

describe('Button', () => {
  it('renders with text', () => {
    render(<Button>Тестовая кнопка</Button>)
    expect(screen.getByText('Тестовая кнопка')).toBeDefined()
  })

  it('applies variant classes', () => {
    render(<Button variant="primary">Primary</Button>)
    const btn = screen.getByText('Primary')
    expect(btn.className).toContain('primary')
  })

  it('renders loading state', () => {
    render(<Button loading>Загрузка</Button>)
    const btn = screen.getByText('Загрузка')
    expect(btn.disabled).toBe(true)
  })
})
