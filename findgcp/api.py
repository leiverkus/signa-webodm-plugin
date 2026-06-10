from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils.translation import gettext_lazy as _

from app.plugins import UserDataStore
from app.plugins.views import TaskView
from app.plugins.worker import run_function_async
from app.api.common import check_project_perms
from worker.tasks import TestSafeAsyncResult

from .gcp_detect import detect_gcps

# Predefined OpenCV ArUco dictionary ids span 0..20; 99 is Find-GCP's custom 3x3.
VALID_DICTS = set(range(0, 21)) | {99}

# Datastore namespace. Must equal the plugin directory name (what
# PluginBase.get_name() / get_user_data_store() use), so detect (write) and
# check (read) address the same per-user store.
PLUGIN_NAMESPACE = "findgcp"


def _run_key(celery_task_id):
    return "run:{}".format(celery_task_id)


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

        # Bind this run to the requesting user (per-user datastore) and to the
        # task, so only the owner can poll/read its result.
        store = UserDataStore(PLUGIN_NAMESPACE, request.user)
        store.set_string(_run_key(celery_task_id), str(task.id))

        return Response({'celery_task_id': celery_task_id}, status=status.HTTP_200_OK)


class TaskFindGCPCheck(APIView):
    """Poll detection status; on completion returns the summary and gcp_list text.

    Results are bound to the user who started the run via the plugin's per-user
    datastore, and to the task: the run's celery id must be recorded in the
    requesting user's store with a matching task pk. This closes the gap where
    any authenticated user could read a result by knowing its celery id.
    """
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, pk=None, celery_task_id=None, **kwargs):
        store = UserDataStore(PLUGIN_NAMESPACE, request.user)
        owned_task = store.get_string(_run_key(celery_task_id), "")
        if not owned_task or owned_task != str(pk):
            # Not started by this user (or not for this task). Return a terminal
            # error (HTTP 200) so the client stops polling instead of looping.
            return Response({'ready': True, 'error': _('Result not found.')},
                            status=status.HTTP_200_OK)

        res = TestSafeAsyncResult(celery_task_id)
        if not res.ready():
            out = {'ready': False}
            if res.state == 'PROGRESS' and res.info is not None:
                for k in res.info:
                    out[k] = res.info[k]
            return Response(out, status=status.HTTP_200_OK)

        # Terminal: release the ownership record (the gcp_list is delivered here
        # and downloaded client-side, so the run does not need to be re-read).
        result = res.get()
        store.del_key(_run_key(celery_task_id))

        if result.get('error') is not None:
            return Response({'ready': True, 'error': result['error']})

        return Response({'ready': True, 'summary': result.get('output')})
