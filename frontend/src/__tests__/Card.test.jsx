import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Card, CardHeader, CardBody } from '../components/ui/Card'

describe('Card', () => {
  it('renders Card with children', () => {
    render(<Card><CardHeader>Заголовок</CardHeader></Card>)
    expect(screen.getByText('Заголовок')).toBeDefined()
  })

  it('renders CardBody', () => {
    render(<Card><CardBody>Содержимое</CardBody></Card>)
    expect(screen.getByText('Содержимое')).toBeDefined()
  })
})
