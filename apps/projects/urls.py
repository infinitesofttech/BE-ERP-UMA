from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProjectJobMasterViewSet,
    ProjectPlanningStageViewSet,
    ProjectTaskViewSet,
    DepartmentAssignmentViewSet,
    ProjectCostViewSet,
    ProjectDocumentViewSet,
)

# The root convenience router already serves /api/projects/ as the project list,
# so this router must not register its own API-root view at the same path.
router = DefaultRouter()
router.include_root_view = False
router.register(r'jobs', ProjectJobMasterViewSet, basename='project-job')
router.register(r'', ProjectJobMasterViewSet, basename='project')
router.register(r'planning-stages', ProjectPlanningStageViewSet, basename='planning-stage')
router.register(r'tasks', ProjectTaskViewSet, basename='task')
router.register(r'assignments', DepartmentAssignmentViewSet, basename='assignment')
router.register(r'costs', ProjectCostViewSet, basename='cost')
router.register(r'documents', ProjectDocumentViewSet, basename='document')

urlpatterns = [
    path('', include(router.urls)),
]
