import uuid
from datetime import datetime
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action

from apps.core.models import NumberingSetting
from .models import (
    ProjectJobMaster,
    ProjectPlanningStage,
    ProjectMilestone,
    ProjectDocument,
    ProjectTask,
    DepartmentAssignment,
    ProjectIssue,
    ProjectDelay,
    CustomerChangeRequest,
    ProjectCost,
)
from .serializers import (
    ProjectJobMasterSerializer,
    ProjectPlanningStageSerializer,
    ProjectMilestoneSerializer,
    ProjectDocumentSerializer,
    ProjectTaskSerializer,
    DepartmentAssignmentSerializer,
    ProjectIssueSerializer,
    ProjectDelaySerializer,
    CustomerChangeRequestSerializer,
    ProjectCostSerializer,
)

STANDARD_16_STAGE_DEFINITIONS = [
    {'num': 1, 'name': 'Order Confirmation & Kickoff', 'dept': 'crm', 'emp': 'Pravin Patel', 'desc': 'Sales Order confirmed, commercial terms agreed, customer PO received and internal kickoff.'},
    {'num': 2, 'name': 'Project Creation & Job Allocation', 'dept': 'project', 'emp': 'Bhavin Shah', 'desc': 'Job Number and Project File created. PM, Design lead and Shop supervisor assigned.'},
    {'num': 3, 'name': 'Design CAD 3D & GA Drawings', 'dept': 'designer', 'emp': 'Dharmesh Joshi', 'desc': 'Mechanical 3D modeling, General Arrangement (GA) drawing and nozzle orientation details.'},
    {'num': 4, 'name': 'Customer Design Approval & Sign-off', 'dept': 'designer', 'emp': 'Dharmesh Joshi', 'desc': 'GA Drawing submitted to customer engineering for official approval and revision lock.'},
    {'num': 5, 'name': 'BOM Finalization & Indent Release', 'dept': 'designer', 'emp': 'Dharmesh Joshi', 'desc': 'BOM exploded into raw plates, forgings, pipes, fasteners and bought-out components.'},
    {'num': 6, 'name': 'Material Planning & Stock Reservation', 'dept': 'store', 'emp': 'Hitesh Rawal', 'desc': 'Warehouse inventory check, stock reservation, and purchase requisition trigger.'},
    {'num': 7, 'name': 'Purchase Requisitions & Supplier POs', 'dept': 'purchase', 'emp': 'Vikram Solanki', 'desc': 'Supplier quotations, commercial comparison, PO release for steel plates, motors & seals.'},
    {'num': 8, 'name': 'Material Receipt & GRN Inspection', 'dept': 'store', 'emp': 'Hitesh Rawal', 'desc': 'Material arrival, Mill Test Certificate (MTC) verification, and GRN inward clearance.'},
    {'num': 9, 'name': 'Production Planning & Routing Card', 'dept': 'production', 'emp': 'Bhavin Shah', 'desc': 'Fabrication bay allocation, CNC cutting plans, welding procedure specification (WPS).'},
    {'num': 10, 'name': 'Raw Material Cutting & Rolling', 'dept': 'production', 'emp': 'Bhavin Shah', 'desc': 'Shell plate CNC plasma cutting, bevelling, and plate rolling machine operation.'},
    {'num': 11, 'name': 'Fabrication, Fit-up & Welding', 'dept': 'production', 'emp': 'Bhavin Shah', 'desc': 'Long-seam and circ-seam SAW/TIG welding, dish end fit-up and nozzle orientation welding.'},
    {'num': 12, 'name': 'Intermediate NDT & Quality Stage Inspection', 'dept': 'production', 'emp': 'Ketan Patel', 'desc': '100% Radiography Testing (RT), Dye Penetrant (DP) and Ultrasonic Testing (UT) on joints.'},
    {'num': 13, 'name': 'Assembly, Agitator & Drive Integration', 'dept': 'production', 'emp': 'Bhavin Shah', 'desc': 'Internal cooling coils, anchor agitator shaft alignment, mechanical seal and gearbox mounting.'},
    {'num': 14, 'name': 'Hydro Testing, FAT & Customer Inspection', 'dept': 'production', 'emp': 'Ketan Patel', 'desc': 'Hydrostatic pressure test at 12.5 Bar shell, hold for 4 hours and joint customer inspection.'},
    {'num': 15, 'name': 'Surface Finishing, Painting & Packaging', 'dept': 'production', 'emp': 'Bhavin Shah', 'desc': 'Internal electro-polishing to mirror finish (Ra < 0.4 um), external epoxy primer and PU paint.'},
    {'num': 16, 'name': 'Commercial Invoicing & Dispatch Handover', 'dept': 'accounting', 'emp': 'Pravin Patel', 'desc': 'Final tax invoice raised, dispatch clearance note issued, transit insurance and truck loading.'},
]


def auto_generate_16_stages(project_id):
    created_stages = []
    for s in STANDARD_16_STAGE_DEFINITIONS:
        stage_id = f"stg-{project_id.lower()}-{s['num']:02d}"
        obj, _ = ProjectPlanningStage.objects.update_or_create(
            id=stage_id,
            defaults={
                'project_id': project_id,
                'stage_number': s['num'],
                'name': s['name'],
                'department': s['dept'],
                'assigned_employee_name': s['emp'],
                'assignees': [{'name': s['emp'], 'department': s['dept']}],
                'status': 'pending',
                'progress': 0,
                'description': s['desc'],
                'planned_duration_days': 7,
            }
        )
        created_stages.append(obj)
    return created_stages


class ProjectJobMasterViewSet(viewsets.ModelViewSet):
    queryset = ProjectJobMaster.objects.all().order_by('-created_at', '-id')
    serializer_class = ProjectJobMasterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        if not data.get('id') and not data.get('project_number') and not data.get('projectNumber'):
            num_setting = NumberingSetting.objects.filter(doc_type='project').first()
            if num_setting:
                p_code = num_setting.generate_next_number(increment=True)
            else:
                next_num = ProjectJobMaster.objects.count() + 1
                p_code = f"PRJ-2026-{next_num:04d}"
                while ProjectJobMaster.objects.filter(id=p_code).exists():
                    next_num += 1
                    p_code = f"PRJ-2026-{next_num:04d}"
            j_code = p_code.replace('PRJ-', 'JOB-')
            data['id'] = p_code
            data['project_number'] = p_code
            data['job_number'] = j_code
        elif not data.get('id'):
            data['id'] = data.get('project_number') or data.get('projectNumber')
        if not data.get('target_delivery_date') and not data.get('targetDeliveryDate'):
            data['target_delivery_date'] = data.get('deliveryDate') or data.get('delivery_date') or datetime.now().strftime('%Y-%m-%d')
        if not data.get('start_date') and not data.get('startDate'):
            data['start_date'] = datetime.now().strftime('%Y-%m-%d')
        if not data.get('project_manager_name') and not data.get('projectManagerName'):
            data['project_manager_name'] = data.get('projectManager') or 'Bhavin Shah'
        if not data.get('current_status') and not data.get('currentStatus'):
            data['current_status'] = data.get('status') or 'planning'

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        project = serializer.save()

        # Auto-create the 16 Standard Planning Stages!
        auto_generate_16_stages(project.id)

        return Response(ProjectJobMasterSerializer(project).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='generate-stages')
    def generate_stages(self, request, pk=None):
        project = self.get_object()
        stages = auto_generate_16_stages(project.id)
        return Response({
            'success': True,
            'message': f'Generated {len(stages)} planning stages for project {project.id}',
            'stages': ProjectPlanningStageSerializer(stages, many=True).data
        })


class ProjectPlanningStageViewSet(viewsets.ModelViewSet):
    queryset = ProjectPlanningStage.objects.all().order_by('stage_number')
    serializer_class = ProjectPlanningStageSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        project_id = self.request.query_params.get('projectId') or self.request.query_params.get('project_id')
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    def create(self, request, *args, **kwargs):
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        proj_id = data.get('project_id') or data.get('projectId') or 'PRJ-DEFAULT'
        data['project_id'] = proj_id
        stage_num = int(data.get('stage_number') or data.get('stageNumber') or 1)
        data['stage_number'] = stage_num

        stage_id = data.get('id') or f"stg-{proj_id.lower()}-{stage_num:02d}"
        
        # Check if record already exists by ID or by (project_id, stage_number) to prevent duplicates
        existing = ProjectPlanningStage.objects.filter(id=stage_id).first()
        if not existing:
            existing = ProjectPlanningStage.objects.filter(project_id=proj_id, stage_number=stage_num).first()
            
        if existing:
            serializer = self.get_serializer(existing, data=data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        data['id'] = stage_id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        pk = kwargs.get('pk', '')
        # Delete case-insensitively
        deleted_count, _ = ProjectPlanningStage.objects.filter(id__iexact=pk).delete()
        if deleted_count > 0:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['post'], url_path='clear-and-reset')
    def clear_and_reset(self, request):
        project_id = request.data.get('projectId') or request.data.get('project_id')
        if not project_id:
            return Response({'error': 'projectId is required'}, status=status.HTTP_400_BAD_REQUEST)
        ProjectPlanningStage.objects.filter(project_id__iexact=project_id).delete()
        stages = auto_generate_16_stages(project_id)
        return Response({
            'success': True,
            'message': f'Reset 16 stages for {project_id}',
            'stages': ProjectPlanningStageSerializer(stages, many=True).data
        })

    @action(detail=False, methods=['post'], url_path='save-project-stages')
    def save_project_stages(self, request):
        project_id = request.data.get('projectId') or request.data.get('project_id')
        if not project_id:
            return Response({'error': 'projectId is required'}, status=status.HTTP_400_BAD_REQUEST)
        stages_data = request.data.get('stages', [])
        # Delete existing stages for this project
        ProjectPlanningStage.objects.filter(project_id__iexact=project_id).delete()
        created_stages = []
        for s in stages_data:
            s_data = s.copy() if hasattr(s, 'copy') else dict(s)
            s_data['project_id'] = project_id
            stage_num = int(s_data.get('stage_number') or s_data.get('stageNumber') or 1)
            s_data['stage_number'] = stage_num
            s_id = s_data.get('id') or f"stg-{project_id.lower()}-{stage_num:02d}"
            s_data['id'] = s_id
            serializer = self.get_serializer(data=s_data)
            if serializer.is_valid():
                obj = serializer.save()
                created_stages.append(obj)
            else:
                obj = ProjectPlanningStage.objects.create(
                    id=s_id,
                    project_id=project_id,
                    stage_number=stage_num,
                    name=s_data.get('name') or s_data.get('stageName') or f'Stage {stage_num}',
                    department=s_data.get('department') or s_data.get('responsibleDepartment') or 'production',
                    assigned_employee_name=s_data.get('assigned_employee_name') or s_data.get('responsibleEmployee') or '',
                    assignees=s_data.get('assignees') or s_data.get('assignedEmployees') or [],
                    status=s_data.get('status') or 'pending',
                    progress=int(s_data.get('progress') or s_data.get('progressPercent') or 0),
                    start_date=s_data.get('start_date') or s_data.get('plannedStart') or '',
                    end_date=s_data.get('end_date') or s_data.get('plannedEnd') or '',
                    description=s_data.get('description') or s_data.get('remarks') or '',
                )
                created_stages.append(obj)
        return Response({
            'success': True,
            'message': f'Saved {len(created_stages)} stages for {project_id}',
            'stages': ProjectPlanningStageSerializer(created_stages, many=True).data
        })

    @action(detail=True, methods=['post'], url_path='complete')
    def mark_completed(self, request, pk=None):
        stage = self.get_object()
        stage.status = 'completed'
        stage.progress = 100
        stage.completed_by = request.data.get('completedBy') or request.data.get('completed_by', 'Current User')
        stage.completion_notes = request.data.get('notes') or request.data.get('completionNotes', '')
        stage.completed_at = datetime.now().strftime('%Y-%m-%d %I:%M %p')
        stage.save()
        return Response(ProjectPlanningStageSerializer(stage).data)


class ProjectMilestoneViewSet(viewsets.ModelViewSet):
    queryset = ProjectMilestone.objects.all().order_by('planned_date', 'target_date')
    serializer_class = ProjectMilestoneSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        if not data.get('id'):
            data['id'] = f"MS-{uuid.uuid4().hex[:8]}"
        if 'milestone_name' not in data:
            data['milestone_name'] = data.get('milestoneName') or data.get('title') or 'Milestone Checkpoint'
        if 'title' not in data:
            data['title'] = data['milestone_name']
        if 'project_id' not in data:
            data['project_id'] = data.get('projectId') or 'PRJ-2026-0001'
        if 'project_number' not in data:
            data['project_number'] = data.get('projectNumber') or ''
        if 'job_number' not in data:
            data['job_number'] = data.get('jobNumber') or ''
        if 'planned_date' not in data:
            data['planned_date'] = data.get('plannedDate') or data.get('target_date') or datetime.now().strftime('%Y-%m-%d')
        if 'target_date' not in data:
            data['target_date'] = data['planned_date']
        if 'owner' not in data:
            data['owner'] = data.get('owner') or 'Bhavin Shah'
        if 'status' not in data:
            data['status'] = 'pending'

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProjectTaskViewSet(viewsets.ModelViewSet):
    queryset = ProjectTask.objects.all().order_by('-id')
    serializer_class = ProjectTaskSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        if not data.get('id'):
            data['id'] = f"TSK-2026-{ProjectTask.objects.count() + 1:03d}"
        if 'title' not in data:
            data['title'] = data.get('task_name') or data.get('taskName') or 'Project Task'
        if 'project_id' not in data:
            data['project_id'] = data.get('projectId') or 'PRJ-2026-0001'
        if 'task_number' not in data:
            data['task_number'] = data.get('taskNumber') or data['id']
        if 'department' not in data:
            data['department'] = data.get('department') or 'production'
        if 'assigned_to_name' not in data:
            data['assigned_to_name'] = data.get('assignedTo') or data.get('assigned_to') or 'Bhavin Shah'
        if 'due_date' not in data:
            data['due_date'] = data.get('dueDate') or data.get('due_date') or ''

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProjectDocumentViewSet(viewsets.ModelViewSet):
    queryset = ProjectDocument.objects.all().order_by('-created_at', '-id')
    serializer_class = ProjectDocumentSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        if not data.get('id'):
            data['id'] = f"DOC-{uuid.uuid4().hex[:8]}"
        if 'document_name' not in data:
            data['document_name'] = data.get('documentName') or data.get('name') or 'Project Document'
        if 'project_id' not in data:
            data['project_id'] = data.get('projectId') or 'PRJ-2026-0001'
        if 'job_number' not in data:
            data['job_number'] = data.get('jobNumber') or ''
        if 'type' not in data:
            data['type'] = data.get('docType') or 'Drawing'
        if 'version' not in data:
            data['version'] = data.get('version') or 'v1.0'
        if 'uploaded_by' not in data:
            data['uploaded_by'] = data.get('uploadedBy') or 'Super Admin'
        if 'department' not in data:
            data['department'] = data.get('department') or 'Design'
        if 'file_size' not in data:
            data['file_size'] = data.get('fileSize') or '1.5 MB'
        if 'upload_date' not in data:
            data['upload_date'] = data.get('uploadDate') or datetime.now().strftime('%Y-%m-%d')

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)



class DepartmentAssignmentViewSet(viewsets.ModelViewSet):
    queryset = DepartmentAssignment.objects.all().order_by('department')
    serializer_class = DepartmentAssignmentSerializer
    permission_classes = [permissions.AllowAny]


class ProjectIssueViewSet(viewsets.ModelViewSet):
    queryset = ProjectIssue.objects.all().order_by('-created_date', '-id')
    serializer_class = ProjectIssueSerializer
    permission_classes = [permissions.AllowAny]


class ProjectDelayViewSet(viewsets.ModelViewSet):
    queryset = ProjectDelay.objects.all().order_by('-date', '-id')
    serializer_class = ProjectDelaySerializer
    permission_classes = [permissions.AllowAny]


class CustomerChangeRequestViewSet(viewsets.ModelViewSet):
    queryset = CustomerChangeRequest.objects.all().order_by('-created_at', '-id')
    serializer_class = CustomerChangeRequestSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        if not data.get('id'):
            data['id'] = f"CR-{uuid.uuid4().hex[:8]}"
        if 'change_request_no' not in data:
            data['change_request_no'] = data.get('changeRequestNo') or data['id']
        if 'request_no' not in data:
            data['request_no'] = data.get('change_request_no') or data['id']
        if 'project_id' not in data:
            data['project_id'] = data.get('projectId') or 'PRJ-2026-0001'
        if 'project_number' not in data:
            data['project_number'] = data.get('projectNumber') or ''
        if 'job_number' not in data:
            data['job_number'] = data.get('jobNumber') or ''
        if 'customer_name' not in data:
            data['customer_name'] = data.get('customerName') or ''
        if 'requested_by' not in data:
            data['requested_by'] = data.get('requestedBy') or 'Customer Representative'
        if 'title' not in data:
            data['title'] = data.get('changeDescription') or data.get('change_description') or 'Change Request'
        if 'change_description' not in data:
            data['change_description'] = data.get('changeDescription') or data.get('description') or ''
        if 'description' not in data:
            data['description'] = data.get('change_description') or ''
        if 'reason' not in data:
            data['reason'] = data.get('reason') or ''
        if 'design_impact' not in data:
            data['design_impact'] = data.get('designImpact') or ''
        if 'material_impact' not in data:
            data['material_impact'] = data.get('materialImpact') or ''
        if 'cost_impact' not in data:
            data['cost_impact'] = data.get('costImpact') or 0
        if 'timeline_impact_days' not in data:
            data['timeline_impact_days'] = data.get('timelineImpactDays') or 0
        if 'approval_status' not in data:
            data['approval_status'] = data.get('approvalStatus') or 'requested'
        if 'status' not in data:
            data['status'] = data.get('status') or 'pending'
        if 'request_date' not in data:
            data['request_date'] = data.get('requestDate') or datetime.now().strftime('%Y-%m-%d')

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProjectCostViewSet(viewsets.ModelViewSet):
    queryset = ProjectCost.objects.all().order_by('category')
    serializer_class = ProjectCostSerializer
    permission_classes = [permissions.AllowAny]
