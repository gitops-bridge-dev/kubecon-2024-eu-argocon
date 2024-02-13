# docker buildx build . --push -t csantanapr/python-argocon:1.2 --platform linux/amd64,linux/arm/v6,linux/arm/v7,linux/arm64
FROM python:3.11-alpine

COPY scripts/requirements.txt .
RUN pip install -r requirements.txt
COPY scripts/sharedlib /usr/local/lib/python3.11/site-packages/sharedlib
