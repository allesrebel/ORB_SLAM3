# Use Ubuntu 22.04 (Jammy Jellyfish) as the base image
FROM ubuntu:jammy

# Set environment variable to prevent user interaction during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Run apt update as root user
RUN apt update
RUN apt install -y cmake python3 python3-pip binutils wget g++

# Copy Artifacts
COPY ORB_SLAM3/. /root/.

# Copy Dataset Artifact
COPY Datasets /root/Datasets

WORKDIR /root

# Create the executables
RUN ./build.sh
