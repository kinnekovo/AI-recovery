import type { AxiosAdapter, AxiosResponse } from 'axios'
import { AxiosError } from 'axios'
import { afterEach, describe, expect, it } from 'vitest'
import { http, ApiError } from '@/api/http'
import { profileV2Api } from '@/api/profileV2'
import { clinicalStageApi } from '@/api/clinicalStage'
import { calibrationApi } from '@/api/calibration'
import { policyV2Api } from '@/api/policyV2'
import { policyValidationApi } from '@/api/policyValidation'
import { controlledPolicyApi } from '@/api/controlledPolicy'
import { governanceApi } from '@/api/governance'

const originalAdapter = http.defaults.adapter
afterEach(() => { http.defaults.adapter = originalAdapter })

describe('V4 real API contracts', () => {
  it('targets the repository backend paths and methods', async () => {
    const seen: string[] = []
    http.defaults.adapter = (async config => {
      seen.push(`${config.method?.toUpperCase()} ${config.url}`)
      const data = config.url?.endsWith('/proposals') || config.url?.endsWith('/history') || config.url?.endsWith('/registry') ? [] : {}
      return { data: { code: 0, message: '', data }, status: 200, statusText: 'OK', headers: {}, config } as AxiosResponse
    }) as AxiosAdapter
    await Promise.all([
      profileV2Api.patientProfile(), profileV2Api.latest('p'), clinicalStageApi.detail('p','a'), clinicalStageApi.preview('p','a'), clinicalStageApi.compare('p','a','b'),
      calibrationApi.dataset('d'), calibrationApi.freeze('d'), policyV2Api.latest('p'), policyV2Api.feedback('p','x',{agreement:'agree',reason_codes:[]}),
      policyValidationApi.registry(), controlledPolicyApi.proposals('p'), controlledPolicyApi.approve('p','x'), controlledPolicyApi.apply('p','x'), governanceApi.registry()
    ])
    expect(seen).toContain('GET /patient/profile')
    expect(seen).toContain('GET /therapist/patients/p/assessments/a/clinical-stage')
    expect(seen).toContain('POST /calibration/datasets/d/freeze')
    expect(seen).toContain('POST /therapist/patients/p/policy-v2/proposals/x/apply')
    expect(seen).toContain('GET /therapist/policy-v2/controlled-governance/registry')
  })

  it('preserves a business-aware 409 error instead of a generic request failure', async () => {
    http.defaults.adapter = (async config => {
      const response = { data: { detail: 'proposal state conflict' }, status: 409, statusText: 'Conflict', headers: {}, config }
      throw new AxiosError('conflict', 'ERR_BAD_REQUEST', config, undefined, response)
    }) as AxiosAdapter
    await expect(controlledPolicyApi.apply('p','x')).rejects.toMatchObject<ApiError>({ status: 409, message: 'proposal state conflict' })
  })
})
