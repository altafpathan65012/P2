FROM python:3.9.2-slim-buster
RUN apt-get update -y && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends gcc libffi-dev musl-dev ffmpeg aria2 python3-pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . /app/
WORKDIR /app/
RUN pip3 install -r requirements.txt
CMD gunicorn app:app & python3 modules/main.py

# Use an official image as the base
FROM ubuntu:latest

# Create a new user with a specific UID
RUN useradd -u 10014 nonrootuser

# Set the user for the container
USER 10014

# Add application setup commands below
WORKDIR /app
COPY . /app
RUN chmod -R 755 /app

# Define the default command
CMD ["python3 modules/main.py", "app.py"]
