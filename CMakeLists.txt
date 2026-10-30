cmake_minimum_required(VERSION 4.0)

find_package(cmake-bare REQUIRED PATHS node_modules/cmake-bare)
find_package(cmake-fetch REQUIRED PATHS node_modules/cmake-fetch)

project(bare_kit_python C)

fetch_package("github:holepunchto/bare-kit@3.0.1")

add_custom_target(bare_kit_python ALL DEPENDS bare::kit::shared)

bare_target(target)

install(
  TARGETS bare_kit_shared
  LIBRARY DESTINATION ${target}
  RUNTIME DESTINATION ${target}
)
