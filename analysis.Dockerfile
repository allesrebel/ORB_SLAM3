# Use the esolang/python2 image as the base
FROM esolang/python2:latest


RUN apk update
# Dependencies for Matplot Lib + Numpy for Python2
RUN apk add freetype-dev pkgconf qhull libpng-dev

# Install any additional Python packages (if needed)
RUN python -m pip install --upgrade pip
RUN python -m pip install -U pip setuptools wheel
RUN python -m pip install numpy matplotlib

# Set the working directory inside the container
WORKDIR /app

# Copy any Python scripts or other files from the local machine into the container
COPY ./evaluation/evaluate_ate_scale.py /app/evaluate_ate_scale.py
COPY ./evaluation/associate.py /app/associate.py
COPY ./evaluation/Ground_truth /app/Ground_truth

# Run the Python script when the container starts
CMD ["bash"]

# example!
# python evaluate_ate_scale Ground_truth/EuRoC_left_cam/MH05_GT.txt /data/f_dataset-MH05_stereo.txt --verbose
