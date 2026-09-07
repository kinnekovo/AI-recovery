export function toUserMessage(err: unknown, fallback: string) {
  if (err instanceof Error && err.message.trim()) return err.message
  if (typeof err === 'string' && err.trim()) return err
  return fallback
}
