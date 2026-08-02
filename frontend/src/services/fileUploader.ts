export function validateFile(file: File | null, allowed: string[]): string {
  if (!file) return '请选择文件'
  if (!allowed.some((type) => file.type.startsWith(type))) return '文件类型不符合要求'
  return ''
}
