echo "Configuring and building ORB_SLAM3 ..."

mkdir -p build
cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
#cmake .. -DCMAKE_BUILD_TYPE=Debug# -DNDEBUG # if you don't want asserts
cmake --build . -j$(nproc)
