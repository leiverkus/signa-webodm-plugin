# Custom WebODM image with OpenCV, for the Find-GCP plugin.
#
# Why: the Find-GCP detection runs in the Celery WORKER via WebODM's
# run_function_async -> eval_async (app/plugins/worker.py), which compiles the
# function source in a bare namespace. The plugin's requirements.txt is only
# importable during web-side calls, so cv2 must exist in the image the worker
# runs. WebODM's docker-compose uses the SAME image for both the `webapp` and
# `worker` services: webodm/webodm_webapp. We extend it here and use this image
# for both services (see docker-compose.findgcp.yml).
#
# numpy already ships with WebODM, so we only add OpenCV (headless = no GUI/X11).
#
# IMPORTANT — reproducibility: pin WEBODM_VERSION to the EXACT tag your WebODM
# runs, so the worker executes the same code as the rest of the stack. Do not
# ship `latest` to production.
#
# Build:
#   docker build -t webodm-findgcp:0.2.0 \
#     --build-arg WEBODM_VERSION=<your-webodm-image-tag> \
#     -f docker/worker.Dockerfile docker/

ARG WEBODM_VERSION=latest
FROM webodm/webodm_webapp:${WEBODM_VERSION}

RUN pip install --no-cache-dir "opencv-contrib-python-headless~=4.10"
