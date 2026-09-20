import type { AxiosAdapter, AxiosResponse } from 'axios'
import { afterEach, describe, expect, it } from 'vitest'
import { http } from '@/api/http'
import { isProductV2Enabled, v2Api } from '@/api/v2'
import router from '@/router'

const originalAdapter = http.defaults.adapter
afterEach(() => { http.defaults.adapter = originalAdapter })

describe('Product Reset v2 contracts', () => {
  it('defaults to v2 and supports an explicit legacy switch', () => {
    expect(isProductV2Enabled(undefined)).toBe(true)
    expect(isProductV2Enabled('true')).toBe(true)
    expect(isProductV2Enabled('false')).toBe(false)
  })
  it('exposes the patient and therapist product routes while retaining legacy routes', () => {
    const paths = router.getRoutes().map(route => route.path)
    expect(paths).toEqual(expect.arrayContaining([
      '/home',
      '/training',
      '/progress',
      '/me',
      '/therapist',
      '/therapist/patients',
      '/therapist/plans',
      '/therapist/patients/:patientId/assessments/new',
      '/legacy/home',
      '/legacy/training'
    ]))
  })

  it('uses aggregate application APIs rather than table-shaped endpoints', async () => {
    const seen: string[] = []
    http.defaults.adapter = (async config => {
      seen.push(`${config.method?.toUpperCase()} ${config.url}`)
      return { data: { code: 0, message: '', data: {} }, status: 200, statusText: 'OK', headers: {}, config } as AxiosResponse
    }) as AxiosAdapter
    await Promise.all([
      v2Api.patientHome(),
      v2Api.progress(),
      v2Api.startOrResume(),
      v2Api.workspace('patient-1'),
      v2Api.workbench(),
      v2Api.createFormalAssessment('patient-1', { instrument_name: 'CADL' })
    ])
    expect(seen).toEqual(expect.arrayContaining([
      'GET /v2/patient/home',
      'GET /v2/patient/progress',
      'POST /v2/patient/training-sessions/start-or-resume',
      'GET /v2/therapist/patients/patient-1/workspace',
      'GET /v2/therapist/workbench',
      'POST /v2/therapist/patients/patient-1/formal-assessments'
    ]))
  })
})
