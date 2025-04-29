cmake_minimum_required(VERSION 3.5)
project(ORB_SLAM3)

IF(NOT CMAKE_BUILD_TYPE)
  SET(CMAKE_BUILD_TYPE Release)
ENDIF()

message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
add_definitions(-DBUILD_TYPE="${CMAKE_BUILD_TYPE}")

option(ASSERT_DISABLE "Disable Asserts via NDEBUG define" ON)
if(ASSERT_DISABLE)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -DNDEBUG")
    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -DNDEBUG")
    message(STATUS "Asserts: Disabled")
else()
    message(STATUS "Asserts: Enabled!!!")
endif()

# Check if tar is installed
execute_process(
    COMMAND tar --version
    RESULT_VARIABLE tar_installed
    OUTPUT_QUIET
    ERROR_QUIET
)
if(NOT tar_installed EQUAL 0)
    message(STATUS "tar is not installed. Installing tar...")

    # Check if the user is root
    execute_process(
        COMMAND id -u
        OUTPUT_VARIABLE USER_ID
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )

    if(USER_ID EQUAL 0)
        execute_process(
            COMMAND apt-get update
            COMMAND apt-get install -y tar
            RESULT_VARIABLE install_result
        )
    else()
        execute_process(
            COMMAND sudo apt-get update
            COMMAND sudo apt-get install -y tar
            RESULT_VARIABLE install_result
        )
    endif()

    if(NOT install_result EQUAL 0)
        message(FATAL_ERROR "Failed to install tar. Please install it manually.")
    endif()
endif()

# Check if the vocabulary file exists and extract it if it doesn't
if(NOT EXISTS "${PROJECT_SOURCE_DIR}/Vocabulary/ORBvoc.txt")
    message(STATUS "Uncompressing vocabulary ...")
    execute_process(
        COMMAND ${CMAKE_COMMAND} -E tar xzf ORBvoc.txt.tar.gz
        WORKING_DIRECTORY ${PROJECT_SOURCE_DIR}/Vocabulary
    )
    execute_process(
        COMMAND ${CMAKE_COMMAND} -E ls -l
        WORKING_DIRECTORY ${PROJECT_SOURCE_DIR}/Vocabulary
    )
endif()

# Add an option to download the dataset
option(DOWNLOAD_DATASET "Download the EuRoc dataset" OFF)

set(DATASET_DIR "${PROJECT_SOURCE_DIR}/Datasets/EuRoc")

if(EXISTS ${DATASET_DIR})
    message(STATUS "The dataset directory already exists: ${DATASET_DIR}")
else()
    set(DOWNLOAD_DATASET ON)
endif()

if(DOWNLOAD_DATASET)
    message(STATUS "Downloading EuRoc dataset...")

    # Define dataset URLs and target directories
    file(MAKE_DIRECTORY ${DATASET_DIR})

    set(DATASETS
        "MH_01_easy|http://robotics.ethz.ch/~asl-datasets/ijrr_euroc_mav_dataset/machine_hall/MH_01_easy/MH_01_easy.zip"
        "MH_02_easy|http://robotics.ethz.ch/~asl-datasets/ijrr_euroc_mav_dataset/machine_hall/MH_02_easy/MH_02_easy.zip"
        "MH_03_medium|http://robotics.ethz.ch/~asl-datasets/ijrr_euroc_mav_dataset/machine_hall/MH_03_medium/MH_03_medium.zip"
        "MH_04_difficult|http://robotics.ethz.ch/~asl-datasets/ijrr_euroc_mav_dataset/machine_hall/MH_04_difficult/MH_04_difficult.zip"
        "MH_05_difficult|http://robotics.ethz.ch/~asl-datasets/ijrr_euroc_mav_dataset/machine_hall/MH_05_difficult/MH_05_difficult.zip"
        "V1_01_easy|http://robotics.ethz.ch/~asl-datasets/ijrr_euroc_mav_dataset/vicon_room1/V1_01_easy/V1_01_easy.zip"
        "V1_02_medium|http://robotics.ethz.ch/~asl-datasets/ijrr_euroc_mav_dataset/vicon_room1/V1_02_medium/V1_02_medium.zip"
        "V1_03_difficult|http://robotics.ethz.ch/~asl-datasets/ijrr_euroc_mav_dataset/vicon_room1/V1_03_difficult/V1_03_difficult.zip"
        "V2_01_easy|http://robotics.ethz.ch/~asl-datasets/ijrr_euroc_mav_dataset/vicon_room2/V2_01_easy/V2_01_easy.zip"
        "V2_02_medium|http://robotics.ethz.ch/~asl-datasets/ijrr_euroc_mav_dataset/vicon_room2/V2_02_medium/V2_02_medium.zip"
        "V2_03_difficult|http://robotics.ethz.ch/~asl-datasets/ijrr_euroc_mav_dataset/vicon_room2/V2_03_difficult/V2_03_difficult.zip"
    )

    foreach(dataset ${DATASETS})
        string(REPLACE "|" ";" DATASET_INFO ${dataset})
        list(GET DATASET_INFO 0 DATASET_NAME)
        list(GET DATASET_INFO 1 DATASET_URL)

        set(DATASET_PATH "${DATASET_DIR}/${DATASET_NAME}")
        file(MAKE_DIRECTORY ${DATASET_PATH})

        set(ZIP_FILE "${DATASET_PATH}/${DATASET_NAME}.zip")

        # Download the dataset
        execute_process(
            COMMAND wget -O ${ZIP_FILE} ${DATASET_URL}
            RESULT_VARIABLE WGET_RESULT
        )

        if(NOT WGET_RESULT EQUAL 0)
            message(FATAL_ERROR "Failed to download dataset ${DATASET_NAME} from ${DATASET_URL}. Please check your internet connection or the URL.")
        endif()

        # Unzip the dataset
        execute_process(
            COMMAND unzip -o ${ZIP_FILE} -d ${DATASET_PATH}
            RESULT_VARIABLE UNZIP_RESULT
        )

        if(NOT UNZIP_RESULT EQUAL 0)
            message(FATAL_ERROR "Failed to unzip dataset ${DATASET_NAME}. Please make sure 'unzip' is installed and try again.")
        endif()

        # Remove the zip file after extraction
        file(REMOVE ${ZIP_FILE})
    endforeach()

    message(STATUS "EuRoc dataset downloaded successfully.")
endif()

# To clean up the build
# TODO: uncomment one at a time, and fix these!!!
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-conversion-null -Wno-deprecated -Wno-deprecated-declarations -Wno-sign-compare -Wno-unused-but-set-variable -Wno-unused-variable -Wno-reorder -Wno-unused-but-set-variable -Wno-dangling-else -Wno-uninitialized -Wno-maybe-uninitialized -Wno-aggressive-loop-optimizations -Wno-class-memaccess -Wno-unused-local-typedefs -Wno-overloaded-virtual -Wno-array-bounds -Wno-error=array-bounds")

# Set C++ flags based on the build type
if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Og -g")
    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Og -g")
elseif(CMAKE_BUILD_TYPE STREQUAL "Release")
    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS}  -Wall   -O3")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS}  -Wall   -O3")
elseif(CMAKE_BUILD_TYPE STREQUAL "RelWithDebInfo")
    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS}  -Wall   -O2 -g")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2 -g")
elseif(CMAKE_BUILD_TYPE STREQUAL "MinSizeRel")
    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS}  -Wall   -Os")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Os")
endif()

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -march=native")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -march=native")

# Check C++11 or C++0x support
include(CheckCXXCompilerFlag)
CHECK_CXX_COMPILER_FLAG("-std=c++17" COMPILER_SUPPORTS_CXX17)
CHECK_CXX_COMPILER_FLAG("-std=c++14" COMPILER_SUPPORTS_CXX14)
CHECK_CXX_COMPILER_FLAG("-std=c++11" COMPILER_SUPPORTS_CXX11)

if(COMPILER_SUPPORTS_CXX17)
   set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++17")
   message(STATUS "Using flags -std=c++17.")
elseif(COMPILER_SUPPORTS_CXX14)
   set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++14")
   message(STATUS "Using flag -std=c++14.")
elseif(COMPILER_SUPPORTS_CXX11)
   set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11")
   message(STATUS "Using flag -std=c++11.")
else()
   message(FATAL_ERROR "The compiler ${CMAKE_CXX_COMPILER} has no C++17,14,11 support. Please use a different C++ compiler.")
endif()

LIST(APPEND CMAKE_MODULE_PATH ${PROJECT_SOURCE_DIR}/cmake_modules)

# Check for OS type and request user to install libopencv-dev if not installed
if(UNIX AND NOT APPLE)
    # Check for libopencv-dev or opencv-dev
    execute_process(
        COMMAND dpkg -s libopencv-dev
        RESULT_VARIABLE libopencv_installed
        OUTPUT_QUIET
        ERROR_QUIET
    )

    execute_process(
        COMMAND dpkg -s opencv-dev
        RESULT_VARIABLE opencv_dev_installed
        OUTPUT_QUIET
        ERROR_QUIET
    )
    # If neither is installed
    if(NOT libopencv_installed EQUAL 0 AND NOT opencv_dev_installed EQUAL 0)
        message(STATUS "libopencv-dev is not installed. Installing libopencv-dev...")
        
        # Check if the user is root
        execute_process(
            COMMAND id -u
            OUTPUT_VARIABLE USER_ID
            OUTPUT_STRIP_TRAILING_WHITESPACE
        )
        
        if(USER_ID EQUAL 0)
            execute_process(
                COMMAND apt-get update
                COMMAND apt-get install -y libopencv-dev
                RESULT_VARIABLE install_result
            )
        else()
            execute_process(
                COMMAND sudo apt-get update
                COMMAND sudo apt-get install -y libopencv-dev
                RESULT_VARIABLE install_result
            )
        endif()

        if(NOT install_result EQUAL 0)
            message(FATAL_ERROR "Failed to install libopencv-dev. Please install it manually.")
        endif()
    endif()
endif()

find_package(OpenCV 4.4)
if(NOT OpenCV_FOUND)
    message(FATAL_ERROR "OpenCV > 4.4 not found.")
endif()

# Check for OS type and request user to install libeigen3-dev if not installed
if(UNIX AND NOT APPLE)
    execute_process(
        COMMAND dpkg -s libeigen3-dev
        RESULT_VARIABLE eigen_installed
        OUTPUT_QUIET
        ERROR_QUIET
    )
    if(NOT eigen_installed EQUAL 0)
        message(STATUS "libeigen3-dev is not installed. Installing libeigen3-dev...")
        
        # Check if the user is root
        execute_process(
            COMMAND id -u
            OUTPUT_VARIABLE USER_ID
            OUTPUT_STRIP_TRAILING_WHITESPACE
        )
        
        if(USER_ID EQUAL 0)
            execute_process(
            COMMAND apt-get update
            COMMAND apt-get install -y libeigen3-dev
            RESULT_VARIABLE install_result
            )
        else()
            execute_process(
            COMMAND sudo apt-get update
            COMMAND sudo apt-get install -y libeigen3-dev
            RESULT_VARIABLE install_result
            )
        endif()

        if(NOT install_result EQUAL 0)
            message(FATAL_ERROR "Failed to install libeigen3-dev. Please install it manually.")
        endif()
    endif()
endif()

# Check for OS type and request user to install libgl-dev if not installed
if(UNIX AND NOT APPLE)
    execute_process(
        COMMAND dpkg -s libgl-dev
        RESULT_VARIABLE libgl_installed
        OUTPUT_QUIET
        ERROR_QUIET
    )
    if(NOT libgl_installed EQUAL 0)
        message(STATUS "libgl-dev is not installed. Installing libgl-dev...")
        
        # Check if the user is root
        execute_process(
            COMMAND id -u
            OUTPUT_VARIABLE USER_ID
            OUTPUT_STRIP_TRAILING_WHITESPACE
        )
        
        if(USER_ID EQUAL 0)
            execute_process(
                COMMAND apt-get update
                COMMAND apt-get install -y libgl-dev
                RESULT_VARIABLE install_result
            )
        else()
            execute_process(
                COMMAND sudo apt-get update
                COMMAND sudo apt-get install -y libgl-dev
                RESULT_VARIABLE install_result
            )
        endif()

        if(NOT install_result EQUAL 0)
            message(FATAL_ERROR "Failed to install libgl-dev. Please install it manually.")
        endif()
    endif()
endif()

# Check for OS type and request user to install libssl-dev if not installed
if(UNIX AND NOT APPLE)
    execute_process(
        COMMAND dpkg -s libssl-dev
        RESULT_VARIABLE libssl_installed
        OUTPUT_QUIET
        ERROR_QUIET
    )
    if(NOT libssl_installed EQUAL 0)
        message(STATUS "libssl-dev is not installed. Installing libssl-dev...")
        
        # Check if the user is root
        execute_process(
            COMMAND id -u
            OUTPUT_VARIABLE USER_ID
            OUTPUT_STRIP_TRAILING_WHITESPACE
        )
        
        if(USER_ID EQUAL 0)
            execute_process(
                COMMAND apt-get update
                COMMAND apt-get install -y libssl-dev
                RESULT_VARIABLE install_result
            )
        else()
            execute_process(
                COMMAND sudo apt-get update
                COMMAND sudo apt-get install -y libssl-dev
                RESULT_VARIABLE install_result
            )
        endif()

        if(NOT install_result EQUAL 0)
            message(FATAL_ERROR "Failed to install libssl-dev. Please install it manually.")
        endif()
    endif()
endif()

find_package(Eigen3 3.1.0 REQUIRED)

option(GUI "Enable GUI support" OFF)
if(GUI)
    find_package(Pangolin REQUIRED)
    add_definitions(-DGUI)
    include_directories(${Pangolin_INCLUDE_DIRS})
endif()

# Check for OS type and request user to install boost libraries if not installed
if(UNIX AND NOT APPLE)
    execute_process(
        COMMAND dpkg -s libboost-all-dev
        RESULT_VARIABLE boost_installed
        OUTPUT_QUIET
        ERROR_QUIET
    )
    if(NOT boost_installed EQUAL 0)
        message(STATUS "libboost-all-dev is not installed. Installing libboost-all-dev...")
        
        # Check if the user is root
        execute_process(
            COMMAND id -u
            OUTPUT_VARIABLE USER_ID
            OUTPUT_STRIP_TRAILING_WHITESPACE
        )
        
        if(USER_ID EQUAL 0)
            execute_process(
                COMMAND apt-get update
                COMMAND apt-get install -y libboost-all-dev
                RESULT_VARIABLE install_result
            )
        else()
            execute_process(
                COMMAND sudo apt-get update
                COMMAND sudo apt-get install -y libboost-all-dev
                RESULT_VARIABLE install_result
            )
        endif()

        if(NOT install_result EQUAL 0)
            message(FATAL_ERROR "Failed to install libboost-all-dev. Please install it manually.")
        endif()
    endif()
endif()


find_package(realsense2)

include_directories(
${PROJECT_SOURCE_DIR}
${PROJECT_SOURCE_DIR}/include
${PROJECT_SOURCE_DIR}/include/CameraModels
${PROJECT_SOURCE_DIR}/Thirdparty/Sophus
${EIGEN3_INCLUDE_DIR}
)

set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/lib)

# Retrieve the latest commit hash
execute_process(
    COMMAND git rev-parse --short HEAD
    OUTPUT_VARIABLE GIT_COMMIT_HASH
    OUTPUT_STRIP_TRAILING_WHITESPACE
)

# Check if the working directory is dirty (has uncommitted changes)
execute_process(
    COMMAND git diff --quiet --exit-code
    RESULT_VARIABLE IS_DIRTY
)

# Append "-dirty" if there are changes
if(IS_DIRTY EQUAL 1)
    set(GIT_COMMIT_HASH "${GIT_COMMIT_HASH}-dirty")
endif()

# Define the preprocessor macro
add_definitions(-DGIT_COMMIT_HASH=\"${GIT_COMMIT_HASH}\")

message(STATUS "Updated GIT_COMMIT_HASH = ${GIT_COMMIT_HASH}")

add_library(${PROJECT_NAME} SHARED
src/System.cc
src/Tracking.cc
src/LocalMapping.cc
src/LoopClosing.cc
src/ORBextractor.cc
src/ORBmatcher.cc
src/FrameDrawer.cc
src/Converter.cc
src/MapPoint.cc
src/KeyFrame.cc
src/Atlas.cc
src/Map.cc
src/MapDrawer.cc
src/Optimizer.cc
src/Frame.cc
src/KeyFrameDatabase.cc
src/Sim3Solver.cc
src/Viewer.cc
src/ImuTypes.cc
src/G2oTypes.cc
src/CameraModels/Pinhole.cpp
src/CameraModels/KannalaBrandt8.cpp
src/OptimizableTypes.cpp
src/MLPnPsolver.cpp
src/GeometricTools.cc
src/TwoViewReconstruction.cc
src/Config.cc
src/Settings.cc
src/CellManager.cc
include/System.h
include/Tracking.h
include/LocalMapping.h
include/LoopClosing.h
include/ORBextractor.h
include/ORBmatcher.h
include/FrameDrawer.h
include/Converter.h
include/MapPoint.h
include/KeyFrame.h
include/Atlas.h
include/Map.h
include/MapDrawer.h
include/Optimizer.h
include/Frame.h
include/KeyFrameDatabase.h
include/Sim3Solver.h
include/Viewer.h
include/ImuTypes.h
include/G2oTypes.h
include/CameraModels/GeometricCamera.h
include/CameraModels/Pinhole.h
include/CameraModels/KannalaBrandt8.h
include/OptimizableTypes.h
include/MLPnPsolver.h
include/GeometricTools.h
include/TwoViewReconstruction.h
include/SerializationUtils.h
include/Config.h
include/Settings.h
include/CellManager.h
)

# Add DBoW2 library
add_subdirectory(${PROJECT_SOURCE_DIR}/Thirdparty/DBoW2)
include_directories(${PROJECT_SOURCE_DIR}/Thirdparty/DBoW2/include)

# Add g2o library
add_subdirectory(${PROJECT_SOURCE_DIR}/Thirdparty/g2o)
include_directories(${PROJECT_SOURCE_DIR}/Thirdparty/g2o)

# Add target libraries, thirdparty libraries, and OpenCV libraries, and boost serialization
target_link_libraries(
    ${PROJECT_NAME}
    ${OpenCV_LIBS}
    ${EIGEN3_LIBS}
    DBoW2
    g2o
    -lboost_serialization
    -lcrypto
)

if(GUI)
    target_link_libraries(${PROJECT_NAME} ${Pangolin_LIBRARIES})
endif()

# If RealSense SDK is found the library is added and its examples compiled
if(realsense2_FOUND)
    include_directories(${PROJECT_NAME}
    ${realsense_INCLUDE_DIR}
    )
    target_link_libraries(${PROJECT_NAME}
    ${realsense2_LIBRARY}
    )
endif()

# Added Settings for Metrics Keeping
add_definitions(-DREGISTER_TIMES)
add_definitions(-DOASIS)

# Build examples

# RGB-D examples
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/Examples/RGB-D)

add_executable(rgbd_tum
        Examples/RGB-D/rgbd_tum.cc)
target_link_libraries(rgbd_tum ${PROJECT_NAME})

if(realsense2_FOUND)
    add_executable(rgbd_realsense_D435i
            Examples/RGB-D/rgbd_realsense_D435i.cc)
    target_link_libraries(rgbd_realsense_D435i ${PROJECT_NAME})
endif()


# RGB-D inertial examples
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/Examples/RGB-D-Inertial)

if(realsense2_FOUND)
    add_executable(rgbd_inertial_realsense_D435i
            Examples/RGB-D-Inertial/rgbd_inertial_realsense_D435i.cc)
    target_link_libraries(rgbd_inertial_realsense_D435i ${PROJECT_NAME})
endif()

#Stereo examples
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/Examples/Stereo)

add_executable(stereo_kitti
        Examples/Stereo/stereo_kitti.cc)
target_link_libraries(stereo_kitti ${PROJECT_NAME})

add_executable(stereo_euroc
        Examples/Stereo/stereo_euroc.cc)
target_link_libraries(stereo_euroc ${PROJECT_NAME})

add_executable(stereo_tum_vi
        Examples/Stereo/stereo_tum_vi.cc)
target_link_libraries(stereo_tum_vi ${PROJECT_NAME})

if(realsense2_FOUND)
    add_executable(stereo_realsense_t265
            Examples/Stereo/stereo_realsense_t265.cc)
    target_link_libraries(stereo_realsense_t265 ${PROJECT_NAME})

    add_executable(stereo_realsense_D435i
            Examples/Stereo/stereo_realsense_D435i.cc)
    target_link_libraries(stereo_realsense_D435i ${PROJECT_NAME})
endif()

#Monocular examples
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/Examples/Monocular)

add_executable(mono_tum
        Examples/Monocular/mono_tum.cc)
target_link_libraries(mono_tum ${PROJECT_NAME})

add_executable(mono_kitti
        Examples/Monocular/mono_kitti.cc)
target_link_libraries(mono_kitti ${PROJECT_NAME})

add_executable(mono_euroc
        Examples/Monocular/mono_euroc.cc)
target_link_libraries(mono_euroc ${PROJECT_NAME})

add_executable(mono_tum_vi
        Examples/Monocular/mono_tum_vi.cc)
target_link_libraries(mono_tum_vi ${PROJECT_NAME})

if(realsense2_FOUND)
    add_executable(mono_realsense_t265
            Examples/Monocular/mono_realsense_t265.cc)
    target_link_libraries(mono_realsense_t265 ${PROJECT_NAME})

    add_executable(mono_realsense_D435i
            Examples/Monocular/mono_realsense_D435i.cc)
    target_link_libraries(mono_realsense_D435i ${PROJECT_NAME})
endif()

#Monocular inertial examples
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/Examples/Monocular-Inertial)

add_executable(mono_inertial_euroc
        Examples/Monocular-Inertial/mono_inertial_euroc.cc)
target_link_libraries(mono_inertial_euroc ${PROJECT_NAME})

add_executable(mono_inertial_tum_vi
        Examples/Monocular-Inertial/mono_inertial_tum_vi.cc)
target_link_libraries(mono_inertial_tum_vi ${PROJECT_NAME})

if(realsense2_FOUND)
    add_executable(mono_inertial_realsense_t265
            Examples/Monocular-Inertial/mono_inertial_realsense_t265.cc)
    target_link_libraries(mono_inertial_realsense_t265 ${PROJECT_NAME})

    add_executable(mono_inertial_realsense_D435i
            Examples/Monocular-Inertial/mono_inertial_realsense_D435i.cc)
    target_link_libraries(mono_inertial_realsense_D435i ${PROJECT_NAME})
endif()

#Stereo Inertial examples
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/Examples/Stereo-Inertial)

add_executable(stereo_inertial_euroc
        Examples/Stereo-Inertial/stereo_inertial_euroc.cc)
target_link_libraries(stereo_inertial_euroc ${PROJECT_NAME})

add_executable(stereo_inertial_tum_vi
        Examples/Stereo-Inertial/stereo_inertial_tum_vi.cc)
target_link_libraries(stereo_inertial_tum_vi ${PROJECT_NAME})

if(realsense2_FOUND)
    add_executable(stereo_inertial_realsense_t265
            Examples/Stereo-Inertial/stereo_inertial_realsense_t265.cc)
    target_link_libraries(stereo_inertial_realsense_t265 ${PROJECT_NAME})

    add_executable(stereo_inertial_realsense_D435i
            Examples/Stereo-Inertial/stereo_inertial_realsense_D435i.cc)
    target_link_libraries(stereo_inertial_realsense_D435i ${PROJECT_NAME})
endif()

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/Examples/Calibration)
if(realsense2_FOUND)
    add_executable(recorder_realsense_D435i
            Examples/Calibration/recorder_realsense_D435i.cc)
    target_link_libraries(recorder_realsense_D435i ${PROJECT_NAME})

    add_executable(recorder_realsense_T265
            Examples/Calibration/recorder_realsense_T265.cc)
    target_link_libraries(recorder_realsense_T265 ${PROJECT_NAME})
endif()

#Old examples

# RGB-D examples
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/Examples_old/RGB-D)

add_executable(rgbd_tum_old
        Examples_old/RGB-D/rgbd_tum.cc)
target_link_libraries(rgbd_tum_old ${PROJECT_NAME})

if(realsense2_FOUND)
    add_executable(rgbd_realsense_D435i_old
            Examples_old/RGB-D/rgbd_realsense_D435i.cc)
    target_link_libraries(rgbd_realsense_D435i_old ${PROJECT_NAME})
endif()


# RGB-D inertial examples
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/Examples_old/RGB-D-Inertial)

if(realsense2_FOUND)
    add_executable(rgbd_inertial_realsense_D435i_old
            Examples_old/RGB-D-Inertial/rgbd_inertial_realsense_D435i.cc)
    target_link_libraries(rgbd_inertial_realsense_D435i_old ${PROJECT_NAME})
endif()

#Stereo examples
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/Examples_old/Stereo)

add_executable(stereo_kitti_old
        Examples_old/Stereo/stereo_kitti.cc)
target_link_libraries(stereo_kitti_old ${PROJECT_NAME})

add_executable(stereo_euroc_old
        Examples_old/Stereo/stereo_euroc.cc)
target_link_libraries(stereo_euroc_old ${PROJECT_NAME})

add_executable(stereo_tum_vi_old
        Examples_old/Stereo/stereo_tum_vi.cc)
target_link_libraries(stereo_tum_vi_old ${PROJECT_NAME})

if(realsense2_FOUND)
    add_executable(stereo_realsense_t265_old
            Examples_old/Stereo/stereo_realsense_t265.cc)
    target_link_libraries(stereo_realsense_t265_old ${PROJECT_NAME})

    add_executable(stereo_realsense_D435i_old
            Examples_old/Stereo/stereo_realsense_D435i.cc)
    target_link_libraries(stereo_realsense_D435i_old ${PROJECT_NAME})
endif()

#Monocular examples
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/Examples_old/Monocular)

add_executable(mono_tum_old
        Examples_old/Monocular/mono_tum.cc)
target_link_libraries(mono_tum_old ${PROJECT_NAME})

add_executable(mono_kitti_old
        Examples_old/Monocular/mono_kitti.cc)
target_link_libraries(mono_kitti_old ${PROJECT_NAME})

add_executable(mono_euroc_old
        Examples_old/Monocular/mono_euroc.cc)
target_link_libraries(mono_euroc_old ${PROJECT_NAME})

add_executable(mono_tum_vi_old
        Examples_old/Monocular/mono_tum_vi.cc)
target_link_libraries(mono_tum_vi_old ${PROJECT_NAME})

if(realsense2_FOUND)
    add_executable(mono_realsense_t265_old
            Examples_old/Monocular/mono_realsense_t265.cc)
    target_link_libraries(mono_realsense_t265_old ${PROJECT_NAME})

    add_executable(mono_realsense_D435i_old
            Examples_old/Monocular/mono_realsense_D435i.cc)
    target_link_libraries(mono_realsense_D435i_old ${PROJECT_NAME})
endif()

#Monocular inertial examples
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/Examples_old/Monocular-Inertial)

add_executable(mono_inertial_euroc_old
        Examples_old/Monocular-Inertial/mono_inertial_euroc.cc)
target_link_libraries(mono_inertial_euroc_old ${PROJECT_NAME})

add_executable(mono_inertial_tum_vi_old
        Examples_old/Monocular-Inertial/mono_inertial_tum_vi.cc)
target_link_libraries(mono_inertial_tum_vi_old ${PROJECT_NAME})

if(realsense2_FOUND)
    add_executable(mono_inertial_realsense_t265_old
            Examples_old/Monocular-Inertial/mono_inertial_realsense_t265.cc)
    target_link_libraries(mono_inertial_realsense_t265_old ${PROJECT_NAME})

    add_executable(mono_inertial_realsense_D435i_old
            Examples_old/Monocular-Inertial/mono_inertial_realsense_D435i.cc)
    target_link_libraries(mono_inertial_realsense_D435i_old ${PROJECT_NAME})
endif()

#Stereo Inertial examples
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/Examples_old/Stereo-Inertial)

add_executable(stereo_inertial_euroc_old
        Examples_old/Stereo-Inertial/stereo_inertial_euroc.cc)
target_link_libraries(stereo_inertial_euroc_old ${PROJECT_NAME})

add_executable(stereo_inertial_tum_vi_old
        Examples_old/Stereo-Inertial/stereo_inertial_tum_vi.cc)
target_link_libraries(stereo_inertial_tum_vi_old ${PROJECT_NAME})

if(realsense2_FOUND)
    add_executable(stereo_inertial_realsense_t265_old
            Examples_old/Stereo-Inertial/stereo_inertial_realsense_t265.cc)
    target_link_libraries(stereo_inertial_realsense_t265_old ${PROJECT_NAME})

    add_executable(stereo_inertial_realsense_D435i_old
            Examples_old/Stereo-Inertial/stereo_inertial_realsense_D435i.cc)
    target_link_libraries(stereo_inertial_realsense_D435i_old ${PROJECT_NAME})
endif()
