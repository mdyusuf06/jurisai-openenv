FROM python:3.10-slim

WORKDIR /app

# Copy the entire project into the container
COPY . .

# Install the project and its dependencies using the new pyproject.toml
RUN pip install --no-cache-dir .

EXPOSE 7860
ENV PYTHONPATH=/app

# Start the server
CMD ["python", "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]