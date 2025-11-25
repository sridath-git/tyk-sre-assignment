
FROM python:3.10-slim

WORKDIR /app

# Copying the Python project
COPY python/ /app/

# Install all dependencies mentioned in the requirements.txt
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# Expose default port
EXPOSE 8080

# Start the application
CMD ["python3", "main.py", "--address", ":8080"]
