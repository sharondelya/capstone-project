# Use an appropriate base image (adjust based on your project type)
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements file (if you have one)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose port (adjust as needed)
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app
ENV DATABASE_URL=${DATABASE_URL}
ENV DB_HOST=${DB_HOST}
ENV DB_PORT=${DB_PORT}
ENV DB_NAME=${DB_NAME}
ENV DB_USER=${DB_USER}
ENV DB_PASSWORD=${DB_PASSWORD}
ENV FLASK_SECRET_KEY={{SECRET_KEY}}
ENV FLASK_ENV=production

# Command to run database initialization followed by your application
CMD ["sh", "-c", "python Database_initialization.py && python app.py"]