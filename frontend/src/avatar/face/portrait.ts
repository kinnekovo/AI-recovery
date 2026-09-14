import { FaceLandmarker, FilesetResolver } from '@mediapipe/tasks-vision'

export interface PortraitAnchor {
  x: number
  y: number
  width: number
  height: number
}

export interface PortraitAnimationConfig {
  schema_version: 1
  face_box: PortraitAnchor
  left_eye: PortraitAnchor
  right_eye: PortraitAnchor
  mouth: PortraitAnchor
  crop: PortraitAnchor
  quality: 'auto'
  motion_scale: number
}

export interface PortraitValidation {
  config: PortraitAnimationConfig | null
  message: string | null
}

let faceLandmarkerPromise: Promise<FaceLandmarker> | null = null

// 随前端发布，答辩现场首次上传不依赖 CDN。
const MODEL_URL = '/mediapipe/face_landmarker.task'
const WASM_URL = '/mediapipe/wasm'

export async function validatePortrait(file: File): Promise<PortraitValidation> {
  if (!file.type.startsWith('image/')) return { config: null, message: '请选择 JPEG、PNG 或 WebP 格式的照片。' }
  if (file.size > 10 * 1024 * 1024) return { config: null, message: '照片不能超过 10 MB，请压缩后再上传。' }
  const image = await loadImage(file)
  if (Math.min(image.width, image.height) < 512) {
    return { config: null, message: '照片短边至少需要 512 像素，请换一张更清晰的正面照。' }
  }
  try {
    const detector = await getFaceLandmarker()
    const result = detector.detect(image)
    if (result.faceLandmarks.length !== 1) {
      return { config: null, message: result.faceLandmarks.length ? '照片中检测到多张人脸，请只保留一位人物。' : '没有检测到清晰正面人脸，请换一张看向镜头、面部无遮挡的照片。' }
    }
    const landmarks = result.faceLandmarks[0]
    const face = bounds(landmarks.map((point) => ({ x: point.x, y: point.y })))
    if (face.width < 0.25 || face.width > 0.72) {
      return { config: null, message: '人物面部在照片中太小或太近，建议上传胸部以上的正面照。' }
    }
    const leftEye = boundsFromIndexes(landmarks, [33, 133, 159, 145])
    const rightEye = boundsFromIndexes(landmarks, [362, 263, 386, 374])
    const mouth = boundsFromIndexes(landmarks, [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291])
    if (Math.abs(leftEye.y - rightEye.y) > face.height * 0.16) {
      return { config: null, message: '请上传面部接近正面的照片，明显侧脸暂不适合动态陪练。' }
    }
    return {
      config: {
        schema_version: 1,
        face_box: face,
        left_eye: padded(leftEye, 0.35, 0.8),
        right_eye: padded(rightEye, 0.35, 0.8),
        mouth: padded(mouth, 0.28, 0.65),
        crop: cropForFace(face),
        quality: 'auto',
        motion_scale: 1,
      },
      message: null,
    }
  } catch {
    return { config: null, message: '照片校验暂时不可用，请检查网络后重试。' }
  }
}

async function getFaceLandmarker(): Promise<FaceLandmarker> {
  faceLandmarkerPromise ||= (async () => {
    const fileset = await FilesetResolver.forVisionTasks(WASM_URL)
    return FaceLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: MODEL_URL },
      runningMode: 'IMAGE',
      numFaces: 2,
    })
  })()
  return faceLandmarkerPromise
}

function bounds(points: Array<{ x: number; y: number }>): PortraitAnchor {
  const xs = points.map((point) => point.x)
  const ys = points.map((point) => point.y)
  const x = Math.max(0, Math.min(...xs))
  const y = Math.max(0, Math.min(...ys))
  return { x, y, width: Math.min(1 - x, Math.max(...xs) - x), height: Math.min(1 - y, Math.max(...ys) - y) }
}

function boundsFromIndexes(landmarks: Array<{ x: number; y: number }>, indexes: number[]) {
  return bounds(indexes.map((index) => landmarks[index]))
}

function padded(anchor: PortraitAnchor, horizontal: number, vertical: number): PortraitAnchor {
  const width = Math.min(1, anchor.width * (1 + horizontal * 2))
  const height = Math.min(1, anchor.height * (1 + vertical * 2))
  return {
    x: Math.max(0, Math.min(1 - width, anchor.x - anchor.width * horizontal)),
    y: Math.max(0, Math.min(1 - height, anchor.y - anchor.height * vertical)),
    width,
    height,
  }
}

function cropForFace(face: PortraitAnchor): PortraitAnchor {
  const size = Math.min(1, Math.max(0.72, face.width * 1.55, face.height * 1.55))
  return {
    x: Math.max(0, Math.min(1 - size, face.x + face.width / 2 - size / 2)),
    y: Math.max(0, Math.min(1 - size, face.y + face.height * 0.44 - size / 2)),
    width: size,
    height: size,
  }
}

function loadImage(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const image = new Image()
    image.onload = () => {
      URL.revokeObjectURL(url)
      resolve(image)
    }
    image.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('image_load_failed'))
    }
    image.src = url
  })
}
