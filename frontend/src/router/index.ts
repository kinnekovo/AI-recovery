import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '@/views/LoginView.vue'
import PatientLayout from '@/layouts/PatientLayout.vue'
import HomeView from '@/views/patient/HomeView.vue'
import AgentCreateView from '@/views/patient/AgentCreateView.vue'
import AgentListView from '@/views/patient/AgentListView.vue'
import TrainingView from '@/views/patient/TrainingView.vue'
import TrainingSessionView from '@/views/patient/TrainingSessionView.vue'
import TrainingResultView from '@/views/patient/TrainingResultView.vue'
import ReportView from '@/views/patient/ReportView.vue'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/home' },
    { path: '/login', component: LoginView },
    {
      path: '/',
      component: PatientLayout,
      children: [
        { path: 'home', component: HomeView },
        { path: 'agent/create', component: AgentCreateView },
        { path: 'agent/list', component: AgentListView },
        { path: 'training', component: TrainingView },
        { path: 'training/:type(repeat|scenario)', component: TrainingSessionView },
        { path: 'training/result', component: TrainingResultView },
        { path: 'report', component: ReportView }
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
})

export default router
