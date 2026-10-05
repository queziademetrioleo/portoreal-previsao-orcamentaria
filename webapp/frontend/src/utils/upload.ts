export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024

export function validarArquivo(file: Pick<File, 'name' | 'size'>, accept: string): string | null {
  const extensoes = accept.split(',').map((ext) => ext.trim().toLowerCase())
  if (!extensoes.some((ext) => file.name.toLowerCase().endsWith(ext))) {
    return `Formato inválido. Selecione um arquivo ${extensoes.join(' ou ')}.`
  }
  if (file.size === 0) return 'O arquivo está vazio. Selecione outro arquivo.'
  if (file.size > MAX_UPLOAD_BYTES) return 'O arquivo excede o limite de 20 MB.'
  return null
}
