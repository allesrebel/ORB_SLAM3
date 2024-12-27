echo "Configuring and building ORB_SLAM3 ..."

cmake -B build -DCMAKE_BUILD_TYPE=Release -DASSERT_DISABLE=ON
#cmake -B build -DCMAKE_BUILD_TYPE=Debug -DASSERT_DISABLE=OFF
cmake --build build -j$(nproc)
