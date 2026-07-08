import type { ReactNode } from 'react'

interface Column {
  key: string
  header: ReactNode
  align?: 'left' | 'right'
  render: (row: Record<string, unknown>, idx: number) => ReactNode
}

interface Props {
  columns: Column[]
  rows: Record<string, unknown>[]
  empty?: string
}

export default function DataTable({ columns, rows, empty = 'Nenhum registro.' }: Props) {
  if (rows.length === 0) {
    return <p className="table-empty">{empty}</p>
  }

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} className={col.align === 'right' ? 'num' : ''}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx}>
              {columns.map((col) => (
                <td key={col.key} className={col.align === 'right' ? 'num' : ''}>
                  {col.render(row, idx)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
