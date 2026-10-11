FROM registry.access.redhat.com/ubi9/python-311:latest

WORKDIR /opt/app-root/src

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

ENV PORT=8080
EXPOSE 8080

USER 1001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
