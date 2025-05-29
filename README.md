# Health Data Extractor

A Flask-based web application for extracting and processing health data from PDF files.

## Prerequisites

- Docker
- Docker Compose

## Quick Start

1. Clone the repository:
```bash
git clone <repository-url>
cd health-data-extractor
```

2. Build and start the application using Docker Compose:
```bash
docker-compose up --build
```

The application will be available at `http://localhost:5000`

## Docker Setup Details

### Using Docker Compose (Recommended)

The project includes a `docker-compose.yml` file that sets up the entire environment:

- Builds the application using the Dockerfile
- Maps port 5000 to your host machine
- Creates a persistent volume for temporary uploads
- Sets up production environment
- Configures automatic restart

To start the application:
```bash
docker-compose up --build
```

To run in detached mode:
```bash
docker-compose up -d
```

To stop the application:
```bash
docker-compose down
```

### Manual Docker Build

If you prefer to use Docker directly:

1. Build the Docker image:
```bash
docker build -t health-data-extractor .
```

2. Run the container:
```bash
docker run -p 5000:5000 -v $(pwd)/temp_uploads:/app/temp_uploads health-data-extractor
```

## Project Structure

- `app.py` - Main Flask application
- `extract_tables.py` - PDF table extraction logic
- `json_to_excel.py` - JSON to Excel conversion utilities
- `requirements.txt` - Python dependencies
- `Dockerfile` - Docker build instructions
- `docker-compose.yml` - Docker Compose configuration
- `temp_uploads/` - Directory for temporary file uploads

## Environment Variables

The following environment variables are configured in the Docker setup:

- `FLASK_ENV=production` - Sets the Flask environment to production mode

## Notes

- The application uses port 5000 by default
- Temporary uploads are persisted in the `temp_uploads` directory
- The container will automatically restart unless explicitly stopped
- The application uses Python 3.11 with a slim base image for optimal size

## Troubleshooting

If you encounter any issues:

1. Check if the container is running:
```bash
docker ps
```

2. View container logs:
```bash
docker-compose logs
```

3. Ensure port 5000 is not in use by another application

4. Verify that the `temp_uploads` directory has proper permissions:
```bash
chmod 755 temp_uploads
``` 