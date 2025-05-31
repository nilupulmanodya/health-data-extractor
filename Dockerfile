FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt
RUN pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Create upload directory
RUN mkdir -p temp_uploads

# Expose the port the app runs on
EXPOSE 5000

# Command to run the application with explicit host and port
CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "5000"] 
