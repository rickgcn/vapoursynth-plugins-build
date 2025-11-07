# CMake toolchain file for x86_64-unknown-linux-gnu cross-compilation
# Platform: linux-x86_64-glibc
# Usage: cmake -DCMAKE_TOOLCHAIN_FILE=/path/to/this/file ..

set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR x86_64)

# Set the compiler
set(CMAKE_C_COMPILER x86_64-unknown-linux-gnu-gcc)
set(CMAKE_CXX_COMPILER x86_64-unknown-linux-gnu-g++)

# Set the tools
set(CMAKE_AR x86_64-unknown-linux-gnu-ar)
set(CMAKE_RANLIB x86_64-unknown-linux-gnu-ranlib)
set(CMAKE_STRIP x86_64-unknown-linux-gnu-strip)
set(CMAKE_NM x86_64-unknown-linux-gnu-nm)
set(CMAKE_OBJCOPY x86_64-unknown-linux-gnu-objcopy)
set(CMAKE_OBJDUMP x86_64-unknown-linux-gnu-objdump)
set(CMAKE_SIZE x86_64-unknown-linux-gnu-size)

# Set the linker
set(CMAKE_LINKER x86_64-unknown-linux-gnu-ld)

# Set compiler configuration
set(CMAKE_C_COMPILER_ID "GNU")
set(CMAKE_C_COMPILER_VERSION "11.5.0")
set(CMAKE_CXX_COMPILER_ID "GNU")
set(CMAKE_CXX_COMPILER_VERSION "11.5.0")

# For CMake versions that need explicit configuration
if(CMAKE_VERSION VERSION_LESS "3.21")
    set(CMAKE_C_COMPILER_FORCED TRUE)
    set(CMAKE_CXX_COMPILER_FORCED TRUE)
endif()

# Set sysroot path
# Location: ~/x-tools/x86_64-unknown-linux-gnu/x86_64-unknown-linux-gnu/sysroot
set(CMAKE_SYSROOT /home/runner/x-tools/x86_64-unknown-linux-gnu/x86_64-unknown-linux-gnu/sysroot)

# Add sysroot to compile flags
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} --sysroot=${CMAKE_SYSROOT}")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} --sysroot=${CMAKE_SYSROOT}")

# Look for programs in the build host directories
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
# Search for libraries and headers in the target environment
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
