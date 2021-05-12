#!/usr/bin/env bash

###############################################################################
# Copyright (c) 2017-21, Lawrence Livermore National Security, LLC
# and RAJA project contributors. See the RAJAPerf/COPYRIGHT file for details.
#
# SPDX-License-Identifier: (BSD-3-Clause)
###############################################################################

if [ "$1" == "" ]; then
  echo
  echo "You must pass a compiler version number to script. For example,"
  echo "    blueos_gcc.sh 8.3.1"
  exit
fi

COMP_VER=$1

BUILD_SUFFIX=lc_blueos-gcc-${COMP_VER}
RAJA_HOSTCONFIG=../tpl/RAJA/host-configs/lc-builds/blueos/gcc_X.cmake

echo
echo "Creating build directory ${BUILD_SUFFIX} and generating configuration in it"
echo

rm -rf build_${BUILD_SUFFIX} 2>/dev/null
mkdir build_${BUILD_SUFFIX} && cd build_${BUILD_SUFFIX}

module load cmake/3.14.5

cmake \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CXX_COMPILER=/usr/tce/packages/gcc/gcc-${COMP_VER}/bin/g++ \
  -C ${RAJA_HOSTCONFIG} \
  -DENABLE_OPENMP=On \
  -DCMAKE_INSTALL_PREFIX=../install_${BUILD_SUFFIX} \
  "$@" \
  .. 

echo
echo "***********************************************************************"
echo "cd into directory ${BUILD_SUFFIX} and run make to build RAJA Perf Suite"
echo "***********************************************************************"
