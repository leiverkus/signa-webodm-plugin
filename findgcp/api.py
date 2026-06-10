from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils.translation import gettext_lazy as _

from app.plugins.views import TaskView
from app.plugins.worker import run_function_async
from app.api.common import check_project_perms
from worker.tasks import TestSafeAsyncResult

from .gcp_detect import detect_gcps

# Predefined OpenCV ArUco dictionary ids span 0..20; 99 is Find-GCP's custom 3x3.
VALID_DICTS = set(range(0, 21)) | {99}


def _validate_params(data):
    """Validate detection parameters. Returns (params_dict, error_message)."""
    try:
        epsg = int(data.get('epsg'))
    except (TypeError, ValueError):
        return None, _('A valid EPSG code is required.')
    if not (1024 <= epsg <= 999999):
        return None, _('EPSG code out of range (1024–999999).')

    try:
        dict_id = int(data.get('dict', 1))
    except (TypeError, ValueError):
        return None, _('Invalid ArUco dictionary id.')
    if dict_id not in VALID_DICTS:
        return None, _('Unsupported ArUco dictionary id (use 0–20 or 99).')

    try:
        minrate = float(data.get('minrate', 0.01))
        ignore = float(data.get('ignore', 0.33))
    except (TypeError, ValueError):
        return None, _('Invalid detection parameters.')
    if not (0.0 < minrate <= 1.0):
        return None, _('minrate must be in the range (0, 1].')
    if not (0.0 <= ignore < 1.0):
        return None, _('ignore must be in the range [0, 1).')

    adjust = str(data.get('adjust', 'true')).lower() in ('1', 'true', 'on', 'yes')
    return {'epsg': epsg, 'dict_id': dict_id, 'minrate': minrate,
            'ignore': ignore, 'adjust': adjust}, None


class TaskFindGCPDetect(TaskView):
    """Start ArUco GCP detection for a task's images in a background worker.

    Tightened beyond WebODM's default TaskNestedView (AllowAny + public-task
    bypass): authentication is required and change_project permission is
    enforced even for public tasks, since detection is an expensive operation.
    """
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, pk=None):
        task = self.get_and_check_task(request, pk)
        # Enforce object-level permission even when the task/project is public.
        check_project_perms(request, task.project, ('change_project',))

        coords_file = request.FILES.get('coords')
        if coords_file is None:
            return Response({'error': _('No GCP coordinate file uploaded.')},
                            status=status.HTTP_200_OK)
        if coords_file.size > 5 * 1024 * 1024:
            return Response({'error': _('Coordinate file too large (max 5 MB).')},
                            status=status.HTTP_200_OK)
        try:
            coords_text = coords_file.read().decode('utf-8', errors='replace')
        except Exception:
            return Response({'error': _('Cannot read the coordinate file.')},
                            status=status.HTTP_200_OK)

        params, error = _validate_params(request.data)
        if error is not None:
            return Response({'error': error}, status=status.HTTP_200_OK)

        image_paths = [task.get_image_path(i) for i in task.scan_images()]
        if not image_paths:
            return Response({'error': _('This task has no images.')},
                            status=status.HTTP_200_OK)

        celery_task_id = run_function_async(
            detect_gcps, image_paths, coords_text, params['epsg'],
            params['dict_id'], params['minrate'], params['ignore'],
            params['adjust'], task.name).task_id

        return Response({'celery_task_id': celery_task_id}, status=status.HTTP_200_OK)


class TaskFindGCPCheck(APIView):
    """Poll detection status; on completion returns the summary and gcp_list text.

    Requires authentication (unlike WebODM's default AllowAny CheckTask) so that
    anonymous callers cannot read results by guessing a celery id.
    """
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, celery_task_id=None, **kwargs):
        res = TestSafeAsyncResult(celery_task_id)
        if not res.ready():
            out = {'ready': False}
            if res.state == 'PROGRESS' and res.info is not None:
                for k in res.info:
                    out[k] = res.info[k]
            return Response(out, status=status.HTTP_200_OK)

        result = res.get()
        if result.get('error') is not None:
            return Response({'ready': True, 'error': result['error']})

        return Response({'ready': True, 'summary': result.get('output')})
