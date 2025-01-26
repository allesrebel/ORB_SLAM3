echo "Configuring and building ORB_SLAM3 ..."

# 1. Configure (generate build system in 'build' directory)
#cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug -DCMAKE_CXX_FLAGS_DEBUG="-DNDEBUG -g" # if you don't want asserts

# 2. Build the project from 'build' directory
cmake --build build -j"$(nproc)"
