FROM python:3.13-slim
WORKDIR /setup
COPY setup.py .
CMD ["python", "setup.py"]
