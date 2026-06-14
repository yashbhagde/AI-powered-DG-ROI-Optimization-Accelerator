# Use a lightweight official Python slim image
FROM python:3.11-slim

# Set environment variables to prevent Python from writing pyc files and buffering stdout
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set the working directory inside the container
WORKDIR /app

# Copy only requirements.txt first to leverage Docker build cache layers
COPY requirements.txt /app/

# Install dependencies without cache to minimize image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files to the container
COPY . /app/

# Set the entrypoint to summon the executive report generator script directly
ENTRYPOINT ["python", "executive_pdf_report.py"]
