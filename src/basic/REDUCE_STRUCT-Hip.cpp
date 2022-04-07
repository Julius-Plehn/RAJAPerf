//~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~//
// Copyright (c) 2017-21, Lawrence Livermore National Security, LLC
// and RAJA Performance Suite project contributors.
// See the RAJAPerf/LICENSE file for details.
//
// SPDX-License-Identifier: (BSD-3-Clause)
//~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~//

#include "REDUCE_STRUCT.hpp"

#include "RAJA/RAJA.hpp"

#if defined(RAJA_ENABLE_HIP)

#include "common/HipDataUtils.hpp"

#include <iostream>

namespace rajaperf
{
namespace basic
{


#define REDUCE_STRUCT_DATA_SETUP_HIP \
  allocAndInitHipDeviceData(particles.x, m_x, particles.N); \
  allocAndInitHipDeviceData(particles.y, m_y, particles.N); \
  
#define REDUCE_STRUCT_DATA_TEARDOWN_HIP \
  deallocHipDeviceData(particles.x); \
  deallocHipDeviceData(particles.y); 

template < size_t block_size >
__launch_bounds__(block_size)
__global__ void reduce_struct(Real_ptr x, Real_ptr y,
                              Real_ptr xsum, Real_ptr xmin, Real_ptr xmax, 
                              Real_ptr ysum, Real_ptr ymin, Real_ptr ymax, 
                              Index_type iend)
{

  //x
  HIP_DYNAMIC_SHARED( Real_type, shared)
  Real_type* pxsum = (Real_type*)&shared[ 0 * blockDim.x ];
  Real_type* pxmin = (Real_type*)&shared[ 1 * blockDim.x ];
  Real_type* pxmax = (Real_type*)&shared[ 2 * blockDim.x ];
  //y
  Real_type* pysum = (Real_type*)&shared[ 3 * blockDim.x ];
  Real_type* pymin = (Real_type*)&shared[ 4 * blockDim.x ];
  Real_type* pymax = (Real_type*)&shared[ 5 * blockDim.x ];

  Index_type i = blockIdx.x * blockDim.x + threadIdx.x;

  //x
  pxsum[ threadIdx.x ] = 0.0;
  pxmin[ threadIdx.x ] = std::numeric_limits<Int_type>::max();
  pxmax[ threadIdx.x ] = std::numeric_limits<Int_type>::min();
  //y
  pysum[ threadIdx.x ] = 0.0;
  pymin[ threadIdx.x ] = std::numeric_limits<Int_type>::max();
  pymax[ threadIdx.x ] = std::numeric_limits<Int_type>::min();


  for ( ; i < iend ; i += gridDim.x * blockDim.x ) {
	//x
    pxsum[ threadIdx.x ] += x[ i ];
    pxmin[ threadIdx.x ] = RAJA_MIN( pxmin[ threadIdx.x ], x[ i ] );
    pxmax[ threadIdx.x ] = RAJA_MAX( pxmax[ threadIdx.x ], x[ i ] );
	//y
    pysum[ threadIdx.x ] += y[ i ];
    pymin[ threadIdx.x ] = RAJA_MIN( pymin[ threadIdx.x ], y[ i ] );
    pymax[ threadIdx.x ] = RAJA_MAX( pymax[ threadIdx.x ], y[ i ] );

  }
  __syncthreads();

  for ( i = blockDim.x / 2; i > 0; i /= 2 ) {
    if ( threadIdx.x < i ) {
	  //x
      pxsum[ threadIdx.x ] += pxsum[ threadIdx.x + i ];
      pxmin[ threadIdx.x ] = RAJA_MIN( pxmin[ threadIdx.x ], pxmin[ threadIdx.x + i ] );
      pxmax[ threadIdx.x ] = RAJA_MAX( pxmax[ threadIdx.x ], pxmax[ threadIdx.x + i ] );
	  //y
      pysum[ threadIdx.x ] += pysum[ threadIdx.x + i ];
      pymin[ threadIdx.x ] = RAJA_MIN( pymin[ threadIdx.x ], pymin[ threadIdx.x + i ] );
      pymax[ threadIdx.x ] = RAJA_MAX( pymax[ threadIdx.x ], pymax[ threadIdx.x + i ] );

    }
     __syncthreads();
  }

// serialized access to shared data;
  if ( threadIdx.x == 0 ) {
    RAJA::atomicAdd<RAJA::hip_atomic>( xsum, pxsum[ 0 ] );
    RAJA::atomicMin<RAJA::hip_atomic>( xmin, pxmin[ 0 ] );
    RAJA::atomicMax<RAJA::hip_atomic>( xmax, pxmax[ 0 ] );

    RAJA::atomicAdd<RAJA::hip_atomic>( ysum, pysum[ 0 ] );
    RAJA::atomicMin<RAJA::hip_atomic>( ymin, pymin[ 0 ] );
    RAJA::atomicMax<RAJA::hip_atomic>( ymax, pymax[ 0 ] );
  }
}


template < size_t block_size >
void REDUCE_STRUCT::runHipVariantImpl(VariantID vid)
{
  const Index_type run_reps = getRunReps();
  const Index_type ibegin = 0;
  const Index_type iend = getActualProblemSize();

  REDUCE_STRUCT_DATA_SETUP;

  if ( vid == Base_HIP ) {

    REDUCE_STRUCT_DATA_SETUP_HIP;

	Real_ptr mem; //xcenter,xmin,xmax,ycenter,ymin,ymax
	allocHipDeviceData(mem,6);

    startTimer();
    for (RepIndex_type irep = 0; irep < run_reps; ++irep) {

      hipErrchk(hipMemsetAsync(mem, 0.0, 6*sizeof(Real_type)));
      const size_t grid_size = RAJA_DIVIDE_CEILING_INT(iend, block_size);
      hipLaunchKernelGGL((reduce_struct<block_size>), dim3(grid_size), dim3(block_size), 6*sizeof(Real_type)*block_size, 0,
	                                                  particles.x, particles.y,
							  mem,  mem+1,mem+2, //xcenter,xmin,xmax
							  mem+3,mem+4,mem+5, //ycenter,ymin,ymax
							  particles.N);

      hipErrchk( hipGetLastError() );

      Real_type lmem[6]={0.0, 0.0, 0.0, 0.0, 0.0, 0.0};
      Real_ptr plmem = &lmem[0];
      getHipDeviceData(plmem, mem, 6);

      particles.SetCenter(lmem[0]/particles.N,lmem[3]/particles.N);
      particles.SetXMin(lmem[1]);
      particles.SetXMax(lmem[2]);
      particles.SetYMin(lmem[4]);
      particles.SetYMax(lmem[5]);
      m_particles=particles;
    }
    stopTimer();

    REDUCE_STRUCT_DATA_TEARDOWN_HIP;

    deallocHipDeviceData(mem);

  } else if ( vid == RAJA_HIP ) {

    REDUCE_STRUCT_DATA_SETUP_HIP;

    startTimer();
    for (RepIndex_type irep = 0; irep < run_reps; ++irep) {

      RAJA::ReduceSum<RAJA::hip_reduce, Real_type> xsum(0.0), ysum(0.0);
      RAJA::ReduceMin<RAJA::hip_reduce, Real_type> xmin(0.0), ymin(0.0);
      RAJA::ReduceMax<RAJA::hip_reduce, Real_type> xmax(0.0), ymax(0.0);

      RAJA::forall< RAJA::hip_exec<block_size, true /*async*/> >(
      RAJA::RangeSegment(ibegin, iend), [=] __device__ (Index_type i) {
      REDUCE_STRUCT_BODY_RAJA;
      });


      particles.SetCenter(static_cast<Real_type>(xsum.get()/(particles.N)),ysum.get()/(particles.N));
      particles.SetXMin(static_cast<Real_type>(xmin.get())); particles.SetXMax(static_cast<Real_type>(xmax.get()));
      particles.SetYMin(static_cast<Real_type>(ymin.get())); particles.SetYMax(static_cast<Real_type>(ymax.get()));
      m_particles=particles;
    }
    stopTimer();

    REDUCE_STRUCT_DATA_TEARDOWN_HIP;

  } else {
     getCout() << "\n  REDUCE_STRUCT : Unknown Hip variant id = " << vid << std::endl;
  }
}
	RAJAPERF_GPU_BLOCK_SIZE_TUNING_DEFINE_BIOLERPLATE(REDUCE_STRUCT, Hip)	
} // end namespace basic
} // end namespace rajaperf

#endif  // RAJA_ENABLE_HIP