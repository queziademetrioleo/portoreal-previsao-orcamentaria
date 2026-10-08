export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024

export function validarArquivo(file: Pick<File, 'name' | 'size'>, accept: string): string | null {
  const extensoes = accept.split(',').map((ext) => ext.trim().toLowerCase())
  if (!extensoes.some((ext) => file.name.toLowerCase().endsWith(ext))) {
    if (accept === '.xls' && file.name.toLowerCase().endsWith('.xlsx')) {
      return 'Este campo é do Condo21 e aceita XLS. Se os relatórios são da Group, selecione Group e envie os arquivos nas caixas da Group.'
    }
    return `Formato inválido. Selecione um arquivo ${extensoes.join(' ou ')}.`
  }
  if (file.size === 0) return 'O arquivo está vazio. Selecione outro arquivo.'
  if (file.size > MAX_UPLOAD_BYTES) return 'O arquivo excede o limite de 20 MB.'
  return null
}
