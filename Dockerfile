FROM python:3.11-slim

WORKDIR /app

# Install minimal requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and scripts
COPY src/ /app/src/
COPY tests/ /app/tests/
COPY run.py baseline_3sigma.py validate_submission.py /app/

# Default entrypoint runs pipeline and validates output
CMD ["python", "run.py", "--data", "data", "--out", "predictions.csv"]
