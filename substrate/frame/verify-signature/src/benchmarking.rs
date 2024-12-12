// This file is part of Substrate.

// Copyright (C) Parity Technologies (UK) Ltd.
// SPDX-License-Identifier: Apache-2.0

// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// 	http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

//! Benchmarks for Verify Signature Pallet

#![cfg(feature = "runtime-benchmarks")]

extern crate alloc;
use super::*;
use frame::benchmarking::prelude::{*, frame_system::Call as SystemCall};

#[allow(unused)]
use crate::{extension::VerifySignature, Config, Pallet as VerifySignaturePallet};
use alloc::vec;

pub trait BenchmarkHelper<Signature, Signer> {
	fn create_signature(entropy: &[u8], msg: &[u8]) -> (Signature, Signer);
}

#[benchmarks(where
	T: Config + Send + Sync,
	T::RuntimeCall: Dispatchable<Info = DispatchInfo> + GetDispatchInfo,
	T::RuntimeOrigin: frame::traits::AsTransactionAuthorizedOrigin,
)]
mod benchmarks {
	use super::*;
	use frame::traits::DispatchTransaction;

	#[benchmark]
	fn verify_signature() -> Result<(), BenchmarkError> {
		let entropy = [42u8; 256];
		let call: T::RuntimeCall = SystemCall::remark { remark: vec![] }.into();
		let ext_version: frame::deps::sp_runtime::generic::ExtensionVersion = 0;
		let info = call.get_dispatch_info();
		let msg = (ext_version, &call).using_encoded(blake2_256).to_vec();
		let (signature, signer) = T::BenchmarkHelper::create_signature(&entropy, &msg[..]);
		let ext = VerifySignature::<T>::new_with_signature(signature, signer);

		#[block]
		{
			assert!(ext
				.validate_only(
					RawOrigin::None.into(),
					&call,
					&info,
					0,
					TransactionSource::External,
					ext_version
				)
				.is_ok());
		}

		Ok(())
	}

	impl_benchmark_test_suite!(Pallet, crate::tests::new_test_ext(), crate::tests::Test);
}
