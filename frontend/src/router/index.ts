import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '@/views/LoginView.vue'
import PatientLayout from '@/layouts/PatientLayout.vue'
import FamilyLayout from '@/layouts/FamilyLayout.vue'
import TherapistLayout from '@/layouts/TherapistLayout.vue'
import HomeView from '@/views/patient/HomeView.vue'
import AgentCreateView from '@/views/patient/AgentCreateView.vue'
import AgentListView from '@/views/patient/AgentListView.vue'
import TrainingView from '@/views/patient/TrainingView.vue'
import TrainingSessionView from '@/views/patient/TrainingSessionView.vue'
import TrainingResultView from '@/views/patient/TrainingResultView.vue'
import ReportView from '@/views/patient/ReportView.vue'
import { useAuthStore } from '@/stores/auth'
import type { UserRole } from '@/types/api'

const roleHome: Record<UserRole, string> = {
  patient: '/home',
  family: '/family',
  therapist: '/therapist',
  admin: '/therapist'
}

function canAccess(userRole: UserRole, requiredRole: UserRole) {
  if (userRole === requiredRole) return true
  return userRole === 'admin' && requiredRole === 'therapist'
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/home' },
    { path: '/login', component: LoginView },
    {
      path: '/',
      component: PatientLayout,
      meta: { role: 'patient' },
      children: [
        { path: 'home', component: HomeView, meta: { role: 'patient' } },
        { path: 'agent/create', component: AgentCreateView, meta: { role: 'patient' } },
        { path: 'agent/list', component: AgentListView, meta: { role: 'patient' } },
        { path: 'training', component: TrainingView, meta: { role: 'patient' } },
        { path: 'training/:type(repeat|scenario)', component: TrainingSessionView, meta: { role: 'patient' } },
        { path: 'training/scenario/result/:dialogueId', component: () => import('@/views/patient/ScenarioDialogueResultView.vue'), meta: { role: 'patient' } },
        { path: 'training/result', component: TrainingResultView, meta: { role: 'patient' } },
        { path: 'evaluation', component: () => import('@/views/patient/EvaluationView.vue'), meta: { role: 'patient' } },
        { path: 'ability', component: () => import('@/views/patient/AbilityProfileView.vue'), meta: { role: 'patient' } },
        { path: '/patient/profile', component: () => import('@/views/patient/PatientProfileView.vue'), meta: { role: 'patient' } },
        { path: 'report', component: ReportView, meta: { role: 'patient' } }
      ]
    },
    {
      path: '/family',
      component: FamilyLayout,
      meta: { role: 'family' },
      children: [
        { path: '', component: () => import('@/views/family/FamilyDashboardView.vue'), meta: { role: 'family' } }
      ]
    },
    {
      path: '/therapist',
      component: TherapistLayout,
      meta: { role: 'therapist' },
      children: [
        { path: '', component: () => import('@/views/therapist/TherapistDashboardView.vue'), meta: { role: 'therapist' } },
        {
          path: 'assessments',
          component: () => import('@/views/therapist/TherapistAssessmentsView.vue'),
          meta: { role: 'therapist' }
        },
        {
          path: 'profiles',
          component: () => import('@/views/therapist/TherapistProfilesView.vue'),
          meta: { role: 'therapist' }
        },
        { path: 'patients', component: () => import('@/views/therapist/PatientsView.vue'), meta: { role: 'therapist' } },
        { path: 'patients/:patientId/:tab(overview|training|assessment|clinical-stage|profile|policy|controlled-actions)?', component: () => import('@/views/therapist/PatientWorkspaceView.vue'), meta: { role: 'therapist' } },
        // Internal calibration/governance routes are deliberately not exposed in
        // the therapist product shell. Keep legacy deep links harmless.
        { path: 'calibration', redirect: '/therapist' },
        { path: 'policy-validation', redirect: '/therapist' },
        { path: 'governance', redirect: '/therapist' },
        { path: 'scenario-dialogues/:dialogueId', component: () => import('@/views/therapist/TherapistScenarioDialogueReviewView.vue'), meta: { role: 'therapist' } },
        {
          path: 'status',
          component: () => import('@/views/therapist/SystemStatusView.vue'),
          meta: { role: 'therapist' }
        }
      ]
    }
  ]
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (to.path !== '/login' && !auth.isAuthenticated) return '/login'
  if (auth.isAuthenticated && !auth.me) {
    try {
      await auth.fetchMe()
    } catch {
      auth.logout()
      return '/login'
    }
  }
  if (to.path === '/login' && auth.isAuthenticated && auth.me) {
    return roleHome[auth.me.user.role]
  }
  const requiredRole = to.matched.find((item) => item.meta.role)?.meta.role as UserRole | undefined
  if (requiredRole && auth.me && !canAccess(auth.me.user.role, requiredRole)) {
    return roleHome[auth.me?.user.role || 'patient']
  }
})

export default router
