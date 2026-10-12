export {}

declare global {
  interface Window {
    IVH?: TencentIVH
  }
}

export interface TencentIVH {
  init(options: {
    element: Element | string
    sign?: string
    assetVirtualmanKey?: string
  }): unknown
  createSessionByAsset(options: {
    driverType?: number
    userId?: string
  }): Promise<{ sessionId?: string; playStreamAddr?: string } | null>
  startSession(): Promise<boolean>
  closeSession(): Promise<boolean>
  play(options: { command: 'audio'; data: string; seq: number; isFinal?: boolean }): unknown
  stop(): unknown
  on(event: string, callback: (payload: any) => void): unknown
}
