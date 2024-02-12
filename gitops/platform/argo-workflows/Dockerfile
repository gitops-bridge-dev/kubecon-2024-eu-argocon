# docker buildx build . --push -t csantanapr/python-argocon:1.0 --platform linux/amd64,linux/arm/v6,linux/arm/v7,linux/arm64
FROM python:3.11-alpine

COPY scripts/requirements.txt .
RUN pip install -r requirements.txt



