cmake_minimum_required(VERSION 3.16)
project(pea_i_upc LANGUAGES CXX)

add_executable(pea_cpp src/cpp/Taller2_XX.cpp)
target_compile_features(pea_cpp PRIVATE cxx_std_17)
set_target_properties(pea_cpp PROPERTIES CXX_EXTENSIONS OFF)
if(MSVC)
    target_compile_options(pea_cpp PRIVATE /W4 /utf-8)
else()
    target_compile_options(pea_cpp PRIVATE -Wall -Wextra -Wpedantic)
endif()

enable_testing()
add_test(NAME pea_cpp_core COMMAND pea_cpp --self-test)

find_package(Python3 3.10 COMPONENTS Interpreter QUIET)
if(Python3_Interpreter_FOUND)
    foreach(check IN ITEMS check_cpp_cli check_interop check_backend)
        add_test(
            NAME ${check}
            COMMAND ${Python3_EXECUTABLE}
                    ${CMAKE_SOURCE_DIR}/tests/integration/${check}.py
                    $<TARGET_FILE:pea_cpp>
        )
    endforeach()
endif()
