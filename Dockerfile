FROM python:3.9.2-slim-buster

# Create a non-root user and group
RUN groupadd -g 1001 nonrootgroup && \
    useradd -r -u 1001 -g nonrootgroup nonrootuser

# Update and install necessary dependencies
RUN apt-get update -y && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends gcc libffi-dev musl-dev ffmpeg aria2 python3-pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory and copy application files
WORKDIR /app
COPY . /app

# Change ownership of the /app directory to the non-root user
RUN chown -R nonrootuser:nonrootgroup /app

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Switch to the non-root user
USER nonrootuser

# Default command
CMD gunicorn app:app & python3 modules/main.py
