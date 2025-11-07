# CMake toolchain file for x86_64-unknown-linux-musl cross-compilation
# Platform: linux-x86_64-musl
# Usage: cmake -DCMAKE_TOOLCHAIN_FILE=/path/to/this/file ..

set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR x86_64)

# Set the compiler
set(CMAKE_C_COMPILER x86_64-unknown-linux-musl-gcc)
set(CMAKE_CXX_COMPILER x86_64-unknown-linux-musl-g++)

# Set the tools
set(CMAKE_AR x86_64-unknown-linux-musl-ar)
set(CMAKE_RANLIB x86_64-unknown-linux-musl-ranlib)
set(CMAKE_STRIP x86_64-unknown-linux-musl-strip)
set(CMAKE_NM x86_64-unknown-linux-musl-nm)
set(CMAKE_OBJCOPY x86_64-unknown-linux-musl-objcopy)
set(CMAKE_OBJDUMP x86_64-unknown-linux-musl-objdump)
set(CMAKE_SIZE x86_64-unknown-linux-musl-size)

# Set the linker
set(CMAKE_LINKER x86_64-unknown-linux-musl-ld)

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
# Location: ~/x-tools/x86_64-unknown-linux-musl/x86_64-unknown-linux-musl/sysroot
set(CMAKE_SYSROOT /home/runner/x-tools/x86_64-unknown-linux-musl/x86_64-unknown-linux-musl/sysroot)

# Add sysroot to compile flags
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} --sysroot=${CMAKE_SYSROOT}")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} --sysroot=${CMAKE_SYSROOT}")

# Look for programs in the build host directories
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
# Search for libraries and headers in the target environment
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
