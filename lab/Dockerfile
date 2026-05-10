FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir "asyncssh>=2.14.0,<3"

COPY mock_cisco_device.py /app/

EXPOSE 22

CMD ["python", "/app/mock_cisco_device.py"]
